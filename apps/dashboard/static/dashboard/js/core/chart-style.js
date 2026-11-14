// Both reference charts and every section use these same presentation rules.
function dashboardMergeStyle(base, extra) {
  const result = { ...base };
  Object.entries(extra || {}).forEach(([key, value]) => {
    result[key] = value && typeof value === 'object' && !Array.isArray(value)
      && typeof base[key] === 'object' && base[key] !== null && !Array.isArray(base[key])
      ? dashboardMergeStyle(base[key], value) : value;
  });
  return result;
}

function dashboardApexBarStyle(options, id) {
  if (options.chart?.type !== 'bar') return options;
  // Keep the original horizontal/vertical distinction, rather than rotating all charts.
  const horizontal = ['chart-factores-modificables', 'chart-ind-edad-sexo', 'chart-ind-vivienda',
    'chart-fam-padres-madres', 'chart-fam-por-edad', 'chart-cov-por-categoria', 'chart-nc-comorbilidades'].includes(id)
    || (options.plotOptions?.bar?.horizontal === true && ![
      'chart-exp-imc-cat', 'chart-exp-auscultacion', 'chart-mod-control-tto',
      'chart-mod-actividad-cat', 'chart-em-sueno', 'chart-em-hormonas-ambiente',
      'chart-cov-historia', 'chart-ecg-anomalias', 'chart-nc-reuma-alergia',
      'chart-mod-obligatorios', 'chart-mod-vasculopatia'].includes(id));
  const bar = options.plotOptions?.bar || {};
  const colorAt = ({ seriesIndex, dataPointIndex, w }) => {
    const index = bar.distributed ? dataPointIndex : seriesIndex;
    return (options.colors || w.globals.colors || ['#3aa0ff'])[index % (options.colors?.length || w.globals.colors?.length || 1)];
  };
  const yaxis = Array.isArray(options.yaxis) ? options.yaxis : { ...options.yaxis };
  const xaxis = { ...options.xaxis };
  if (horizontal && !['chart-factores-modificables', 'chart-ind-edad-sexo'].includes(id)) {
    delete xaxis.max;
    xaxis.min = 0;
  }
  if (!Array.isArray(yaxis)) {
    delete yaxis.max;
    yaxis.min = 0;
    if (horizontal) delete yaxis.title;
  }
  return {
    ...options,
    chart: { ...options.chart, fontFamily: 'inherit', foreColor: '#1e293b', fontSize: '12px',
      height: Math.max(320, (options.xaxis?.categories?.length || 1) * (options.series?.length > 1 && !options.chart.stacked ? 76 : 48) + 90) },
    grid: { borderColor: '#e8eef5', strokeDashArray: 4, padding: { right: 24, left: 8 } },
    fill: { type: 'solid', opacity: 1 },
    plotOptions: { ...options.plotOptions, bar: {
      ...bar, horizontal, borderRadius: 6, barHeight: '78%', columnWidth: '80%',
      dataLabels: { position: 'center', hideOverflowingLabels: false },
      colors: { backgroundBarColors: ['#f1f5f9'], backgroundBarRadius: 6 }
    } },
    xaxis: { ...xaxis, axisBorder: { show: false }, axisTicks: { show: false } },
    yaxis,
    dataLabels: { ...options.dataLabels, enabled: true, offsetX: 0, offsetY: 0,
      style: { fontSize: '11px', fontWeight: 700, colors: [colorAt] },
      // A same-color label backing extends the fill under short labels without
      // altering their real values or the proportional length of the bar.
      background: { enabled: true, foreColor: '#ffffff', opacity: 1, padding: 4,
        borderRadius: 4, borderWidth: 0 }, dropShadow: { enabled: false }
    }
  };
}

function createDashboardApexChart(element, options) {
  let current = options;
  const chart = new ApexCharts(element, dashboardApexBarStyle(current, element.id));
  const update = chart.updateOptions.bind(chart);
  chart.updateOptions = (next, ...args) => {
    current = dashboardMergeStyle(current, next);
    return update(dashboardApexBarStyle(current, element.id), ...args);
  };
  return chart;
}

function dashboardChartJsStyle(config) {
  if (config.type !== 'bar') return;
  const options = config.options ||= {};
  options.plugins ||= {};
  options.scales ||= {};
  const horizontal = options.indexAxis === 'y';
  const valueAxis = horizontal ? 'x' : 'y';
  const categoryAxis = horizontal ? 'y' : 'x';
  if (options.scales[valueAxis] && config.data.datasets[0]?.label !== 'Latidos por Minuto (lpm)') {
    delete options.scales[valueAxis].max;
  }
  options.scales[categoryAxis] = dashboardMergeStyle(options.scales[categoryAxis] || {}, {
    grid: { display: false }, border: { display: false },
    ticks: { color: '#1e293b', font: { size: 12, weight: '600' } }
  });
  options.scales[valueAxis] = dashboardMergeStyle(options.scales[valueAxis] || {}, {
    beginAtZero: true, grid: { color: '#edf2f7' }, border: { display: false },
    ticks: { precision: 0, color: '#1e293b', font: { size: 12, weight: '600' } }
  });
  config.data.datasets.forEach(dataset => Object.assign(dataset, {
    maxBarThickness: 76, categoryPercentage: 0.8, barPercentage: 0.9, borderRadius: 4
  }));
  const oldLabels = options.plugins.datalabels || {};
  options.plugins.datalabels = {
    ...oldLabels, color: '#ffffff', anchor: 'center', align: 'center', offset: 0,
    clip: false, font: { weight: 'bold', size: 11 }, borderWidth: 0, borderRadius: 4,
    padding: 4,
    backgroundColor: ctx => {
      const color = ctx.dataset.backgroundColor;
      return Array.isArray(color) ? color[ctx.dataIndex % color.length] : color;
    },
    formatter: (value, ctx) => {
      const formatted = oldLabels.formatter ? oldLabels.formatter(value, ctx) : String(value);
      // Two lines keep the full value inside the width of a vertical column.
      return typeof formatted === 'string' ? formatted.replace(' (', '\n(').split('\n') : formatted;
    }
  };
  options.plugins.legend = dashboardMergeStyle(options.plugins.legend || {}, {
    labels: { usePointStyle: true, pointStyle: 'circle', boxWidth: 10, padding: 18,
      color: '#0f172a', font: { size: 12, weight: '600' } }
  });
}

function createDashboardChart(element, config) {
  dashboardChartJsStyle(config);
  return new Chart(element, config);
}
