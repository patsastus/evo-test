import json

import pytest
import trimesh
from PIL import Image, ImageDraw

import cli


@pytest.fixture
def shapes_png(tmp_path):
    """Small two-shadow target: a disc on the left, a diamond on the right."""
    img = Image.new("L", (160, 80), 255)
    d = ImageDraw.Draw(img)
    d.ellipse((12, 10, 68, 66), fill=0)
    d.polygon([(120, 8), (150, 40), (120, 72), (90, 40)], fill=0)
    path = tmp_path / "shapes.png"
    img.save(path)
    return path


def run_cli(image, out, *extra):
    return cli.main([str(image), "--out", str(out), "--candidates", "2",
                     "--max-total-nodes", "300", "--seed", "1", *extra])


def test_cli_writes_all_outputs_and_a_watertight_stl(shapes_png, tmp_path):
    out = tmp_path / "out"
    assert run_cli(shapes_png, out) == 0
    for name in ("scene.stl", "shadows.png", "comparison.png", "report.json"):
        assert (out / name).is_file()

    mesh = trimesh.load(out / "scene.stl")
    assert mesh.is_watertight and mesh.volume > 0

    report = json.loads((out / "report.json").read_text())
    assert report["seed"] == 1 and report["nozzle"] == "0.4"
    assert report["mesh"]["watertight"] is True
    assert report["best"]["nodes"] <= 300
    assert len(report["best"]["shadow_match_per_light"]) == 2
    assert len(report["all_candidates"]) == 2
    scores = [c["score"] for c in report["all_candidates"]]
    assert scores == sorted(scores, reverse=True)  # best first
    assert "remaining_attractors_points" not in report["stats"]


def test_cli_comparison_image_stacks_target_over_render(shapes_png, tmp_path):
    out = tmp_path / "out"
    run_cli(shapes_png, out)
    target = Image.open(shapes_png)
    comp = Image.open(out / "comparison.png")
    assert comp.width == target.width and comp.height > 2 * target.height


def test_cli_same_seed_gives_the_same_report(shapes_png, tmp_path):
    run_cli(shapes_png, tmp_path / "a")
    run_cli(shapes_png, tmp_path / "b")
    a = json.loads((tmp_path / "a" / "report.json").read_text())
    b = json.loads((tmp_path / "b" / "report.json").read_text())
    for r in (a, b):
        r.pop("seconds")
    assert a == b


def test_cli_nozzle_option_is_recorded(shapes_png, tmp_path):
    assert run_cli(shapes_png, tmp_path / "o", "--nozzle", "0.2") == 0
    report = json.loads((tmp_path / "o" / "report.json").read_text())
    assert report["nozzle"] == "0.2" and report["printability_report"]["nozzle"] == "0.2"


def test_cli_missing_image_fails_cleanly(tmp_path, capsys):
    assert run_cli(tmp_path / "nope.png", tmp_path / "o") == 2
    assert "no such image" in capsys.readouterr().err


def test_cli_rejects_non_image(tmp_path, capsys):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    assert run_cli(bad, tmp_path / "o") == 2
    assert "not a valid image" in capsys.readouterr().err
