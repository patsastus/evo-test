export interface TreeNode {
  id: string;
  x: number;
  y: number;
  z: number;
  radius: number;
  parentId: string | null;
}

export interface SceneData {
  id: string;
  trees: TreeNode[];
  fitness: {
    printability: number;
    shadowMatch: number;
  };
  shadowImageUrl: string;
  generation: number;
  timestamp: number;
}

export interface GenerationParams {
  treeCount: number;
  maxThickness: number;
  branchingProb: number;
  maxAngle: number;
}

export interface GeneticParams {
  generations: number;
  mutationRate: number;
  populationSize: number;
}

export enum AppState {
  IDLE = 'IDLE',
  GENERATING = 'GENERATING',
  VIEWING = 'VIEWING',
}

export interface Vec3 {
  x: number;
  y: number;
  z: number;
}