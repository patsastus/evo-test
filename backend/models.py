from typing import Optional

from pydantic import BaseModel


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


class TargetShadow(BaseModel):
    imageData: str
    lightVector: Vec3


class AttractorPoint(BaseModel):
    x: float
    y: float
    z: float


class TreeGenome(BaseModel):
    influence_radius: float = 15.0
    kill_distance: float = 0.15
    growth_step: float = 0.3
    repulsion_strength: float = 2.0
    attraction_strength: float = 1.0
    repulsion_radius: float = 1.5
    max_children_per_node: int = 5
    wiggle_factor: float = 0.1
    random_seed: int = 42

    def mutate(self) -> "TreeGenome":
        import random

        # Local RNG: deterministic per genome seed, never touches the global `random` state.
        rng = random.Random(self.random_seed)

        def mutate_param(value: float, mutation_range: float = 0.15) -> float:
            change = (rng.random() - 0.5) * 2 * mutation_range
            new_value = value * (1 + change)
            return max(value * 0.5, min(value * 1.5, new_value))

        def mutate_int(value: int, mutation_range: float = 0.15) -> int:
            change = int(value * mutation_range)
            if change < 1:
                change = 1
            new_value = value + rng.randint(-change, change)
            return max(1, new_value)

        def mutate_bool(value: bool, flip_chance: float = 0.2) -> bool:
            if rng.random() < flip_chance:
                return not value
            return value

        return TreeGenome(
            influence_radius=mutate_param(self.influence_radius, 0.15),
            kill_distance=mutate_param(self.kill_distance, 0.15),
            growth_step=mutate_param(self.growth_step, 0.15),
            repulsion_strength=mutate_param(self.repulsion_strength, 0.15),
            attraction_strength=mutate_param(self.attraction_strength, 0.15),
            repulsion_radius=mutate_param(self.repulsion_radius, 0.15),
            max_children_per_node=mutate_int(self.max_children_per_node, 0.15),
            wiggle_factor=mutate_param(self.wiggle_factor, 0.20),
            random_seed=rng.randint(0, 1000000),
        )


class GenerateScenesRequest(BaseModel):
    count: int
    params: GenerationParams
    targetShadows: list[TargetShadow]
    parent_nodes: Optional[list[TreeNode]] = None
    parent_genome: Optional[TreeGenome] = None
    parent_generation: Optional[int] = None
    remaining_attractors: Optional[list[AttractorPoint]] = None
    max_new_nodes: int = 500
    run_until_complete: bool = False


class ExportObjRequest(BaseModel):
    scene: SceneData


class GenerationStats(BaseModel):
    attractors_exhausted: bool
    remaining_attractors: int
    total_attractors: int
    nodes_grown: int
    growth_stopped_reason: str
    remaining_attractors_points: Optional[list[AttractorPoint]] = None
