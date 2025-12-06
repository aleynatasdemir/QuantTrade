/**
 * API Client for QuantTrade Backend
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Portfolio API
export const portfolioAPI = {
  getState: async () => {
    const response = await fetch(`${API_BASE_URL}/api/portfolio/state`);
    if (!response.ok) throw new Error('Failed to fetch portfolio state');
    return response.json();
  },

  getEquity: async () => {
    const response = await fetch(`${API_BASE_URL}/api/portfolio/equity`);
    if (!response.ok) throw new Error('Failed to fetch equity history');
    return response.json();
  },

  getTrades: async () => {
    const response = await fetch(`${API_BASE_URL}/api/portfolio/trades`);
    if (!response.ok) throw new Error('Failed to fetch trades');
    return response.json();
  },

  getSummary: async () => {
    const response = await fetch(`${API_BASE_URL}/api/portfolio/summary`);
    if (!response.ok) throw new Error('Failed to fetch portfolio summary');
    return response.json();
  },
};

// Pipeline API
export const pipelineAPI = {
  run: async (script_type: string = 'pipeline') => {
    const response = await fetch(`${API_BASE_URL}/api/pipeline/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ script: script_type })
    });
    if (!response.ok) throw new Error('Failed to start pipeline');
    return response.json();
  },

  stop: async () => {
    const response = await fetch(`${API_BASE_URL}/api/pipeline/stop`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error('Failed to stop pipeline');
    return response.json();
  },

  getStatus: async () => {
    const response = await fetch(`${API_BASE_URL}/api/pipeline/status`);
    if (!response.ok) throw new Error('Failed to fetch pipeline status');
    return response.json();
  },

  getLogs: async (sinceLine: number = 0) => {
    const response = await fetch(`${API_BASE_URL}/api/pipeline/logs?since_line=${sinceLine}`);
    if (!response.ok) throw new Error('Failed to fetch pipeline logs');
    return response.json();
  },
};

// Telegram API
export const telegramAPI = {
  getConfig: async () => {
    const response = await fetch(`${API_BASE_URL}/api/telegram/config`);
    if (!response.ok) throw new Error('Failed to fetch telegram config');
    return response.json();
  },

  updateConfig: async (config: { bot_token?: string; bot_username?: string; test_mode?: boolean }) => {
    const response = await fetch(`${API_BASE_URL}/api/telegram/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    if (!response.ok) throw new Error('Failed to update telegram config');
    return response.json();
  },

  getSubscribers: async () => {
    const response = await fetch(`${API_BASE_URL}/api/telegram/subscribers`);
    if (!response.ok) throw new Error('Failed to fetch subscribers');
    return response.json();
  },

  addSubscriber: async (subscriber: { name: string; chat_id: string; role?: string }) => {
    const response = await fetch(`${API_BASE_URL}/api/telegram/subscribers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(subscriber),
    });
    if (!response.ok) throw new Error('Failed to add subscriber');
    return response.json();
  },

  updateSubscriber: async (id: number, update: { name?: string; active?: boolean; role?: string }) => {
    const response = await fetch(`${API_BASE_URL}/api/telegram/subscribers/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(update),
    });
    if (!response.ok) throw new Error('Failed to update subscriber');
    return response.json();
  },

  deleteSubscriber: async (id: number) => {
    const response = await fetch(`${API_BASE_URL}/api/telegram/subscribers/${id}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete subscriber');
    return response.json();
  },

  broadcast: async (message: { message: string; message_type?: string; symbol?: string; price?: number }) => {
    const response = await fetch(`${API_BASE_URL}/api/telegram/broadcast`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(message),
    });
    if (!response.ok) throw new Error('Failed to broadcast message');
    return response.json();
  },

  getMessages: async (limit: number = 50) => {
    const response = await fetch(`${API_BASE_URL}/api/telegram/messages?limit=${limit}`);
    if (!response.ok) throw new Error('Failed to fetch message history');
    return response.json();
  },
};

// GPT Analysis API
export const gptAPI = {
  getAnalysis: async () => {
    const response = await fetch(`${API_BASE_URL}/api/gpt/analysis`);
    if (!response.ok) throw new Error('Failed to fetch GPT analysis');
    return response.json();
  },
};

