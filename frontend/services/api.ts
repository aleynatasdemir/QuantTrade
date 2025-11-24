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
  run: async (script: 'pipeline' | 'portfolio_manager' = 'pipeline') => {
    const response = await fetch(`${API_BASE_URL}/api/pipeline/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ script }),
    });
    if (!response.ok) throw new Error('Failed to run pipeline');
    return response.json();
  },

  getStatus: async () => {
    const response = await fetch(`${API_BASE_URL}/api/pipeline/status`);
    if (!response.ok) throw new Error('Failed to fetch pipeline status');
    return response.json();
  },

  getLogs: async (maxLines: number = 100) => {
    const response = await fetch(`${API_BASE_URL}/api/pipeline/logs?max_lines=${maxLines}`);
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
};
