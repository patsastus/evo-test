import base64
import io
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter
from PIL import Image

from models import (
    EvolveScenesRequest,
    ExportObjRequest,
    Fitness,
    GenerateScenesRequest,
    SceneData,
)
from scene import _evolve_scenes, _export_to_obj
from sca import grow_tree
from shadow import _generate_shadow_image
from tree_gen import _generate_uuid
from voxel import _calculate_intersection_volume

router = APIRouter()


@router.post("/scenes/generate", response_model=list[SceneData])
def generate_scenes(request: GenerateScenesRequest):
    def _generate():
        scenes: list[SceneData] = []

        if request.targetShadows:
            img_data = request.targetShadows[0].imageData
            if "data:" in img_data:
                img_data = img_data.split(",")[1] if "," in img_data else img_data
            img_bytes = base64.b64decode(img_data)
            img = Image.open(io.BytesIO(img_bytes))
            ref_width, ref_height = img.size
        else:
            ref_width, ref_height = 512, 153

        attractors, repulsion_points = _calculate_intersection_volume(
            request.targetShadows
        )

        for i in range(request.count):
            trees = grow_tree(attractors, request.params.treeCount, repulsion_points)
            shadow_url = _generate_shadow_image(trees, ref_width, ref_height)

            scenes.append(
                SceneData(
                    id=_generate_uuid(),
                    trees=trees,
                    fitness=Fitness(
                        printability=0.8,
                        shadowMatch=0.5,
                    ),
                    shadowImageUrl=shadow_url,
                    generation=0,
                    timestamp=int(time.time() * 1000),
                )
            )

        return scenes

    import time

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(_generate).result()


@router.post("/scenes/evolve", response_model=list[SceneData])
def evolve_scenes(request: EvolveScenesRequest):
    return _evolve_scenes(request.parent, request.params)


@router.post("/export/obj")
def export_obj(request: ExportObjRequest):
    return {"obj": _export_to_obj(request.scene)}
