import base64
import io
import random
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from PIL import Image

from models import (
    AttractorPoint,
    ExportObjRequest,
    Fitness,
    GenerateScenesRequest,
    GenerationStats,
    SceneData,
    TreeGenome,
)
from scene import _export_to_obj
from sca import _generate_uuid, grow_tree
from shadow import _generate_shadow_image, calculate_fitness
from voxel import _calculate_intersection_volume

router = APIRouter()

generation_aborted = False


class GenerateResponse(BaseModel):
    scenes: list[SceneData]
    stats: GenerationStats


@router.post("/scenes/abort")
def abort_generation():
    global generation_aborted
    generation_aborted = True
    return {"aborted": True}


def _reset_abort():
    global generation_aborted
    generation_aborted = False


def _subsample_attractors(
    attractors: list[AttractorPoint], drop_rate: float, seed: int
) -> list[AttractorPoint]:
    rng = random.Random(seed)
    result = []
    for a in attractors:
        if rng.random() >= drop_rate:
            result.append(a)
    return result


@router.post("/scenes/generate")
def generate_scenes(request: GenerateScenesRequest):
    _reset_abort()
    parent_nodes_count = len(request.parent_nodes) if request.parent_nodes else 0
    remaining_count = (
        len(request.remaining_attractors) if request.remaining_attractors else 0
    )
    print(
        f"[DEBUG] Received: count={request.count}, parent_nodes={parent_nodes_count}, remaining_attractors={remaining_count}"
    )

    def _generate() -> dict[str, Any]:
        scenes: list[SceneData] = []
        overall_stats: GenerationStats | None = None

        print(f"[DEBUG] Starting generation...")
        if request.targetShadows:
            img_data = request.targetShadows[0].imageData
            if "data:" in img_data:
                img_data = img_data.split(",")[1] if "," in img_data else img_data
            img_bytes = base64.b64decode(img_data)
            img = Image.open(io.BytesIO(img_bytes))
            ref_width, ref_height = img.size
            print(f"[DEBUG] Image: {ref_width}x{ref_height}")
        else:
            ref_width, ref_height = 512, 153

        has_parent = request.parent_nodes is not None and len(request.parent_nodes) > 0
        parent_generation = (
            request.parent_generation if request.parent_generation is not None else 0
        )

        # Use provided remaining_attractors or recalculate from scratch
        if request.remaining_attractors and len(request.remaining_attractors) > 0:
            print(
                f"[DEBUG] Using provided remaining_attractors: {len(request.remaining_attractors)}"
            )
            attractors = request.remaining_attractors
        else:
            print(f"[DEBUG] Calculating new attractors from target shadows...")
            attractors, _ = _calculate_intersection_volume(request.targetShadows)
            print(f"[DEBUG] New attractors: {len(attractors)}")

        _, repulsion_points = _calculate_intersection_volume(request.targetShadows)
        total_attractors = len(attractors)

        genome = request.parent_genome if request.parent_genome else TreeGenome()

        for i in range(request.count):
            unique_seed = random.randint(0, 1000000)
            drop_rate = random.uniform(0.05, 0.10)
            subsampled_attractors = _subsample_attractors(
                attractors, drop_rate, unique_seed
            )
            current_attractors = subsampled_attractors
            existing_nodes = request.parent_nodes if has_parent else None
            current_genome = TreeGenome(
                influence_radius=genome.influence_radius,
                kill_distance=genome.kill_distance,
                growth_step=genome.growth_step,
                repulsion_strength=genome.repulsion_strength,
                attraction_strength=genome.attraction_strength,
                repulsion_radius=genome.repulsion_radius,
                max_children_per_node=genome.max_children_per_node,
                wiggle_factor=genome.wiggle_factor,
                random_seed=unique_seed,
            ).mutate()
            generation = 0 if not has_parent else parent_generation + 1

            print(
                f"[DEBUG] Candidate {i}: seed={unique_seed}, attractors={len(current_attractors)}, drop_rate={drop_rate:.2f}"
            )

            if request.run_until_complete:
                all_nodes = list(existing_nodes) if existing_nodes else []
                total_nodes_grown = 0
                max_loop_iterations = 100
                loop_iteration = 0
                consecutive_no_progress = 0

                while current_attractors and loop_iteration < max_loop_iterations:
                    loop_iteration += 1

                    if generation_aborted:
                        overall_stats = GenerationStats(
                            attractors_exhausted=False,
                            remaining_attractors=len(current_attractors),
                            total_attractors=total_attractors,
                            nodes_grown=total_nodes_grown,
                            growth_stopped_reason="aborted",
                            remaining_attractors_points=current_attractors,
                        )
                        break

                    # Same genome throughout; only the RNG seed varies per iteration.
                    iteration_genome = current_genome.model_copy(
                        update={"random_seed": current_genome.random_seed + loop_iteration}
                    )
                    result = grow_tree(
                        current_attractors,
                        request.params.treeCount,
                        repulsion_points,
                        genome=iteration_genome,
                        existing_nodes=all_nodes if all_nodes else None,
                        max_new_nodes=request.max_new_nodes,
                    )
                    trees, stats, remaining = result
                    all_nodes = trees
                    total_nodes_grown += stats.nodes_grown

                    overall_stats = GenerationStats(
                        attractors_exhausted=stats.attractors_exhausted,
                        remaining_attractors=stats.remaining_attractors,
                        total_attractors=total_attractors,
                        nodes_grown=total_nodes_grown,
                        growth_stopped_reason=stats.growth_stopped_reason,
                        remaining_attractors_points=remaining,
                    )

                    if stats.attractors_exhausted or not remaining:
                        current_attractors = []
                    elif stats.nodes_grown == 0:
                        consecutive_no_progress += 1
                        if consecutive_no_progress >= 3:
                            overall_stats = GenerationStats(
                                attractors_exhausted=False,
                                remaining_attractors=len(remaining),
                                total_attractors=total_attractors,
                                nodes_grown=total_nodes_grown,
                                growth_stopped_reason="unreachable_attractors",
                                remaining_attractors_points=remaining,
                            )
                            current_attractors = []
                    else:
                        consecutive_no_progress = 0
                        current_attractors = remaining

                trees = all_nodes
                shadow_url = _generate_shadow_image(trees, ref_width, ref_height)

                shadow_match, printability = calculate_fitness(
                    trees, request.targetShadows, ref_width, ref_height
                )

                scenes.append(
                    SceneData(
                        id=_generate_uuid(),
                        trees=trees,
                        fitness=Fitness(
                            printability=printability,
                            shadowMatch=shadow_match,
                        ),
                        shadowImageUrl=shadow_url,
                        generation=generation,
                        timestamp=int(time.time() * 1000),
                    )
                )
            else:
                result = grow_tree(
                    current_attractors,
                    request.params.treeCount,
                    repulsion_points,
                    genome=current_genome,
                    existing_nodes=existing_nodes,
                    max_new_nodes=request.max_new_nodes,
                )

                trees, stats, remaining = result
                overall_stats = GenerationStats(
                    attractors_exhausted=stats.attractors_exhausted,
                    remaining_attractors=stats.remaining_attractors,
                    total_attractors=total_attractors,
                    nodes_grown=stats.nodes_grown,
                    growth_stopped_reason=stats.growth_stopped_reason,
                    remaining_attractors_points=remaining,
                )

                shadow_url = _generate_shadow_image(trees, ref_width, ref_height)

                shadow_match, printability = calculate_fitness(
                    trees, request.targetShadows, ref_width, ref_height
                )
                print(
                    f"[DEBUG] Candidate {i}: shadow_match={shadow_match:.3f}, printability={printability:.3f}"
                )

                scenes.append(
                    SceneData(
                        id=_generate_uuid(),
                        trees=trees,
                        fitness=Fitness(
                            printability=printability,
                            shadowMatch=shadow_match,
                        ),
                        shadowImageUrl=shadow_url,
                        generation=generation,
                        timestamp=int(time.time() * 1000),
                    )
                )

        if overall_stats is None:
            overall_stats = GenerationStats(
                attractors_exhausted=False,
                remaining_attractors=0,
                total_attractors=0,
                nodes_grown=0,
                growth_stopped_reason="no_attractors",
                remaining_attractors_points=[],
            )

        print(f"[DEBUG] Returning {len(scenes)} scenes")
        print(
            f"[DEBUG] stats remaining_attractors_points length: {len(overall_stats.remaining_attractors_points) if overall_stats.remaining_attractors_points else 'None'}"
        )

        # Return as dict for proper serialization
        return {
            "scenes": [s.model_dump() for s in scenes],
            "stats": overall_stats.model_dump(),
        }

    with ThreadPoolExecutor(max_workers=1) as executor:
        print("[DEBUG] Submitting to ThreadPoolExecutor")
        result = executor.submit(_generate).result()
        print("[DEBUG] ThreadPoolExecutor completed")
        return result


@router.post("/export/obj")
def export_obj(request: ExportObjRequest):
    return {"obj": _export_to_obj(request.scene)}
