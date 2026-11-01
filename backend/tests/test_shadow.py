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
