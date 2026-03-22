from enum import Enum


BOUNDS = {
    "minX": -5,
    "maxX": 5,
    "minZ": -5,
    "maxZ": 5,
    "minY": 0,
    "maxY": 10,
}

CANVAS_WIDTH = 10

X_MIN = -5
X_MAX = 5
Z_MIN = -5
Z_MAX = 5
Y_BASE = 0.5

Z_WALL_X = -7.5
X_WALL_Z = 7.5


class LightType(Enum):
    LIGHT_Z = "light_z"
    LIGHT_X = "light_x"


LIGHT_Z = {
    "name": "Light Z",
    "type": LightType.LIGHT_Z,
    "direction": (1, 0, 0),
    "wall_x": Z_WALL_X,
    "axis_u": "y",
    "axis_v": "z",
}

LIGHT_X = {
    "name": "Light X",
    "type": LightType.LIGHT_X,
    "direction": (0, 0, 1),
    "wall_z": X_WALL_Z,
    "axis_u": "x",
    "axis_v": "y",
}
