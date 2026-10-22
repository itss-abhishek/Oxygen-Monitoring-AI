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

  async getHistory(range = '15m') {
    const res = await fetch(`/api/history?range=${range}`);
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
  }
};
