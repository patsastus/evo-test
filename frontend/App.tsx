import React, { useState } from 'react';
import { ControlPanel } from './components/ControlPanel';
import { Gallery } from './components/Gallery';
import { DetailModal } from './components/DetailModal';
import { SceneData, GenerationParams, GeneticParams, AppState, TargetShadow } from './types';
import { generateInitialScenes, evolveScenes } from './services/api';

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

const App: React.FC = () => {
  // State
  const [targetImage, setTargetImage] = useState<string | null>(null);
  const [scenes, setScenes] = useState<SceneData[]>([]);
  const [savedScenes, setSavedScenes] = useState<SceneData[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [appState, setAppState] = useState<AppState>(AppState.IDLE);
  const [activeTab, setActiveTab] = useState<'generated' | 'saved'>('generated');
  const [isDetailOpen, setIsDetailOpen] = useState(false);

  // Parameters
  const [genParams, setGenParams] = useState<GenerationParams>({
    treeCount: 5,
    maxThickness: 0.3,
    branchingProb: 0.7,
    maxAngle: 0.8
  });

  const [geneticParams, setGeneticParams] = useState<GeneticParams>({
    generations: 10,
    mutationRate: 0.2,
    populationSize: 8
  });

  const handleImageUpload = (file: File) => {
    const url = URL.createObjectURL(file);
    setTargetImage(url);
  };

  const handleCreateInitial = async () => {
    if (!targetImage) return;
    
    setAppState(AppState.GENERATING);
    setActiveTab('generated');
    try {
      const imageData = await blobToBase64(targetImage);
      
      const targetShadows: TargetShadow[] = [
        {
          imageData,
          lightVector: { x: 1, y: 0, z: 2 },
        },
        {
          imageData,
          lightVector: { x: -2, y: 0, z: -1 },
        },
      ];
      const newScenes = await generateInitialScenes(1, genParams, targetShadows);
      setScenes(newScenes);
      setAppState(AppState.IDLE);
    } catch (e) {
      console.error(e);
      setAppState(AppState.IDLE);
    }
  };

  const handleEvolve = async () => {
    const parent = scenes.find(s => s.id === selectedId) || savedScenes.find(s => s.id === selectedId);
    if (!parent) return;

    setAppState(AppState.GENERATING);
    setActiveTab('generated');
    setIsDetailOpen(false); // Close modal if evolving from there

    try {
      const offspring = await evolveScenes(parent, geneticParams);
      setScenes(offspring); // Replace current candidates with new generation
      setAppState(AppState.IDLE);
    } catch (e) {
      console.error(e);
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

  const selectedScene = scenes.find(s => s.id === selectedId) || savedScenes.find(s => s.id === selectedId);

  return (
    <div className="flex w-full h-screen bg-slate-950 overflow-hidden font-sans">
      {/* Sidebar Controls */}
      <div className="w-80 flex-shrink-0 z-20 shadow-xl">
        <ControlPanel
          onImageUpload={handleImageUpload}
          targetImage={targetImage}
          genParams={genParams}
          setGenParams={setGenParams}
          geneticParams={geneticParams}
          setGeneticParams={setGeneticParams}
          onCreateInitial={handleCreateInitial}
          onEvolve={handleEvolve}
          isGenerating={appState === AppState.GENERATING}
          hasSelection={!!selectedId}
        />
      </div>

      {/* Main Content Area */}
      <Gallery
        scenes={scenes}
        savedScenes={savedScenes}
        selectedId={selectedId}
        onSelect={handleSelectScene}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
      />

      {/* Detail Modal */}
      {isDetailOpen && selectedScene && (
        <DetailModal
          scene={selectedScene}
          onClose={() => setIsDetailOpen(false)}
          onSave={handleSaveScene}
          isSaved={!!savedScenes.find(s => s.id === selectedScene.id)}
          onEvolveThis={handleEvolve}
        />
      )}
    </div>
  );
};

export default App;