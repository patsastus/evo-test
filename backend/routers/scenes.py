import base64
import binascii
import io
import logging
import random
import threading
import time
import uuid

from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from PIL import Image, UnidentifiedImageError

from config import MAX_IMAGE_BYTES, MAX_IMAGE_DIM, MAX_RUN_SECONDS, MAX_TOTAL_NODES
from models import (
    AttractorPoint,
    ExportObjRequest,
    Fitness,
    GenerateResponse,
    GenerateScenesRequest,
    GenerationStats,
    SceneData,
    TargetShadow,
    TreeGenome,
    TreeNode,
)
from mesh import build_scene_mesh, mesh_report
from scene import _export_to_obj
from sca import _generate_uuid, grow_tree
from shadow import _generate_shadow_image, calculate_fitness
from voxel import _calculate_intersection_volume

logger = logging.getLogger(__name__)

router = APIRouter()

# In-flight generate requests, so an abort only affects the request(s) it targets.
_active_requests: dict[str, threading.Event] = {}
_active_lock = threading.Lock()


@router.post("/scenes/abort")
def abort_generation(request_id: str | None = None):
    """Abort one in-flight generation by id, or all of them if no id is given."""
    with _active_lock:
        targets = (
            list(_active_requests.values())
            if request_id is None
            else [e for rid, e in _active_requests.items() if rid == request_id]
        )
    for event in targets:
        event.set()
    return {"aborted": True, "requests_aborted": len(targets)}


def _subsample_attractors(
    attractors: list[AttractorPoint], drop_rate: float, seed: int
) -> list[AttractorPoint]:
    rng = random.Random(seed)
    return [a for a in attractors if rng.random() >= drop_rate]


def _validated_image_size(target: TargetShadow, index: int) -> tuple[int, int]:
    """Decode a target image just far enough to validate it; return (width, height)."""
    data = target.imageData
    if data.startswith("data:"):
        if "," not in data:
            raise HTTPException(422, f"targetShadows[{index}]: malformed data URL")
        data = data.split(",", 1)[1]
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(422, f"targetShadows[{index}]: invalid base64")
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(
            413, f"targetShadows[{index}]: image larger than {MAX_IMAGE_BYTES} bytes"
        )
    try:
        with Image.open(io.BytesIO(raw)) as img:
            width, height = img.size
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(422, f"targetShadows[{index}]: not a valid image")
    if not (2 <= width <= MAX_IMAGE_DIM and 1 <= height <= MAX_IMAGE_DIM):
        raise HTTPException(
            422,
            f"targetShadows[{index}]: size {width}x{height} outside 2..{MAX_IMAGE_DIM}",
        )
    return width, height


def _make_scene(
    trees: list[TreeNode],
    request: GenerateScenesRequest,
    ref_width: int,
    ref_height: int,
    generation: int,
) -> SceneData:
    shadow_url = _generate_shadow_image(trees, ref_width, ref_height)
    shadow_match, printability = calculate_fitness(
        trees, request.targetShadows, ref_width, ref_height
    )
    return SceneData(
        id=_generate_uuid(),
        trees=trees,
        fitness=Fitness(printability=printability, shadowMatch=shadow_match),
        shadowImageUrl=shadow_url,
        generation=generation,
        timestamp=int(time.time() * 1000),
    )


def _grow_until_complete(
    start_attractors: list[AttractorPoint],
    repulsion_points: list[AttractorPoint],
    genome: TreeGenome,
    existing_nodes: list[TreeNode] | None,
    request: GenerateScenesRequest,
    total_attractors: int,
    aborted: threading.Event,
    deadline: float,
) -> tuple[list[TreeNode], GenerationStats]:
    all_nodes = list(existing_nodes) if existing_nodes else []
    current = start_attractors
    total_grown = 0
    stats: GenerationStats | None = None
    consecutive_no_progress = 0

    def make_stats(reason: str, remaining: list[AttractorPoint], exhausted=False):
        return GenerationStats(
            attractors_exhausted=exhausted,
            remaining_attractors=len(remaining),
            total_attractors=total_attractors,
            nodes_grown=total_grown,
            growth_stopped_reason=reason,
            remaining_attractors_points=remaining,
        )

    for iteration in range(1, 101):
        if not current:
            break
        if aborted.is_set():
            return all_nodes, make_stats("aborted", current)
        if len(all_nodes) >= MAX_TOTAL_NODES:
            return all_nodes, make_stats("node_limit", current)
        if time.monotonic() >= deadline:
            return all_nodes, make_stats("time_limit", current)

        # Same genome throughout; only the RNG seed varies per iteration.
        iteration_genome = genome.model_copy(
            update={"random_seed": genome.random_seed + iteration}
        )
        budget = min(request.max_new_nodes, MAX_TOTAL_NODES - len(all_nodes))
        all_nodes, step_stats, remaining = grow_tree(
            current,
            request.params.treeCount,
            repulsion_points,
            genome=iteration_genome,
            existing_nodes=all_nodes or None,
            max_new_nodes=budget,
        )
        total_grown += step_stats.nodes_grown
        stats = make_stats(
            step_stats.growth_stopped_reason,
            remaining,
            exhausted=step_stats.attractors_exhausted,
        )

        if step_stats.attractors_exhausted or not remaining:
            break
        if step_stats.nodes_grown == 0:
            consecutive_no_progress += 1
            if consecutive_no_progress >= 3:
                return all_nodes, make_stats("unreachable_attractors", remaining)
        else:
            consecutive_no_progress = 0
        current = remaining

    return all_nodes, stats or make_stats("no_attractors", current)


@router.post("/scenes/generate", response_model=GenerateResponse)
def generate_scenes(request: GenerateScenesRequest):
    request_id = request.request_id or uuid.uuid4().hex
    aborted = threading.Event()
    with _active_lock:
        if request_id in _active_requests:
            raise HTTPException(409, f"request_id {request_id!r} is already running")
        _active_requests[request_id] = aborted

    try:
        return _generate(request, aborted)
    finally:
        with _active_lock:
            _active_requests.pop(request_id, None)


def _generate(
    request: GenerateScenesRequest, aborted: threading.Event
) -> GenerateResponse:
    sizes = [_validated_image_size(t, i) for i, t in enumerate(request.targetShadows)]
    ref_width, ref_height = sizes[0]

    has_parent = bool(request.parent_nodes)
    parent_generation = request.parent_generation or 0
    generation = parent_generation + 1 if has_parent else 0
    logger.info(
        "generate: count=%d parent_nodes=%d remaining_attractors=%d image=%dx%d",
        request.count,
        len(request.parent_nodes or []),
        len(request.remaining_attractors or []),
        ref_width,
        ref_height,
    )

    computed_attractors, repulsion_points = _calculate_intersection_volume(
        request.targetShadows
    )
    attractors = (
        request.remaining_attractors
        if request.remaining_attractors
        else computed_attractors
    )
    total_attractors = len(attractors)
    genome = request.parent_genome or TreeGenome()
    existing_nodes = request.parent_nodes if has_parent else None

    deadline = time.monotonic() + MAX_RUN_SECONDS
    scenes: list[SceneData] = []
    overall_stats: GenerationStats | None = None

    for i in range(request.count):
        if aborted.is_set():
            break

        unique_seed = random.randint(0, 1000000)
        drop_rate = random.uniform(0.05, 0.10)
        current_attractors = _subsample_attractors(attractors, drop_rate, unique_seed)
        current_genome = genome.model_copy(update={"random_seed": unique_seed}).mutate()
        logger.debug(
            "candidate %d: seed=%d attractors=%d drop_rate=%.2f",
            i,
            unique_seed,
            len(current_attractors),
            drop_rate,
        )

        if request.run_until_complete:
            trees, overall_stats = _grow_until_complete(
                current_attractors,
                repulsion_points,
                current_genome,
                existing_nodes,
                request,
                total_attractors,
                aborted,
                deadline,
            )
        else:
            trees, stats, remaining = grow_tree(
                current_attractors,
                request.params.treeCount,
                repulsion_points,
                genome=current_genome,
                existing_nodes=existing_nodes,
                max_new_nodes=request.max_new_nodes,
            )
            overall_stats = GenerationStats(
                attractors_exhausted=stats.attractors_exhausted,
                remaining_attractors=stats.remaining_attractors,
                total_attractors=total_attractors,
                nodes_grown=stats.nodes_grown,
                growth_stopped_reason=stats.growth_stopped_reason,
                remaining_attractors_points=remaining,
            )

        scene = _make_scene(trees, request, ref_width, ref_height, generation)
        logger.debug(
            "candidate %d: shadow_match=%.3f printability=%.3f",
            i,
            scene.fitness.shadowMatch,
            scene.fitness.printability,
        )
        scenes.append(scene)

    if overall_stats is None:
        overall_stats = GenerationStats(
            attractors_exhausted=False,
            remaining_attractors=0,
            total_attractors=0,
            nodes_grown=0,
            growth_stopped_reason="aborted" if aborted.is_set() else "no_attractors",
            remaining_attractors_points=[],
        )

    logger.info("generate: returning %d scenes", len(scenes))
    return GenerateResponse(scenes=scenes, stats=overall_stats)


@router.post("/export/obj")
def export_obj(request: ExportObjRequest):
    return {"obj": _export_to_obj(request.scene)}


@router.post("/export/mesh")
def export_mesh(request: ExportObjRequest, format: Literal["stl", "obj"] = "stl"):
    """Printable solid (tubes + standard foot with keyed sockets), 100 mm scale."""
    try:
        mesh = build_scene_mesh(request.scene.trees)
    except ValueError as e:
        raise HTTPException(422, str(e))
    data = mesh.export(file_type=format)
    if isinstance(data, str):
        data = data.encode()
    media = "model/stl" if format == "stl" else "text/plain"
    return Response(
        content=data,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="scene.{format}"',
            "X-Mesh-Watertight": str(mesh_report(mesh)["watertight"]).lower(),
        },
    )
