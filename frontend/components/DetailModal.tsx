import React, { useState } from 'react';
import { X, Save, Download, Printer, Play } from 'lucide-react';
import { SceneData } from '../types';
import { Scene3D } from './Scene3D';
import { exportToOBJ } from '../services/api';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

interface DetailModalProps {
  scene: SceneData;
  onClose: () => void;
  onSave: (scene: SceneData) => void;
  isSaved: boolean;
  onEvolveThis: () => void;
}

export const DetailModal: React.FC<DetailModalProps> = ({ scene, onClose, onSave, isSaved, onEvolveThis }) => {
  const [activeView, setActiveView] = useState<'model' | 'shadow'>('model');

  const handleDownload = async () => {
    try {
      const objContent = await exportToOBJ(scene);
      const blob = new Blob([objContent], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `shadow-sculpture-${scene.id}.obj`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error('Failed to export OBJ:', e);
    }
  };

  const chartData = [
    { name: 'Printability', score: scene.fitness.printability * 100 },
    { name: 'Shadow Match', score: scene.fitness.shadowMatch * 100 },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 md:p-8">
      <div className="bg-slate-900 w-full max-w-6xl h-[90vh] rounded-2xl border border-slate-700 shadow-2xl flex flex-col md:flex-row overflow-hidden">
        
        {/* Left Side: Visualization */}
        <div className="flex-1 flex flex-col min-h-[50%] md:min-h-full border-b md:border-b-0 md:border-r border-slate-700 relative">
            {/* View Toggles */}
            <div className="absolute top-4 left-4 z-10 flex gap-2">
                <button 
                    onClick={() => setActiveView('model')}
                    className={`px-3 py-1.5 rounded-full text-xs font-semibold backdrop-blur-md transition-colors ${
                        activeView === 'model' ? 'bg-white/10 text-white border border-white/20' : 'bg-black/20 text-slate-400 hover:bg-black/40'
                    }`}
                >
                    3D Model
                </button>
                <button 
                    onClick={() => setActiveView('shadow')}
                    className={`px-3 py-1.5 rounded-full text-xs font-semibold backdrop-blur-md transition-colors ${
                        activeView === 'shadow' ? 'bg-white/10 text-white border border-white/20' : 'bg-black/20 text-slate-400 hover:bg-black/40'
                    }`}
                >
                    Projected Shadow
                </button>
            </div>

            <div className="flex-1 bg-slate-950">
                {activeView === 'model' ? (
                    <Scene3D data={scene} />
                ) : (
                    <div className="w-full h-full flex items-center justify-center bg-white">
                         {scene.shadowImageUrl ? (
                             <img 
                                src={scene.shadowImageUrl} 
                                alt="Raytraced Shadow" 
                                className="w-full h-full object-contain p-8"
                             />
                         ) : (
                             <div className="text-slate-900 font-bold opacity-20 text-xl">Shadow Generating...</div>
                         )}
                    </div>
                )}
            </div>
        </div>

        {/* Right Side: Details & Actions */}
        <div className="w-full md:w-[400px] flex flex-col bg-slate-800">
          <div className="p-6 border-b border-slate-700 flex justify-between items-start">
            <div>
                <h2 className="text-2xl font-bold text-white">Scene Details</h2>
                <p className="text-slate-400 text-sm font-mono mt-1">ID: {scene.id}</p>
                <p className="text-slate-400 text-sm font-mono">Generation: {scene.generation}</p>
            </div>
            <button onClick={onClose} className="p-2 hover:bg-slate-700 rounded-full text-slate-400 hover:text-white transition-colors">
              <X size={24} />
            </button>
          </div>

          <div className="p-6 flex-1 overflow-y-auto space-y-8">
            {/* Metrics Chart */}
            <div className="space-y-2">
                <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Fitness Analysis</h3>
                <div className="h-48 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={chartData} layout="vertical" margin={{ left: 20 }}>
                            <XAxis type="number" domain={[0, 100]} hide />
                            <YAxis type="category" dataKey="name" stroke="#94a3b8" fontSize={12} width={100} />
                            <Tooltip 
                                contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#f8fafc' }}
                                cursor={{ fill: '#334155', opacity: 0.2 }}
                            />
                            <Bar dataKey="score" fill="#3b82f6" radius={[0, 4, 4, 0]} barSize={20} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-2 gap-4">
                <div className="bg-slate-700/50 p-3 rounded-lg">
                    <div className="text-xs text-slate-400">Trees</div>
                    <div className="text-lg font-bold text-white">{scene.trees.filter(t => !t.parentId).length}</div>
                </div>
                <div className="bg-slate-700/50 p-3 rounded-lg">
                    <div className="text-xs text-slate-400">Total Segments</div>
                    <div className="text-lg font-bold text-white">{scene.trees.length}</div>
                </div>
            </div>
          </div>

          <div className="p-6 bg-slate-900 border-t border-slate-700 space-y-3">
            <button 
                onClick={() => onSave(scene)}
                disabled={isSaved}
                className={`w-full flex items-center justify-center gap-2 py-3 rounded-lg font-medium transition-all ${
                    isSaved 
                        ? 'bg-green-600/20 text-green-400 cursor-default'
                        : 'bg-slate-700 hover:bg-slate-600 text-white'
                }`}
            >
                {isSaved ? <><CheckCircle2 size={18}/> Saved to Library</> : <><Save size={18}/> Save to Library</>}
            </button>
            
            <button 
                onClick={handleDownload}
                className="w-full flex items-center justify-center gap-2 py-3 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium transition-colors"
            >
                <Download size={18} /> Export .OBJ for Printing
            </button>

            <button 
                onClick={onEvolveThis}
                className="w-full flex items-center justify-center gap-2 py-3 bg-purple-600 hover:bg-purple-500 text-white rounded-lg font-medium transition-colors shadow-lg shadow-purple-900/20"
            >
                <Play size={18} /> Evolve from this Scene
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
import { CheckCircle2 } from 'lucide-react';