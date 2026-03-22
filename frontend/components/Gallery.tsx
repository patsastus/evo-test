import React, { useState } from 'react';
import { SceneData, GenerationStats } from '../types';
import { Scene3D } from './Scene3D';
import { Cuboid, CheckCircle2, Layers } from 'lucide-react';

interface GalleryProps {
  scenes: SceneData[];
  selectedId: string | null;
  onSelect: (scene: SceneData) => void;
  activeTab: 'generated' | 'saved';
  setActiveTab: (tab: 'generated' | 'saved') => void;
  savedScenes: SceneData[];
  stats?: GenerationStats;
  targetImage?: string | null;
}

export const Gallery: React.FC<GalleryProps> = ({ 
  scenes, 
  selectedId, 
  onSelect,
  activeTab,
  setActiveTab,
  savedScenes,
  stats,
  targetImage,
}) => {
  const displayScenes = activeTab === 'generated' ? scenes : savedScenes;
  const [overlayReference, setOverlayReference] = useState(false);

  const totalNodes = displayScenes.reduce((sum, scene) => sum + scene.trees.length, 0);
  const avgNodes = displayScenes.length > 0 ? Math.round(totalNodes / displayScenes.length) : 0;

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-slate-900">
      {/* Header with Stats */}
      <div className="flex items-center justify-between px-6 py-3 bg-slate-800/80 border-b border-slate-700">
        <div className="flex gap-6 text-xs font-mono text-slate-400">
          <span>Nodes: <span className="text-slate-200">{avgNodes}</span></span>
          {stats && (
            <>
              <span>Remaining: <span className="text-slate-200">{stats.remaining_attractors}</span></span>
              <span>Total: <span className="text-slate-200">{stats.total_attractors}</span></span>
            </>
          )}
        </div>
        
        <label className="flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={overlayReference}
            onChange={(e) => setOverlayReference(e.target.checked)}
            className="sr-only peer"
          />
          <div className="w-9 h-5 bg-slate-700 rounded-full peer peer-checked:bg-cyan-600 transition-colors relative">
            <div className="absolute w-4 h-4 bg-white rounded-full top-0.5 left-0.5 peer-checked:left-[18px] transition-all shadow" />
          </div>
          <span className="text-xs text-slate-300 flex items-center gap-1.5">
            <Layers size={14} />
            Overlay Reference
          </span>
        </label>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-700 bg-slate-800/50">
        <button
          onClick={() => setActiveTab('generated')}
          className={`px-6 py-4 text-sm font-medium transition-colors border-b-2 ${
            activeTab === 'generated' 
              ? 'border-blue-500 text-white' 
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Candidates ({scenes.length})
        </button>
        <button
          onClick={() => setActiveTab('saved')}
          className={`px-6 py-4 text-sm font-medium transition-colors border-b-2 ${
            activeTab === 'saved' 
              ? 'border-blue-500 text-white' 
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Saved Models ({savedScenes.length})
        </button>
      </div>

      {/* Grid */}
      <div className="flex-1 overflow-y-auto p-6">
        {displayScenes.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-500">
            <Cuboid size={48} className="mb-4 opacity-50" />
            <p className="text-lg">No scenes available.</p>
            <p className="text-sm">Use the control panel to generate some.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {displayScenes.map((scene) => (
              <div 
                key={scene.id}
                onClick={() => onSelect(scene)}
                className={`group flex flex-col rounded-xl overflow-hidden cursor-pointer transition-all border-2 bg-slate-800 ${
                  selectedId === scene.id 
                    ? 'border-blue-500 ring-2 ring-blue-500/20' 
                    : 'border-slate-700 hover:border-slate-500'
                }`}
              >
                {/* Visuals Row */}
                <div className="flex h-64 border-b border-slate-700">
                    {/* 3D View */}
                    <div className="flex-1 border-r border-slate-700 relative">
                        <div className="absolute top-2 left-2 z-10 bg-black/50 px-2 py-0.5 rounded text-[10px] text-slate-300 font-mono">
                            3D VIEW
                        </div>
                        <Scene3D data={scene} />
                    </div>
                    {/* Shadow View */}
                    <div className="flex-1 relative bg-slate-100 flex items-center justify-center overflow-hidden">
                        <div className="absolute top-2 left-2 z-10 bg-black/50 px-2 py-0.5 rounded text-[10px] text-slate-300 font-bold font-mono">
                            SHADOW
                        </div>
                        {scene.shadowImageUrl ? (
                          <div className="relative w-full h-full">
                            <img 
                              src={scene.shadowImageUrl} 
                              alt="Projected Shadow" 
                              className="w-full h-full object-contain p-2"
                            />
                            {overlayReference && targetImage && (
                              <img
                                src={targetImage}
                                alt="Reference Overlay"
                                className="absolute inset-0 w-full h-full object-contain p-2 opacity-30 mix-blend-color"
                                style={{ mixBlendMode: 'multiply' }}
                              />
                            )}
                          </div>
                        ) : (
                          <div className="text-slate-300 text-xs">No Shadow Data</div>
                        )}
                    </div>
                </div>
                
                {/* Info Footer */}
                <div className="p-3 bg-slate-800 flex justify-between items-center">
                  <div>
                      <div className="flex gap-4 text-xs font-mono text-slate-400">
                          <span>GEN: {scene.generation}</span>
                          <span>Printability: {(scene.fitness.printability * 100).toFixed(0)}%</span>
                          <span>Match: {(scene.fitness.shadowMatch * 100).toFixed(0)}%</span>
                          <span>Nodes: {scene.trees.length}</span>
                      </div>
                  </div>
                  {selectedId === scene.id && (
                      <CheckCircle2 className="text-blue-500" size={20} />
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
