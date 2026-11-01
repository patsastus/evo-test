import base64
import io
from functools import lru_cache
from io import BytesIO

import numpy as np
from PIL import Image, ImageFilter

from config import CANVAS_WIDTH, PERCEIVED_SIGMA_FRAC, PERCEIVED_THRESHOLD
from models import TreeNode, TargetShadow
from printability import score as printability_score
from projection import default_projectors, uv_to_pixels


def _rasterize_shadows(
    trees: list[TreeNode], img_width: int, img_height: int
) -> tuple[list[list[float]], ...]:
    """Draw the tree onto one half-width shadow grid per light (Z wall, X wall)."""
    half_width = img_width // 2
    projectors = default_projectors(img_width, img_height)

    index = {n.id: i for i, n in enumerate(trees)}
    segments = [
        (index[n.parentId], i)
        for i, n in enumerate(trees)
        if n.parentId and n.parentId in index
    ]
    grids = [[[0.0] * half_width for _ in range(img_height)] for _ in projectors]
    if not segments:
        return tuple(grids)

    points = np.array([[n.x, n.y, n.z] for n in trees])
    radii = np.array([n.radius for n in trees])

    for grid, projector in zip(grids, projectors):
        u, v = projector.project(points)
        px, py = uv_to_pixels(u, v, img_height, half_width)
        scale = projector.scale_at(points)
        for parent_i, child_i in segments:
            thickness = (radii[child_i] + radii[parent_i]) / 2 * scale[child_i]
            line_width = max(1, int(thickness * half_width / CANVAS_WIDTH))
            _draw_line(
                grid,
                int(px[parent_i]),
                int(py[parent_i]),
                int(px[child_i]),
                int(py[child_i]),
                line_width,
                half_width,
            )

    return tuple(grids)


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


def _perceived_mask(mask: np.ndarray, sigma: float, threshold: float) -> np.ndarray:
    """What a viewer sees from afar: blur the shadow and keep pixels whose local
    darkness density reaches `threshold`. Thin, dense branches then read as a
    filled region, like the (filled) target silhouettes."""
    img = Image.fromarray((mask.astype(np.uint8) * 255), "L")
    blurred = np.asarray(img.filter(ImageFilter.GaussianBlur(sigma)))
    return blurred >= threshold * 255


@lru_cache(maxsize=16)
def _target_perceived_masks(image_data: str) -> tuple[np.ndarray, np.ndarray]:
    """Perceived (left, right) masks of a target image; cached across candidates."""
    arr = _decode_image(image_data)
    height, width = arr.shape
    half = width // 2
    sigma = PERCEIVED_SIGMA_FRAC * half
    dark = arr < 128
    left = _perceived_mask(dark[:, :half], sigma, PERCEIVED_THRESHOLD)
    right = _perceived_mask(dark[:, width - half :], sigma, PERCEIVED_THRESHOLD)
    left.setflags(write=False)
    right.setflags(write=False)
    return left, right


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    union = np.logical_or(a, b).sum()
    if union == 0:
        return 0.0
    return float(np.logical_and(a, b).sum() / union)


def shadow_match_per_light(
    trees: list[TreeNode], target_shadows: list[TargetShadow]
) -> list[float]:
    """IoU of the perceived rendered shadow vs the perceived target, per light.

    Light index 0 is compared with the left half of its image, index 1 with the
    right half (see ISSUES: lightVector is not interpreted yet).
    """
    scores = []
    for i, target in enumerate(target_shadows):
        left, right = _target_perceived_masks(target.imageData)
        target_mask = left if i == 0 else right
        height, half = target_mask.shape
        gen_z, gen_x = _get_shadow_arrays(trees, half * 2, height)
        gen = gen_z if i == 0 else gen_x
        sigma = PERCEIVED_SIGMA_FRAC * half
        scores.append(_iou(_perceived_mask(gen, sigma, PERCEIVED_THRESHOLD), target_mask))
    return scores


def combine_lights(scores: list[float]) -> float:
    """Harmonic mean: every shadow has to work, a bad one drags the total down."""
    if not scores or min(scores) <= 0:
        return 0.0
    return float(len(scores) / sum(1.0 / s for s in scores))


def calculate_fitness(
    trees: list[TreeNode],
    target_shadows: list[TargetShadow],
    reference_width: int = 512,
    reference_height: int = 153,
    nozzle: str = "0.4",
) -> tuple[float, float]:
    if not target_shadows or not trees:
        return 0.0, 0.0

    shadow_match = combine_lights(shadow_match_per_light(trees, target_shadows))
    printability = printability_score(trees, nozzle)
    return shadow_match, printability
