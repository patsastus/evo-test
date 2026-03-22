import React, { useRef } from 'react';
import { Upload, Play, SkipForward, Flag, Square } from 'lucide-react';
import { GenerationParams } from '../types';

interface ControlPanelProps {
  onImageUpload: (file: File) => void;
  targetImage: string | null;
  treeCount: number;
  setTreeCount: (count: number) => void;
  onGenerate: () => void;
  onContinue: () => void;
  onFinish: () => void;
  onAbort: () => void;
  isGenerating: boolean;
  hasScenes: boolean;
  hasSelection: boolean;
  generationNumber: number;
  growthComplete: boolean;
}

export const ControlPanel: React.FC<ControlPanelProps> = ({
  onImageUpload,
  targetImage,
  treeCount,
  setTreeCount,
  onGenerate,
  onContinue,
  onFinish,
  onAbort,
  isGenerating,
  hasScenes,
  hasSelection,
  generationNumber,
  growthComplete,
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
        <p className="text-slate-400 text-sm">Interactive tree growth system.</p>
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

      {/* Tree Count */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <label className="text-sm font-semibold text-slate-300 flex items-center gap-2">
            <Play size={16} /> Tree Count
          </label>
          <span className="text-lg font-mono text-white">{treeCount}</span>
        </div>
        
        <input 
          type="range" 
          min="1" 
          max="10" 
          step="1"
          value={treeCount}
          onChange={(e) => setTreeCount(parseInt(e.target.value))}
          className="w-full accent-blue-500 h-2 bg-slate-600 rounded-lg appearance-none cursor-pointer"
        />
      </div>

      {/* Generation Buttons */}
      <div className="space-y-3 mt-auto">
        <button
          onClick={onGenerate}
          disabled={isGenerating || !targetImage}
          className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-600 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors shadow-lg shadow-blue-900/20 flex items-center justify-center gap-2"
        >
          {isGenerating ? (
            'Generating...'
          ) : hasScenes ? (
            <>
              <Play size={18} /> Regenerate ({generationNumber})
            </>
          ) : (
            <>
              <Play size={18} /> Generate Scenes
            </>
          )}
        </button>

        <button
          onClick={onContinue}
          disabled={isGenerating || !hasSelection || growthComplete}
          className={`w-full py-3 rounded-lg text-sm font-medium transition-colors shadow-lg flex items-center justify-center gap-2 ${
            !hasSelection || isGenerating || growthComplete
              ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
              : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-900/20'
          }`}
        >
          <SkipForward size={18} /> 
          {growthComplete 
            ? 'Growth Complete' 
            : !hasSelection 
              ? 'Select a scene first' 
              : 'Continue Generation'}
        </button>

        <button
          onClick={onFinish}
          disabled={isGenerating || !hasScenes || growthComplete}
          className={`w-full py-3 rounded-lg text-sm font-medium transition-colors shadow-lg flex items-center justify-center gap-2 ${
            !hasScenes || isGenerating || growthComplete
              ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
              : 'bg-amber-600 hover:bg-amber-500 text-white shadow-amber-900/20'
          }`}
        >
          <Flag size={18} /> 
          Finish Generation
        </button>

        {isGenerating && (
          <button
            onClick={onAbort}
            className="w-full py-3 bg-red-600 hover:bg-red-500 text-white rounded-lg text-sm font-medium transition-colors shadow-lg shadow-red-900/20 flex items-center justify-center gap-2"
          >
            <Square size={18} /> 
            Abort
          </button>
        )}

        {hasScenes && !hasSelection && !growthComplete && (
          <p className="text-xs text-slate-500 text-center">Select a scene to continue growth</p>
        )}

        {growthComplete && hasScenes && (
          <p className="text-xs text-amber-500 text-center">All attractors exhausted</p>
        )}
      </div>
    </div>
  );
};
