import base64
import io
import logging

import numpy as np
from PIL import Image

from config import (
    BOUNDS,
    CANVAS_WIDTH,
    X_MIN,
    Z_MIN,
    Y_BASE,
    Z_WALL_X,
    X_WALL_Z,
)
from models import AttractorPoint, TargetShadow
from projection import calculate_wall_height, default_projectors, uv_to_pixels

logger = logging.getLogger(__name__)


def _calculate_intersection_volume(
    target_shadows: list[TargetShadow],
) -> tuple[list[AttractorPoint], list[AttractorPoint]]:
    if not target_shadows:
        return [], []

    bounds = np.array(
        [
            [BOUNDS["minX"], BOUNDS["maxX"]],
            [BOUNDS["minY"], BOUNDS["maxY"]],
            [BOUNDS["minZ"], BOUNDS["maxZ"]],
        ]
    )

    step_size = 0.5
    grid_x = np.arange(bounds[0, 0], bounds[0, 1] + step_size, step_size)
    grid_y = np.arange(bounds[1, 0], bounds[1, 1] + step_size, step_size)
    grid_z = np.arange(bounds[2, 0], bounds[2, 1] + step_size, step_size)

    voxel_centers = (
        np.array(np.meshgrid(grid_x, grid_y, grid_z, indexing="ij")).reshape(3, -1).T
    )

    total_voxels = len(voxel_centers)
    logger.debug("voxels checked: %d", total_voxels)

    in_shadow_z = np.zeros(len(voxel_centers), dtype=bool)
    in_shadow_x = np.zeros(len(voxel_centers), dtype=bool)
    in_light_z = np.zeros(len(voxel_centers), dtype=bool)
    in_light_x = np.zeros(len(voxel_centers), dtype=bool)

    if len(target_shadows) >= 2:
        shadow_z = target_shadows[0]
        shadow_x = target_shadows[1]
    elif len(target_shadows) == 1:
        shadow_z = target_shadows[0]
        shadow_x = target_shadows[0]
    else:
        return [], []

    def decode_image(target: TargetShadow) -> np.ndarray:
        image_data = target.imageData
        if "data:" in image_data:
            image_data = image_data.split(",")[1] if "," in image_data else image_data
        image_bytes = base64.b64decode(image_data)
        img = Image.open(io.BytesIO(image_bytes)).convert("L")
        return np.array(img)

    img_array_z = decode_image(shadow_z)
    img_array_x = decode_image(shadow_x)

    img_height, img_width = img_array_z.shape
    half_width = img_width // 2
    wall_height = calculate_wall_height(img_height, img_width)

    shadow_mask_z = img_array_z < 128
    white_mask_z = img_array_z >= 128
    shadow_mask_x = img_array_x < 128
    white_mask_x = img_array_x >= 128

    left_shadow = shadow_mask_z[:, :half_width]
    left_white = white_mask_z[:, :half_width]
    right_shadow = shadow_mask_x[:, half_width:]
    right_white = white_mask_x[:, half_width:]

    # Voxels outside the scene volume (or below the wall) never constrain anything.
    in_domain = (
        (voxel_centers[:, 0] >= X_MIN)
        & (voxel_centers[:, 0] <= BOUNDS["maxX"])
        & (voxel_centers[:, 2] >= Z_MIN)
        & (voxel_centers[:, 2] <= BOUNDS["maxZ"])
        & (voxel_centers[:, 1] >= Y_BASE)
        & (voxel_centers[:, 1] <= Y_BASE + wall_height)
    )
    domain_idx = np.where(in_domain)[0]
    domain_pts = voxel_centers[domain_idx]

    # One pass per light, in light-index order: light 0 <-> left half of its image,
    # light 1 <-> right half. The projector decides where each voxel lands on the wall.
    projector_z, projector_x = default_projectors(img_width, img_height)
    for projector, dark, white, in_shadow, in_light in (
        (projector_z, left_shadow, left_white, in_shadow_z, in_light_z),
        (projector_x, right_shadow, right_white, in_shadow_x, in_light_x),
    ):
        u, v = projector.project(domain_pts)
        px, py = uv_to_pixels(u, v, img_height, half_width)
        hit_dark = dark[py, px]
        hit_white = white[py, px] & ~hit_dark
        in_shadow[domain_idx[hit_dark]] = True
        in_light[domain_idx[hit_white]] = True

    attractor_mask = in_shadow_z & in_shadow_x
    repulsion_mask = in_light_z | in_light_x

    attractor_indices = np.where(attractor_mask)[0]
    attractors = [
        AttractorPoint(
            x=float(voxel_centers[i, 0]),
            y=float(voxel_centers[i, 1]),
            z=float(voxel_centers[i, 2]),
        )
        for i in attractor_indices
    ]

    repulsion_indices = np.where(repulsion_mask)[0]
    repulsion_points = [
        AttractorPoint(
            x=float(voxel_centers[i, 0]),
            y=float(voxel_centers[i, 1]),
            z=float(voxel_centers[i, 2]),
        )
        for i in repulsion_indices
    ]

    logger.debug(
        "attractors=%d repulsors=%d shadow_z_voxels=%d shadow_x_voxels=%d",
        len(attractors),
        len(repulsion_points),
        np.sum(in_shadow_z),
        np.sum(in_shadow_x),
    )

    return attractors, repulsion_points
