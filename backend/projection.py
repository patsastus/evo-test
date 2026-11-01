"""Projection of 3D points onto the shadow walls.

This is the seam between "where the lights are" and the rest of the pipeline.
voxel.py (target shadows -> attractor volume) and shadow.py (tree -> rendered
shadows) only talk to the `Projector` interface; today the only implementation
is `ParallelWallProjector` (parallel light, orthographic). A point-light
implementation (perspective: ray from the light through the point to the wall)
plugs in here without touching callers.

A projector maps scene points to wall coordinates (u, v) in [0, 1] x [0, 1]
(u across the wall, v up it) and reports the local length magnification, which
callers use to scale branch thickness (1.0 for parallel light).
"""

from typing import Literal, Protocol

import numpy as np

from config import CANVAS_WIDTH, X_MIN, Z_MIN, Y_BASE


def calculate_wall_height(img_height: int, img_width: int) -> float:
    half_width = img_width // 2
    if half_width == 0:
        half_width = 1
    half_aspect_ratio = img_height / half_width
    return CANVAS_WIDTH * half_aspect_ratio


class Projector(Protocol):
    def project(self, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(N, 3) scene points -> (u, v), each shape (N,)."""
        ...

    def scale_at(self, points: np.ndarray) -> np.ndarray:
        """(N, 3) scene points -> length magnification on the wall, shape (N,)."""
        ...


class ParallelWallProjector:
    """Parallel light straight onto a wall: drops one horizontal axis.

    wall="z": light travels along x, the shadow falls on the Z-Y wall (u follows z).
    wall="x": light travels along z, the shadow falls on the X-Y wall (u follows x).
    """

    def __init__(self, wall: Literal["z", "x"], wall_height: float):
        self.wall = wall
        self.wall_height = wall_height

    def project(self, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        pts = np.asarray(points, dtype=float).reshape(-1, 3)
        if self.wall == "z":
            u = (pts[:, 2] - Z_MIN) / CANVAS_WIDTH
        else:
            u = (pts[:, 0] - X_MIN) / CANVAS_WIDTH
        v = (pts[:, 1] - Y_BASE) / self.wall_height
        return u, v

    def scale_at(self, points: np.ndarray) -> np.ndarray:
        return np.ones(len(np.asarray(points).reshape(-1, 3)))


def default_projectors(img_width: int, img_height: int) -> tuple[Projector, Projector]:
    """The current rig, in light-index order: light 0 -> Z wall (left half of the
    target image), light 1 -> X wall (right half)."""
    wall_height = calculate_wall_height(img_height, img_width)
    return (
        ParallelWallProjector("z", wall_height),
        ParallelWallProjector("x", wall_height),
    )


def uv_to_pixels(
    u: np.ndarray, v: np.ndarray, img_height: int, half_width: int
) -> tuple[np.ndarray, np.ndarray]:
    """Vectorised wall coords -> pixel indices, truncating then clamping."""
    px = np.trunc(np.asarray(u) * half_width).astype(np.int64)
    py = np.trunc((1 - np.asarray(v)) * img_height).astype(np.int64)
    return np.clip(px, 0, half_width - 1), np.clip(py, 0, img_height - 1)


# Scalar helpers (kept for tests and simple callers).
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
    px, py = uv_to_pixels(np.array([u]), np.array([v]), img_height, half_width)
    return int(px[0]), int(py[0])
