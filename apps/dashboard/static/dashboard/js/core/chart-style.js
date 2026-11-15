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

// ============================================================================
// REGLA INFALTABLE: ESTILO ÚNICO CENTRALIZADO DE ETIQUETAS DE VALOR
// Tomado exactamente de la dona de referencia: "Distribución por Categoría de Personal"
// Color blanco (#ffffff), tipografía inherit, negrita (700), tamaño base 11px
// con sombra oscura sutil (dropShadow / textStroke) para contraste universal.
// ============================================================================
var UNIVERSAL_VALUE_LABEL_STYLE = {
  color: '#ffffff',
  fontFamily: 'inherit',
  fontWeight: 'bold',
  baseSize: 11,
  minSize: 9.5,
  maxSize: 12,
  textStrokeColor: 'rgba(15, 23, 42, 0.50)',
  textStrokeWidth: 2,
  textShadowBlur: 3,
  textShadowColor: 'rgba(0, 0, 0, 0.35)',
  apexDropShadow: {
    enabled: true,
    top: 1,
    left: 1,
    blur: 2,
    color: '#0f172a',
    opacity: 0.6
  }
};

function dashboardLabelLines(formatted, horizontal = false) {
  if (formatted === '' || formatted === null || formatted === undefined) return '';
  if (Array.isArray(formatted)) return formatted;
  const text = String(formatted);
  if (text.includes('·') || text.includes('IC 95%:') || text.includes('IC:')) return text;
  const match = text.match(/^(.*?)\s*\(?([\d.,]+\s*%)\)?\s*$/);
  if (!match) return text;
  return `${match[1].trim()} (${match[2]})`;
}

function dashboardVerticalLabel(formatted) {
  if (Array.isArray(formatted)) return formatted;
  const label = dashboardLabelLines(formatted);
  if (typeof label !== 'string') return label;
  if (label.includes('·') || label.includes('IC 95%:')) return label;
  const parts = label.match(/^(.*?)\s+(\([\d.,]+\s*%\))$/);
  return parts ? [parts[1], parts[2]] : label;
}

function dashboardFitVerticalChartJsBars(chart, formatLabel) {
  if (chart.config.type !== 'bar' || chart.options.indexAxis === 'y') return;
  const canvasId = chart.canvas ? chart.canvas.id : (chart.ctx?.canvas?.id || '');
  if (canvasId === 'chart-ecg-fc-comparativa') return;
  const dsLabel = chart.data?.datasets?.[0]?.label || chart.config?.data?.datasets?.[0]?.label || '';
  if (dsLabel === 'Latidos por Minuto (lpm)') return;
  if (chart.options?.scales?.y?.min !== undefined && Number(chart.options.scales.y.min) > 0) return;
  if (chart.scales?.y?.min !== undefined && Number(chart.scales.y.min) > 0) return;
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
    yaxis: { labels: { maxWidth: 280, style: { colors: '#1e293b', fontSize: '12px', fontWeight: 600 } } },
    dataLabels: { enabled: true, offsetX: 0, offsetY: 0,
      style: { fontSize: '11px', fontWeight: 700, fontFamily: 'inherit', colors: ['#ffffff'] },
      background: { enabled: false }, dropShadow: UNIVERSAL_VALUE_LABEL_STYLE.apexDropShadow
    }
  };
}

// Rediseño defensivo del marcador puntual del Forest Plot:
// En vez de una línea vertical completa que cruza y solapa el texto,
// dibuja marcas cortas (notches) en los bordes superior e inferior y un rombo (diamond).
// Las marcas se ubican en los bordes exteriormente para que jamás crucen el texto interior.
function redesignForestPlotGoals(root) {
  const goalMarkers = root.querySelectorAll('.apexcharts-bar-goals-groups line, .apexcharts-goals-markers line, line.apexcharts-goal-marker');
  goalMarkers.forEach(line => {
    if (line.getAttribute('data-redesigned') === 'true') return;
    const y1 = parseFloat(line.getAttribute('y1'));
    const y2 = parseFloat(line.getAttribute('y2'));
    const x1 = parseFloat(line.getAttribute('x1'));
    if (isNaN(y1) || isNaN(y2) || isNaN(x1)) return;

    const barHeight = Math.abs(y2 - y1);
    if (barHeight < 15) return;

    const topY = Math.min(y1, y2);
    const bottomY = Math.max(y1, y2);

    // 1. Marca corta en el borde superior (hacia arriba en el borde): de topY - 7 a topY
    line.setAttribute('y1', String(topY - 7));
    line.setAttribute('y2', String(topY));
    line.setAttribute('stroke', '#0f172a');
    line.setAttribute('stroke-width', '3');
    line.setAttribute('stroke-linecap', 'round');
    line.setAttribute('data-redesigned', 'true');

    // 2. Marca corta en el borde inferior (hacia abajo en el borde): de bottomY a bottomY + 7
    const bottomTick = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    bottomTick.setAttribute('x1', String(x1));
    bottomTick.setAttribute('y1', String(bottomY));
    bottomTick.setAttribute('x2', String(x1));
    bottomTick.setAttribute('y2', String(bottomY + 7));
    bottomTick.setAttribute('stroke', '#0f172a');
    bottomTick.setAttribute('stroke-width', '3');
    bottomTick.setAttribute('stroke-linecap', 'round');
    bottomTick.setAttribute('class', 'forest-goal-bottom-tick');
    line.parentElement.appendChild(bottomTick);

    // 3. Rombo (diamond) en el borde superior apuntando exactamente a la prevalencia puntual
    const diamond = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    const dSize = 4;
    const pts = `${x1},${topY - dSize * 2} ${x1 + dSize},${topY - dSize} ${x1},${topY} ${x1 - dSize},${topY - dSize}`;
    diamond.setAttribute('points', pts);
    diamond.setAttribute('fill', '#0f172a');
    diamond.setAttribute('class', 'forest-goal-diamond');
    line.parentElement.appendChild(diamond);
  });
}

// Apex does not expose a per-point anchor callback. Position SVG labels from
// their actual measured bar/text dimensions after each render and update.
function dashboardPlaceApexLabels(chart) {
  const root = chart.w?.dom?.baseEl || chart.w?.globals?.dom?.baseEl;
  if (!root || !['bar', 'rangeBar'].includes(chart.w.config.chart.type)) return;
  const chartId = root.closest('[id]')?.id || '';
  const horizontal = chart.w.config.plotOptions?.bar?.horizontal;

  if (chartId === 'chart-rg-forest-prevalencias') {
    redesignForestPlotGoals(root);
  }

  const series = root.querySelectorAll('.apexcharts-bar-series .apexcharts-series, .apexcharts-rangebar-series .apexcharts-series, .apexcharts-series');
  const labels = root.querySelectorAll('.apexcharts-datalabels');
  const stackEdges = new Map();
  series.forEach((group, seriesIndex) => {
    const realIndex = Number(group.getAttribute('data:realIndex') ?? seriesIndex);
    const bars = group.querySelectorAll('.apexcharts-bar-area, .apexcharts-rangebar-area');
    bars.forEach((bar, index) => {
      const pointIndex = Number(bar.getAttribute('j') ?? index);
      const raw = chart.w.config.series[realIndex]?.data[pointIndex];
      const value = Number(raw && typeof raw === 'object' ? (raw.y !== undefined ? (Array.isArray(raw.y) ? raw.y[1] - raw.y[0] : raw.y) : raw) : raw);
      bar.style.display = Math.abs(value) > 0 || Array.isArray(raw?.y) ? '' : 'none';
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
      bar.removeAttribute('transform');
      let barRect = bar.getBoundingClientRect();
      let textRect = text.getBoundingClientRect();
      if (!textRect.width || !textRect.height) return;
      if (barRect.width < 1 || barRect.height < 1) {
        text.style.visibility = 'hidden';
        return;
      }
      text.style.visibility = 'visible';

      // Escalar geometría de barras apiladas (stacked) para garantizar que quepan las etiquetas
      // Aplica tanto a horizontal (100% stacked o conteo) como a vertical apilado (stacked: true).
      // En pirámides poblacionales o gráficos agrupados, no escalar ni encadenar stacks.
      const isPyramid = chartId === 'chart-ind-edad-sexo';
      const isStacked = Boolean(chart.w.config.chart.stacked && !isPyramid);
      const canScaleBar = isStacked;
      const minTextW = Math.max(48, (textRect.width || 0) + 12);
      const minTextH = Math.max(42, (textRect.height || 0) + 14);
      const scaleX = (canScaleBar && horizontal) ? Math.max(1, minTextW / barRect.width) : 1;
      const scaleY = (canScaleBar && !horizontal) ? Math.max(1, minTextH / barRect.height) : 1;
      if (canScaleBar && (scaleX > 1 || scaleY > 1 || stackEdges.has(pointIndex))) {
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
      } else {
        bar.removeAttribute('transform');
        if (isStacked) {
          stackEdges.set(pointIndex, horizontal ? barRect.right : barRect.top);
        }
      }
      barRect = bar.getBoundingClientRect();
      textRect = text.getBoundingClientRect();

      // Escalera de ajuste para texto en barras:
      // Medir tamaño real del texto y el espacio disponible de la forma
      let fontSize = 11;
      text.setAttribute('font-size', String(fontSize));
      text.querySelectorAll('tspan').forEach(ts => ts.setAttribute('font-size', String(fontSize)));
      textRect = text.getBoundingClientRect();

      let fitsInside = horizontal
        ? (barRect.width >= textRect.width + 14)
        : (barRect.height >= textRect.height + 6 && barRect.width >= textRect.width + 4);

      // Paso 3b: Si no cabe cómodamente, reducir fuente responsivamente (9.5px o 9px)
      if (!fitsInside) {
        fontSize = 9.5;
        text.setAttribute('font-size', String(fontSize));
        text.querySelectorAll('tspan').forEach(ts => ts.setAttribute('font-size', String(fontSize)));
        textRect = text.getBoundingClientRect();
        fitsInside = horizontal
          ? (barRect.width >= textRect.width + 12)
          : (barRect.height >= textRect.height + 4 && barRect.width >= textRect.width + 2);
        if (!fitsInside && !horizontal) {
          fontSize = 8.5;
          text.setAttribute('font-size', String(fontSize));
          text.querySelectorAll('tspan').forEach(ts => ts.setAttribute('font-size', String(fontSize)));
          textRect = text.getBoundingClientRect();
          fitsInside = (barRect.height >= textRect.height + 2 && barRect.width >= textRect.width);
        }
      }

      // Paso 3c/3d: En barras verticales con 2 líneas, optimizar texto para ganar espacio horizontal
      if (!fitsInside && !horizontal && text.querySelectorAll('tspan').length > 1) {
        text.querySelectorAll('tspan').forEach(ts => {
          const t = ts.textContent.trim();
          if (t.startsWith('(') && t.endsWith(')')) {
            ts.textContent = t.slice(1, -1);
          }
        });
        textRect = text.getBoundingClientRect();
        fitsInside = (barRect.height >= textRect.height + 2 && barRect.width >= textRect.width);
        // Si aún no cabe el ancho, recortar a valor esencial (Paso 3d)
        if (!fitsInside && barRect.width < textRect.width) {
          const tspans = text.querySelectorAll('tspan');
          const countVal = tspans[0].textContent.trim();
          while (text.firstChild) text.removeChild(text.firstChild);
          text.textContent = countVal;
          text.setAttribute('font-size', '9.5');
          textRect = text.getBoundingClientRect();
          fitsInside = (barRect.height >= textRect.height + 2 && barRect.width >= textRect.width);
        }
      }

      // Paso 3c: Si aún no cabe en una sola línea horizontal y la altura lo permite, partir en 2 líneas
      if (!fitsInside && horizontal && barRect.height >= 22 && text.querySelectorAll('tspan').length <= 1) {
        const fullContent = text.textContent.trim();
        const splitMatch = fullContent.match(/^(.*?)\s*[\(·]\s*([\d.,]+\s*%)\)?$/);
        if (splitMatch) {
          const l1 = splitMatch[1].trim();
          const l2 = splitMatch[2].trim().replace(/\)$/, '');
          while (text.firstChild) text.removeChild(text.firstChild);
          const ts1 = document.createElementNS('http://www.w3.org/2000/svg', 'tspan');
          ts1.setAttribute('x', '0');
          ts1.setAttribute('dy', '-0.55em');
          ts1.setAttribute('font-size', String(fontSize));
          ts1.textContent = l1;
          const ts2 = document.createElementNS('http://www.w3.org/2000/svg', 'tspan');
          ts2.setAttribute('x', '0');
          ts2.setAttribute('dy', '1.15em');
          ts2.setAttribute('font-size', String(fontSize));
          ts2.textContent = l2.startsWith('(') ? l2 : (l2.endsWith('%') ? `(${l2})` : `(${l2}%)`);
          text.appendChild(ts1);
          text.appendChild(ts2);
          textRect = text.getBoundingClientRect();
          fitsInside = (barRect.width >= textRect.width + 6);

          if (!fitsInside) {
            // Si ni en 2 líneas cabe cómodamente dentro de la barra, restaurar para Paso 3e
            text.textContent = fullContent;
            textRect = text.getBoundingClientRect();
          }
        }
      }

      // Paso 3e (Último recurso): si la dimensión que codifica el dato no permite contener el texto
      if (!fitsInside) {
        // La etiqueta sale junto a la forma con color de texto normal del dashboard (#0f172a, nunca blanco sobre fondo blanco)
        text.setAttribute('fill', '#0f172a');
        text.style.filter = 'none';
        text.querySelectorAll('tspan').forEach(ts => {
          ts.setAttribute('fill', '#0f172a');
          ts.style.fill = '#0f172a';
          const t = ts.textContent.trim();
          if (t.endsWith('%') && !t.startsWith('(')) {
            ts.textContent = `(${t})`;
          }
        });
        const matrix = text.getScreenCTM();
        if (matrix) {
          const inverse = matrix.inverse();
          if (horizontal) {
            const isNegativeVal = isPyramid && realIndex === 0;
            const dx = isNegativeVal ? ((barRect.left - 6) - textRect.right) : ((barRect.right + 6) - textRect.left);
            const dy = (barRect.top + barRect.height / 2) - (textRect.top + textRect.height / 2);
            text.setAttribute('transform', `translate(${inverse.a * dx + inverse.c * dy},${inverse.b * dx + inverse.d * dy})`);
          } else {
            const dx = (barRect.left + barRect.width / 2) - (textRect.left + textRect.width / 2);
            const dy = (barRect.top - 6) - textRect.bottom;
            text.setAttribute('transform', `translate(${inverse.a * dx + inverse.c * dy},${inverse.b * dx + inverse.d * dy})`);
          }
        }
      } else {
        // Dentro de la forma: siempre blanco (#ffffff) con sombra de referencia
        const dx = barRect.left + barRect.width / 2 - (textRect.left + textRect.width / 2);
        const dy = barRect.top + barRect.height / 2 - (textRect.top + textRect.height / 2);
        const matrix = text.getScreenCTM();
        if (matrix) {
          const inverse = matrix.inverse();
          text.setAttribute('transform', `translate(${inverse.a * dx + inverse.c * dy},${inverse.b * dx + inverse.d * dy})`);
        }
        text.setAttribute('fill', '#ffffff');
        text.style.filter = 'drop-shadow(1px 1px 1.5px rgba(15, 23, 42, 0.65))';
        text.style.fontFamily = 'inherit';
        text.style.fontWeight = '700';
        text.querySelectorAll('tspan').forEach(ts => {
          ts.setAttribute('fill', '#ffffff');
          ts.style.fill = '#ffffff';
        });
      }
    });
  });
}

function dashboardApexBarStyle(options, id) {
  const originalFormatter = options.dataLabels?.formatter;
  if (['pie', 'donut'].includes(options.chart?.type)) {
    return {
      ...options,
      plotOptions: {
        ...options.plotOptions,
        pie: {
          ...options.plotOptions?.pie,
          donut: {
            size: '28%',
            labels: { show: false }
          }
        }
      },
      dataLabels: {
        ...options.dataLabels,
        style: { fontSize: '11px', fontWeight: 700, fontFamily: 'inherit', colors: ['#ffffff'] },
        dropShadow: UNIVERSAL_VALUE_LABEL_STYLE.apexDropShadow
      }
    };
  }
  if (options.chart?.type === 'heatmap') {
    return {
      ...options,
      dataLabels: {
        ...options.dataLabels,
        style: {
          fontSize: '11px',
          fontWeight: 700,
          fontFamily: 'inherit',
          colors: [({ value }) => (Number(value) > 0 ? '#ffffff' : '#0f172a')]
        },
        dropShadow: UNIVERSAL_VALUE_LABEL_STYLE.apexDropShadow
      }
    };
  }
  if (!['bar', 'rangeBar'].includes(options.chart?.type)) return {
    ...options,
    dataLabels: { ...options.dataLabels,
      background: { enabled: false },
      style: { ...options.dataLabels?.style, colors: ['#ffffff'], fontWeight: 700, fontFamily: 'inherit' },
      dropShadow: UNIVERSAL_VALUE_LABEL_STYLE.apexDropShadow,
      formatter: (value, ctx) => dashboardLabelLines(originalFormatter ? originalFormatter(value, ctx) : value)
    }
  };
  // Keep the original horizontal/vertical distinction, rather than rotating all charts.
  const horizontal = ['chart-factores-modificables', 'chart-ind-edad-sexo', 'chart-ind-vivienda',
    'chart-fam-padres-madres', 'chart-fam-por-edad', 'chart-cov-por-categoria', 'chart-nc-comorbilidades',
    'chart-rg-forest-prevalencias', 'chart-covid-prevalencia-ic', 'chart-em-hormonas-ambiente',
    'chart-nc-sexo-categoria'].includes(id)
    || (options.plotOptions?.bar?.horizontal === true && ![
      'chart-exp-imc-cat', 'chart-exp-auscultacion', 'chart-mod-control-tto',
      'chart-mod-actividad-cat', 'chart-em-sueno',
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
  if (horizontal && !['chart-factores-modificables', 'chart-ind-edad-sexo', 'chart-covid-prevalencia-ic', 'chart-rg-forest-prevalencias'].includes(id)) {
    if (options.xaxis?.max === undefined) {
      delete xaxis.max;
    }
    if (xaxis.min === undefined) {
      xaxis.min = 0;
    }
  }
  if (!Array.isArray(yaxis)) {
    delete yaxis.max;
    yaxis.min = 0;
    if (horizontal) delete yaxis.title;
  }
  const styled = {
    ...options,
    chart: { ...options.chart, events: { ...events, ...labelEvents }, fontFamily: 'inherit', foreColor: '#1e293b', fontSize: '12px',
      height: options.chart?.height || Math.max(320, (options.xaxis?.categories?.length || 1) * (options.series?.length > 1 && !options.chart.stacked ? 76 : 48) + 90) },
    grid: { borderColor: '#e8eef5', strokeDashArray: 4, padding: id === 'chart-ind-edad-sexo' ? { right: 24, left: 24, top: 24 } : (horizontal ? { right: 90, left: 8, top: 36 } : { right: 20, left: 16, top: 20, bottom: 25 }) },
    fill: { type: 'solid', opacity: 1 },
    plotOptions: { ...options.plotOptions, bar: {
      borderRadius: 6, barHeight: bar.barHeight || '78%', columnWidth: bar.columnWidth || '72%',
      ...bar, horizontal,
      dataLabels: { position: 'center', hideOverflowingLabels: false, ...bar.dataLabels },
      colors: {
        backgroundBarRadius: 6,
        backgroundBarColors: (id === 'chart-ecg-hist-qtc' || (bar.colors && Array.isArray(bar.colors.backgroundBarColors)))
          ? (bar.colors?.backgroundBarColors || [])
          : ['#f1f5f9'],
        ...bar.colors
      }
    } },
    xaxis: { ...xaxis, axisBorder: { show: false }, axisTicks: { show: false } },
    yaxis,
    dataLabels: { ...options.dataLabels, enabled: true, offsetX: 0, offsetY: 0,
      formatter: (value, ctx) => {
        if (originalFormatter) {
          const res = originalFormatter(value, ctx);
          if (Array.isArray(res)) return res;
          if (String(res).includes('·') || String(res).includes('IC 95%:')) return res;
          return horizontal ? dashboardLabelLines(res, true) : dashboardVerticalLabel(res);
        }
        if (!(Number(value) > 0)) return '';
        return horizontal ? dashboardLabelLines(value, true) : dashboardVerticalLabel(value);
      },
      style: { fontSize: '11px', fontWeight: 700, fontFamily: 'inherit', colors: ['#ffffff'] },
      background: { enabled: false },
      dropShadow: UNIVERSAL_VALUE_LABEL_STYLE.apexDropShadow
    }
  };
  return horizontal ? dashboardMergeStyle(dashboardHorizontalStyle(), styled) : styled;
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
  if (['doughnut', 'pie'].includes(config.type)) {
    // Ensanchar grosor del pastel: orificio interior moderado (28%) para maximizar área de rebanada
    options.cutout = '28%';
    options.plugins.legend = dashboardMergeStyle(options.plugins.legend || {}, {
      position: 'bottom',
      labels: {
        usePointStyle: true,
        pointStyle: 'circle',
        boxWidth: 10,
        padding: 16,
        color: '#0f172a',
        font: { size: 12, weight: '600' }
      }
    });
    options.plugins.datalabels = {
      ...originalLabels,
      display: (ctx) => {
        if (typeof originalLabels.display === 'function') {
          return originalLabels.display(ctx);
        }
        const v = Number(ctx.dataset.data[ctx.dataIndex]) || 0;
        const sum = ctx.dataset.data.reduce((a, b) => a + (Number(b) || 0), 0) || 1;
        return (v / sum) >= 0.06;
      },
      color: '#ffffff',
      textStrokeColor: 'rgba(15, 23, 42, 0.50)',
      textStrokeWidth: 2,
      textShadowBlur: 3,
      textShadowColor: 'rgba(0, 0, 0, 0.35)',
      anchor: 'center',
      align: 'center',
      textAlign: 'center',
      backgroundColor: 'transparent',
      font: (ctx) => {
        if (typeof originalLabels.font === 'function') {
          return originalLabels.font(ctx);
        }
        const v = Number(ctx.dataset.data[ctx.dataIndex]) || 0;
        const sum = ctx.dataset.data.reduce((a, b) => a + (Number(b) || 0), 0) || 1;
        const pct = v / sum;
        if (pct >= 0.25) return { size: 12, weight: 'bold', family: 'inherit', lineHeight: 1.15 };
        if (pct >= 0.10) return { size: 11, weight: 'bold', family: 'inherit', lineHeight: 1.15 };
        return { size: 9.5, weight: 'bold', family: 'inherit', lineHeight: 1.1 };
      },
      formatter: (value, ctx) => {
        const val = Number(value) || 0;
        const total = ctx.dataset.data.reduce((a, b) => a + (Number(b) || 0), 0) || 1;
        const pct = ((val / total) * 100).toFixed(1).replace('.', ',');
        if (typeof originalLabels.formatter === 'function') {
          const res = originalLabels.formatter(value, ctx);
          if (Array.isArray(res)) return res;
          if (typeof res === 'string' && res.includes('\n')) return res.split('\n');
          const match = String(res).match(/^(.*?)\s*\(?([\d.,]+\s*%)\)?$/);
          if (match) {
            return [match[1].trim(), `(${match[2]})`];
          }
          return res;
        }
        return [String(val), `(${pct}%)`];
      }
    };
    return;
  }
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
  const isLpm = config.data.datasets[0]?.label === 'Latidos por Minuto (lpm)' || options.scales[valueAxis]?.min !== undefined;
  if (options.scales[valueAxis] && !isLpm) {
    delete options.scales[valueAxis].max;
  }
  options.scales[categoryAxis] = dashboardMergeStyle(options.scales[categoryAxis] || {}, {
    grid: { display: false }, border: { display: false },
    ticks: { maxRotation: 0, minRotation: 0, color: '#1e293b', font: { size: 12, weight: '600' } }
  });
  options.scales[valueAxis] = dashboardMergeStyle(options.scales[valueAxis] || {}, {
    beginAtZero: !isLpm, grid: { color: '#edf2f7' }, border: { display: false },
    ticks: { precision: 0, color: '#1e293b', font: { size: 12, weight: '600' } }
  });
  config.data.datasets.forEach(dataset => Object.assign(dataset, {
    maxBarThickness: 76, categoryPercentage: 0.8, barPercentage: 0.9, borderRadius: 4
  }));
  const oldLabels = options.plugins.datalabels || {};
  options.plugins.datalabels = {
    ...oldLabels,
    display: ctx => Boolean(ctx?.dataset?.data && Number(ctx.dataset.data[ctx.dataIndex]) > 0),
    color: '#ffffff',
    textStrokeColor: 'rgba(15, 23, 42, 0.50)',
    textStrokeWidth: 2,
    textShadowBlur: 3,
    textShadowColor: 'rgba(0, 0, 0, 0.35)',
    anchor: isLpm ? 'end' : (oldLabels.anchor || 'center'),
    align: isLpm ? 'bottom' : (oldLabels.align || 'center'),
    offset: isLpm ? 16 : (oldLabels.offset !== undefined ? oldLabels.offset : 0),
    clip: false,
    font: (ctx) => {
      const customFont = typeof oldLabels.font === 'function' ? oldLabels.font(ctx) : oldLabels.font;
      return {
        family: 'inherit',
        weight: 'bold',
        size: customFont?.size || 11,
        lineHeight: 1.15
      };
    },
    borderWidth: 0, borderRadius: 4,
    padding: 0, textAlign: 'center', backgroundColor: 'transparent',
    formatter: (value, ctx) => {
      if (oldLabels.formatter) {
        const formatted = oldLabels.formatter(value, ctx);
        if (Array.isArray(formatted)) return formatted;
        if (typeof formatted === 'string' && formatted.endsWith(' lpm')) return formatted;
        return horizontal ? dashboardLabelLines(formatted, true) : dashboardVerticalLabel(formatted);
      }
      return horizontal ? dashboardLabelLines(value, true) : dashboardVerticalLabel(value);
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
  const isSpecialBar = element?.id === 'chart-ecg-fc-comparativa'
    || config.data?.datasets?.[0]?.label === 'Latidos por Minuto (lpm)'
    || config.options?.scales?.y?.min !== undefined;
  if (config.type === 'bar' && config.options.indexAxis !== 'y' && !isSpecialBar) {
    const formatLabel = config.options.plugins.datalabels.formatter;
    config.plugins = [...(config.plugins || []), {
      id: 'dashboard-fit-vertical-labels',
      afterDatasetsUpdate: chart => dashboardFitVerticalChartJsBars(chart, formatLabel)
    }];
  }
  return new Chart(element, config);
}
