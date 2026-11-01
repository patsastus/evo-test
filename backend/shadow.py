import base64
import io
from io import BytesIO

import numpy as np
from PIL import Image

from config import CANVAS_WIDTH
from models import TreeNode, TargetShadow
from printability import score as printability_score
from projection import (
    calculate_wall_height,
    to_x_wall_uv,
    to_z_wall_uv,
    uv_to_pixel,
)


def _rasterize_shadows(
    trees: list[TreeNode], img_width: int, img_height: int
) -> tuple[list[list[float]], list[list[float]]]:
    """Draw the tree onto the two half-width shadow grids (Z wall, X wall)."""
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

        thickness = (node.radius + parent.radius) / 2
        line_width = max(1, int(thickness * half_width / CANVAS_WIDTH))

        for grid, to_uv in ((shadow_z, to_z_wall_uv), (shadow_x, to_x_wall_uv)):
            p1_u, p1_v = to_uv(parent.x, parent.y, parent.z, wall_height)
            p2_u, p2_v = to_uv(node.x, node.y, node.z, wall_height)
            p1_px, p1_py = uv_to_pixel(p1_u, p1_v, img_height, half_width)
            p2_px, p2_py = uv_to_pixel(p2_u, p2_v, img_height, half_width)
            _draw_line(grid, p1_px, p1_py, p2_px, p2_py, line_width, half_width)

    return shadow_z, shadow_x


def _generate_shadow_image(
    trees: list[TreeNode], reference_width: int = 512, reference_height: int = 153
) -> str:
    img_width = reference_width
    img_height = reference_height
    half_width = img_width // 2

    shadow_z, shadow_x = _rasterize_shadows(trees, img_width, img_height)

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
    shadow_z, shadow_x = _rasterize_shadows(trees, reference_width, reference_height)

    arr_z = np.array(shadow_z) > 0.5
    arr_x = np.array(shadow_x) > 0.5
    return arr_z, arr_x


def calculate_fitness(
    trees: list[TreeNode],
    target_shadows: list[TargetShadow],
    reference_width: int = 512,
    reference_height: int = 153,
    nozzle: str = "0.4",
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

    printability = printability_score(trees, nozzle)

    return shadow_match, printability
