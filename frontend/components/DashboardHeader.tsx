import React from 'react';
import { Cpu, Activity, Zap } from 'lucide-react';

export const DashboardHeader: React.FC = () => {
  return (
    <header className="flex flex-col md:flex-row justify-between items-start md:items-center pb-8 border-b border-white/5 mb-8">
      <div className="flex items-center gap-4">
        <div className="relative group">
          <div className="absolute -inset-1 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-lg blur opacity-25 group-hover:opacity-75 transition duration-1000 group-hover:duration-200"></div>
          <div className="relative p-3 bg-zinc-900 ring-1 ring-white/10 rounded-lg">
            <Cpu className="w-8 h-8 text-cyan-400" />
          </div>
        </div>
        <div>
          <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-zinc-500">
            AlphaTrade AI
          </h1>
          <div className="flex items-center gap-2 mt-1">
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="text-xs font-mono text-emerald-400 tracking-wider">SYSTEM ONLINE • T+1 STRATEGY</span>
          </div>
        </div>
      </div>
      
      <div className="mt-4 md:mt-0 flex gap-3">
        <div className="px-4 py-2 rounded-full bg-white/5 border border-white/10 backdrop-blur-sm flex items-center gap-2 text-sm text-zinc-400">
          <Activity size={14} />
          <span>CatBoost Model v2.1</span>
        </div>
        <div className="px-4 py-2 rounded-full bg-indigo-500/10 border border-indigo-500/20 backdrop-blur-sm flex items-center gap-2 text-sm text-indigo-400">
          <Zap size={14} />
          <span>Max 5 Pos</span>
        </div>
      </div>
    </header>
  );
};
