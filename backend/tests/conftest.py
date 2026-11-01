import base64
import io
from pathlib import Path

import pytest
from PIL import Image

from models import TargetShadow, Vec3

IMAGES_DIR = Path(__file__).resolve().parents[2] / "tests" / "images"


def to_data_url(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def solid_image(width: int, height: int, value: int) -> Image.Image:
    return Image.new("L", (width, height), value)


def make_targets(data_url: str) -> list[TargetShadow]:
    return [
        TargetShadow(imageData=data_url, lightVector=Vec3(x=0, y=0, z=-1)),
        TargetShadow(imageData=data_url, lightVector=Vec3(x=-1, y=0, z=0)),
    ]


@pytest.fixture(scope="session")
def ct_image() -> Image.Image:
    return Image.open(IMAGES_DIR / "ct.png")


@pytest.fixture(scope="session")
def ct_targets(ct_image):
    return make_targets(to_data_url(ct_image))


@pytest.fixture(scope="session")
def ct_volume(ct_targets):
    from voxel import _calculate_intersection_volume

    return _calculate_intersection_volume(ct_targets)
