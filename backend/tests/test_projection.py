import numpy as np
from PIL import Image

import shadow
import voxel
from config import CANVAS_WIDTH
from models import TreeNode
from projection import (
    ParallelWallProjector,
    calculate_wall_height,
    default_projectors,
    to_x_wall_uv,
    to_z_wall_uv,
    uv_to_pixel,
    uv_to_pixels,
)

from conftest import make_targets, solid_image, to_data_url


def test_wall_height_uses_half_width_aspect():
    # 100 wide -> 50 per half; 25 tall -> aspect 0.5
    assert calculate_wall_height(25, 100) == CANVAS_WIDTH * 0.5


def test_wall_height_tiny_width_does_not_divide_by_zero():
    assert calculate_wall_height(10, 1) == CANVAS_WIDTH * 10


def test_uv_mapping_axes():
    # Z wall's u follows z, X wall's u follows x
    assert to_z_wall_uv(99, 0.5, -5, 10)[0] == 0.0
    assert to_x_wall_uv(5, 0.5, 99, 10)[0] == 1.0


def test_uv_to_pixel_clamps_to_bounds():
    assert uv_to_pixel(-1, 2, 40, 20) == (0, 0)
    assert uv_to_pixel(5, -3, 40, 20) == (19, 39)
    assert uv_to_pixel(0.5, 0.5, 40, 20) == (10, 20)


# ---- Projector seam ----------------------------------------------------------

def test_parallel_projector_matches_scalar_helpers():
    pts = np.array([[-5.0, 0.5, 5.0], [0.0, 3.3, -2.0], [4.5, 9.0, 1.0]])
    wh = calculate_wall_height(153, 347)
    u, v = ParallelWallProjector("z", wh).project(pts)
    for p, ui, vi in zip(pts, u, v):
        assert (ui, vi) == to_z_wall_uv(*p, wh)
    u, v = ParallelWallProjector("x", wh).project(pts)
    for p, ui, vi in zip(pts, u, v):
        assert (ui, vi) == to_x_wall_uv(*p, wh)


def test_vectorised_pixels_match_scalar_including_clamping():
    rng = np.random.default_rng(1)
    u, v = rng.uniform(-0.5, 1.5, 200), rng.uniform(-0.5, 1.5, 200)
    px, py = uv_to_pixels(u, v, 153, 173)
    for i in range(200):
        assert (px[i], py[i]) == uv_to_pixel(u[i], v[i], 153, 173)


def test_parallel_magnification_is_one_and_default_rig_order():
    z, x = default_projectors(347, 153)
    assert z.wall == "z" and x.wall == "x"  # light 0 -> Z wall, light 1 -> X wall
    assert (z.scale_at(np.zeros((4, 3))) == 1.0).all()


class _Wrap:
    """Test projector: parallel projection with optional overrides."""

    def __init__(self, inner, scale=1.0, const_uv=None):
        self.inner, self.scale, self.const_uv = inner, scale, const_uv

    def project(self, points):
        u, v = self.inner.project(points)
        if self.const_uv is not None:
            return np.full_like(u, self.const_uv[0]), np.full_like(v, self.const_uv[1])
        return u, v

    def scale_at(self, points):
        return np.full(len(points), self.scale)


def _vertical_stick():
    return [
        TreeNode(id="a", x=0, y=1, z=0, radius=0.1, parentId=None),
        TreeNode(id="b", x=0, y=6, z=0, radius=0.1, parentId="a"),
    ]


def test_renderer_uses_projector_magnification(monkeypatch):
    base = shadow._get_shadow_arrays(_vertical_stick(), 200, 80)
    real = shadow.default_projectors
    monkeypatch.setattr(
        shadow, "default_projectors", lambda w, h: tuple(_Wrap(p, scale=4.0) for p in real(w, h))
    )
    fat = shadow._get_shadow_arrays(_vertical_stick(), 200, 80)
    assert fat[0].sum() > 2 * base[0].sum() and fat[1].sum() > 2 * base[1].sum()


def test_voxel_stage_uses_projector(monkeypatch):
    # Target: dark disc only at the wall centre. Projecting every voxel to the wall
    # centre must then make the whole scene volume attractors; real parallel
    # projection only keeps the voxels behind the disc.
    img = Image.new("L", (200, 80), 255)
    img.paste(0, (45, 30, 55, 50))  # left half centre
    img.paste(0, (145, 30, 155, 50))  # right half centre
    targets = make_targets(to_data_url(img))
    real_att, _ = voxel._calculate_intersection_volume(targets)

    real = voxel.default_projectors
    monkeypatch.setattr(
        voxel,
        "default_projectors",
        lambda w, h: tuple(_Wrap(p, const_uv=(0.5, 0.5)) for p in real(w, h)),
    )
    const_att, _ = voxel._calculate_intersection_volume(targets)
    black_all, _ = voxel._calculate_intersection_volume(
        make_targets(to_data_url(solid_image(200, 80, 0)))
    )
    assert 0 < len(real_att) < len(const_att)
    assert len(const_att) == len(black_all)  # every in-domain voxel
