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

function dashboardLabelLines(formatted, horizontal = false) {
  if (formatted === '' || formatted === null || formatted === undefined) return '';
  const text = Array.isArray(formatted) ? formatted.join(' ') : String(formatted);
  const match = text.match(/^(.*?)\s*\(?([\d.,]+\s*%)\)?\s*$/);
  if (!match) return text;
  return `${match[1].trim()} (${match[2]})`;
}

function dashboardVerticalLabel(formatted) {
  const label = dashboardLabelLines(formatted);
  if (typeof label !== 'string') return label;
  const parts = label.match(/^(.*?)\s+(\([\d.,]+\s*%\))$/);
  return parts ? [parts[1], parts[2]] : label;
}

function dashboardFitVerticalChartJsBars(chart, formatLabel) {
  if (chart.config.type !== 'bar' || chart.options.indexAxis === 'y') return;
  const stacked = chart.options.scales?.y?.stacked;
  const stackEdges = new Map();
  const canvas = chart.ctx;
  canvas.save();
  canvas.font = 'bold 11px sans-serif';
  chart.getSortedVisibleDatasetMetas().forEach(meta => {
    const dataset = chart.data.datasets[meta.index];
    meta.data.forEach((bar, index) => {
      if (!(Number(dataset.data[index]) > 0)) {
        bar.y = bar.base;
        bar.height = 0;
        bar.width = 0;
        return;
      }
      const ctx = { chart, dataset, datasetIndex: meta.index, dataIndex: index, active: false };
      const label = formatLabel(dataset.data[index], ctx);
      const lines = Array.isArray(label) ? label : [String(label)];
      const width = Math.max(...lines.map(line => canvas.measureText(line).width)) + 12;
      const length = Math.abs(bar.base - bar.y);
      const height = Math.max(length, lines.length * 14 + 8);
      const key = `${meta.stack || ''}:${index}`;
      bar.width = Math.max(bar.width, width);
      if (stacked && stackEdges.has(key)) bar.base = stackEdges.get(key);
      bar.y = bar.base - height;
      if (stacked) stackEdges.set(key, bar.y);
    });
  });
  canvas.restore();
}

// One complete visual definition for the reference and every horizontal bar.
function dashboardHorizontalStyle() {
  return {
    chart: { fontFamily: 'inherit', foreColor: '#1e293b', fontSize: '12px' },
    fill: { type: 'solid', opacity: 1 },
    grid: { borderColor: '#e8eef5', strokeDashArray: 4,
      padding: { right: 90, left: 8, top: 36 } },
    plotOptions: { bar: {
      horizontal: true, barHeight: '78%', borderRadius: 6,
      dataLabels: { position: 'center', hideOverflowingLabels: false },
      colors: { backgroundBarColors: ['#f1f5f9'], backgroundBarRadius: 6 }
    } },
    xaxis: { min: 0, tickAmount: 4,
      axisBorder: { show: false }, axisTicks: { show: false },
      labels: { style: { colors: '#1e293b', fontSize: '12px', fontWeight: 600 } }
    },
    yaxis: { labels: { style: { colors: '#1e293b', fontSize: '12px', fontWeight: 600 } } },
    dataLabels: { enabled: true, offsetX: 0, offsetY: 0,
      style: { fontSize: '11px', fontWeight: 700, colors: ['#ffffff'] },
      background: { enabled: false }, dropShadow: { enabled: false }
    }
  };
}

// Apex does not expose a per-point anchor callback. Position SVG labels from
// their actual measured bar/text dimensions after each render and update.
function dashboardPlaceApexLabels(chart) {
  const root = chart.w?.dom?.baseEl || chart.w?.globals?.dom?.baseEl;
  if (!root || chart.w.config.chart.type !== 'bar') return;
  const horizontal = chart.w.config.plotOptions.bar.horizontal;
  const series = root.querySelectorAll('.apexcharts-bar-series .apexcharts-series');
  const labels = root.querySelectorAll('.apexcharts-datalabels');
  const stackEdges = new Map();
  series.forEach((group, seriesIndex) => {
    const realIndex = Number(group.getAttribute('data:realIndex') ?? seriesIndex);
    const bars = group.querySelectorAll('.apexcharts-bar-area');
    bars.forEach((bar, index) => {
      const pointIndex = Number(bar.getAttribute('j') ?? index);
      const raw = chart.w.config.series[realIndex]?.data[pointIndex];
      const value = Number(raw && typeof raw === 'object' ? raw.y : raw);
      bar.style.display = value > 0 ? '' : 'none';
      bar.removeAttribute('transform');
    });
    const labelGroup = Array.from(labels).find(item => Number(item.getAttribute('data:realIndex')) === realIndex)
      || labels[seriesIndex];
    const texts = labelGroup?.querySelectorAll('text') || [];
    const drawnIndexes = chart.w.globals.lastDrawnDataLabelsIndexes?.[realIndex];
    texts.forEach((text, index) => {
      const pointIndex = drawnIndexes?.[index] ?? index;
      const bar = Array.from(bars).find(item => item.getAttribute('j') !== null
        && Number(item.getAttribute('j')) === pointIndex) || bars[pointIndex];
      if (!bar) return;
      if (bar.style.display === 'none') {
        text.style.visibility = 'hidden';
        return;
      }
      text.removeAttribute('transform');
      text.setAttribute('font-size', '11');
      bar.removeAttribute('transform');
      let barRect = bar.getBoundingClientRect();
      const textRect = text.getBoundingClientRect();
      if (!textRect.width || !textRect.height) return;
      if (barRect.width < 1 || barRect.height < 1) {
        text.style.visibility = 'hidden';
        return;
      }
      text.style.visibility = 'visible';
      // Keep the same 11px label everywhere; give small fills a visual minimum.
      const scaleX = Math.max(1, (textRect.width + 12) / barRect.width);
      const scaleY = Math.max(1, (textRect.height + 8) / barRect.height);
      const box = bar.getBBox();
      let tx = (horizontal ? box.x : box.x + box.width / 2) * (1 - scaleX);
      let ty = (horizontal ? box.y + box.height / 2 : box.y + box.height) * (1 - scaleY);
      bar.setAttribute('transform', `matrix(${scaleX},0,0,${scaleY},${tx},${ty})`);
      barRect = bar.getBoundingClientRect();
      if (chart.w.config.chart.stacked) {
        const edge = stackEdges.get(pointIndex);
        if (edge !== undefined) {
          const dx = horizontal ? edge - barRect.left : 0;
          const dy = horizontal ? 0 : edge - barRect.bottom;
          const matrix = group.getScreenCTM();
          if (matrix) {
            const inverse = matrix.inverse();
            tx += inverse.a * dx + inverse.c * dy;
            ty += inverse.b * dx + inverse.d * dy;
            bar.setAttribute('transform', `matrix(${scaleX},0,0,${scaleY},${tx},${ty})`);
            barRect = bar.getBoundingClientRect();
          }
        }
        stackEdges.set(pointIndex, horizontal ? barRect.right : barRect.top);
      }
      barRect = bar.getBoundingClientRect();
      const fittedRect = text.getBoundingClientRect();
      const dx = barRect.left + barRect.width / 2 - (fittedRect.left + fittedRect.width / 2);
      const dy = barRect.top + barRect.height / 2 - (fittedRect.top + fittedRect.height / 2);
      const matrix = text.getScreenCTM();
      if (matrix) {
        const inverse = matrix.inverse();
        text.setAttribute('transform', `translate(${inverse.a * dx + inverse.c * dy},${inverse.b * dx + inverse.d * dy})`);
      }
      text.setAttribute('fill', '#ffffff');
    });
  });
}

function dashboardApexBarStyle(options, id) {
  const originalFormatter = options.dataLabels?.formatter;
  if (options.chart?.type !== 'bar') return {
    ...options,
    dataLabels: { ...options.dataLabels,
      background: { enabled: false },
      formatter: (value, ctx) => dashboardLabelLines(originalFormatter ? originalFormatter(value, ctx) : value)
    }
  };
  // Keep the original horizontal/vertical distinction, rather than rotating all charts.
  const horizontal = ['chart-factores-modificables', 'chart-ind-edad-sexo', 'chart-ind-vivienda',
    'chart-fam-padres-madres', 'chart-fam-por-edad', 'chart-cov-por-categoria', 'chart-nc-comorbilidades'].includes(id)
    || (options.plotOptions?.bar?.horizontal === true && ![
      'chart-exp-imc-cat', 'chart-exp-auscultacion', 'chart-mod-control-tto',
      'chart-mod-actividad-cat', 'chart-em-sueno', 'chart-em-hormonas-ambiente',
      'chart-cov-historia', 'chart-ecg-anomalias', 'chart-nc-reuma-alergia',
      'chart-mod-obligatorios', 'chart-mod-vasculopatia'].includes(id));
  const bar = options.plotOptions?.bar || {};
  const events = options.chart?.events || {};
  const labelEvents = {};
  ['mounted', 'updated', 'animationEnd'].forEach(name => {
    labelEvents[name] = (chart, ...args) => {
      if (typeof events[name] === 'function') events[name](chart, ...args);
      requestAnimationFrame(() => dashboardPlaceApexLabels(chart));
    };
  });
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
  const styled = {
    ...options,
    chart: { ...options.chart, events: { ...events, ...labelEvents }, fontFamily: 'inherit', foreColor: '#1e293b', fontSize: '12px',
      height: Math.max(320, (options.xaxis?.categories?.length || 1) * (options.series?.length > 1 && !options.chart.stacked ? 76 : 48) + 90) },
    grid: { borderColor: '#e8eef5', strokeDashArray: 4, padding: { right: 90, left: 8, top: 36 } },
    fill: { type: 'solid', opacity: 1 },
    plotOptions: { ...options.plotOptions, bar: {
      ...bar, horizontal, borderRadius: 6, barHeight: '78%', columnWidth: '80%',
      dataLabels: { position: 'center', hideOverflowingLabels: false },
      colors: { backgroundBarColors: ['#f1f5f9'], backgroundBarRadius: 6 }
    } },
    xaxis: { ...xaxis, axisBorder: { show: false }, axisTicks: { show: false } },
    yaxis,
    dataLabels: { ...options.dataLabels, enabled: true, offsetX: 0, offsetY: 0,
      formatter: (value, ctx) => {
        if (!(Number(value) > 0)) return '';
        const label = dashboardLabelLines(originalFormatter ? originalFormatter(value, ctx) : value, horizontal);
        return horizontal ? label : dashboardVerticalLabel(label);
      },
      style: { fontSize: '11px', fontWeight: 700, colors: ['#ffffff'] },
      background: { enabled: false }, dropShadow: { enabled: false }
    }
  };
  return horizontal ? dashboardMergeStyle(styled, dashboardHorizontalStyle()) : styled;
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
  const options = config.options ||= {};
  options.plugins ||= {};
  const originalLabels = options.plugins.datalabels || {};
  if (config.type !== 'bar') {
    options.plugins.datalabels = { ...originalLabels, backgroundColor: 'transparent',
      formatter: (value, ctx) => dashboardLabelLines(originalLabels.formatter ? originalLabels.formatter(value, ctx) : value)
    };
    return;
  }
  options.scales ||= {};
  const horizontal = options.indexAxis === 'y';
  if (!horizontal) options.animation = false;
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
    ...oldLabels,
    display: ctx => Number(ctx.dataset.data[ctx.dataIndex]) > 0,
    color: '#ffffff', anchor: 'center', align: 'center', offset: 0,
    clip: false, font: { weight: 'bold', size: 11 }, borderWidth: 0, borderRadius: 4,
    padding: 0, textAlign: 'center', backgroundColor: 'transparent',
    formatter: (value, ctx) => {
      const formatted = oldLabels.formatter ? oldLabels.formatter(value, ctx) : String(value);
      return horizontal ? dashboardLabelLines(formatted, true) : dashboardVerticalLabel(formatted);
    }
  };
  config.data.datasets.forEach(dataset => {
    // A global minimum makes Chart.js draw positive stubs even for zero values.
    // Only the geometry hook expands actual positive bars.
    dataset.minBarLength = 0;
  });
  options.plugins.legend = dashboardMergeStyle(options.plugins.legend || {}, {
    labels: { usePointStyle: true, pointStyle: 'circle', boxWidth: 10, padding: 18,
      color: '#0f172a', font: { size: 12, weight: '600' } }
  });
}

function createDashboardChart(element, config) {
  dashboardChartJsStyle(config);
  if (config.type === 'bar' && config.options.indexAxis !== 'y') {
    const formatLabel = config.options.plugins.datalabels.formatter;
    config.plugins = [...(config.plugins || []), {
      id: 'dashboard-fit-vertical-labels',
      afterDatasetsUpdate: chart => dashboardFitVerticalChartJsBars(chart, formatLabel)
    }];
  }
  return new Chart(element, config);
}
