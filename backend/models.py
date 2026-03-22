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


class GenerateScenesRequest(BaseModel):
    count: int
    params: GenerationParams
    targetShadows: list[TargetShadow]


class EvolveScenesRequest(BaseModel):
    parent: SceneData
    params: GeneticParams


class ExportObjRequest(BaseModel):
    scene: SceneData


class AttractorPoint(BaseModel):
    x: float
    y: float
    z: float
