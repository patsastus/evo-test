"""Shared wall-projection helpers used by voxel.py (target shadows -> volume)
and shadow.py (tree -> rendered shadows)."""

from config import CANVAS_WIDTH, X_MIN, Z_MIN, Y_BASE


def calculate_wall_height(img_height: int, img_width: int) -> float:
    half_width = img_width // 2
    if half_width == 0:
        half_width = 1
    half_aspect_ratio = img_height / half_width
    return CANVAS_WIDTH * half_aspect_ratio


def to_z_wall_uv(x: float, y: float, z: float, wall_height: float) -> tuple[float, float]:
    u = (z - Z_MIN) / CANVAS_WIDTH
    v = (y - Y_BASE) / wall_height
    return u, v


def to_x_wall_uv(x: float, y: float, z: float, wall_height: float) -> tuple[float, float]:
    u = (x - X_MIN) / CANVAS_WIDTH
    v = (y - Y_BASE) / wall_height
    return u, v


def uv_to_pixel(
    u: float, v: float, img_height: int, half_width: int
) -> tuple[int, int]:
    px = int(u * half_width)
    py = int((1 - v) * img_height)
    px = max(0, min(px, half_width - 1))
    py = max(0, min(py, img_height - 1))
    return px, py
