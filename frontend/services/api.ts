import { SceneData, GenerationParams, GeneticParams, TargetShadow } from '../types';

const API_BASE = 'http://localhost:8000';

export const generateInitialScenes = async (
  count: number,
  params: GenerationParams,
  targetShadows: TargetShadow[]
): Promise<SceneData[]> => {
  const response = await fetch(`${API_BASE}/scenes/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ count, params, targetShadows }),
  });

  if (!response.ok) {
    throw new Error(`Failed to generate scenes: ${response.statusText}`);
  }

  return response.json();
};

export const evolveScenes = async (
  parent: SceneData,
  params: GeneticParams
): Promise<SceneData[]> => {
  const response = await fetch(`${API_BASE}/scenes/evolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ parent, params }),
  });

  if (!response.ok) {
    throw new Error(`Failed to evolve scenes: ${response.statusText}`);
  }

  return response.json();
};

export const exportToOBJ = async (scene: SceneData): Promise<string> => {
  const response = await fetch(`${API_BASE}/export/obj`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scene }),
  });

  if (!response.ok) {
    throw new Error(`Failed to export OBJ: ${response.statusText}`);
  }

  const data = await response.json();
  return data.obj;
};
