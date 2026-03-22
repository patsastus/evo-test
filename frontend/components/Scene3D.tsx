import React, { useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera, Environment } from '@react-three/drei';
import * as THREE from 'three';
import { SceneData, TreeNode } from '../types';

interface Scene3DProps {
  data: SceneData;
}

const WALL_HEIGHT_BASE = 0.5;
const WALL_WIDTH = 12.5;
const Z_WALL_X = -7.5;
const X_WALL_Z = 7.5;

const TreeRenderer: React.FC<{ trees: TreeNode[] }> = ({ trees }) => {
  const connections = useMemo(() => {
    const comps: React.ReactElement[] = [];
    const nodeMap = new Map<string, TreeNode>();
    trees.forEach(t => nodeMap.set(t.id, t));

    trees.forEach((node) => {
      if (!node.parentId) return;
      const parent = nodeMap.get(node.parentId);
      if (!parent) return;

      const start = new THREE.Vector3(parent.x, parent.y, parent.z);
      const end = new THREE.Vector3(node.x, node.y, node.z);
      const distance = start.distanceTo(end);
      const position = start.clone().add(end).multiplyScalar(0.5);
      
      const direction = end.clone().sub(start).normalize();
      const quaternion = new THREE.Quaternion();
      quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction);

      comps.push(
        <mesh 
            key={node.id} 
            position={position} 
            quaternion={quaternion} 
            castShadow 
            receiveShadow
        >
          <cylinderGeometry args={[node.radius, parent.radius, distance, 6]} />
          <meshStandardMaterial color="#8b5a2b" roughness={0.9} />
        </mesh>
      );
      
      comps.push(
          <mesh key={`joint-${node.id}`} position={start} castShadow receiveShadow>
              <sphereGeometry args={[parent.radius, 6, 6]} />
              <meshStandardMaterial color="#8b5a2b" roughness={0.9} />
          </mesh>
      )
    });
    return comps;
  }, [trees]);

  return <group>{connections}</group>;
};

const SceneVisualization: React.FC = () => {
  const lights = useMemo(() => {
    const positions: THREE.Vector3[] = [];
    for (let i = 0; i < 9; i++) {
      const theta = (i / 8) * (Math.PI / 2);
      const x = -5 + 15 * Math.cos(theta);
      const z = 5 - 15 * Math.sin(theta);
      positions.push(new THREE.Vector3(x, 0, z));
    }
    return positions;
  }, []);

  const wallHeight = WALL_WIDTH * (153 / 256);

  return (
    <group>
      <gridHelper args={[20, 20, 0x444444, 0x222222]} position={[0, -0.01, 0]} />
      
      <mesh position={[0, 0, 0]} rotation={[0, 0, 0]} receiveShadow>
        <boxGeometry args={[10, 0.1, 10]} />
        <meshStandardMaterial color="#1a1a1a" />
      </mesh>

      <mesh position={[Z_WALL_X, WALL_HEIGHT_BASE + wallHeight / 2, (Z_WALL_Z_MIN + Z_WALL_Z_MAX) / 2]} receiveShadow>
        <boxGeometry args={[0.1, wallHeight, WALL_WIDTH]} />
        <meshStandardMaterial color="#666666" transparent opacity={0.5} />
      </mesh>
      <mesh position={[(X_WALL_X_MIN + X_WALL_X_MAX) / 2, WALL_HEIGHT_BASE + wallHeight / 2, X_WALL_Z]} receiveShadow>
        <boxGeometry args={[WALL_WIDTH, wallHeight, 0.1]} />
        <meshStandardMaterial color="#555555" transparent opacity={0.5} />
      </mesh>

      {lights.map((pos, i) => (
        <mesh key={i} position={pos}>
          <sphereGeometry args={[0.3, 16, 16]} />
          <meshStandardMaterial color="#ffff00" emissive="#ffff00" emissiveIntensity={0.5} />
        </mesh>
      ))}

      <lineSegments position={[0, 5, 0]}>
        <edgesGeometry args={[new THREE.BoxGeometry(10, 10, 10)]} />
        <lineBasicMaterial color="#334155" />
      </lineSegments>
    </group>
  );
};

const Z_WALL_Z_MIN = -5;
const Z_WALL_Z_MAX = 7.5;
const X_WALL_X_MIN = -7.5;
const X_WALL_X_MAX = 5;

export const Scene3D: React.FC<Scene3DProps> = ({ data }) => {
  return (
    <Canvas 
        shadows 
        dpr={[1, 1.5]} 
        className="w-full h-full bg-slate-900"
    >
      <PerspectiveCamera makeDefault position={[12, 12, 12]} fov={45} />
      <OrbitControls makeDefault minPolarAngle={0} maxPolarAngle={Math.PI / 2} />
      <ambientLight intensity={0.8} />
      
      <SceneVisualization />

      <group position={[0, 0, 0]}>
        <TreeRenderer trees={data.trees} />
      </group>
    </Canvas>
  );
};