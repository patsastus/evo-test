import math
from typing import Optional

from pydantic import BaseModel

from models import Vec3, TreeNode


class Segment(BaseModel):
    p1: Vec3
    p2: Vec3
    radius: float
    nodeId: str
    parentId: str


def _sub(v1: Vec3, v2: Vec3) -> Vec3:
    return Vec3(x=v1.x - v2.x, y=v1.y - v2.y, z=v1.z - v2.z)


def _dot(v1: Vec3, v2: Vec3) -> float:
    return v1.x * v2.x + v1.y * v2.y + v1.z * v2.z


def _get_seg_seg_dist(p1: Vec3, p2: Vec3, p3: Vec3, p4: Vec3) -> float:
    u = _sub(p2, p1)
    v = _sub(p4, p3)
    w = _sub(p1, p3)
    a = _dot(u, u)
    b = _dot(u, v)
    c = _dot(v, v)
    d = _dot(u, w)
    e = _dot(v, w)
    d_val = a * c - b * b

    small_num = 0.00000001

    s_d = d_val
    t_d = d_val

    if d_val < small_num:
        s_n = 0.0
        s_d = 1.0
        t_n = e
        t_d = c
    else:
        s_n = b * e - c * d
        t_n = a * e - b * d
        if s_n < 0.0:
            s_n = 0.0
            t_n = e
            t_d = c
        elif s_n > s_d:
            s_n = s_d
            t_n = e + b
            t_d = c

    if t_n < 0.0:
        t_n = 0.0
        if -d < 0.0:
            s_n = 0.0
        elif -d > a:
            s_n = s_d
        else:
            s_n = -d
            s_d = a
    elif t_n > t_d:
        t_n = t_d
        if (-d + b) < 0.0:
            s_n = 0.0
        elif (-d + b) > a:
            s_n = s_d
        else:
            s_n = -d + b
            s_d = a

    sc = 0.0 if abs(s_n) < small_num else s_n / s_d
    tc = 0.0 if abs(t_n) < small_num else t_n / t_d

    d_p = Vec3(
        x=w.x + (sc * u.x) - (tc * v.x),
        y=w.y + (sc * u.y) - (tc * v.y),
        z=w.z + (sc * u.z) - (tc * v.z),
    )

    return math.sqrt(_dot(d_p, d_p))


def _get_all_segments(nodes: list[TreeNode]) -> list[Segment]:
    node_map = {n.id: n for n in nodes}
    segments: list[Segment] = []
    for n in nodes:
        if n.parentId:
            p = node_map.get(n.parentId)
            if p:
                segments.append(
                    Segment(
                        p1=Vec3(x=p.x, y=p.y, z=p.z),
                        p2=Vec3(x=n.x, y=n.y, z=n.z),
                        radius=(n.radius + p.radius) / 2,
                        nodeId=n.id,
                        parentId=p.id,
                    )
                )
    return segments


def _check_collision(
    p1: Vec3,
    p2: Vec3,
    r: float,
    segments: list[Segment],
    ignore_node_ids: Optional[list[str]] = None,
) -> bool:
    if ignore_node_ids is None:
        ignore_node_ids = []
    for seg in segments:
        if seg.nodeId in ignore_node_ids or seg.parentId in ignore_node_ids:
            continue

        dist = _get_seg_seg_dist(p1, p2, seg.p1, seg.p2)
        threshold = (r + seg.radius) * 0.85

        if dist < threshold:
            return True
    return False
