from config import BOUNDS, Y_BASE
from voxel import _calculate_intersection_volume

from conftest import make_targets, solid_image, to_data_url


def test_no_targets_returns_empty():
    assert _calculate_intersection_volume([]) == ([], [])


def test_all_black_gives_attractors_and_no_repulsors():
    att, rep = _calculate_intersection_volume(
        make_targets(to_data_url(solid_image(100, 30, 0)))
    )
    assert len(att) > 0
    assert rep == []


def test_all_white_gives_repulsors_and_no_attractors():
    att, rep = _calculate_intersection_volume(
        make_targets(to_data_url(solid_image(100, 30, 255)))
    )
    assert att == []
    assert len(rep) > 0


def test_ct_attractors_inside_bounds(ct_volume):
    att, rep = ct_volume
    assert len(att) > 0 and len(rep) > 0
    for a in att:
        assert BOUNDS["minX"] <= a.x <= BOUNDS["maxX"]
        assert BOUNDS["minZ"] <= a.z <= BOUNDS["maxZ"]
        assert a.y >= Y_BASE


def test_ct_attractors_and_repulsors_are_disjoint(ct_volume):
    att, rep = ct_volume
    assert {(a.x, a.y, a.z) for a in att}.isdisjoint({(r.x, r.y, r.z) for r in rep})
