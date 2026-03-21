import { SceneData, TreeNode, GenerationParams, GeneticParams, Vec3 } from '../types';

// Helper to generate a unique ID
const uuid = () => Math.random().toString(36).substr(2, 9);

// Bounds: 10x10x10 cm. 
// Center base at (0,0,0). 
// X: [-5, 5], Z: [-5, 5], Y: [0, 10]
const BOUNDS = {
  minX: -5, maxX: 5,
  minZ: -5, maxZ: 5,
  minY: 0, maxY: 10
};

// --- Math Helpers for Collision Detection ---

function sub(v1: Vec3, v2: Vec3) { return {x: v1.x-v2.x, y: v1.y-v2.y, z: v1.z-v2.z}; }
function dot(v1: Vec3, v2: Vec3) { return v1.x*v2.x + v1.y*v2.y + v1.z*v2.z; }

// Robust Segment-Segment Distance in 3D
function getSegSegDist(p1: Vec3, p2: Vec3, p3: Vec3, p4: Vec3) {
    const u = sub(p2, p1);
    const v = sub(p4, p3);
    const w = sub(p1, p3);
    const a = dot(u, u);
    const b = dot(u, v);
    const c = dot(v, v);
    const d = dot(u, w);
    const e = dot(v, w);
    const D = a*c - b*b;
    
    let sc, sN, sD = D;
    let tc, tN, tD = D;

    const SMALL_NUM = 0.00000001;

    if (D < SMALL_NUM) { // Parallel
        sN = 0.0;
        sD = 1.0;
        tN = e;
        tD = c;
    } else {
        sN = (b*e - c*d);
        tN = (a*e - b*d);
        if (sN < 0.0) { sN = 0.0; tN = e; tD = c; }
        else if (sN > sD) { sN = sD; tN = e + b; tD = c; }
    }

    if (tN < 0.0) {
        tN = 0.0;
        if (-d < 0.0) sN = 0.0;
        else if (-d > a) sN = sD;
        else { sN = -d; sD = a; }
    }
    else if (tN > tD) {
        tN = tD;
        if ((-d + b) < 0.0) sN = 0;
        else if ((-d + b) > a) sN = sD;
        else { sN = (-d + b); sD = a; }
    }

    sc = (Math.abs(sN) < SMALL_NUM ? 0.0 : sN / sD);
    tc = (Math.abs(tN) < SMALL_NUM ? 0.0 : tN / tD);

    const dP = {
        x: w.x + (sc * u.x) - (tc * v.x),
        y: w.y + (sc * u.y) - (tc * v.y),
        z: w.z + (sc * u.z) - (tc * v.z)
    };

    return Math.sqrt(dot(dP, dP));
}

interface Segment {
    p1: Vec3;
    p2: Vec3;
    radius: number;
    nodeId: string;
    parentId: string;
}

const getAllSegments = (nodes: TreeNode[]): Segment[] => {
    const nodeMap = new Map<string, TreeNode>();
    nodes.forEach(n => nodeMap.set(n.id, n));
    const segments: Segment[] = [];
    nodes.forEach(n => {
        if (n.parentId) {
            const p = nodeMap.get(n.parentId);
            if (p) {
                segments.push({
                    p1: {x: p.x, y: p.y, z: p.z},
                    p2: {x: n.x, y: n.y, z: n.z},
                    radius: (n.radius + p.radius) / 2,
                    nodeId: n.id,
                    parentId: p.id
                });
            }
        }
    });
    return segments;
};

const checkCollision = (p1: Vec3, p2: Vec3, r: number, segments: Segment[], ignoreNodeIds: string[] = []): boolean => {
    for (const seg of segments) {
        // Skip checking against segments connected to the node we are moving/creating
        // i.e., skip if the segment shares a vertex with p1 or p2 conceptually
        // In our case, p1 is usually the parent node. 
        // We handle this by checking distance. 
        // If distance is near zero at endpoints, we must ignore it if they are topologically connected.
        // However, geometric coincidence != topological connection for separate trees.
        // So we explicitly ignore segments based on ID if provided.
        
        if (ignoreNodeIds.includes(seg.nodeId) || ignoreNodeIds.includes(seg.parentId)) continue;

        // "Welding" check: if p1 or p2 is very close to seg.p1 or seg.p2, it might be a joint.
        // We assume valid connections are handled via ignoreNodeIds. 
        // Any other close proximity is a collision.
        
        const dist = getSegSegDist(p1, p2, seg.p1, seg.p2);
        
        // Threshold: sum of radii. 
        // We multiply by 0.9 to allow a tiny bit of overlap (grazing) without triggering, 
        // otherwise joints might trigger self-collision due to float precision.
        const threshold = (r + seg.radius) * 0.85;

        if (dist < threshold) {
             return true; 
        }
    }
    return false;
};

// --- End Math Helpers ---


// Simulate server-side shadow generation
// We project the 3D nodes onto a 2D plane using 15 lights in a semicircle
const generateShadowImage = (trees: TreeNode[]): string => {
    const size = 512;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');
    if (!ctx) return '';

    // Fill white background
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, size, size);

    const LIGHT_COUNT = 15;
    const RADIUS = 10;
    const SCREEN_Z = -10; // Screen is 10cm behind center (0,0,0)

    // Temporary canvas for individual light pass (binary shadow mask)
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = size;
    tempCanvas.height = size;
    const tempCtx = tempCanvas.getContext('2d');
    if (!tempCtx) return '';

    // Generate lights in semicircle at Y=0
    // Z > 0 is front. Semicircle centered on middle (0,0,0)
    const lights: {x:number, y:number, z:number}[] = [];
    for(let i=0; i<LIGHT_COUNT; i++) {
        // Angle from 0 to PI
        const angle = Math.PI * (i / (LIGHT_COUNT - 1));
        lights.push({
            x: RADIUS * Math.cos(angle),
            y: 0, 
            z: RADIUS * Math.sin(angle) // Z always positive (front)
        });
    }

    // Prepare projection helper
    // Fits roughly 25x25 area
    const scale = size / 24; 
    const offsetX = size / 2;
    const offsetY = size - 20; // Padding from bottom

    const project = (p: {x:number, y:number, z:number}, light: {x:number, y:number, z:number}) => {
         // Intersect line L->P with plane Z=SCREEN_Z
         if (Math.abs(p.z - light.z) < 0.001) return {x:0, y:0}; // Parallel protection

         const t = (SCREEN_Z - light.z) / (p.z - light.z);
         const projX = light.x + (p.x - light.x) * t;
         const projY = light.y + (p.y - light.y) * t;
         
         // Transform to Canvas Coords
         // World Y is up, Canvas Y is down.
         const x = offsetX + projX * scale;
         const y = offsetY - projY * scale;

         return { x, y };
    };

    // Node Map for fast lookup
    const nodeMap = new Map<string, TreeNode>();
    trees.forEach(t => nodeMap.set(t.id, t));

    // Accumulate shadows: standard source-over blending with low alpha simulates light blocking
    // Each light adds 1/15th intensity.
    ctx.globalAlpha = 1 / LIGHT_COUNT;

    lights.forEach(light => {
        // Clear temp canvas (transparent)
        tempCtx.clearRect(0, 0, size, size);
        tempCtx.lineCap = 'round';
        tempCtx.lineJoin = 'round';
        tempCtx.strokeStyle = 'black';
        tempCtx.fillStyle = 'black';

        // Draw tree on temp canvas as a solid binary mask for this light source
        trees.forEach(node => {
            if (!node.parentId) return;
            const parent = nodeMap.get(node.parentId);
            if (!parent) return;

            const p1 = project(parent, light);
            const p2 = project(node, light);

            // Approximate projected thickness
            // d_screen / d_object = (ScreenZ - LightZ) / (ObjectZ - LightZ)
            const avgZ = (node.z + parent.z) / 2;
            const mag = Math.abs((SCREEN_Z - light.z) / (avgZ - light.z));
            
            // *2 factor helps visibility of thin lines
            const thickness = ((node.radius + parent.radius) / 2) * mag * scale * 2; 

            tempCtx.lineWidth = Math.max(1, thickness);
            
            tempCtx.beginPath();
            tempCtx.moveTo(p1.x, p1.y);
            tempCtx.lineTo(p2.x, p2.y);
            tempCtx.stroke();
            
            // Cap joints
            tempCtx.beginPath();
            tempCtx.arc(p1.x, p1.y, tempCtx.lineWidth/2, 0, Math.PI*2);
            tempCtx.fill();
        });

        // Draw temp canvas to main
        ctx.drawImage(tempCanvas, 0, 0);
    });

    return canvas.toDataURL('image/png');
};

const generateTree = (rootX: number, rootZ: number, params: GenerationParams, existingSceneNodes: TreeNode[]): TreeNode[] => {
  const nodes: TreeNode[] = [];
  const rootId = uuid();
  
  // Collect all existing segments in the scene so far to check collision against
  const sceneSegments = getAllSegments(existingSceneNodes);

  // Helper to add local segments to the check list as we grow
  const addLocalSegment = (n: TreeNode, p: TreeNode) => {
      sceneSegments.push({
          p1: {x: p.x, y: p.y, z: p.z},
          p2: {x: n.x, y: n.y, z: n.z},
          radius: (n.radius + p.radius) / 2,
          nodeId: n.id,
          parentId: p.id
      });
  };

  const safeRootX = Math.max(BOUNDS.minX + 1, Math.min(BOUNDS.maxX - 1, rootX));
  const safeRootZ = Math.max(BOUNDS.minZ + 1, Math.min(BOUNDS.maxZ - 1, rootZ));

  // Root node
  const rootNode = {
    id: rootId,
    x: safeRootX,
    y: 0,
    z: safeRootZ,
    radius: Math.min(params.maxThickness, 0.8),
    parentId: null
  };
  nodes.push(rootNode);

  const queue = [{ 
      id: rootId, 
      x: safeRootX, 
      y: 0, 
      z: safeRootZ, 
      level: 0, 
      dir: { x: 0, y: 1, z: 0 },
      radius: rootNode.radius
  }];
  
  const maxLevels = 6;

  while (queue.length > 0) {
    const current = queue.shift()!;
    if (current.level >= maxLevels) continue;

    const branchCount = Math.random() < params.branchingProb ? 2 : 1;

    for (let i = 0; i < branchCount; i++) {
      // Try multiple times to find a valid direction if collision occurs
      let added = false;
      for (let attempt = 0; attempt < 3; attempt++) {
          const angleModX = (Math.random() - 0.5) * params.maxAngle * (1 + attempt * 0.5); // Widen search on retries
          const angleModZ = (Math.random() - 0.5) * params.maxAngle * (1 + attempt * 0.5);
          
          const newDir = {
            x: current.dir.x + angleModX,
            y: current.dir.y, 
            z: current.dir.z + angleModZ
          };

          const len = Math.sqrt(newDir.x**2 + newDir.y**2 + newDir.z**2);
          newDir.x /= len; newDir.y /= len; newDir.z /= len;

          const branchLength = 1.5 - (current.level * 0.15); 
          
          const newX = current.x + newDir.x * branchLength;
          const newY = current.y + newDir.y * branchLength;
          const newZ = current.z + newDir.z * branchLength;
          
          if (newX < BOUNDS.minX || newX > BOUNDS.maxX || 
              newZ < BOUNDS.minZ || newZ > BOUNDS.maxZ || 
              newY > BOUNDS.maxY || newY < BOUNDS.minY) {
              continue;
          }

          const newId = uuid();
          const newRadius = params.maxThickness * (1 - (current.level + 1) / (maxLevels + 2));
          const avgRadius = (current.radius + newRadius) / 2;

          // Check Collision
          const start = {x: current.x, y: current.y, z: current.z};
          const end = {x: newX, y: newY, z: newZ};
          
          // Ignore the current node's parent connection in check (physically connected)
          if (!checkCollision(start, end, avgRadius, sceneSegments, [current.id])) {
              const newNode: TreeNode = {
                id: newId,
                x: newX,
                y: newY,
                z: newZ,
                radius: Math.max(0.04, newRadius),
                parentId: current.id
              };

              nodes.push(newNode);
              addLocalSegment(newNode, {x: current.x, y: current.y, z: current.z, id: current.id} as any);

              queue.push({
                id: newId,
                x: newX,
                y: newY,
                z: newZ,
                level: current.level + 1,
                dir: newDir,
                radius: newRadius
              });
              added = true;
              break; // Success, stop attempts
          }
      }
    }
  }

  return nodes;
};

export const generateInitialScenes = async (count: number, params: GenerationParams): Promise<SceneData[]> => {
  await new Promise(resolve => setTimeout(resolve, 800));

  const scenes: SceneData[] = [];
  for (let i = 0; i < count; i++) {
    const trees: TreeNode[] = [];
    // Generate trees sequentially so they can check for collisions against previous ones
    for (let t = 0; t < params.treeCount; t++) {
        const angle = (t / params.treeCount) * Math.PI * 2 + (Math.random() * 0.5);
        const radius = Math.random() * 3.5;
        const tx = Math.cos(angle) * radius;
        const tz = Math.sin(angle) * radius;
        
        // Pass current existing trees to detect collision
        const newTreeNodes = generateTree(tx, tz, params, trees);
        trees.push(...newTreeNodes);
    }

    const shadowUrl = generateShadowImage(trees);

    scenes.push({
      id: uuid(),
      trees,
      fitness: {
        printability: 0.5 + Math.random() * 0.5,
        shadowMatch: 0.3 + Math.random() * 0.5,
      },
      shadowImageUrl: shadowUrl,
      generation: 0,
      timestamp: Date.now(),
    });
  }

  // Sort scenes by shadow match fitness (descending)
  scenes.sort((a, b) => b.fitness.shadowMatch - a.fitness.shadowMatch);

  return scenes;
};

export const evolveScenes = async (parent: SceneData, params: GeneticParams): Promise<SceneData[]> => {
  await new Promise(resolve => setTimeout(resolve, 1500));

  const offspring: SceneData[] = [];
  
  for (let i = 0; i < params.populationSize; i++) {
    // Deep clone nodes
    const newTrees: TreeNode[] = parent.trees.map(t => ({ ...t }));
    
    // Map for quick lookup
    const nodeMap = new Map<string, TreeNode>();
    newTrees.forEach(n => nodeMap.set(n.id, n));

    // Get all segments for collision check. 
    // We will update this or re-check against it.
    // For simplicity, we check against the *original* structure state or the *current* state?
    // Current state is better.
    let currentSegments = getAllSegments(newTrees);

    newTrees.forEach(node => {
        // Only mutate non-root nodes
        if (node.parentId && Math.random() < params.mutationRate) {
            const originalPos = { x: node.x, y: node.y, z: node.z };
            
            const mx = (Math.random() - 0.5) * 0.8;
            const my = (Math.random() - 0.5) * 0.8;
            const mz = (Math.random() - 0.5) * 0.8;
            
            const candidate = {
                x: node.x + mx,
                y: node.y + my,
                z: node.z + mz
            };

            // Bounds check
            if (candidate.x < BOUNDS.minX || candidate.x > BOUNDS.maxX) candidate.x = originalPos.x;
            if (candidate.y < BOUNDS.minY || candidate.y > BOUNDS.maxY) candidate.y = originalPos.y;
            if (candidate.z < BOUNDS.minZ || candidate.z > BOUNDS.maxZ) candidate.z = originalPos.z;

            // If no change, skip
            if (candidate.x === originalPos.x && candidate.y === originalPos.y && candidate.z === originalPos.z) return;

            // Check collision for all segments connected to this node:
            // 1. Parent -> Node
            // 2. Node -> Children
            
            const parent = nodeMap.get(node.parentId);
            const children = newTrees.filter(n => n.parentId === node.id);
            
            let collision = false;
            
            if (parent) {
                // Check Parent -> NewNode position
                const avgR = (parent.radius + node.radius) / 2;
                // Ignore: Current Node ID (the segment we are moving) and Parent ID (connected)
                // We use ignoreNodeIds to skip the *old* version of the segment in 'currentSegments' 
                // and any other connected segments that naturally touch.
                if (checkCollision({x: parent.x, y: parent.y, z: parent.z}, candidate, avgR, currentSegments, [node.id, parent.id])) {
                    collision = true;
                }
            }

            if (!collision) {
                for (const child of children) {
                    const avgR = (node.radius + child.radius) / 2;
                    if (checkCollision(candidate, {x: child.x, y: child.y, z: child.z}, avgR, currentSegments, [node.id, child.id])) {
                        collision = true;
                        break;
                    }
                }
            }

            if (!collision) {
                // Apply mutation
                node.x = candidate.x;
                node.y = candidate.y;
                node.z = candidate.z;
                
                // Update segments list for next iteration (brute force rebuild is safer than partial update for this scale)
                currentSegments = getAllSegments(newTrees);
            }
        }
    });

    const shadowUrl = generateShadowImage(newTrees);

    offspring.push({
      id: uuid(),
      trees: newTrees,
      fitness: {
        printability: Math.min(1, parent.fitness.printability + (Math.random() - 0.5) * 0.2),
        shadowMatch: Math.min(1, parent.fitness.shadowMatch + (Math.random() - 0.3) * 0.2),
      },
      shadowImageUrl: shadowUrl,
      generation: parent.generation + params.generations,
      timestamp: Date.now(),
    });
  }

  // Sort offspring by shadow match fitness (descending)
  offspring.sort((a, b) => b.fitness.shadowMatch - a.fitness.shadowMatch);

  return offspring;
};

export const exportToOBJ = (scene: SceneData): string => {
  let objOutput = "# Shadow Evolution Export\n";
  
  scene.trees.forEach(node => {
      objOutput += `v ${node.x.toFixed(4)} ${node.y.toFixed(4)} ${node.z.toFixed(4)}\n`;
  });

  const idToIndexMap = new Map<string, number>();
  scene.trees.forEach((node, index) => {
      idToIndexMap.set(node.id, index + 1);
  });

  objOutput += "\n";
  
  scene.trees.forEach(node => {
      if (node.parentId) {
          const parentIdx = idToIndexMap.get(node.parentId);
          const currentIdx = idToIndexMap.get(node.id);
          if (parentIdx && currentIdx) {
              objOutput += `l ${parentIdx} ${currentIdx}\n`;
          }
      }
  });

  return objOutput;
};