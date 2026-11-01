from models import SceneData


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
