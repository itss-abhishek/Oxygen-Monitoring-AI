/**
 * static/js/charts.js — Medical-Grade Chart.js Management for OxySense
 */

const OxyCharts = {
  pressureChart: null,
  flowChart: null,
  reserveChart: null,
  eteChart: null,
  liveFullChart: null,
  homePreviewChart: null,

  _createGradient(ctx, topColor, bottomColor) {
    try {
      const grad = ctx.createLinearGradient(0, 0, 0, 260);
      grad.addColorStop(0, topColor);
      grad.addColorStop(0.7, topColor.replace(/[\d.]+\)$/g, '0.06)'));
      grad.addColorStop(1, bottomColor);
      return grad;
    } catch {
      return topColor;
    }
  },

  initHomePreviewChart() {
    const canvas = document.getElementById('chart-home-preview');
    if (canvas && !this.homePreviewChart) {
      const ctx2d = canvas.getContext('2d');
      const gradP = this._createGradient(ctx2d, 'rgba(13, 148, 136, 0.32)', 'rgba(13, 148, 136, 0.00)');
      const gradF = this._createGradient(ctx2d, 'rgba(2, 132, 199, 0.20)', 'rgba(2, 132, 199, 0.00)');

      // Pre-fill with realistic starting points so both lines render immediately
      const defaultLabels = ['00:00', '00:02', '00:04', '00:06', '00:08', '00:10', '00:12', '00:14', '00:16', '00:18', '00:20'];
      const defaultPressures = [2165, 2160, 2155, 2152, 2150, 2148, 2145, 2142, 2140, 2138, 2135];
      const defaultFlows = [2.0, 2.0, 2.1, 2.0, 1.9, 2.0, 2.0, 2.1, 2.0, 1.9, 2.0];

      this.homePreviewChart = new Chart(canvas, {
        type: 'line',
        data: {
          labels: defaultLabels,
          datasets: [
            {
              label: 'Pressure (PSI)',
              data: defaultPressures,
              borderColor: '#0d9488',
              backgroundColor: gradP,
              borderWidth: 2.5,
              tension: 0.38,
              fill: true,
              pointRadius: 0,
              yAxisID: 'y'
            },
            {
              label: 'Flow Rate (L/min)',
              data: defaultFlows,
              borderColor: '#0284c7',
              backgroundColor: gradF,
              borderWidth: 2.2,
              borderDash: [4, 3],
              tension: 0.35,
              fill: false,
              pointRadius: 0,
              yAxisID: 'y1'
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: {
            mode: 'index',
            intersect: false
          },
          plugins: {
            legend: {
              display: true,
              position: 'top',
              align: 'end',
              labels: {
                boxWidth: 10,
                boxHeight: 10,
                padding: 10,
                font: { size: 10.5, weight: '600' },
                color: document.documentElement.classList.contains('dark') ? '#cbd5e1' : '#64748b'
              }
            },
            tooltip: {
              enabled: true,
              callbacks: {
                label: function(ctx) {
                  if (ctx.datasetIndex === 0) {
                    return ` Pressure: ${ctx.parsed.y} PSI`;
                  }
                  return ` Flow Rate: ${ctx.parsed.y.toFixed(1)} L/min`;
                }
              }
            }
          },
          scales: {
            x: { display: false },
            y: {
              display: false,
              position: 'left'
            },
            y1: {
              display: false,
              position: 'right',
              min: 0,
              max: 6
            }
          }
        }
      });
    }
  },

  initOverviewCharts() {
    const ctxP = document.getElementById('chart-pressure');
    const ctxF = document.getElementById('chart-flow');
    const ctxR = document.getElementById('chart-reserve');
    const ctxE = document.getElementById('chart-ete');

    if (ctxP && !this.pressureChart) {
      const ctx2dP = ctxP.getContext('2d');
      const gradP = this._createGradient(ctx2dP, 'rgba(2, 132, 199, 0.32)', 'rgba(2, 132, 199, 0.00)');

      this.pressureChart = new Chart(ctxP, {
        type: 'line',
        data: {
          labels: [],
          datasets: [{
            label: 'Cylinder Pressure (PSI)',
            data: [],
            borderColor: '#0284c7',
            backgroundColor: gradP,
            borderWidth: 2.6,
            tension: 0.32,
            fill: true,
            pointRadius: (ctx) => (ctx.dataIndex === ctx.dataset.data.length - 1 ? 5 : 0),
            pointBackgroundColor: '#0284c7',
            pointBorderColor: '#ffffff',
            pointBorderWidth: 2,
            pointHoverRadius: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 300 },
          plugins: {
            legend: { display: false },
            tooltip: {
              mode: 'index',
              intersect: false,
              backgroundColor: 'rgba(15, 23, 42, 0.94)',
              titleColor: '#38bdf8',
              bodyColor: '#ffffff',
              borderColor: '#0284c7',
              borderWidth: 1,
              padding: 10,
              boxPadding: 4,
              callbacks: {
                label: ctx => ` Pressure: ${ctx.parsed.y} PSI (${(ctx.parsed.y / 14.5038).toFixed(1)} Bar)`
              }
            }
          },
          scales: {
            x: {
              grid: { color: 'rgba(148, 163, 184, 0.12)' },
              ticks: { color: '#94a3b8', maxTicksLimit: 7 }
            },
            y: {
              grid: { color: 'rgba(148, 163, 184, 0.12)' },
              title: { display: true, text: 'Pressure (PSI)', color: '#0284c7', font: { weight: 600 } },
              ticks: {
                color: '#94a3b8',
                callback: val => `${val} PSI`
              }
            }
          }
        }
      });
    }

    if (ctxF && !this.flowChart) {
      const ctx2dF = ctxF.getContext('2d');
      const gradF = this._createGradient(ctx2dF, 'rgba(13, 148, 136, 0.25)', 'rgba(13, 148, 136, 0.00)');

      this.flowChart = new Chart(ctxF, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            {
              label: 'Actual Flow (L/min)',
              data: [],
              borderColor: '#0d9488',
              backgroundColor: gradF,
              borderWidth: 2.6,
              tension: 0,
              fill: true,
              pointRadius: (ctx) => (ctx.dataIndex === ctx.dataset.data.length - 1 ? 5 : 0),
              pointBackgroundColor: '#0d9488',
              pointBorderColor: '#ffffff',
              pointBorderWidth: 2,
              pointHoverRadius: 6
            },
            {
              label: 'Prescribed Flow (L/min)',
              data: [],
              borderColor: '#38bdf8',
              borderDash: [6, 4],
              borderWidth: 2,
              tension: 0,
              fill: false,
              pointRadius: 0,
              pointHoverRadius: 4
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 300 },
          plugins: {
            legend: {
              display: true,
              position: 'top',
              align: 'end',
              labels: {
                boxWidth: 12,
                boxHeight: 10,
                color: '#94a3b8',
                font: { size: 11, weight: 600 }
              }
            },
            tooltip: {
              mode: 'index',
              intersect: false,
              backgroundColor: 'rgba(15, 23, 42, 0.94)',
              titleColor: '#2dd4bf',
              bodyColor: '#ffffff',
              borderColor: '#0d9488',
              borderWidth: 1,
              padding: 10,
              callbacks: {
                label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)} L/min`
              }
            }
          },
          scales: {
            x: {
              grid: { color: 'rgba(148, 163, 184, 0.12)' },
              ticks: { color: '#94a3b8', maxTicksLimit: 6 }
            },
            y: {
              type: 'linear',
              display: true,
              position: 'left',
              title: { display: true, text: 'Flow Rate (L/min)', color: '#0d9488', font: { weight: 600 } },
              grid: { color: 'rgba(148, 163, 184, 0.12)' },
              ticks: { color: '#94a3b8', callback: val => `${val} L/min` },
              min: 0,
              suggestedMax: 4.0
            }
          }
        }
      });
    }

    if (ctxR && !this.reserveChart) {
      const ctx2dR = ctxR.getContext('2d');
      const gradR = this._createGradient(ctx2dR, 'rgba(99, 102, 241, 0.32)', 'rgba(99, 102, 241, 0.00)');

      this.reserveChart = new Chart(ctxR, {
        type: 'line',
        data: {
          labels: [],
          datasets: [{
            label: 'Reserve Remaining (%)',
            data: [],
            borderColor: '#6366f1',
            backgroundColor: gradR,
            borderWidth: 2.6,
            tension: 0.32,
            fill: true,
            pointRadius: (ctx) => (ctx.dataIndex === ctx.dataset.data.length - 1 ? 5 : 0),
            pointBackgroundColor: '#6366f1',
            pointBorderColor: '#ffffff',
            pointBorderWidth: 2,
            pointHoverRadius: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 300 },
          plugins: {
            legend: { display: false },
            tooltip: {
              mode: 'index',
              intersect: false,
              backgroundColor: 'rgba(15, 23, 42, 0.94)',
              titleColor: '#a5b4fc',
              bodyColor: '#ffffff',
              borderColor: '#6366f1',
              borderWidth: 1,
              padding: 10,
              callbacks: {
                label: ctx => ` Usable Reserve: ${ctx.parsed.y}%`
              }
            }
          },
          scales: {
            x: {
              grid: { color: 'rgba(148, 163, 184, 0.12)' },
              ticks: { color: '#94a3b8', maxTicksLimit: 6 }
            },
            y: {
              type: 'linear',
              display: true,
              position: 'left',
              title: { display: true, text: 'Remaining Oxygen (%)', color: '#6366f1', font: { weight: 600 } },
              grid: { color: 'rgba(148, 163, 184, 0.12)' },
              ticks: { color: '#94a3b8', callback: val => `${val}%` },
              min: 0,
              max: 100
            }
          }
        }
      });
    }

    if (ctxE && !this.eteChart) {
      const ctx2dE = ctxE.getContext('2d');
      const gradE = this._createGradient(ctx2dE, 'rgba(245, 158, 11, 0.30)', 'rgba(245, 158, 11, 0.00)');

      this.eteChart = new Chart(ctxE, {
        type: 'line',
        data: {
          labels: [],
          datasets: [{
            label: 'Estimated Supply Time (min)',
            data: [],
            borderColor: '#f59e0b',
            backgroundColor: gradE,
            borderWidth: 2.6,
            tension: 0.32,
            fill: true,
            pointRadius: (ctx) => (ctx.dataIndex === ctx.dataset.data.length - 1 ? 5 : 0),
            pointBackgroundColor: '#f59e0b',
            pointBorderColor: '#ffffff',
            pointBorderWidth: 2,
            pointHoverRadius: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 300 },
          plugins: {
            legend: { display: false },
            tooltip: {
              mode: 'index',
              intersect: false,
              backgroundColor: 'rgba(15, 23, 42, 0.94)',
              titleColor: '#fcd34d',
              bodyColor: '#ffffff',
              borderColor: '#f59e0b',
              borderWidth: 1,
              padding: 10,
              callbacks: {
                label: ctx => {
                  const mins = Math.max(0, Math.round(ctx.parsed.y));
                  const hrs = Math.floor(mins / 60);
                  const rem = mins % 60;
                  return ` Supply ETE: ${mins} min (${hrs}h ${rem}m)`;
                }
              }
            }
          },
          scales: {
            x: {
              grid: { color: 'rgba(148, 163, 184, 0.12)' },
              ticks: { color: '#94a3b8', maxTicksLimit: 6 }
            },
            y: {
              type: 'linear',
              display: true,
              position: 'left',
              title: { display: true, text: 'Supply Time (Minutes)', color: '#f59e0b', font: { weight: 600 } },
              grid: { color: 'rgba(148, 163, 184, 0.12)' },
              ticks: { color: '#94a3b8', callback: val => `${val} min` },
              min: 0,
              suggestedMax: 120
            }
          }
        }
      });
    }
  },

  initLiveFullChart() {
    const ctxFull = document.getElementById('chart-live-full');
    if (ctxFull && !this.liveFullChart) {
      const ctx2d = ctxFull.getContext('2d');
      const grad = this._createGradient(ctx2d, 'rgba(2, 132, 199, 0.28)', 'rgba(2, 132, 199, 0.00)');

      this.liveFullChart = new Chart(ctxFull, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            {
              label: 'Real-Time Pressure (PSI)',
              data: [],
              borderColor: '#0284c7',
              backgroundColor: grad,
              borderWidth: 2.4,
              fill: true,
              tension: 0.35,
              pointRadius: 0,
              yAxisID: 'y'
            },
            {
              label: 'Flow Rate (L/min)',
              data: [],
              borderColor: '#0d9488',
              borderWidth: 2.2,
              fill: false,
              tension: 0.35,
              pointRadius: 0,
              yAxisID: 'y1'
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          scales: {
            x: {
              grid: { color: 'rgba(148, 163, 184, 0.12)' },
              ticks: { color: '#94a3b8', maxTicksLimit: 12 }
            },
            y: {
              position: 'left',
              title: { display: true, text: 'Pressure (PSI)', color: '#0284c7' },
              grid: { color: 'rgba(148, 163, 184, 0.12)' },
              ticks: { color: '#94a3b8' }
            },
            y1: {
              position: 'right',
              title: { display: true, text: 'Flow (L/min)', color: '#0d9488' },
              grid: { drawOnChartArea: false },
              ticks: { color: '#94a3b8' }
            }
          }
        }
      });
    }
  },

  updateFromHistory(historyPoints, prescribedFlow = 2.0) {
    if (!historyPoints || !historyPoints.length) return;

    const labels = historyPoints.map(p => p.timestamp || '');
    const pressures = historyPoints.map(p => (typeof p.pressure_psi === 'number' ? p.pressure_psi : Math.round((p.pressure_bar || 0) * 14.5038)));
    const flows = historyPoints.map(p => (typeof p.flow_lpm === 'number' ? p.flow_lpm : 0.0));
    
    // Constant prescribed flow reference line
    const targetPrescribed = (typeof prescribedFlow === 'number' && prescribedFlow > 0) ? prescribedFlow : 2.0;
    const prescribedSeries = new Array(labels.length).fill(targetPrescribed);

    // Consistent cylinder capacity and Boyle-Mariotte reserve percentage model
    const remainings = historyPoints.map(p => {
      if (typeof p.remaining_pct === 'number') return p.remaining_pct;
      const pBar = p.pressure_bar || (p.pressure_psi ? p.pressure_psi / 14.5038 : 0);
      return Math.max(0, Math.min(100, Math.round((pBar / 200.0) * 1000) / 10));
    });

    // Recalculated / deterministic ETE in minutes with safe division-by-zero handling
    const etes = historyPoints.map(p => {
      if (typeof p.ete_minutes === 'number' && p.ete_minutes >= 0) return p.ete_minutes;
      const f = typeof p.flow_lpm === 'number' ? p.flow_lpm : 0.0;
      const pBar = p.pressure_bar || (p.pressure_psi ? p.pressure_psi / 14.5038 : 0);
      if (f <= 0.05 || pBar <= 0) return 0;
      const usableL = 660.0 * (pBar / 200.0);
      return Math.max(0, Math.round((usableL / f) * 10) / 10);
    });

    if (this.pressureChart) {
      this.pressureChart.data.labels = labels;
      this.pressureChart.data.datasets[0].data = pressures;

      // Dynamic clinical auto-scale to display visible decay curves & micro-variations
      if (pressures.length) {
        const minP = Math.min(...pressures);
        const maxP = Math.max(...pressures);
        const rangeP = Math.max(35, maxP - minP);
        const pad = Math.max(20, Math.round(rangeP * 0.4));
        this.pressureChart.options.scales.y.min = Math.max(0, Math.floor((minP - pad) / 20) * 20);
        this.pressureChart.options.scales.y.max = Math.ceil((maxP + pad) / 20) * 20;
      }

      this.pressureChart.update('none');
    }

    if (this.flowChart) {
      this.flowChart.data.labels = labels;
      this.flowChart.data.datasets[0].data = flows;
      if (this.flowChart.data.datasets[1]) {
        this.flowChart.data.datasets[1].data = prescribedSeries;
      }

      // 0 baseline, auto-expanding ceiling for flow
      if (flows.length) {
        const maxF = Math.max(...flows, targetPrescribed);
        this.flowChart.options.scales.y.min = 0;
        this.flowChart.options.scales.y.max = Math.max(4.0, Math.ceil(maxF + 0.8));
      }

      this.flowChart.update('none');
    }

    if (this.reserveChart) {
      this.reserveChart.data.labels = labels;
      this.reserveChart.data.datasets[0].data = remainings;
      this.reserveChart.options.scales.y.min = 0;
      this.reserveChart.options.scales.y.max = 100;
      this.reserveChart.update('none');
    }

    if (this.eteChart) {
      this.eteChart.data.labels = labels;
      this.eteChart.data.datasets[0].data = etes;

      if (etes.length) {
        const maxE = Math.max(...etes);
        this.eteChart.options.scales.y.min = 0;
        this.eteChart.options.scales.y.max = Math.max(60, Math.ceil((maxE * 1.18) / 30) * 30);
      }

      this.eteChart.update('none');
    }

    if (this.liveFullChart) {
      this.liveFullChart.data.labels = labels;
      this.liveFullChart.data.datasets[0].data = pressures;
      this.liveFullChart.data.datasets[1].data = flows;

      if (pressures.length) {
        const minP = Math.min(...pressures);
        const maxP = Math.max(...pressures);
        const rangeP = Math.max(40, maxP - minP);
        const pad = Math.max(25, Math.round(rangeP * 0.4));
        this.liveFullChart.options.scales.y.min = Math.max(0, Math.floor((minP - pad) / 25) * 25);
        this.liveFullChart.options.scales.y.max = Math.ceil((maxP + pad) / 25) * 25;
      }

      this.liveFullChart.update('none');
    }

    if (this.homePreviewChart) {
      this.homePreviewChart.data.labels = labels.slice(-20);
      this.homePreviewChart.data.datasets[0].data = pressures.slice(-20);
      if (this.homePreviewChart.data.datasets[1]) {
        this.homePreviewChart.data.datasets[1].data = flows.slice(-20);
      }
      this.homePreviewChart.update('none');
    }
  },

  updateTheme(theme) {
    const isDark = theme === 'dark' || document.documentElement.classList.contains('dark') || document.body.classList.contains('dark');
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(148, 163, 184, 0.15)';
    const textColor = isDark ? '#cbd5e1' : '#64748b';

    [this.pressureChart, this.flowChart, this.reserveChart, this.eteChart, this.liveFullChart, this.homePreviewChart].forEach(chart => {
      if (chart && chart.options && chart.options.scales) {
        if (chart.options.scales.x) {
          if (chart.options.scales.x.grid) chart.options.scales.x.grid.color = gridColor;
          if (chart.options.scales.x.ticks) chart.options.scales.x.ticks.color = textColor;
        }
        if (chart.options.scales.y) {
          if (chart.options.scales.y.grid) chart.options.scales.y.grid.color = gridColor;
          if (chart.options.scales.y.ticks) chart.options.scales.y.ticks.color = textColor;
        }
        if (chart.options.scales.y1) {
          if (chart.options.scales.y1.grid) chart.options.scales.y1.grid.color = gridColor;
          if (chart.options.scales.y1.ticks) chart.options.scales.y1.ticks.color = textColor;
        }
        if (chart.options.plugins && chart.options.plugins.legend && chart.options.plugins.legend.labels) {
          chart.options.plugins.legend.labels.color = textColor;
        }
        chart.update();
      }
    });
  }
};
