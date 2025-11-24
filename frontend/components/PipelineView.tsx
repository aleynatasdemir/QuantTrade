import React, { useState, useEffect, useRef } from 'react';
import { Play, Database, FileJson, Server, Layers, CheckCircle2, Terminal as TerminalIcon, Download, Loader2, AlertCircle } from 'lucide-react';
import { pipelineAPI } from '../services/api';

interface LogEntry {
  id: number;
  timestamp: string;
  level: 'INFO' | 'WARNING' | 'ERROR';
  message: string;
}

type StepStatus = 'idle' | 'running' | 'completed' | 'error';
type PipelineStep = 'ingestion' | 'processing' | 'features' | 'master';

export const PipelineView: React.FC = () => {
  const [status, setStatus] = useState<'idle' | 'running' | 'completed' | 'failed'>('idle');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [activeStep, setActiveStep] = useState<PipelineStep | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Auto-scroll logs
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  const addLog = (message: string, level: 'INFO' | 'WARNING' | 'ERROR' = 'INFO') => {
    const now = new Date();
    const timeString = now.toLocaleTimeString('en-US', { hour12: false }) + '.' + now.getMilliseconds().toString().padStart(3, '0');
    setLogs(prev => [...prev, { id: Date.now() + Math.random(), timestamp: timeString, level, message }]);
  };

  const parseLogsFromBackend = (logText: string) => {
    const lines = logText.split('\n').filter(line => line.trim());
    const parsedLogs: LogEntry[] = [];

    lines.forEach(line => {
      const now = new Date();
      const timeString = now.toLocaleTimeString('en-US', { hour12: false }) + '.' + now.getMilliseconds().toString().padStart(3, '0');

      let level: 'INFO' | 'WARNING' | 'ERROR' = 'INFO';
      if (line.includes('ERROR') || line.includes('💥')) {
        level = 'ERROR';
      } else if (line.includes('WARNING') || line.includes('UYARI')) {
        level = 'WARNING';
      }

      parsedLogs.push({
        id: Date.now() + Math.random(),
        timestamp: timeString,
        level,
        message: line
      });
    });

    return parsedLogs;
  };

  const pollLogsAndStatus = async () => {
    try {
      const [statusData, logsData] = await Promise.all([
        pipelineAPI.getStatus(),
        pipelineAPI.getLogs()
      ]);

      // Update status
      if (statusData.status === 'completed') {
        setStatus('completed');
        setActiveStep(null);
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
      } else if (statusData.status === 'failed') {
        setStatus('failed');
        setActiveStep(null);
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
      } else if (statusData.status === 'running') {
        setStatus('running');
        // Determine active step from progress message
        const progress = statusData.progress?.toLowerCase() || '';
        if (progress.includes('ingestion') || progress.includes('downloader') || progress.includes('macro') || progress.includes('ohlcv')) {
          setActiveStep('ingestion');
        } else if (progress.includes('processing') || progress.includes('cleaner') || progress.includes('normalizer')) {
          setActiveStep('processing');
        } else if (progress.includes('feature') || progress.includes('engineer')) {
          setActiveStep('features');
        } else if (progress.includes('master') || progress.includes('builder')) {
          setActiveStep('master');
        }
      }

      // Update logs
      if (logsData.logs && logsData.logs.trim()) {
        const newLogs = parseLogsFromBackend(logsData.logs);
        setLogs(newLogs);
      }
    } catch (error) {
      console.error('Failed to poll logs/status:', error);
    }
  };

  const runPipeline = async () => {
    if (status === 'running') return;

    setStatus('running');
    setLogs([]);
    setActiveStep('ingestion');

    try {
      addLog("Starting pipeline: run_daily_pipeline.py", "INFO");

      // Call backend API to start pipeline
      const result = await pipelineAPI.run('pipeline');

      if (result.status === 'started') {
        addLog(`Pipeline started with job ID: ${result.job_id}`, "INFO");

        // Start polling for logs and status
        pollIntervalRef.current = setInterval(pollLogsAndStatus, 2000); // Poll every 2 seconds
      } else {
        addLog(`Failed to start pipeline: ${result.message}`, "ERROR");
        setStatus('failed');
        setActiveStep(null);
      }
    } catch (error: any) {
      addLog(`Error starting pipeline: ${error.message}`, "ERROR");
      setStatus('failed');
      setActiveStep(null);
    }
  };

  const downloadFile = (fileName: string) => {
    // Simulation
    alert(`Downloading ${fileName}...`);
  };

  return (
    <div className="animate-in fade-in duration-500">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 border-b border-white/5 pb-6 gap-4">
        <div>
          <h2 className="text-2xl md:text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-emerald-400 mb-2">
            Pipeline Orchestrator
          </h2>
          <p className="text-zinc-500 font-mono text-xs md:text-sm">Automated Data Ingestion & Feature Engineering</p>
        </div>

        <button
          onClick={runPipeline}
          disabled={status === 'running'}
          className={`
            w-full md:w-auto
            group flex items-center justify-center gap-3 px-8 py-3 rounded-lg font-bold tracking-wider transition-all duration-300
            ${status === 'running'
              ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed border border-white/5'
              : 'bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/50 hover:border-emerald-500 hover:shadow-[0_0_20px_rgba(16,185,129,0.3)]'}
          `}
        >
          {status === 'running' ? (
            <>
              <Loader2 className="animate-spin" /> EXECUTING...
            </>
          ) : (
            <>
              <Play className="fill-current" /> RUN PIPELINE
            </>
          )}
        </button>
      </div>

      {/* Visual Flow */}
      <div className="relative bg-zinc-900 border border-white/5 rounded-2xl p-6 md:p-10 mb-8 overflow-hidden">
        {/* Background Grid */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px]"></div>

        <div className="relative z-10 flex flex-col lg:flex-row justify-between items-center gap-6 lg:gap-4">

          <PipelineNode
            title="Data Sources"
            icon={Database}
            active={activeStep === 'ingestion'}
            completed={status === 'completed' || ['processing', 'features', 'master'].includes(activeStep || '')}
            subtext="Macro, OHLCV, KAP, Financials"
          />

          <Connector active={activeStep === 'ingestion' || activeStep === 'processing'} />

          <PipelineNode
            title="Processing"
            icon={Server}
            active={activeStep === 'processing'}
            completed={status === 'completed' || ['features', 'master'].includes(activeStep || '')}
            subtext="Clean, Normalize, Split Adj."
          />

          <Connector active={activeStep === 'processing' || activeStep === 'features'} />

          <PipelineNode
            title="Feature Eng."
            icon={Layers}
            active={activeStep === 'features'}
            completed={status === 'completed' || ['master'].includes(activeStep || '')}
            subtext="RSI, MACD, Financial Ratios"
          />

          <Connector active={activeStep === 'features' || activeStep === 'master'} />

          <PipelineNode
            title="Master Build"
            icon={FileJson}
            active={activeStep === 'master'}
            completed={status === 'completed'}
            subtext="Merge & Final Validation"
            isLast
          />

        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Terminal Section */}
        <div className="lg:col-span-2 bg-black border border-zinc-800 rounded-xl overflow-hidden flex flex-col shadow-2xl">
          <div className="bg-zinc-900/50 border-b border-white/5 p-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <TerminalIcon size={16} className="text-zinc-500" />
              <span className="text-xs font-mono text-zinc-400 hidden sm:inline">root@quanttrade:~/pipelines/run_daily_pipeline.py</span>
              <span className="text-xs font-mono text-zinc-400 sm:hidden">.../run_daily_pipeline.py</span>
            </div>
            <div className="flex gap-1.5">
              <div className="w-3 h-3 rounded-full bg-red-500/20 border border-red-500/50"></div>
              <div className="w-3 h-3 rounded-full bg-yellow-500/20 border border-yellow-500/50"></div>
              <div className="w-3 h-3 rounded-full bg-green-500/20 border border-green-500/50"></div>
            </div>
          </div>
          <div
            ref={scrollRef}
            className="h-[300px] md:h-[400px] overflow-y-auto p-4 font-mono text-xs md:text-sm space-y-1 scroll-smooth"
          >
            {logs.length === 0 && (
              <div className="text-zinc-600 italic opacity-50">Waiting for execution command...</div>
            )}
            {logs.map((log) => (
              <div key={log.id} className="flex gap-2 md:gap-3 animate-in slide-in-from-left-2 duration-300">
                <span className="text-zinc-600 shrink-0 hidden sm:inline">[{log.timestamp}]</span>
                <span className={`
                  break-all
                  ${log.level === 'INFO' ? 'text-zinc-300' : ''}
                  ${log.level === 'WARNING' ? 'text-amber-400' : ''}
                  ${log.level === 'ERROR' ? 'text-rose-500 font-bold' : ''}
                  ${log.message.includes('STEP') ? 'text-cyan-400 font-bold mt-2 mb-1' : ''}
                  ${log.message.includes('✓') || log.message.includes('Success') || log.message.includes('OK') ? 'text-emerald-400' : ''}
                `}>
                  {log.message}
                </span>
              </div>
            ))}
            {status === 'running' && (
              <div className="w-2 h-4 bg-zinc-500 animate-pulse mt-1"></div>
            )}
          </div>
        </div>

        {/* Output Section */}
        <div className="bg-zinc-900 border border-white/5 rounded-xl p-6 flex flex-col">
          <div className="flex items-center gap-2 mb-6">
            <Database className="text-emerald-500" size={20} />
            <h3 className="font-bold text-lg text-zinc-100">Dataset Output</h3>
          </div>

          {status !== 'completed' ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-8 border-2 border-dashed border-zinc-800 rounded-lg bg-zinc-950/30 min-h-[200px]">
              {status === 'running' ? (
                <>
                  <Loader2 className="animate-spin text-cyan-500 mb-4" size={32} />
                  <p className="text-zinc-400 font-mono">Processing data...</p>
                </>
              ) : (
                <>
                  <AlertCircle className="text-zinc-600 mb-4" size={32} />
                  <p className="text-zinc-500">Run pipeline to generate new datasets.</p>
                </>
              )}
            </div>
          ) : (
            <div className="flex-1 flex flex-col gap-3 animate-in zoom-in-95 duration-500">
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
                <p className="text-xs text-emerald-400 font-mono mb-1">STATUS</p>
                <p className="font-bold text-white flex items-center gap-2">
                  <CheckCircle2 size={16} className="text-emerald-500" />
                  SUCCESS
                </p>
              </div>

              <div className="mt-4 space-y-2">
                <p className="text-xs font-mono text-zinc-500 uppercase">Available for Download</p>

                <DownloadItem
                  name="master_df.parquet"
                  size="450 MB"
                  type="parquet"
                  onDownload={() => downloadFile('master_df.parquet')}
                />
                <DownloadItem
                  name="price_features.csv"
                  size="128 MB"
                  type="csv"
                  onDownload={() => downloadFile('price_features.csv')}
                />
                <DownloadItem
                  name="financials_long.csv"
                  size="85 MB"
                  type="csv"
                  onDownload={() => downloadFile('financials_long.csv')}
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const PipelineNode = ({ title, icon: Icon, active, completed, subtext, isLast }: any) => {
  return (
    <div className={`relative flex flex-row lg:flex-col items-center group z-10 w-full lg:w-auto transition-all duration-500 gap-4 lg:gap-0 p-2 lg:p-0 ${active ? 'scale-105' : ''}`}>
      <div className={`
         w-12 h-12 lg:w-16 lg:h-16 rounded-2xl flex items-center justify-center border-2 transition-all duration-500 shadow-xl shrink-0
         ${active
          ? 'bg-zinc-900 border-cyan-500 shadow-[0_0_30px_rgba(6,182,212,0.4)]'
          : completed
            ? 'bg-emerald-950 border-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.2)]'
            : 'bg-zinc-900 border-zinc-700 opacity-50'}
       `}>
        <Icon size={24} className={`
           lg:w-8 lg:h-8
           transition-colors duration-500
           ${active ? 'text-cyan-400 animate-pulse' : completed ? 'text-emerald-400' : 'text-zinc-600'}
         `} />
      </div>
      <div className="mt-0 lg:mt-4 text-left lg:text-center">
        <h4 className={`font-bold transition-colors ${active ? 'text-cyan-400' : completed ? 'text-emerald-400' : 'text-zinc-500'}`}>
          {title}
        </h4>
        <p className="text-xs text-zinc-500 font-mono mt-1 lg:max-w-[120px]">{subtext}</p>
      </div>
    </div>
  );
};

const Connector = ({ active }: { active: boolean }) => {
  return (
    <>
      {/* Horizontal Line for Desktop */}
      <div className="hidden lg:block flex-1 h-[2px] bg-zinc-800 relative mx-4">
        {active && (
          <div className="absolute inset-0 bg-gradient-to-r from-cyan-500 to-emerald-500 animate-loading-bar shadow-[0_0_10px_rgba(6,182,212,0.5)]"></div>
        )}
      </div>

      {/* Vertical Line for Mobile */}
      <div className="block lg:hidden h-8 w-[2px] bg-zinc-800 relative ml-6">
        {active && (
          <div className="absolute inset-0 bg-gradient-to-b from-cyan-500 to-emerald-500 shadow-[0_0_10px_rgba(6,182,212,0.5)]"></div>
        )}
      </div>
    </>
  );
};

const DownloadItem = ({ name, size, type, onDownload }: any) => {
  return (
    <button
      onClick={onDownload}
      className="w-full flex items-center justify-between p-3 rounded-lg bg-zinc-950 border border-white/5 hover:border-white/20 hover:bg-white/5 transition-all group text-left"
    >
      <div className="flex items-center gap-3 overflow-hidden">
        <div className={`p-2 rounded bg-opacity-10 shrink-0 ${type === 'parquet' ? 'bg-blue-500 text-blue-400' : 'bg-orange-500 text-orange-400'}`}>
          <FileJson size={18} />
        </div>
        <div className="truncate">
          <p className="text-sm font-medium text-zinc-300 group-hover:text-white transition-colors truncate">{name}</p>
          <p className="text-xs text-zinc-600">{size}</p>
        </div>
      </div>
      <Download size={16} className="text-zinc-600 group-hover:text-emerald-400 transition-colors shrink-0" />
    </button>
  );
}

// Add CSS keyframe for the loading bar
const style = document.createElement('style');
style.innerHTML = `
  @keyframes loading-bar {
    0% { width: 0%; left: 0; opacity: 1; }
    50% { width: 100%; left: 0; opacity: 1; }
    100% { width: 100%; left: 100%; opacity: 0; }
  }
  .animate-loading-bar {
    animation: loading-bar 1.5s infinite linear;
    width: 30%; /* Start small and move across */
  }
`;
document.head.appendChild(style);
