import math

import pytest
from fastapi.testclient import TestClient

from app import app
from models import TreeNode
from printability import NOZZLE_PROFILES, analyze, score

client = TestClient(app)


def branch(dx=0.0, dy=1.0, dz=0.0, r0=0.2, r1=0.2, x=0.0, z=0.0):
    """Root at (x, 0, z) plus one child offset by (dx, dy, dz) scene units."""
    return [
        TreeNode(id="r", x=x, y=0, z=z, radius=r0, parentId=None),
        TreeNode(id="c", x=x + dx, y=dy, z=z + dz, radius=r1, parentId="r"),
    ]


def test_vertical_thick_branch_is_fully_printable():
    rep = analyze(branch())
    assert rep.gate_ok and rep.score == pytest.approx(1.0)
    assert rep.overhang_length_fraction == 0.0


def test_horizontal_branch_is_a_full_overhang():
    rep = analyze(branch(dx=1.0, dy=0.0))
    assert rep.overhang_score == pytest.approx(0.0)
    assert rep.score == pytest.approx(0.0)
    assert rep.overhang_length_fraction == 1.0


def test_forty_five_degrees_is_the_support_free_limit():
    rep = analyze(branch(dx=1.0, dy=1.0))
    assert rep.overhang_score == pytest.approx(1.0)
    assert rep.overhang_length_fraction == 0.0  # float error at exactly 45 deg must not count


def test_overhang_penalty_is_linear_between_horizontal_and_limit():
    # 22.5 deg elevation -> halfway between horizontal (1.0) and the limit (0.0)
    d = math.tan(math.radians(22.5))
    assert analyze(branch(dx=1.0, dy=d)).overhang_score == pytest.approx(0.5, abs=0.01)


def test_downward_growth_is_judged_by_elevation_not_direction():
    steep_down = [
        TreeNode(id="r", x=0, y=2, z=0, radius=0.2, parentId=None),
        TreeNode(id="c", x=0, y=1, z=0, radius=0.2, parentId="r"),
    ]
    # root at y=2 is fine for the gate (only footprint is checked); vertical tube
    assert analyze(steep_down).overhang_score == pytest.approx(1.0)


def test_thickness_depends_on_nozzle():
    thin = branch(r0=0.02, r1=0.02)  # 0.4 mm diameter at 10 mm/unit
    assert analyze(thin, "0.4").thickness_score == pytest.approx(0.0)  # <= 0.5 fail
    # 0.2 nozzle: warn 0.5, fail 0.3 -> (0.5 - 0.4) / 0.2 = 0.5 penalty
    assert analyze(thin, "0.2").thickness_score == pytest.approx(0.5)


def test_thickness_ramp_between_warn_and_fail():
    p = NOZZLE_PROFILES["0.4"]
    mid = (p.warn_diameter + p.fail_diameter) / 2
    r_units = mid / 2 / 10
    rep = analyze(branch(r0=r_units, r1=r_units), "0.4")
    assert rep.thickness_score == pytest.approx(0.5)
    assert rep.thin_length_fraction == 1.0
    assert rep.unprintable_length_fraction == 0.0


def test_tapered_segment_is_judged_by_its_thin_end():
    rep = analyze(branch(r0=0.3, r1=0.02))
    assert rep.min_diameter_mm == pytest.approx(0.4)
    assert rep.thickness_score == pytest.approx(0.0)


def test_thickness_is_length_weighted():
    nodes = [
        TreeNode(id="r", x=0, y=0, z=0, radius=0.2, parentId=None),
        TreeNode(id="a", x=0, y=3, z=0, radius=0.2, parentId="r"),  # 3 units thick
        TreeNode(id="b", x=0, y=4, z=0, radius=0.02, parentId="a"),  # 1 unit thin
    ]
    # thin end of segment b is at b; segment b min diameter 0.4 mm -> penalty 1 on 1/4
    assert analyze(nodes, "0.4").thickness_score == pytest.approx(0.75)


@pytest.mark.parametrize(
    "nodes, reason",
    [
        ([], "no nodes"),
        ([TreeNode(id="r", x=0, y=0, z=0, radius=0.2, parentId=None)], "no branches"),
        (branch(x=4.0), "outside the standard foot"),
    ],
)
def test_gate_failures_score_zero_with_reason(nodes, reason):
    rep = analyze(nodes)
    assert not rep.gate_ok and rep.score == 0.0
    assert reason in rep.gate_reason


def test_com_offset_and_height_reported():
    rep = analyze(branch(dy=4.0, x=2.0))  # 20 mm off-centre, 40 mm tall, midpoint 20 mm
    assert rep.com_offset_mm == pytest.approx(20.0, abs=0.01)
    assert rep.com_height_mm == pytest.approx(20.0, abs=0.01)


def test_unknown_nozzle_rejected():
    with pytest.raises(ValueError):
        analyze(branch(), "0.6")


def test_score_helper_matches_report():
    nodes = branch(dx=1.0, dy=0.5)
    assert score(nodes) == analyze(nodes).score


def scene_body(nodes):
    return {
        "scene": {
            "id": "s",
            "trees": [n.model_dump() for n in nodes],
            "fitness": {"printability": 0, "shadowMatch": 0},
            "shadowImageUrl": "",
            "generation": 0,
            "timestamp": 0,
        }
    }


def test_report_endpoint_includes_mesh_checks():
    r = client.post("/scenes/printability", json=scene_body(branch(dy=4.0)))
    assert r.status_code == 200
    data = r.json()
    assert data["printability"]["gate_ok"] and data["printability"]["nozzle"] == "0.4"
    assert data["mesh"]["watertight"] and data["mesh"]["volume_mm3"] > 0


def test_report_endpoint_gate_failure_has_no_mesh():
    r = client.post("/scenes/printability", json=scene_body(branch(x=4.0)))
    assert r.json()["mesh"] is None and not r.json()["printability"]["gate_ok"]


def test_report_endpoint_nozzle_param_and_validation():
    thin = scene_body(branch(r0=0.02, r1=0.02, dy=4.0))
    a = client.post("/scenes/printability", params={"nozzle": "0.4"}, json=thin).json()
    b = client.post("/scenes/printability", params={"nozzle": "0.2"}, json=thin).json()
    assert a["printability"]["score"] < b["printability"]["score"]
    assert client.post("/scenes/printability", params={"nozzle": "9"}, json=thin).status_code == 422
