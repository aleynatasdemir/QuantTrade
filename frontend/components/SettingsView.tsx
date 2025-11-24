import React, { useState } from 'react';
import { User, Shield, Bell, Key, Mail, Smartphone, Save, CreditCard, LogOut, CheckCircle2 } from 'lucide-react';

type Tab = 'general' | 'security' | 'notifications';

export const SettingsView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('general');
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const tabs = [
    { id: 'general', label: 'General Profile', icon: User },
    { id: 'security', label: 'Login & Security', icon: Shield },
    { id: 'notifications', label: 'Notifications', icon: Bell },
  ];

  return (
    <div className="animate-in fade-in duration-500 max-w-5xl mx-auto">
      <div className="mb-8 border-b border-white/5 pb-6">
        <h2 className="text-2xl md:text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-zinc-100 to-zinc-500 mb-2">
          Account Settings
        </h2>
        <p className="text-zinc-500 font-mono text-sm">Manage your personal information and system preferences</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
        {/* Navigation Sidebar / Horizontal Tabs on Mobile */}
        <div className="md:col-span-1">
           <div className="flex flex-row md:flex-col gap-2 overflow-x-auto md:overflow-visible pb-4 md:pb-0">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as Tab)}
                  className={`
                    flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 text-sm font-medium whitespace-nowrap md:whitespace-normal
                    ${
                      activeTab === tab.id
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/5 bg-zinc-900/50 md:bg-transparent'
                    }
                  `}
                >
                  <Icon size={18} />
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Content Area */}
        <div className="md:col-span-3">
          <div className="bg-zinc-900 border border-white/5 rounded-2xl p-6 md:p-8 relative overflow-hidden">
            
            {/* Success Toast */}
            {saved && (
              <div className="absolute top-4 right-4 left-4 md:left-auto bg-emerald-500/20 border border-emerald-500/50 text-emerald-400 px-4 py-2 rounded-lg flex items-center justify-center md:justify-start gap-2 text-sm animate-in slide-in-from-top-2 fade-in shadow-xl z-20">
                <CheckCircle2 size={16} /> Changes Saved
              </div>
            )}

            {activeTab === 'general' && (
              <div className="space-y-8 animate-in slide-in-from-right-4 duration-300">
                <div className="flex flex-col sm:flex-row items-center sm:items-start gap-6 text-center sm:text-left">
                  <div className="relative group cursor-pointer">
                    <div className="w-24 h-24 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-3xl font-bold text-white shadow-xl">
                      BY
                    </div>
                    <div className="absolute inset-0 bg-black/50 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                      <span className="text-xs font-medium text-white">Change</span>
                    </div>
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-white">Burak Yılmaz</h3>
                    <p className="text-zinc-500">Senior Algorithmic Trader</p>
                    <p className="text-xs font-mono text-zinc-600 mt-1">ID: 8829-XJ-29</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <label className="text-xs font-mono text-zinc-500 uppercase">Full Name</label>
                    <input type="text" defaultValue="Burak Yılmaz" className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-zinc-200 focus:border-cyan-500 outline-none transition-colors" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs font-mono text-zinc-500 uppercase">Job Title</label>
                    <input type="text" defaultValue="Senior Trader" className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-zinc-200 focus:border-cyan-500 outline-none transition-colors" />
                  </div>
                  <div className="space-y-2 md:col-span-2">
                    <label className="text-xs font-mono text-zinc-500 uppercase">Bio</label>
                    <textarea rows={3} defaultValue="Specializing in high-frequency trading strategies and machine learning integration for BIST markets." className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-zinc-200 focus:border-cyan-500 outline-none transition-colors resize-none" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs font-mono text-zinc-500 uppercase">Email Address</label>
                    <input type="email" defaultValue="burak@quanttrade.com" className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-zinc-200 focus:border-cyan-500 outline-none transition-colors" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs font-mono text-zinc-500 uppercase">Location</label>
                    <input type="text" defaultValue="Istanbul, TR" className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-zinc-200 focus:border-cyan-500 outline-none transition-colors" />
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'security' && (
              <div className="space-y-8 animate-in slide-in-from-right-4 duration-300">
                <div className="pb-6 border-b border-white/5">
                  <h4 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
                    <Key size={18} className="text-cyan-400" /> Password Update
                  </h4>
                  <div className="space-y-4 max-w-md">
                    <div className="space-y-2">
                      <label className="text-xs font-mono text-zinc-500 uppercase">Current Password</label>
                      <input type="password" placeholder="••••••••" className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-zinc-200 focus:border-cyan-500 outline-none transition-colors" />
                    </div>
                    <div className="space-y-2">
                      <label className="text-xs font-mono text-zinc-500 uppercase">New Password</label>
                      <input type="password" placeholder="••••••••" className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-zinc-200 focus:border-cyan-500 outline-none transition-colors" />
                    </div>
                  </div>
                </div>

                <div>
                   <h4 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
                    <Smartphone size={18} className="text-emerald-400" /> Two-Factor Authentication
                  </h4>
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-4 rounded-xl bg-zinc-950 border border-zinc-800 gap-4">
                    <div>
                      <p className="text-sm font-medium text-zinc-200">Authenticator App</p>
                      <p className="text-xs text-zinc-500 mt-1">Use an app like Google Authenticator to protect your account.</p>
                    </div>
                    <div className="flex items-center gap-2 w-full sm:w-auto">
                      <span className="text-xs text-emerald-500 font-mono bg-emerald-500/10 px-2 py-1 rounded">ENABLED</span>
                      <button className="flex-1 sm:flex-none px-3 py-1.5 text-xs bg-zinc-800 hover:bg-zinc-700 rounded text-white transition-colors">Configure</button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'notifications' && (
               <div className="space-y-6 animate-in slide-in-from-right-4 duration-300">
                  <div className="flex items-start justify-between p-4 rounded-xl bg-zinc-950 border border-zinc-800">
                    <div className="flex gap-4">
                      <div className="p-2 bg-sky-500/10 rounded-lg h-fit">
                        <Mail size={20} className="text-sky-400" />
                      </div>
                      <div>
                        <h4 className="font-medium text-zinc-200">Email Notifications</h4>
                        <p className="text-sm text-zinc-500 mt-1">Receive daily pipeline summaries and critical system alerts.</p>
                      </div>
                    </div>
                    <div className="relative inline-block w-11 h-6 transition-colors duration-200 ease-in-out bg-emerald-500 rounded-full cursor-pointer shrink-0">
                        <span className="inline-block w-5 h-5 ml-0.5 mt-0.5 transform translate-x-5 bg-white rounded-full shadow ring-0 transition duration-200 ease-in-out"></span>
                    </div>
                  </div>

                  <div className="flex items-start justify-between p-4 rounded-xl bg-zinc-950 border border-zinc-800">
                    <div className="flex gap-4">
                      <div className="p-2 bg-indigo-500/10 rounded-lg h-fit">
                        <Smartphone size={20} className="text-indigo-400" />
                      </div>
                      <div>
                        <h4 className="font-medium text-zinc-200">Telegram Signals</h4>
                        <p className="text-sm text-zinc-500 mt-1">Real-time buy/sell signals sent directly to your configured bot.</p>
                      </div>
                    </div>
                    <div className="relative inline-block w-11 h-6 transition-colors duration-200 ease-in-out bg-emerald-500 rounded-full cursor-pointer shrink-0">
                        <span className="inline-block w-5 h-5 ml-0.5 mt-0.5 transform translate-x-5 bg-white rounded-full shadow ring-0 transition duration-200 ease-in-out"></span>
                    </div>
                  </div>

                  <div className="flex items-start justify-between p-4 rounded-xl bg-zinc-950 border border-zinc-800">
                    <div className="flex gap-4">
                      <div className="p-2 bg-orange-500/10 rounded-lg h-fit">
                        <CreditCard size={20} className="text-orange-400" />
                      </div>
                      <div>
                        <h4 className="font-medium text-zinc-200">Billing Alerts</h4>
                        <p className="text-sm text-zinc-500 mt-1">Get notified when server costs exceed defined thresholds.</p>
                      </div>
                    </div>
                    <div className="relative inline-block w-11 h-6 transition-colors duration-200 ease-in-out bg-zinc-700 rounded-full cursor-pointer shrink-0">
                        <span className="inline-block w-5 h-5 ml-0.5 mt-0.5 translate-x-0 bg-zinc-400 rounded-full shadow ring-0 transition duration-200 ease-in-out"></span>
                    </div>
                  </div>
               </div>
            )}

            <div className="mt-10 pt-6 border-t border-white/5 flex flex-col sm:flex-row justify-end gap-3">
              <button className="w-full sm:w-auto px-6 py-2.5 rounded-lg text-sm font-medium text-zinc-400 hover:text-white hover:bg-white/5 transition-colors">
                Cancel
              </button>
              <button 
                onClick={handleSave}
                className="w-full sm:w-auto px-6 py-2.5 rounded-lg bg-white text-zinc-950 text-sm font-bold hover:bg-zinc-200 transition-colors flex items-center justify-center gap-2"
              >
                <Save size={16} /> Save Changes
              </button>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
};
