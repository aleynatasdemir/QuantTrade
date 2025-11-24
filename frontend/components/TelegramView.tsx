
import React, { useState } from 'react';
import { Send, UserPlus, Trash2, Shield, Radio, CheckCircle2, AlertTriangle, TrendingUp, TrendingDown, Bot, Settings, Lock } from 'lucide-react';

interface TelegramUser {
  id: number;
  name: string;
  chatId: string;
  role: 'Admin' | 'Trader' | 'Viewer';
  active: boolean;
  avatarColor: string;
}

interface SignalMessage {
  id: number;
  type: 'BUY' | 'SELL' | 'INFO';
  symbol: string;
  price: number;
  timestamp: string;
  date: string; // Grouping
  message: string;
  status: 'SENT' | 'PENDING';
}

const MOCK_USERS: TelegramUser[] = [
  { id: 1, name: 'Admin User', chatId: '192837465', role: 'Admin', active: true, avatarColor: 'bg-indigo-500' },
  { id: 2, name: 'Burak Yılmaz', chatId: '554433221', role: 'Trader', active: true, avatarColor: 'bg-emerald-500' },
  { id: 3, name: 'Analist Grubu', chatId: '-100293847', role: 'Viewer', active: false, avatarColor: 'bg-zinc-600' },
];

const MOCK_MESSAGES: SignalMessage[] = [
  { 
    id: 1, type: 'BUY', symbol: 'THYAO', price: 284.50, timestamp: '10:42', date: 'Today', 
    message: 'AL Sinyali Tespit Edildi.\nRSI < 30 ve MACD Pozitif Kesişim.\nHedef: 305.00 TL', status: 'SENT' 
  },
  { 
    id: 2, type: 'SELL', symbol: 'KCHOL', price: 162.10, timestamp: '09:15', date: 'Today', 
    message: 'SAT Sinyali.\nStop-Loss seviyesi tetiklendi (163.00).\nPozisyon kapatılıyor.', status: 'SENT' 
  },
  { 
    id: 3, type: 'INFO', symbol: 'SYSTEM', price: 0, timestamp: '09:00', date: 'Today', 
    message: 'Günlük Pipeline tamamlandı. Piyasalar açılmadan önce veriler güncellendi.', status: 'SENT' 
  },
  { 
    id: 4, type: 'BUY', symbol: 'ASELS', price: 48.20, timestamp: '17:55', date: 'Yesterday', 
    message: 'Kapanışa doğru hacim artışı. T+1 Stratejisi için portföye ekleniyor.', status: 'SENT' 
  },
];

export const TelegramView: React.FC = () => {
  const [users, setUsers] = useState<TelegramUser[]>(MOCK_USERS);
  const [newUser, setNewUser] = useState({ name: '', chatId: '' });
  const [showAddModal, setShowAddModal] = useState(false);
  const [botToken, setBotToken] = useState('781293:AAGHs82...'); 
  const [isEditingToken, setIsEditingToken] = useState(false);

  const toggleUserStatus = (id: number) => {
    setUsers(users.map(u => u.id === id ? { ...u, active: !u.active } : u));
  };

  const deleteUser = (id: number) => {
    setUsers(users.filter(u => u.id !== id));
  };

  const handleAddUser = () => {
    if (newUser.name && newUser.chatId) {
      setUsers([...users, {
        id: Date.now(),
        name: newUser.name,
        chatId: newUser.chatId,
        role: 'Trader',
        active: true,
        avatarColor: 'bg-cyan-600'
      }]);
      setNewUser({ name: '', chatId: '' });
      setShowAddModal(false);
    }
  };

  return (
    <div className="animate-in fade-in duration-500 grid grid-cols-1 lg:grid-cols-3 gap-6 lg:gap-8 min-h-[calc(100vh-140px)]">
      
      {/* LEFT COLUMN: MESSAGE FEED */}
      <div className="lg:col-span-2 flex flex-col bg-zinc-900 border border-white/5 rounded-2xl overflow-hidden shadow-2xl h-[500px] lg:h-auto">
        <div className="p-4 md:p-6 border-b border-white/5 bg-zinc-900/50 backdrop-blur flex justify-between items-center sticky top-0 z-10">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-sky-500/10 rounded-lg">
              <Send className="text-sky-400" size={20} />
            </div>
            <div>
              <h2 className="text-lg md:text-xl font-bold text-zinc-100">Canlı Sinyal Akışı</h2>
              <p className="text-xs text-zinc-500 font-mono hidden sm:block">QuantTrade Bot • @quant_alpha_bot</p>
            </div>
          </div>
          <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span className="text-xs font-medium text-emerald-400">ONLINE</span>
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-95">
          {['Today', 'Yesterday'].map(dateGroup => {
            const groupMessages = MOCK_MESSAGES.filter(m => m.date === dateGroup);
            if (groupMessages.length === 0) return null;

            return (
              <div key={dateGroup}>
                <div className="flex justify-center mb-6">
                  <span className="px-3 py-1 rounded-full bg-zinc-800 text-xs text-zinc-500 font-medium border border-zinc-700">
                    {dateGroup}
                  </span>
                </div>
                <div className="space-y-4">
                  {groupMessages.map(msg => (
                    <div 
                      key={msg.id} 
                      className={`relative group flex gap-4 p-4 rounded-xl border transition-all duration-300 ${
                        msg.type === 'BUY' 
                          ? 'bg-emerald-950/20 border-emerald-500/20 hover:bg-emerald-950/30' 
                          : msg.type === 'SELL' 
                            ? 'bg-rose-950/20 border-rose-500/20 hover:bg-rose-950/30'
                            : 'bg-zinc-800/50 border-zinc-700 hover:bg-zinc-800'
                      }`}
                    >
                      {/* Icon */}
                      <div className={`mt-1 shrink-0 w-10 h-10 rounded-full flex items-center justify-center border ${
                         msg.type === 'BUY' ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' :
                         msg.type === 'SELL' ? 'bg-rose-500/10 border-rose-500/30 text-rose-400' :
                         'bg-zinc-700/50 border-zinc-600 text-zinc-400'
                      }`}>
                        {msg.type === 'BUY' ? <TrendingUp size={18} /> : 
                         msg.type === 'SELL' ? <TrendingDown size={18} /> : 
                         <Bot size={18} />}
                      </div>

                      {/* Content */}
                      <div className="flex-1">
                        <div className="flex justify-between items-start">
                          <h4 className={`font-bold text-sm tracking-wider ${
                             msg.type === 'BUY' ? 'text-emerald-400' :
                             msg.type === 'SELL' ? 'text-rose-400' :
                             'text-zinc-300'
                          }`}>
                            {msg.type === 'INFO' ? 'SYSTEM NOTIFICATION' : `${msg.type} ${msg.symbol}`}
                          </h4>
                          <span className="text-xs text-zinc-500 font-mono">{msg.timestamp}</span>
                        </div>
                        
                        {msg.price > 0 && (
                          <div className="mt-1 mb-2 font-mono text-xl font-medium text-white">
                            ₺{msg.price.toFixed(2)}
                          </div>
                        )}
                        
                        <p className="text-sm text-zinc-400 whitespace-pre-line leading-relaxed">
                          {msg.message}
                        </p>
                      </div>

                      {/* Status Indicator */}
                      <div className="absolute bottom-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
                         <CheckCircle2 size={16} className="text-sky-500" />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* Fake Input Area */}
        <div className="p-4 border-t border-white/5 bg-zinc-900 flex gap-3">
          <input 
            type="text" 
            placeholder="Broadcast manual message..." 
            className="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2 text-sm text-zinc-200 focus:outline-none focus:border-sky-500 transition-colors"
          />
          <button className="px-4 py-2 bg-sky-600 hover:bg-sky-500 rounded-lg text-white transition-colors">
            <Send size={18} />
          </button>
        </div>
      </div>

      {/* RIGHT COLUMN: CONFIG & SUBSCRIBERS */}
      <div className="flex flex-col gap-6">
        
        {/* Config Card */}
        <div className="bg-zinc-900 border border-white/5 rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <Settings className="text-zinc-400" size={20} />
            <h3 className="font-bold text-zinc-100">Bot Configuration</h3>
          </div>
          
          <div className="space-y-4">
             <div>
               <label className="text-xs text-zinc-500 uppercase font-semibold block mb-1">Bot Name</label>
               <input type="text" value="@quant_alpha_bot" readOnly className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-400 focus:outline-none" />
             </div>
             <div>
               <label className="text-xs text-zinc-500 uppercase font-semibold block mb-1">API Token</label>
               <div className="relative">
                 <input 
                   type={isEditingToken ? "text" : "password"} 
                   value={botToken}
                   onChange={(e) => setBotToken(e.target.value)}
                   readOnly={!isEditingToken}
                   className={`w-full bg-zinc-950 border rounded-lg px-3 py-2 text-sm text-zinc-400 focus:outline-none pr-10 ${isEditingToken ? 'border-sky-500 text-white' : 'border-zinc-800'}`} 
                 />
                 <button 
                   onClick={() => setIsEditingToken(!isEditingToken)}
                   className="absolute right-2 top-2 text-zinc-500 hover:text-white"
                 >
                   {isEditingToken ? <CheckCircle2 size={16} /> : <Lock size={16} />}
                 </button>
               </div>
             </div>
             
             <div className="pt-2">
                <div className="flex items-center justify-between p-3 rounded-lg bg-yellow-500/5 border border-yellow-500/10">
                   <div className="flex items-center gap-2">
                     <AlertTriangle size={16} className="text-yellow-500" />
                     <span className="text-xs text-yellow-200/80">Test Mode Active</span>
                   </div>
                   <div className="relative inline-block w-8 h-4 rounded-full bg-yellow-500/20 cursor-pointer">
                      <span className="absolute left-4 top-0.5 block w-3 h-3 rounded-full bg-yellow-500 shadow-sm"></span>
                   </div>
                </div>
             </div>
          </div>
        </div>

        {/* Users Card */}
        <div className="bg-zinc-900 border border-white/5 rounded-2xl p-6 flex-1 flex flex-col min-h-[300px]">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2">
              <Shield className="text-zinc-400" size={20} />
              <h3 className="font-bold text-zinc-100">Subscribers</h3>
            </div>
            <button 
              onClick={() => setShowAddModal(!showAddModal)}
              className="p-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-zinc-300 transition-colors"
            >
              <UserPlus size={18} />
            </button>
          </div>

          {showAddModal && (
            <div className="mb-4 p-4 rounded-xl bg-zinc-950 border border-zinc-800 animate-in slide-in-from-top-2">
              <h4 className="text-sm font-semibold text-white mb-3">Add New Subscriber</h4>
              <div className="space-y-3">
                <input 
                  type="text" 
                  placeholder="User Name" 
                  value={newUser.name}
                  onChange={e => setNewUser({...newUser, name: e.target.value})}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded p-2 text-sm text-white focus:border-sky-500 outline-none"
                />
                <input 
                  type="text" 
                  placeholder="Chat ID (e.g. 123456789)" 
                  value={newUser.chatId}
                  onChange={e => setNewUser({...newUser, chatId: e.target.value})}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded p-2 text-sm text-white focus:border-sky-500 outline-none font-mono"
                />
                <div className="flex gap-2">
                  <button onClick={handleAddUser} className="flex-1 bg-sky-600 hover:bg-sky-500 text-white text-xs py-2 rounded font-medium">Add User</button>
                  <button onClick={() => setShowAddModal(false)} className="px-3 bg-zinc-800 hover:bg-zinc-700 text-zinc-400 text-xs rounded">Cancel</button>
                </div>
              </div>
            </div>
          )}

          <div className="space-y-3 flex-1 overflow-y-auto pr-1">
            {users.map(user => (
              <div key={user.id} className="flex items-center justify-between p-3 rounded-xl bg-zinc-950/50 border border-white/5 group hover:border-white/10 transition-colors">
                <div className="flex items-center gap-3">
                  <div className={`w-8 h-8 rounded-full ${user.avatarColor} flex items-center justify-center text-xs font-bold text-white shadow-lg`}>
                    {user.name.substring(0, 1)}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-zinc-200">{user.name}</p>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono text-zinc-500">{user.chatId}</span>
                      <span className="text-[10px] px-1.5 py-0.5 bg-zinc-800 rounded text-zinc-400">{user.role}</span>
                    </div>
                  </div>
                </div>
                
                <div className="flex items-center gap-2">
                   <button 
                    onClick={() => toggleUserStatus(user.id)}
                    className={`relative w-8 h-4 rounded-full transition-colors ${user.active ? 'bg-emerald-500/20' : 'bg-zinc-700'}`}
                   >
                     <span className={`absolute top-0.5 w-3 h-3 rounded-full shadow-sm transition-all duration-300 ${user.active ? 'left-4 bg-emerald-500' : 'left-0.5 bg-zinc-500'}`}></span>
                   </button>
                   <button 
                    onClick={() => deleteUser(user.id)}
                    className="p-1.5 text-zinc-600 hover:text-rose-500 transition-colors opacity-100 lg:opacity-0 group-hover:opacity-100"
                   >
                     <Trash2 size={14} />
                   </button>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 pt-4 border-t border-white/5 text-center">
            <p className="text-xs text-zinc-500">
               Total {users.filter(u => u.active).length} active subscribers receiving daily signals.
            </p>
          </div>
        </div>

      </div>
    </div>
  );
};
