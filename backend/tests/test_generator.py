import random

import pytest

from generator import ImageError, candidate_deadline, generate, rank, validated_image_size
from models import GenerateScenesRequest, GenerationParams, TargetShadow, Vec3

from conftest import make_targets, solid_image, to_data_url


@pytest.fixture(scope="module")
def black_url():
    return to_data_url(solid_image(100, 30, 0))


def request(url, **overrides):
    base = dict(
        count=2,
        params=GenerationParams(treeCount=1, maxThickness=0.5, branchingProb=0.5, maxAngle=0.5),
        targetShadows=make_targets(url),
        max_new_nodes=100,
    )
    base.update(overrides)
    return GenerateScenesRequest(**base)


def coords(scene):
    return [(round(n.x, 9), round(n.y, 9), round(n.z, 9)) for n in scene.trees]


def test_candidate_deadline_splits_remaining_time_fairly():
    assert candidate_deadline(0.0, 60.0, 4) == 15.0
    assert candidate_deadline(10.0, 60.0, 1) == 60.0  # last candidate gets the rest
    assert candidate_deadline(10.0, 10.0, 3) == 10.0  # nothing left -> immediate
    assert candidate_deadline(70.0, 60.0, 2) == 70.0  # already past the deadline


def test_seeded_runs_are_reproducible_and_seeds_differ(black_url):
    a = generate(request(black_url), rng=random.Random(5))
    b = generate(request(black_url), rng=random.Random(5))
    c = generate(request(black_url), rng=random.Random(6))
    assert [coords(s) for s in a.scenes] == [coords(s) for s in b.scenes]
    assert [s.fitness for s in a.scenes] == [s.fitness for s in b.scenes]
    assert [coords(s) for s in a.scenes] != [coords(s) for s in c.scenes]


def test_max_total_nodes_caps_growth_and_is_reported(black_url):
    stats = []
    resp = generate(
        request(black_url, run_until_complete=True, count=2),
        rng=random.Random(1),
        max_total_nodes=150,
        candidate_stats=stats,
    )
    assert all(len(s.trees) <= 150 for s in resp.scenes)
    assert all(st.growth_stopped_reason == "node_limit" for st in stats)


def test_candidate_stats_has_one_entry_per_candidate(black_url):
    stats = []
    resp = generate(request(black_url, count=3), rng=random.Random(1), candidate_stats=stats)
    assert len(resp.scenes) == len(stats) == 3
    assert resp.stats == stats[-1]  # response still carries the last one


def test_every_candidate_gets_nodes_when_time_is_shared(black_url):
    # Regression: one request-wide deadline let the first candidates starve the rest.
    resp = generate(
        request(black_url, run_until_complete=True, count=3, max_new_nodes=50),
        rng=random.Random(2),
        max_seconds=3.0,
        max_total_nodes=400,
    )
    assert all(len(s.trees) > 1 for s in resp.scenes)


def test_rank_requires_both_shadow_match_and_printability(black_url):
    resp = generate(request(black_url, count=1), rng=random.Random(1))
    scene = resp.scenes[0]
    assert rank(scene) == pytest.approx(scene.fitness.shadowMatch * scene.fitness.printability)
    zero = scene.model_copy(update={"fitness": scene.fitness.model_copy(update={"printability": 0.0})})
    assert rank(zero) == 0.0


@pytest.mark.parametrize(
    "image_data, status",
    [
        ("data:image/png;base64", 422),
        ("data:image/png;base64,!!!", 422),
        ("data:image/png;base64,aGVsbG8=", 422),
        ("data:image/png;base64," + "A" * 12_000_000, 413),
    ],
)
def test_image_errors_carry_the_http_status(image_data, status):
    target = TargetShadow(imageData=image_data, lightVector=Vec3(x=0, y=0, z=1))
    with pytest.raises(ImageError) as exc:
        validated_image_size(target, 0)
    assert exc.value.status == status
