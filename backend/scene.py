import math
import random
import time

from geometry import _get_all_segments
from models import Fitness, GeneticParams, GenerationParams, SceneData, TreeNode
from shadow import _generate_shadow_image
from tree_gen import _generate_tree, _generate_uuid


def _generate_initial_scenes(count: int, params: GenerationParams) -> list[SceneData]:
    scenes: list[SceneData] = []

    for _ in range(count):
        trees: list[TreeNode] = []
        for t in range(params.treeCount):
            angle = (t / params.treeCount) * math.pi * 2 + (random.random() * 0.5)
            radius = random.random() * 3.5
            tx = math.cos(angle) * radius
            tz = math.sin(angle) * radius

            new_tree_nodes = _generate_tree(tx, tz, params, trees)
            trees.extend(new_tree_nodes)

        shadow_url = _generate_shadow_image(trees)

        scenes.append(
            SceneData(
                id=_generate_uuid(),
                trees=trees,
                fitness=Fitness(
                    printability=0.5 + random.random() * 0.5,
                    shadowMatch=0.3 + random.random() * 0.5,
                ),
                shadowImageUrl=shadow_url,
                generation=0,
                timestamp=int(time.time() * 1000),
            )
        )

    scenes.sort(key=lambda s: s.fitness.shadowMatch, reverse=True)
    return scenes


def _evolve_scenes(parent: SceneData, params: GeneticParams) -> list[SceneData]:
    from config import BOUNDS
    from geometry import _check_collision
    from models import Vec3

    offspring: list[SceneData] = []

    for _ in range(params.populationSize):
        new_trees = [TreeNode(**t.model_dump()) for t in parent.trees]

        node_map = {n.id: n for n in new_trees}

        current_segments = _get_all_segments(new_trees)

        for node in new_trees:
            if node.parentId and random.random() < params.mutationRate:
                original_pos = Vec3(x=node.x, y=node.y, z=node.z)

                mx = (random.random() - 0.5) * 0.8
                my = (random.random() - 0.5) * 0.8
                mz = (random.random() - 0.5) * 0.8

                candidate = Vec3(
                    x=node.x + mx,
                    y=node.y + my,
                    z=node.z + mz,
                )

                if candidate.x < BOUNDS["minX"] or candidate.x > BOUNDS["maxX"]:
                    candidate.x = original_pos.x
                if candidate.y < BOUNDS["minY"] or candidate.y > BOUNDS["maxY"]:
                    candidate.y = original_pos.y
                if candidate.z < BOUNDS["minZ"] or candidate.z > BOUNDS["maxZ"]:
                    candidate.z = original_pos.z

                if (
                    candidate.x == original_pos.x
                    and candidate.y == original_pos.y
                    and candidate.z == original_pos.z
                ):
                    continue

                parent_node = node_map.get(node.parentId)
                children = [n for n in new_trees if n.parentId == node.id]

                collision = False

                if parent_node:
                    avg_r = (parent_node.radius + node.radius) / 2
                    if _check_collision(
                        Vec3(x=parent_node.x, y=parent_node.y, z=parent_node.z),
                        candidate,
                        avg_r,
                        current_segments,
                        [node.id, parent_node.id],
                    ):
                        collision = True

                if not collision:
                    for child in children:
                        avg_r = (node.radius + child.radius) / 2
                        if _check_collision(
                            candidate,
                            Vec3(x=child.x, y=child.y, z=child.z),
                            avg_r,
                            current_segments,
                            [node.id, child.id],
                        ):
                            collision = True
                            break

                if not collision:
                    node.x = candidate.x
                    node.y = candidate.y
                    node.z = candidate.z
                    current_segments = _get_all_segments(new_trees)

        shadow_url = _generate_shadow_image(new_trees)

        offspring.append(
            SceneData(
                id=_generate_uuid(),
                trees=new_trees,
                fitness=Fitness(
                    printability=min(
                        1, parent.fitness.printability + (random.random() - 0.5) * 0.2
                    ),
                    shadowMatch=min(
                        1, parent.fitness.shadowMatch + (random.random() - 0.3) * 0.2
                    ),
                ),
                shadowImageUrl=shadow_url,
                generation=parent.generation + params.generations,
                timestamp=int(time.time() * 1000),
            )
        )

    offspring.sort(key=lambda s: s.fitness.shadowMatch, reverse=True)
    return offspring


def _export_to_obj(scene: SceneData) -> str:
    obj_output = "# Shadow Evolution Export\n"

    for node in scene.trees:
        obj_output += f"v {node.x:.4f} {node.y:.4f} {node.z:.4f}\n"

    id_to_index: dict[str, int] = {}
    for index, node in enumerate(scene.trees):
        id_to_index[node.id] = index + 1

    obj_output += "\n"

    for node in scene.trees:
        if node.parentId:
            parent_idx = id_to_index.get(node.parentId)
            current_idx = id_to_index.get(node.id)
            if parent_idx and current_idx:
                obj_output += f"l {parent_idx} {current_idx}\n"

    return obj_output
