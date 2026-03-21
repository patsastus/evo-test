import React, { useRef } from 'react';
import { Upload, Sliders, Activity, Save } from 'lucide-react';
import { GenerationParams, GeneticParams } from '../types';

interface ControlPanelProps {
  onImageUpload: (file: File) => void;
  targetImage: string | null;
  genParams: GenerationParams;
  setGenParams: (p: GenerationParams) => void;
  geneticParams: GeneticParams;
  setGeneticParams: (p: GeneticParams) => void;
  onCreateInitial: () => void;
  onEvolve: () => void;
  isGenerating: boolean;
  hasSelection: boolean;
}

export const ControlPanel: React.FC<ControlPanelProps> = ({
  onImageUpload,
  targetImage,
  genParams,
  setGenParams,
  geneticParams,
  setGeneticParams,
  onCreateInitial,
  onEvolve,
  isGenerating,
  hasSelection
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      onImageUpload(e.target.files[0]);
    }
  };

  return (
    <div className="w-full h-full flex flex-col gap-6 p-6 bg-slate-800 border-r border-slate-700 overflow-y-auto">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold text-white tracking-tight">Shadow Evolution</h1>
        <p className="text-slate-400 text-sm">Design 3D printable shadow casters.</p>
      </div>

      {/* Target Image Upload */}
      <div className="space-y-3">
        <label className="text-sm font-semibold text-slate-300 flex items-center gap-2">
          <Upload size={16} /> Target Shadow
        </label>
        <div 
          onClick={() => fileInputRef.current?.click()}
          className="border-2 border-dashed border-slate-600 rounded-lg p-4 cursor-pointer hover:border-blue-500 hover:bg-slate-700/50 transition-colors flex flex-col items-center justify-center min-h-[160px]"
        >
          {targetImage ? (
            <img src={targetImage} alt="Target" className="max-h-32 object-contain" />
          ) : (
            <div className="text-center text-slate-500">
              <p className="text-sm">Click to upload image</p>
              <p className="text-xs mt-1">PNG, JPG</p>
            </div>
          )}
          <input 
            type="file" 
            ref={fileInputRef} 
            onChange={handleFileChange} 
            className="hidden" 
            accept="image/*"
          />
        </div>
      </div>

      <hr className="border-slate-700" />

      {/* Initial Generation Params */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <label className="text-sm font-semibold text-slate-300 flex items-center gap-2">
            <Sliders size={16} /> Scene Parameters
          </label>
        </div>
        
        <div className="space-y-3">
          <div>
            <div className="flex justify-between text-xs text-slate-400 mb-1">
              <span>Tree Count</span>
              <span>{genParams.treeCount}</span>
            </div>
            <input 
              type="range" min="1" max="20" step="1"
              value={genParams.treeCount}
              onChange={(e) => setGenParams({...genParams, treeCount: parseInt(e.target.value)})}
              className="w-full accent-blue-500 h-1 bg-slate-600 rounded-lg appearance-none cursor-pointer"
            />
          </div>
          
          <div>
            <div className="flex justify-between text-xs text-slate-400 mb-1">
              <span>Max Thickness</span>
              <span>{genParams.maxThickness.toFixed(2)}</span>
            </div>
            <input 
              type="range" min="0.1" max="1.0" step="0.05"
              value={genParams.maxThickness}
              onChange={(e) => setGenParams({...genParams, maxThickness: parseFloat(e.target.value)})}
              className="w-full accent-blue-500 h-1 bg-slate-600 rounded-lg appearance-none cursor-pointer"
            />
          </div>

          <div>
            <div className="flex justify-between text-xs text-slate-400 mb-1">
              <span>Branching Prob</span>
              <span>{(genParams.branchingProb * 100).toFixed(0)}%</span>
            </div>
            <input 
              type="range" min="0" max="1" step="0.05"
              value={genParams.branchingProb}
              onChange={(e) => setGenParams({...genParams, branchingProb: parseFloat(e.target.value)})}
              className="w-full accent-blue-500 h-1 bg-slate-600 rounded-lg appearance-none cursor-pointer"
            />
          </div>
        </div>

        <button
          onClick={onCreateInitial}
          disabled={isGenerating}
          className="w-full py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-600 disabled:cursor-not-allowed text-white rounded-md text-sm font-medium transition-colors shadow-lg shadow-blue-900/20"
        >
          {isGenerating ? 'Generating...' : 'Create Initial Scenes'}
        </button>
      </div>

      <hr className="border-slate-700" />

      {/* Genetic Algorithm Params */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <label className="text-sm font-semibold text-slate-300 flex items-center gap-2">
            <Activity size={16} /> Evolution Params
          </label>
        </div>

        <div className="space-y-3">
          <div>
            <div className="flex justify-between text-xs text-slate-400 mb-1">
              <span>Population Size</span>
              <span>{geneticParams.populationSize}</span>
            </div>
            <input 
              type="range" min="4" max="20" step="1"
              value={geneticParams.populationSize}
              onChange={(e) => setGeneticParams({...geneticParams, populationSize: parseInt(e.target.value)})}
              className="w-full accent-purple-500 h-1 bg-slate-600 rounded-lg appearance-none cursor-pointer"
            />
          </div>

          <div>
            <div className="flex justify-between text-xs text-slate-400 mb-1">
              <span>Generations</span>
              <span>{geneticParams.generations}</span>
            </div>
            <input 
              type="range" min="1" max="50" step="1"
              value={geneticParams.generations}
              onChange={(e) => setGeneticParams({...geneticParams, generations: parseInt(e.target.value)})}
              className="w-full accent-purple-500 h-1 bg-slate-600 rounded-lg appearance-none cursor-pointer"
            />
          </div>

          <div>
            <div className="flex justify-between text-xs text-slate-400 mb-1">
              <span>Mutation Rate</span>
              <span>{(geneticParams.mutationRate * 100).toFixed(0)}%</span>
            </div>
            <input 
              type="range" min="0" max="1" step="0.01"
              value={geneticParams.mutationRate}
              onChange={(e) => setGeneticParams({...geneticParams, mutationRate: parseFloat(e.target.value)})}
              className="w-full accent-purple-500 h-1 bg-slate-600 rounded-lg appearance-none cursor-pointer"
            />
          </div>
        </div>

        <button
          onClick={onEvolve}
          disabled={!hasSelection || isGenerating}
          className={`w-full py-2 rounded-md text-sm font-medium transition-colors shadow-lg ${
            !hasSelection 
                ? 'bg-slate-700 text-slate-500 cursor-not-allowed' 
                : 'bg-purple-600 hover:bg-purple-500 text-white shadow-purple-900/20'
          }`}
        >
          {isGenerating ? 'Evolving...' : 'Evolve Selection'}
        </button>
        {!hasSelection && (
            <p className="text-xs text-slate-500 text-center">Select a scene to evolve from.</p>
        )}
      </div>
    </div>
  );
};