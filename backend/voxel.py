import base64
import io
from typing import Optional

import numpy as np
from PIL import Image

from config import (
    BOUNDS,
    LIGHT_X,
    LIGHT_Z,
    WALL_HEIGHT_BASE,
    WALL_WIDTH,
    Z_WALL_X,
    X_WALL_Z,
)
from models import AttractorPoint, TargetShadow


def _project_orthographic_z_wall(
    voxel: np.ndarray,
) -> tuple[float, float]:
    vx, vy, vz = voxel
    u = vz
    v = vy
    return u, v


def _project_orthographic_x_wall(
    voxel: np.ndarray,
) -> tuple[float, float]:
    vx, vy, vz = voxel
    u = vx
    v = vy
    return u, v


def _project_to_image_coords(
    u: float,
    v: float,
    img_height: int,
    half_width: int,
    wall_height: float,
    is_z_wall: bool,
) -> Optional[tuple[int, int]]:
    u_min = -5.0 if is_z_wall else -7.5
    u_max = 7.5 if is_z_wall else 5.0

    if u < u_min or u > u_max:
        return None
    if v < WALL_HEIGHT_BASE or v > WALL_HEIGHT_BASE + wall_height:
        return None

    px = int((u - u_min) / (u_max - u_min) * (half_width - 1))
    if is_z_wall:
        px = int((u - (-5)) / 12.5 * (half_width - 1))
    else:
        px = half_width + int((u - (-7.5)) / 12.5 * (half_width - 1))

    py = int((1 - (v - WALL_HEIGHT_BASE) / wall_height) * (img_height - 1))

    return px, py


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
    print(f"Total Voxels checked: {total_voxels}")

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

    for shadow, in_shadow_arr, in_light_arr, is_z_wall in [
        (shadow_z, in_shadow_z, in_light_z, True),
        (shadow_x, in_shadow_x, in_light_x, False),
    ]:
        image_data = shadow.imageData
        if "data:" in image_data:
            image_data = image_data.split(",")[1] if "," in image_data else image_data

        image_bytes = base64.b64decode(image_data)
        img = Image.open(io.BytesIO(image_bytes)).convert("L")
        img_array = np.array(img)
        img_height, img_width = img_array.shape

        half_width = img_width // 2
        aspect_ratio = img_height / half_width
        wall_height = WALL_WIDTH * aspect_ratio

        shadow_mask = img_array < 128
        white_mask = img_array >= 128

        for vi, voxel in enumerate(voxel_centers):
            vx, vy, vz = voxel

            if is_z_wall:
                u, v = _project_orthographic_z_wall(voxel)
            else:
                u, v = _project_orthographic_x_wall(voxel)

            coords = _project_to_image_coords(
                u, v, img_height, half_width, wall_height, is_z_wall
            )

            if coords is None:
                continue

            px, py = coords
            px = np.clip(px, 0, img_width - 1)
            py = np.clip(py, 0, img_height - 1)

            if shadow_mask[py, px]:
                in_shadow_arr[vi] = True
            elif white_mask[py, px]:
                in_light_arr[vi] = True

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

    print(f"Attractors found (Intersection - dark on BOTH): {len(attractors)}")
    print(f"Repulsion points (White on EITHER): {len(repulsion_points)}")
    print(f"Shadow Z voxels: {np.sum(in_shadow_z)}")
    print(f"Shadow X voxels: {np.sum(in_shadow_x)}")

    return attractors, repulsion_points
