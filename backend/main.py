import math
import random
import time
import uuid
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BOUNDS = {
    "minX": -5,
    "maxX": 5,
    "minZ": -5,
    "maxZ": 5,
    "minY": 0,
    "maxY": 10,
}


class Vec3(BaseModel):
    x: float
    y: float
    z: float


class TreeNode(BaseModel):
    id: str
    x: float
    y: float
    z: float
    radius: float
    parentId: Optional[str] = None


class Fitness(BaseModel):
    printability: float
    shadowMatch: float


class SceneData(BaseModel):
    id: str
    trees: list[TreeNode]
    fitness: Fitness
    shadowImageUrl: str
    generation: int
    timestamp: int


class GenerationParams(BaseModel):
    treeCount: int
    maxThickness: float
    branchingProb: float
    maxAngle: float


class GeneticParams(BaseModel):
    generations: int
    mutationRate: float
    populationSize: int


class GenerateScenesRequest(BaseModel):
    count: int
    params: GenerationParams


class EvolveScenesRequest(BaseModel):
    parent: SceneData
    params: GeneticParams


class ExportObjRequest(BaseModel):
    scene: SceneData


def _sub(v1: Vec3, v2: Vec3) -> Vec3:
    return Vec3(x=v1.x - v2.x, y=v1.y - v2.y, z=v1.z - v2.z)


def _dot(v1: Vec3, v2: Vec3) -> float:
    return v1.x * v2.x + v1.y * v2.y + v1.z * v2.z


def _get_seg_seg_dist(p1: Vec3, p2: Vec3, p3: Vec3, p4: Vec3) -> float:
    u = _sub(p2, p1)
    v = _sub(p4, p3)
    w = _sub(p1, p3)
    a = _dot(u, u)
    b = _dot(u, v)
    c = _dot(v, v)
    d = _dot(u, w)
    e = _dot(v, w)
    d_val = a * c - b * b

    small_num = 0.00000001

    s_d = d_val
    t_d = d_val

    if d_val < small_num:
        s_n = 0.0
        s_d = 1.0
        t_n = e
        t_d = c
    else:
        s_n = b * e - c * d
        t_n = a * e - b * d
        if s_n < 0.0:
            s_n = 0.0
            t_n = e
            t_d = c
        elif s_n > s_d:
            s_n = s_d
            t_n = e + b
            t_d = c

    if t_n < 0.0:
        t_n = 0.0
        if -d < 0.0:
            s_n = 0.0
        elif -d > a:
            s_n = s_d
        else:
            s_n = -d
            s_d = a
    elif t_n > t_d:
        t_n = t_d
        if (-d + b) < 0.0:
            s_n = 0
        elif (-d + b) > a:
            s_n = s_d
        else:
            s_n = -d + b
            s_d = a

    sc = 0.0 if abs(s_n) < small_num else s_n / s_d
    tc = 0.0 if abs(t_n) < small_num else t_n / t_d

    d_p = Vec3(
        x=w.x + (sc * u.x) - (tc * v.x),
        y=w.y + (sc * u.y) - (tc * v.y),
        z=w.z + (sc * u.z) - (tc * v.z),
    )

    return math.sqrt(_dot(d_p, d_p))


class Segment(BaseModel):
    p1: Vec3
    p2: Vec3
    radius: float
    nodeId: str
    parentId: str


def _get_all_segments(nodes: list[TreeNode]) -> list[Segment]:
    node_map = {n.id: n for n in nodes}
    segments: list[Segment] = []
    for n in nodes:
        if n.parentId:
            p = node_map.get(n.parentId)
            if p:
                segments.append(
                    Segment(
                        p1=Vec3(x=p.x, y=p.y, z=p.z),
                        p2=Vec3(x=n.x, y=n.y, z=n.z),
                        radius=(n.radius + p.radius) / 2,
                        nodeId=n.id,
                        parentId=p.id,
                    )
                )
    return segments


def _check_collision(
    p1: Vec3,
    p2: Vec3,
    r: float,
    segments: list[Segment],
    ignore_node_ids: Optional[list[str]] = None,
) -> bool:
    if ignore_node_ids is None:
        ignore_node_ids = []
    for seg in segments:
        if seg.nodeId in ignore_node_ids or seg.parentId in ignore_node_ids:
            continue

        dist = _get_seg_seg_dist(p1, p2, seg.p1, seg.p2)
        threshold = (r + seg.radius) * 0.85

        if dist < threshold:
            return True
    return False


def _generate_uuid() -> str:
    return uuid.uuid4().hex[:9]


def _generate_shadow_image(trees: list[TreeNode]) -> str:
    import base64
    from io import BytesIO
    from PIL import Image, ImageDraw

    size = 512
    light_count = 15
    radius = 10
    screen_z = -10
    scale = size / 24
    offset_x = size / 2
    offset_y = size - 20

    lights: list[Vec3] = []
    for i in range(light_count):
        angle = math.pi * (i / (light_count - 1))
        lights.append(
            Vec3(
                x=radius * math.cos(angle),
                y=0,
                z=radius * math.sin(angle),
            )
        )

    node_map = {n.id: n for n in trees}

    shadow_pixels = [[0.0] * size for _ in range(size)]

    for light in lights:
        temp_shadow = [[0.0] * size for _ in range(size)]

        for node in trees:
            if not node.parentId:
                continue
            parent = node_map.get(node.parentId)
            if not parent:
                continue

            if abs(node.z - light.z) < 0.001:
                continue

            t = (screen_z - light.z) / (node.z - light.z)

            p1_proj_x = light.x + (parent.x - light.x) * t
            p1_proj_y = light.y + (parent.y - light.y) * t
            p2_proj_x = light.x + (node.x - light.x) * t
            p2_proj_y = light.y + (node.y - light.y) * t

            p1_screen = (
                int(offset_x + p1_proj_x * scale),
                int(offset_y - p1_proj_y * scale),
            )
            p2_screen = (
                int(offset_x + p2_proj_x * scale),
                int(offset_y - p2_proj_y * scale),
            )

            avg_z = (node.z + parent.z) / 2
            mag = abs((screen_z - light.z) / (avg_z - light.z))
            thickness = ((node.radius + parent.radius) / 2) * mag * scale * 2
            line_width = max(1, int(thickness))

            p1_center = (p1_screen[0] - line_width // 2, p1_screen[1] - line_width // 2)
            p1_bounds = [
                p1_screen[0] - line_width // 2,
                p1_screen[1] - line_width // 2,
                p1_screen[0] + line_width // 2,
                p1_screen[1] + line_width // 2,
            ]

            for y in range(
                max(0, min(p1_screen[1], p2_screen[1]) - line_width),
                min(size, max(p1_screen[1], p2_screen[1]) + line_width),
            ):
                for x in range(
                    max(0, min(p1_screen[0], p2_screen[0]) - line_width),
                    min(size, max(p1_screen[0], p2_screen[0]) + line_width),
                ):
                    dist_to_line = _point_to_segment_dist(
                        x, y, p1_screen[0], p1_screen[1], p2_screen[0], p2_screen[1]
                    )
                    dist_to_p1 = math.sqrt(
                        (x - p1_screen[0]) ** 2 + (y - p1_screen[1]) ** 2
                    )
                    if dist_to_line <= line_width / 2 or dist_to_p1 <= line_width / 2:
                        temp_shadow[y][x] = 1.0

        for y in range(size):
            for x in range(size):
                if temp_shadow[y][x] > 0:
                    shadow_pixels[y][x] += 1.0 / light_count

    buffer = BytesIO()
    img = Image.new("RGB", (size, size), "white")
    for y in range(size):
        for x in range(size):
            intensity = shadow_pixels[y][x]
            val = int(255 * (1 - intensity))
            img.putpixel((x, y), (val, val, val))

    img.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"


def _point_to_segment_dist(
    px: float, py: float, x1: int, y1: int, x2: int, y2: int
) -> float:
    dx = x2 - x1
    dy = y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.sqrt((px - x1) ** 2 + (py - y1) ** 2)
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / length_sq))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.sqrt((px - proj_x) ** 2 + (py - proj_y) ** 2)


def _generate_tree(
    root_x: float,
    root_z: float,
    params: GenerationParams,
    existing_scene_nodes: list[TreeNode],
) -> list[TreeNode]:
    nodes: list[TreeNode] = []
    scene_segments = _get_all_segments(existing_scene_nodes)

    def add_local_segment(n: TreeNode, p: TreeNode) -> None:
        scene_segments.append(
            Segment(
                p1=Vec3(x=p.x, y=p.y, z=p.z),
                p2=Vec3(x=n.x, y=n.y, z=n.z),
                radius=(n.radius + p.radius) / 2,
                nodeId=n.id,
                parentId=p.id,
            )
        )

    safe_root_x = max(BOUNDS["minX"] + 1, min(BOUNDS["maxX"] - 1, root_x))
    safe_root_z = max(BOUNDS["minZ"] + 1, min(BOUNDS["maxZ"] - 1, root_z))

    root_id = _generate_uuid()
    root_node = TreeNode(
        id=root_id,
        x=safe_root_x,
        y=0,
        z=safe_root_z,
        radius=min(params.maxThickness, 0.8),
        parentId=None,
    )
    nodes.append(root_node)

    queue = [
        {
            "id": root_id,
            "x": safe_root_x,
            "y": 0,
            "z": safe_root_z,
            "level": 0,
            "dir": Vec3(x=0, y=1, z=0),
            "radius": root_node.radius,
        }
    ]

    max_levels = 6

    while queue:
        current = queue.pop(0)
        if current["level"] >= max_levels:
            continue

        branch_count = 2 if random.random() < params.branchingProb else 1

        for i in range(branch_count):
            added = False
            for attempt in range(3):
                angle_mod_x = (
                    (random.random() - 0.5) * params.maxAngle * (1 + attempt * 0.5)
                )
                angle_mod_z = (
                    (random.random() - 0.5) * params.maxAngle * (1 + attempt * 0.5)
                )

                new_dir = Vec3(
                    x=current["dir"].x + angle_mod_x,
                    y=current["dir"].y,
                    z=current["dir"].z + angle_mod_z,
                )

                length = math.sqrt(new_dir.x**2 + new_dir.y**2 + new_dir.z**2)
                new_dir.x /= length
                new_dir.y /= length
                new_dir.z /= length

                branch_length = 1.5 - (current["level"] * 0.15)

                new_x = current["x"] + new_dir.x * branch_length
                new_y = current["y"] + new_dir.y * branch_length
                new_z = current["z"] + new_dir.z * branch_length

                if (
                    new_x < BOUNDS["minX"]
                    or new_x > BOUNDS["maxX"]
                    or new_z < BOUNDS["minZ"]
                    or new_z > BOUNDS["maxZ"]
                    or new_y > BOUNDS["maxY"]
                    or new_y < BOUNDS["minY"]
                ):
                    continue

                new_id = _generate_uuid()
                new_radius = params.maxThickness * (
                    1 - (current["level"] + 1) / (max_levels + 2)
                )
                avg_radius = (current["radius"] + new_radius) / 2

                start = Vec3(x=current["x"], y=current["y"], z=current["z"])
                end = Vec3(x=new_x, y=new_y, z=new_z)

                if not _check_collision(
                    start, end, avg_radius, scene_segments, [current["id"]]
                ):
                    new_node = TreeNode(
                        id=new_id,
                        x=new_x,
                        y=new_y,
                        z=new_z,
                        radius=max(0.04, new_radius),
                        parentId=current["id"],
                    )

                    nodes.append(new_node)
                    add_local_segment(
                        new_node,
                        TreeNode(
                            id=current["id"],
                            x=current["x"],
                            y=current["y"],
                            z=current["z"],
                            radius=current["radius"],
                        ),
                    )

                    queue.append(
                        {
                            "id": new_id,
                            "x": new_x,
                            "y": new_y,
                            "z": new_z,
                            "level": current["level"] + 1,
                            "dir": new_dir,
                            "radius": new_radius,
                        }
                    )
                    added = True
                    break

    return nodes


def _generate_initial_scenes(count: int, params: GenerationParams) -> list[SceneData]:
    scenes: list[SceneData] = []

    for _ in range(count):
        trees: list[TreeNode] = []
        for t in range(params.treeCount):
            angle = (t / params.treeCount) * math.pi * 2 + (random.random() * 0.5)
            radius = random.random() * 3.5
            tx = math.cos(angle) * radius
            tz = math.sin(angle) * radius

            new_tree_nodes = _generate_tree(tx, tz, params, trees)
            trees.extend(new_tree_nodes)

        shadow_url = _generate_shadow_image(trees)

        scenes.append(
            SceneData(
                id=_generate_uuid(),
                trees=trees,
                fitness=Fitness(
                    printability=0.5 + random.random() * 0.5,
                    shadowMatch=0.3 + random.random() * 0.5,
                ),
                shadowImageUrl=shadow_url,
                generation=0,
                timestamp=int(time.time() * 1000),
            )
        )

    scenes.sort(key=lambda s: s.fitness.shadowMatch, reverse=True)
    return scenes


def _evolve_scenes(parent: SceneData, params: GeneticParams) -> list[SceneData]:
    offspring: list[SceneData] = []

    for _ in range(params.populationSize):
        new_trees = [TreeNode(**t.model_dump()) for t in parent.trees]

        node_map = {n.id: n for n in new_trees}

        current_segments = _get_all_segments(new_trees)

        for node in new_trees:
            if node.parentId and random.random() < params.mutationRate:
                original_pos = Vec3(x=node.x, y=node.y, z=node.z)

                mx = (random.random() - 0.5) * 0.8
                my = (random.random() - 0.5) * 0.8
                mz = (random.random() - 0.5) * 0.8

                candidate = Vec3(
                    x=node.x + mx,
                    y=node.y + my,
                    z=node.z + mz,
                )

                if candidate.x < BOUNDS["minX"] or candidate.x > BOUNDS["maxX"]:
                    candidate.x = original_pos.x
                if candidate.y < BOUNDS["minY"] or candidate.y > BOUNDS["maxY"]:
                    candidate.y = original_pos.y
                if candidate.z < BOUNDS["minZ"] or candidate.z > BOUNDS["maxZ"]:
                    candidate.z = original_pos.z

                if (
                    candidate.x == original_pos.x
                    and candidate.y == original_pos.y
                    and candidate.z == original_pos.z
                ):
                    continue

                parent_node = node_map.get(node.parentId)
                children = [n for n in new_trees if n.parentId == node.id]

                collision = False

                if parent_node:
                    avg_r = (parent_node.radius + node.radius) / 2
                    if _check_collision(
                        Vec3(x=parent_node.x, y=parent_node.y, z=parent_node.z),
                        candidate,
                        avg_r,
                        current_segments,
                        [node.id, parent_node.id],
                    ):
                        collision = True

                if not collision:
                    for child in children:
                        avg_r = (node.radius + child.radius) / 2
                        if _check_collision(
                            candidate,
                            Vec3(x=child.x, y=child.y, z=child.z),
                            avg_r,
                            current_segments,
                            [node.id, child.id],
                        ):
                            collision = True
                            break

                if not collision:
                    node.x = candidate.x
                    node.y = candidate.y
                    node.z = candidate.z
                    current_segments = _get_all_segments(new_trees)

        shadow_url = _generate_shadow_image(new_trees)

        offspring.append(
            SceneData(
                id=_generate_uuid(),
                trees=new_trees,
                fitness=Fitness(
                    printability=min(
                        1, parent.fitness.printability + (random.random() - 0.5) * 0.2
                    ),
                    shadowMatch=min(
                        1, parent.fitness.shadowMatch + (random.random() - 0.3) * 0.2
                    ),
                ),
                shadowImageUrl=shadow_url,
                generation=parent.generation + params.generations,
                timestamp=int(time.time() * 1000),
            )
        )

    offspring.sort(key=lambda s: s.fitness.shadowMatch, reverse=True)
    return offspring


def _export_to_obj(scene: SceneData) -> str:
    obj_output = "# Shadow Evolution Export\n"

    for node in scene.trees:
        obj_output += f"v {node.x:.4f} {node.y:.4f} {node.z:.4f}\n"

    id_to_index: dict[str, int] = {}
    for index, node in enumerate(scene.trees):
        id_to_index[node.id] = index + 1

    obj_output += "\n"

    for node in scene.trees:
        if node.parentId:
            parent_idx = id_to_index.get(node.parentId)
            current_idx = id_to_index.get(node.id)
            if parent_idx and current_idx:
                obj_output += f"l {parent_idx} {current_idx}\n"

    return obj_output


@app.get("/")
def read_root():
    return {"message": "Shadow Evolution Backend API"}


@app.post("/scenes/generate", response_model=list[SceneData])
def generate_scenes(request: GenerateScenesRequest):
    return _generate_initial_scenes(request.count, request.params)


@app.post("/scenes/evolve", response_model=list[SceneData])
def evolve_scenes(request: EvolveScenesRequest):
    return _evolve_scenes(request.parent, request.params)


@app.post("/export/obj")
def export_obj(request: ExportObjRequest):
    return {"obj": _export_to_obj(request.scene)}
