/**
 * static/js/app.js — OxySense Web Dashboard Main Application Controller
 */

document.addEventListener('DOMContentLoaded', () => {
  // Initialize Lucide Icons
  if (window.lucide) {
    lucide.createIcons();
  }

  // State
  let streamInterval = null;
  let isStreaming = true;
  let currentView = 'view-overview';

  // ═════════════════════════════════════════════════════════════════════════
  // 1. Navigation & View Switching
  // ═════════════════════════════════════════════════════════════════════════
  const navItems = document.querySelectorAll('.sidebar-menu .nav-item');
  const pageViews = document.querySelectorAll('.page-view');

  function switchView(viewId) {
    currentView = viewId;
    navItems.forEach(item => {
      if (item.getAttribute('data-view') === viewId) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    pageViews.forEach(view => {
      if (view.id === viewId) {
        view.classList.add('active');
      } else {
        view.classList.remove('active');
      }
    });

    // View-specific initializers
    if (viewId === 'view-overview') {
      OxyCharts.initOverviewCharts();
    } else if (viewId === 'view-live') {
      OxyCharts.initLiveFullChart();
    } else if (viewId === 'view-cylinders') {
      loadCylinderFleet();
    } else if (viewId === 'view-alerts') {
      loadAlertsView();
    } else if (viewId === 'view-ai') {
      loadAiInsights();
    } else if (viewId === 'view-history') {
      loadHistoryTable();
    } else if (viewId === 'view-settings') {
      loadSettingsForm();
    }

    if (window.lucide) lucide.createIcons();
  }

  navItems.forEach(item => {
    item.addEventListener('click', () => {
      const targetView = item.getAttribute('data-view');
      switchView(targetView);
      // Close mobile menu if open
      document.getElementById('sidebar')?.classList.remove('mobile-open');
    });
  });

  // Mobile menu toggle
  document.getElementById('mobile-menu-btn')?.addEventListener('click', () => {
    document.getElementById('sidebar')?.classList.toggle('mobile-open');
  });

  // Quick jump button from overview to fleet
  document.getElementById('btn-view-all-cylinders')?.addEventListener('click', () => {
    switchView('view-cylinders');
  });

  // Header notif icon jump to alerts
  document.getElementById('header-notif-btn')?.addEventListener('click', () => {
    switchView('view-alerts');
  });

  // ═════════════════════════════════════════════════════════════════════════
  // 2. Telemetry Polling & Live Stream
  // ═════════════════════════════════════════════════════════════════════════
  async function pollLiveTelemetry() {
    try {
      const data = await OxyAPI.getLiveStream();
      renderOverviewMetrics(data);
      OxyCharts.updateFromHistory(data.history);

      // Also refresh tables if currently visible
      if (currentView === 'view-cylinders') {
        loadCylinderFleet(false);
      } else if (currentView === 'view-history') {
        renderHistoryRows(data.history);
      }
    } catch (err) {
      console.error('Telemetry polling error:', err);
    }
  }

  function startStreaming() {
    if (streamInterval) clearInterval(streamInterval);
    pollLiveTelemetry();
    streamInterval = setInterval(pollLiveTelemetry, 2000);
    isStreaming = true;
    updateStreamButtonState();
  }

  function stopStreaming() {
    if (streamInterval) {
      clearInterval(streamInterval);
      streamInterval = null;
    }
    isStreaming = false;
    updateStreamButtonState();
  }

  function updateStreamButtonState() {
    const btn = document.getElementById('btn-toggle-stream');
    if (!btn) return;
    if (isStreaming) {
      btn.innerHTML = '<i data-lucide="pause"></i> Pause Stream';
      btn.className = 'btn btn-primary';
    } else {
      btn.innerHTML = '<i data-lucide="play"></i> Resume Stream';
      btn.className = 'btn btn-warning-soft';
    }
    if (window.lucide) lucide.createIcons();
  }

  document.getElementById('btn-toggle-stream')?.addEventListener('click', () => {
    if (isStreaming) {
      stopStreaming();
      showToast('Live telemetry stream paused');
    } else {
      startStreaming();
      showToast('Live telemetry stream resumed');
    }
  });

  // ═════════════════════════════════════════════════════════════════════════
  // 3. Overview Metrics Rendering
  // ═════════════════════════════════════════════════════════════════════════
  function renderOverviewMetrics(data) {
    if (!data) return;

    // Clock & Connection
    document.getElementById('live-clock').textContent = data.device.last_update || '--:--:--';
    
    const pill = document.getElementById('esp32-status-pill');
    const pillText = document.getElementById('esp32-status-text');
    if (data.device.esp32_connected) {
      pill.className = 'status-pill online';
      pillText.textContent = 'ESP32 Connected (Simulated)';
    } else {
      pill.className = 'status-pill offline';
      pillText.textContent = 'Sensor Disconnected';
    }

    // Card A: Pressure
    const pVal = data.pressure.value;
    const pUnit = data.pressure.unit;
    document.getElementById('val-pressure-primary').textContent = data.device.esp32_connected ? pVal : '--';
    document.getElementById('unit-pressure-primary').textContent = pUnit;
    document.getElementById('val-pressure-secondary').textContent = data.device.esp32_connected
      ? `${data.pressure.bar} bar (${data.pressure.psi} PSI)`
      : 'Telemetry Unavailable';
    
    const pFill = document.getElementById('pressure-progress');
    const pPct = data.pressure.percentage || 0;
    pFill.style.width = `${Math.min(100, Math.max(0, pPct))}%`;
    if (data.status.level === 'CRITICAL') {
      pFill.style.background = 'var(--status-critical)';
    } else if (data.status.level === 'LOW_PRESSURE') {
      pFill.style.background = 'var(--status-warning)';
    } else {
      pFill.style.background = 'linear-gradient(90deg, var(--blue-primary), var(--teal-primary))';
    }

    // Card B: Flow
    const fVal = data.flow.value;
    document.getElementById('val-flow-primary').textContent = data.device.esp32_connected ? fVal.toFixed(1) : '--';
    document.getElementById('val-flow-prescribed').textContent = `Prescribed: ${data.flow.prescribed.toFixed(1)} L/min`;
    const fFill = document.getElementById('flow-progress');
    fFill.style.width = `${Math.min(100, (fVal / 10.0) * 100)}%`;
    const flowDiff = (fVal - data.flow.prescribed).toFixed(1);
    document.getElementById('flow-diff-label').textContent = `${flowDiff > 0 ? '+' : ''}${flowDiff} L/min delta`;

    // Card C: ETE
    document.getElementById('val-ete-primary').textContent = data.ete.display;
    if (data.ete.valid) {
      document.getElementById('val-ete-litres').textContent = `Est. Usable: ~${data.ete.remaining_litres} L remaining`;
    } else {
      document.getElementById('val-ete-litres').textContent = data.ete.reason || 'Estimate unavailable';
    }

    // Card D: Status
    const badge = document.getElementById('val-status-badge');
    badge.textContent = data.status.label;
    badge.className = `status-pill-large ${data.status.badge_class}`;

    const iconWrap = document.getElementById('status-icon-wrap');
    if (data.status.level === 'CRITICAL') {
      iconWrap.className = 'icon-wrap red';
      document.getElementById('val-status-desc').textContent = 'Urgent: Reserve nearing exhaustion. Stage replacement cylinder.';
    } else if (data.status.level === 'LOW_PRESSURE') {
      iconWrap.className = 'icon-wrap orange';
      document.getElementById('val-status-desc').textContent = 'Warning: Pressure below configured clinical threshold.';
    } else if (data.status.level === 'SENSOR_DISCONNECTED') {
      iconWrap.className = 'icon-wrap gray';
      document.getElementById('val-status-desc').textContent = 'Notice: Hardware communication interrupted or node offline.';
    } else {
      iconWrap.className = 'icon-wrap green';
      document.getElementById('val-status-desc').textContent = 'All telemetry parameters within normal operational envelope.';
    }

    // Alert Badges
    const alertCount = data.active_alerts_count || 0;
    document.getElementById('header-notif-badge').textContent = alertCount;
    document.getElementById('nav-alert-count').textContent = alertCount;
    document.getElementById('val-active-alerts-tag').textContent = `${alertCount} Active Alert${alertCount === 1 ? '' : 's'}`;

    // Overview Fleet Table
    renderOverviewFleetTable();
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 4. Fleet & Cylinders View
  // ═════════════════════════════════════════════════════════════════════════
  async function renderOverviewFleetTable() {
    try {
      const data = await OxyAPI.getCylinders('', 'ALL');
      const tbody = document.getElementById('tbody-overview-cylinders');
      if (!tbody) return;
      tbody.innerHTML = '';

      data.cylinders.slice(0, 4).forEach(c => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${c.id}</strong></td>
          <td>${c.ward}</td>
          <td>${c.pressure_psi} PSI <span class="text-muted">(${c.pressure_bar} bar)</span></td>
          <td>${c.ete}</td>
          <td><span class="status-pill-large badge-${c.status.toLowerCase()}">${formatStatus(c.status)}</span></td>
        `;
        tbody.appendChild(tr);
      });
    } catch (err) {
      console.error('Fleet preview error:', err);
    }
  }

  async function loadCylinderFleet(showSpinner = true) {
    const searchVal = document.getElementById('input-cylinder-search')?.value || '';
    const statusVal = document.getElementById('select-cylinder-status')?.value || 'ALL';
    const tbody = document.getElementById('tbody-fleet-cylinders');
    if (!tbody) return;

    try {
      const data = await OxyAPI.getCylinders(searchVal, statusVal);
      tbody.innerHTML = '';

      if (!data.cylinders.length) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;padding:30px;color:#94a3b8;">No cylinders match the specified filter.</td></tr>`;
        return;
      }

      data.cylinders.forEach(c => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${c.id}</strong></td>
          <td>${c.ward}<br><small class="text-muted">${c.patient}</small></td>
          <td>${c.type}</td>
          <td><strong>${c.pressure_psi} PSI</strong> <br><small class="text-muted">${c.pressure_bar} bar</small></td>
          <td>${c.flow_lpm.toFixed(1)} L/min</td>
          <td><strong>${c.ete}</strong></td>
          <td><span class="status-pill-large badge-${c.status.toLowerCase()}">${formatStatus(c.status)}</span></td>
          <td><small class="font-mono text-muted">${c.sensor_id}</small></td>
          <td>
            <button class="btn btn-outline-sm btn-view-cyl-detail" data-id="${c.id}">
              Details
            </button>
          </td>
        `;
        tbody.appendChild(tr);
      });

      // Bind modal detail triggers
      document.querySelectorAll('.btn-view-cyl-detail').forEach(b => {
        b.addEventListener('click', () => openCylinderModal(b.getAttribute('data-id')));
      });
    } catch (err) {
      console.error('Error loading cylinder fleet:', err);
    }
  }

  document.getElementById('input-cylinder-search')?.addEventListener('keyup', () => loadCylinderFleet(false));
  document.getElementById('select-cylinder-status')?.addEventListener('change', () => loadCylinderFleet(false));

  async function openCylinderModal(cylId) {
    try {
      const res = await OxyAPI.getCylinderDetail(cylId);
      if (!res.success) return;
      const c = res.cylinder;
      document.getElementById('modal-cylinder-id').textContent = `${c.id} — Diagnostic Specification`;
      document.getElementById('modal-content').innerHTML = `
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:18px;">
          <div><strong>Ward / Location:</strong><br>${c.ward}</div>
          <div><strong>Assigned Patient:</strong><br>${c.patient}</div>
          <div><strong>Cylinder Model:</strong><br>${c.type} (${c.capacity_l} L capacity)</div>
          <div><strong>Telemetry Node:</strong><br><code>${c.sensor_id}</code> (Battery: ${c.battery_pct}%)</div>
          <div><strong>Current Pressure:</strong><br><span style="font-size:1.2rem;font-weight:700;">${c.pressure_psi} PSI</span> (${c.pressure_bar} bar)</div>
          <div><strong>Flow Rate:</strong><br><span style="font-size:1.2rem;font-weight:700;">${c.flow_lpm} L/min</span></div>
          <div><strong>Estimated Time Remaining:</strong><br><span style="font-size:1.1rem;font-weight:700;color:var(--teal-primary);">${c.ete}</span></div>
          <div><strong>Operational Status:</strong><br><span class="status-pill-large badge-${c.status.toLowerCase()}">${formatStatus(c.status)}</span></div>
        </div>
        <div class="ete-disclaimer-box">
          <span>⚠️ All displayed telemetry metrics reflect software demonstration data. For real clinical decisions, inspect certified mechanical gauges.</span>
        </div>
      `;
      document.getElementById('cylinder-modal').classList.add('active');
    } catch (err) {
      console.error('Modal detail fetch error:', err);
    }
  }

  document.getElementById('modal-close')?.addEventListener('click', () => {
    document.getElementById('cylinder-modal').classList.remove('active');
  });

  document.getElementById('cylinder-modal')?.addEventListener('click', (e) => {
    if (e.target.id === 'cylinder-modal') {
      document.getElementById('cylinder-modal').classList.remove('active');
    }
  });

  // ═════════════════════════════════════════════════════════════════════════
  // 5. Alerts & Simulation Controls
  // ═════════════════════════════════════════════════════════════════════════
  async function loadAlertsView() {
    try {
      const data = await OxyAPI.getAlerts();
      const activeContainer = document.getElementById('active-alerts-container');
      const histContainer = document.getElementById('historical-alerts-container');
      if (!activeContainer || !histContainer) return;

      activeContainer.innerHTML = '';
      histContainer.innerHTML = '';

      const unack = data.alerts.filter(a => !a.acknowledged);
      const ack = data.alerts.filter(a => a.acknowledged);

      document.getElementById('active-alert-counter').textContent = `${unack.length} Active`;

      if (!unack.length) {
        activeContainer.innerHTML = `<div style="padding:24px;text-align:center;color:#166534;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;font-weight:500;">All telemetry nominal. No active unacknowledged alerts.</div>`;
      } else {
        unack.forEach(a => {
          const div = document.createElement('div');
          div.className = `alert-item severity-${a.severity.toLowerCase()}`;
          const iconType = a.severity === 'CRITICAL' ? 'alert-triangle' : (a.severity === 'WARNING' ? 'alert-circle' : 'info');
          const boxClass = a.severity === 'CRITICAL' ? 'crit' : (a.severity === 'WARNING' ? 'warn' : 'info');
          div.innerHTML = `
            <div class="alert-left">
              <div class="alert-icon-box ${boxClass}">
                <i data-lucide="${iconType}"></i>
              </div>
              <div>
                <div class="alert-title">${a.title}</div>
                <div class="alert-desc">${a.description}</div>
                <div class="alert-meta">Timestamp: ${a.timestamp} · Severity: ${a.severity}</div>
              </div>
            </div>
            <button class="btn btn-outline-sm btn-ack-alert" data-id="${a.id}">
              Acknowledge
            </button>
          `;
          activeContainer.appendChild(div);
        });
      }

      ack.forEach(a => {
        const div = document.createElement('div');
        div.className = `alert-item severity-${a.severity.toLowerCase()}`;
        div.style.opacity = '0.75';
        div.innerHTML = `
          <div class="alert-left">
            <div class="alert-icon-box info">
              <i data-lucide="check"></i>
            </div>
            <div>
              <div class="alert-title">${a.title}</div>
              <div class="alert-desc">${a.description}</div>
              <div class="alert-meta">Logged: ${a.timestamp} · Acknowledged by Ward Staff</div>
            </div>
          </div>
        `;
        histContainer.appendChild(div);
      });

      if (window.lucide) lucide.createIcons();

      // Bind Acknowledge Buttons
      document.querySelectorAll('.btn-ack-alert').forEach(btn => {
        btn.addEventListener('click', async () => {
          const alertId = btn.getAttribute('data-id');
          await OxyAPI.acknowledgeAlert(alertId);
          showToast(`Alert ${alertId} acknowledged.`);
          loadAlertsView();
          pollLiveTelemetry();
        });
      });
    } catch (err) {
      console.error('Error loading alerts:', err);
    }
  }

  document.getElementById('btn-refresh-alerts')?.addEventListener('click', loadAlertsView);

  // Simulation Scenario Triggers
  document.getElementById('btn-sim-low')?.addEventListener('click', async () => {
    await OxyAPI.triggerScenario('LOW_PRESSURE');
    showToast('Simulation: Low Supply condition activated (42 Bar / 609 PSI)');
    pollLiveTelemetry();
  });

  document.getElementById('btn-sim-disconnect')?.addEventListener('click', async () => {
    await OxyAPI.triggerScenario('SENSOR_DISCONNECTED');
    showToast('Simulation: Sensor Disconnected / Telemetry Lost');
    pollLiveTelemetry();
  });

  document.getElementById('btn-sim-reset')?.addEventListener('click', async () => {
    await OxyAPI.triggerScenario('RESET');
    showToast('Simulation: Restored to nominal baseline (160 Bar / 2320 PSI)');
    pollLiveTelemetry();
  });

  // ═════════════════════════════════════════════════════════════════════════
  // 6. AI Insights View
  // ═════════════════════════════════════════════════════════════════════════
  async function loadAiInsights() {
    try {
      const data = await OxyAPI.getAiInsights();
      
      document.getElementById('ai-engine-full-name').textContent = data.engine;
      document.getElementById('ai-engine-tag').textContent = data.is_llm_active ? 'Cloud LLM' : 'Rule Engine';
      document.getElementById('ai-timestamp').textContent = `Last analyzed: ${data.timestamp}`;
      document.getElementById('ai-main-summary').textContent = data.summary;

      // Update overview widget snippet as well
      document.getElementById('ai-overview-summary').textContent = data.summary;
      const ovActions = document.getElementById('ai-overview-actions');
      if (ovActions) {
        ovActions.innerHTML = '';
        data.operational_suggestions.slice(0, 2).forEach(act => {
          ovActions.innerHTML += `<div class="ai-action-item"><i data-lucide="check-circle-2"></i><span>${act}</span></div>`;
        });
      }

      // Populate Conditions
      const condList = document.getElementById('ai-conditions-list');
      if (condList) {
        condList.innerHTML = '';
        data.detected_conditions.forEach(c => {
          condList.innerHTML += `<li>${c}</li>`;
        });
      }

      // Populate Actions
      const actContainer = document.getElementById('ai-actions-container');
      if (actContainer) {
        actContainer.innerHTML = '';
        data.operational_suggestions.forEach(act => {
          actContainer.innerHTML += `<div class="action-pill-item"><i data-lucide="arrow-right-circle"></i> ${act}</div>`;
        });
      }

      // Populate Triggers
      const trigBox = document.getElementById('ai-triggers-box');
      if (trigBox) {
        trigBox.innerHTML = '';
        data.trigger_rules.forEach(r => {
          trigBox.innerHTML += `<div class="rule-code-tag">${r}</div>`;
        });
      }

      if (window.lucide) lucide.createIcons();
    } catch (err) {
      console.error('AI Insights load error:', err);
    }
  }

  document.getElementById('btn-refresh-ai')?.addEventListener('click', () => {
    showToast('Re-analyzing telemetry...');
    loadAiInsights();
  });

  // ═════════════════════════════════════════════════════════════════════════
  // 7. Historical Reports View
  // ═════════════════════════════════════════════════════════════════════════
  async function loadHistoryTable() {
    try {
      const data = await OxyAPI.getHistory('24h');
      renderHistoryRows(data.points);
    } catch (err) {
      console.error('History load error:', err);
    }
  }

  function renderHistoryRows(points) {
    const tbody = document.getElementById('tbody-history-logs');
    if (!tbody || !points) return;
    tbody.innerHTML = '';

    // Reverse to show newest first
    const reversed = [...points].reverse().slice(0, 25);
    reversed.forEach(p => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${p.timestamp}</td>
        <td>${p.pressure_bar}</td>
        <td><strong>${p.pressure_psi}</strong></td>
        <td>${p.flow_lpm.toFixed(2)}</td>
        <td>${p.remaining_pct}%</td>
        <td>${p.ete_minutes ? `${Math.floor(p.ete_minutes / 60)}h ${Math.round(p.ete_minutes % 60)}m` : 'N/A'}</td>
        <td><span class="status-pill-large badge-${p.status.toLowerCase()}">${formatStatus(p.status)}</span></td>
        <td><span class="badge-tag">Synthetic Hash OK</span></td>
      `;
      tbody.appendChild(tr);
    });
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 8. Settings View
  // ═════════════════════════════════════════════════════════════════════════
  async function loadSettingsForm() {
    try {
      const res = await OxyAPI.getSettings();
      const cfg = res.config;
      document.getElementById('setting-warning').value = cfg.warning_threshold_bar;
      document.getElementById('setting-critical').value = cfg.critical_threshold_bar;
      document.getElementById('setting-prescribed').value = cfg.prescribed_flow_lpm;
      document.getElementById('setting-capacity').value = cfg.cylinder_capacity_litres;
      document.getElementById('setting-unit').value = cfg.pressure_unit;
    } catch (err) {
      console.error('Settings load error:', err);
    }
  }

  document.getElementById('form-settings')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
      warning_threshold_bar: document.getElementById('setting-warning').value,
      critical_threshold_bar: document.getElementById('setting-critical').value,
      prescribed_flow_lpm: document.getElementById('setting-prescribed').value,
      cylinder_capacity_litres: document.getElementById('setting-capacity').value,
      pressure_unit: document.getElementById('setting-unit').value
    };
    try {
      await OxyAPI.saveSettings(payload);
      showToast('Settings saved successfully!');
      pollLiveTelemetry();
    } catch (err) {
      showToast('Failed to save settings');
    }
  });

  // Range pill buttons on chart
  document.querySelectorAll('.btn-pill').forEach(pill => {
    pill.addEventListener('click', async () => {
      document.querySelectorAll('.btn-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      const r = pill.getAttribute('data-range');
      const hist = await OxyAPI.getHistory(r);
      OxyCharts.updateFromHistory(hist.points);
    });
  });

  // ═════════════════════════════════════════════════════════════════════════
  // 9. Utilities & Helpers
  // ═════════════════════════════════════════════════════════════════════════
  function formatStatus(status) {
    if (status === 'NORMAL') return 'Normal';
    if (status === 'LOW_PRESSURE') return 'Low Supply';
    if (status === 'CRITICAL') return 'Critical';
    if (status === 'SENSOR_DISCONNECTED') return 'Disconnected';
    return status;
  }

  function showToast(message) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = `<i data-lucide="info"></i> <span>${message}</span>`;
    container.appendChild(toast);
    if (window.lucide) lucide.createIcons();

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3200);
  }

  // ═════════════════════════════════════════════════════════════════════════
  // Initial Boot
  // ═════════════════════════════════════════════════════════════════════════
  OxyCharts.initOverviewCharts();
  loadAiInsights();
  startStreaming();
});
