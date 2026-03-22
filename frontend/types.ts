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

export interface TreeGenome {
  influence_radius: number;
  kill_distance: number;
  growth_step: number;
  repulsion_strength: number;
  attraction_strength: number;
  repulsion_radius: number;
  max_children_per_node: number;
  wiggle_factor: number;
  random_seed: number;
}

export interface GenerateRequest {
  count: number;
  params: GenerationParams;
  targetShadows: TargetShadow[];
  parent_nodes?: TreeNode[];
  parent_genome?: TreeGenome;
  parent_generation?: number;
  remaining_attractors?: AttractorPoint[];
  max_new_nodes: number;
  run_until_complete?: boolean;
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

export interface TargetShadow {
  imageData: string;
  lightVector: Vec3;
}

export interface AttractorPoint {
  x: number;
  y: number;
  z: number;
}

export interface GenerationStats {
  attractors_exhausted: boolean;
  remaining_attractors: number;
  total_attractors: number;
  nodes_grown: number;
  growth_stopped_reason: string;
  remaining_attractors_points?: AttractorPoint[];
}

export interface GenerateResponse {
  scenes: SceneData[];
  stats: GenerationStats;
}
