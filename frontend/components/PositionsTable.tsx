import React from 'react';
import { TrendingUp, TrendingDown, DollarSign } from 'lucide-react';

interface Position {
    symbol: string;
    shares: number;
    avg_price: number;
    current_price: number;
}

interface PositionsTableProps {
    positions: Position[];
}

export const PositionsTable: React.FC<PositionsTableProps> = ({ positions }) => {
    if (!positions || positions.length === 0) {
        return (
            <div className="bg-zinc-900 border border-white/5 rounded-2xl p-8 text-center">
                <p className="text-zinc-500">Aktif pozisyon yok</p>
            </div>
        );
    }

    return (
        <div className="bg-zinc-900 border border-white/5 rounded-2xl overflow-hidden">
            {/* Header */}
            <div className="p-4 border-b border-white/5 bg-zinc-950/50">
                <h3 className="font-bold text-lg text-zinc-100 flex items-center gap-2">
                    <DollarSign className="text-emerald-500" size={20} />
                    Aktif Pozisyonlar
                </h3>
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
                <table className="w-full">
                    <thead className="bg-zinc-950/30 border-b border-white/5">
                        <tr>
                            <th className="text-left p-4 text-xs font-semibold text-zinc-400 uppercase">Sembol</th>
                            <th className="text-right p-4 text-xs font-semibold text-zinc-400 uppercase">Lot</th>
                            <th className="text-right p-4 text-xs font-semibold text-zinc-400 uppercase">Alış ₺</th>
                            <th className="text-right p-4 text-xs font-semibold text-zinc-400 uppercase">Güncel ₺</th>
                            <th className="text-right p-4 text-xs font-semibold text-zinc-400 uppercase">Değer</th>
                            <th className="text-right p-4 text-xs font-semibold text-zinc-400 uppercase">Kar/Zarar</th>
                            <th className="text-right p-4 text-xs font-semibold text-zinc-400 uppercase">Getiri %</th>
                        </tr>
                    </thead>
                    <tbody>
                        {positions.map((pos, idx) => {
                            // Safety checks for undefined values
                            const avgPrice = pos.avg_price || 0;
                            const currentPrice = pos.current_price || avgPrice || 0;
                            const shares = pos.shares || 0;

                            const currentValue = shares * currentPrice;
                            const costBasis = shares * avgPrice;
                            const profitLoss = currentValue - costBasis;
                            const returnPct = avgPrice > 0 ? ((currentPrice - avgPrice) / avgPrice) * 100 : 0;
                            const isProfit = profitLoss >= 0;

                            return (
                                <tr
                                    key={idx}
                                    className="border-b border-white/5 hover:bg-white/[0.02] transition-colors"
                                >
                                    <td className="p-4">
                                        <span className="font-bold text-zinc-100">{pos.symbol || 'N/A'}</span>
                                    </td>
                                    <td className="p-4 text-right text-zinc-300 font-mono">
                                        {shares.toLocaleString()}
                                    </td>
                                    <td className="p-4 text-right text-zinc-400 font-mono">
                                        ₺{avgPrice.toFixed(2)}
                                    </td>
                                    <td className="p-4 text-right text-zinc-100 font-mono font-semibold">
                                        ₺{currentPrice.toFixed(2)}
                                    </td>
                                    <td className="p-4 text-right text-zinc-300 font-mono">
                                        ₺{currentValue.toLocaleString('tr-TR', { maximumFractionDigits: 0 })}
                                    </td>
                                    <td className={`p-4 text-right font-mono font-semibold ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
                                        {isProfit ? '+' : ''}₺{profitLoss.toLocaleString('tr-TR', { maximumFractionDigits: 0 })}
                                    </td>
                                    <td className="p-4 text-right">
                                        <div className={`inline-flex items-center gap-1 px-3 py-1 rounded-full font-semibold ${isProfit
                                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                            : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                                            }`}>
                                            {isProfit ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                                            {isProfit ? '+' : ''}{returnPct.toFixed(2)}%
                                        </div>
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                    <tfoot className="bg-zinc-950/30">
                        <tr className="border-t-2 border-white/10">
                            <td colSpan={4} className="p-4 text-right font-bold text-zinc-300">
                                TOPLAM:
                            </td>
                            <td className="p-4 text-right font-bold text-zinc-100 font-mono">
                                ₺{positions.reduce((sum, pos) => sum + (pos.shares * pos.current_price), 0).toLocaleString('tr-TR', { maximumFractionDigits: 0 })}
                            </td>
                            <td className={`p-4 text-right font-bold font-mono ${positions.reduce((sum, pos) => sum + ((pos.shares * pos.current_price) - (pos.shares * pos.avg_price)), 0) >= 0
                                ? 'text-emerald-400'
                                : 'text-rose-400'
                                }`}>
                                {positions.reduce((sum, pos) => sum + ((pos.shares * pos.current_price) - (pos.shares * pos.avg_price)), 0) >= 0 ? '+' : ''}
                                ₺{positions.reduce((sum, pos) => sum + ((pos.shares * pos.current_price) - (pos.shares * pos.avg_price)), 0).toLocaleString('tr-TR', { maximumFractionDigits: 0 })}
                            </td>
                            <td></td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        </div>
    );
};
