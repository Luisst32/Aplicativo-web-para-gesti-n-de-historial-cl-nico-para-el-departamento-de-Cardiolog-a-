/**
 * CARDIOUNEMI - Dashboard Epidemiológico y Clínico.
 * Motor dinámico de analítica, agregación estadística y exportación profesional.
 * Procesa la cohorte clínica institucional a través de los 8 bloques:
 * 1. Datos del Individuo
 * 2. Exploración Física
 * 3. Factores de Riesgo Modificables
 * 4. Factores Emergentes
 * 5. Antecedentes Familiares
 * 6. Historia No Cardiovascular
 * 7. COVID-19 y Secuelas
 * 8. Electrocardiograma (ECG)
 */

// Variables de Estado Global
let allRecords = [];
let filteredRecords = [];
let activeTabId = 'resumen-general';

// Almacén de instancias de gráficos para actualización dinámica
const charts = {};

// Paleta de colores institucional y semafórica
const PALETTE = {
  canvas: '#FFFFFF',
  iceBlue: '#CFE9FF',
  primaryBlue: '#3AA0FF',
  emergencyRed: '#FF5A5F',
  navy: '#1B2A41',
  green: '#10B981',
  yellow: '#F59E0B',
  purple: '#8B5CF6',
  teal: '#14B8A6',
  gray: '#94A3B8'
};

// Formateadores numéricos locales
function formatPct(cnt, total) {
  if (!total || total === 0) return '0,0';
  return ((cnt / total) * 100).toFixed(1).replace('.', ',');
}

function formatMean(arr, decimals = 1) {
  const valid = arr.filter(v => v !== null && v !== undefined && !isNaN(v) && v > 0);
  if (valid.length === 0) return '0';
  const mean = valid.reduce((a, b) => a + b, 0) / valid.length;
  return decimals === 0 ? Math.round(mean).toString() : mean.toFixed(decimals).replace('.', ',');
}

function recordsWithValue(field) {
  return filteredRecords.filter(record => record[field] !== null && record[field] !== undefined);
}

function setKpiCaption(el, text) {
  const body = el.closest('.kpi-main-body');
  if (!body) return;
  let caption = body.querySelector('.kpi-caption');
  if (!caption) {
    caption = document.createElement('div');
    caption.className = 'kpi-caption';
    body.appendChild(caption);
  }
  caption.textContent = text;
}

function setPrevalenceEl(id, cases, valid, note = '') {
  const el = document.getElementById(id);
  if (!el) return;

  el.classList.remove('kpi-prevalence');
  el.textContent = valid > 0 ? `${formatPct(cases, valid)} %` : 'Sin dato';
  el.title = `${cases} casos de ${valid} registros evaluables${note ? `; ${note}` : ''}`;
  el.setAttribute('aria-label', el.title);
  setKpiCaption(el, `${cases} de ${valid} con dato${note ? ` · ${note}` : ''}`);
}

// Helpers para tooltips con porcentaje (ApexCharts y Chart.js)
function apexCountTooltip(customTotal) {
  return {
    y: {
      formatter: function(val) {
        if (typeof val !== 'number') return val;
        const total = customTotal || filteredRecords.length || 1;
        const pct = total > 0 ? ((val / total) * 100).toFixed(1).replace('.', ',') : '0,0';
        return `${val} casos (${pct} %)`;
      }
    }
  };
}

function apexPctTooltip() {
  return {
    y: {
      formatter: function(val) {
        if (typeof val !== 'number') return val;
        const n = filteredRecords.length || 0;
        const casos = n > 0 ? Math.round((val * n) / 100) : 0;
        return `${val}% (${casos} de ${n} casos)`;
      }
    }
  };
}

// Helper para DataLabels en ApexCharts: muestra cantidad y porcentaje en color negro nítido sin fondo negro
function apexCountAndPctDataLabel(customTotal, extraOptions = {}) {
  const extraStyle = extraOptions.style || {};
  return {
    enabled: true,
    formatter: function(val) {
      if (typeof val !== 'number') {
        val = parseFloat(val);
      }
      if (isNaN(val) || val <= 0) return '';
      const total = customTotal || filteredRecords.length || 1;
      const pct = ((val / total) * 100).toFixed(1).replace('.', ',');
      return `${val} (${pct}%)`;
    },
    style: {
      fontSize: '11px',
      fontWeight: 'bold',
      colors: ['#ffffff'],
      ...extraStyle
    },
    background: {
      enabled: false
    },
    dropShadow: {
      enabled: true,
      top: 1,
      left: 0,
      blur: 1,
      color: '#0f172a',
      opacity: 0.45
    },
    ...extraOptions,
    style: {
      fontSize: '11px',
      fontWeight: 'bold',
      colors: ['#ffffff'],
      ...extraStyle
    }
  };
}

// Configuración de Chart.js y DataLabels
// Configuración Global de ApexCharts (Desactivar animaciones, texto negro en ejes X e Y y relleno sólido)
if (typeof ApexCharts !== 'undefined' || typeof window.Apex !== 'undefined') {
  window.Apex = {
    chart: {
      toolbar: { show: false },
      animations: {
        enabled: false,
        animateGradually: { enabled: false },
        dynamicAnimation: { enabled: false }
      }
    },
    fill: {
      type: 'solid',
      opacity: 1
    },
    grid: {
      borderColor: '#e8eef5',
      strokeDashArray: 4
    },
    plotOptions: {
      bar: {
        horizontal: true,
        barHeight: '78%',
        borderRadius: 6,
        dataLabels: { position: 'center' },
        colors: {
          backgroundBarColors: ['#f1f5f9'],
          backgroundBarRadius: 6
        }
      }
    },
    xaxis: {
      labels: {
        style: {
          colors: '#000000',
          fontSize: '11px',
          fontWeight: 600
        }
      },
      axisBorder: {
        color: '#000000'
      },
      axisTicks: {
        color: '#000000'
      }
    },
    yaxis: {
      labels: {
        style: {
          colors: '#000000',
          fontSize: '11px',
          fontWeight: 600
        }
      }
    }
  };
}

if (typeof Chart !== 'undefined') {
  Chart.defaults.devicePixelRatio = Math.max(window.devicePixelRatio || 1, 2);
  Chart.defaults.color = '#000000';
  Chart.defaults.plugins.legend = Chart.defaults.plugins.legend || {};
  Chart.defaults.plugins.legend.labels = {
    ...(Chart.defaults.plugins.legend.labels || {}),
    usePointStyle: true,
    pointStyle: 'circle',
    boxWidth: 10,
    padding: 18,
    color: '#0f172a',
    font: { size: 12, weight: '600' }
  };
  Chart.defaults.datasets.doughnut = {
    ...(Chart.defaults.datasets.doughnut || {}),
    borderColor: '#ffffff',
    borderWidth: 4,
    borderRadius: 5,
    hoverOffset: 6
  };
  Chart.overrides.doughnut = Chart.overrides.doughnut || {};
  Chart.overrides.doughnut.cutout = '52%';
  Chart.defaults.datasets.bar = {
    ...(Chart.defaults.datasets.bar || {}),
    maxBarThickness: 76,
    categoryPercentage: 0.8,
    barPercentage: 0.9,
    borderRadius: 4
  };
  if (Chart.defaults.scale && Chart.defaults.scale.ticks) {
    Chart.defaults.scale.ticks.color = '#000000';
    Chart.defaults.scale.ticks.font = { weight: '600' };
  }
  if (typeof ChartDataLabels !== 'undefined') {
    Chart.register(ChartDataLabels);
    Chart.defaults.plugins.datalabels = {
      display: false,
      clip: false
    };
  }
  Chart.defaults.layout = Chart.defaults.layout || {};
  Chart.defaults.layout.padding = { top: 24, right: 8, bottom: 4, left: 4 };

  if (Chart.defaults?.plugins?.tooltip) {
    Chart.defaults.plugins.tooltip.callbacks.label = function(context) {
      let label = context.dataset.label || '';
      if (label) label += ': ';

      if (context.chart.config.type === 'scatter') {
        const p = context.raw || context.parsed;
        return `${label}IMC: ${p.x} kg/m², Cintura: ${p.y} cm`;
      }

      const val = context.parsed.y !== undefined ? context.parsed.y : (context.parsed !== undefined ? context.parsed : context.raw);
      if (typeof val !== 'number') return `${label}${val}`;

      if (context.chart.canvas.id === 'chart-ecg-fc-comparativa') {
        return `${label}${val} lpm`;
      }

      let total = 0;
      if (context.chart.config.type === 'doughnut' || context.chart.config.type === 'pie') {
        total = context.dataset.data.reduce((a, b) => a + (typeof b === 'number' ? b : 0), 0);
      } else if (context.chart.config.options?.scales?.x?.stacked || context.chart.config.options?.scales?.y?.stacked) {
        total = context.chart.data.datasets.reduce((acc, ds) => acc + (typeof ds.data[context.dataIndex] === 'number' ? ds.data[context.dataIndex] : 0), 0);
      } else {
        total = filteredRecords.length || context.dataset.data.reduce((a, b) => a + (typeof b === 'number' ? b : 0), 0);
      }

      const pct = total > 0 ? ((val / total) * 100).toFixed(1).replace('.', ',') : '0,0';
      return `${label}${val} casos (${pct} %)`;
    };
  }
}

// Helper para datalabels de Chart.js en barras (sin fondo negro, texto negro)
function chartJsBarDataLabels(showPct = true, customTotal = null) {
  return {
    display: (ctx) => {
      const v = ctx.dataset.data[ctx.dataIndex];
      return typeof v === 'number' && v > 0;
    },
    anchor: 'center',
    align: 'center',
    offset: 0,
    clip: false,
    color: '#ffffff',
    backgroundColor: 'transparent',
    borderRadius: 0,
    padding: { top: 1, bottom: 1, left: 2, right: 2 },
    borderWidth: 0,
    font: { weight: 'bold', size: 11 },
    formatter: (val) => {
      if (!val || val <= 0) return '';
      const total = customTotal || filteredRecords.length || 1;
      const pct = ((val / total) * 100).toFixed(1).replace('.', ',');
      return `${val} (${pct}%)`;
    }
  };
}

// Helper para datalabels de Chart.js en donas/pies (sin fondo negro, texto negro)
function chartJsDonutDataLabels(minPct = 0.08) {
  return {
    display: (ctx) => {
      const v = ctx.dataset.data[ctx.dataIndex];
      const sum = ctx.dataset.data.reduce((a, b) => a + (typeof b === 'number' ? b : 0), 0);
      return typeof v === 'number' && v > 0 && (v / sum) >= minPct;
    },
    color: '#ffffff',
    anchor: 'center',
    align: 'center',
    backgroundColor: 'transparent',
    borderRadius: 0,
    padding: { top: 1, bottom: 1, left: 2, right: 2 },
    borderWidth: 0,
    font: { weight: 'bold', size: 10 },
    formatter: (val, ctx) => {
      const sum = ctx.dataset.data.reduce((a, b) => a + (typeof b === 'number' ? b : 0), 0) || 1;
      const pct = ((val / sum) * 100).toFixed(1).replace('.', ',');
      return `${val} (${pct}%)`;
    }
  };
}

// Navegación entre pestañas temáticas
function switchTab(tabId, element) {
  activeTabId = tabId;
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  if (element) {
    element.classList.add('active');
  } else {
    const navBtn = document.querySelector(`.nav-item[onclick*="${tabId}"]`);
    if (navBtn) navBtn.classList.add('active');
  }

  document.querySelectorAll('.tab-view').forEach(view => view.classList.remove('active'));
  const targetView = document.getElementById('tab-' + tabId);
  if (targetView) targetView.classList.add('active');

  // Actualizar título de vista activa
  const titleEl = document.getElementById('view-title');
  if (titleEl) {
    const titles = {
      'resumen-general': 'Resumen General Epidemiológico',
      'datos-individuo': 'Datos del Individuo y Filiación',
      'exploracion-fisica': 'Exploración Física y Antropometría',
      'factores-modificables': 'Factores de Riesgo Modificables',
      'factores-emergentes': 'Factores de Riesgo Emergentes',
      'antecedentes-familiares': 'Antecedentes Familiares Cardiovasculares',
      'historia-no-cardio': 'Historia Clínica No Cardiovascular',
      'covid-19': 'COVID-19 y Secuelas Post-Infección',
      'electrocardiograma': 'Resultados del Electrocardiograma (ECG)'
    };
    titleEl.innerText = titles[tabId] || 'Dashboard Epidemiológico';
  }

  // Renderizar o actualizar gráficos del tab activo
  renderTabCharts(tabId);

  setTimeout(() => {
    window.dispatchEvent(new Event('resize'));
  }, 60);
}

// Inicialización del Dashboard
async function initDashboard() {
  const embeddedDataEl = document.getElementById('dashboard-records-data');
  if (embeddedDataEl && embeddedDataEl.textContent.trim()) {
    try {
      allRecords = JSON.parse(embeddedDataEl.textContent);
    } catch (e) {
      console.warn('Error al parsear datos embebidos:', e);
    }
  }

  if (!allRecords || allRecords.length === 0) {
    try {
      const response = await fetch('/api/data/');
      if (response.ok) {
        const payload = await response.json();
        allRecords = payload.records || [];
      }
    } catch (err) {
      console.error('Error al consultar /api/data/:', err);
    }
  }

  syncSlicerOptions();
  filteredRecords = [...allRecords];
  updateAllKPIs();
  renderTabCharts(activeTabId);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initDashboard);
} else {
  initDashboard();
}

// Sincronización de opciones de selectores
function syncSlicerOptions() {
  if (!allRecords || allRecords.length === 0) return;

  const codigoSelect = document.getElementById('slicer-codigo');
  if (codigoSelect && codigoSelect.tagName === 'SELECT') {
    const existing = Array.from(codigoSelect.options).map(o => o.value);
    const uniqueMap = new Map();
    allRecords.forEach(r => {
      const c = r.study_code || r.patient_id || r.id;
      if (c && !uniqueMap.has(String(c))) {
        uniqueMap.set(String(c), {
          code: String(c),
          label: r.nombre ? `Ficha #${c} (${r.nombre})` : `Ficha #${c}`
        });
      }
    });
    const unique = Array.from(uniqueMap.values()).sort((a, b) => {
      const numA = parseInt(a.code, 10);
      const numB = parseInt(b.code, 10);
      if (!isNaN(numA) && !isNaN(numB)) return numA - numB;
      return a.code.localeCompare(b.code);
    });
    unique.forEach(item => {
      if (!existing.includes(item.code)) {
        const opt = document.createElement('option');
        opt.value = item.code;
        opt.textContent = item.label;
        codigoSelect.appendChild(opt);
      }
    });
  }

  const instSelect = document.getElementById('slicer-inst');
  if (instSelect) {
    const existing = Array.from(instSelect.options).map(o => o.value);
    const unique = [...new Set(allRecords.map(r => r.institucion))].filter(Boolean).sort();
    unique.forEach(inst => {
      if (!existing.includes(inst)) {
        const opt = document.createElement('option');
        opt.value = inst;
        opt.textContent = inst;
        instSelect.appendChild(opt);
      }
    });
  }

  const yearSelect = document.getElementById('slicer-ano');
  if (yearSelect) {
    const existing = Array.from(yearSelect.options).map(o => o.value);
    const unique = [...new Set(allRecords.map(r => r.ano))].filter(Boolean).sort((a, b) => b - a);
    unique.forEach(y => {
      const valStr = String(y);
      if (!existing.includes(valStr)) {
        const opt = document.createElement('option');
        opt.value = valStr;
        opt.textContent = `Año ${y}`;
        yearSelect.appendChild(opt);
      }
    });
  }

  const catSelect = document.getElementById('slicer-cat');
  if (catSelect) {
    const existing = Array.from(catSelect.options).map(o => o.value);
    const unique = [...new Set(allRecords.map(r => r.categoria))].filter(Boolean).sort();
    unique.forEach(c => {
      if (!existing.includes(c)) {
        const opt = document.createElement('option');
        opt.value = c;
        opt.textContent = c;
        catSelect.appendChild(opt);
      }
    });
  }

  poblarDropdownFichasDesdeRecords();
}

// =========================================================================
// GESTIÓN DEL DROPDOWN Y FILTRO POR N.° FICHA CLÍNICA
// =========================================================================
function abrirDropdownFichas() {
  const menu = document.getElementById('dropdown-fichas-menu');
  if (menu) {
    menu.style.display = 'block';
    filtrarDropdownFichas();
  }
}

function cerrarDropdownFichas() {
  const menu = document.getElementById('dropdown-fichas-menu');
  if (menu) menu.style.display = 'none';
}

function toggleDropdownFichas(e) {
  if (e) e.stopPropagation();
  const menu = document.getElementById('dropdown-fichas-menu');
  if (menu) {
    if (menu.style.display === 'block') {
      menu.style.display = 'none';
    } else {
      menu.style.display = 'block';
      filtrarDropdownFichas();
    }
  }
}

function seleccionarFichaSlicer(code) {
  const inp = document.getElementById('slicer-codigo');
  if (inp) {
    inp.value = code ? code : '';
  }
  cerrarDropdownFichas();
  onSlicerChange();
}

window.abrirDropdownFichas = abrirDropdownFichas;
window.cerrarDropdownFichas = cerrarDropdownFichas;
window.toggleDropdownFichas = toggleDropdownFichas;
window.seleccionarFichaSlicer = seleccionarFichaSlicer;
window.onSlicerCodigoInput = onSlicerCodigoInput;
window.filtrarDropdownFichas = filtrarDropdownFichas;
window.onSlicerChange = onSlicerChange;
window.toggleSlicersPanel = toggleSlicersPanel;

function toggleSlicersPanel() {
  const wrapper = document.getElementById('slicers-collapse-wrapper');
  const btn = document.getElementById('btn-toggle-slicers');
  const label = document.getElementById('slicers-toggle-label');
  if (!wrapper) return;

  const isCurrentlyCollapsed = wrapper.classList.contains('is-collapsed');

  if (isCurrentlyCollapsed) {
    wrapper.classList.add('is-animating');
    wrapper.classList.remove('is-collapsed');
    if (btn) {
      btn.classList.remove('is-collapsed');
      btn.setAttribute('aria-expanded', 'true');
      btn.title = 'Ocultar filtros';
    }
    if (label) label.textContent = 'Ocultar filtros';
    try { localStorage.setItem('cardiounemi_slicers_collapsed', 'false'); } catch (e) {}

    setTimeout(() => {
      wrapper.classList.remove('is-animating');
      window.dispatchEvent(new Event('resize'));
    }, 360);
  } else {
    wrapper.classList.add('is-animating');
    if (typeof cerrarDropdownFichas === 'function') cerrarDropdownFichas();
    wrapper.classList.add('is-collapsed');
    if (btn) {
      btn.classList.add('is-collapsed');
      btn.setAttribute('aria-expanded', 'false');
      btn.title = 'Mostrar filtros';
    }
    if (label) label.textContent = 'Mostrar filtros';
    try { localStorage.setItem('cardiounemi_slicers_collapsed', 'true'); } catch (e) {}

    setTimeout(() => {
      wrapper.classList.remove('is-animating');
      window.dispatchEvent(new Event('resize'));
    }, 360);
  }
}

function onSlicerCodigoInput() {
  filtrarDropdownFichas();
  abrirDropdownFichas();
  onSlicerChange();
}

function filtrarDropdownFichas() {
  const inp = document.getElementById('slicer-codigo');
  const raw = (inp?.value || '').trim().toLowerCase();
  const val = raw.replace(/^#/, '').replace(/^ficha\s*#?/, '').trim();
  const menu = document.getElementById('dropdown-fichas-menu');
  if (!menu) return;

  const items = menu.querySelectorAll('.dropdown-ficha-item');
  items.forEach(it => {
    const code = (it.getAttribute('data-code') || '').toLowerCase();
    if (!code || !val || code === val || code.startsWith(val) || it.textContent.toLowerCase().includes(val)) {
      it.style.display = 'block';
    } else {
      it.style.display = 'none';
    }
  });
}

function poblarDropdownFichasDesdeRecords() {
  const menu = document.getElementById('dropdown-fichas-menu');
  if (!menu || !allRecords || allRecords.length === 0) return;

  const existingCodes = Array.from(menu.querySelectorAll('[data-code]')).map(el => el.getAttribute('data-code'));
  const uniqueCodes = [...new Set(allRecords.map(r => r.study_code ? String(r.study_code).trim() : null).filter(Boolean))].sort((a, b) => {
    const na = parseInt(a, 10);
    const nb = parseInt(b, 10);
    if (!isNaN(na) && !isNaN(nb)) return na - nb;
    return a.localeCompare(b);
  });

  if (existingCodes.length === 0) {
    menu.innerHTML = '<div class="dropdown-ficha-item" onclick="seleccionarFichaSlicer(\'\')" style="padding: 6px 12px; cursor: pointer; font-size: 0.85rem; font-weight: 600; color: #1e293b; border-bottom: 1px solid #f1f5f9;">Todas las Fichas</div>';
    uniqueCodes.forEach(c => {
      const item = document.createElement('div');
      item.className = 'dropdown-ficha-item';
      item.setAttribute('data-code', c);
      item.style.cssText = 'padding: 6px 12px; cursor: pointer; font-size: 0.85rem; font-weight: 600; color: #334155; font-family: monospace;';
      item.textContent = `Ficha #${c}`;
      item.onclick = () => seleccionarFichaSlicer(c);
      menu.appendChild(item);
    });
  }
}

// Cerrar desplegable al hacer clic fuera del control
document.addEventListener('click', (e) => {
  const wrapper = document.getElementById('slicer-codigo-wrapper');
  if (wrapper && !wrapper.contains(e.target)) {
    cerrarDropdownFichas();
  }
});

// Evento disparado al cambiar cualquier slicer
function onSlicerChange() {
  const rawInput = (document.getElementById('slicer-codigo')?.value || '').trim().toLowerCase();
  const codigo = rawInput.replace(/^#/, '').replace(/^ficha\s*#?/, '').trim();
  const inst = document.getElementById('slicer-inst')?.value || 'all';
  const ano = document.getElementById('slicer-ano')?.value || 'all';
  const cat = document.getElementById('slicer-cat')?.value || 'all';
  const sexo = document.getElementById('slicer-sexo')?.value || 'all';
  const edad = document.getElementById('slicer-edad')?.value || 'all';
  const riesgo = document.getElementById('slicer-riesgo')?.value || 'all';

  const isCodigoAll = !codigo || codigo === 'all';

  filteredRecords = allRecords.filter(r => {
    if (codigo && codigo !== 'all' && codigo !== 'todas las fichas' && codigo !== 'todas') {
      const sc = String(r.study_code || '').trim().toLowerCase();
      // Si el código buscado son dígitos o número de ficha, aplicar coincidencia exacta de ficha
      if (/^\d+$/.test(codigo)) {
        if (sc !== codigo) {
          return false;
        }
      } else {
        const pid = String(r.patient_id || r.id || '').toLowerCase();
        const ced = String(r.id_card || '').toLowerCase();
        const nom = String(r.nombre || '').toLowerCase();
        if (sc !== codigo && !pid.includes(codigo) && !ced.includes(codigo) && !nom.includes(codigo)) {
          return false;
        }
      }
    }
    if (inst !== 'all' && r.institucion !== inst) return false;
    if (ano !== 'all' && String(r.ano) !== String(ano)) return false;
    if (cat !== 'all' && r.categoria !== cat) return false;
    if (sexo !== 'all' && r.sexo !== sexo) return false;
    if (edad !== 'all' && r.grupo_edad !== edad) return false;
    if (riesgo !== 'all' && r.riesgo_global !== riesgo) return false;
    return true;
  });

  const total = allRecords.length;
  const count = filteredRecords.length;
  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
  const sampleCountEl = document.getElementById('active-sample-count');
  if (sampleCountEl) {
    sampleCountEl.textContent = `${count} de ${total} evaluados (${pct}%)`;
  }

  updateAllKPIs();
  renderTabCharts(activeTabId);
}

// Actualiza todos los valores de las tarjetas KPI en todas las pestañas
function updateAllKPIs() {
  const n = filteredRecords.length;

  // TAB 0: Resumen General
  const htaCnt = filteredRecords.filter(r => r.hipertension).length;
  const dlCnt = filteredRecords.filter(r => r.dislipemia).length;
  const spObCnt = filteredRecords.filter(r => r.sobrepeso_u_obesidad).length;
  const altoCnt = filteredRecords.filter(r => r.factores_riesgo_count >= 2).length;

  const setEl = (id, val) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = val;
    if (id === 'kpi-total') {
      setKpiCaption(el, `${formatPct(n, allRecords.length)} % de la muestra total`);
    } else {
      setKpiCaption(el, id === 'kpi-cov-recuperados' ? 'Entre quienes tuvieron COVID-19' : 'Promedio de valores registrados');
    }
  };

  setEl('kpi-total', n.toString());
  setPrevalenceEl('kpi-hta', htaCnt, recordsWithValue('hipertension').length);
  setPrevalenceEl('kpi-dl', dlCnt, recordsWithValue('dislipemia').length);
  setPrevalenceEl('kpi-sp-ob', spObCnt, recordsWithValue('sobrepeso_u_obesidad').length);
  setPrevalenceEl('kpi-riesgo-alto', altoCnt, recordsWithValue('factores_riesgo_count').length);

  // TAB 1: Datos del Individuo
  const hombresCnt = filteredRecords.filter(r => r.sexo === 'Hombre').length;
  const mujeresCnt = filteredRecords.filter(r => r.sexo === 'Mujer').length;
  const postgradoCnt = filteredRecords.filter(r => r.nivel_estudios === 'Postgrado').length;
  const casadosCnt = filteredRecords.filter(r => r.estado_civil === 'Casado/a').length;

  setEl('kpi-ind-edad', `${formatMean(filteredRecords.map(r => r.edad))} años`);
  setPrevalenceEl('kpi-ind-hombres', hombresCnt, recordsWithValue('sexo').length);
  setPrevalenceEl('kpi-ind-mujeres', mujeresCnt, recordsWithValue('sexo').length);
  setPrevalenceEl('kpi-ind-postgrado', postgradoCnt, recordsWithValue('nivel_estudios').length);
  setPrevalenceEl('kpi-ind-casados', casadosCnt, recordsWithValue('estado_civil').length);

  // TAB 2: Exploración Física
  const cinturaRiesgo = filteredRecords.filter(r => r.abd_riesgo && r.abd_riesgo.includes('Riesgo')).length;
  setEl('kpi-exp-imc', `${formatMean(filteredRecords.map(r => r.imc))} kg/m²`);
  setPrevalenceEl('kpi-exp-cintura', cinturaRiesgo, recordsWithValue('abd_riesgo').filter(r => r.abd_riesgo !== 'Sin dato').length);
  setEl('kpi-exp-tas', `${formatMean(filteredRecords.map(r => r.tas), 0)} mmHg`);
  setEl('kpi-exp-tad', `${formatMean(filteredRecords.map(r => r.tad), 0)} mmHg`);
  setEl('kpi-exp-sato2', `${formatMean(filteredRecords.map(r => r.sat_o2), 0)} %`);

  // TAB 3: Factores Modificables
  const dmCnt = filteredRecords.filter(r => r.diabetes).length;
  const tabacoCnt = filteredRecords.filter(r => r.fumador_activo).length;
  const actFisicaCnt = filteredRecords.filter(r => r.actividad_fisica).length;
  const higadoCnt = filteredRecords.filter(r => r.higado_graso).length;
  const apneaCnt = filteredRecords.filter(r => r.apnea_sueno).length;
  const vascCnt = filteredRecords.filter(r => r.vasculopatia_cualquiera).length;
  const hombres = filteredRecords.filter(r => r.sexo === 'Hombre');
  const disfuncionCnt = hombres.filter(r => r.disfuncion_erectil).length;
  setPrevalenceEl('kpi-mod-hta', htaCnt, recordsWithValue('hipertension').filter(r => r['hipertension'] !== 'Sin dato').length);
  setPrevalenceEl('kpi-mod-dm', dmCnt, recordsWithValue('diabetes').filter(r => r['diabetes'] !== 'Sin dato').length);
  setPrevalenceEl('kpi-mod-dl', dlCnt, recordsWithValue('dislipemia').filter(r => r['dislipemia'] !== 'Sin dato').length);
  setPrevalenceEl('kpi-mod-tabaco', tabacoCnt, recordsWithValue('fumador_activo').length);
  setPrevalenceEl('kpi-mod-act-fisica', actFisicaCnt, recordsWithValue('actividad_fisica').length);
  setPrevalenceEl('kpi-mod-higado', higadoCnt, recordsWithValue('higado_graso').length);
  setPrevalenceEl('kpi-mod-apnea', apneaCnt, recordsWithValue('apnea_sueno').length);
  setPrevalenceEl('kpi-mod-vasculopatia', vascCnt, recordsWithValue('vasculopatia_cualquiera').length);
  setPrevalenceEl('kpi-mod-disfuncion', disfuncionCnt, hombres.filter(r => r.disfuncion_erectil !== null && r.disfuncion_erectil !== undefined).length, 'solo hombres');

  // TAB 4: Factores Emergentes
  const suenoMalo = filteredRecords.filter(r => r.calidad_sueno === 'Mala').length;
  const estresTot = filteredRecords.filter(r => r.estres && r.estres !== 'Sin dato' && !r.estres.includes('Sin estrés')).length;
  const malAmb = filteredRecords.filter(r => r.mal_ambiente_laboral).length;
  const persA = filteredRecords.filter(r => r.personalidad_tipo_a).length;
  const toxicos = filteredRecords.filter(r => r.toxicos_laboral).length;
  setPrevalenceEl('kpi-em-sueno-malo', suenoMalo, recordsWithValue('calidad_sueno').filter(r => r.calidad_sueno !== 'Sin dato').length);
  setPrevalenceEl('kpi-em-estres', estresTot, recordsWithValue('estres').filter(r => r.estres !== 'Sin dato').length);
  setPrevalenceEl('kpi-em-mal-amb', malAmb, recordsWithValue('mal_ambiente_laboral').filter(r => r['mal_ambiente_laboral'] !== 'Sin dato').length);
  setPrevalenceEl('kpi-em-pers-a', persA, recordsWithValue('personalidad_tipo_a').filter(r => r['personalidad_tipo_a'] !== 'Sin dato').length);
  setPrevalenceEl('kpi-em-toxicos', toxicos, recordsWithValue('toxicos_laboral').filter(r => r['toxicos_laboral'] !== 'Sin dato').length);

  // TAB 5: Antecedentes Familiares
  const famHta = filteredRecords.filter(r => r.ant_fam_hta).length;
  const famDm = filteredRecords.filter(r => r.ant_fam_dm).length;
  const famDlp = filteredRecords.filter(r => r.ant_fam_dlp).length;
  const famCvMayor = filteredRecords.filter(r => r.ant_fam_cv_mayor).length;
  const famCualquiera = filteredRecords.filter(r => r.ant_fam_cualquiera).length;
  setPrevalenceEl('kpi-fam-hta', famHta, recordsWithValue('ant_fam_hta').length);
  setPrevalenceEl('kpi-fam-dm', famDm, recordsWithValue('ant_fam_dm').length);
  setPrevalenceEl('kpi-fam-dlp', famDlp, recordsWithValue('ant_fam_dlp').length);
  setPrevalenceEl('kpi-fam-cv-mayor', famCvMayor, recordsWithValue('ant_fam_cv_mayor').length);
  setPrevalenceEl('kpi-fam-total', famCualquiera, recordsWithValue('ant_fam_cualquiera').length);

  // TAB 6: Historia No Cardiovascular
  const respCnt = filteredRecords.filter(r => r.respiratorio_desc && r.respiratorio_desc !== 'Sin dato' && !r.respiratorio_desc.includes('Sin patología')).length;
  const mentalCnt = filteredRecords.filter(r => r.salud_mental_desc && r.salud_mental_desc !== 'Sin dato' && !r.salud_mental_desc.includes('Sin trastorno')).length;
  const reumaCnt = filteredRecords.filter(r => r.enfermedad_reumatologica).length;
  const alergiasCnt = filteredRecords.filter(r => r.alergias_medicamentos).length;
  const cancerCnt = filteredRecords.filter(r => r.cancer).length;
  const ircCnt = filteredRecords.filter(r => r.insuficiencia_renal).length;
  setPrevalenceEl('kpi-nc-resp', respCnt, recordsWithValue('respiratorio_desc').filter(r => r['respiratorio_desc'] !== 'Sin dato').length);
  setPrevalenceEl('kpi-nc-mental', mentalCnt, recordsWithValue('salud_mental_desc').filter(r => r['salud_mental_desc'] !== 'Sin dato').length);
  setPrevalenceEl('kpi-nc-reuma', reumaCnt, recordsWithValue('enfermedad_reumatologica').filter(r => r['enfermedad_reumatologica'] !== 'Sin dato').length);
  setPrevalenceEl('kpi-nc-alergias', alergiasCnt, recordsWithValue('alergias_medicamentos').filter(r => r['alergias_medicamentos'] !== 'Sin dato').length);
  setPrevalenceEl('kpi-nc-cancer', cancerCnt, recordsWithValue('cancer').length);
  setPrevalenceEl('kpi-nc-irc', ircCnt, recordsWithValue('insuficiencia_renal').length);

  // TAB 7: COVID-19 y Secuelas
  const covidInf = filteredRecords.filter(r => r.covid_infeccion).length;
  const covidHosp = filteredRecords.filter(r => r.covid_hospitalizacion).length;
  const covidSec = filteredRecords.filter(r => r.covid_tiene_secuelas).length;
  const covidFatiga = filteredRecords.filter(r => r.covid_fatiga_long).length;
  const covidRecup = covidInf > 0 ? (covidInf - covidSec) : 0;
  setPrevalenceEl('kpi-cov-infeccion', covidInf, recordsWithValue('covid_infeccion').filter(r => r['covid_infeccion'] !== 'Sin dato').length);
  setPrevalenceEl('kpi-cov-hosp', covidHosp, recordsWithValue('covid_hospitalizacion').filter(r => r['covid_hospitalizacion'] !== 'Sin dato').length);
  setPrevalenceEl('kpi-cov-secuelas', covidSec, recordsWithValue('covid_tiene_secuelas').filter(r => r['covid_tiene_secuelas'] !== 'Sin dato').length);
  setPrevalenceEl('kpi-cov-fatiga', covidFatiga, recordsWithValue('covid_fatiga_long').filter(r => r['covid_fatiga_long'] !== 'Sin dato').length);
  setEl('kpi-cov-recuperados', `${formatPct(covidRecup, covidInf || 1)} %`);
  setPrevalenceEl('kpi-covid-summary', covidInf, recordsWithValue('covid_infeccion').length);

  // TAB 8: Electrocardiograma (ECG)
  const sinusalCnt = filteredRecords.filter(r => r.ecg_es_sinusal).length;
  const arritmiaCnt = filteredRecords.filter(r => r.ecg_arritmia).length;
  setPrevalenceEl('kpi-ecg-sinusal', sinusalCnt, recordsWithValue('ecg_es_sinusal').filter(r => r['ecg_es_sinusal'] !== 'Sin dato').length);
  setPrevalenceEl('kpi-ecg-arritmia', arritmiaCnt, recordsWithValue('ecg_arritmia').filter(r => r['ecg_arritmia'] !== 'Sin dato').length);
  setEl('kpi-ecg-pr', `${formatMean(filteredRecords.map(r => r.ecg_pr_ms), 0)} ms`);
  setEl('kpi-ecg-qrs', `${formatMean(filteredRecords.map(r => r.ecg_qrs_ms), 0)} ms`);
  setEl('kpi-ecg-qtc', `${formatMean(filteredRecords.map(r => r.ecg_qtc_ms), 0)} ms`);
}

// Despachador de renderizado por pestaña activa
function renderTabCharts(tabId) {
  const targetView = document.getElementById('tab-' + tabId);
  if (targetView) {
    targetView.querySelectorAll('.chart-skeleton-placeholder').forEach(el => el.remove());
    targetView.querySelectorAll('.chart-container').forEach(el => el.classList.remove('skeleton-loading'));
  }

  switch (tabId) {
    case 'resumen-general':
      renderTabResumenGeneral();
      break;
    case 'datos-individuo':
      renderTabDatosIndividuo();
      break;
    case 'exploracion-fisica':
      renderTabExploracionFisica();
      break;
    case 'factores-modificables':
      renderTabFactoresModificables();
      break;
    case 'factores-emergentes':
      renderTabFactoresEmergentes();
      break;
    case 'antecedentes-familiares':
      renderTabAntecedentesFamiliares();
      break;
    case 'historia-no-cardio':
      renderTabHistoriaNoCardio();
      break;
    case 'covid-19':
      renderTabCovid19();
      break;
    case 'electrocardiograma':
      renderTabElectrocardiograma();
      break;
  }
}

// -------------------------------------------------------------
// TAB 0: RESUMEN GENERAL CHARTS
// -------------------------------------------------------------

