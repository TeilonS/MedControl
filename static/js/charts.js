/*
=============================================================================
  MedControl — Lógica de Gráficos (Chart.js)
  Centraliza a configuração e inicialização de todos os gráficos do sistema.
  Para usar: inclua este arquivo no template APÓS o Chart.js e APÓS
  definir a variável global `window.CHART_DATA` com os dados do backend.

  Exemplo no template (antes deste script):
  <script>
    window.CHART_DATA = {{ chart_data | safe }};
  </script>
  <script src="{{ url_for('static', filename='js/charts.js') }}"></script>
=============================================================================
*/

// ── TEMA GLOBAL DOS GRÁFICOS ──────────────────────────────────────────
Chart.defaults.color          = '#94a3b8';
Chart.defaults.font.family    = "'DM Sans', sans-serif";
Chart.defaults.font.size      = 12;
Chart.defaults.borderColor    = 'rgba(255,255,255,0.06)';
Chart.defaults.backgroundColor = 'rgba(255,255,255,0.03)';

// ── PALETA DE CORES PADRÃO ────────────────────────────────────────────
const COLORS = {
  red:    '#ef4444',
  orange: '#f97316',
  yellow: '#eab308',
  green:  '#22c55e',
  teal:   '#14b8a6',
  blue:   '#3b82f6',
  purple: '#a855f7',
  muted:  '#475569',
};

// ── FUNÇÃO: GRÁFICO DE ROSCA (PERDAS vs ESTOQUE) ──────────────────────
function initLossChart(canvasId, data) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !data) return null;

  const ctx = canvas.getContext('2d');

  return new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: data.labels,
      datasets: [{
        data:            data.values,
        backgroundColor: data.colors.map(c => c + 'cc'),
        borderColor:     data.colors,
        borderWidth:     2,
        hoverOffset:     10,
      }]
    },
    options: {
      responsive:          true,
      maintainAspectRatio: false,
      cutout:              '65%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color:     '#94a3b8',
            font:      { family: 'DM Sans', size: 11 },
            padding:   14,
            boxWidth:  12,
            boxHeight: 12,
          }
        },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              const val = ctx.parsed;
              return ' R$ ' + val.toLocaleString('pt-BR', { minimumFractionDigits: 2 });
            },
            title: function(items) {
              return items[0].label;
            }
          },
          backgroundColor: '#1e293b',
          borderColor:     'rgba(255,255,255,0.1)',
          borderWidth:     1,
          titleColor:      '#f1f5f9',
          bodyColor:       '#94a3b8',
          padding:         12,
          cornerRadius:    10,
        }
      },
      animation: {
        animateRotate: true,
        duration:      900,
        easing:        'easeOutQuart',
      }
    }
  });
}

// ── FUNÇÃO: GRÁFICO DE BARRAS (STATUS POR QUANTIDADE) ─────────────────
function initStatusBarChart(canvasId, stats) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !stats) return null;

  const ctx = canvas.getContext('2d');

  return new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ['Vencidos', 'Próx. 30 dias', 'Próx. 60 dias', 'OK'],
      datasets: [{
        label:           'Medicamentos',
        data:            [stats.vencidos, stats.alerta_30, stats.alerta_60, stats.ok],
        backgroundColor: [
          COLORS.red    + '33',
          COLORS.orange + '33',
          COLORS.yellow + '33',
          COLORS.green  + '33',
        ],
        borderColor: [COLORS.red, COLORS.orange, COLORS.yellow, COLORS.green],
        borderWidth:  2,
        borderRadius: 8,
        borderSkipped: false,
      }]
    },
    options: {
      responsive:          true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1e293b',
          borderColor:     'rgba(255,255,255,0.1)',
          borderWidth:     1,
          titleColor:      '#f1f5f9',
          bodyColor:       '#94a3b8',
          padding:         12,
          cornerRadius:    10,
        }
      },
      scales: {
        x: {
          grid:  { color: 'rgba(255,255,255,0.04)' },
          ticks: { color: '#64748b' },
        },
        y: {
          grid:      { color: 'rgba(255,255,255,0.04)' },
          ticks:     { color: '#64748b', stepSize: 1 },
          beginAtZero: true,
        }
      },
      animation: { duration: 700, easing: 'easeOutQuart' }
    }
  });
}

// ── FUNÇÃO: GRÁFICO DE LINHA (HISTÓRICO — PARA USO FUTURO) ───────────
function initHistoryChart(canvasId, historyData) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !historyData) return null;

  const ctx = canvas.getContext('2d');

  // Gradiente
  const gradient = ctx.createLinearGradient(0, 0, 0, 200);
  gradient.addColorStop(0,   'rgba(20, 184, 166, 0.3)');
  gradient.addColorStop(1,   'rgba(20, 184, 166, 0.0)');

  return new Chart(ctx, {
    type: 'line',
    data: {
      labels:   historyData.labels,
      datasets: [{
        label:           'Valor em Risco (R$)',
        data:            historyData.values,
        borderColor:     COLORS.teal,
        backgroundColor: gradient,
        borderWidth:     2,
        pointRadius:     4,
        pointBackgroundColor: COLORS.teal,
        pointBorderColor:     '#0f172a',
        pointBorderWidth:     2,
        fill:            true,
        tension:         0.4,
      }]
    },
    options: {
      responsive:          true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => ' R$ ' + ctx.parsed.y.toLocaleString('pt-BR', { minimumFractionDigits: 2 })
          },
          backgroundColor: '#1e293b',
          borderColor:     'rgba(255,255,255,0.1)',
          borderWidth:     1,
          padding:         12,
          cornerRadius:    10,
          titleColor:      '#f1f5f9',
          bodyColor:       '#94a3b8',
        }
      },
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#64748b' } },
        y: {
          grid:        { color: 'rgba(255,255,255,0.04)' },
          ticks:       { color: '#64748b', callback: v => 'R$ ' + v.toLocaleString('pt-BR') },
          beginAtZero: true,
        }
      },
      animation: { duration: 1000, easing: 'easeOutQuart' }
    }
  });
}

// ── INICIALIZAÇÃO AUTOMÁTICA ──────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  const data = window.CHART_DATA;
  if (!data) return;

  // Gráfico de rosca principal (dashboard)
  initLossChart('lossChart', data);

  // Gráfico de barras por status (se o canvas existir)
  if (window.STATS_DATA) {
    initStatusBarChart('statusChart', window.STATS_DATA);
  }

  // Gráfico de histórico (se o canvas existir)
  if (window.HISTORY_DATA) {
    initHistoryChart('historyChart', window.HISTORY_DATA);
  }
});
