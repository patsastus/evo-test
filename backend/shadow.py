import base64
import math
from io import BytesIO

import numpy as np
from PIL import Image

from config import Z_WALL_X, X_WALL_Z, WALL_HEIGHT_BASE, WALL_WIDTH
from models import TreeNode


def _generate_shadow_image(
    trees: list[TreeNode], reference_width: int = 512, reference_height: int = 153
) -> str:
    img_width = reference_width
    img_height = reference_height
    half_width = img_width // 2

    light_count = 9
    lights = []
    for i in range(light_count):
        theta = (i / (light_count - 1)) * (math.pi / 2)
        x = -5 + 15 * math.cos(theta)
        z = 5 - 15 * math.sin(theta)
        lights.append((x, 0, z))

    node_map = {n.id: n for n in trees}

    shadow_pixels = [[0.0] * img_width for _ in range(img_height)]

    aspect_ratio = img_height / half_width
    wall_height = WALL_WIDTH * aspect_ratio

    for light_x, light_y, light_z in lights:
        toward_light = np.array([light_x, light_y, light_z])
        toward_light = toward_light / (np.linalg.norm(toward_light) + 1e-8)
        light_dir = -toward_light

        t_z_wall = float("inf")
        if abs(light_dir[0]) > 1e-8:
            t_z_wall = (Z_WALL_X - light_x) / light_dir[0]

        t_x_wall = float("inf")
        if abs(light_dir[2]) > 1e-8:
            t_x_wall = (X_WALL_Z - light_z) / light_dir[2]

        if t_z_wall <= 0:
            t_z_wall = float("inf")
        if t_x_wall <= 0:
            t_x_wall = float("inf")

        hits_z_wall = t_z_wall <= t_x_wall

        for node in trees:
            if not node.parentId:
                continue
            parent = node_map.get(node.parentId)
            if not parent:
                continue

            def project_to_image(wx, wy, wz):
                if hits_z_wall:
                    t = (
                        (Z_WALL_X - wx) / light_dir[0]
                        if abs(light_dir[0]) > 1e-8
                        else float("inf")
                    )
                else:
                    t = (
                        (X_WALL_Z - wz) / light_dir[2]
                        if abs(light_dir[2]) > 1e-8
                        else float("inf")
                    )

                if t <= 0 or t == float("inf"):
                    return None, None

                hit_y = wy + light_dir[1] * t
                if hit_y < WALL_HEIGHT_BASE or hit_y > WALL_HEIGHT_BASE + wall_height:
                    return None, None

                if hits_z_wall:
                    hit_z = wz + light_dir[2] * t
                    if hit_z < -5 or hit_z > 7.5:
                        return None, None
                    px = int((hit_z - (-5)) / 12.5 * (half_width - 1))
                else:
                    hit_x = wx + light_dir[0] * t
                    if hit_x < -7.5 or hit_x > 5:
                        return None, None
                    px = half_width + int((hit_x - (-7.5)) / 12.5 * (half_width - 1))

                py = int(
                    (1 - (hit_y - WALL_HEIGHT_BASE) / wall_height) * (img_height - 1)
                )
                return px, py

            p1_result = project_to_image(parent.x, parent.y, parent.z)
            p2_result = project_to_image(node.x, node.y, node.z)

            if p1_result[0] is None or p2_result[0] is None:
                continue

            p1_px: int = p1_result[0]
            p1_py: int = p1_result[1]
            p2_px: int = p2_result[0]
            p2_py: int = p2_result[1]

            p1_screen = (p1_px, p1_py)
            p2_screen = (p2_px, p2_py)

            thickness = (node.radius + parent.radius) / 2
            line_width = max(1, int(thickness * img_width / WALL_WIDTH))

            x_min = max(0, min(p1_screen[0], p2_screen[0]) - line_width)
            x_max = min(img_width, max(p1_screen[0], p2_screen[0]) + line_width + 1)
            y_min = max(0, min(p1_screen[1], p2_screen[1]) - line_width)
            y_max = min(img_height, max(p1_screen[1], p2_screen[1]) + line_width + 1)

            dx_screen = p2_screen[0] - p1_screen[0]
            dy_screen = p2_screen[1] - p1_screen[1]
            line_len_sq = dx_screen * dx_screen + dy_screen * dy_screen
            half_width_pix = line_width / 2

            for py in range(y_min, y_max):
                for px in range(x_min, x_max):
                    if line_len_sq == 0:
                        dist_sq = (px - p1_screen[0]) ** 2 + (py - p1_screen[1]) ** 2
                    else:
                        tt = max(
                            0,
                            min(
                                1,
                                (
                                    (px - p1_screen[0]) * dx_screen
                                    + (py - p1_screen[1]) * dy_screen
                                )
                                / line_len_sq,
                            ),
                        )
                        proj_x = p1_screen[0] + tt * dx_screen
                        proj_y = p1_screen[1] + tt * dy_screen
                        dist_sq = (px - proj_x) ** 2 + (py - proj_y) ** 2

                    if dist_sq <= half_width_pix * half_width_pix:
                        shadow_pixels[py][px] += 1.0 / light_count

    buffer = BytesIO()
    img = Image.new("RGB", (img_width, img_height), "white")
    pixels = img.load()
    for y in range(img_height):
        for x in range(img_width):
            intensity = shadow_pixels[y][x]
            val = int(255 * (1 - intensity))
            pixels[x, y] = (val, val, val)

    border_size = 4
    border_color = (255, 0, 0)
    for y in range(img_height):
        for x in range(border_size):
            pixels[x, y] = border_color
            pixels[img_width - 1 - x, y] = border_color
    for x in range(img_width):
        for y in range(border_size):
            pixels[x, y] = border_color
            pixels[x, img_height - 1 - y] = border_color

    img.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"
