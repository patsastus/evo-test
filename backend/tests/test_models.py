import random

from models import TreeGenome


def test_mutate_is_deterministic_per_seed():
    g = TreeGenome(random_seed=1)
    assert g.mutate() == g.mutate()


def test_mutate_differs_across_seeds():
    assert TreeGenome(random_seed=1).mutate() != TreeGenome(random_seed=2).mutate()


def test_mutate_does_not_touch_global_random_state():
    random.seed(123)
    expected = random.random()
    random.seed(123)
    TreeGenome(random_seed=7).mutate()
    assert random.random() == expected


def test_mutate_stays_within_half_to_one_and_a_half():
    base = TreeGenome()
    for seed in range(50):
        m = TreeGenome(random_seed=seed).mutate()
        for field in ("growth_step", "kill_distance", "influence_radius", "wiggle_factor"):
            assert 0.5 * getattr(base, field) <= getattr(m, field) <= 1.5 * getattr(base, field)
        assert m.max_children_per_node >= 1
