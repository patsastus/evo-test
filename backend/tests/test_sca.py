import numpy as np

from models import AttractorPoint, TreeGenome
from sca import MAX_WORKING_ATTRACTORS, grow_tree


def line_of_attractors(n=20, x=0.0, z=0.0, y0=1.0, dy=0.25):
    return [AttractorPoint(x=x, y=y0 + i * dy, z=z) for i in range(n)]


def key(p):
    return (p.x, p.y, p.z)


def test_single_root_at_origin_and_valid_parent_links():
    nodes, _, _ = grow_tree(line_of_attractors(), max_new_nodes=50)
    root = nodes[0]
    assert (root.x, root.y, root.z, root.parentId) == (0.0, 0.0, 0.0, None)
    ids = {n.id for n in nodes}
    assert all(n.parentId in ids for n in nodes if n.parentId)
    assert len(ids) == len(nodes)


def test_tree_reaches_and_exhausts_straight_line_of_attractors():
    genome = TreeGenome(wiggle_factor=0.0)
    nodes, stats, remaining = grow_tree(
        line_of_attractors(), genome=genome, max_new_nodes=500
    )
    assert stats.attractors_exhausted
    assert stats.growth_stopped_reason == "attractors_exhausted"
    assert remaining == []
    assert max(n.y for n in nodes) >= 4.5


def test_max_new_nodes_is_respected():
    nodes, stats, _ = grow_tree(line_of_attractors(), max_new_nodes=5)
    assert stats.nodes_grown <= 5
    assert len(nodes) == 1 + stats.nodes_grown
    assert stats.growth_stopped_reason == "max_nodes"


def test_no_attractors_stops_immediately():
    nodes, stats, remaining = grow_tree([], max_new_nodes=10)
    assert len(nodes) == 1
    assert stats.growth_stopped_reason == "attractors_exhausted"
    assert remaining == []


def test_attractor_cap_does_not_discard_points():
    # More attractors than the working-set cap, far above the origin and out of reach.
    n = MAX_WORKING_ATTRACTORS * 2 + 7
    rng = np.random.default_rng(0)
    pts = [
        AttractorPoint(x=float(x), y=float(y), z=float(z))
        for x, y, z in rng.uniform([-1, 8, -1], [1, 9, 1], size=(n, 3))
    ]
    genome = TreeGenome(influence_radius=1.0)
    _, stats, remaining = grow_tree(pts, genome=genome, max_new_nodes=10)
    assert stats.total_attractors == n
    assert stats.remaining_attractors == n == len(remaining)
    assert {key(p) for p in remaining} == {key(p) for p in pts}


def test_remaining_is_subset_of_input_and_shrinks_across_continues():
    pts = line_of_attractors(n=40, dy=0.25)
    genome = TreeGenome(wiggle_factor=0.0)
    nodes, stats1, rem1 = grow_tree(pts, genome=genome, max_new_nodes=5)
    nodes, stats2, rem2 = grow_tree(
        rem1, genome=genome, existing_nodes=nodes, max_new_nodes=5
    )
    assert {key(p) for p in rem2} <= {key(p) for p in rem1} <= {key(p) for p in pts}
    assert len(rem2) < len(rem1) < len(pts)
    assert stats1.total_attractors == len(pts)


def test_same_seed_is_deterministic():
    pts = line_of_attractors()
    g = TreeGenome(random_seed=5)
    a, _, _ = grow_tree(pts, genome=g, max_new_nodes=30)
    b, _, _ = grow_tree(pts, genome=g, max_new_nodes=30)
    assert [(n.x, n.y, n.z) for n in a] == [(n.x, n.y, n.z) for n in b]


def test_existing_nodes_are_preserved_and_not_mutated_in_place():
    first, _, rem = grow_tree(line_of_attractors(), max_new_nodes=5)
    snapshot = [(n.id, n.x, n.y, n.z) for n in first]
    grown, _, _ = grow_tree(rem, existing_nodes=first, max_new_nodes=5)
    assert [(n.id, n.x, n.y, n.z) for n in grown[: len(first)]] == snapshot
    assert [(n.id, n.x, n.y, n.z) for n in first] == snapshot


def test_repulsor_pushes_growth_away():
    # Attractor straight above; repulsor just to the +x side of the first step.
    pts = [AttractorPoint(x=0, y=5, z=0)]
    repulsor = [AttractorPoint(x=0.5, y=0.3, z=0)]
    genome = TreeGenome(wiggle_factor=0.0, repulsion_radius=2.0)
    without, _, _ = grow_tree(pts, genome=genome, max_new_nodes=1)
    with_rep, _, _ = grow_tree(
        pts, repulsion_points=repulsor, genome=genome, max_new_nodes=1
    )
    assert with_rep[1].x < without[1].x  # moved to -x, away from repulsor


def test_multiple_trees_get_distinct_roots():
    nodes, _, _ = grow_tree(line_of_attractors(), tree_count=3, max_new_nodes=0)
    roots = [n for n in nodes if n.parentId is None]
    assert len(roots) == 3
    assert len({(r.x, r.z) for r in roots}) == 3


def test_ct_growth_reaches_top_of_volume(ct_volume):
    att, rep = ct_volume
    nodes, stats, _ = grow_tree(att, 1, rep, genome=TreeGenome(), max_new_nodes=300)
    assert stats.total_attractors == len(att)
    assert max(n.y for n in nodes) > 5.5  # regression: used to stall near y=3.2


def positions(nodes):
    return [(n.x, n.y, n.z) for n in nodes]


def test_direction_filter_none_and_identity_are_equivalent():
    pts = line_of_attractors()
    g = TreeGenome(random_seed=3)
    base, _, _ = grow_tree(pts, genome=g, max_new_nodes=20)
    ident, _, _ = grow_tree(pts, genome=g, max_new_nodes=20, direction_filter=lambda pos, d: d)
    # identity re-normalises an already-unit vector, so allow last-digit float noise
    assert len(base) == len(ident)
    assert np.allclose(positions(base), positions(ident), atol=1e-12)


def test_direction_filter_is_called_per_segment_and_controls_growth():
    calls = []

    def straight_up(pos, d):
        calls.append((pos.copy(), d.copy()))
        return np.array([0.0, 1.0, 0.0])

    pts = [AttractorPoint(x=3, y=3, z=3)]  # pulls sideways; filter overrides
    nodes, stats, _ = grow_tree(
        pts, genome=TreeGenome(wiggle_factor=0.0), max_new_nodes=5, direction_filter=straight_up
    )
    assert len(calls) == stats.nodes_grown == 5
    assert all(np.isclose(np.linalg.norm(d), 1.0) for _, d in calls)
    assert all(n.x == 0.0 and n.z == 0.0 for n in nodes)  # only grew upward


def test_direction_filter_returning_zero_vector_is_ignored():
    pts = line_of_attractors()
    g = TreeGenome(random_seed=4)
    base, _, _ = grow_tree(pts, genome=g, max_new_nodes=10)
    zero, _, _ = grow_tree(pts, genome=g, max_new_nodes=10, direction_filter=lambda p, d: np.zeros(3))
    assert positions(base) == positions(zero)
