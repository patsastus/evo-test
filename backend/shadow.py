import base64
from io import BytesIO

import numpy as np
from PIL import Image

from config import WALL_HEIGHT_BASE, WALL_WIDTH
from models import TreeNode


def _project_orthographic_z_wall(
    wx: float, wy: float, wz: float
) -> tuple[float, float]:
    return wz, wy


def _project_orthographic_x_wall(
    wx: float, wy: float, wz: float
) -> tuple[float, float]:
    return wx, wy


def _project_to_image_coords(
    u: float,
    v: float,
    img_height: int,
    half_width: int,
    wall_height: float,
    is_z_wall: bool,
) -> tuple[int, int]:
    if is_z_wall:
        u_min, u_max = -5.0, 7.5
        px = int((u - u_min) / (u_max - u_min) * (half_width - 1))
    else:
        u_min, u_max = -7.5, 5.0
        px = half_width + int((u - u_min) / (u_max - u_min) * (half_width - 1))

    py = int((1 - (v - WALL_HEIGHT_BASE) / wall_height) * (img_height - 1))

    px = max(0, min(px, half_width * 2 - 1))
    py = max(0, min(py, img_height - 1))

    return px, py


def _generate_shadow_image(
    trees: list[TreeNode], reference_width: int = 512, reference_height: int = 153
) -> str:
    img_width = reference_width
    img_height = reference_height
    half_width = img_width // 2

    aspect_ratio = img_height / half_width
    wall_height = WALL_WIDTH * aspect_ratio

    node_map = {n.id: n for n in trees}

    shadow_z = [[0.0] * half_width for _ in range(img_height)]
    shadow_x = [[0.0] * half_width for _ in range(img_height)]

    for node in trees:
        if not node.parentId:
            continue
        parent = node_map.get(node.parentId)
        if not parent:
            continue

        p1_u, p1_v = _project_orthographic_z_wall(parent.x, parent.y, parent.z)
        p2_u, p2_v = _project_orthographic_z_wall(node.x, node.y, node.z)

        p1_px, p1_py = _project_to_image_coords(
            p1_u, p1_v, img_height, half_width, wall_height, True
        )
        p2_px, p2_py = _project_to_image_coords(
            p2_u, p2_v, img_height, half_width, wall_height, True
        )

        thickness = (node.radius + parent.radius) / 2
        line_width = max(1, int(thickness * half_width / 12.5))

        _draw_line(shadow_z, p1_px, p1_py, p2_px, p2_py, line_width, half_width)

        p1_u, p1_v = _project_orthographic_x_wall(parent.x, parent.y, parent.z)
        p2_u, p2_v = _project_orthographic_x_wall(node.x, node.y, node.z)

        p1_px, p1_py = _project_to_image_coords(
            p1_u, p1_v, img_height, half_width, wall_height, False
        )
        p2_px, p2_py = _project_to_image_coords(
            p2_u, p2_v, img_height, half_width, wall_height, False
        )

        _draw_line(
            shadow_x,
            p1_px - half_width,
            p1_py,
            p2_px - half_width,
            p2_py,
            line_width,
            half_width,
        )

    buffer = BytesIO()
    img = Image.new("RGB", (img_width, img_height), "white")
    pixels = img.load()

    for y in range(img_height):
        for x in range(half_width):
            intensity = shadow_z[y][x]
            val = int(255 * (1 - intensity))
            pixels[x, y] = (val, val, val)
            intensity = shadow_x[y][x]
            val = int(255 * (1 - intensity))
            pixels[half_width + x, y] = (val, val, val)

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


def _draw_line(
    shadow: list[list[float]],
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    line_width: int,
    width: int,
    height: int = None,
) -> None:
    if height is None:
        height = len(shadow)

    dx = x2 - x1
    dy = y2 - y1
    line_len_sq = dx * dx + dy * dy

    x_min = max(0, min(x1, x2) - line_width)
    x_max = min(width, max(x1, x2) + line_width + 1)
    y_min = max(0, min(y1, y2) - line_width)
    y_max = min(height, max(y1, y2) + line_width + 1)

    half_width_pix = line_width / 2

    for py in range(y_min, y_max):
        for px in range(x_min, x_max):
            if line_len_sq == 0:
                dist_sq = (px - x1) ** 2 + (py - y1) ** 2
            else:
                tt = max(
                    0,
                    min(1, ((px - x1) * dx + (py - y1) * dy) / line_len_sq),
                )
                proj_x = x1 + tt * dx
                proj_y = y1 + tt * dy
                dist_sq = (px - proj_x) ** 2 + (py - proj_y) ** 2

            if dist_sq <= half_width_pix * half_width_pix:
                shadow[py][px] = min(1.0, shadow[py][px] + 1.0)
