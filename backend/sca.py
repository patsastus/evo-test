import math
import uuid
from typing import Optional

import numpy as np

from models import AttractorPoint, GenerationStats, TreeGenome, TreeNode


def _generate_uuid() -> str:
    return uuid.uuid4().hex[:9]


def grow_tree(
    attractors: list[AttractorPoint],
    tree_count: int = 1,
    repulsion_points: Optional[list[AttractorPoint]] = None,
    genome: Optional[TreeGenome] = None,
    existing_nodes: Optional[list[TreeNode]] = None,
    max_new_nodes: int = 500,
) -> tuple[list[TreeNode], GenerationStats, list[AttractorPoint]]:
    if repulsion_points is None:
        repulsion_points = []

    if genome is None:
        genome = TreeGenome()

    np.random.seed(genome.random_seed)

    original_attractor_count = len(attractors)
    total_attractors = original_attractor_count

    if len(attractors) > 400:
        indices = np.random.choice(len(attractors), 400, replace=False)
        attractors = [attractors[i] for i in indices]
        total_attractors = 400

    if len(repulsion_points) > 100:
        if attractors:
            rep_y_min = min(a.y for a in attractors)
            filtered_repulsion = [r for r in repulsion_points if r.y >= rep_y_min]
            if len(filtered_repulsion) > 100:
                indices = np.random.choice(len(filtered_repulsion), 100, replace=False)
                repulsion_points = [filtered_repulsion[i] for i in indices]
            else:
                repulsion_points = filtered_repulsion
        else:
            repulsion_points = []

    nodes: list[TreeNode] = []

    if existing_nodes:
        nodes = [TreeNode(**n.model_dump()) for n in existing_nodes]
    else:
        root_positions = []
        if tree_count == 1:
            root_positions = [(0.0, 0.0)]
        else:
            golden_angle = 2.399963229728653
            root_spread = 3.0
            for i in range(1, tree_count + 1):
                angle = i * golden_angle
                radius = math.sqrt(i) * (root_spread / math.sqrt(tree_count))
                x = math.cos(angle) * radius
                z = math.sin(angle) * radius
                root_positions.append((x, z))

        for x, z in root_positions:
            nodes.append(
                TreeNode(
                    id=_generate_uuid(),
                    x=x,
                    y=0.0,
                    z=z,
                    radius=0.1,
                    parentId=None,
                )
            )

    attractor_positions = (
        np.array([[a.x, a.y, a.z] for a in attractors])
        if attractors
        else np.array([]).reshape(0, 3)
    )

    repulsion_positions = (
        np.array([[r.x, r.y, r.z] for r in repulsion_points])
        if repulsion_points
        else np.array([]).reshape(0, 3)
    )

    active_attractors = np.ones(len(attractor_positions), dtype=bool)

    new_nodes_added = 0
    growth_stopped_reason = "max_nodes"
    initial_node_count = len(nodes)

    while new_nodes_added < max_new_nodes:
        if not active_attractors.any():
            growth_stopped_reason = "attractors_exhausted"
            break

        active_positions = attractor_positions[active_attractors]
        node_positions = np.array([[n.x, n.y, n.z] for n in nodes])

        all_distances = np.linalg.norm(
            active_positions[:, np.newaxis, :] - node_positions[np.newaxis, :, :],
            axis=2,
        )

        nearest_node = np.argmin(all_distances, axis=1)
        nearest_dist = np.min(all_distances, axis=1)

        influenced_mask = nearest_dist <= genome.influence_radius

        if not influenced_mask.any():
            growth_stopped_reason = "influence_radius"
            break

        growth_directions: dict[int, list[np.ndarray]] = {}
        children_added: dict[int, int] = {}

        for local_idx in np.where(influenced_mask)[0]:
            node_idx = nearest_node[local_idx]
            if node_idx not in growth_directions:
                growth_directions[node_idx] = []
                children_added[node_idx] = 0
            growth_directions[node_idx].append(active_positions[local_idx])

        nodes_added_this_iter = 0

        for node_idx, attracted_positions in growth_directions.items():
            if children_added[node_idx] >= genome.max_children_per_node:
                continue

            if new_nodes_added + nodes_added_this_iter >= max_new_nodes:
                break

            node_pos = node_positions[node_idx]

            attraction_vector = np.zeros(3)
            if len(attracted_positions) > 0:
                vectors = attracted_positions - node_pos
                attraction_vector = np.mean(vectors, axis=0)

            repulsion_vector = np.zeros(3)
            if len(repulsion_positions) > 0:
                rep_dists = np.linalg.norm(repulsion_positions - node_pos, axis=1)
                nearby_mask = rep_dists < genome.repulsion_radius
                nearby_repulsors = repulsion_positions[nearby_mask]

                if len(nearby_repulsors) > 0:
                    for rep_pos in nearby_repulsors:
                        diff = rep_pos - node_pos
                        dist = np.linalg.norm(diff)
                        if dist > 0.1:
                            repulsion_vector += diff / (dist * dist)

            final_vector = (attraction_vector * genome.attraction_strength) + (
                repulsion_vector * genome.repulsion_strength
            )

            norm = np.linalg.norm(final_vector)
            if norm > 1e-8:
                final_vector = final_vector / norm

            if genome.wiggle_factor > 0:
                wiggle = np.random.randn(3) * genome.wiggle_factor
                final_vector = final_vector + wiggle
                final_vector = final_vector / np.linalg.norm(final_vector)

            new_pos = node_pos + final_vector * genome.growth_step

            new_node = TreeNode(
                id=_generate_uuid(),
                x=float(new_pos[0]),
                y=float(new_pos[1]),
                z=float(new_pos[2]),
                radius=0.1,
                parentId=nodes[node_idx].id,
            )
            nodes.append(new_node)
            children_added[node_idx] += 1
            nodes_added_this_iter += 1
            new_nodes_added += 1

        if nodes_added_this_iter == 0:
            growth_stopped_reason = "no_valid_growth"
            break

        node_positions = np.array([[n.x, n.y, n.z] for n in nodes])
        distances = np.linalg.norm(
            attractor_positions[:, np.newaxis] - node_positions[np.newaxis, :, :],
            axis=2,
        )
        min_dist_to_nodes = np.min(distances, axis=1)
        active_attractors = min_dist_to_nodes >= genome.kill_distance

    node_map: dict[str, TreeNode] = {n.id: n for n in nodes}
    children_map: dict[str, list[TreeNode]] = {}
    for node in nodes:
        if node.parentId:
            if node.parentId not in children_map:
                children_map[node.parentId] = []
            children_map[node.parentId].append(node)

    leaves = [n for n in nodes if n.id not in children_map]
    for leaf in leaves:
        leaf.radius = 0.1

    MAX_RADIUS = 0.3

    parent_ids_with_children = set(children_map.keys())

    leaves = [n for n in nodes if n.id not in children_map]
    for leaf in leaves:
        leaf.radius = 0.05

    for _ in range(100):
        updated = False
        for node_id in parent_ids_with_children:
            node = node_map.get(node_id)
            if not node:
                continue
            children = children_map.get(node_id, [])
            if children:
                max_child_radius = max(c.radius for c in children)
                parent_radius = min(MAX_RADIUS, max_child_radius + 0.005)
                if abs(node.radius - parent_radius) > 0.001:
                    node.radius = parent_radius
                    updated = True
        if not updated:
            break

    remaining_indices = np.where(active_attractors)[0]
    remaining_attractor_points = [
        AttractorPoint(
            x=float(attractor_positions[i, 0]),
            y=float(attractor_positions[i, 1]),
            z=float(attractor_positions[i, 2]),
        )
        for i in remaining_indices
    ]

    remaining_attractors = len(remaining_attractor_points)
    attractors_exhausted = remaining_attractors == 0

    stats = GenerationStats(
        attractors_exhausted=attractors_exhausted,
        remaining_attractors=remaining_attractors,
        total_attractors=total_attractors,
        nodes_grown=new_nodes_added,
        growth_stopped_reason=growth_stopped_reason,
    )

    return nodes, stats, remaining_attractor_points
