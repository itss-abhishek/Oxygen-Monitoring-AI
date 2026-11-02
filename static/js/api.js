/**
 * static/js/api.js — OxySense API Client Layer
 */

const OxyAPI = {
  async getOverview() {
    const res = await fetch('/api/overview');
    return res.json();
  },

  async getLiveStream() {
    const res = await fetch('/api/live-stream');
    return res.json();
  },

  async getHistory(range = '15m', cylinderId = '') {
    const query = new URLSearchParams({ range });
    if (cylinderId) query.set('cylinder_id', cylinderId);
    const res = await fetch(`/api/history?${query}`);
    return res.json();
  },

  async getCylinderTelemetry(cylinderId, limit = 200) {
    const res = await fetch(`/api/cylinders/${encodeURIComponent(cylinderId)}/telemetry?limit=${limit}`);
    return res.json();
  },

  async getCylinders(search = '', status = 'ALL') {
    const query = new URLSearchParams({ search, status });
    const res = await fetch(`/api/cylinders?${query}`);
    return res.json();
  },

  async getCylinderDetail(id) {
    const res = await fetch(`/api/cylinders/${id}`);
    return res.json();
  },

  async setActiveCylinder(cylinderId) {
    const res = await fetch('/api/cylinders/active', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cylinder_id: cylinderId })
    });
    return res.json();
  },

  async getActiveCylinder() {
    const res = await fetch('/api/cylinders/active');
    return res.json();
  },

  async getAlerts() {
    const res = await fetch('/api/alerts');
    return res.json();
  },

  async acknowledgeAlert(alertId) {
    const res = await fetch('/api/alerts/acknowledge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ alert_id: alertId })
    });
    return res.json();
  },

  async triggerScenario(scenario) {
    const res = await fetch('/api/simulation/scenario', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario })
    });
    return res.json();
  },

  async getAiInsights() {
    const res = await fetch('/api/ai-insights');
    return res.json();
  },

  async getSettings() {
    const res = await fetch('/api/settings');
    return res.json();
  },

  async saveSettings(settings) {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings)
    });
    return res.json();
  },

  async login(email, password) {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    return res.json();
  },

  async logout() {
    const res = await fetch('/api/auth/logout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    return res.json();
  },

  async getSession() {
    try {
      const res = await fetch('/api/auth/session');
      return res.json();
    } catch (err) {
      return { authenticated: false };
    }
  }
};
