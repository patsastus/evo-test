"""Turn a tree node graph into a printable, watertight solid.

Pipeline: each branch segment is the convex hull of two spheres (one per node, at
the node radius), all segments are unioned with manifold3d, and the result is
fused with a standard scene foot that has keyed sockets (see connector.py).

Coordinates: scene space is (x, y-up, z); print space is millimetres, Z-up, via a
pure rotation about X: (x, y, z) -> (x, -z, y) * MM_PER_UNIT (no mirroring, so
the shadows are not flipped). The tree root (scene y = 0) sits on the foot's top
face at Z = 0; the foot occupies Z in [-foot_height, 0].
"""

import numpy as np
import manifold3d as m3d
import trimesh

from config import MM_PER_UNIT
from connector import DEFAULT_CONNECTOR, ConnectorSpec
from models import TreeNode

SPHERE_SEGMENTS = 10
MIN_RADIUS_MM = 1e-3


def to_print_space(x: float, y: float, z: float, scale: float = MM_PER_UNIT):
    return (x * scale, -z * scale, y * scale)


def build_tree_manifold(
    nodes: list[TreeNode], scale: float = MM_PER_UNIT
) -> m3d.Manifold:
    if not nodes:
        return m3d.Manifold()

    spheres: dict[str, m3d.Manifold] = {}
    positions: dict[str, tuple[float, float, float]] = {}
    for n in nodes:
        r = max(n.radius * scale, MIN_RADIUS_MM)
        p = to_print_space(n.x, n.y, n.z, scale)
        positions[n.id] = p
        spheres[n.id] = m3d.Manifold.sphere(r, SPHERE_SEGMENTS).translate(p)

    pieces: list[m3d.Manifold] = []
    has_children: set[str] = set()
    for n in nodes:
        if n.parentId and n.parentId in spheres:
            has_children.add(n.parentId)
            pieces.append(m3d.Manifold.batch_hull([spheres[n.parentId], spheres[n.id]]))
    # Lone nodes (e.g. a root that never grew) still get a sphere.
    for n in nodes:
        if n.id not in has_children and not (n.parentId and n.parentId in spheres):
            pieces.append(spheres[n.id])

    return m3d.Manifold.batch_boolean(pieces, m3d.OpType.Add)


def build_foot_manifold(spec: ConnectorSpec = DEFAULT_CONNECTOR) -> m3d.Manifold:
    spec.validate()
    foot = m3d.Manifold.cube(
        (spec.foot_width, spec.foot_depth, spec.foot_height), center=True
    ).translate((0.0, 0.0, -spec.foot_height / 2))
    z_bottom = -spec.foot_height
    for peg in spec.pegs:
        r = spec.socket_radius(peg)
        body = m3d.Manifold.cylinder(spec.peg_length, r, r, 48)
        ceiling = m3d.Manifold.cylinder(r, r, 0.0, 48).translate((0, 0, spec.peg_length))
        socket = (body + ceiling).translate((peg.x, peg.y, z_bottom))
        # Extend slightly below the bottom face so the cut is clean.
        socket = socket + m3d.Manifold.cylinder(0.5, r, r, 48).translate(
            (peg.x, peg.y, z_bottom - 0.5)
        )
        foot = foot - socket
    return foot


def roots_outside_foot(
    nodes: list[TreeNode],
    spec: ConnectorSpec = DEFAULT_CONNECTOR,
    scale: float = MM_PER_UNIT,
) -> list[str]:
    """Ids of root nodes whose footprint (incl. radius) falls outside the foot."""
    bad = []
    for n in nodes:
        if n.parentId:
            continue
        x, y, _ = to_print_space(n.x, n.y, n.z, scale)
        r = n.radius * scale
        if abs(x) + r > spec.foot_width / 2 or abs(y) + r > spec.foot_depth / 2:
            bad.append(n.id)
    return bad


def build_scene_manifold(
    nodes: list[TreeNode], spec: ConnectorSpec = DEFAULT_CONNECTOR
) -> m3d.Manifold:
    outside = roots_outside_foot(nodes, spec)
    if outside:
        raise ValueError(f"root nodes outside the standard foot: {outside}")
    return build_tree_manifold(nodes) + build_foot_manifold(spec)


def to_trimesh(manifold: m3d.Manifold) -> trimesh.Trimesh:
    mesh = manifold.to_mesh()
    return trimesh.Trimesh(
        vertices=np.asarray(mesh.vert_properties[:, :3], dtype=np.float64),
        faces=np.asarray(mesh.tri_verts, dtype=np.int64),
        process=False,
    )


def build_scene_mesh(
    nodes: list[TreeNode], spec: ConnectorSpec = DEFAULT_CONNECTOR
) -> trimesh.Trimesh:
    return to_trimesh(build_scene_manifold(nodes, spec))


def mesh_report(mesh: trimesh.Trimesh) -> dict:
    """Basic solidity facts; the printability score builds on these."""
    lo, hi = mesh.bounds
    return {
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "volume_mm3": float(mesh.volume),
        "size_mm": [float(v) for v in (hi - lo)],
        "triangles": int(len(mesh.faces)),
    }
