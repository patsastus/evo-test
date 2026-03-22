import React, { useState, useEffect, useRef } from 'react';
import { ControlPanel } from './components/ControlPanel';
import { Gallery } from './components/Gallery';
import { DetailModal } from './components/DetailModal';
import { SceneData, AppState, TargetShadow, TreeGenome, GenerationParams, GenerationStats, AttractorPoint } from './types';
import { generateScenes, abortGeneration } from './services/api';

const blobToBase64 = (blobUrl: string): Promise<string> => {
  return fetch(blobUrl)
    .then(res => res.blob())
    .then(blob => {
      return new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result as string);
        reader.onerror = reject;
        reader.readAsDataURL(blob);
      });
    });
};

const DEFAULT_GENOME: TreeGenome = {
  influence_radius: 15.0,
  kill_distance: 0.15,
  growth_step: 0.3,
  repulsion_strength: 2.0,
  attraction_strength: 1.0,
  repulsion_radius: 1.5,
  max_children_per_node: 5,
  wiggle_factor: 0.1,
  random_seed: 42,
};

const App: React.FC = () => {
  const [targetImage, setTargetImage] = useState<string | null>(null);
  const [scenes, setScenes] = useState<SceneData[]>([]);
  const [savedScenes, setSavedScenes] = useState<SceneData[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [appState, setAppState] = useState<AppState>(AppState.IDLE);
  const [activeTab, setActiveTab] = useState<'generated' | 'saved'>('generated');
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [treeCount, setTreeCount] = useState(1);
  const [currentGenome, setCurrentGenome] = useState<TreeGenome>(DEFAULT_GENOME);
  const [generationNumber, setGenerationNumber] = useState(0);
  const [growthComplete, setGrowthComplete] = useState(false);
  const [stats, setStats] = useState<GenerationStats | null>(null);
  const [remainingAttractors, setRemainingAttractors] = useState<AttractorPoint[]>([]);
  
  // Use ref to avoid closure issues with async state
  const remainingAttractorsRef = useRef<AttractorPoint[]>([]);
  
  useEffect(() => {
    remainingAttractorsRef.current = remainingAttractors;
    console.log('[DEBUG] remainingAttractors state updated:', remainingAttractors.length, 'items');
    console.log('[DEBUG] ref now contains:', remainingAttractorsRef.current.length, 'items');
  }, [remainingAttractors]);

  useEffect(() => {
    if (scenes.length > 0 && !selectedId) {
      setSelectedId(scenes[0].id);
    }
  }, [scenes, selectedId]);

  const handleImageUpload = (file: File) => {
    const url = URL.createObjectURL(file);
    setTargetImage(url);
  };

  const handleGenerate = async () => {
    if (!targetImage) return;
    
    console.log('[DEBUG] handleGenerate called - starting fresh');
    setAppState(AppState.GENERATING);
    setActiveTab('generated');
    try {
      const imageData = await blobToBase64(targetImage);
      
      const targetShadows: TargetShadow[] = [
        {
          imageData,
          lightVector: { x: 0, y: 0, z: 1 },
        },
        {
          imageData,
          lightVector: { x: 1, y: 0, z: 0 },
        },
      ];

      const request: any = {
        count: 4,
        params: { treeCount, maxThickness: 0.5, branchingProb: 0.5, maxAngle: 0.5 } as GenerationParams,
        targetShadows,
        max_new_nodes: 200,
      };

      console.log('[DEBUG] Sending generate request (no parent_nodes - fresh start)');
      const response = await generateScenes(request);
      setScenes(response.scenes);
      setStats(response.stats);
      setGrowthComplete(response.stats.attractors_exhausted);
      setRemainingAttractors(response.stats.remaining_attractors_points || []);
      setGenerationNumber(0);
      
      if (response.scenes.length > 0) {
        setSelectedId(response.scenes[0].id);
        setGenerationNumber(response.scenes[0].generation);
      }
      
      console.log('[DEBUG] Generate complete, scenes:', response.scenes.length);
      console.log('[DEBUG] Remaining attractors (count):', response.stats.remaining_attractors);
      console.log('[DEBUG] Remaining attractors points (array length):', response.stats.remaining_attractors_points?.length);
      setAppState(AppState.IDLE);
    } catch (e) {
      console.error('[ERROR] handleGenerate failed:', e);
      setAppState(AppState.IDLE);
    }
  };

  const handleContinue = async () => {
    if (!targetImage || !selectedId) {
      console.log('[DEBUG] handleContinue skipped - no targetImage or selectedId');
      return;
    }
    
    const selectedScene = scenes.find(s => s.id === selectedId);
    if (!selectedScene) {
      console.log('[DEBUG] handleContinue skipped - no selectedScene found');
      return;
    }

    // CAPTURE PARENT NODES BEFORE ASYNC - prevents closure issues
    const parentNodesToSend = selectedScene.trees;
    const parentGeneration = selectedScene.generation;
    
    console.log('[DEBUG] handleContinue START');
    console.log('[DEBUG]   selected scene:', selectedScene.id);
    console.log('[DEBUG]   parent_nodes:', parentNodesToSend.length, 'nodes');
    console.log('[DEBUG]   generation:', parentGeneration);
    console.log('[DEBUG]   ref.current BEFORE request:', remainingAttractorsRef.current.length, 'attractors');
    
    setAppState(AppState.GENERATING);
    setActiveTab('generated');
    setIsDetailOpen(false);

    try {
      const imageData = await blobToBase64(targetImage);
      
      const targetShadows: TargetShadow[] = [
        {
          imageData,
          lightVector: { x: 0, y: 0, z: 1 },
        },
        {
          imageData,
          lightVector: { x: 1, y: 0, z: 0 },
        },
      ];

      const mutatedGenome = { ...currentGenome };
      mutatedGenome.random_seed = Math.floor(Math.random() * 100000);
      mutatedGenome.wiggle_factor = currentGenome.wiggle_factor * (0.8 + Math.random() * 0.4);
      setCurrentGenome(mutatedGenome);

      const request = {
        count: 4,
        params: { treeCount, maxThickness: 0.5, branchingProb: 0.5, maxAngle: 0.5 } as GenerationParams,
        targetShadows,
        parent_nodes: parentNodesToSend,
        parent_genome: mutatedGenome,
        parent_generation: parentGeneration,
        remaining_attractors: remainingAttractorsRef.current,
        max_new_nodes: 100,
        run_until_complete: false,
      };
      
      console.log('[DEBUG] Sending continue request');
      console.log('[DEBUG]   parent_nodes:', request.parent_nodes?.length || 0);
      console.log('[DEBUG]   parent_generation:', request.parent_generation);
      console.log('[DEBUG]   remaining_attractors (from ref):', request.remaining_attractors?.length || 0);

      const response = await generateScenes(request);

      setScenes(response.scenes);
      setStats(response.stats);
      setGrowthComplete(response.stats.attractors_exhausted);
      setRemainingAttractors(response.stats.remaining_attractors_points || []);
      
      if (response.scenes.length > 0) {
        setSelectedId(response.scenes[0].id);
        setGenerationNumber(response.scenes[0].generation);
      }
      
      console.log('[DEBUG] Continue COMPLETE');
      console.log('[DEBUG] New scenes:', response.scenes.length);
      console.log('[DEBUG] First scene:', response.scenes[0]?.id, '- nodes:', response.scenes[0]?.trees.length);
      console.log('[DEBUG] First scene generation:', response.scenes[0]?.generation);
      console.log('[DEBUG] Remaining attractors after:', response.stats.remaining_attractors);
      setAppState(AppState.IDLE);
    } catch (e) {
      console.error('[ERROR] handleContinue failed:', e);
      setAppState(AppState.IDLE);
    }
  };

  const handleFinish = async () => {
    if (!targetImage || !selectedId) return;
    
    const selectedScene = scenes.find(s => s.id === selectedId);
    if (!selectedScene) return;

    // CAPTURE PARENT NODES BEFORE ASYNC
    const parentNodesToSend = selectedScene.trees;
    const parentGeneration = selectedScene.generation;

    console.log('[DEBUG] handleFinish START');
    setAppState(AppState.GENERATING);
    setActiveTab('generated');
    setIsDetailOpen(false);

    try {
      const imageData = await blobToBase64(targetImage);
      
      const targetShadows: TargetShadow[] = [
        {
          imageData,
          lightVector: { x: 0, y: 0, z: 1 },
        },
        {
          imageData,
          lightVector: { x: 1, y: 0, z: 0 },
        },
      ];

      const mutatedGenome = { ...currentGenome };
      mutatedGenome.random_seed = Math.floor(Math.random() * 100000);
      mutatedGenome.wiggle_factor = currentGenome.wiggle_factor * (0.8 + Math.random() * 0.4);
      setCurrentGenome(mutatedGenome);

      const response = await generateScenes({
        count: 1,
        params: { treeCount, maxThickness: 0.5, branchingProb: 0.5, maxAngle: 0.5 } as GenerationParams,
        targetShadows,
        parent_nodes: parentNodesToSend,
        parent_genome: mutatedGenome,
        parent_generation: parentGeneration,
        remaining_attractors: remainingAttractorsRef.current,
        max_new_nodes: 500,
        run_until_complete: true,
      });

      setScenes(response.scenes);
      setStats(response.stats);
      setGrowthComplete(response.stats.attractors_exhausted);
      setRemainingAttractors(response.stats.remaining_attractors_points || []);
      
      if (response.scenes.length > 0) {
        setSelectedId(response.scenes[0].id);
        setGenerationNumber(response.scenes[0].generation);
      }
      
      console.log('[DEBUG] Finish COMPLETE, remaining attractors:', response.stats.remaining_attractors);
      setAppState(AppState.IDLE);
    } catch (e) {
      console.error('[ERROR] handleFinish failed:', e);
      setAppState(AppState.IDLE);
    }
  };

  const handleSelectScene = (scene: SceneData) => {
    setSelectedId(scene.id);
    setIsDetailOpen(true);
  };

  const handleSaveScene = (scene: SceneData) => {
    if (!savedScenes.find(s => s.id === scene.id)) {
        setSavedScenes([...savedScenes, scene]);
    }
  };

  const handleAbort = async () => {
    try {
      await abortGeneration();
    } catch (e) {
      console.error('Failed to abort:', e);
    }
  };

  const selectedScene = scenes.find(s => s.id === selectedId) || savedScenes.find(s => s.id === selectedId);

  return (
    <div className="flex w-full h-screen bg-slate-950 overflow-hidden font-sans">
      <div className="w-80 flex-shrink-0 z-20 shadow-xl">
        <ControlPanel
          onImageUpload={handleImageUpload}
          targetImage={targetImage}
          treeCount={treeCount}
          setTreeCount={setTreeCount}
          onGenerate={handleGenerate}
          onContinue={handleContinue}
          onFinish={handleFinish}
          onAbort={handleAbort}
          isGenerating={appState === AppState.GENERATING}
          hasScenes={scenes.length > 0}
          hasSelection={!!selectedId && !!selectedScene}
          generationNumber={generationNumber}
          growthComplete={growthComplete}
        />
      </div>

      <Gallery
        scenes={scenes}
        savedScenes={savedScenes}
        selectedId={selectedId}
        onSelect={handleSelectScene}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        stats={stats ?? undefined}
        targetImage={targetImage}
      />

      {isDetailOpen && selectedScene && (
        <DetailModal
          scene={selectedScene}
          onClose={() => setIsDetailOpen(false)}
          onSave={handleSaveScene}
          isSaved={!!savedScenes.find(s => s.id === selectedScene.id)}
          onEvolveThis={handleContinue}
        />
      )}
    </div>
  );
};

export default App;
