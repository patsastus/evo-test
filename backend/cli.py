"""Command-line prototype: target image -> printable scene STL + shadow previews.

    uv run python cli.py ../tests/images/solids.png --out out/solids

Grows several candidate trees to completion, keeps the best one (shadow match x
printability), and writes scene.stl, shadows.png, comparison.png and report.json.
"""

import argparse
import base64
import io
import json
import logging
import random
import sys
import threading
import time
from pathlib import Path

from PIL import Image

from config import MAX_RUN_SECONDS
from generator import ImageError, generate, rank
from mesh import build_scene_mesh, mesh_report
from models import (
    GenerateScenesRequest,
    GenerationParams,
    SceneData,
    TargetShadow,
    Vec3,
)
from printability import analyze as analyze_printability
from shadow import shadow_match_per_light


def image_to_data_url(path: Path) -> str:
    return "data:;base64," + base64.b64encode(path.read_bytes()).decode()


def decode_data_url(url: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))


def build_request(image_path: Path, args: argparse.Namespace) -> GenerateScenesRequest:
    url = image_to_data_url(image_path)
    # One image holds both shadows side by side (left half = light 0, right = light 1).
    targets = [
        TargetShadow(imageData=url, lightVector=Vec3(x=0, y=0, z=1)),
        TargetShadow(imageData=url, lightVector=Vec3(x=1, y=0, z=0)),
    ]
    return GenerateScenesRequest(
        count=args.candidates,
        params=GenerationParams(
            treeCount=args.tree_count, maxThickness=0.5, branchingProb=0.5, maxAngle=0.5
        ),
        targetShadows=targets,
        max_new_nodes=args.max_nodes,
        run_until_complete=True,
        nozzle=args.nozzle,
    )


def comparison_image(target: Image.Image, rendered: Image.Image) -> Image.Image:
    """Target on top, our rendered shadows below, same width."""
    target = target.convert("RGB")
    rendered = rendered.convert("RGB").resize(target.size)
    out = Image.new("RGB", (target.width, target.height * 2 + 6), (200, 200, 200))
    out.paste(target, (0, 0))
    out.paste(rendered, (0, target.height + 6))
    return out


def run(args: argparse.Namespace) -> int:
    image_path = Path(args.image)
    if not image_path.is_file():
        print(f"error: no such image: {image_path}", file=sys.stderr)
        return 2

    seed = args.seed if args.seed is not None else random.randrange(1_000_000)
    request = build_request(image_path, args)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"image: {image_path}  nozzle: {args.nozzle}  candidates: {args.candidates}  seed: {seed}")
    started = time.monotonic()
    per_candidate_stats: list = []
    try:
        response = generate(
            request,
            threading.Event(),
            max_seconds=args.time_limit,
            rng=random.Random(seed),
            max_total_nodes=args.max_total_nodes,
            candidate_stats=per_candidate_stats,
        )
    except ImageError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    elapsed = time.monotonic() - started

    if not response.scenes:
        print("error: no scenes were generated", file=sys.stderr)
        return 1

    pairs = sorted(zip(response.scenes, per_candidate_stats), key=lambda p: rank(p[0]), reverse=True)
    ranked = [sc for sc, _ in pairs]
    best: SceneData = ranked[0]
    stats = pairs[0][1]  # stats of the best candidate (not just the last one grown)

    print(f"\ngenerated {len(response.scenes)} candidates in {elapsed:.1f}s "
          f"(attractors {stats.total_attractors}; best candidate stopped: {stats.growth_stopped_reason}, "
          f"{stats.remaining_attractors} attractors left)")
    print(f"{'rank':>4} {'nodes':>6} {'shadow':>7} {'print':>7} {'score':>7}")
    for i, sc in enumerate(ranked, 1):
        print(f"{i:>4} {len(sc.trees):>6} {sc.fitness.shadowMatch:>7.3f} "
              f"{sc.fitness.printability:>7.3f} {rank(sc):>7.3f}{'  <- best' if sc is best else ''}")

    # --- outputs for the best candidate ---------------------------------------
    printability = analyze_printability(best.trees, args.nozzle)
    per_light = shadow_match_per_light(best.trees, request.targetShadows)
    mesh_info, stl_path, mesh_error = None, None, None
    try:
        mesh = build_scene_mesh(best.trees)
        stl_path = out_dir / "scene.stl"
        mesh.export(stl_path)
        mesh_info = mesh_report(mesh)
    except ValueError as e:
        mesh_error = str(e)

    rendered = decode_data_url(best.shadowImageUrl)
    rendered.save(out_dir / "shadows.png")
    comparison_image(Image.open(image_path), rendered).save(out_dir / "comparison.png")

    report = {
        "image": str(image_path),
        "nozzle": args.nozzle,
        "seed": seed,
        "candidates": args.candidates,
        "seconds": round(elapsed, 2),
        "stats": stats.model_dump(exclude={"remaining_attractors_points"}),
        "best": {
            "nodes": len(best.trees),
            "shadow_match": best.fitness.shadowMatch,
            "shadow_match_per_light": per_light,
            "printability": best.fitness.printability,
            "score": rank(best),
        },
        "printability_report": printability.to_dict(),
        "mesh": mesh_info,
        "mesh_error": mesh_error,
        "all_candidates": [
            {
                "nodes": len(sc.trees),
                "shadow_match": sc.fitness.shadowMatch,
                "printability": sc.fitness.printability,
                "score": rank(sc),
            }
            for sc in ranked
        ],
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2))

    print(f"\nbest: shadow match {best.fitness.shadowMatch:.3f} "
          f"(per light {', '.join(f'{s:.3f}' for s in per_light)}), "
          f"printability {best.fitness.printability:.3f}")
    print(f"  thinnest branch {printability.min_diameter_mm:.2f} mm, "
          f"{printability.overhang_length_fraction * 100:.0f}% of branch length needs support")
    if mesh_info:
        print(f"  mesh: watertight={mesh_info['watertight']}, "
              f"{mesh_info['size_mm'][0]:.0f} x {mesh_info['size_mm'][1]:.0f} x {mesh_info['size_mm'][2]:.0f} mm")
    if mesh_error:
        print(f"  mesh: NOT written ({mesh_error})")
    print(f"wrote {out_dir}/" + ("scene.stl, " if stl_path else "") + "shadows.png, comparison.png, report.json")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image", help="target image: left half = light 0 shadow, right half = light 1")
    parser.add_argument("--out", default="out", help="output directory (default: out)")
    parser.add_argument("--nozzle", choices=["0.4", "0.2"], default="0.4")
    parser.add_argument("--candidates", type=int, default=4, help="candidate trees to grow (1-16)")
    parser.add_argument("--max-nodes", type=int, default=500, help="nodes per growth pass (1-5000)")
    parser.add_argument("--tree-count", type=int, default=1, help="separate trees on the foot (1-10)")
    parser.add_argument("--max-total-nodes", type=int, default=4000,
                        help="stop growing a candidate at this many nodes (default 4000; fewer nodes = "
                             "simpler, faster-to-print tree, lower shadow match)")
    parser.add_argument("--seed", type=int, default=None, help="make a run reproducible")
    parser.add_argument("--time-limit", type=float, default=MAX_RUN_SECONDS,
                        help=f"wall-clock budget in seconds (default {MAX_RUN_SECONDS})")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
