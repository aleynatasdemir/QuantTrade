import React from 'react';
import { ArrowRight, Clock, Target } from 'lucide-react';
import { PendingBuy } from '../types';

interface PendingOrdersProps {
  orders: PendingBuy[];
}

export const PendingOrders: React.FC<PendingOrdersProps> = ({ orders }) => {
  if (orders.length === 0) return null;

  return (
    <div className="bg-zinc-900 border border-white/5 rounded-2xl p-6 h-full">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-zinc-100 flex items-center gap-2">
          <Target className="text-emerald-500" size={20} />
          Generated Signals (Buy)
        </h3>
        <span className="text-xs font-mono text-zinc-500 bg-zinc-800 px-2 py-1 rounded">
          {orders[0]?.decision_date}
        </span>
      </div>

      <div className="space-y-3">
        {orders.map((order, idx) => (
          <div 
            key={order.symbol} 
            className="group relative overflow-hidden bg-zinc-950/50 border border-white/5 hover:border-emerald-500/30 rounded-xl p-4 transition-all duration-300 hover:bg-zinc-900"
            style={{ animationDelay: `${idx * 100}ms` }}
          >
            {/* Hover Gradient Effect */}
            <div className="absolute inset-0 bg-gradient-to-r from-emerald-500/0 via-emerald-500/0 to-emerald-500/0 group-hover:via-emerald-500/5 transition-all duration-500" />
            
            <div className="flex items-center justify-between relative z-10">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-lg bg-zinc-800 flex items-center justify-center border border-white/5 group-hover:border-emerald-500/20 text-emerald-400 font-bold tracking-wider">
                  {order.symbol.substring(0, 2)}
                </div>
                <div>
                  <h4 className="font-bold text-lg tracking-tight group-hover:text-emerald-400 transition-colors">
                    {order.symbol}
                  </h4>
                  <div className="flex items-center gap-2 text-xs text-zinc-500 font-mono">
                     <span className="w-2 h-2 rounded-full bg-emerald-500/50 animate-pulse"></span>
                     SIGNAL: BUY
                  </div>
                </div>
              </div>

              <div className="text-right">
                <p className="text-sm text-zinc-400 mb-1">Planned Allocation</p>
                <p className="font-mono text-lg font-medium text-white">
                  ₺{order.planned_capital.toLocaleString()}
                </p>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between text-xs text-zinc-500 font-mono">
              <span className="flex items-center gap-1">
                <Clock size={12} />
                EXECUTE AT OPEN
              </span>
              <div className="flex items-center gap-1 group-hover:translate-x-1 transition-transform text-emerald-600 group-hover:text-emerald-400 cursor-pointer">
                DETAILS <ArrowRight size={12} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
