import logging
import threading
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, Response

from config import MAX_RUN_SECONDS
from generator import ImageError, generate
from mesh import build_scene_mesh, mesh_report
from models import ExportObjRequest, GenerateResponse, GenerateScenesRequest
from printability import analyze as analyze_printability
from scene import _export_to_obj

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


@router.post("/scenes/generate", response_model=GenerateResponse)
def generate_scenes(request: GenerateScenesRequest):
    request_id = request.request_id or uuid.uuid4().hex
    aborted = threading.Event()
    with _active_lock:
        if request_id in _active_requests:
            raise HTTPException(409, f"request_id {request_id!r} is already running")
        _active_requests[request_id] = aborted

    try:
        return generate(request, aborted, max_seconds=MAX_RUN_SECONDS)
    except ImageError as e:
        raise HTTPException(e.status, str(e))
    finally:
        with _active_lock:
            _active_requests.pop(request_id, None)


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


@router.post("/scenes/printability")
def scene_printability(request: ExportObjRequest, nozzle: Literal["0.4", "0.2"] = "0.4"):
    """Full printability report: skeleton metrics plus checks on the built solid."""
    report = analyze_printability(request.scene.trees, nozzle)
    out = {"printability": report.to_dict(), "mesh": None}
    if report.gate_ok:
        out["mesh"] = mesh_report(build_scene_mesh(request.scene.trees))
    return out
