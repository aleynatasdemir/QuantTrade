import React from 'react';
import { Wallet, TrendingUp, Briefcase, Layers } from 'lucide-react';
import { PortfolioState } from '../types';

interface StatsGridProps {
  data: PortfolioState;
}

export const StatsGrid: React.FC<StatsGridProps> = ({ data }) => {
  // Calculate total equity (Cash + Value of positions)
  // Use current_price if available, otherwise use avg_price
  const positionValue = data.positions.reduce((acc, pos) => {
    const price = pos.current_price || pos.avg_price;
    return acc + (pos.shares * price);
  }, 0);
  const totalEquity = data.cash + positionValue;

  // Calculate total profit/loss
  const totalCost = data.positions.reduce((acc, pos) => {
    return acc + (pos.shares * pos.avg_price);
  }, 0);
  const totalProfit = positionValue - totalCost;
  const totalProfitPct = totalCost > 0 ? (totalProfit / totalCost) * 100 : 0;

  const stats = [
    {
      label: 'Total Equity',
      value: `₺${totalEquity.toLocaleString(undefined, { minimumFractionDigits: 2 })}`,
      change: totalProfit >= 0
        ? `+₺${totalProfit.toLocaleString(undefined, { maximumFractionDigits: 0 })} (+${totalProfitPct.toFixed(2)}%)`
        : `₺${totalProfit.toLocaleString(undefined, { maximumFractionDigits: 0 })} (${totalProfitPct.toFixed(2)}%)`,
      icon: Wallet,
      trend: totalProfit >= 0 ? 'up' : 'down',
      color: 'text-white'
    },
    {
      label: 'Available Cash',
      value: `₺${data.cash.toLocaleString(undefined, { minimumFractionDigits: 2 })}`,
      change: '100% of Portfolio',
      icon: Layers,
      trend: 'neutral',
      color: 'text-cyan-400'
    },
    {
      label: 'Active Positions',
      value: data.positions.length.toString(),
      change: `${data.positions.length < 5 ? 'Accumulating' : 'Max Allocation'}`,
      icon: Briefcase,
      trend: 'neutral',
      color: 'text-purple-400'
    },
    {
      label: 'Pending Signals',
      value: data.pending_buys.length.toString(),
      change: 'Action Required Tomorrow',
      icon: TrendingUp,
      trend: 'up',
      color: 'text-emerald-400'
    }
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
      {stats.map((stat, index) => (
        <div
          key={index}
          className="relative overflow-hidden bg-zinc-900 border border-white/5 rounded-2xl p-6 group hover:border-white/10 transition-all duration-300"
        >
          <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
            <stat.icon size={64} />
          </div>

          <div className="flex items-center gap-3 mb-4">
            <div className={`p-2 rounded-lg bg-white/5 ${stat.color}`}>
              <stat.icon size={20} />
            </div>
            <span className="text-sm font-medium text-zinc-400">{stat.label}</span>
          </div>

          <div className="relative z-10">
            <h3 className="text-2xl font-bold font-mono tracking-tight mb-1">{stat.value}</h3>
            <div className={`text-xs font-medium flex items-center gap-1 ${stat.trend === 'up' ? 'text-emerald-500' :
              stat.trend === 'down' ? 'text-rose-500' : 'text-zinc-500'
              }`}>
              {stat.change}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};
