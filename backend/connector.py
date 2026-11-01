"""Shared connector spec for the standard scene foot (and, later, the base plate).

All lengths are millimetres in print space. The scene foot carries *sockets*
(negatives) that mate with pegs on a base plate built from the same spec, so any
scene fits any base. Socket sizes/positions are deliberately asymmetric so the
scene can only be inserted in one orientation (the shadows only work at the
right angle to the light walls).

The clearance is a first guess for FDM friction fits and is meant to be tuned
with test prints.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PegSpec:
    x: float  # offset from foot centre
    y: float
    diameter: float  # peg diameter on the base plate


@dataclass(frozen=True)
class ConnectorSpec:
    # Scene foot (the standard part every scene grows out of).
    foot_width: float = 70.0  # X extent
    foot_depth: float = 70.0  # Y extent
    foot_height: float = 12.0  # Z extent, root sits on top

    # Peg/socket geometry.
    peg_length: float = 5.0 # cylindrical part; a 45 deg cone ceiling is added
    clearance: float = 0.25  # radial clearance of the socket over the peg
    pegs: tuple[PegSpec, ...] = (
        PegSpec(x=-15.0, y=-10.0, diameter=6.0),
        PegSpec(x=15.0, y=10.0, diameter=8.0),
    )

    def socket_radius(self, peg: PegSpec) -> float:
        return peg.diameter / 2 + self.clearance

    def socket_depth(self, peg: PegSpec) -> float:
        # Cylinder + 45 deg cone ceiling (cone height == radius): bridge-free.
        return self.peg_length + self.socket_radius(peg)

    def validate(self) -> None:
        for peg in self.pegs:
            r = self.socket_radius(peg)
            if self.socket_depth(peg) >= self.foot_height:
                raise ValueError("socket deeper than foot; increase foot_height")
            if abs(peg.x) + r > self.foot_width / 2 or abs(peg.y) + r > self.foot_depth / 2:
                raise ValueError("socket outside foot footprint")


DEFAULT_CONNECTOR = ConnectorSpec()
