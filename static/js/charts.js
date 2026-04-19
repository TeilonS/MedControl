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

// ── AUX: LER CORES DO TEMA ───────────────────────────────────────────
const getThemeColor = (varName, fallback) => {
  return getComputedStyle(document.documentElement).getPropertyValue(varName).trim() || fallback;
};

// ── TEMA GLOBAL DOS GRÁFICOS ──────────────────────────────────────────
const updateChartDefaults = () => {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const textColor = getThemeColor('--muted', '#94a3b8');
  const gridColor = isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)';

  Chart.defaults.color          = textColor;
  Chart.defaults.font.family    = "'DM Sans', sans-serif";
  Chart.defaults.font.size      = 12;
  Chart.defaults.borderColor    = gridColor;
};

// ── PALETA DE CORES DINÂMICA ──────────────────────────────────────────
const getPalette = () => ({
  red:    getThemeColor('--red',    '#ef4444'),
  orange: getThemeColor('--orange', '#f97316'),
  yellow: getThemeColor('--yellow', '#ca8a04'),
  green:  getThemeColor('--green',  '#16a34a'),
  teal:   getThemeColor('--primary-l', '#0d9488'),
  bg:     getThemeColor('--card-bg', '#1e293b'),
  text:   getThemeColor('--text', '#f1f5f9'),
});

// ── FUNÇÃO: GRÁFICO DE ROSCA (PERDAS vs ESTOQUE) ──────────────────────
function initLossChart(canvasId, data) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !data) return null;

  updateChartDefaults();
  const palette = getPalette();
  const ctx = canvas.getContext('2d');

  return new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: data.labels,
      datasets: [{
        data:            data.values,
        backgroundColor: [palette.red + 'cc', palette.green + 'cc'],
        borderColor:     [palette.red, palette.green],
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
            color:     getThemeColor('--muted', '#94a3b8'),
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
            }
          },
          backgroundColor: palette.bg,
          borderColor:     'rgba(255,255,255,0.1)',
          borderWidth:     1,
          titleColor:      palette.text,
          bodyColor:       getThemeColor('--muted', '#94a3b8'),
          padding:         12,
          cornerRadius:    10,
        }
      },
      animation: { animateRotate: true, duration: 900, easing: 'easeOutQuart' }
    }
  });
}

// ── FUNÇÃO: GRÁFICO DE BARRAS (STATUS POR QUANTIDADE) ─────────────────
function initStatusBarChart(canvasId, stats) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !stats) return null;

  updateChartDefaults();
  const palette = getPalette();
  const ctx = canvas.getContext('2d');

  return new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ['Vencidos', '30 dias', '60 dias', 'OK'],
      datasets: [{
        label:           'Medicamentos',
        data:            [stats.vencidos, stats.alerta_30, stats.alerta_60, stats.ok],
        backgroundColor: [
          palette.red    + '33',
          palette.orange + '33',
          palette.yellow + '33',
          palette.green  + '33',
        ],
        borderColor: [palette.red, palette.orange, palette.yellow, palette.green],
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
          backgroundColor: palette.bg,
          borderColor:     'rgba(255,255,255,0.1)',
          borderWidth:     1,
          titleColor:      palette.text,
          bodyColor:       getThemeColor('--muted', '#94a3b8'),
          padding:         12,
          cornerRadius:    10,
        }
      },
      scales: {
        x: { ticks: { color: getThemeColor('--muted', '#64748b') }, grid: { display: false } },
        y: {
          ticks:     { color: getThemeColor('--muted', '#64748b'), stepSize: 1 },
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
