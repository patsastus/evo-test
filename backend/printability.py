"""Printability of a tree for FDM printing (target: Bambu A1, 0.4 / 0.2 mm nozzles).

Scored analytically from the branch graph (exact for tube geometry, microseconds
per candidate) so it can run for every candidate. The watertight/solid checks live
in mesh.py and are used by the report at export time.

Score = thickness_score * overhang_score, or 0 if the gate fails (a root outside
the standard foot, or nothing to print). Bed contact and tipping are NOT scored:
the standard foot provides the bed contact, and display stability is the base
plate's job. COM offset is reported for information only.

All thresholds are rules of thumb and should be checked against test prints.
"""

from dataclasses import dataclass, asdict
from typing import Literal

import numpy as np

from config import MM_PER_UNIT
from connector import DEFAULT_CONNECTOR, ConnectorSpec
from models import TreeNode

Nozzle = Literal["0.4", "0.2"]


@dataclass(frozen=True)
class NozzleProfile:
    # Branch diameters (mm): >= warn is fully fine, <= fail is unprintable,
    # linear penalty in between.
    warn_diameter: float
    fail_diameter: float


NOZZLE_PROFILES: dict[str, NozzleProfile] = {
    "0.4": NozzleProfile(warn_diameter=0.8, fail_diameter=0.5),
    "0.2": NozzleProfile(warn_diameter=0.5, fail_diameter=0.3),
}

# Surfaces tilted less than this from horizontal need support. Penalty ramps from
# 0 at the limit to 1 for a horizontal branch.
OVERHANG_LIMIT_DEG = 45.0


@dataclass
class PrintabilityReport:
    score: float
    thickness_score: float
    overhang_score: float
    gate_ok: bool
    gate_reason: str | None
    nozzle: str
    min_diameter_mm: float
    thin_length_fraction: float  # branch length below the nozzle's warn diameter
    unprintable_length_fraction: float  # branch length at/below the fail diameter
    overhang_length_fraction: float  # branch length needing support (< 45 deg)
    total_branch_length_mm: float
    com_offset_mm: float  # horizontal offset of tree centre of mass from foot centre
    com_height_mm: float

    def to_dict(self) -> dict:
        return asdict(self)


def _segments(trees: list[TreeNode], scale: float):
    """Return (p_parent, p_child, r_parent, r_child) arrays in print space (mm)."""
    by_id = {n.id: n for n in trees}
    pa, pb, ra, rb = [], [], [], []
    for n in trees:
        parent = by_id.get(n.parentId) if n.parentId else None
        if parent is None:
            continue
        # (x, y-up, z) -> (x, -z, y), same mapping as mesh.to_print_space
        pa.append((parent.x * scale, -parent.z * scale, parent.y * scale))
        pb.append((n.x * scale, -n.z * scale, n.y * scale))
        ra.append(parent.radius * scale)
        rb.append(n.radius * scale)
    return (np.array(pa), np.array(pb), np.array(ra), np.array(rb))


def _empty_report(nozzle: str, reason: str) -> PrintabilityReport:
    return PrintabilityReport(
        score=0.0,
        thickness_score=0.0,
        overhang_score=0.0,
        gate_ok=False,
        gate_reason=reason,
        nozzle=nozzle,
        min_diameter_mm=0.0,
        thin_length_fraction=0.0,
        unprintable_length_fraction=0.0,
        overhang_length_fraction=0.0,
        total_branch_length_mm=0.0,
        com_offset_mm=0.0,
        com_height_mm=0.0,
    )


def analyze(
    trees: list[TreeNode],
    nozzle: str = "0.4",
    spec: ConnectorSpec = DEFAULT_CONNECTOR,
    scale: float = MM_PER_UNIT,
) -> PrintabilityReport:
    if nozzle not in NOZZLE_PROFILES:
        raise ValueError(f"unknown nozzle {nozzle!r}; choose from {sorted(NOZZLE_PROFILES)}")
    profile = NOZZLE_PROFILES[nozzle]

    if not trees:
        return _empty_report(nozzle, "no nodes")

    for n in trees:
        if n.parentId is None:
            x, y = n.x * scale, -n.z * scale
            r = n.radius * scale
            if abs(x) + r > spec.foot_width / 2 or abs(y) + r > spec.foot_depth / 2:
                return _empty_report(nozzle, f"root {n.id} outside the standard foot")

    pa, pb, ra, rb = _segments(trees, scale)
    if len(pa) == 0:
        return _empty_report(nozzle, "no branches to print")

    vec = pb - pa
    length = np.linalg.norm(vec, axis=1)
    keep = length > 1e-9
    pa, pb, ra, rb, vec, length = pa[keep], pb[keep], ra[keep], rb[keep], vec[keep], length[keep]
    if len(length) == 0:
        return _empty_report(nozzle, "no branches to print")
    total = float(length.sum())

    # Thickness: a tapered segment is only as printable as its thinnest end.
    diameter = 2.0 * np.minimum(ra, rb)
    span = profile.warn_diameter - profile.fail_diameter
    thin_penalty = np.clip((profile.warn_diameter - diameter) / span, 0.0, 1.0)
    thickness_score = float(1.0 - (thin_penalty * length).sum() / total)

    # Overhang: elevation of the branch axis above horizontal. The underside of a
    # tube tilts by the same angle, so low-elevation branches need support.
    elevation = np.degrees(np.arcsin(np.clip(np.abs(vec[:, 2]) / length, 0.0, 1.0)))
    over_penalty = np.clip((OVERHANG_LIMIT_DEG - elevation) / OVERHANG_LIMIT_DEG, 0.0, 1.0)
    overhang_score = float(1.0 - (over_penalty * length).sum() / total)

    # Centre of mass (informational): frustum volumes at segment midpoints.
    vol = np.pi * length / 3.0 * (ra**2 + ra * rb + rb**2)
    mid = (pa + pb) / 2.0
    com = (mid * vol[:, None]).sum(axis=0) / vol.sum()

    return PrintabilityReport(
        score=float(np.clip(thickness_score * overhang_score, 0.0, 1.0)),
        thickness_score=thickness_score,
        overhang_score=overhang_score,
        gate_ok=True,
        gate_reason=None,
        nozzle=nozzle,
        min_diameter_mm=float(diameter.min()),
        thin_length_fraction=float(length[diameter < profile.warn_diameter].sum() / total),
        unprintable_length_fraction=float(
            length[diameter <= profile.fail_diameter].sum() / total
        ),
        overhang_length_fraction=float(length[elevation < OVERHANG_LIMIT_DEG].sum() / total),
        total_branch_length_mm=total,
        com_offset_mm=float(np.hypot(com[0], com[1])),
        com_height_mm=float(com[2]),
    )


def score(trees: list[TreeNode], nozzle: str = "0.4") -> float:
    return analyze(trees, nozzle).score
