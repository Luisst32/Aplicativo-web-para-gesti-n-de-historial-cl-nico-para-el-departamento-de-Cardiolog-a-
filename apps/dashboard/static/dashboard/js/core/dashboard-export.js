const DASHBOARD_TABS = [
  { id: 'resumen-general', title: 'Resumen General Epidemiológico' },
  { id: 'datos-individuo', title: 'Datos del Individuo y Filiación' },
  { id: 'exploracion-fisica', title: 'Exploración Física y Antropometría' },
  { id: 'factores-modificables', title: 'Factores de Riesgo Modificables' },
  { id: 'factores-emergentes', title: 'Factores de Riesgo Emergentes' },
  { id: 'antecedentes-familiares', title: 'Antecedentes Familiares Cardiovasculares' },
  { id: 'historia-no-cardio', title: 'Historia Clínica No Cardiovascular' },
  { id: 'covid-19', title: 'COVID-19 y Secuelas Post-Infección' },
  { id: 'electrocardiograma', title: 'Resultados del Electrocardiograma (ECG)' }
];

const DASHBOARD_EXPORT_CONTENT_WIDTH_MM = 277;
const DASHBOARD_EXPORT_CONTENT_HEIGHT_MM = 164;
const DASHBOARD_EXPORT_CSS_PX_PER_MM = 96 / 25.4;
const DASHBOARD_EXPORT_CONTENT_WIDTH_PX = Math.round(
  DASHBOARD_EXPORT_CONTENT_WIDTH_MM * DASHBOARD_EXPORT_CSS_PX_PER_MM
);
const DASHBOARD_EXPORT_CONTENT_HEIGHT_PX = Math.round(
  DASHBOARD_EXPORT_CONTENT_HEIGHT_MM * DASHBOARD_EXPORT_CSS_PX_PER_MM
);
const DASHBOARD_EXPORT_FONT_STACK = "'Inter', 'Segoe UI', Arial, Helvetica, sans-serif";

function openExportModal() {
  const modal = document.getElementById('modal-export-dashboard');
  if (modal) {
    modal.style.display = 'flex';
    const curTab = DASHBOARD_TABS.find(t => t.id === activeTabId) || DASHBOARD_TABS[0];
    const lbl = document.getElementById('export-current-tab-name');
    if (lbl) lbl.textContent = curTab.title;
    const prog = document.getElementById('export-progress-container');
    if (prog) prog.style.display = 'none';
    const btn = document.getElementById('btn-do-export');
    if (btn) btn.disabled = false;
  } else {
    console.warn('Modal de exportación #modal-export-dashboard no encontrado en el DOM.');
  }
}

// Exposición explícita global para llamadas inline y listeners
window.openExportModal = openExportModal;
window.closeExportModal = closeExportModal;
window.startExport = startExport;

// Enlace defensivo directo al botón de exportar
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.btn-export-dashboard').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      openExportModal();
    });
  });
});

function closeExportModal() {
  const modal = document.getElementById('modal-export-dashboard');
  if (modal) modal.style.display = 'none';
}

// Obtiene metadatos legibles de los filtros activos sin exponer valores crudos como "all"
function getExportCohortMetadata() {
  const readSelectLabel = (id, fallbackAll) => {
    const el = document.getElementById(id);
    if (!el) return fallbackAll;
    const val = (el.value || '').trim();
    if (!val || val.toLowerCase() === 'all') return fallbackAll;
    const selectedOpt = el.options && el.selectedIndex >= 0 ? el.options[el.selectedIndex] : null;
    return (selectedOpt?.textContent || val).trim();
  };

  const instLabel = readSelectLabel('slicer-inst', 'Todas las Instituciones');
  const anoEl = document.getElementById('slicer-ano');
  const rawAno = (anoEl?.value || '').trim();
  const anoLabel = (!rawAno || rawAno.toLowerCase() === 'all')
    ? 'Todos los años'
    : (rawAno.toLowerCase().startsWith('año') ? rawAno : `Año ${rawAno}`);

  const activeExtras = [];
  const catEl = document.getElementById('slicer-cat');
  if (catEl && catEl.value && catEl.value !== 'all') activeExtras.push(catEl.value.trim());
  const sexoEl = document.getElementById('slicer-sexo');
  if (sexoEl && sexoEl.value && sexoEl.value !== 'all') activeExtras.push(sexoEl.value.trim());
  const edadEl = document.getElementById('slicer-edad');
  if (edadEl && edadEl.value && edadEl.value !== 'all') activeExtras.push(edadEl.value.trim());
  const riesgoEl = document.getElementById('slicer-riesgo');
  if (riesgoEl && riesgoEl.value && riesgoEl.value !== 'all') activeExtras.push(riesgoEl.value.trim());
  const codigoEl = document.getElementById('slicer-codigo');
  if (codigoEl && codigoEl.value && codigoEl.value.trim()) activeExtras.push(`Ficha #${codigoEl.value.trim()}`);

  const evalCount = Array.isArray(filteredRecords) ? filteredRecords.length : 0;
  const totalCount = Array.isArray(allRecords) ? allRecords.length : evalCount;
  const pct = totalCount > 0 ? ((evalCount / totalCount) * 100).toFixed(1).replace('.', ',') : '0,0';
  const sampleText = `${evalCount} de ${totalCount} evaluados (${pct}%)`;
  const todayStr = new Date().toLocaleDateString('es-EC', { year: 'numeric', month: 'long', day: 'numeric' });
  const filterSuffix = activeExtras.length ? ` • ${activeExtras.join(' · ')}` : '';

  return {
    instLabel,
    anoLabel,
    activeExtras,
    evalCount,
    totalCount,
    sampleText,
    todayStr,
    headerSummary: `Cohorte: ${evalCount} de ${totalCount} evaluados | ${instLabel} • ${anoLabel}${filterSuffix} | ${todayStr}`
  };
}

// Controlador de inicio de exportación
async function startExport() {
  const formatEl = document.querySelector('input[name="export-format"]:checked');
  const scopeEl = document.querySelector('input[name="export-scope"]:checked');
  const format = formatEl ? formatEl.value : 'pdf';
  const scope = scopeEl ? scopeEl.value : 'current';

  const btn = document.getElementById('btn-do-export');
  const progBox = document.getElementById('export-progress-container');
  const progText = document.getElementById('export-progress-text');
  const progBar = document.getElementById('export-progress-bar');
  const modalBackdrop = document.getElementById('modal-export-dashboard');

  if (btn) btn.disabled = true;
  if (progBox) progBox.style.display = 'flex';
  if (modalBackdrop) {
    modalBackdrop.style.background = 'rgba(15, 23, 42, 0.94)';
  }
  document.body.style.overflow = 'hidden';

  const setProgress = (text, pct) => {
    if (progText) progText.textContent = text;
    if (progBar) progBar.style.width = `${pct}%`;
  };

  const nextFrame = () => new Promise(resolve => requestAnimationFrame(resolve));

  try {
    setProgress('Iniciando exportación de alta velocidad...', 6);
    await nextFrame();

    if (format === 'csv') {
      await exportCsv(scope, setProgress);
    } else if (format === 'image') {
      await exportImage(scope, setProgress);
    } else if (format === 'pptx') {
      await exportPowerPoint(scope, setProgress);
    } else {
      await exportPdf(scope, setProgress);
    }
    setTimeout(() => {
      closeExportModal();
    }, 350);
  } catch (err) {
    console.error('Error durante la exportación:', err);
    alert('Ocurrió un inconveniente al generar la exportación: ' + (err.message || err));
  } finally {
    if (btn) btn.disabled = false;
    if (progBox) progBox.style.display = 'none';
    if (modalBackdrop) {
      modalBackdrop.style.background = 'rgba(15, 23, 42, 0.72)';
    }
    document.body.style.overflow = '';
  }
}

// Helper para normalizar gradientes, desactivar clipPath problemáticos y asegurar visibilidad de rellenos SVG
function fixSvgFillsForHtml2Canvas(clonedDoc, tabId, rootOverride = null) {
  if (!clonedDoc) return;
  try {
    const root = rootOverride || (tabId ? clonedDoc.getElementById('tab-' + tabId) : null) || clonedDoc;

    // 1. Desactivar clip-path SVG que trunca etiquetas y barras en exportación
    root.querySelectorAll('[clip-path], [clipPath], [style*="clip-path"]').forEach(el => {
      if (el.hasAttribute('clip-path')) el.removeAttribute('clip-path');
      if (el.hasAttribute('clipPath')) el.removeAttribute('clipPath');
      if (el.style && el.style.clipPath) el.style.clipPath = 'none';
    });

    // 2. Normalizar rellenos con gradientes url(#...)
    const svgElements = root.querySelectorAll('svg [fill*="url("]');
    svgElements.forEach(el => {
      const fillAttr = el.getAttribute('fill') || '';
      const match = fillAttr.match(/url\(#?([^)]+)\)/);
      if (match) {
        const gradId = match[1].replace(/["']/g, '');
        const grad = clonedDoc.getElementById(gradId) || document.getElementById(gradId);
        if (grad) {
          const stop = grad.querySelector('stop');
          if (stop) {
            const color = stop.getAttribute('stop-color') || stop.style.stopColor;
            if (color) {
              el.setAttribute('fill', color);
              el.style.fill = color;
              el.setAttribute('fill-opacity', '1');
              el.style.fillOpacity = '1';
            }
          }
        }
      }
    });

    root.querySelectorAll('.apexcharts-bar-area, .apexcharts-series path, .apexcharts-area').forEach(el => {
      const fill = el.getAttribute('fill') || el.style?.fill || '';
      if (fill.startsWith('url(')) {
        const match = fill.match(/url\(#?([^)]+)\)/);
        if (match) {
          const gradId = match[1].replace(/["']/g, '');
          const grad = clonedDoc.getElementById(gradId) || document.getElementById(gradId);
          if (grad) {
            const stop = grad.querySelector('stop');
            if (stop) {
              const color = stop.getAttribute('stop-color') || stop.style.stopColor;
              if (color) {
                el.setAttribute('fill', color);
                el.style.fill = color;
                el.setAttribute('fill-opacity', '1');
                el.style.fillOpacity = '1';
              }
            }
          }
        }
      }
    });
  } catch (err) {
    console.warn('Advertencia en fixSvgFillsForHtml2Canvas:', err);
  }
}

// Títulos ejecutivos por sección clínica
function getTabPartsConfig(tabId) {
  const configs = {
    'resumen-general': {
      splitIdx: 3,
      part1Title: 'Resumen General • Indicadores Clave y Tendencia Epidemiológica',
      part2Title: 'Resumen General • Distribución Sociodemográfica y Estratificación',
      extraTitle: 'Resumen General • Análisis Estadístico Avanzado (IC 95% Wilson)'
    },
    'datos-individuo': {
      splitIdx: 3,
      part1Title: 'Datos del Individuo • Demografía, Edad y Nivel Educativo',
      part2Title: 'Datos del Individuo • Estado Civil y Régimen de Vivienda',
      extraTitle: 'Datos del Individuo • Gradientes Socioeconómicos de Riesgo'
    },
    'exploracion-fisica': {
      splitIdx: 3,
      part1Title: 'Exploración Física • Antropometría y Correlación Corporal',
      part2Title: 'Exploración Física • Presión Arterial y Auscultación Cardíaca',
      extraTitle: 'Exploración Física • Análisis Hemodinámico y Correlaciones'
    },
    'factores-modificables': {
      splitIdx: 5,
      part1Title: 'Factores de Riesgo Modificables • Prevalencia y Control Terapéutico',
      part2Title: 'Factores de Riesgo Modificables • Hábitos, Actividad Física y Dieta',
      extraTitle: 'Factores de Riesgo Modificables • Co-ocurrencia y Patrón PREDIMED'
    },
    'factores-emergentes': {
      splitIdx: 3,
      part1Title: 'Factores de Riesgo Emergentes • Sueño, Estrés y Perfil Psicosocial',
      part2Title: 'Factores de Riesgo Emergentes • Personalidad Tipo A y Exposición Laboral',
      extraTitle: 'Factores de Riesgo Emergentes • Interacción Psicosocial e Hipertensión'
    },
    'antecedentes-familiares': {
      splitIdx: 3,
      part1Title: 'Antecedentes Familiares • Carga Genética Paterna y Materna',
      part2Title: 'Antecedentes Familiares • Historia Familiar por Edad y Coexistencia',
      extraTitle: 'Antecedentes Familiares • Concordancia Genética vs. Diagnóstico Propio'
    },
    'historia-no-cardio': {
      splitIdx: 3,
      part1Title: 'Historia Clínica No Cardiovascular • Comorbilidades y Salud Mental',
      part2Title: 'Historia Clínica No Cardiovascular • Patología Respiratoria e Inmunológica',
      extraTitle: 'Historia Clínica No Cardiovascular • Comorbilidades por Sexo y Categoría'
    },
    'covid-19': {
      splitIdx: 3,
      part1Title: 'COVID-19 y Secuelas • Historial de Infección y Espectro Clínico',
      part2Title: 'COVID-19 y Secuelas • Distribución por Personal, Género y Edad',
      extraTitle: 'COVID-19 y Secuelas • Prevalencia con IC 95% y Síndrome Long-COVID'
    },
    'electrocardiograma': {
      splitIdx: 3,
      part1Title: 'Electrocardiograma • Ritmo Cardíaco e Intervalos de Conducción',
      part2Title: 'Electrocardiograma • Anomalías Eléctricas y Frecuencia Cardíaca',
      extraTitle: 'Electrocardiograma • Intervalo QTc Bazett y Análisis Especializado'
    }
  };

  return configs[tabId] || {
    splitIdx: 3,
    part1Title: 'Indicadores y Distribución Epidemiológica',
    part2Title: 'Análisis Clínico Complementario',
    extraTitle: 'Análisis Estadístico Avanzado'
  };
}

function isExportCardVisible(card) {
  if (!card) return false;
  if (card.hidden || card.style.display === 'none') return false;
  return true;
}

// Detecta todas las filas visuales reales de gráficas visibles dentro de una sección.
function getPdfVisualRows(targetEl) {
  const sourceRows = Array.from(targetEl.children).filter(child =>
    child && child.nodeType === 1 && child.tagName === 'DIV' &&
    !child.classList.contains('kpi-row') &&
    (child.classList.contains('grid-row') || child.classList.contains('grid'))
  );
  const allCards = Array.from(targetEl.querySelectorAll('.card-visual'));
  const cards = [];
  const visualRows = [];

  sourceRows.forEach(sourceRow => {
    const rowVisibleCards = Array.from(sourceRow.children)
      .filter(child => child.classList.contains('card-visual') && isExportCardVisible(child));
    if (!rowVisibleCards.length) return;

    let pending = [];
    const flushPending = () => {
      if (!pending.length) return;
      visualRows.push({
        cardIndexes: pending.map(item => item.domIndex),
        titles: pending.map(item => item.title).filter(Boolean),
        chartHeight: Math.max(...pending.map(item => item.chartHeight))
      });
      pending = [];
    };

    rowVisibleCards.forEach(card => {
      const domIndex = allCards.indexOf(card);
      if (domIndex < 0) return;

      const containers = Array.from(card.querySelectorAll('.chart-container'));
      const explicitHeights = containers.flatMap(container => {
        const values = [container.style.height, container.style.minHeight];
        values.push(...Array.from(container.querySelectorAll('.chart-skeleton-placeholder')).map(el => el.style.height));
        return values.map(value => Number.parseInt(value, 10)).filter(Number.isFinite);
      });
      const maxExplicitHeight = explicitHeights.length ? Math.max(...explicitHeights) : 340;
      const chartHeight = Math.max(360, maxExplicitHeight);
      const heading = card.querySelector('.visual-title h3, h3')?.textContent?.trim() || '';
      const styleAttr = card.getAttribute('style') || '';
      const spansFullWidth = rowVisibleCards.length === 1 ||
        /\/\s*-1/.test(styleAttr) ||
        maxExplicitHeight >= 480 ||
        Boolean(card.querySelector('#chart-ecg-anomalias, #chart-mod-actividad-cat, #chart-mod-predimed-items'));

      const entry = { element: card, domIndex, chartHeight, title: heading };
      cards.push(entry);

      if (spansFullWidth) {
        flushPending();
        visualRows.push({
          cardIndexes: [domIndex],
          titles: heading ? [heading] : [],
          chartHeight
        });
        return;
      }

      pending.push(entry);
      if (pending.length === 2) flushPending();
    });

    flushPending();
  });

  return { cards, visualRows };
}

// Paginación de calidad presentación ejecutiva:
// Exactamente 1 fila visual de gráficas por lámina horizontal (100% ancho útil,
// escala 1:1 sin encogimiento, números grandes y nítidos).
function getTabExportItems(tab) {
  const targetEl = document.getElementById('tab-' + tab.id);
  const cfg = getTabPartsConfig(tab.id);
  const { visualRows } = targetEl ? getPdfVisualRows(targetEl) : { visualRows: [] };

  if (!visualRows.length) {
    return [{
      tab,
      partNumber: 1,
      title: cfg.part1Title,
      suffix: 'lamina_1',
      layout: null
    }];
  }

  return visualRows.map((row, pageIndex) => {
    let slideTitle = cfg.part1Title;
    if (pageIndex === 1) {
      slideTitle = cfg.part2Title;
    } else if (pageIndex >= 2) {
      slideTitle = cfg.extraTitle || cfg.part2Title;
    }

    const includeKpis = pageIndex === 0;
    const preferredHeight = includeKpis
      ? 410
      : Math.max(460, Math.min(515, row.chartHeight));

    return {
      tab,
      title: slideTitle,
      partNumber: pageIndex + 1,
      suffix: `lamina_${pageIndex + 1}`,
      layout: {
        visualRows: [row.cardIndexes],
        includeKpis,
        chartHeight: preferredHeight
      }
    };
  });
}

function getPdfExportItems(scope) {
  const tabs = scope === 'all'
    ? DASHBOARD_TABS
    : [DASHBOARD_TABS.find(t => t.id === activeTabId) || DASHBOARD_TABS[0]];

  return tabs.flatMap(tab => getTabExportItems(tab));
}

// Unifica los bloques de exportación para PDF, PPTX e Imágenes PNG de alta resolución
function getExportItems(scope) {
  return getPdfExportItems(scope);
}

// Clona recursivamente opciones/datos de Chart.js preservando callbacks (formatter/display)
// y omitiendo referencias internas o nodos del DOM.
function cloneChartConfigValue(val, depth = 0) {
  if (depth > 12 || val === null || val === undefined) return val;
  if (typeof val === 'function' || typeof val !== 'object') return val;
  if (
    (typeof HTMLElement !== 'undefined' && val instanceof HTMLElement) ||
    (typeof CanvasRenderingContext2D !== 'undefined' && val instanceof CanvasRenderingContext2D)
  ) {
    return undefined;
  }
  if (Array.isArray(val)) {
    return val.map(item => cloneChartConfigValue(item, depth + 1));
  }
  const copy = {};
  Object.keys(val).forEach(key => {
    if (key.startsWith('_') || key.startsWith('$') || key === 'chart' || key === 'canvas' || key === 'ctx') {
      return;
    }
    const cloned = cloneChartConfigValue(val[key], depth + 1);
    if (cloned !== undefined) copy[key] = cloned;
  });
  return copy;
}

// Renderiza un gráfico Chart.js en un lienzo offscreen Ultra-HD (4x DPI / ~384 DPI)
// al tamaño exacto de su contenedor de exportación con etiquetas numéricas de alto contraste.
function renderExportChartJsDataUrl(sourceCanvas, targetWidthPx, targetHeightPx) {
  const width = Math.max(360, Math.round(targetWidthPx || sourceCanvas.clientWidth || 500));
  const height = Math.max(280, Math.round(targetHeightPx || sourceCanvas.clientHeight || 400));

  const liveChart = (window.Chart && typeof window.Chart.getChart === 'function'
    ? window.Chart.getChart(sourceCanvas)
    : null) || Object.values(typeof charts !== 'undefined' ? charts : {}).find(c => c && c.canvas === sourceCanvas);

  if (!liveChart || typeof window.Chart !== 'function') {
    return sourceCanvas.toDataURL('image/png');
  }

  let offscreenWrap = null;
  let tempChart = null;
  try {
    const rawCfg = liveChart.config?._config || liveChart.config || {};
    const type = rawCfg.type || liveChart.config?.type || 'bar';
    const data = cloneChartConfigValue(liveChart.data);
    const options = cloneChartConfigValue(rawCfg.options || liveChart.options || {});
    const plugins = Array.isArray(rawCfg.plugins) ? [...rawCfg.plugins] : [];

    const isCircular = type === 'doughnut' || type === 'pie';

    options.responsive = false;
    options.maintainAspectRatio = false;
    options.animation = false;
    options.devicePixelRatio = 2.5;

    options.layout = options.layout || {};
    options.layout.padding = isCircular
      ? { top: 14, right: 16, bottom: 10, left: 16 }
      : { top: 30, right: 24, bottom: 10, left: 10 };

    options.plugins = options.plugins || {};
    if (options.plugins.legend && options.plugins.legend.display !== false) {
      options.plugins.legend = {
        ...options.plugins.legend,
        labels: {
          ...(options.plugins.legend.labels || {}),
          color: '#0F172A',
          boxWidth: 11,
          padding: 15,
          font: {
            family: DASHBOARD_EXPORT_FONT_STACK,
            size: 13,
            weight: '700'
          }
        }
      };
    }

    if (options.scales && typeof options.scales === 'object') {
      Object.keys(options.scales).forEach(axisKey => {
        const scaleCfg = options.scales[axisKey];
        if (!scaleCfg || typeof scaleCfg !== 'object') return;
        scaleCfg.ticks = {
          ...(scaleCfg.ticks || {}),
          color: '#0F172A',
          font: {
            ...(scaleCfg.ticks?.font || {}),
            family: DASHBOARD_EXPORT_FONT_STACK,
            size: 12.5,
            weight: '600'
          }
        };
        if (scaleCfg.title) {
          scaleCfg.title = {
            ...scaleCfg.title,
            color: '#0F172A',
            font: {
              ...(scaleCfg.title.font || {}),
              family: DASHBOARD_EXPORT_FONT_STACK,
              size: 13,
              weight: '700'
            }
          };
        }
      });
    }

    // Etiquetas de valor limpias sin recuadro de fondo: letras blancas nítidas sobre figuras de color
    if (options.plugins.datalabels) {
      const origDl = options.plugins.datalabels;
      const isOutsideLabel = origDl.anchor === 'end' && (origDl.align === 'bottom' || origDl.align === 'top' || origDl.align === 'end');
      options.plugins.datalabels = {
        ...origDl,
        clip: false,
        color: isOutsideLabel ? '#0F172A' : '#FFFFFF',
        backgroundColor: 'transparent',
        borderColor: 'transparent',
        borderWidth: 0,
        borderRadius: 0,
        padding: 0,
        textStrokeWidth: 0,
        textStrokeColor: 'transparent',
        textShadowBlur: isOutsideLabel ? 0 : 4,
        textShadowColor: isOutsideLabel ? 'transparent' : 'rgba(15, 23, 42, 0.52)',
        font: (ctx) => {
          if (isCircular && ctx?.dataset?.data) {
            const v = Number(ctx.dataset.data[ctx.dataIndex]) || 0;
            const sum = ctx.dataset.data.reduce((a, b) => a + (Number(b) || 0), 0) || 1;
            const ratio = v / sum;
            return {
              family: DASHBOARD_EXPORT_FONT_STACK,
              weight: '700',
              size: ratio >= 0.14 ? 14 : 12.5,
              lineHeight: 1.18
            };
          }
          return {
            family: DASHBOARD_EXPORT_FONT_STACK,
            weight: '700',
            size: 13,
            lineHeight: 1.18
          };
        }
      };
    }

    offscreenWrap = document.createElement('div');
    offscreenWrap.style.cssText = `position:fixed;left:-100000px;top:0;width:${width}px;height:${height}px;overflow:visible;pointer-events:none;background:#FFFFFF;`;
    const offCanvas = document.createElement('canvas');
    if (sourceCanvas.id) offCanvas.id = `${sourceCanvas.id}-export-hd`;
    offCanvas.width = width;
    offCanvas.height = height;
    offCanvas.style.cssText = `width:${width}px;height:${height}px;display:block;`;
    offscreenWrap.appendChild(offCanvas);
    document.body.appendChild(offscreenWrap);

    tempChart = new window.Chart(offCanvas, { type, data, options, plugins });
    tempChart.update('none');
    return offCanvas.toDataURL('image/png');
  } catch (err) {
    console.warn('Fallback en renderExportChartJsDataUrl:', err);
    return sourceCanvas.toDataURL('image/png');
  } finally {
    if (tempChart) {
      try { tempChart.destroy(); } catch (e) {}
    }
    if (offscreenWrap) {
      offscreenWrap.remove();
    }
  }
}

// Optimiza los gráficos vectoriales SVG de ApexCharts dentro del escenario de exportación:
// - Restaura etiquetas de eje X ocultadas por colisión en anchos reducidos.
// - Elimina filtros borrosos drop-shadow para preservar vectores puros en Chromium PDF.
// - Inserta cápsulas vectoriales de alto contraste (sin doble trazo de texto) para nitidez absoluta.
// - Resuelve colisiones entre cápsulas cercanas (ej. líneas con valores próximos).
// - Recalcula dinámicamente el viewBox ajustado al contenido real sin márgenes muertos ni recortes.
function enhanceApexSvgForExport(cloneRoot, sourceTabEl = null) {
  if (!cloneRoot) return;
  fixSvgFillsForHtml2Canvas(document, null, cloneRoot);

  const allApexInstances = Object.values(typeof charts !== 'undefined' ? charts : {}).filter(
    c => c && c.w && c.w.config
  );

  const svgs = cloneRoot.querySelectorAll('svg.apexcharts-svg, .chart-container svg');
  svgs.forEach(svg => {
    if (svg.closest('.forest-methodology-note, .visual-header')) return;

    const containerEl = svg.closest('.chart-container');
    const containerId = containerEl?.id || '';
    const sourceContainer = (containerId && sourceTabEl)
      ? sourceTabEl.querySelector(`#${CSS.escape(containerId)}`)
      : null;
    const apexInst = sourceContainer
      ? allApexInstances.find(inst =>
          inst.el === sourceContainer ||
          inst.w?.globals?.dom?.baseEl === sourceContainer ||
          inst.w?.globals?.dom?.baseEl?.parentElement === sourceContainer
        )
      : null;

    const origAttrW = parseFloat(svg.getAttribute('width')) || svg.clientWidth || 480;
    const origAttrH = parseFloat(svg.getAttribute('height')) || svg.clientHeight || 340;

    // 0. Restaurar etiquetas del eje X que ApexCharts haya vaciado por colisión horizontal
    if (apexInst && !apexInst.w?.config?.plotOptions?.bar?.horizontal) {
      const categories = apexInst.w?.config?.xaxis?.categories;
      const xLabelNodes = Array.from(svg.querySelectorAll('.apexcharts-xaxis-texts-g text.apexcharts-xaxis-label'));
      if (Array.isArray(categories) && categories.length === xLabelNodes.length && xLabelNodes.length > 1) {
        const hadHiddenLabel = xLabelNodes.some((node, idx) => !node.textContent.trim() && categories[idx]);
        if (hadHiddenLabel) {
          xLabelNodes.forEach((node, idx) => {
            const rawCat = categories[idx];
            if (rawCat === undefined || rawCat === null) return;
            const catStr = Array.isArray(rawCat) ? rawCat.join(' ') : String(rawCat).trim();
            if (!catStr) return;
            const xCoord = node.getAttribute('x') || '0';
            const isRotated = (node.getAttribute('transform') || '').includes('rotate');
            while (node.firstChild) node.removeChild(node.firstChild);

            // Partir en 2 líneas etiquetas largas horizontales para evitar cualquier solapamiento
            let lines = [catStr];
            if (!isRotated && catStr.length > 14 && catStr.includes(' ')) {
              const parenIdx = catStr.indexOf(' (');
              if (parenIdx > 0) {
                lines = [catStr.slice(0, parenIdx).trim(), catStr.slice(parenIdx + 1).trim()];
              } else {
                const words = catStr.split(/\s+/);
                const mid = Math.ceil(words.length / 2);
                lines = [words.slice(0, mid).join(' '), words.slice(mid).join(' ')];
              }
            }
            lines.forEach((lineText, lineIdx) => {
              const ts = document.createElementNS('http://www.w3.org/2000/svg', 'tspan');
              ts.setAttribute('x', xCoord);
              if (lineIdx > 0) ts.setAttribute('dy', '1.15em');
              ts.textContent = lineText;
              node.appendChild(ts);
            });
          });
        }
      }
    }

    // 1. Limpiar filtros rasterizados que emborronan los dígitos en PDF
    svg.querySelectorAll('[filter]').forEach(el => el.removeAttribute('filter'));
    svg.querySelectorAll('[style*="filter"]').forEach(el => {
      if (el.style && el.style.filter) el.style.filter = 'none';
    });

    // 2. Asegurar nitidez y contraste en etiquetas de ejes
    svg.querySelectorAll(
      '.apexcharts-xaxis-label, .apexcharts-yaxis-label, .apexcharts-xaxis-title-text, .apexcharts-yaxis-title-text'
    ).forEach(axisText => {
      axisText.style.fontFamily = DASHBOARD_EXPORT_FONT_STACK;
      axisText.style.fontWeight = '600';
      axisText.setAttribute('fill', '#0F172A');
      axisText.removeAttribute('stroke');
      axisText.querySelectorAll('tspan').forEach(ts => {
        ts.setAttribute('fill', '#0F172A');
        ts.style.fill = '#0F172A';
        ts.removeAttribute('stroke');
      });
    });

    // 3. Mejorar legibilidad de etiquetas numéricas (DataLabels) SIN recuadro de fondo:
    //    letras blancas nítidas sobre barras/sectores de color y oscuras solo sobre fondo blanco.
    const labelNodes = [];
    const apexChartType = apexInst?.w?.config?.chart?.type || '';
    const isLineOrAreaOnWhite = ['area', 'line', 'scatter', 'boxPlot'].includes(apexChartType);

    svg.querySelectorAll('.apexcharts-datalabels rect.apexcharts-datalabel-box, .export-svg-label-pill').forEach(r => r.remove());

    svg.querySelectorAll('.apexcharts-datalabels text, .apexcharts-datalabel text').forEach(text => {
      if (text.style.visibility === 'hidden' || text.style.display === 'none') return;
      const content = (text.textContent || '').trim();
      if (!content) return;

      const currentSize = parseFloat(text.getAttribute('font-size') || text.style.fontSize || '11') || 11;
      const targetSize = currentSize < 11.5 ? 12 : Math.max(currentSize, 12.5);
      text.setAttribute('font-size', String(targetSize));
      text.style.fontSize = `${targetSize}px`;
      text.style.fontFamily = DASHBOARD_EXPORT_FONT_STACK;
      text.style.fontWeight = '700';
      text.setAttribute('font-weight', '700');
      text.removeAttribute('stroke');
      text.removeAttribute('stroke-width');
      text.style.stroke = 'none';

      const tspans = Array.from(text.querySelectorAll('tspan'));
      tspans.forEach((ts, idx) => {
        ts.setAttribute('font-size', String(targetSize));
        ts.style.fontSize = `${targetSize}px`;
        ts.style.fontWeight = '700';
        ts.removeAttribute('stroke');
        ts.removeAttribute('stroke-width');
        ts.style.stroke = 'none';
        if (idx > 0) {
          const dyRaw = ts.getAttribute('dy') || '';
          if (dyRaw && !dyRaw.endsWith('em') && !dyRaw.endsWith('%')) {
            const dyPx = parseFloat(dyRaw);
            if (Number.isFinite(dyPx) && dyPx > 0 && dyPx < targetSize * 1.16) {
              ts.setAttribute('dy', (targetSize * 1.18).toFixed(1));
            }
          }
        }
      });

      const rawFill = (
        text.getAttribute('fill') ||
        text.style.fill ||
        tspans[0]?.getAttribute('fill') ||
        ''
      ).trim().toLowerCase();
      const wasWhiteLabel = rawFill === '#ffffff' || rawFill === '#fff' ||
        rawFill === 'white' || rawFill.replace(/\s+/g, '') === 'rgb(255,255,255)';
      const useWhiteOverColor = wasWhiteLabel && !isLineOrAreaOnWhite;

      const finalColor = useWhiteOverColor ? '#FFFFFF' : '#0F172A';
      text.setAttribute('fill', finalColor);
      text.style.fill = finalColor;
      text.style.filter = useWhiteOverColor
        ? 'drop-shadow(0px 1px 1.8px rgba(15, 23, 42, 0.55))'
        : 'none';
      tspans.forEach(ts => {
        ts.setAttribute('fill', finalColor);
        ts.style.fill = finalColor;
      });

      labelNodes.push(text);
    });

    // 3b. Resolver colisiones verticales entre etiquetas cercanas en un mismo eje X (ej. curvas con valores próximos)
    if (labelNodes.length > 1) {
      const svgScreenRect = svg.getBoundingClientRect();
      const sy = svgScreenRect.height > 0 ? (origAttrH / svgScreenRect.height) : 1;
      const appendTranslateY = (el, dySvg) => {
        const prev = (el.getAttribute('transform') || '').trim();
        el.setAttribute('transform', prev ? `${prev} translate(0, ${dySvg.toFixed(2)})` : `translate(0, ${dySvg.toFixed(2)})`);
      };
      for (let aIdx = 0; aIdx < labelNodes.length; aIdx++) {
        for (let bIdx = aIdx + 1; bIdx < labelNodes.length; bIdx++) {
          const rA = labelNodes[aIdx].getBoundingClientRect();
          const rB = labelNodes[bIdx].getBoundingClientRect();
          const overlapX = Math.min(rA.right, rB.right) - Math.max(rA.left, rB.left);
          const overlapY = Math.min(rA.bottom, rB.bottom) - Math.max(rA.top, rB.top);
          if (overlapX > 2 && overlapY > -3) {
            const upper = (rA.top + rA.bottom) <= (rB.top + rB.bottom) ? labelNodes[aIdx] : labelNodes[bIdx];
            const shiftSvg = -((overlapY + 5) * sy);
            appendTranslateY(upper, shiftSvg);
          }
        }
      }
    }

    // 3c. Evitar que la leyenda HTML flotante de ApexCharts se superponga con el eje X
    const apexCanvasWrap = svg.closest('.apexcharts-canvas');
    if (apexCanvasWrap) {
      apexCanvasWrap.style.setProperty('width', '100%', 'important');
      apexCanvasWrap.style.setProperty('height', '100%', 'important');
      apexCanvasWrap.style.setProperty('max-width', '100%', 'important');
      const htmlLegend = apexCanvasWrap.querySelector('.apexcharts-legend');
      if (htmlLegend && htmlLegend.children.length > 0 && window.getComputedStyle(htmlLegend).display !== 'none') {
        apexCanvasWrap.style.setProperty('display', 'flex', 'important');
        apexCanvasWrap.style.setProperty('flex-direction', 'column', 'important');
        svg.style.setProperty('flex', '1 1 auto', 'important');
        svg.style.setProperty('min-height', '0', 'important');
        htmlLegend.style.setProperty('position', 'static', 'important');
        htmlLegend.style.setProperty('inset', 'auto', 'important');
        htmlLegend.style.setProperty('flex', '0 0 auto', 'important');
        htmlLegend.style.setProperty('justify-content', 'center', 'important');
        htmlLegend.style.setProperty('padding', '6px 4px 2px 4px', 'important');
      }
    }

    // 4. Recalcular viewBox ajustado exactamente al contenido real visible (cero márgenes muertos y cero recortes)
    try {
      const svgRect = svg.getBoundingClientRect();
      if (svgRect.width > 0 && svgRect.height > 0) {
        const scaleX = origAttrW / svgRect.width;
        const scaleY = origAttrH / svgRect.height;
        let minX = Infinity;
        let minY = Infinity;
        let maxX = -Infinity;
        let maxY = -Infinity;

        svg.querySelectorAll(
          'text, .apexcharts-graphical, .apexcharts-datalabels, .apexcharts-xaxis, .apexcharts-yaxis'
        ).forEach(node => {
          if (node.style?.display === 'none' || node.style?.visibility === 'hidden') return;
          if (node.getAttribute('opacity') === '0' || node.getAttribute('stroke') === 'transparent') return;
          if (node.tagName === 'text' && !(node.textContent || '').trim()) return;
          const r = node.getBoundingClientRect();
          if (!r || (r.width === 0 && r.height === 0)) return;
          const x1 = (r.left - svgRect.left) * scaleX;
          const x2 = (r.right - svgRect.left) * scaleX;
          const y1 = (r.top - svgRect.top) * scaleY;
          const y2 = (r.bottom - svgRect.top) * scaleY;
          if (Math.abs(x1) > 4000 || Math.abs(x2) > 4000 || Math.abs(y1) > 4000 || Math.abs(y2) > 4000) return;
          if (x1 < minX) minX = x1;
          if (x2 > maxX) maxX = x2;
          if (y1 < minY) minY = y1;
          if (y2 > maxY) maxY = y2;
        });

        if (!Number.isFinite(minX) || !Number.isFinite(minY)) {
          minX = 0;
          minY = 0;
          maxX = origAttrW;
          maxY = origAttrH;
        }

        const padX = 14;
        const padY = 12;
        const vbX = Math.floor(minX - padX);
        const vbY = Math.floor(minY - padY);
        const vbW = Math.max(100, Math.ceil((maxX - minX) + padX * 2));
        const vbH = Math.max(80, Math.ceil((maxY - minY) + padY * 2));

        const targetSvgW = Math.max(320, Math.round(containerEl?.clientWidth || origAttrW));
        const targetSvgH = Math.max(200, Math.round(svg.clientHeight || containerEl?.clientHeight || origAttrH));

        svg.setAttribute('viewBox', `${vbX} ${vbY} ${vbW} ${vbH}`);
        svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
        svg.setAttribute('width', String(targetSvgW));
        svg.setAttribute('height', String(targetSvgH));
        svg.style.setProperty('width', '100%', 'important');
        svg.style.setProperty('height', '100%', 'important');
        svg.style.setProperty('max-width', '100%', 'important');
        svg.style.setProperty('max-height', '100%', 'important');
        svg.style.setProperty('overflow', 'visible', 'important');
      }
    } catch (errVb) {
      console.warn('Advertencia calculando viewBox de exportación:', errVb);
    }
  });
}

function buildExportHtmlStage(tab, partNumber, layout = null) {
  const targetEl = document.getElementById('tab-' + tab.id);
  if (!targetEl) return null;

  const exportSourceWidth = DASHBOARD_EXPORT_CONTENT_WIDTH_PX;
  const availableHeight = DASHBOARD_EXPORT_CONTENT_HEIGHT_PX;

  const stage = document.createElement('div');
  stage.className = 'dashboard-export-html-stage';
  stage.setAttribute('aria-hidden', 'true');
  stage.style.cssText = `position:fixed;left:-100000px;top:0;width:${exportSourceWidth}px;min-height:10px;padding:0;margin:0;background:#FFFFFF;z-index:1;overflow:visible;pointer-events:none;`;

  let clone;
  if (layout?.visualRows) {
    clone = document.createElement('div');
    clone.className = `${targetEl.className || ''} dashboard-export-html-source active`.trim();
    if (layout.includeKpis) {
      Array.from(targetEl.children).forEach(child => {
        if (child && child.nodeType === 1 && child.classList.contains('kpi-row')) {
          clone.appendChild(child.cloneNode(true));
        }
      });
    }
    const sourceVisualCards = Array.from(targetEl.querySelectorAll('.card-visual'));
    layout.visualRows.forEach(cardIndexes => {
      const exportRow = document.createElement('div');
      const isSingleCol = cardIndexes.length === 1;
      exportRow.className = isSingleCol
        ? 'grid grid-row dashboard-export-chart-row'
        : 'grid grid-row grid-2-cols-equal dashboard-export-chart-row';
      exportRow.style.setProperty('display', 'grid', 'important');
      exportRow.style.setProperty(
        'grid-template-columns',
        isSingleCol ? 'minmax(0, 1fr)' : 'repeat(2, minmax(0, 1fr))',
        'important'
      );
      exportRow.style.setProperty('gap', '16px', 'important');
      exportRow.style.setProperty('width', '100%', 'important');
      exportRow.style.setProperty('margin', '0', 'important');

      cardIndexes.forEach(cardIndex => {
        const srcCard = sourceVisualCards[cardIndex];
        if (!srcCard) return;
        const card = srcCard.cloneNode(true);
        card.style.setProperty('width', '100%', 'important');
        card.style.setProperty('min-width', '0', 'important');
        card.style.setProperty('margin', '0', 'important');
        card.style.setProperty('padding', '14px 16px', 'important');
        card.style.setProperty('grid-column', isSingleCol ? '1 / -1' : 'auto', 'important');
        exportRow.appendChild(card);
      });
      clone.appendChild(exportRow);
    });
  } else {
    clone = targetEl.cloneNode(true);
    clone.classList.add('dashboard-export-html-source');
    clone.classList.add('active');
    const cfg = getTabPartsConfig(tab.id);
    const rows = Array.from(clone.children).filter(c =>
      c && c.nodeType === 1 && c.tagName === 'DIV' &&
      (c.classList.contains('kpi-row') || c.classList.contains('grid-row') || c.classList.contains('grid'))
    );
    const splitIdx = cfg.splitIdx || 3;
    rows.forEach((row, index) => {
      if ((partNumber === 1 && index >= splitIdx) || (partNumber === 2 && index < splitIdx)) row.remove();
    });
  }

  clone.id = 'dashboard-export-tab-' + tab.id;
  clone.style.setProperty('display', 'flex', 'important');
  clone.style.flexDirection = 'column';
  clone.style.gap = '12px';
  clone.style.width = `${exportSourceWidth}px`;
  clone.style.maxWidth = `${exportSourceWidth}px`;
  clone.style.height = 'auto';
  clone.style.minHeight = '0';
  clone.style.maxHeight = 'none';
  clone.style.padding = '0';
  clone.style.margin = '0';
  clone.style.background = '#FFFFFF';

  clone.querySelectorAll('.chart-skeleton-placeholder').forEach(el => el.remove());
  clone.querySelectorAll('button, input, select, textarea').forEach(el => {
    el.style.pointerEvents = 'none';
  });

  // Configurar tarjetas KPI visibles para aprovechar el 100% del ancho de lámina
  clone.querySelectorAll('.kpi-row').forEach(row => {
    Array.from(row.children).forEach(child => {
      if (child.hidden || child.style.display === 'none') child.remove();
    });
    const visibleKpis = Array.from(row.children).filter(child => child.classList.contains('card-kpi'));
    if (!visibleKpis.length) {
      row.remove();
      return;
    }
    const columns = visibleKpis.length;
    row.style.setProperty('display', 'grid', 'important');
    row.style.setProperty('--export-kpi-columns', String(columns));
    row.style.setProperty('grid-template-columns', `repeat(${columns}, minmax(0, 1fr))`, 'important');
    row.style.setProperty('width', '100%', 'important');
    row.style.setProperty('margin', '0', 'important');
    row.style.setProperty('gap', '12px', 'important');
  });

  clone.querySelectorAll('.card-kpi .kpi-title, .card-kpi .kpi-value, .card-kpi .kpi-caption').forEach(el => {
    el.style.setProperty('visibility', 'visible', 'important');
    el.style.setProperty('opacity', '1', 'important');
  });

  let exportChartHeight = layout?.chartHeight || 420;
  clone.style.setProperty('--export-chart-height', `${exportChartHeight}px`);
  clone.querySelectorAll('.card-visual .chart-container').forEach(container => {
    container.style.setProperty('width', '100%', 'important');
    container.style.setProperty('height', `${exportChartHeight}px`, 'important');
    container.style.setProperty('min-height', `${exportChartHeight}px`, 'important');
  });

  // Insertar en el DOM real para medir geometría exacta a 277 mm (1047 px) de ancho
  stage.appendChild(clone);
  document.body.appendChild(stage);

  // Ajustar la altura del área del gráfico para encajar al 100% en A4 horizontal SIN encoger con transform:scale
  const rowCount = Math.max(1, layout?.visualRows?.length || 1);
  if (clone.scrollHeight > availableHeight - 2) {
    const excessPx = clone.scrollHeight - (availableHeight - 4);
    const adjustedHeight = Math.max(260, Math.floor(exportChartHeight - (excessPx / rowCount)));
    exportChartHeight = adjustedHeight;
    clone.style.setProperty('--export-chart-height', `${exportChartHeight}px`);
    clone.querySelectorAll('.card-visual .chart-container').forEach(container => {
      container.style.setProperty('height', `${exportChartHeight}px`, 'important');
      container.style.setProperty('min-height', `${exportChartHeight}px`, 'important');
    });
  } else if (clone.scrollHeight < availableHeight - 24 && rowCount === 1) {
    // Aprovechar todo el alto disponible de la diapositiva para maximizar tamaño de gráficas y números
    const sparePx = (availableHeight - 8) - clone.scrollHeight;
    const expandedHeight = Math.min(520, exportChartHeight + sparePx);
    exportChartHeight = expandedHeight;
    clone.style.setProperty('--export-chart-height', `${exportChartHeight}px`);
    clone.querySelectorAll('.card-visual .chart-container').forEach(container => {
      container.style.setProperty('height', `${exportChartHeight}px`, 'important');
      container.style.setProperty('min-height', `${exportChartHeight}px`, 'important');
    });
  }

  // Renderizar cada <canvas> Chart.js en Ultra-HD (4x DPI) al tamaño exacto final de su contenedor
  clone.querySelectorAll('canvas').forEach(clonedCanvas => {
    const canvasId = clonedCanvas.id;
    const sourceCanvas = canvasId
      ? targetEl.querySelector(`#${CSS.escape(canvasId)}`)
      : null;
    if (!sourceCanvas) return;

    const container = clonedCanvas.closest('.chart-container') || clonedCanvas.parentElement;
    const targetW = Math.max(360, container?.clientWidth || 500);
    const targetH = Math.max(260, container?.clientHeight || exportChartHeight);
    const hdDataUrl = renderExportChartJsDataUrl(sourceCanvas, targetW, targetH);

    const image = document.createElement('img');
    image.src = hdDataUrl;
    image.width = targetW;
    image.height = targetH;
    image.alt = '';
    image.className = 'dashboard-export-hd-chart-img';
    image.style.cssText = 'display:block;width:100%;height:100%;object-fit:contain;';
    clonedCanvas.replaceWith(image);
  });

  // Optimizar gráficos vectoriales SVG de ApexCharts con cápsulas de alto contraste y viewBox sin recortes
  enhanceApexSvgForExport(clone, targetEl);

  // Verificación final de altura sin deformar ni encoger horizontalmente la lámina
  if (clone.scrollHeight > availableHeight + 2) {
    const finalScale = Math.max(0.92, availableHeight / clone.scrollHeight);
    clone.style.setProperty('zoom', String(finalScale));
  }

  return { stage, root: clone };
}

async function renderSectionPartCanvas(h2c, tab, partNumber, scale = 2.0, layout = null) {
  const htmlStage = buildExportHtmlStage(tab, partNumber, layout);
  if (!htmlStage) return null;
  const targetEl = htmlStage.stage;

  try {
    return await h2c(targetEl, {
      scale: scale,
      useCORS: true,
      backgroundColor: '#FFFFFF',
      logging: false,
      imageTimeout: 0,
      ignoreElements: (el) => {
        if (!el) return false;
        if (el.parentElement === document.body) {
          const tag = el.tagName;
          return el !== targetEl && tag !== 'STYLE' && tag !== 'LINK';
        }
        return false;
      },
      onclone: (clonedDoc) => {
        const clonedTarget = clonedDoc.getElementById('dashboard-export-tab-' + tab.id);
        if (!clonedTarget) return;
        fixSvgFillsForHtml2Canvas(clonedDoc, tab.id, clonedTarget);
        clonedTarget.style.setProperty('display', 'flex', 'important');
        clonedTarget.style.flexDirection = 'column';
        clonedTarget.style.background = '#FFFFFF';
        clonedTarget.style.padding = '0';
        clonedTarget.style.margin = '0';
        clonedTarget.style.height = 'auto';
        clonedTarget.style.minHeight = '0';
        clonedTarget.style.maxHeight = 'none';
      }
    });
  } finally {
    htmlStage.stage.remove();
  }
}

// Wrapper retrocompatible
async function renderSectionCanvas(h2c, tab, scale = 2.0) {
  return await renderSectionPartCanvas(h2c, tab, 1, scale);
}

// Prepara cada pestaña a lo sumo UNA sola vez por exportación y omite esperas artificiales:
// si la pestaña activa ya está renderizada en pantalla, su costo es 0 ms.
async function ensureTabReadyForExport(tabId, preparedTabs) {
  if (preparedTabs && preparedTabs.has(tabId)) return;

  const targetView = document.getElementById('tab-' + tabId);
  const alreadyVisibleAndRendered = (
    activeTabId === tabId &&
    targetView &&
    targetView.offsetWidth > 0 &&
    !targetView.querySelector('.chart-skeleton-placeholder') &&
    Boolean(targetView.querySelector('canvas, svg.apexcharts-svg, [data-empty-chart]'))
  );

  if (alreadyVisibleAndRendered) {
    try {
      if (typeof updateActiveTabKPIs === 'function') updateActiveTabKPIs(tabId);
    } catch (err) {}
    if (preparedTabs) preparedTabs.add(tabId);
    return;
  }

  if (activeTabId !== tabId && typeof switchTab === 'function') {
    switchTab(tabId, document.querySelector(`.nav-item[onclick*="${tabId}"]`));
  }
  try {
    if (typeof updateActiveTabKPIs === 'function') updateActiveTabKPIs(tabId);
    if (typeof renderTabCharts === 'function') renderTabCharts(tabId);
  } catch (err) {
    console.warn('Advertencia al preparar pestaña para exportación:', err);
  }
  await new Promise(r => requestAnimationFrame(r));
  if (preparedTabs) preparedTabs.add(tabId);
}

async function prepareTabForExport(tabId, isNewTab) {
  const dummySet = isNewTab ? null : new Set([tabId]);
  await ensureTabReadyForExport(tabId, dummySet);
}

// 1. Exportación a Imagen PNG Ultra-HD (Láminas de Presentación)
async function exportImage(scope, setProgress) {
  const h2c = window.html2canvas || (typeof html2canvas !== 'undefined' ? html2canvas : null);
  if (!h2c) {
    throw new Error('La librería html2canvas no está disponible.');
  }

  const tabs = scope === 'all'
    ? DASHBOARD_TABS
    : [DASHBOARD_TABS.find(t => t.id === activeTabId) || DASHBOARD_TABS[0]];
  const originalTab = activeTabId;
  const preparedTabs = new Set();

  try {
    let slideCounter = 0;
    for (let tIdx = 0; tIdx < tabs.length; tIdx++) {
      const tab = tabs[tIdx];
      await ensureTabReadyForExport(tab.id, preparedTabs);
      const tabItems = getTabExportItems(tab);

      for (let sIdx = 0; sIdx < tabItems.length; sIdx++) {
        const item = tabItems[sIdx];
        slideCounter++;
        const approxPct = Math.min(95, Math.round(((tIdx + (sIdx + 0.5) / tabItems.length) / tabs.length) * 95));
        setProgress(`Renderizando lámina HD: ${item.title}...`, approxPct);

        const canvas = await renderSectionPartCanvas(h2c, tab, item.partNumber, 2.0, item.layout);
        if (!canvas) continue;

        const link = document.createElement('a');
        const safeTitle = tab.id.replace(/[^a-z0-9]/gi, '_');
        link.download = `CardioUNEMI_${safeTitle}_${item.suffix}_${new Date().toISOString().slice(0, 10)}.png`;
        link.href = canvas.toDataURL('image/png');
        link.click();
        if (slideCounter < tabItems.length || tIdx < tabs.length - 1) {
          await new Promise(r => requestAnimationFrame(r));
        }
      }
    }
    setProgress('¡Imágenes PNG en alta resolución descargadas con éxito!', 100);
  } finally {
    if (activeTabId !== originalTab && typeof switchTab === 'function') {
      switchTab(originalTab, document.querySelector(`.nav-item[onclick*="${originalTab}"]`));
    }
  }
}

// 2. Exportación a Documento PDF Ejecutivo Vectorial de Alta Definición
function escapeExportHtml(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function getExportCsrfToken() {
  if (typeof getCsrfToken === 'function') return getCsrfToken();
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : '';
}

let _cachedExportCss = null;

function collectDashboardExportStyles() {
  if (_cachedExportCss !== null) return _cachedExportCss;
  const chunks = [];
  document.querySelectorAll('style').forEach(style => {
    if (style.textContent) chunks.push(style.textContent);
  });
  document.querySelectorAll('link[rel="stylesheet"]').forEach(link => {
    try {
      const sheet = link.sheet;
      if (sheet && sheet.cssRules) {
        chunks.push(Array.from(sheet.cssRules).map(rule => rule.cssText).join('\n'));
      }
    } catch (err) {}
  });
  _cachedExportCss = chunks.join('\n');
  return _cachedExportCss;
}

function serializeExportRoot(root, mutateInPlace = false) {
  const target = mutateInPlace ? root : root.cloneNode(true);
  target.querySelectorAll('.chart-skeleton-placeholder').forEach(el => el.remove());
  target.querySelectorAll('button, input, select, textarea').forEach(el => el.remove());
  target.querySelectorAll('canvas').forEach(canvas => {
    const image = document.createElement('img');
    image.src = canvas.toDataURL('image/png');
    image.width = canvas.width;
    image.height = canvas.height;
    image.style.cssText = canvas.getAttribute('style') || '';
    image.className = canvas.className;
    canvas.replaceWith(image);
  });
  return target.outerHTML;
}

function buildDashboardHtmlReport(pages, scope) {
  const meta = getExportCohortMetadata();
  const pageCount = pages.length;
  const css = collectDashboardExportStyles();
  const pageHtml = pages.map((page, index) => `
    <section class="cardiounemi-export-page">
      <header class="cardiounemi-export-header">
        <strong>CARDIOUNEMI • VIGILANCIA EPIDEMIOLÓGICA CARDIOVASCULAR</strong>
        <span>${escapeExportHtml(meta.headerSummary)}</span>
      </header>
      <h1 class="cardiounemi-export-slide-title">${escapeExportHtml(page.title)}</h1>
      <main class="cardiounemi-export-content">${page.html}</main>
      <footer class="cardiounemi-export-footer">
        <span>Universidad Estatal de Milagro (UNEMI) • Departamento de Cardiología</span>
        <span>Página ${index + 1} de ${pageCount}</span>
      </footer>
    </section>`).join('\n');

  return `<!doctype html><html lang="es"><head><meta charset="utf-8"><title>CardioUNEMI Dashboard</title>
    <style>
      ${css}
      @page { size: A4 landscape; margin: 0; }
      * {
        box-sizing: border-box;
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
      }
      html, body {
        margin: 0 !important;
        padding: 0 !important;
        background: #FFFFFF !important;
        color: #0F172A !important;
        font-family: ${DASHBOARD_EXPORT_FONT_STACK} !important;
        -webkit-font-smoothing: antialiased;
      }
      body {
        display: block !important;
        width: 297mm !important;
        min-width: 297mm !important;
      }
      .cardiounemi-export-page {
        display: flex !important;
        flex-direction: column !important;
        position: relative !important;
        width: 297mm !important;
        height: 210mm !important;
        min-height: 210mm !important;
        max-height: 210mm !important;
        padding: 7mm 10mm !important;
        margin: 0 !important;
        overflow: hidden !important;
        background: #FFFFFF !important;
        break-after: page !important;
        page-break-after: always !important;
      }
      .cardiounemi-export-page:last-child {
        break-after: auto !important;
        page-break-after: auto !important;
      }
      .cardiounemi-export-header {
        height: 13mm !important;
        min-height: 13mm !important;
        padding: 0 5mm !important;
        margin: 0 0 2.5mm 0 !important;
        border-radius: 6px !important;
        background: #1B2A41 !important;
        color: #FFFFFF !important;
        display: flex !important;
        justify-content: space-between !important;
        align-items: center !important;
        gap: 12px !important;
        font: 700 10.5pt ${DASHBOARD_EXPORT_FONT_STACK} !important;
      }
      .cardiounemi-export-header span {
        font-size: 8.2pt !important;
        font-weight: 500 !important;
        color: #E2E8F0 !important;
        white-space: nowrap !important;
      }
      .cardiounemi-export-slide-title {
        height: 7.5mm !important;
        line-height: 7.5mm !important;
        margin: 0 0 2mm 0 !important;
        padding: 0 1mm !important;
        color: #1B2A41 !important;
        font: 800 12.5pt ${DASHBOARD_EXPORT_FONT_STACK} !important;
        letter-spacing: -0.01em !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
      }
      .cardiounemi-export-content {
        display: block !important;
        flex: 1 1 auto !important;
        width: 277mm !important;
        max-width: 100% !important;
        height: 164mm !important;
        max-height: 164mm !important;
        margin: 0 auto !important;
        overflow: hidden !important;
      }
      .cardiounemi-export-content .dashboard-export-html-source {
        display: flex !important;
        flex-direction: column !important;
        gap: 12px !important;
        width: ${DASHBOARD_EXPORT_CONTENT_WIDTH_PX}px !important;
        max-width: 100% !important;
        height: auto !important;
        min-height: 0 !important;
        padding: 0 !important;
        margin: 0 auto !important;
      }
      .cardiounemi-export-content .dashboard-export-html-source .kpi-row {
        display: grid !important;
        width: 100% !important;
        grid-template-columns: repeat(var(--export-kpi-columns, 5), minmax(0, 1fr)) !important;
        gap: 12px !important;
        margin: 0 !important;
      }
      .cardiounemi-export-content .dashboard-export-html-source .card-kpi {
        min-width: 0 !important;
        padding: 10px 14px !important;
        border: 1.5px solid #CBD5E1 !important;
        border-radius: 10px !important;
        background: #FFFFFF !important;
        box-shadow: none !important;
      }
      .cardiounemi-export-content .dashboard-export-html-source .card-kpi .kpi-title {
        font-size: 9pt !important;
        font-weight: 700 !important;
        color: #334155 !important;
        line-height: 1.25 !important;
      }
      .cardiounemi-export-content .dashboard-export-html-source .card-kpi .kpi-value {
        font-size: 18.5pt !important;
        font-weight: 800 !important;
        line-height: 1.15 !important;
        margin-top: 3px !important;
      }
      .cardiounemi-export-content .dashboard-export-html-source .card-kpi .kpi-caption {
        font-size: 8.2pt !important;
        font-weight: 600 !important;
        color: #475569 !important;
        margin-top: 4px !important;
        line-height: 1.25 !important;
      }
      .cardiounemi-export-content .dashboard-export-html-source .card-visual {
        width: 100% !important;
        min-width: 0 !important;
        padding: 14px 16px !important;
        border: 1.5px solid #CBD5E1 !important;
        border-radius: 12px !important;
        background: #FFFFFF !important;
        box-shadow: none !important;
      }
      .cardiounemi-export-content .dashboard-export-html-source .visual-header {
        margin-bottom: 8px !important;
        padding-bottom: 8px !important;
        border-bottom: 1px solid #E2E8F0 !important;
      }
      .cardiounemi-export-content .dashboard-export-html-source .visual-title h3 {
        font-size: 10.8pt !important;
        font-weight: 700 !important;
        color: #0F172A !important;
        margin: 0 !important;
        line-height: 1.25 !important;
      }
      .cardiounemi-export-content .dashboard-export-html-source .card-visual .chart-container {
        width: 100% !important;
        height: var(--export-chart-height, 420px) !important;
        min-height: var(--export-chart-height, 420px) !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        overflow: visible !important;
      }
      .cardiounemi-export-content .dashboard-export-html-source .apexcharts-canvas {
        width: 100% !important;
        height: 100% !important;
        max-width: 100% !important;
        overflow: visible !important;
      }
      .cardiounemi-export-content .dashboard-export-html-source .apexcharts-svg {
        width: 100% !important;
        max-width: 100% !important;
        overflow: visible !important;
      }
      .cardiounemi-export-content .card,
      .cardiounemi-export-content .grid,
      .cardiounemi-export-content .grid-row {
        break-inside: avoid !important;
      }
      .cardiounemi-export-footer {
        height: 5mm !important;
        min-height: 5mm !important;
        margin-top: 2mm !important;
        padding: 0 1mm !important;
        border-top: 1px solid #E2E8F0 !important;
        display: flex !important;
        justify-content: space-between !important;
        align-items: center !important;
        color: #64748B !important;
        font: 600 8pt ${DASHBOARD_EXPORT_FONT_STACK} !important;
      }
    </style></head><body data-export-scope="${escapeExportHtml(scope)}">${pageHtml}</body></html>`;
}

async function requestDashboardHtmlPdf(reportHtml) {
  const response = await fetch('/dashboard/export/html-pdf/', {
    method: 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getExportCsrfToken() },
    body: JSON.stringify({ html: reportHtml })
  });
  if (!response.ok) {
    let message = 'No se pudo convertir el HTML a PDF.';
    try { const data = await response.json(); if (data.error) message = data.error; } catch (err) {}
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return await response.blob();
}

function downloadExportBlob(blob, fileName) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url; link.download = fileName;
  document.body.appendChild(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function exportPdf(scope, setProgress) {
  const tabs = scope === 'all'
    ? DASHBOARD_TABS
    : [DASHBOARD_TABS.find(t => t.id === activeTabId) || DASHBOARD_TABS[0]];
  const originalTab = activeTabId;
  const preparedTabs = new Set();
  const pages = [];

  try {
    for (let tIdx = 0; tIdx < tabs.length; tIdx++) {
      const tab = tabs[tIdx];
      setProgress(`Preparando sección: ${tab.title} (${tIdx + 1}/${tabs.length})...`, Math.round(10 + ((tIdx + 0.3) / tabs.length) * 65));
      await ensureTabReadyForExport(tab.id, preparedTabs);
      const tabItems = getTabExportItems(tab);

      for (let sIdx = 0; sIdx < tabItems.length; sIdx++) {
        const item = tabItems[sIdx];
        const htmlStage = buildExportHtmlStage(tab, item.partNumber, item.layout);
        if (!htmlStage) continue;
        try {
          pages.push({ title: item.title, html: serializeExportRoot(htmlStage.root, true) });
        } finally {
          htmlStage.stage.remove();
        }
      }
      if (tabs.length > 1) {
        await new Promise(r => requestAnimationFrame(r));
      }
    }
    if (!pages.length) throw new Error('No se encontraron secciones con datos para exportar.');

    setProgress('Generando PDF vectorial de alta definición...', 85);
    try {
      const pdfBlob = await requestDashboardHtmlPdf(buildDashboardHtmlReport(pages, scope));
      downloadExportBlob(pdfBlob, scope === 'all'
        ? `CardioUNEMI_Reporte_Ejecutivo_Integral_${new Date().toISOString().slice(0, 10)}.pdf`
        : `CardioUNEMI_${originalTab}_${new Date().toISOString().slice(0, 10)}.pdf`);
      setProgress('¡PDF de presentación generado exitosamente!', 100);
    } catch (pdfErr) {
      if (pdfErr && pdfErr.status === 503) {
        console.warn('Chromium no disponible en servidor, usando motor PDF HD de respaldo:', pdfErr.message);
        await exportPdfRasterFallback(scope, setProgress, preparedTabs);
        return;
      }
      throw pdfErr;
    }
  } finally {
    if (activeTabId !== originalTab && typeof switchTab === 'function') {
      switchTab(originalTab, document.querySelector(`.nav-item[onclick*="${originalTab}"]`));
    }
  }
}

async function exportPdfRasterFallback(scope, setProgress, existingPreparedTabs = null) {
  const { jsPDF } = window.jspdf || window;
  if (!jsPDF) {
    throw new Error('La librería jsPDF no está disponible.');
  }
  const h2c = window.html2canvas || (typeof html2canvas !== 'undefined' ? html2canvas : null);
  if (!h2c) {
    throw new Error('La librería html2canvas no está disponible.');
  }

  const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4', compress: true });
  const tabs = scope === 'all'
    ? DASHBOARD_TABS
    : [DASHBOARD_TABS.find(t => t.id === activeTabId) || DASHBOARD_TABS[0]];
  const originalTab = activeTabId;
  const preparedTabs = existingPreparedTabs || new Set();

  const pageWidth = 297;
  const pageHeight = 210;
  const marginX = 10;
  const contentWidth = pageWidth - (marginX * 2);
  const maxImgHeight = 166;
  const meta = getExportCohortMetadata();

  try {
    const allSlides = [];
    for (let tIdx = 0; tIdx < tabs.length; tIdx++) {
      await ensureTabReadyForExport(tabs[tIdx].id, preparedTabs);
      allSlides.push(...getTabExportItems(tabs[tIdx]));
    }
    const total = allSlides.length;

    for (let i = 0; i < total; i++) {
      const item = allSlides[i];
      const tab = item.tab;
      setProgress(`Renderizando lámina HD: ${item.title} (${i + 1}/${total})...`, Math.round(((i + 0.2) / total) * 92));

      await ensureTabReadyForExport(tab.id, preparedTabs);
      const canvas = await renderSectionPartCanvas(h2c, tab, item.partNumber, 2.0, item.layout);
      if (!canvas) continue;

      if (i > 0) doc.addPage();

      const imgData = canvas.toDataURL('image/png');

      doc.setFillColor(27, 42, 65);
      doc.roundedRect(marginX, 7, contentWidth, 13, 1.5, 1.5, 'F');

      doc.setTextColor(255, 255, 255);
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(10.2);
      doc.text('CARDIOUNEMI • VIGILANCIA EPIDEMIOLÓGICA CARDIOVASCULAR', marginX + 4, 15);

      doc.setFont('helvetica', 'normal');
      doc.setFontSize(8);
      doc.text(meta.headerSummary, pageWidth - marginX - 4, 15, { align: 'right' });

      doc.setTextColor(27, 42, 65);
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(12);
      doc.text(item.title, marginX, 26.5);

      const imgAspect = canvas.height / canvas.width;
      let renderW = contentWidth;
      let renderH = renderW * imgAspect;
      if (renderH > maxImgHeight) {
        renderH = maxImgHeight;
        renderW = renderH / imgAspect;
      }
      const renderX = marginX + (contentWidth - renderW) / 2;
      const renderY = 30;

      doc.addImage(imgData, 'PNG', renderX, renderY, renderW, renderH, undefined, 'FAST');

      doc.setTextColor(100, 116, 139);
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(8);
      doc.text('Universidad Estatal de Milagro (UNEMI) • Departamento de Cardiología', marginX, pageHeight - 5);
      doc.text(`Página ${i + 1} de ${total}`, pageWidth - marginX, pageHeight - 5, { align: 'right' });
    }

    setProgress('Compilando archivo PDF final...', 96);
    const fileName = scope === 'all'
      ? `CardioUNEMI_Reporte_Ejecutivo_Integral_${new Date().toISOString().slice(0, 10)}.pdf`
      : `CardioUNEMI_${originalTab}_${new Date().toISOString().slice(0, 10)}.pdf`;

    doc.save(fileName);
    setProgress('¡PDF generado exitosamente!', 100);
  } finally {
    if (activeTabId !== originalTab && typeof switchTab === 'function') {
      switchTab(originalTab, document.querySelector(`.nav-item[onclick*="${originalTab}"]`));
    }
  }
}

// 3. Exportación a Diapositivas PowerPoint (.pptx) 16:9 en Alta Definición (PNG sin pérdidas)
async function exportPowerPoint(scope, setProgress) {
  const pptxClass = window.PptxGenJS || (typeof PptxGenJS !== 'undefined' ? PptxGenJS : null);
  if (!pptxClass) {
    throw new Error('La librería PptxGenJS no está disponible.');
  }
  const h2c = window.html2canvas || (typeof html2canvas !== 'undefined' ? html2canvas : null);
  if (!h2c) {
    throw new Error('La librería html2canvas no está disponible.');
  }

  const pptx = new pptxClass();
  pptx.layout = 'LAYOUT_16x9';

  const tabs = scope === 'all'
    ? DASHBOARD_TABS
    : [DASHBOARD_TABS.find(t => t.id === activeTabId) || DASHBOARD_TABS[0]];
  const originalTab = activeTabId;
  const preparedTabs = new Set();
  const meta = getExportCohortMetadata();

  try {
    setProgress('Preparando secciones para PowerPoint...', 8);
    const exportItems = [];
    for (let tIdx = 0; tIdx < tabs.length; tIdx++) {
      await ensureTabReadyForExport(tabs[tIdx].id, preparedTabs);
      exportItems.push(...getTabExportItems(tabs[tIdx]));
    }
    const total = exportItems.length;

    const slidePortada = pptx.addSlide();
    slidePortada.background = { color: '1B2A41' };

    slidePortada.addText('UNIVERSIDAD ESTATAL DE MILAGRO', {
      x: 0.8, y: 1.0, w: 8.4, h: 0.4,
      fontSize: 13, color: '3AA0FF', bold: true
    });

    slidePortada.addText('CARDIOUNEMI • INFORME EPIDEMIOLÓGICO', {
      x: 0.8, y: 1.45, w: 8.4, h: 1.0,
      fontSize: 27, color: 'FFFFFF', bold: true
    });

    slidePortada.addText('Vigilancia de Salud Cardiovascular y Factores de Riesgo Clínico', {
      x: 0.8, y: 2.5, w: 8.4, h: 0.5,
      fontSize: 14, color: 'CFE9FF'
    });

    slidePortada.addShape(pptx.ShapeType.rect, {
      x: 0.8, y: 3.25, w: 8.4, h: 1.65,
      fill: { color: '142132' },
      line: { color: '3AA0FF', width: 1.5 }
    });

    slidePortada.addText([
      { text: 'Muestra Total Analizada: ', options: { bold: true, color: '3AA0FF' } },
      { text: `${meta.sampleText}\n`, options: { color: 'FFFFFF' } },
      { text: 'Institución / Cohorte: ', options: { bold: true, color: '3AA0FF' } },
      { text: `${meta.instLabel} (${meta.anoLabel})\n`, options: { color: 'FFFFFF' } },
      { text: 'Fecha de Emisión: ', options: { bold: true, color: '3AA0FF' } },
      { text: `${meta.todayStr}\n`, options: { color: 'FFFFFF' } },
      { text: 'Alcance del Reporte: ', options: { bold: true, color: '3AA0FF' } },
      {
        text: scope === 'all'
          ? `Informe Integral Completo (9 Secciones Clínicas • ${total} Diapositivas HD)`
          : `Módulo Específico: ${exportItems[0]?.tab?.title || ''} (${total} Diapositivas HD)`,
        options: { color: 'FFFFFF' }
      }
    ], {
      x: 1.05, y: 3.4, w: 7.9, h: 1.35,
      fontSize: 11
    });

    const maxW = 9.3;
    const maxH = 4.55;
    const topY = 0.72;

    for (let i = 0; i < total; i++) {
      const item = exportItems[i];
      const tab = item.tab;
      setProgress(`Generando diapositivas HD: ${item.title} (${i + 1}/${total})...`, Math.round(14 + ((i + 1) / total) * 80));

      await ensureTabReadyForExport(tab.id, preparedTabs);
      const canvas = await renderSectionPartCanvas(h2c, tab, item.partNumber, 2.0, item.layout);
      if (!canvas) continue;

      const imgData = canvas.toDataURL('image/png');

      const slide = pptx.addSlide();
      slide.background = { color: 'FFFFFF' };

      slide.addShape(pptx.ShapeType.rect, {
        x: 0, y: 0, w: 10, h: 0.62,
        fill: { color: '1B2A41' }
      });

      slide.addText(`CARDIOUNEMI • ${item.title}`, {
        x: 0.35, y: 0.11, w: 7.4, h: 0.4,
        fontSize: 11, color: 'FFFFFF', bold: true
      });

      slide.addText(`${meta.todayStr} | n = ${meta.evalCount}`, {
        x: 7.8, y: 0.13, w: 1.85, h: 0.35,
        fontSize: 8.5, color: 'CFE9FF', align: 'right'
      });

      const imgAspect = canvas.height / canvas.width;
      let w = maxW;
      let h = w * imgAspect;
      if (h > maxH) {
        h = maxH;
        w = h / imgAspect;
      }
      const x = 0.35 + (maxW - w) / 2;
      const y = topY + (maxH - h) / 2;

      slide.addImage({ data: imgData, x, y, w, h });

      slide.addText('Universidad Estatal de Milagro (UNEMI) • Departamento de Cardiología', {
        x: 0.35, y: 5.34, w: 6.5, h: 0.24,
        fontSize: 8, color: '64748B'
      });
      slide.addText(`Diapositiva ${i + 2} de ${total + 1}`, {
        x: 7.5, y: 5.34, w: 2.15, h: 0.24,
        fontSize: 8, color: '64748B', align: 'right'
      });
    }

    setProgress('Compilando presentación PowerPoint (.pptx)...', 96);
    const fileName = scope === 'all'
      ? `CardioUNEMI_Presentacion_Ejecutiva_${new Date().toISOString().slice(0, 10)}.pptx`
      : `CardioUNEMI_${originalTab}_${new Date().toISOString().slice(0, 10)}.pptx`;

    await pptx.writeFile({ fileName });
    setProgress('¡Presentación PPTX descargada exitosamente!', 100);
  } finally {
    if (activeTabId !== originalTab && typeof switchTab === 'function') {
      switchTab(originalTab, document.querySelector(`.nav-item[onclick*="${originalTab}"]`));
    }
  }
}

// Sanitiza celdas CSV contra inyección de fórmulas en hojas de cálculo (Excel / Calc)
function sanitizeCsvCell(value) {
  let str = String(value == null ? '' : value).replace(/\r?\n|\r/g, ' ').trim();
  if (/^[=+@\-\t]/.test(str)) {
    str = "'" + str;
  }
  return `"${str.replace(/"/g, '""')}"`;
}

// 4. Exportación Tabular Estructurada a CSV (Compatible con Excel UTF-8 BOM, Cero PII)
async function exportCsv(scope, setProgress) {
  const tabs = scope === 'all'
    ? DASHBOARD_TABS
    : [DASHBOARD_TABS.find(t => t.id === activeTabId) || DASHBOARD_TABS[0]];
  const originalTab = activeTabId;
  const meta = getExportCohortMetadata();
  const rows = [];

  rows.push(['REPORTE EPIDEMIOLÓGICO CARDIOUNEMI - EXPORTACIÓN DE INDICADORES Y GRÁFICAS']);
  rows.push(['Institución', meta.instLabel, 'Periodo', meta.anoLabel, 'Muestra', meta.sampleText, 'Fecha', meta.todayStr]);
  if (meta.activeExtras.length) {
    rows.push(['Filtros Adicionales Activos', meta.activeExtras.join(' | ')]);
  }
  rows.push([]);
  rows.push([
    'Sección del Dashboard',
    'Tipo de Elemento',
    'Título del Indicador o Gráfica',
    'Serie / Grupo',
    'Categoría / Etiqueta',
    'Valor / Casos',
    'Porcentaje / Detalle Estadístico (IC 95%)'
  ]);

  const allApexInstances = Object.values(typeof charts !== 'undefined' ? charts : {}).filter(
    c => c && c.w && c.w.config
  );

  const preparedTabs = new Set();
  try {
    for (let i = 0; i < tabs.length; i++) {
      const tab = tabs[i];
      setProgress(`Extrayendo métricas: ${tab.title} (${i + 1}/${tabs.length})...`, Math.round(((i + 0.4) / tabs.length) * 90));
      await ensureTabReadyForExport(tab.id, preparedTabs);

      const tabEl = document.getElementById('tab-' + tab.id);
      if (!tabEl) continue;

      // 1. Extraer KPIs visibles de la sección
      tabEl.querySelectorAll('.card-kpi').forEach(kpiCard => {
        if (!isExportCardVisible(kpiCard)) return;
        const title = kpiCard.querySelector('.kpi-title')?.textContent?.trim() || '';
        const value = kpiCard.querySelector('.kpi-value')?.textContent?.trim() || '';
        const caption = kpiCard.querySelector('.kpi-caption')?.textContent?.trim() || '';
        if (title) {
          rows.push([tab.title, 'Indicador KPI', title, 'Cohorte Filtrada', title, value, caption]);
        }
      });

      // 2. Extraer series y datos exactos de cada gráfica visible en la sección
      tabEl.querySelectorAll('.card-visual').forEach(visCard => {
        if (!isExportCardVisible(visCard)) return;
        const chartTitle = visCard.querySelector('.visual-title h3, h3')?.textContent?.trim() || 'Gráfica';

        // Caso A: Gráfica Chart.js (<canvas>)
        const canvasEl = visCard.querySelector('canvas');
        if (canvasEl) {
          const cj = (window.Chart && typeof window.Chart.getChart === 'function'
            ? window.Chart.getChart(canvasEl)
            : null) || Object.values(typeof charts !== 'undefined' ? charts : {}).find(c => c && c.canvas === canvasEl);
          if (cj && cj.data) {
            const labels = Array.isArray(cj.data.labels) ? cj.data.labels : [];
            (cj.data.datasets || []).forEach((ds, dsIdx) => {
              const seriesName = ds.label || `Serie ${dsIdx + 1}`;
              const dataArr = Array.isArray(ds.data) ? ds.data : [];
              const sum = dataArr.reduce((acc, v) => acc + (typeof v === 'number' ? v : 0), 0);
              dataArr.forEach((pt, ptIdx) => {
                if (pt && typeof pt === 'object' && ('x' in pt || 'y' in pt)) {
                  rows.push([
                    tab.title,
                    'Gráfica (Dispersión)',
                    chartTitle,
                    seriesName,
                    `Punto ${ptIdx + 1}`,
                    `X=${pt.x}`,
                    `Y=${pt.y}`
                  ]);
                } else {
                  const rawLbl = labels[ptIdx] !== undefined ? labels[ptIdx] : `Categoría ${ptIdx + 1}`;
                  const cleanLbl = Array.isArray(rawLbl) ? rawLbl.join(' ') : String(rawLbl);
                  const numVal = typeof pt === 'number' ? pt : Number(pt);
                  const denom = (cj.config?.type === 'doughnut' || cj.config?.type === 'pie')
                    ? sum
                    : (meta.evalCount || sum || 1);
                  const pctStr = Number.isFinite(numVal) && denom > 0
                    ? `${((numVal / denom) * 100).toFixed(1).replace('.', ',')}%`
                    : '';
                  rows.push([tab.title, 'Gráfica', chartTitle, seriesName, cleanLbl, pt, pctStr]);
                }
              });
            });
          }
          return;
        }

        // Caso B: Gráfica ApexCharts (contenedor con SVG)
        const containerEl = visCard.querySelector('.chart-container[id]');
        if (containerEl) {
          const apexInst = allApexInstances.find(inst =>
            inst.el === containerEl ||
            inst.w?.globals?.dom?.baseEl === containerEl ||
            inst.w?.globals?.dom?.baseEl?.parentElement === containerEl
          );
          if (apexInst && apexInst.w?.config) {
            const cfg = apexInst.w.config;
            const categories = cfg.xaxis?.categories || cfg.labels || [];
            const seriesList = Array.isArray(cfg.series) ? cfg.series : [];
            seriesList.forEach((serie, sIdx) => {
              if (typeof serie === 'number') {
                const catName = categories[sIdx] || `Categoría ${sIdx + 1}`;
                const totalPie = seriesList.reduce((a, b) => a + (Number(b) || 0), 0) || 1;
                const pctStr = `${((serie / totalPie) * 100).toFixed(1).replace('.', ',')}%`;
                rows.push([tab.title, 'Gráfica', chartTitle, 'Distribución', catName, serie, pctStr]);
                return;
              }
              const sName = serie?.name || `Serie ${sIdx + 1}`;
              const sData = Array.isArray(serie?.data) ? serie.data : [];
              sData.forEach((dItem, dIdx) => {
                if (dItem && typeof dItem === 'object' && !Array.isArray(dItem)) {
                  const cat = dItem.x || categories[dIdx] || `Ítem ${dIdx + 1}`;
                  const yVal = Array.isArray(dItem.y) ? dItem.y.join(' – ') : dItem.y;
                  const goalVal = dItem.goals?.[0]?.value !== undefined ? `Estimación puntual: ${dItem.goals[0].value}%` : '';
                  rows.push([tab.title, 'Gráfica', chartTitle, sName, cat, yVal, goalVal]);
                } else {
                  const cat = categories[dIdx] || `Categoría ${dIdx + 1}`;
                  const cleanCat = Array.isArray(cat) ? cat.join(' ') : String(cat);
                  const numVal = Number(dItem);
                  const pctStr = Number.isFinite(numVal) && meta.evalCount > 0
                    ? `${((Math.abs(numVal) / meta.evalCount) * 100).toFixed(1).replace('.', ',')}%`
                    : '';
                  rows.push([tab.title, 'Gráfica', chartTitle, sName, cleanCat, dItem, pctStr]);
                }
              });
            });
          }
        }
      });
    }

    setProgress('Generando archivo CSV compatible con Excel...', 96);
    const csvContent = rows.map(row => row.map(sanitizeCsvCell).join(',')).join('\r\n');
    const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
    const fileName = scope === 'all'
      ? `CardioUNEMI_Datos_Dashboard_Integral_${new Date().toISOString().slice(0, 10)}.csv`
      : `CardioUNEMI_Datos_${originalTab}_${new Date().toISOString().slice(0, 10)}.csv`;

    downloadExportBlob(blob, fileName);
    setProgress('¡Archivo CSV descargado exitosamente!', 100);
  } finally {
    if (activeTabId !== originalTab) {
      switchTab(originalTab, document.querySelector(`.nav-item[onclick*="${originalTab}"]`));
    }
  }
}

window.exportCsv = exportCsv;
