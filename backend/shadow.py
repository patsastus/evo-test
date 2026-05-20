import base64
import io
from io import BytesIO
from typing import Optional

import numpy as np
from PIL import Image

from config import CANVAS_WIDTH, X_MIN, Z_MIN, Y_BASE
from models import TreeNode, TargetShadow


def calculate_wall_height(img_height: int, img_width: int) -> float:
    half_width = img_width // 2
    if half_width == 0:
        half_width = 1
    half_aspect_ratio = img_height / half_width
    return CANVAS_WIDTH * half_aspect_ratio


def node_to_z_wall_uv(
    wx: float, wy: float, wz: float, wall_height: float
) -> tuple[float, float]:
    u = (wz - Z_MIN) / CANVAS_WIDTH
    v = (wy - Y_BASE) / wall_height
    return u, v


def node_to_x_wall_uv(
    wx: float, wy: float, wz: float, wall_height: float
) -> tuple[float, float]:
    u = (wx - X_MIN) / CANVAS_WIDTH
    v = (wy - Y_BASE) / wall_height
    return u, v


def uv_to_pixel_left(
    u: float, v: float, img_height: int, half_width: int
) -> tuple[int, int]:
    px = int(u * half_width)
    py = int((1 - v) * img_height)
    px = max(0, min(px, half_width - 1))
    py = max(0, min(py, img_height - 1))
    return px, py


def uv_to_pixel_right(
    u: float, v: float, img_height: int, half_width: int
) -> tuple[int, int]:
    px = int(u * half_width)
    py = int((1 - v) * img_height)
    px = max(0, min(px, half_width - 1))
    py = max(0, min(py, img_height - 1))
    return px, py


def _generate_shadow_image(
    trees: list[TreeNode], reference_width: int = 512, reference_height: int = 153
) -> str:
    img_width = reference_width
    img_height = reference_height
    half_width = img_width // 2

    wall_height = calculate_wall_height(img_height, img_width)

    node_map = {n.id: n for n in trees}

    shadow_z = [[0.0] * half_width for _ in range(img_height)]
    shadow_x = [[0.0] * half_width for _ in range(img_height)]

    for node in trees:
        if not node.parentId:
            continue
        parent = node_map.get(node.parentId)
        if not parent:
            continue

        p1_u, p1_v = node_to_z_wall_uv(parent.x, parent.y, parent.z, wall_height)
        p2_u, p2_v = node_to_z_wall_uv(node.x, node.y, node.z, wall_height)

        p1_px, p1_py = uv_to_pixel_left(p1_u, p1_v, img_height, half_width)
        p2_px, p2_py = uv_to_pixel_left(p2_u, p2_v, img_height, half_width)

        thickness = (node.radius + parent.radius) / 2
        line_width = max(1, int(thickness * half_width / CANVAS_WIDTH))

        _draw_line(shadow_z, p1_px, p1_py, p2_px, p2_py, line_width, half_width)

        p1_u, p1_v = node_to_x_wall_uv(parent.x, parent.y, parent.z, wall_height)
        p2_u, p2_v = node_to_x_wall_uv(node.x, node.y, node.z, wall_height)

        p1_px, p1_py = uv_to_pixel_right(p1_u, p1_v, img_height, half_width)
        p2_px, p2_py = uv_to_pixel_right(p2_u, p2_v, img_height, half_width)

        _draw_line(
            shadow_x,
            p1_px,
            p1_py,
            p2_px,
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
    height: int | None = None,
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


def _decode_image(image_data: str) -> np.ndarray:
    if "data:" in image_data:
        image_data = image_data.split(",")[1] if "," in image_data else image_data
    image_bytes = base64.b64decode(image_data)
    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    return np.array(img)


def _get_shadow_arrays(
    trees: list[TreeNode], reference_width: int, reference_height: int
) -> tuple[np.ndarray, np.ndarray]:
    img_width = reference_width
    img_height = reference_height
    half_width = img_width // 2
    wall_height = calculate_wall_height(img_height, img_width)

    node_map = {n.id: n for n in trees}
    shadow_z = [[0.0] * half_width for _ in range(img_height)]
    shadow_x = [[0.0] * half_width for _ in range(img_height)]

    for node in trees:
        if not node.parentId:
            continue
        parent = node_map.get(node.parentId)
        if not parent:
            continue

        p1_u, p1_v = node_to_z_wall_uv(parent.x, parent.y, parent.z, wall_height)
        p2_u, p2_v = node_to_z_wall_uv(node.x, node.y, node.z, wall_height)
        p1_px, p1_py = uv_to_pixel_left(p1_u, p1_v, img_height, half_width)
        p2_px, p2_py = uv_to_pixel_left(p2_u, p2_v, img_height, half_width)
        thickness = (node.radius + parent.radius) / 2
        line_width = max(1, int(thickness * half_width / CANVAS_WIDTH))
        _draw_line(shadow_z, p1_px, p1_py, p2_px, p2_py, line_width, half_width)

        p1_u, p1_v = node_to_x_wall_uv(parent.x, parent.y, parent.z, wall_height)
        p2_u, p2_v = node_to_x_wall_uv(node.x, node.y, node.z, wall_height)
        p1_px, p1_py = uv_to_pixel_right(p1_u, p1_v, img_height, half_width)
        p2_px, p2_py = uv_to_pixel_right(p2_u, p2_v, img_height, half_width)
        _draw_line(shadow_x, p1_px, p1_py, p2_px, p2_py, line_width, half_width)

    arr_z = np.array(shadow_z) > 0.5
    arr_x = np.array(shadow_x) > 0.5
    return arr_z, arr_x


def calculate_fitness(
    trees: list[TreeNode],
    target_shadows: list[TargetShadow],
    reference_width: int = 512,
    reference_height: int = 153,
) -> tuple[float, float]:
    if not target_shadows or not trees:
        return 0.0, 0.0

    shadow_match_scores = []

    for i, target in enumerate(target_shadows):
        target_arr = _decode_image(target.imageData)
        target_height, target_width = target_arr.shape

        gen_z, gen_x = _get_shadow_arrays(trees, target_width, target_height)

        gen_arr = gen_z if i == 0 else gen_x
        target_arr_use = (
            target_arr[:, : gen_arr.shape[1]]
            if i == 0
            else target_arr[:, target_width - gen_arr.shape[1] :]
        )

        target_dark = target_arr_use < 128
        target_white = target_arr_use >= 128

        target_pixels = target_dark.sum()
        if target_pixels == 0:
            shadow_match_scores.append(0.0)
            continue

        covered = (gen_arr & target_dark).sum()
        false_positives = (gen_arr & target_white).sum()
        total_gen = gen_arr.sum()
        if total_gen == 0:
            shadow_match_scores.append(0.0)
            continue

        coverage = covered / target_pixels
        false_positive_rate = false_positives / total_gen if total_gen > 0 else 0
        penalty = false_positive_rate * 0.3
        score = max(0.0, min(1.0, coverage - penalty))
        shadow_match_scores.append(score)

    shadow_match = float(np.mean(shadow_match_scores)) if shadow_match_scores else 0.0

    printability = calculate_printability(trees)

    return shadow_match, printability


def calculate_printability(trees: list[TreeNode]) -> float:
    if not trees:
        return 0.0

    grounded_nodes = sum(1 for n in trees if n.y <= 0.6 and n.parentId is not None)

    if grounded_nodes == 0:
        return 0.0

    max_y = max(n.y for n in trees) if trees else 0
    aspect_ratio = max_y / 5.0 if max_y > 0 else 0

    base_score = grounded_nodes / len(trees) if trees else 0
    aspect_penalty = max(0, 1 - aspect_ratio / 2) * 0.3

    score = base_score - aspect_penalty
    return max(0.0, min(1.0, score))
