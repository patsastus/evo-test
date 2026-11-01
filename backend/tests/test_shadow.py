import base64
import io

from PIL import Image

from models import TreeNode
from shadow import _generate_shadow_image, calculate_fitness

from conftest import make_targets, solid_image, to_data_url


def trunk(height=8.0, steps=40, radius=0.3):
    nodes = [TreeNode(id="n0", x=0, y=0.5, z=0, radius=radius, parentId=None)]
    for i in range(1, steps + 1):
        nodes.append(
            TreeNode(
                id=f"n{i}",
                x=0,
                y=0.5 + height * i / steps,
                z=0,
                radius=radius,
                parentId=f"n{i-1}",
            )
        )
    return nodes


def decode(url: str) -> Image.Image:
    assert url.startswith("data:image/png;base64,")
    return Image.open(io.BytesIO(base64.b64decode(url.split(",")[1])))


def test_shadow_image_has_requested_size():
    assert decode(_generate_shadow_image(trunk(), 200, 60)).size == (200, 60)


def test_shadow_image_odd_width_keeps_size():
    assert decode(_generate_shadow_image(trunk(), 347, 153)).size == (347, 153)


def test_shadow_image_draws_dark_pixels_for_tree_and_none_for_empty():
    empty = decode(_generate_shadow_image([], 200, 60)).convert("L")
    drawn = decode(_generate_shadow_image(trunk(), 200, 60)).convert("L")
    interior = lambda im: im.crop((10, 10, 190, 50))
    assert interior(empty).getextrema()[0] == 255
    assert interior(drawn).getextrema()[0] < 255


def test_fitness_empty_inputs_are_zero():
    targets = make_targets(to_data_url(solid_image(100, 30, 0)))
    assert calculate_fitness([], targets) == (0.0, 0.0)
    assert calculate_fitness(trunk(), []) == (0.0, 0.0)


def test_fitness_scores_are_in_unit_range_on_black_target():
    targets = make_targets(to_data_url(solid_image(200, 60, 0)))
    match, printability = calculate_fitness(trunk(), targets, 200, 60)
    assert 0.0 < match <= 1.0
    assert 0.0 <= printability <= 1.0


def test_fitness_white_target_scores_zero_match():
    targets = make_targets(to_data_url(solid_image(200, 60, 255)))
    match, _ = calculate_fitness(trunk(), targets, 200, 60)
    assert match == 0.0


# ---- perceived-shadow IoU metric -------------------------------------------

import numpy as np
import pytest

from models import AttractorPoint, TreeGenome
from sca import grow_tree
from shadow import (
    _get_shadow_arrays,
    _target_perceived_masks,
    combine_lights,
    shadow_match_per_light,
)
from voxel import _calculate_intersection_volume


def target_from_arrays(gz, gx, shift=0):
    """A target image whose left/right halves are exactly the given shadows."""
    half = gz.shape[1]
    arr = np.full((gz.shape[0], half * 2), 255, dtype=np.uint8)
    arr[:, :half][np.roll(gz, shift, axis=1)] = 0
    arr[:, half:][np.roll(gx, shift, axis=1)] = 0
    return make_targets(to_data_url(Image.fromarray(arr, "L")))


def test_exact_copy_of_the_shadow_scores_one():
    tree = trunk()
    gz, gx = _get_shadow_arrays(tree, 200, 60)
    targets = target_from_arrays(gz, gx)
    assert shadow_match_per_light(tree, targets) == [1.0, 1.0]
    assert calculate_fitness(tree, targets)[0] == 1.0


def test_score_falls_smoothly_with_misalignment():
    tree = trunk(radius=0.3)
    gz, gx = _get_shadow_arrays(tree, 200, 60)
    scores = [calculate_fitness(tree, target_from_arrays(gz, gx, shift=k))[0] for k in (0, 1, 3, 8)]
    assert scores[0] == 1.0
    assert all(a > b for a, b in zip(scores, scores[1:]))
    assert scores[1] > 0.7  # one pixel off still reads as the same shape
    assert scores[3] < 0.2


def test_shadow_far_from_the_target_scores_zero():
    tree = trunk()
    gz, gx = _get_shadow_arrays(tree, 200, 60)
    far = np.zeros_like(gz)
    far[:, :10] = True  # target dark only at the far left edge, trunk is mid-image
    assert shadow_match_per_light(tree, target_from_arrays(far, far)) == [0.0, 0.0]


def test_combine_lights_is_harmonic_so_the_weak_light_dominates():
    assert combine_lights([0.5, 0.5]) == pytest.approx(0.5)
    assert combine_lights([1.0, 0.0]) == 0.0
    assert combine_lights([0.9, 0.1]) < 0.2  # arithmetic mean would be 0.5
    assert combine_lights([]) == 0.0


def test_target_masks_are_cached_across_candidates():
    url = to_data_url(solid_image(100, 30, 0))
    _target_perceived_masks.cache_clear()
    _target_perceived_masks(url)
    _target_perceived_masks(url)
    assert _target_perceived_masks.cache_info().hits == 1


def blob_tree():
    nodes = [TreeNode(id="r", x=0, y=0, z=0, radius=0.1, parentId=None)]
    k = 0
    for x in np.linspace(-5, 5, 11):
        for y in np.linspace(0.5, 9.5, 10):
            k += 1
            nodes.append(
                TreeNode(id=f"a{k}", x=float(x), y=float(y), z=float(x), radius=0.8, parentId="r")
            )
    return nodes


def test_ct_more_growth_scores_higher_and_a_blob_scores_below_a_real_tree(ct_image, ct_targets, ct_volume):
    att, rep = ct_volume
    w, h = ct_image.size
    score = lambda nodes: calculate_fitness(nodes, ct_targets, w, h)[0]
    small = grow_tree(att, 1, rep, genome=TreeGenome(), max_new_nodes=300)[0]
    big = grow_tree(att, 1, rep, genome=TreeGenome(), max_new_nodes=800)[0]
    # regression: the old coverage-minus-penalty metric gave the blob 0.785 vs ~0.4
    assert score(small) < score(big)
    assert score(blob_tree()) < score(big)
    assert 0.0 <= score(big) <= 1.0
