import base64
import io
from typing import Optional

import numpy as np
from PIL import Image

from config import BOUNDS, Z_WALL_X, X_WALL_Z, WALL_HEIGHT_BASE, WALL_WIDTH
from models import AttractorPoint, TargetShadow


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

    union_mask = np.zeros(len(voxel_centers), dtype=bool)
    intersection_mask = np.ones(len(voxel_centers), dtype=bool)
    repulsion_mask = np.zeros(len(voxel_centers), dtype=bool)

    for shadow in target_shadows:
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

        light_dir = np.array(
            [shadow.lightVector.x, shadow.lightVector.y, shadow.lightVector.z]
        )
        light_dir = light_dir / (np.linalg.norm(light_dir) + 1e-8)

        shadow_mask = img_array < 128
        white_mask = img_array >= 128

        voxel_in_shadow = np.zeros(len(voxel_centers), dtype=bool)
        voxel_in_light = np.zeros(len(voxel_centers), dtype=bool)

        for vi, voxel in enumerate(voxel_centers):
            vx, vy, vz = voxel

            t_z_wall = float("inf")
            if abs(light_dir[0]) > 1e-8:
                t_z_wall = (Z_WALL_X - vx) / light_dir[0]

            t_x_wall = float("inf")
            if abs(light_dir[2]) > 1e-8:
                t_x_wall = (X_WALL_Z - vz) / light_dir[2]

            if t_z_wall <= 0:
                t_z_wall = float("inf")
            if t_x_wall <= 0:
                t_x_wall = float("inf")

            hit_z_wall = t_z_wall < t_x_wall

            if hit_z_wall and t_z_wall < float("inf"):
                wall_y = vy + light_dir[1] * t_z_wall
                wall_z = vz + light_dir[2] * t_z_wall

                if wall_y < WALL_HEIGHT_BASE or wall_y > WALL_HEIGHT_BASE + wall_height:
                    continue
                if wall_z < -5 or wall_z > 7.5:
                    continue

                px = int((wall_z - (-5)) / 12.5 * (half_width - 1))
                py = int((wall_y - WALL_HEIGHT_BASE) / wall_height * (img_height - 1))

            elif t_x_wall < float("inf"):
                wall_y = vy + light_dir[1] * t_x_wall
                wall_x = vx + light_dir[0] * t_x_wall

                if wall_y < WALL_HEIGHT_BASE or wall_y > WALL_HEIGHT_BASE + wall_height:
                    continue
                if wall_x < -7.5 or wall_x > 5:
                    continue

                px = half_width + int((wall_x - (-7.5)) / 12.5 * (half_width - 1))
                py = int((wall_y - WALL_HEIGHT_BASE) / wall_height * (img_height - 1))

            else:
                continue

            px = np.clip(px, 0, img_width - 1)
            py = np.clip(py, 0, img_height - 1)

            t_min = -np.inf
            t_max = np.inf
            valid = True

            for axis in range(3):
                if abs(light_dir[axis]) < 1e-8:
                    if voxel[axis] < bounds[axis, 0] or voxel[axis] > bounds[axis, 1]:
                        valid = False
                        break
                else:
                    t1 = (bounds[axis, 0] - voxel[axis]) / light_dir[axis]
                    t2 = (bounds[axis, 1] - voxel[axis]) / light_dir[axis]
                    t_min = max(t_min, min(t1, t2))
                    t_max = min(t_max, max(t1, t2))

            if valid and t_min <= t_max and t_min <= 0 <= t_max:
                if shadow_mask[py, px]:
                    voxel_in_shadow[vi] = True
                elif white_mask[py, px]:
                    voxel_in_light[vi] = True

        union_mask |= voxel_in_shadow
        intersection_mask &= voxel_in_shadow
        repulsion_mask |= voxel_in_light

    attractor_indices = np.where(union_mask)[0]
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

    intersection_count = np.sum(intersection_mask)

    print(f"Attractors found (Union): {len(attractors)}")
    print(f"Repulsion points found (Any White): {len(repulsion_points)}")
    print(f"Intersection points (Perfect Overlap): {intersection_count}")

    return attractors, repulsion_points
