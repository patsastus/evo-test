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


# Request limits (defensive caps for /scenes/generate; UI currently sends
# count<=4, treeCount<=10, max_new_nodes<=500).
MAX_CANDIDATES = 16
MAX_TREE_COUNT = 10
MAX_NEW_NODES = 5000
MAX_TOTAL_NODES = 20000  # hard cap on tree size incl. run_until_complete loops
MAX_ATTRACTORS = 20000  # voxel grid yields at most ~9.3k, so this is generous
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_DIM = 4096
MAX_RUN_SECONDS = 60  # wall-clock budget per generate request (checked between growth passes)


# Print-space scale: 1 scene unit (the scene box is 10 units wide) == 10 mm,
# i.e. the 10-unit-wide scene is 100 mm.
MM_PER_UNIT = 10.0

# Shadow-match: "perceived" shadow = Gaussian blur (sigma as a fraction of one
# shadow's width) thresholded at this local darkness density. Chosen from a
# calibration sweep on tests/images (stable across 1-3% / 0.1-0.3).
PERCEIVED_SIGMA_FRAC = 0.02
PERCEIVED_THRESHOLD = 0.2
