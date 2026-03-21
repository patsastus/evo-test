import React, { useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera, Environment } from '@react-three/drei';
import * as THREE from 'three';
import { SceneData, TreeNode } from '../types';

interface Scene3DProps {
  data: SceneData;
}

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

export const Scene3D: React.FC<Scene3DProps> = ({ data }) => {
  return (
    <Canvas 
        shadows 
        dpr={[1, 1.5]} 
        className="w-full h-full bg-slate-900"
    >
      <PerspectiveCamera makeDefault position={[12, 12, 12]} fov={45} />
      <OrbitControls makeDefault minPolarAngle={0} maxPolarAngle={Math.PI / 2} />
      <ambientLight intensity={0.5} />
      <directionalLight position={[5, 10, 5]} intensity={1} castShadow />
      <Environment preset="city" />
      
      {/* 10x10x10 Bounding Box Helper */}
      <lineSegments position={[0, 5, 0]}>
          <boxGeometry args={[10, 10, 10]} />
          <lineBasicMaterial color="#334155" transparent opacity={0.5} />
      </lineSegments>

      <group position={[0, 0, 0]}>
        <TreeRenderer trees={data.trees} />
        <gridHelper args={[20, 20, 0x444444, 0x222222]} position={[0, -0.01, 0]} />
      </group>
    </Canvas>
  );
};