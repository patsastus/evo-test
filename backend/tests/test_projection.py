from config import CANVAS_WIDTH
from projection import calculate_wall_height, to_x_wall_uv, to_z_wall_uv, uv_to_pixel


def test_wall_height_uses_half_width_aspect():
    # 100 wide -> 50 per half; 25 tall -> aspect 0.5
    assert calculate_wall_height(25, 100) == CANVAS_WIDTH * 0.5


def test_wall_height_tiny_width_does_not_divide_by_zero():
    assert calculate_wall_height(10, 1) == CANVAS_WIDTH * 10


def test_uv_mapping_axes():
    # Z wall's u follows z, X wall's u follows x
    assert to_z_wall_uv(99, 0.5, -5, 10)[0] == 0.0
    assert to_x_wall_uv(5, 0.5, 99, 10)[0] == 1.0


def test_uv_to_pixel_clamps_to_bounds():
    assert uv_to_pixel(-1, 2, 40, 20) == (0, 0)
    assert uv_to_pixel(5, -3, 40, 20) == (19, 39)
    assert uv_to_pixel(0.5, 0.5, 40, 20) == (10, 20)
