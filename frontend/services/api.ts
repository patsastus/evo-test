import { GenerateRequest, GenerateResponse, SceneData } from '../types';

const API_BASE = 'http://localhost:8000';

export const generateScenes = async (
  request: GenerateRequest
): Promise<GenerateResponse> => {
  const response = await fetch(`${API_BASE}/scenes/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Failed to generate scenes: ${response.statusText}`);
  }

  const json = await response.json();
  console.log('[DEBUG] API response stats:', json.stats);
  console.log('[DEBUG] remaining_attractors_points:', json.stats?.remaining_attractors_points);
  return json;
};

export const abortGeneration = async (): Promise<void> => {
  await fetch(`${API_BASE}/scenes/abort`, {
    method: 'POST',
  });
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
