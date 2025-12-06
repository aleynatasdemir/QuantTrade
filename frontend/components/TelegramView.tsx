
import React, { useState, useEffect } from 'react';
import { Send, UserPlus, Trash2, Shield, Radio, CheckCircle2, AlertTriangle, TrendingUp, TrendingDown, Bot, Settings, Lock } from 'lucide-react';
import { telegramAPI } from '../services/api';

interface TelegramUser {
  id: number;
  name: string;
  chat_id: string;
  role: 'Admin' | 'Trader' | 'Viewer';
  active: boolean;
  avatar_color: string;
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

// Mock messages - backend'de message logging sistemi olana kadar kullanılacak
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

// Helper functions for date formatting
const isToday = (dateStr: string) => {
  const today = new Date().toISOString().split('T')[0];
  return dateStr === today;
};

const isYesterday = (dateStr: string) => {
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  return dateStr === yesterday.toISOString().split('T')[0];
};

export const TelegramView: React.FC = () => {
  const [users, setUsers] = useState<TelegramUser[]>([]);
  const [newUser, setNewUser] = useState({ name: '', chatId: '', role: 'Trader' as 'Admin' | 'Trader' | 'Viewer' });
  const [showAddModal, setShowAddModal] = useState(false);
  const [botToken, setBotToken] = useState('');
  const [botUsername, setBotUsername] = useState('');
  const [testMode, setTestMode] = useState(true);
  const [isEditingToken, setIsEditingToken] = useState(false);
  const [loading, setLoading] = useState(true);
  const [broadcastMessage, setBroadcastMessage] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [messages, setMessages] = useState<SignalMessage[]>([]);

  // Load configuration and subscribers on mount
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [config, subscribers, messageHistory] = await Promise.all([
        telegramAPI.getConfig(),
        telegramAPI.getSubscribers(),
        telegramAPI.getMessages()
      ]);

      setBotToken(config.bot_token || '');
      setBotUsername(config.bot_username || '');
      setTestMode(config.test_mode ?? true);
      setUsers(subscribers.map((sub: any) => ({
        id: sub.id,
        name: sub.name,
        chat_id: sub.chat_id,
        role: sub.role,
        active: sub.active,
        avatar_color: sub.avatar_color || 'bg-cyan-600'
      })));

      // Process message history and group by date
      const processedMessages = messageHistory.map((msg: any) => ({
        ...msg,
        date: isToday(msg.date) ? 'Today' : isYesterday(msg.date) ? 'Yesterday' : msg.date
      }));
      setMessages(processedMessages);
    } catch (error) {
      console.error('Failed to load telegram data:', error);
    } finally {
      setLoading(false);
    }
  };

  const toggleUserStatus = async (id: number) => {
    const user = users.find(u => u.id === id);
    if (!user) return;

    try {
      await telegramAPI.updateSubscriber(id, { active: !user.active });
      setUsers(users.map(u => u.id === id ? { ...u, active: !u.active } : u));
    } catch (error) {
      console.error('Failed to update subscriber:', error);
      alert('Failed to update subscriber status');
    }
  };

  const deleteUser = async (id: number) => {
    if (!confirm('Are you sure you want to delete this subscriber?')) return;

    try {
      await telegramAPI.deleteSubscriber(id);
      setUsers(users.filter(u => u.id !== id));
    } catch (error) {
      console.error('Failed to delete subscriber:', error);
      alert('Failed to delete subscriber');
    }
  };

  const handleAddUser = async () => {
    if (newUser.name && newUser.chatId) {
      try {
        const added = await telegramAPI.addSubscriber({
          name: newUser.name,
          chat_id: newUser.chatId,
          role: newUser.role
        });
        setUsers([...users, {
          id: added.id,
          name: added.name,
          chat_id: added.chat_id,
          role: added.role,
          active: added.active,
          avatar_color: added.avatar_color || 'bg-cyan-600'
        }]);
        setNewUser({ name: '', chatId: '', role: 'Trader' });
        setShowAddModal(false);
      } catch (error) {
        console.error('Failed to add subscriber:', error);
        alert('Failed to add subscriber');
      }
    }
  };

  const handleSaveToken = async () => {
    try {
      await telegramAPI.updateConfig({ bot_token: botToken });
      setIsEditingToken(false);
      alert('Bot token updated successfully');
    } catch (error) {
      console.error('Failed to update token:', error);
      alert('Failed to update bot token');
    }
  };

  const handleToggleTestMode = async () => {
    try {
      const newTestMode = !testMode;
      await telegramAPI.updateConfig({ test_mode: newTestMode });
      setTestMode(newTestMode);
    } catch (error) {
      console.error('Failed to toggle test mode:', error);
      alert('Failed to toggle test mode');
    }
  };

  const handleBroadcast = async () => {
    if (!broadcastMessage.trim()) return;

    try {
      setIsSending(true);
      const result = await telegramAPI.broadcast({
        message: broadcastMessage,
        message_type: 'INFO'
      });
      alert(result.message || 'Message broadcasted successfully');
      setBroadcastMessage('');

      // Reload messages to show the new broadcast
      const messageHistory = await telegramAPI.getMessages();
      const processedMessages = messageHistory.map((msg: any) => ({
        ...msg,
        date: isToday(msg.date) ? 'Today' : isYesterday(msg.date) ? 'Yesterday' : msg.date
      }));
      setMessages(processedMessages);
    } catch (error) {
      console.error('Failed to broadcast message:', error);
      alert('Failed to broadcast message');
    } finally {
      setIsSending(false);
    }
  };

  const handleRoleChange = async (id: number, newRole: 'Admin' | 'Trader' | 'Viewer') => {
    try {
      await telegramAPI.updateSubscriber(id, { role: newRole });
      setUsers(users.map(u => u.id === id ? { ...u, role: newRole } : u));
    } catch (error) {
      console.error('Failed to update role:', error);
      alert('Failed to update subscriber role');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-zinc-500">Loading telegram configuration...</div>
      </div>
    );
  }

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
              <p className="text-xs text-zinc-500 font-mono hidden sm:block">QuantTrade Bot • {botUsername || '@quant_alpha_bot'}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span className="text-xs font-medium text-emerald-400">ONLINE</span>
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-95">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <Bot size={48} className="text-zinc-700 mb-4" />
              <p className="text-zinc-500 text-sm">Henüz broadcast mesajı yok</p>
              <p className="text-zinc-600 text-xs mt-2">İlk mesajınızı göndererek başlayın</p>
            </div>
          ) : (
            ['Today', 'Yesterday'].map(dateGroup => {
              const groupMessages = messages.filter(m => m.date === dateGroup);
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
                      <div key={msg.id} className="flex gap-3">
                        <div className="flex-1 bg-gradient-to-br from-blue-950/30 to-purple-950/30 backdrop-blur-md rounded-2xl p-4 border border-white/10 shadow-xl">
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-bold text-zinc-400">{msg.symbol}</span>
                              <span className={`text-[10px] px-2 py-0.5 rounded-full ${msg.type === 'BUY' ? 'bg-emerald-500/20 text-emerald-400' : msg.type === 'SELL' ? 'bg-rose-500/20 text-rose-400' : 'bg-sky-500/20 text-sky-400'}`}>
                                {msg.type}
                              </span>
                            </div>
                            <span className="text-[10px] text-zinc-600 font-mono">{msg.timestamp}</span>
                          </div>
                          <p className="text-sm text-zinc-300 leading-relaxed whitespace-pre-wrap">{msg.message}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Broadcast Input Area */}
        <div className="p-4 border-t border-white/5 bg-zinc-900 flex gap-3">
          <input
            type="text"
            placeholder="Broadcast manual message..."
            value={broadcastMessage}
            onChange={(e) => setBroadcastMessage(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && !isSending && handleBroadcast()}
            disabled={isSending}
            className="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2 text-sm text-zinc-200 focus:outline-none focus:border-sky-500 transition-colors disabled:opacity-50"
          />
          <button
            onClick={handleBroadcast}
            disabled={isSending || !broadcastMessage.trim()}
            className="px-4 py-2 bg-sky-600 hover:bg-sky-500 rounded-lg text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSending ? <Radio size={18} className="animate-spin" /> : <Send size={18} />}
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
              <input type="text" value={botUsername} readOnly className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-400 focus:outline-none" />
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
                  onClick={() => {
                    if (isEditingToken) {
                      handleSaveToken();
                    } else {
                      setIsEditingToken(true);
                    }
                  }}
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
                  <span className="text-xs text-yellow-200/80">Test Mode {testMode ? 'Active' : 'Inactive'}</span>
                </div>
                <button
                  onClick={handleToggleTestMode}
                  className={`relative inline-block w-8 h-4 rounded-full cursor-pointer transition-colors ${testMode ? 'bg-yellow-500/20' : 'bg-zinc-700'}`}
                >
                  <span className={`absolute top-0.5 w-3 h-3 rounded-full shadow-sm transition-all duration-300 ${testMode ? 'left-4 bg-yellow-500' : 'left-0.5 bg-zinc-500'}`}></span>
                </button>
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
                  onChange={e => setNewUser({ ...newUser, name: e.target.value })}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded p-2 text-sm text-white focus:border-sky-500 outline-none"
                />
                <input
                  type="text"
                  placeholder="Chat ID (e.g. 123456789)"
                  value={newUser.chatId}
                  onChange={e => setNewUser({ ...newUser, chatId: e.target.value })}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded p-2 text-sm text-white focus:border-sky-500 outline-none font-mono"
                />
                <select
                  value={newUser.role}
                  onChange={e => setNewUser({ ...newUser, role: e.target.value as any })}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded p-2 text-sm text-white focus:border-sky-500 outline-none"
                >
                  <option value="Viewer">Viewer</option>
                  <option value="Trader">Trader</option>
                  <option value="Admin">Admin</option>
                </select>
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
                <div className="flex items-center gap-3 flex-1">
                  <div className={`w-8 h-8 rounded-full ${user.avatar_color} flex items-center justify-center text-xs font-bold text-white shadow-lg`}>
                    {user.name.substring(0, 1)}
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-zinc-200">{user.name}</p>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[10px] font-mono text-zinc-500">{user.chat_id}</span>
                      <select
                        value={user.role}
                        onChange={(e) => handleRoleChange(user.id, e.target.value as any)}
                        className="text-[10px] px-1.5 py-0.5 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded text-zinc-300 focus:outline-none focus:border-sky-500 cursor-pointer transition-colors"
                      >
                        <option value="Viewer">Viewer</option>
                        <option value="Trader">Trader</option>
                        <option value="Admin">Admin</option>
                      </select>
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
