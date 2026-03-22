import math
import random
import uuid

from config import BOUNDS
from geometry import Segment, _check_collision, _get_all_segments
from models import GenerationParams, TreeNode, Vec3


def _generate_uuid() -> str:
    return uuid.uuid4().hex[:9]


def _generate_tree(
    root_x: float,
    root_z: float,
    params: GenerationParams,
    existing_scene_nodes: list[TreeNode],
) -> list[TreeNode]:
    nodes: list[TreeNode] = []
    scene_segments = _get_all_segments(existing_scene_nodes)

    def add_local_segment(n: TreeNode, p: TreeNode) -> None:
        scene_segments.append(
            Segment(
                p1=Vec3(x=p.x, y=p.y, z=p.z),
                p2=Vec3(x=n.x, y=n.y, z=n.z),
                radius=(n.radius + p.radius) / 2,
                nodeId=n.id,
                parentId=p.id,
            )
        )

    safe_root_x = max(BOUNDS["minX"] + 1, min(BOUNDS["maxX"] - 1, root_x))
    safe_root_z = max(BOUNDS["minZ"] + 1, min(BOUNDS["maxZ"] - 1, root_z))

    root_id = _generate_uuid()
    root_node = TreeNode(
        id=root_id,
        x=safe_root_x,
        y=0,
        z=safe_root_z,
        radius=min(params.maxThickness, 0.8),
        parentId=None,
    )
    nodes.append(root_node)

    queue = [
        {
            "id": root_id,
            "x": safe_root_x,
            "y": 0,
            "z": safe_root_z,
            "level": 0,
            "dir": Vec3(x=0, y=1, z=0),
            "radius": root_node.radius,
        }
    ]

    max_levels = 6

    while queue:
        current = queue.pop(0)
        if current["level"] >= max_levels:
            continue

        branch_count = 2 if random.random() < params.branchingProb else 1

        for i in range(branch_count):
            added = False
            for attempt in range(3):
                angle_mod_x = (
                    (random.random() - 0.5) * params.maxAngle * (1 + attempt * 0.5)
                )
                angle_mod_z = (
                    (random.random() - 0.5) * params.maxAngle * (1 + attempt * 0.5)
                )

                new_dir = Vec3(
                    x=current["dir"].x + angle_mod_x,
                    y=current["dir"].y,
                    z=current["dir"].z + angle_mod_z,
                )

                length = math.sqrt(new_dir.x**2 + new_dir.y**2 + new_dir.z**2)
                new_dir.x /= length
                new_dir.y /= length
                new_dir.z /= length

                branch_length = 1.5 - (current["level"] * 0.15)

                new_x = current["x"] + new_dir.x * branch_length
                new_y = current["y"] + new_dir.y * branch_length
                new_z = current["z"] + new_dir.z * branch_length

                if (
                    new_x < BOUNDS["minX"]
                    or new_x > BOUNDS["maxX"]
                    or new_z < BOUNDS["minZ"]
                    or new_z > BOUNDS["maxZ"]
                    or new_y > BOUNDS["maxY"]
                    or new_y < BOUNDS["minY"]
                ):
                    continue

                new_id = _generate_uuid()
                new_radius = params.maxThickness * (
                    1 - (current["level"] + 1) / (max_levels + 2)
                )
                avg_radius = (current["radius"] + new_radius) / 2

                start = Vec3(x=current["x"], y=current["y"], z=current["z"])
                end = Vec3(x=new_x, y=new_y, z=new_z)

                if not _check_collision(
                    start, end, avg_radius, scene_segments, [current["id"]]
                ):
                    new_node = TreeNode(
                        id=new_id,
                        x=new_x,
                        y=new_y,
                        z=new_z,
                        radius=max(0.04, new_radius),
                        parentId=current["id"],
                    )

                    nodes.append(new_node)
                    add_local_segment(
                        new_node,
                        TreeNode(
                            id=current["id"],
                            x=current["x"],
                            y=current["y"],
                            z=current["z"],
                            radius=current["radius"],
                        ),
                    )

                    queue.append(
                        {
                            "id": new_id,
                            "x": new_x,
                            "y": new_y,
                            "z": new_z,
                            "level": current["level"] + 1,
                            "dir": new_dir,
                            "radius": new_radius,
                        }
                    )
                    added = True
                    break

    return nodes
