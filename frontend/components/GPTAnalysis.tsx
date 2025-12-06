import React, { useEffect, useState } from 'react';
import { gptAPI } from '../services/api';
import { Brain, Calendar, Clock, TrendingUp, AlertTriangle, CheckCircle, X, Maximize2 } from 'lucide-react';

interface GPTAnalysisData {
    timestamp: string;
    as_of_date: string;
    analysis: string;
    snapshot_ref: string;
}

export const GPTAnalysis: React.FC = () => {
    const [analysis, setAnalysis] = useState<GPTAnalysisData | null>(null);
    const [loading, setLoading] = useState(true);
    const [available, setAvailable] = useState(false);
    const [showModal, setShowModal] = useState(false);

    const fetchAnalysis = async () => {
        try {
            const data = await gptAPI.getAnalysis();
            setAvailable(data.available);
            if (data.available) {
                setAnalysis(data.data);
            }
        } catch (error) {
            console.error('Error fetching GPT analysis:', error);
            setAvailable(false);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchAnalysis();

        // Auto-refresh every 5 minutes
        const interval = setInterval(fetchAnalysis, 5 * 60 * 1000);
        return () => clearInterval(interval);
    }, []);

    const formatTimestamp = (isoString: string) => {
        try {
            const date = new Date(isoString);
            return date.toLocaleString('tr-TR', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch {
            return isoString;
        }
    };

    // Parse analysis to extract sections
    const formatAnalysis = (text: string) => {
        const sections = text.split('\n\n');
        return sections.map((section, idx) => {
            const hasRisk = section.toLowerCase().includes('risk') ||
                section.toLowerCase().includes('uyarı') ||
                section.toLowerCase().includes('warning');
            const hasSuccess = section.toLowerCase().includes('kalite') ||
                section.toLowerCase().includes('quality') ||
                section.toLowerCase().includes('✓');

            return (
                <div key={idx} className="mb-4">
                    {section.split('\n').map((line, lineIdx) => {
                        if (line.startsWith('##') || line.startsWith('===') || line.match(/^[A-Z\s]{10,}:/)) {
                            return (
                                <h3 key={lineIdx} className="text-lg font-semibold text-blue-400 mb-2 flex items-center gap-2">
                                    {hasRisk && <AlertTriangle className="w-5 h-5 text-yellow-500" />}
                                    {hasSuccess && <CheckCircle className="w-5 h-5 text-green-500" />}
                                    {line.replace(/^#+\s*/, '').replace(/^===+\s*/, '')}
                                </h3>
                            );
                        }

                        if (line.trim().startsWith('-') || line.trim().startsWith('•')) {
                            return (
                                <div key={lineIdx} className="ml-4 text-zinc-300 flex items-start gap-2">
                                    <span className="text-blue-400 mt-1">•</span>
                                    <span>{line.replace(/^[\s-•]+/, '')}</span>
                                </div>
                            );
                        }

                        return line.trim() ? (
                            <p key={lineIdx} className="text-zinc-300 leading-relaxed mb-2">
                                {line}
                            </p>
                        ) : null;
                    })}
                </div>
            );
        });
    };

    if (loading) {
        return (
            <div className="bg-zinc-900 border border-white/5 rounded-2xl p-6">
                <div className="flex items-center gap-3">
                    <Brain className="w-6 h-6 text-blue-400" />
                    <h2 className="text-xl font-semibold text-zinc-100">GPT Portfolio Analizi</h2>
                    <div className="ml-auto">
                        <div className="w-6 h-6 border-2 border-blue-400/30 border-t-blue-400 rounded-full animate-spin"></div>
                    </div>
                </div>
            </div>
        );
    }

    if (!available || !analysis) {
        return (
            <div className="bg-zinc-900 border border-white/5 rounded-2xl p-6">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Brain className="w-6 h-6 text-blue-400" />
                        <h2 className="text-xl font-semibold text-zinc-100">GPT Portfolio Analizi</h2>
                    </div>
                    <div className="text-sm text-zinc-500">Analiz bekleniyor...</div>
                </div>
            </div>
        );
    }

    return (
        <>
            {/* Compact Card */}
            <div className="bg-zinc-900 border border-white/5 rounded-2xl p-6">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Brain className="w-6 h-6 text-blue-400" />
                        <h2 className="text-xl font-semibold text-zinc-100">GPT Portfolio Analizi</h2>
                    </div>

                    <div className="flex items-center gap-4">
                        {/* Meta Info */}
                        <div className="flex items-center gap-4 text-sm text-zinc-400">
                            <div className="flex items-center gap-2">
                                <Calendar className="w-4 h-4" />
                                <span>{analysis.as_of_date}</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <Clock className="w-4 h-4" />
                                <span>{formatTimestamp(analysis.timestamp)}</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <TrendingUp className="w-4 h-4 text-green-400" />
                                <span className="text-green-400">Aktif</span>
                            </div>
                        </div>

                        {/* View Button */}
                        <button
                            onClick={() => setShowModal(true)}
                            className="flex items-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition-colors"
                        >
                            <Maximize2 className="w-4 h-4" />
                            <span>Analizi Göster</span>
                        </button>
                    </div>
                </div>
            </div>

            {/* Modal */}
            {showModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
                    <div className="relative w-full max-w-5xl max-h-[90vh] bg-zinc-900 border border-white/10 rounded-2xl shadow-2xl flex flex-col">
                        {/* Modal Header */}
                        <div className="flex items-center justify-between p-6 border-b border-white/10">
                            <div className="flex items-center gap-3">
                                <Brain className="w-6 h-6 text-blue-400" />
                                <h2 className="text-xl font-semibold text-zinc-100">GPT Portfolio Analizi</h2>
                            </div>

                            <button
                                onClick={() => setShowModal(false)}
                                className="p-2 hover:bg-white/5 rounded-lg transition-colors"
                            >
                                <X className="w-5 h-5 text-zinc-400" />
                            </button>
                        </div>

                        {/* Meta Info Bar */}
                        <div className="flex flex-wrap gap-4 px-6 py-4 bg-blue-500/10 border-b border-blue-500/20">
                            <div className="flex items-center gap-2 text-sm">
                                <Calendar className="w-4 h-4 text-blue-400" />
                                <span className="text-zinc-400">Tarih:</span>
                                <span className="text-zinc-200 font-medium">{analysis.as_of_date}</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                                <Clock className="w-4 h-4 text-blue-400" />
                                <span className="text-zinc-400">Analiz:</span>
                                <span className="text-zinc-200 font-medium">{formatTimestamp(analysis.timestamp)}</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm ml-auto">
                                <TrendingUp className="w-4 h-4 text-green-400" />
                                <span className="text-green-400 font-medium">Aktif</span>
                            </div>
                        </div>

                        {/* Modal Content */}
                        <div className="flex-1 overflow-y-auto p-6">
                            <div className="prose prose-sm prose-invert max-w-none">
                                <div className="bg-zinc-800/50 rounded-xl p-6 border border-white/5">
                                    {formatAnalysis(analysis.analysis)}
                                </div>
                            </div>
                        </div>

                        {/* Modal Footer */}
                        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-white/10">
                            <button
                                onClick={fetchAnalysis}
                                className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg transition-colors"
                            >
                                Yenile
                            </button>
                            <button
                                onClick={() => setShowModal(false)}
                                className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition-colors"
                            >
                                Kapat
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
};
