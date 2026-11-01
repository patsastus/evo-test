import base64
import io

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
from projection import (
    calculate_wall_height,
    to_x_wall_uv,
    to_z_wall_uv,
    uv_to_pixel,
)


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

    for vi, voxel in enumerate(voxel_centers):
        vx, vy, vz = voxel

        if vx < X_MIN or vx > BOUNDS["maxX"]:
            continue
        if vz < Z_MIN or vz > BOUNDS["maxZ"]:
            continue
        if vy < Y_BASE or vy > Y_BASE + wall_height:
            continue

        u_z, v_z = to_z_wall_uv(vx, vy, vz, wall_height)
        px_z, py_z = uv_to_pixel(u_z, v_z, img_height, half_width)

        u_x, v_x = to_x_wall_uv(vx, vy, vz, wall_height)
        px_x, py_x = uv_to_pixel(u_x, v_x, img_height, half_width)

        if left_shadow[py_z, px_z]:
            in_shadow_z[vi] = True
        elif left_white[py_z, px_z]:
            in_light_z[vi] = True

        if right_shadow[py_x, px_x]:
            in_shadow_x[vi] = True
        elif right_white[py_x, px_x]:
            in_light_x[vi] = True

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
