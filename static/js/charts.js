/**
 * static/js/charts.js — Chart.js Management for OxySense
 */

const OxyCharts = {
  pressureChart: null,
  flowChart: null,
  liveFullChart: null,
  homePreviewChart: null,

  initHomePreviewChart() {
    const ctxH = document.getElementById('chart-home-preview');
    if (ctxH && !this.homePreviewChart) {
      this.homePreviewChart = new Chart(ctxH, {
        type: 'line',
        data: {
          labels: [],
          datasets: [{
            label: 'Cylinder Pressure (PSI)',
            data: [],
            borderColor: '#0d9488',
            backgroundColor: 'rgba(13, 148, 136, 0.12)',
            borderWidth: 2,
            tension: 0.3,
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
            y: { display: false, suggestedMin: 0, suggestedMax: 3000 }
          }
        }
      });
    }
  },

  initOverviewCharts() {
    const ctxP = document.getElementById('chart-pressure');
    const ctxF = document.getElementById('chart-flow');

    if (ctxP && !this.pressureChart) {
      this.pressureChart = new Chart(ctxP, {
        type: 'line',
        data: {
          labels: [],
          datasets: [{
            label: 'Cylinder Pressure (PSI)',
            data: [],
            borderColor: '#0284c7',
            backgroundColor: 'rgba(2, 132, 199, 0.08)',
            borderWidth: 2.2,
            tension: 0.3,
            fill: true,
            pointRadius: 2,
            pointHoverRadius: 5
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              mode: 'index',
              intersect: false,
              callbacks: {
                label: ctx => `Pressure: ${ctx.parsed.y} PSI`
              }
            }
          },
          scales: {
            x: {
              grid: { color: '#f1f5f9' },
              ticks: { color: '#94a3b8', maxTicksLimit: 7 }
            },
            y: {
              grid: { color: '#f1f5f9' },
              ticks: { color: '#94a3b8' },
              suggestedMin: 0,
              suggestedMax: 3000
            }
          }
        }
      });
    }

    if (ctxF && !this.flowChart) {
      this.flowChart = new Chart(ctxF, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            {
              label: 'Oxygen Flow (L/min)',
              data: [],
              borderColor: '#0d9488',
              backgroundColor: 'rgba(13, 148, 136, 0.12)',
              borderWidth: 2,
              tension: 0.2,
              fill: true,
              yAxisID: 'y'
            },
            {
              label: 'Supply Remaining %',
              data: [],
              borderColor: '#6366f1',
              borderDash: [4, 4],
              borderWidth: 1.8,
              fill: false,
              pointRadius: 0,
              yAxisID: 'y1'
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              display: true,
              position: 'top',
              labels: { boxWidth: 12, font: { size: 11 } }
            }
          },
          scales: {
            x: {
              grid: { color: '#f1f5f9' },
              ticks: { color: '#94a3b8', maxTicksLimit: 6 }
            },
            y: {
              type: 'linear',
              display: true,
              position: 'left',
              title: { display: true, text: 'L/min', color: '#0d9488' },
              suggestedMin: 0,
              suggestedMax: 10,
              grid: { color: '#f1f5f9' }
            },
            y1: {
              type: 'linear',
              display: true,
              position: 'right',
              title: { display: true, text: 'Remaining %', color: '#6366f1' },
              suggestedMin: 0,
              suggestedMax: 100,
              grid: { drawOnChartArea: false }
            }
          }
        }
      });
    }
  },

  initLiveFullChart() {
    const ctxFull = document.getElementById('chart-live-full');
    if (ctxFull && !this.liveFullChart) {
      this.liveFullChart = new Chart(ctxFull, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            {
              label: 'Real-Time Pressure (PSI)',
              data: [],
              borderColor: '#0284c7',
              backgroundColor: 'rgba(2, 132, 199, 0.06)',
              borderWidth: 2,
              fill: true,
              tension: 0.2,
              yAxisID: 'y'
            },
            {
              label: 'Flow Rate (L/min)',
              data: [],
              borderColor: '#0d9488',
              borderWidth: 2,
              fill: false,
              tension: 0.2,
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
              grid: { color: '#f1f5f9' },
              ticks: { color: '#94a3b8', maxTicksLimit: 12 }
            },
            y: {
              position: 'left',
              title: { display: true, text: 'Pressure (PSI)' },
              suggestedMin: 0,
              suggestedMax: 3000,
              grid: { color: '#f1f5f9' }
            },
            y1: {
              position: 'right',
              title: { display: true, text: 'Flow (L/min)' },
              suggestedMin: 0,
              suggestedMax: 10,
              grid: { drawOnChartArea: false }
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
      this.pressureChart.update('none');
    }

    if (this.flowChart) {
      this.flowChart.data.labels = labels;
      this.flowChart.data.datasets[0].data = flows;
      this.flowChart.data.datasets[1].data = remainings;
      this.flowChart.update('none');
    }

    if (this.liveFullChart) {
      this.liveFullChart.data.labels = labels;
      this.liveFullChart.data.datasets[0].data = pressures;
      this.liveFullChart.data.datasets[1].data = flows;
      this.liveFullChart.update('none');
    }

    if (this.homePreviewChart) {
      this.homePreviewChart.data.labels = labels.slice(-15);
      this.homePreviewChart.data.datasets[0].data = pressures.slice(-15);
      this.homePreviewChart.update('none');
    }
  },

  updateTheme(theme) {
    const isDark = theme === 'dark';
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.05)';
    const textColor = isDark ? '#94a3b8' : '#64748b';

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
        chart.update();
      }
    });
  }
};
