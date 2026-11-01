import dataclasses
import io

import manifold3d as m3d
import pytest
import trimesh
from fastapi.testclient import TestClient

from app import app
from connector import DEFAULT_CONNECTOR, ConnectorSpec, PegSpec
from mesh import (
    build_foot_manifold,
    build_scene_mesh,
    build_tree_manifold,
    mesh_report,
    roots_outside_foot,
    to_print_space,
    to_trimesh,
)
from models import TreeNode
from sca import grow_tree
from models import AttractorPoint, TreeGenome

client = TestClient(app)


def stick(height=5.0, steps=10, radius=0.2, x=0.0, z=0.0):
    nodes = [TreeNode(id="n0", x=x, y=0, z=z, radius=radius, parentId=None)]
    for i in range(1, steps + 1):
        nodes.append(
            TreeNode(id=f"n{i}", x=x, y=height * i / steps, z=z, radius=radius, parentId=f"n{i-1}")
        )
    return nodes


def test_print_space_is_a_rotation_not_a_mirror():
    # (x, y-up, z) -> (x, -z, y) * 10 ; determinant of the linear map must be +1
    assert to_print_space(1, 2, 3) == (10.0, -30.0, 20.0)
    import numpy as np

    m = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]])
    assert round(np.linalg.det(m)) == 1


def test_scene_mesh_is_watertight_single_solid():
    mesh = build_scene_mesh(stick())
    rep = mesh_report(mesh)
    assert rep["watertight"] and rep["winding_consistent"]
    assert rep["volume_mm3"] > 0


def test_scene_is_one_piece_even_with_several_trees():
    nodes, _, _ = grow_tree(
        [AttractorPoint(x=0, y=4, z=0)], tree_count=4, genome=TreeGenome(), max_new_nodes=20
    )
    from mesh import build_scene_manifold

    assert len(build_scene_manifold(nodes).decompose()) == 1


def test_tree_height_and_scale_are_100mm_per_scene():
    mesh = to_trimesh(build_tree_manifold(stick(height=5.0, radius=0.2)))
    lo, hi = mesh.bounds
    assert hi[2] == pytest.approx(5.0 * 10 + 2.0, abs=0.2)  # top sphere radius 2 mm
    assert (hi[0] - lo[0]) == pytest.approx(4.0, abs=0.3)  # 0.2 units radius -> 4 mm dia


def test_scene_z_maps_to_negative_print_y():
    mesh = to_trimesh(build_tree_manifold(stick(z=2.0)))
    assert mesh.bounds[:, 1].mean() == pytest.approx(-20.0, abs=0.5)


def test_foot_geometry_and_sockets():
    spec = DEFAULT_CONNECTOR
    foot = to_trimesh(build_foot_manifold(spec))
    lo, hi = foot.bounds
    assert hi[2] == pytest.approx(0.0, abs=1e-6)
    assert lo[2] == pytest.approx(-spec.foot_height, abs=1e-6)
    assert (hi[0] - lo[0], hi[1] - lo[1]) == pytest.approx((spec.foot_width, spec.foot_depth))
    solid = spec.foot_width * spec.foot_depth * spec.foot_height
    assert foot.volume < solid  # sockets removed
    assert foot.is_watertight


def solid_at(manifold, point, size=0.2):
    probe = m3d.Manifold.cube((size,) * 3, center=True).translate(tuple(point))
    return (manifold ^ probe).volume() > 0.5 * size**3


def test_sockets_open_on_bottom_face_and_are_closed_on_top():
    spec = DEFAULT_CONNECTOR
    foot = build_foot_manifold(spec)
    for peg in spec.pegs:
        r = spec.socket_radius(peg)
        # inside the socket just above the bottom face -> empty
        assert not solid_at(foot, (peg.x, peg.y, -spec.foot_height + 1.0))
        # roof above the socket is solid
        assert solid_at(foot, (peg.x, peg.y, -0.5))
        # beside the socket is solid
        assert solid_at(foot, (peg.x, peg.y + r + 1.0, -spec.foot_height + 1.0))


def test_socket_ceiling_has_no_flat_overhang():
    # No downward-facing, near-horizontal faces except the foot's own bottom plane.
    spec = DEFAULT_CONNECTOR
    foot = to_trimesh(build_foot_manifold(spec))
    down_flat = foot.face_normals[:, 2] < -0.99
    z_of_flat = foot.triangles_center[down_flat][:, 2]
    assert z_of_flat.max() == pytest.approx(-spec.foot_height, abs=1e-6)


def test_connector_is_keyed_no_rotational_symmetry():
    spec = DEFAULT_CONNECTOR
    mesh = to_trimesh(build_foot_manifold(spec))
    for k in (1, 2, 3):
        rot = trimesh.transformations.rotation_matrix(k * 3.14159265 / 2, [0, 0, 1])
        rotated = mesh.copy()
        rotated.apply_transform(rot)
        # overlap volume with the original must be less than the full volume
        inter = trimesh.boolean.intersection([mesh, rotated], engine="manifold")
        assert inter.volume < mesh.volume - 1.0


def test_symmetric_spec_is_detectable_as_not_keyed():
    sym = dataclasses.replace(
        DEFAULT_CONNECTOR,
        pegs=(PegSpec(-15, 0, 6.0), PegSpec(15, 0, 6.0)),
    )
    mesh = to_trimesh(build_foot_manifold(sym))
    rot = trimesh.transformations.rotation_matrix(3.14159265, [0, 0, 1])
    rotated = mesh.copy()
    rotated.apply_transform(rot)
    inter = trimesh.boolean.intersection([mesh, rotated], engine="manifold")
    assert inter.volume == pytest.approx(mesh.volume, rel=1e-3)


def test_spec_validation_rejects_too_deep_or_outside_sockets():
    with pytest.raises(ValueError):
        dataclasses.replace(DEFAULT_CONNECTOR, foot_height=5.0).validate()
    with pytest.raises(ValueError):
        dataclasses.replace(
            DEFAULT_CONNECTOR, pegs=(PegSpec(34.0, 0.0, 8.0),)
        ).validate()


def test_roots_outside_foot_detected():
    far = stick(x=4.0)  # 40 mm from centre, foot half-width is 35 mm
    assert roots_outside_foot(far) == ["n0"]
    with pytest.raises(ValueError):
        build_scene_mesh(far)


def export_body():
    nodes = [n.model_dump() for n in stick()]
    return {
        "scene": {
            "id": "s",
            "trees": nodes,
            "fitness": {"printability": 0, "shadowMatch": 0},
            "shadowImageUrl": "",
            "generation": 0,
            "timestamp": 0,
        }
    }


def test_export_mesh_stl_roundtrips_watertight():
    r = client.post("/export/mesh", json=export_body())
    assert r.status_code == 200
    assert r.headers["X-Mesh-Watertight"] == "true"
    loaded = trimesh.load(io.BytesIO(r.content), file_type="stl")
    assert loaded.is_watertight and loaded.volume > 0


def test_export_mesh_obj_has_faces():
    r = client.post("/export/mesh", params={"format": "obj"}, json=export_body())
    assert r.status_code == 200
    assert b"\nf " in r.content


def test_export_mesh_rejects_root_outside_foot():
    body = export_body()
    for n in body["scene"]["trees"]:
        n["x"] += 4.0
    assert client.post("/export/mesh", json=body).status_code == 422


def test_old_skeleton_export_still_works():
    assert "obj" in client.post("/export/obj", json=export_body()).json()
