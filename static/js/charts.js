/**
 * static/js/charts.js — Medical-Grade Chart.js Management for OxySense
 */

const OxyCharts = {
  pressureChart: null,
  flowChart: null,
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
      const grad = this._createGradient(ctx2d, 'rgba(13, 148, 136, 0.35)', 'rgba(13, 148, 136, 0.00)');

      this.homePreviewChart = new Chart(canvas, {
        type: 'line',
        data: {
          labels: [],
          datasets: [{
            label: 'Cylinder Pressure (PSI)',
            data: [],
            borderColor: '#0d9488',
            backgroundColor: grad,
            borderWidth: 2.5,
            tension: 0.38,
            fill: true,
            pointRadius: 0
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: { enabled: true } },
          scales: {
            x: { display: false },
            y: { display: false }
          }
        }
      });
    }
  },

  initOverviewCharts() {
    const ctxP = document.getElementById('chart-pressure');
    const ctxF = document.getElementById('chart-flow');

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
            tension: 0.38,
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
          animation: { duration: 350 },
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
      const gradF = this._createGradient(ctx2dF, 'rgba(13, 148, 136, 0.32)', 'rgba(13, 148, 136, 0.00)');

      this.flowChart = new Chart(ctxF, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            {
              label: 'Oxygen Flow (L/min)',
              data: [],
              borderColor: '#0d9488',
              backgroundColor: gradF,
              borderWidth: 2.6,
              tension: 0.38,
              fill: true,
              pointRadius: (ctx) => (ctx.dataIndex === ctx.dataset.data.length - 1 ? 5 : 0),
              pointBackgroundColor: '#0d9488',
              pointBorderColor: '#ffffff',
              pointBorderWidth: 2,
              pointHoverRadius: 6,
              yAxisID: 'y'
            },
            {
              label: 'Reserve Remaining %',
              data: [],
              borderColor: '#6366f1',
              borderDash: [5, 5],
              borderWidth: 2,
              fill: false,
              pointRadius: 0,
              yAxisID: 'y1'
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 350 },
          plugins: {
            legend: {
              display: true,
              position: 'top',
              align: 'end',
              labels: {
                boxWidth: 10,
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
              padding: 10
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
              title: { display: true, text: 'Flow (L/min)', color: '#0d9488', font: { weight: 600 } },
              grid: { color: 'rgba(148, 163, 184, 0.12)' },
              ticks: { color: '#94a3b8' }
            },
            y1: {
              type: 'linear',
              display: true,
              position: 'right',
              title: { display: true, text: 'Reserve %', color: '#6366f1', font: { weight: 600 } },
              min: 0,
              max: 100,
              grid: { drawOnChartArea: false },
              ticks: { color: '#94a3b8', callback: val => `${val}%` }
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

  updateFromHistory(historyPoints) {
    if (!historyPoints || !historyPoints.length) return;

    const labels = historyPoints.map(p => p.timestamp);
    const pressures = historyPoints.map(p => p.pressure_psi);
    const flows = historyPoints.map(p => p.flow_lpm);
    const remainings = historyPoints.map(p => p.remaining_pct);

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
      this.flowChart.data.datasets[1].data = remainings;

      // Dynamic auto-scale for flow to display respiratory rhythm clearly
      if (flows.length) {
        const minF = Math.min(...flows);
        const maxF = Math.max(...flows);
        const rangeF = Math.max(0.5, maxF - minF);
        const padF = Math.max(0.3, Number((rangeF * 0.45).toFixed(1)));
        this.flowChart.options.scales.y.min = Math.max(0, Number((minF - padF).toFixed(1)));
        this.flowChart.options.scales.y.max = Number((maxF + padF).toFixed(1));
      }

      this.flowChart.update('none');
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
      this.homePreviewChart.data.labels = labels.slice(-15);
      this.homePreviewChart.data.datasets[0].data = pressures.slice(-15);
      this.homePreviewChart.update('none');
    }
  },

  updateTheme(theme) {
    const isDark = theme === 'dark' || document.documentElement.classList.contains('dark') || document.body.classList.contains('dark');
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(148, 163, 184, 0.15)';
    const textColor = isDark ? '#cbd5e1' : '#64748b';

    [this.pressureChart, this.flowChart, this.liveFullChart].forEach(chart => {
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
