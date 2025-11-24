import React, { useState, useEffect } from 'react';
import { DashboardHeader } from './components/DashboardHeader';
import { StatsGrid } from './components/StatsGrid';
import { EquityChart } from './components/EquityChart';
import { PendingOrders } from './components/PendingOrders';
import { PipelineView } from './components/PipelineView';
import { TelegramView } from './components/TelegramView';
import { SettingsView } from './components/SettingsView';
import { LoginView } from './components/LoginView';
import { portfolioAPI, pipelineAPI } from './services/api';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip as RechartsTooltip } from 'recharts';
import { LayoutDashboard, Settings, Layers, Send, LogOut, Menu, Play, RefreshCw, Terminal } from 'lucide-react';

type ViewState = 'dashboard' | 'pipeline' | 'telegram' | 'settings';

function App() {
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(true); // Skip login
  const [currentView, setCurrentView] = useState<ViewState>('dashboard');
  const [data, setData] = useState<any>(null);
  const [equityHistory, setEquityHistory] = useState<any[]>([]);
  const [isRunningPortfolio, setIsRunningPortfolio] = useState(false);
  const [portfolioLogs, setPortfolioLogs] = useState<string[]>([]);
  const [showPortfolioLogs, setShowPortfolioLogs] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Load portfolio data from API
  useEffect(() => {
    loadPortfolioData();
  }, []);

  const loadPortfolioData = async () => {
    try {
      setLoading(true);
      const [state, equity] = await Promise.all([
        portfolioAPI.getState(),
        portfolioAPI.getEquity()
      ]);
      setData(state);
      setEquityHistory(equity);
    } catch (error) {
      console.error('Failed to load portfolio data:', error);
      // Set default data on error
      setData({ cash: 100000, positions: [], pending_buys: [], last_date: null });
      setEquityHistory([]);
    } finally {
      setLoading(false);
    }
  };

  const handleRunPortfolioManager = async () => {
    try {
      setIsRunningPortfolio(true);
      setPortfolioLogs(['Starting Live Portfolio Manager...']);
      setShowPortfolioLogs(true);

      // Call backend API to run portfolio manager
      const result = await pipelineAPI.run('portfolio_manager');

      if (result.status === 'started') {
        setPortfolioLogs(prev => [...prev, `Portfolio manager started with job ID: ${result.job_id}`]);

        // Poll for logs and status
        const pollInterval = setInterval(async () => {
          try {
            const [statusData, logsData] = await Promise.all([
              pipelineAPI.getStatus(),
              pipelineAPI.getLogs()
            ]);

            if (logsData.logs && logsData.logs.trim()) {
              setPortfolioLogs(logsData.logs.split('\n').filter(line => line.trim()));
            }

            if (statusData.status === 'completed' || statusData.status === 'failed') {
              clearInterval(pollInterval);
              setIsRunningPortfolio(false);

              if (statusData.status === 'completed') {
                setPortfolioLogs(prev => [...prev, '✅ Portfolio manager completed successfully']);
                // Reload portfolio data after completion
                setTimeout(() => loadPortfolioData(), 1000);
              } else {
                setPortfolioLogs(prev => [...prev, `❌ Portfolio manager failed: ${statusData.error}`]);
              }
            }
          } catch (error) {
            console.error('Failed to poll status:', error);
          }
        }, 2000);

        // Cleanup after 5 minutes
        setTimeout(() => {
          clearInterval(pollInterval);
          setIsRunningPortfolio(false);
        }, 300000);
      } else {
        setPortfolioLogs(prev => [...prev, `Failed to start: ${result.message}`]);
        setIsRunningPortfolio(false);
      }
    } catch (error: any) {
      console.error('Failed to run portfolio manager:', error);
      setPortfolioLogs(prev => [...prev, `Error: ${error.message}`]);
      setIsRunningPortfolio(false);
    }
  };

  const handleLogin = () => {
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    setCurrentView('dashboard');
  };

  // Prepare data for Allocation Chart
  const totalPlanned = data ? data.pending_buys.reduce((acc: number, curr: any) => acc + curr.planned_capital, 0) : 0;
  const remainingCash = data ? data.cash - totalPlanned : 0;

  const allocationData = [
    { name: 'Reserved (Signals)', value: totalPlanned, color: '#10b981' },
    { name: 'Free Cash', value: remainingCash, color: '#3f3f46' },
  ];

  if (loading || !data) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="relative w-16 h-16">
            <div className="absolute inset-0 rounded-full border-t-2 border-emerald-500 animate-spin"></div>
            <div className="absolute inset-2 rounded-full border-r-2 border-cyan-500 animate-spin reverse duration-700"></div>
          </div>
          <p className="text-zinc-500 font-mono text-sm animate-pulse">LOADING PORTFOLIO DATA...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-200 selection:bg-emerald-500/30 pb-20 md:pb-0">

      {/* Hamburger Menu Button - Desktop */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="fixed top-4 left-4 z-50 p-3 rounded-xl bg-zinc-900 border border-white/5 hover:bg-zinc-800 transition-all hidden md:block"
        title={sidebarOpen ? "Close menu" : "Open menu"}
      >
        <Menu size={20} className="text-zinc-400" />
      </button>

      {/* Hamburger Menu Button - Mobile */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="fixed top-4 left-4 z-50 p-3 rounded-xl bg-zinc-900 border border-white/5 hover:bg-zinc-800 transition-all md:hidden"
        title="Menu"
      >
        <Menu size={20} className="text-zinc-400" />
      </button>

      {/* Backdrop overlay for mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Desktop Sidebar - Collapsible */}
      <nav className={`
        fixed left-0 top-0 h-full bg-zinc-900 border-r border-white/5 
        flex-col items-center py-8 gap-8 z-40
        transition-transform duration-300 ease-in-out
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full md:-translate-x-full'}
        w-64 md:w-20
        flex md:flex
      `}>
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-cyan-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
          <span className="font-bold text-white">A</span>
        </div>

        <div className="flex flex-col gap-6 w-full items-center flex-1">
          <NavButton
            active={currentView === 'dashboard'}
            onClick={() => {
              setCurrentView('dashboard');
              // Close sidebar on mobile after selection
              if (window.innerWidth < 768) setSidebarOpen(false);
            }}
            icon={LayoutDashboard}
            color="text-emerald-400"
            activeColor="bg-emerald-500"
            label="Dashboard"
          />
          <NavButton
            active={currentView === 'pipeline'}
            onClick={() => {
              setCurrentView('pipeline');
              if (window.innerWidth < 768) setSidebarOpen(false);
            }}
            icon={Layers}
            color="text-cyan-400"
            activeColor="bg-cyan-500"
            label="Pipeline"
          />
          <NavButton
            active={currentView === 'telegram'}
            onClick={() => {
              setCurrentView('telegram');
              if (window.innerWidth < 768) setSidebarOpen(false);
            }}
            icon={Send}
            color="text-sky-400"
            activeColor="bg-sky-500"
            label="Telegram"
          />
          <NavButton
            active={currentView === 'settings'}
            onClick={() => {
              setCurrentView('settings');
              if (window.innerWidth < 768) setSidebarOpen(false);
            }}
            icon={Settings}
            color="text-purple-400"
            activeColor="bg-purple-500"
            label="Settings"
          />
        </div>

        {/* Bottom Actions */}
        <button
          onClick={handleLogout}
          className="p-3 rounded-xl text-zinc-600 hover:text-rose-500 hover:bg-rose-500/10 transition-colors"
          title="Logout"
        >
          <LogOut size={24} />
        </button>
      </nav>

      {/* Mobile Bottom Navigation */}
      <nav className="fixed bottom-0 left-0 w-full bg-zinc-900/90 backdrop-blur-lg border-t border-white/5 md:hidden flex justify-around items-center p-4 z-50 safe-area-pb">
        <MobileNavButton
          active={currentView === 'dashboard'}
          onClick={() => setCurrentView('dashboard')}
          icon={LayoutDashboard}
          activeColor="text-emerald-400"
        />
        <MobileNavButton
          active={currentView === 'pipeline'}
          onClick={() => setCurrentView('pipeline')}
          icon={Layers}
          activeColor="text-cyan-400"
        />
        <div className="relative -top-5">
          <div className="w-12 h-12 rounded-full bg-gradient-to-br from-emerald-500 to-cyan-600 flex items-center justify-center shadow-lg shadow-emerald-500/20 border-4 border-zinc-950">
            <span className="font-bold text-white">A</span>
          </div>
        </div>
        <MobileNavButton
          active={currentView === 'telegram'}
          onClick={() => setCurrentView('telegram')}
          icon={Send}
          activeColor="text-sky-400"
        />
        <MobileNavButton
          active={currentView === 'settings'}
          onClick={() => setCurrentView('settings')}
          icon={Settings}
          activeColor="text-purple-400"
        />
      </nav>

      {/* Main Content */}
      <main className={`p-4 md:p-6 lg:p-10 max-w-[1920px] mx-auto min-h-screen transition-all duration-300 ${sidebarOpen ? 'md:pl-24' : 'md:pl-20'}`}>
        <DashboardHeader />

        {currentView === 'dashboard' && (
          <div className="animate-in fade-in duration-500">
            {/* Action Buttons */}
            <div className="mb-6 flex gap-4">
              <button
                onClick={handleRunPortfolioManager}
                disabled={isRunningPortfolio}
                className="px-6 py-3 bg-gradient-to-r from-emerald-500 to-cyan-600 hover:from-emerald-600 hover:to-cyan-700 disabled:from-zinc-700 disabled:to-zinc-800 rounded-xl font-semibold text-white shadow-lg transition-all flex items-center gap-2"
              >
                {isRunningPortfolio ? (
                  <><RefreshCw size={20} className="animate-spin" /> Running...</>
                ) : (
                  <><Play size={20} /> Run Live Portfolio Manager</>
                )}
              </button>
              <button
                onClick={loadPortfolioData}
                className="px-6 py-3 bg-zinc-800 hover:bg-zinc-700 rounded-xl font-semibold text-white transition-all flex items-center gap-2"
              >
                <RefreshCw size={20} /> Refresh Data
              </button>
            </div>

            {/* Portfolio Manager Logs */}
            {showPortfolioLogs && (
              <div className="mb-6 bg-black border border-zinc-800 rounded-xl overflow-hidden shadow-2xl">
                <div className="bg-zinc-900/50 border-b border-white/5 p-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Terminal size={16} className="text-zinc-500" />
                    <span className="text-xs font-mono text-zinc-400">Live Portfolio Manager Output</span>
                  </div>
                  <button
                    onClick={() => setShowPortfolioLogs(false)}
                    className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
                  >
                    Close
                  </button>
                </div>
                <div className="h-[200px] overflow-y-auto p-4 font-mono text-xs space-y-1 scroll-smooth">
                  {portfolioLogs.length === 0 ? (
                    <div className="text-zinc-600 italic opacity-50">Waiting for output...</div>
                  ) : (
                    portfolioLogs.map((log, idx) => (
                      <div key={idx} className="text-zinc-300 animate-in slide-in-from-left-2 duration-300">
                        {log}
                      </div>
                    ))
                  )}
                  {isRunningPortfolio && (
                    <div className="w-2 h-4 bg-zinc-500 animate-pulse mt-1"></div>
                  )}
                </div>
              </div>
            )}

            {/* Top KPI Cards */}
            <StatsGrid data={data} />

            {/* Middle Section: Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">

              {/* Main Equity Curve */}
              <div className="lg:col-span-2 bg-zinc-900 border border-white/5 rounded-2xl p-4 md:p-6">
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4">
                  <div>
                    <h3 className="text-lg font-semibold text-zinc-100">Equity Curve</h3>
                    <p className="text-sm text-zinc-500">20 Day Performance Analysis</p>
                  </div>
                  <div className="flex gap-2 w-full sm:w-auto overflow-x-auto pb-1 sm:pb-0">
                    {['1W', '1M', '3M', 'YTD'].map(period => (
                      <button
                        key={period}
                        className={`text-xs px-3 py-1 rounded-md transition-colors whitespace-nowrap ${period === '1M' ? 'bg-zinc-800 text-white' : 'text-zinc-600 hover:text-zinc-400'}`}
                      >
                        {period}
                      </button>
                    ))}
                  </div>
                </div>
                <EquityChart data={equityHistory.map(e => ({ date: e.date, value: e.equity }))} />
              </div>

              {/* Allocation / Radial */}
              <div className="bg-zinc-900 border border-white/5 rounded-2xl p-4 md:p-6 flex flex-col">
                <div className="mb-4">
                  <h3 className="text-lg font-semibold text-zinc-100">Capital Allocation</h3>
                  <p className="text-sm text-zinc-500">Projected Post-Execution</p>
                </div>

                <div className="flex-1 min-h-[250px] relative">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={allocationData}
                        innerRadius={60}
                        outerRadius={80}
                        paddingAngle={5}
                        dataKey="value"
                        stroke="none"
                      >
                        {allocationData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <RechartsTooltip
                        contentStyle={{ backgroundColor: '#18181b', borderColor: '#27272a', borderRadius: '8px' }}
                        itemStyle={{ color: '#e4e4e7' }}
                        formatter={(value: number) => `₺${value.toLocaleString()}`}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  {/* Center Text */}
                  <div className="absolute inset-0 flex items-center justify-center flex-col pointer-events-none">
                    <span className="text-2xl font-bold font-mono text-white">100%</span>
                    <span className="text-xs text-zinc-500 uppercase tracking-widest">Liquid</span>
                  </div>
                </div>

                <div className="mt-4 space-y-3">
                  {allocationData.map(item => (
                    <div key={item.name} className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2">
                        <span className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }}></span>
                        <span className="text-zinc-300">{item.name}</span>
                      </div>
                      <span className="font-mono text-zinc-500">₺{item.value.toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Bottom Section: Pending Orders & Algo Details */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <PendingOrders orders={data.pending_buys} />

              <div className="bg-zinc-900 border border-white/5 rounded-2xl p-4 md:p-6">
                <h3 className="text-lg font-semibold text-zinc-100 mb-6">Algorithm Parameters</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 rounded-xl bg-zinc-950 border border-white/5">
                    <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Stop Loss</p>
                    <p className="text-xl font-mono text-rose-400 font-bold">5.00%</p>
                    <div className="w-full bg-zinc-900 h-1 mt-3 rounded-full overflow-hidden">
                      <div className="w-1/4 h-full bg-rose-500"></div>
                    </div>
                  </div>
                  <div className="p-4 rounded-xl bg-zinc-950 border border-white/5">
                    <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Horizon</p>
                    <p className="text-xl font-mono text-blue-400 font-bold">T+20 Days</p>
                    <div className="w-full bg-zinc-900 h-1 mt-3 rounded-full overflow-hidden">
                      <div className="w-2/3 h-full bg-blue-500"></div>
                    </div>
                  </div>
                  <div className="p-4 rounded-xl bg-zinc-950 border border-white/5">
                    <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Commission</p>
                    <p className="text-xl font-mono text-zinc-300 font-bold">0.2%</p>
                  </div>
                  <div className="p-4 rounded-xl bg-zinc-950 border border-white/5">
                    <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Max Positions</p>
                    <p className="text-xl font-mono text-zinc-300 font-bold">5</p>
                  </div>
                </div>

                <div className="mt-6 p-4 rounded-xl bg-blue-500/5 border border-blue-500/10 text-sm text-blue-300/80 leading-relaxed">
                  <p>
                    <span className="font-bold text-blue-400">System Note:</span> Signals are generated based on sector-neutralized indicators using CatBoost. Orders in the "Pending" queue should be executed at the next market open price.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {currentView === 'pipeline' && (
          <PipelineView />
        )}

        {currentView === 'telegram' && (
          <TelegramView />
        )}

        {currentView === 'settings' && (
          <SettingsView />
        )}
      </main>
    </div>
  );
}

// Subcomponents for clearer readability
const NavButton = ({ active, onClick, icon: Icon, color, activeColor, label }: any) => (
  <button
    onClick={onClick}
    className={`p-3 rounded-xl transition-all duration-300 relative ${active ? `bg-white/10 ${color}` : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/5'}`}
    title={label}
  >
    <Icon size={24} />
    {active && <span className={`absolute right-2 top-2 w-2 h-2 rounded-full ${activeColor} shadow-[0_0_10px_currentColor]`}></span>}
  </button>
);

const MobileNavButton = ({ active, onClick, icon: Icon, activeColor }: any) => (
  <button
    onClick={onClick}
    className={`p-2 rounded-xl transition-all duration-300 ${active ? activeColor : 'text-zinc-500'}`}
  >
    <Icon size={24} strokeWidth={active ? 2.5 : 2} />
  </button>
);

export default App;
