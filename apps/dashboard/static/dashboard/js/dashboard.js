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

// Helper para DataLabels en ApexCharts: muestra cantidad y porcentaje de manera visible
function apexCountAndPctDataLabel(customTotal) {
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
      colors: ['#1B2A41']
    },
    background: {
      enabled: true,
      foreColor: '#FFFFFF',
      borderRadius: 4,
      padding: 4,
      opacity: 0.95,
      borderWidth: 1,
      borderColor: '#0F172A'
    }
  };
}

// Configuración de Chart.js y DataLabels
if (typeof Chart !== 'undefined') {
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

// Helper para datalabels de Chart.js en barras
function chartJsBarDataLabels(showPct = true, customTotal = null) {
  return {
    display: (ctx) => {
      const v = ctx.dataset.data[ctx.dataIndex];
      return typeof v === 'number' && v > 0;
    },
    anchor: 'end',
    align: 'top',
    offset: 5,
    clip: false,
    color: '#FFFFFF',
    backgroundColor: '#1B2A41',
    borderRadius: 4,
    padding: { top: 3, bottom: 3, left: 6, right: 6 },
    borderWidth: 1,
    borderColor: '#0F172A',
    font: { weight: 'bold', size: 10.5 },
    formatter: (val) => {
      if (!val || val <= 0) return '';
      const total = customTotal || filteredRecords.length || 1;
      const pct = ((val / total) * 100).toFixed(1).replace('.', ',');
      return `${val} (${pct}%)`;
    }
  };
}

// Helper para datalabels de Chart.js en donas/pies
function chartJsDonutDataLabels() {
  return {
    display: (ctx) => {
      const v = ctx.dataset.data[ctx.dataIndex];
      const sum = ctx.dataset.data.reduce((a, b) => a + (typeof b === 'number' ? b : 0), 0);
      return typeof v === 'number' && v > 0 && (v / sum) >= 0.05;
    },
    color: '#FFFFFF',
    backgroundColor: '#1B2A41',
    borderRadius: 4,
    padding: { top: 3, bottom: 3, left: 6, right: 6 },
    borderWidth: 1,
    borderColor: '#0F172A',
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
}

// Evento disparado al cambiar cualquier slicer
function onSlicerChange() {
  const inst = document.getElementById('slicer-inst')?.value || 'all';
  const ano = document.getElementById('slicer-ano')?.value || 'all';
  const cat = document.getElementById('slicer-cat')?.value || 'all';
  const sexo = document.getElementById('slicer-sexo')?.value || 'all';
  const edad = document.getElementById('slicer-edad')?.value || 'all';
  const riesgo = document.getElementById('slicer-riesgo')?.value || 'all';

  filteredRecords = allRecords.filter(r => {
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

  const setEl = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };

  setEl('kpi-total', n.toString());
  setEl('kpi-hta', `${formatPct(htaCnt, n)} %`);
  setEl('kpi-dl', `${formatPct(dlCnt, n)} %`);
  setEl('kpi-sp-ob', `${formatPct(spObCnt, n)} %`);
  setEl('kpi-riesgo-alto', `${formatPct(altoCnt, n)} %`);

  // TAB 1: Datos del Individuo
  const hombresCnt = filteredRecords.filter(r => r.sexo === 'Hombre').length;
  const mujeresCnt = filteredRecords.filter(r => r.sexo === 'Mujer').length;
  const postgradoCnt = filteredRecords.filter(r => r.nivel_estudios === 'Postgrado').length;
  const casadosCnt = filteredRecords.filter(r => r.estado_civil === 'Casado/a').length;

  setEl('kpi-ind-edad', `${formatMean(filteredRecords.map(r => r.edad))} años`);
  setEl('kpi-ind-hombres', `${formatPct(hombresCnt, n)} %`);
  setEl('kpi-ind-mujeres', `${formatPct(mujeresCnt, n)} %`);
  setEl('kpi-ind-postgrado', `${formatPct(postgradoCnt, n)} %`);
  setEl('kpi-ind-casados', `${formatPct(casadosCnt, n)} %`);

  // TAB 2: Exploración Física
  const cinturaRiesgo = filteredRecords.filter(r => r.abd_riesgo && r.abd_riesgo.includes('Riesgo')).length;
  setEl('kpi-exp-imc', `${formatMean(filteredRecords.map(r => r.imc))} kg/m²`);
  setEl('kpi-exp-cintura', `${formatPct(cinturaRiesgo, n)} %`);
  setEl('kpi-exp-tas', `${formatMean(filteredRecords.map(r => r.tas), 0)} mmHg`);
  setEl('kpi-exp-tad', `${formatMean(filteredRecords.map(r => r.tad), 0)} mmHg`);
  setEl('kpi-exp-sato2', `${formatMean(filteredRecords.map(r => r.sat_o2), 0)} %`);

  // TAB 3: Factores Modificables
  const dmCnt = filteredRecords.filter(r => r.diabetes).length;
  const tabacoCnt = filteredRecords.filter(r => r.fumador_activo).length;
  const actFisicaCnt = filteredRecords.filter(r => r.actividad_fisica).length;
  setEl('kpi-mod-hta', `${formatPct(htaCnt, n)} %`);
  setEl('kpi-mod-dm', `${formatPct(dmCnt, n)} %`);
  setEl('kpi-mod-dl', `${formatPct(dlCnt, n)} %`);
  setEl('kpi-mod-tabaco', `${formatPct(tabacoCnt, n)} %`);
  setEl('kpi-mod-act-fisica', `${formatPct(actFisicaCnt, n)} %`);

  // TAB 4: Factores Emergentes
  const suenoMalo = filteredRecords.filter(r => r.calidad_sueno === 'Mala').length;
  const estresTot = filteredRecords.filter(r => r.estres && !r.estres.includes('Sin estrés')).length;
  const malAmb = filteredRecords.filter(r => r.mal_ambiente_laboral).length;
  const persA = filteredRecords.filter(r => r.personalidad_tipo_a).length;
  const toxicos = filteredRecords.filter(r => r.toxicos_laboral).length;
  setEl('kpi-em-sueno-malo', `${formatPct(suenoMalo, n)} %`);
  setEl('kpi-em-estres', `${formatPct(estresTot, n)} %`);
  setEl('kpi-em-mal-amb', `${formatPct(malAmb, n)} %`);
  setEl('kpi-em-pers-a', `${formatPct(persA, n)} %`);
  setEl('kpi-em-toxicos', `${formatPct(toxicos, n)} %`);

  // TAB 5: Antecedentes Familiares
  const famHta = filteredRecords.filter(r => r.ant_fam_hta).length;
  const famDm = filteredRecords.filter(r => r.ant_fam_dm).length;
  const famDlp = filteredRecords.filter(r => r.ant_fam_dlp).length;
  const famCvMayor = filteredRecords.filter(r => r.ant_fam_cv_mayor).length;
  const famCualquiera = filteredRecords.filter(r => r.ant_fam_cualquiera).length;
  setEl('kpi-fam-hta', `${formatPct(famHta, n)} %`);
  setEl('kpi-fam-dm', `${formatPct(famDm, n)} %`);
  setEl('kpi-fam-dlp', `${formatPct(famDlp, n)} %`);
  setEl('kpi-fam-cv-mayor', `${formatPct(famCvMayor, n)} %`);
  setEl('kpi-fam-total', `${formatPct(famCualquiera, n)} %`);

  // TAB 6: Historia No Cardiovascular
  const respCnt = filteredRecords.filter(r => r.respiratorio_desc && !r.respiratorio_desc.includes('Sin patología')).length;
  const mentalCnt = filteredRecords.filter(r => r.salud_mental_desc && !r.salud_mental_desc.includes('Sin trastorno')).length;
  const reumaCnt = filteredRecords.filter(r => r.enfermedad_reumatologica).length;
  const alergiasCnt = filteredRecords.filter(r => r.alergias_medicamentos).length;
  const cancerIrcCnt = filteredRecords.filter(r => r.cancer || r.insuficiencia_renal).length;
  setEl('kpi-nc-resp', `${formatPct(respCnt, n)} %`);
  setEl('kpi-nc-mental', `${formatPct(mentalCnt, n)} %`);
  setEl('kpi-nc-reuma', `${formatPct(reumaCnt, n)} %`);
  setEl('kpi-nc-alergias', `${formatPct(alergiasCnt, n)} %`);
  setEl('kpi-nc-cancer-irc', `${formatPct(cancerIrcCnt, n)} %`);

  // TAB 7: COVID-19 y Secuelas
  const covidInf = filteredRecords.filter(r => r.covid_infeccion).length;
  const covidHosp = filteredRecords.filter(r => r.covid_hospitalizacion).length;
  const covidSec = filteredRecords.filter(r => r.covid_tiene_secuelas).length;
  const covidFatiga = filteredRecords.filter(r => r.covid_fatiga_long).length;
  const covidRecup = covidInf > 0 ? (covidInf - covidSec) : 0;
  setEl('kpi-cov-infeccion', `${formatPct(covidInf, n)} %`);
  setEl('kpi-cov-hosp', `${formatPct(covidHosp, n)} %`);
  setEl('kpi-cov-secuelas', `${formatPct(covidSec, n)} %`);
  setEl('kpi-cov-fatiga', `${formatPct(covidFatiga, n)} %`);
  setEl('kpi-cov-recuperados', `${formatPct(covidRecup, covidInf || 1)} %`);

  // TAB 8: Electrocardiograma (ECG)
  const sinusalCnt = filteredRecords.filter(r => r.ecg_es_sinusal).length;
  const arritmiaCnt = filteredRecords.filter(r => r.ecg_arritmia).length;
  setEl('kpi-ecg-sinusal', `${formatPct(sinusalCnt, n)} %`);
  setEl('kpi-ecg-arritmia', `${formatPct(arritmiaCnt, n)} %`);
  setEl('kpi-ecg-pr', `${formatMean(filteredRecords.map(r => r.ecg_pr_ms), 0)} ms`);
  setEl('kpi-ecg-qrs', `${formatMean(filteredRecords.map(r => r.ecg_qrs_ms), 0)} ms`);
  setEl('kpi-ecg-qtc', `${formatMean(filteredRecords.map(r => r.ecg_qtc_ms), 0)} ms`);
}

// Despachador de renderizado por pestaña activa
function renderTabCharts(tabId) {
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
function renderTabResumenGeneral() {
  const n = filteredRecords.length;

  // 1. Tendencia Temporal por Año
  const yearCounts = {};
  filteredRecords.forEach(r => {
    yearCounts[r.ano] = (yearCounts[r.ano] || 0) + 1;
  });
  const years = Object.keys(yearCounts).sort();
  const yearData = years.map(y => yearCounts[y]);

  const elTendencia = document.getElementById('chart-tendencia-temporal');
  if (elTendencia) {
    if (charts.tendencia) {
      charts.tendencia.updateOptions({
        xaxis: { categories: years.map(y => `Año ${y}`) },
        series: [{ name: 'Evaluados', data: yearData }]
      });
    } else {
      charts.tendencia = new ApexCharts(elTendencia, {
        chart: { type: 'area', height: 260, toolbar: { show: false } },
        colors: [PALETTE.primaryBlue],
        stroke: { curve: 'smooth', width: 3 },
        fill: { type: 'gradient', gradient: { shadeIntensity: 1, opacityFrom: 0.45, opacityTo: 0.05 } },
        series: [{ name: 'Evaluados', data: yearData }],
        xaxis: { categories: years.map(y => `Año ${y}`) },
        dataLabels: {
          enabled: true,
          formatter: val => `${val} (${formatPct(val, filteredRecords.length)}%)`,
          style: { fontSize: '11px', fontWeight: 'bold', colors: ['#1B2A41'] },
          background: { enabled: true, foreColor: '#FFFFFF', borderRadius: 4, padding: 4, opacity: 0.95, borderWidth: 1, borderColor: '#0F172A' }
        },
        tooltip: apexCountTooltip()
      });
      charts.tendencia.render();
    }
  }

  // 2. Factores Modificables Globales (Barra horizontal)
  const htaPct = n > 0 ? (filteredRecords.filter(r => r.hipertension).length / n * 100) : 0;
  const dlPct = n > 0 ? (filteredRecords.filter(r => r.dislipemia).length / n * 100) : 0;
  const obPct = n > 0 ? (filteredRecords.filter(r => r.obesidad).length / n * 100) : 0;
  const dmPct = n > 0 ? (filteredRecords.filter(r => r.diabetes).length / n * 100) : 0;
  const tabPct = n > 0 ? (filteredRecords.filter(r => r.fumador_activo).length / n * 100) : 0;
  const sedPct = n > 0 ? (filteredRecords.filter(r => !r.actividad_fisica).length / n * 100) : 0;

  const fLabels = ['Hipertensión', 'Dislipemia', 'Obesidad', 'Diabetes', 'Tabaquismo', 'Sedentarismo'];
  const fData = [htaPct.toFixed(1), dlPct.toFixed(1), obPct.toFixed(1), dmPct.toFixed(1), tabPct.toFixed(1), sedPct.toFixed(1)];

  const elFactores = document.getElementById('chart-factores-modificables');
  if (elFactores) {
    if (charts.factores) {
      charts.factores.updateOptions({
        series: [{ name: 'Prevalencia (%)', data: fData }]
      });
    } else {
      charts.factores = new ApexCharts(elFactores, {
        chart: { type: 'bar', height: 260, toolbar: { show: false } },
        plotOptions: { bar: { horizontal: true, distributed: true, borderRadius: 4 } },
        colors: [PALETTE.emergencyRed, PALETTE.yellow, PALETTE.yellow, PALETTE.primaryBlue, PALETTE.green, PALETTE.purple],
        series: [{ name: 'Prevalencia (%)', data: fData }],
        xaxis: { categories: fLabels, max: 100 },
        legend: { show: false },
        dataLabels: {
          enabled: true,
          formatter: (val) => {
            const total = filteredRecords.length || 1;
            const casos = Math.round((parseFloat(val) * total) / 100);
            return `${casos} (${val}%)`;
          },
          style: { fontSize: '11px', fontWeight: 'bold', colors: ['#1B2A41'] },
          background: { enabled: true, foreColor: '#FFFFFF', borderRadius: 4, padding: 4, opacity: 0.95, borderWidth: 1, borderColor: '#0F172A' }
        },
        tooltip: apexPctTooltip()
      });
      charts.factores.render();
    }
  }

  // 3. Distribución por Categoría de Personal (Chart.js Donut con Leyenda Detallada)
  const catCounts = {};
  filteredRecords.forEach(r => { catCounts[r.categoria] = (catCounts[r.categoria] || 0) + 1; });
  const catLabels = Object.keys(catCounts);
  const catVals = catLabels.map(k => catCounts[k]);
  const catLegendLabels = catLabels.map(k => `${k}: ${catCounts[k]} (${formatPct(catCounts[k], n)}%)`);

  const ctxCat = document.getElementById('chart-categoria-personal');
  if (ctxCat) {
    if (charts.categoria) {
      charts.categoria.data.labels = catLegendLabels;
      charts.categoria.data.datasets[0].data = catVals;
      charts.categoria.update();
    } else {
      charts.categoria = new Chart(ctxCat, {
        type: 'doughnut',
        data: {
          labels: catLegendLabels,
          datasets: [{
            data: catVals,
            backgroundColor: [PALETTE.primaryBlue, PALETTE.yellow, PALETTE.green, PALETTE.purple, PALETTE.navy]
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'bottom' },
            datalabels: chartJsDonutDataLabels()
          }
        }
      });
    }
  }

  // 4. Género y Nivel de Riesgo (Chart.js Stacked Bar)
  const riesgos = ['Bajo (0 factores)', 'Moderado (1 factor)', 'Alto (2-3 factores)', 'Muy Alto (4+ factores)'];
  const hRiesgo = riesgos.map(rg => filteredRecords.filter(r => r.sexo === 'Hombre' && r.riesgo_global === rg).length);
  const mRiesgo = riesgos.map(rg => filteredRecords.filter(r => r.sexo === 'Mujer' && r.riesgo_global === rg).length);

  const ctxGen = document.getElementById('chart-genero-riesgo');
  if (ctxGen) {
    if (charts.genero) {
      charts.genero.data.datasets[0].data = hRiesgo;
      charts.genero.data.datasets[1].data = mRiesgo;
      charts.genero.update();
    } else {
      charts.genero = new Chart(ctxGen, {
        type: 'bar',
        data: {
          labels: ['Bajo (0)', 'Moderado (1)', 'Alto (2-3)', 'Muy Alto (4+)'],
          datasets: [
            { label: 'Hombres', data: hRiesgo, backgroundColor: PALETTE.primaryBlue },
            { label: 'Mujeres', data: mRiesgo, backgroundColor: PALETTE.purple }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: { top: 15, right: 8, bottom: 4, left: 4 } },
          scales: {
            x: { stacked: true },
            y: {
              stacked: true,
              beginAtZero: true,
              grace: '10%',
              title: { display: true, text: 'Casos (n)', font: { size: 11, weight: 'bold' } }
            }
          },
          plugins: {
            legend: { position: 'bottom' },
            datalabels: {
              display: (ctx) => ctx.dataset.data[ctx.dataIndex] > 0,
              color: '#FFFFFF',
              backgroundColor: '#1B2A41',
              borderRadius: 4,
              padding: { top: 2.5, bottom: 2.5, left: 5, right: 5 },
              borderWidth: 1,
              borderColor: '#0F172A',
              font: { weight: 'bold', size: 9.5 },
              clip: false,
              formatter: (val) => {
                if (!val || val <= 0) return '';
                const n = filteredRecords.length || 1;
                return `${val} (${formatPct(val, n)}%)`;
              }
            }
          }
        }
      });
    }
  }
}

// -------------------------------------------------------------
// TAB 1: DATOS DEL INDIVIDUO CHARTS
// -------------------------------------------------------------
function renderTabDatosIndividuo() {
  const n = filteredRecords.length;
  const grupos = ['<40 años', '40-49 años', '50-59 años', '60+ años'];
  const hEdad = grupos.map(g => filteredRecords.filter(r => r.sexo === 'Hombre' && r.grupo_edad === g).length);
  const mEdad = grupos.map(g => filteredRecords.filter(r => r.sexo === 'Mujer' && r.grupo_edad === g).length);

  const elPiramide = document.getElementById('chart-ind-edad-sexo');
  if (elPiramide) {
    if (charts.indEdad) {
      charts.indEdad.updateOptions({
        series: [
          { name: 'Hombres', data: hEdad },
          { name: 'Mujeres', data: mEdad }
        ],
        dataLabels: apexCountAndPctDataLabel()
      });
    } else {
      charts.indEdad = new ApexCharts(elPiramide, {
        chart: { type: 'bar', height: 260, toolbar: { show: false } },
        colors: [PALETTE.primaryBlue, PALETTE.purple],
        plotOptions: { bar: { horizontal: true, barHeight: '65%', borderRadius: 4 } },
        series: [
          { name: 'Hombres', data: hEdad },
          { name: 'Mujeres', data: mEdad }
        ],
        xaxis: { categories: grupos },
        legend: { position: 'top' },
        dataLabels: apexCountAndPctDataLabel(),
        tooltip: apexCountTooltip()
      });
      charts.indEdad.render();
    }
  }

  // Educación Donut
  const eduCounts = {};
  filteredRecords.forEach(r => { eduCounts[r.nivel_estudios] = (eduCounts[r.nivel_estudios] || 0) + 1; });
  const eduLabels = Object.keys(eduCounts);
  const eduVals = eduLabels.map(k => eduCounts[k]);
  const eduLegendLabels = eduLabels.map(k => `${k}: ${eduCounts[k]} (${formatPct(eduCounts[k], n)}%)`);

  const ctxEdu = document.getElementById('chart-ind-educacion');
  if (ctxEdu) {
    if (charts.indEdu) {
      charts.indEdu.data.labels = eduLegendLabels;
      charts.indEdu.data.datasets[0].data = eduVals;
      charts.indEdu.update();
    } else {
      charts.indEdu = new Chart(ctxEdu, {
        type: 'doughnut',
        data: {
          labels: eduLegendLabels,
          datasets: [{ data: eduVals, backgroundColor: [PALETTE.green, PALETTE.primaryBlue, PALETTE.yellow, PALETTE.navy] }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'bottom' },
            datalabels: chartJsDonutDataLabels()
          }
        }
      });
    }
  }

  // Estado Civil Bar
  const civCounts = {};
  filteredRecords.forEach(r => { civCounts[r.estado_civil] = (civCounts[r.estado_civil] || 0) + 1; });
  const civLabels = Object.keys(civCounts);
  const civVals = civLabels.map(k => civCounts[k]);

  const ctxCiv = document.getElementById('chart-ind-estado-civil');
  if (ctxCiv) {
    if (charts.indCiv) {
      charts.indCiv.data.labels = civLabels;
      charts.indCiv.data.datasets[0].data = civVals;
      charts.indCiv.update();
    } else {
      charts.indCiv = new Chart(ctxCiv, {
        type: 'bar',
        data: {
          labels: civLabels,
          datasets: [{ label: 'Personas', data: civVals, backgroundColor: PALETTE.teal, borderRadius: 6 }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: { top: 25, right: 8, bottom: 4, left: 4 } },
          scales: {
            y: {
              beginAtZero: true,
              grace: '20%',
              title: { display: true, text: 'Casos (n)', font: { size: 11, weight: 'bold' } }
            }
          },
          plugins: {
            legend: { display: false },
            datalabels: chartJsBarDataLabels()
          }
        }
      });
    }
  }

  // Régimen de Vivienda
  const vivCounts = {};
  filteredRecords.forEach(r => { vivCounts[r.tipo_vivienda] = (vivCounts[r.tipo_vivienda] || 0) + 1; });
  const vivLabels = Object.keys(vivCounts);
  const vivVals = vivLabels.map(k => vivCounts[k]);

  const elViv = document.getElementById('chart-ind-vivienda');
  if (elViv) {
    if (charts.indViv) {
      charts.indViv.updateOptions({
        xaxis: { categories: vivLabels },
        series: [{ name: 'Viviendas', data: vivVals }]
      });
    } else {
      charts.indViv = new ApexCharts(elViv, {
        chart: { type: 'bar', height: 260, toolbar: { show: false } },
        colors: [PALETTE.primaryBlue],
        plotOptions: { bar: { horizontal: true, borderRadius: 4 } },
        series: [{ name: 'Personas', data: vivVals }],
        xaxis: { categories: vivLabels },
        dataLabels: apexCountAndPctDataLabel(),
        tooltip: apexCountTooltip()
      });
      charts.indViv.render();
    }
  }
}

// -------------------------------------------------------------
// TAB 2: EXPLORACIÓN FÍSICA CHARTS
// -------------------------------------------------------------
function renderTabExploracionFisica() {
  const n = filteredRecords.length;
  const imcCats = ['Bajo peso', 'Normal', 'Sobrepeso', 'Obesidad I', 'Obesidad II', 'Obesidad Mórbida'];
  const imcCounts = imcCats.map(c => filteredRecords.filter(r => r.imc_cat === c).length);

  const elImc = document.getElementById('chart-exp-imc-cat');
  if (elImc) {
    if (charts.expImc) {
      charts.expImc.updateOptions({
        series: [{ name: 'Casos', data: imcCounts }]
      });
    } else {
      charts.expImc = new ApexCharts(elImc, {
        chart: { type: 'bar', height: 260, toolbar: { show: false } },
        colors: [PALETTE.iceBlue, PALETTE.green, PALETTE.yellow, PALETTE.emergencyRed, '#DC2626', '#991B1B'],
        plotOptions: { bar: { distributed: true, borderRadius: 5 } },
        series: [{ name: 'Casos', data: imcCounts }],
        xaxis: { categories: imcCats },
        legend: { show: false },
        dataLabels: apexCountAndPctDataLabel(),
        tooltip: apexCountTooltip()
      });
      charts.expImc.render();
    }
  }

  // Scatter IMC vs Perímetro Abdominal
  const scatterH = filteredRecords.filter(r => r.sexo === 'Hombre' && r.imc > 0 && r.perimetro_abdominal > 0)
    .map(r => ({ x: r.imc, y: r.perimetro_abdominal }));
  const scatterM = filteredRecords.filter(r => r.sexo === 'Mujer' && r.imc > 0 && r.perimetro_abdominal > 0)
    .map(r => ({ x: r.imc, y: r.perimetro_abdominal }));

  const ctxScatter = document.getElementById('chart-scatter-imc-cintura');
  if (ctxScatter) {
    if (charts.expScatter) {
      charts.expScatter.data.datasets[0].data = scatterH;
      charts.expScatter.data.datasets[1].data = scatterM;
      charts.expScatter.update();
    } else {
      charts.expScatter = new Chart(ctxScatter, {
        type: 'scatter',
        data: {
          datasets: [
            { label: 'Hombres', data: scatterH, backgroundColor: PALETTE.primaryBlue },
            { label: 'Mujeres', data: scatterM, backgroundColor: PALETTE.purple }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: { title: { display: true, text: 'IMC (kg/m²)' } },
            y: { title: { display: true, text: 'Perímetro Abdominal (cm)' } }
          },
          plugins: { datalabels: { display: false } }
        }
      });
    }
  }

  // Clasificación Presión Arterial (Pie con leyenda detallada)
  const paCats = ['PA Normal (<130/<80)', 'PA Elevada (130-139/80-89)', 'HTA Grado 1 (140-159/90-99)', 'HTA Grado 2 (≥140/90)'];
  const paVals = paCats.map(c => filteredRecords.filter(r => r.pa_categoria === c).length);
  const paLegendLabels = ['Normal', 'Elevada / Limítrofe', 'HTA Grado 1', 'HTA Grado 2'].map((lbl, idx) => `${lbl}: ${paVals[idx]} (${formatPct(paVals[idx], n)}%)`);

  const ctxPa = document.getElementById('chart-exp-pa-cat');
  if (ctxPa) {
    if (charts.expPa) {
      charts.expPa.data.labels = paLegendLabels;
      charts.expPa.data.datasets[0].data = paVals;
      charts.expPa.update();
    } else {
      charts.expPa = new Chart(ctxPa, {
        type: 'pie',
        data: {
          labels: paLegendLabels,
          datasets: [{ data: paVals, backgroundColor: [PALETTE.green, PALETTE.yellow, PALETTE.emergencyRed, '#991B1B'] }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'bottom' },
            datalabels: chartJsDonutDataLabels()
          }
        }
      });
    }
  }

  // Hallazgos Auscultación
  const auscNorm = filteredRecords.filter(r => r.ausc_pulm_normal && r.ausc_abdom_normal && !r.soplos).length;
  const soplosPres = filteredRecords.filter(r => r.soplos).length;
  const auscAlt = filteredRecords.filter(r => !r.ausc_pulm_normal || !r.ausc_abdom_normal).length;

  const elAusc = document.getElementById('chart-exp-auscultacion');
  if (elAusc) {
    if (charts.expAusc) {
      charts.expAusc.updateOptions({
        series: [{ name: 'Casos', data: [auscNorm, soplosPres, auscAlt] }]
      });
    } else {
      charts.expAusc = new ApexCharts(elAusc, {
        chart: { type: 'bar', height: 260, toolbar: { show: false } },
        colors: [PALETTE.green, PALETTE.yellow, PALETTE.emergencyRed],
        plotOptions: { bar: { distributed: true, borderRadius: 5 } },
        series: [{ name: 'Casos', data: [auscNorm, soplosPres, auscAlt] }],
        xaxis: { categories: ['Auscultación Normal', 'Soplos Cardíacos', 'Ruidos / Alteración'] },
        legend: { show: false },
        dataLabels: apexCountAndPctDataLabel(),
        tooltip: apexCountTooltip()
      });
      charts.expAusc.render();
    }
  }
}

// -------------------------------------------------------------
// TAB 3: FACTORES DE RIESGO MODIFICABLES CHARTS
// -------------------------------------------------------------
function renderTabFactoresModificables() {
  const n = filteredRecords.length;

  // Control Terapéutico
  const htaTto = filteredRecords.filter(r => r.hta_desc === 'Tratada').length;
  const htaNoTto = filteredRecords.filter(r => r.hta_desc === 'No tratada').length;
  const dmTto = filteredRecords.filter(r => r.db_desc.includes('tratada')).length;
  const dmNoTto = filteredRecords.filter(r => r.db_desc.includes('Diabetes') && !r.db_desc.includes('tratada')).length;
  const dlTto = filteredRecords.filter(r => r.dl_desc === 'Tratada').length;
  const dlNoTto = filteredRecords.filter(r => r.dl_desc === 'No tratada').length;

  const elControl = document.getElementById('chart-mod-control-tto');
  if (elControl) {
    if (charts.modControl) {
      charts.modControl.updateOptions({
        series: [
          { name: 'Bajo Tratamiento Farmacológico', data: [htaTto, dmTto, dlTto] },
          { name: 'Sin Tratamiento / Sin Control', data: [htaNoTto, dmNoTto, dlNoTto] }
        ]
      });
    } else {
      charts.modControl = new ApexCharts(elControl, {
        chart: { type: 'bar', height: 260, toolbar: { show: false } },
        colors: [PALETTE.green, PALETTE.emergencyRed],
        plotOptions: { bar: { horizontal: false, columnWidth: '55%', borderRadius: 4 } },
        series: [
          { name: 'Bajo Tratamiento Farmacológico', data: [htaTto, dmTto, dlTto] },
          { name: 'Sin Tratamiento / Sin Control', data: [htaNoTto, dmNoTto, dlNoTto] }
        ],
        xaxis: { categories: ['Hipertensión (HTA)', 'Diabetes Mellitus', 'Dislipemia'] },
        legend: { position: 'top' },
        dataLabels: apexCountAndPctDataLabel(),
        tooltip: apexCountTooltip()
      });
      charts.modControl.render();
    }
  }

  // Hábitos Tóxicos (Tabaquismo y Alcohol)
  const tabNo = filteredRecords.filter(r => r.tabaquismo === 'No fuma').length;
  const tabEx = filteredRecords.filter(r => r.tabaquismo === 'Exfumador').length;
  const tabAct = filteredRecords.filter(r => r.tabaquismo === 'Fumador Activo').length;

  const alcNo = filteredRecords.filter(r => r.alcohol === 'No consume').length;
  const alcOcas = filteredRecords.filter(r => r.alcohol === 'Ocasional').length;
  const alcReg = filteredRecords.filter(r => r.alcohol === 'Semanal' || r.alcohol === 'Diario').length;

  const toxCats = ['Sin Consumo / No Fuma', 'Consumo Ocasional / Ex', 'Consumo Activo / Regular'];

  const ctxTox = document.getElementById('chart-mod-toxicos');
  if (ctxTox) {
    if (charts.modTox) {
      charts.modTox.data.labels = toxCats;
      charts.modTox.data.datasets[0].data = [tabNo, tabEx, tabAct];
      charts.modTox.data.datasets[1].data = [alcNo, alcOcas, alcReg];
      charts.modTox.update();
    } else {
      charts.modTox = new Chart(ctxTox, {
        type: 'bar',
        data: {
          labels: toxCats,
          datasets: [
            { label: 'Tabaquismo', data: [tabNo, tabEx, tabAct], backgroundColor: PALETTE.emergencyRed, borderRadius: 5 },
            { label: 'Consumo de Alcohol', data: [alcNo, alcOcas, alcReg], backgroundColor: PALETTE.primaryBlue, borderRadius: 5 }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: true, position: 'top' },
            datalabels: chartJsBarDataLabels()
          }
        }
      });
    }
  }

  // Actividad Física por Categoría
  const catNames = [...new Set(filteredRecords.map(r => r.categoria))].filter(Boolean);
  const actSi = catNames.map(c => filteredRecords.filter(r => r.categoria === c && r.actividad_fisica).length);
  const actNo = catNames.map(c => filteredRecords.filter(r => r.categoria === c && !r.actividad_fisica).length);

  const elActCat = document.getElementById('chart-mod-actividad-cat');
  if (elActCat) {
    if (charts.modActCat) {
      charts.modActCat.updateOptions({
        xaxis: { categories: catNames },
        series: [
          { name: 'Activos Físicamente', data: actSi },
          { name: 'Sedentarios', data: actNo }
        ]
      });
    } else {
      charts.modActCat = new ApexCharts(elActCat, {
        chart: { type: 'bar', height: 260, toolbar: { show: false }, stacked: true },
        colors: [PALETTE.green, PALETTE.emergencyRed],
        plotOptions: { bar: { horizontal: false, borderRadius: 4 } },
        series: [
          { name: 'Activos Físicamente', data: actSi },
          { name: 'Sedentarios', data: actNo }
        ],
        xaxis: { categories: catNames },
        yaxis: { title: { text: 'Casos (n)' } },
        legend: { position: 'top' },
        dataLabels: apexCountAndPctDataLabel(),
        tooltip: apexCountTooltip()
      });
      charts.modActCat.render();
    }
  }

  // Dieta Mediterránea PREDIMED (Donut con leyenda detallada)
  const predimedAlta = filteredRecords.filter(r => r.predimed_adherencia === 'Buena Adherencia').length;
  const predimedBaja = filteredRecords.filter(r => r.predimed_adherencia !== 'Buena Adherencia').length;
  const predLegend = [
    `Buena Adherencia Mediterránea: ${predimedAlta} (${formatPct(predimedAlta, n)}%)`,
    `Adherencia Moderada / Baja: ${predimedBaja} (${formatPct(predimedBaja, n)}%)`
  ];

  const ctxPred = document.getElementById('chart-mod-predimed');
  if (ctxPred) {
    if (charts.modPred) {
      charts.modPred.data.labels = predLegend;
      charts.modPred.data.datasets[0].data = [predimedAlta, predimedBaja];
      charts.modPred.update();
    } else {
      charts.modPred = new Chart(ctxPred, {
        type: 'doughnut',
        data: {
          labels: predLegend,
          datasets: [{ data: [predimedAlta, predimedBaja], backgroundColor: [PALETTE.green, PALETTE.yellow] }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'bottom' },
            datalabels: chartJsDonutDataLabels()
          }
        }
      });
    }
  }
}

// -------------------------------------------------------------
// TAB 4: FACTORES EMERGENTES CHARTS
// -------------------------------------------------------------
function renderTabFactoresEmergentes() {
  const n = filteredRecords.length;
  const suenoBuena = filteredRecords.filter(r => r.calidad_sueno === 'Buena').length;
  const suenoMala = filteredRecords.filter(r => r.calidad_sueno === 'Mala').length;
  const suenoAdecuado = filteredRecords.filter(r => r.cantidad_sueno.includes('Adecuada')).length;
  const suenoInsuf = filteredRecords.filter(r => r.cantidad_sueno.includes('Insuficiente')).length;

  const elSueno = document.getElementById('chart-em-sueno');
  if (elSueno) {
    if (charts.emSueno) {
      charts.emSueno.updateOptions({
        series: [{ name: 'Casos', data: [suenoBuena, suenoMala, suenoAdecuado, suenoInsuf] }]
      });
    } else {
      charts.emSueno = new ApexCharts(elSueno, {
        chart: { type: 'bar', height: 260, toolbar: { show: false } },
        colors: [PALETTE.green, PALETTE.emergencyRed, PALETTE.primaryBlue, PALETTE.yellow],
        plotOptions: { bar: { distributed: true, borderRadius: 5 } },
        series: [{ name: 'Casos', data: [suenoBuena, suenoMala, suenoAdecuado, suenoInsuf] }],
        xaxis: { categories: ['Buena Calidad', 'Mala Calidad', 'Sueño Adecuado (7-8h)', 'Sueño Corto (<6h)'] },
        legend: { show: false },
        dataLabels: apexCountAndPctDataLabel(),
        tooltip: apexCountTooltip()
      });
      charts.emSueno.render();
    }
  }

  // Espectro de Estrés (Pie con leyenda detallada)
  const estLab = filteredRecords.filter(r => r.estres === 'Estrés Laboral').length;
  const estFam = filteredRecords.filter(r => r.estres === 'Estrés Familiar').length;
  const estAmbos = filteredRecords.filter(r => r.estres === 'Laboral y Familiar').length;
  const estSin = filteredRecords.filter(r => r.estres === 'Sin estrés significativo').length;

  const estLabels = [
    `Estrés Laboral: ${estLab} (${formatPct(estLab, n)}%)`,
    `Estrés Familiar: ${estFam} (${formatPct(estFam, n)}%)`,
    `Ambos Factores: ${estAmbos} (${formatPct(estAmbos, n)}%)`,
    `Sin Estrés Significativo: ${estSin} (${formatPct(estSin, n)}%)`
  ];

  const ctxEstres = document.getElementById('chart-em-estres');
  if (ctxEstres) {
    if (charts.emEstres) {
      charts.emEstres.data.labels = estLabels;
      charts.emEstres.data.datasets[0].data = [estLab, estFam, estAmbos, estSin];
      charts.emEstres.update();
    } else {
      charts.emEstres = new Chart(ctxEstres, {
        type: 'pie',
        data: {
          labels: estLabels,
          datasets: [{ data: [estLab, estFam, estAmbos, estSin], backgroundColor: [PALETTE.yellow, PALETTE.purple, PALETTE.emergencyRed, PALETTE.green] }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'bottom' },
            datalabels: chartJsDonutDataLabels()
          }
        }
      });
    }
  }

  // Personalidad Tipo A (Donut con leyenda detallada)
  const persSi = filteredRecords.filter(r => r.personalidad_tipo_a).length;
  const persNo = filteredRecords.filter(r => !r.personalidad_tipo_a).length;
  const persLabels = [
    `Con Personalidad Tipo A: ${persSi} (${formatPct(persSi, n)}%)`,
    `Sin Personalidad Tipo A: ${persNo} (${formatPct(persNo, n)}%)`
  ];

  const ctxPers = document.getElementById('chart-em-personalidad-a');
  if (ctxPers) {
    if (charts.emPers) {
      charts.emPers.data.labels = persLabels;
      charts.emPers.data.datasets[0].data = [persSi, persNo];
      charts.emPers.update();
    } else {
      charts.emPers = new Chart(ctxPers, {
        type: 'doughnut',
        data: {
          labels: persLabels,
          datasets: [{ data: [persSi, persNo], backgroundColor: [PALETTE.emergencyRed, PALETTE.teal] }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'bottom' },
            datalabels: chartJsDonutDataLabels()
          }
        }
      });
    }
  }

  // Factores Ginecológicos y Toxicidad
  const malAmb = filteredRecords.filter(r => r.mal_ambiente_laboral).length;
  const toxLab = filteredRecords.filter(r => r.toxicos_laboral).length;
  const estrogenos = filteredRecords.filter(r => r.bajos_estrogenos).length;
  const anticoncep = filteredRecords.filter(r => r.anticonceptivos_35).length;

  const elHorm = document.getElementById('chart-em-hormonas-ambiente');
  if (elHorm) {
    if (charts.emHorm) {
      charts.emHorm.updateOptions({
        series: [{ name: 'Casos', data: [malAmb, toxLab, estrogenos, anticoncep] }]
      });
    } else {
      charts.emHorm = new ApexCharts(elHorm, {
        chart: { type: 'bar', height: 260, toolbar: { show: false } },
        colors: [PALETTE.yellow, PALETTE.purple, PALETTE.emergencyRed, PALETTE.teal],
        plotOptions: { bar: { distributed: true, borderRadius: 5 } },
        series: [{ name: 'Casos', data: [malAmb, toxLab, estrogenos, anticoncep] }],
        xaxis: { categories: ['Mal Clima Laboral', 'Tóxicos Ocupacionales', 'Bajos Estrógenos / Menopausia', 'Anticonceptivos >35a'] },
        legend: { show: false },
        dataLabels: apexCountAndPctDataLabel(),
        tooltip: apexCountTooltip()
      });
      charts.emHorm.render();
    }
  }
}

// -------------------------------------------------------------
// TAB 5: ANTECEDENTES FAMILIARES CHARTS
// -------------------------------------------------------------
function renderTabAntecedentesFamiliares() {
  const n = filteredRecords.length;
  const padreHta = filteredRecords.filter(r => r.ant_padre_hta).length;
  const madreHta = filteredRecords.filter(r => r.ant_madre_hta).length;
  const padreDm = filteredRecords.filter(r => r.ant_padre_dm).length;
  const madreDm = filteredRecords.filter(r => r.ant_madre_dm).length;
  const padreDlp = filteredRecords.filter(r => r.ant_padre_dlp).length;
  const madreDlp = filteredRecords.filter(r => r.ant_madre_dlp).length;
  const padreIam = filteredRecords.filter(r => r.ant_padre_iam).length;
  const madreIam = filteredRecords.filter(r => r.ant_madre_iam).length;

  const elPadres = document.getElementById('chart-fam-padres-madres');
  if (elPadres) {
    if (charts.famPadres) {
      charts.famPadres.updateOptions({
        series: [
          { name: 'Rama Paterna', data: [padreHta, padreDm, padreDlp, padreIam] },
          { name: 'Rama Materna', data: [madreHta, madreDm, madreDlp, madreIam] }
        ],
        dataLabels: apexCountAndPctDataLabel()
      });
    } else {
      charts.famPadres = new ApexCharts(elPadres, {
        chart: { type: 'bar', height: 260, toolbar: { show: false } },
        colors: [PALETTE.primaryBlue, PALETTE.purple],
        plotOptions: { bar: { horizontal: true, barHeight: '65%', borderRadius: 4 } },
        series: [
          { name: 'Rama Paterna', data: [padreHta, padreDm, padreDlp, padreIam] },
          { name: 'Rama Materna', data: [madreHta, madreDm, madreDlp, madreIam] }
        ],
        xaxis: { categories: ['Hipertensión', 'Diabetes', 'Dislipemia', 'Infarto / Ictus'] },
        legend: { position: 'top' },
        dataLabels: apexCountAndPctDataLabel(),
        tooltip: apexCountTooltip()
      });
      charts.famPadres.render();
    }
  }

  // Agregación de Carga Familiar
  let c0 = 0, c1 = 0, c2 = 0, c3 = 0;
  filteredRecords.forEach(r => {
    let fCount = (r.ant_fam_hta ? 1 : 0) + (r.ant_fam_dm ? 1 : 0) + (r.ant_fam_dlp ? 1 : 0) + (r.ant_fam_cv_mayor ? 1 : 0);
    if (fCount === 0) c0++;
    else if (fCount === 1) c1++;
    else if (fCount === 2) c2++;
    else c3++;
  });

  const cargaLabels = [
    `Sin Antecedentes: ${c0} (${formatPct(c0, n)}%)`,
    `1 Antecedente: ${c1} (${formatPct(c1, n)}%)`,
    `2 Antecedentes: ${c2} (${formatPct(c2, n)}%)`,
    `≥3 Antecedentes: ${c3} (${formatPct(c3, n)}%)`
  ];

  const ctxCarga = document.getElementById('chart-fam-carga-global');
  if (ctxCarga) {
    if (charts.famCarga) {
      charts.famCarga.data.labels = cargaLabels;
      charts.famCarga.data.datasets[0].data = [c0, c1, c2, c3];
      charts.famCarga.update();
    } else {
      charts.famCarga = new Chart(ctxCarga, {
        type: 'doughnut',
        data: {
          labels: cargaLabels,
          datasets: [{ data: [c0, c1, c2, c3], backgroundColor: [PALETTE.green, PALETTE.teal, PALETTE.yellow, PALETTE.emergencyRed] }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'bottom' },
            datalabels: chartJsDonutDataLabels()
          }
        }
      });
    }
  }

  // Antecedentes por Grupo Etario
  const grupos = ['<40 años', '40-49 años', '50-59 años', '60+ años'];
  const htaPorEdad = grupos.map(g => filteredRecords.filter(r => r.grupo_edad === g && r.ant_fam_hta).length);
  const dmPorEdad = grupos.map(g => filteredRecords.filter(r => r.grupo_edad === g && r.ant_fam_dm).length);

  const elEdad = document.getElementById('chart-fam-por-edad');
  if (elEdad) {
    if (charts.famEdad) {
      charts.famEdad.updateOptions({
        series: [
          { name: 'HTA Familiar', data: htaPorEdad },
          { name: 'Diabetes Familiar', data: dmPorEdad }
        ]
      });
    } else {
      charts.famEdad = new ApexCharts(elEdad, {
        chart: { type: 'bar', height: 260, toolbar: { show: false } },
        colors: [PALETTE.emergencyRed, PALETTE.yellow],
        plotOptions: { bar: { horizontal: true, barHeight: '65%', borderRadius: 4 } },
        series: [
          { name: 'HTA Familiar', data: htaPorEdad },
          { name: 'Diabetes Familiar', data: dmPorEdad }
        ],
        xaxis: { categories: grupos },
        yaxis: { title: { text: 'Casos (n)' } },
        legend: { position: 'top' },
        dataLabels: apexCountAndPctDataLabel(),
        tooltip: apexCountTooltip()
      });
      charts.famEdad.render();
    }
  }

  // Coexistencia HTA y Diabetes
  const soloHta = filteredRecords.filter(r => r.ant_fam_hta && !r.ant_fam_dm).length;
  const soloDm = filteredRecords.filter(r => !r.ant_fam_hta && r.ant_fam_dm).length;
  const ambos = filteredRecords.filter(r => r.ant_fam_hta && r.ant_fam_dm).length;
  const ninguno = filteredRecords.filter(r => !r.ant_fam_hta && !r.ant_fam_dm).length;

  const ctxCoex = document.getElementById('chart-fam-coexistencia');
  if (ctxCoex) {
    if (charts.famCoex) {
      charts.famCoex.data.datasets[0].data = [soloHta, soloDm, ambos, ninguno];
      charts.famCoex.update();
    } else {
      charts.famCoex = new Chart(ctxCoex, {
        type: 'bar',
        data: {
          labels: ['Solo HTA Familiar', 'Solo Diabetes Familiar', 'Ambas Coexistentes', 'Sin Estos Antecedentes'],
          datasets: [{ label: 'Casos', data: [soloHta, soloDm, ambos, ninguno], backgroundColor: [PALETTE.emergencyRed, PALETTE.yellow, PALETTE.purple, PALETTE.green], borderRadius: 5 }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: { top: 25, right: 8, bottom: 4, left: 4 } },
          scales: {
            y: {
              beginAtZero: true,
              grace: '20%',
              title: { display: true, text: 'Casos (n)', font: { size: 10, weight: 'bold' } }
            }
          },
          plugins: {
            legend: { display: false },
            datalabels: chartJsBarDataLabels()
          }
        }
      });
    }
  }
}

// -------------------------------------------------------------
// TAB 6: HISTORIA NO CARDIOVASCULAR CHARTS
// -------------------------------------------------------------
function renderTabHistoriaNoCardio() {
  const n = filteredRecords.length;
  const respCnt = filteredRecords.filter(r => r.respiratorio_desc && !r.respiratorio_desc.includes('Sin patología')).length;
  const mentalCnt = filteredRecords.filter(r => r.salud_mental_desc && !r.salud_mental_desc.includes('Sin trastorno')).length;
  const reumaCnt = filteredRecords.filter(r => r.enfermedad_reumatologica).length;
  const alergiasCnt = filteredRecords.filter(r => r.alergias_medicamentos).length;
  const cancerCnt = filteredRecords.filter(r => r.cancer).length;
  const ircCnt = filteredRecords.filter(r => r.insuficiencia_renal).length;

  const labels = ['Respiratorio (Asma/EPOC)', 'Salud Mental (Ansiedad/Dep)', 'Alergias Medicamentosas', 'Reumatológica', 'Cáncer / Oncología', 'Insuficiencia Renal'];
  const vals = [respCnt, mentalCnt, alergiasCnt, reumaCnt, cancerCnt, ircCnt];

  const elComorb = document.getElementById('chart-nc-comorbilidades');
  if (elComorb) {
    if (charts.ncComorb) {
      charts.ncComorb.updateOptions({
        series: [{ name: 'Prevalencia Casos', data: vals }]
      });
    } else {
      charts.ncComorb = new ApexCharts(elComorb, {
        chart: { type: 'bar', height: 260, toolbar: { show: false } },
        plotOptions: { bar: { horizontal: true, distributed: true, borderRadius: 4 } },
        colors: [PALETTE.yellow, PALETTE.purple, PALETTE.teal, PALETTE.primaryBlue, PALETTE.emergencyRed, PALETTE.navy],
        series: [{ name: 'Prevalencia Casos', data: vals }],
        xaxis: { categories: labels },
        legend: { show: false },
        dataLabels: apexCountAndPctDataLabel(),
        tooltip: apexCountTooltip()
      });
      charts.ncComorb.render();
    }
  }

  // Salud Mental Donut (con cantidades y porcentajes explícitos en leyenda)
  const ansSolo = filteredRecords.filter(r => r.salud_mental_desc === 'Ansiedad').length;
  const depSolo = filteredRecords.filter(r => r.salud_mental_desc === 'Depresión').length;
  const ambMental = filteredRecords.filter(r => r.salud_mental_desc.includes('Ansiedad y Depresión')).length;
  const sinMental = filteredRecords.filter(r => r.salud_mental_desc.includes('Sin trastorno')).length;

  const mentalLegend = [
    `Solo Ansiedad: ${ansSolo} (${formatPct(ansSolo, n)}%)`,
    `Solo Depresión: ${depSolo} (${formatPct(depSolo, n)}%)`,
    `Ansiedad y Depresión: ${ambMental} (${formatPct(ambMental, n)}%)`,
    `Sin Trastorno: ${sinMental} (${formatPct(sinMental, n)}%)`
  ];

  const ctxMental = document.getElementById('chart-nc-salud-mental');
  if (ctxMental) {
    if (charts.ncMental) {
      charts.ncMental.data.labels = mentalLegend;
      charts.ncMental.data.datasets[0].data = [ansSolo, depSolo, ambMental, sinMental];
      charts.ncMental.update();
    } else {
      charts.ncMental = new Chart(ctxMental, {
        type: 'doughnut',
        data: {
          labels: mentalLegend,
          datasets: [{ data: [ansSolo, depSolo, ambMental, sinMental], backgroundColor: [PALETTE.yellow, PALETTE.purple, PALETTE.emergencyRed, PALETTE.green] }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'bottom' },
            datalabels: chartJsDonutDataLabels()
          }
        }
      });
    }
  }

  // Respiratorio Bar
  const asmaCnt = filteredRecords.filter(r => r.asma).length;
  const epocCnt = filteredRecords.filter(r => r.epoc).length;
  const sinResp = filteredRecords.filter(r => !r.asma && !r.epoc).length;

  const ctxResp = document.getElementById('chart-nc-respiratorio');
  if (ctxResp) {
    if (charts.ncResp) {
      charts.ncResp.data.datasets[0].data = [asmaCnt, epocCnt, sinResp];
      charts.ncResp.update();
    } else {
      charts.ncResp = new Chart(ctxResp, {
        type: 'bar',
        data: {
          labels: ['Asma Bronquial', 'EPOC', 'Sin Patología Respiratoria'],
          datasets: [{ label: 'Casos', data: [asmaCnt, epocCnt, sinResp], backgroundColor: [PALETTE.yellow, PALETTE.emergencyRed, PALETTE.green], borderRadius: 5 }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: { top: 25, right: 8, bottom: 4, left: 4 } },
          scales: {
            y: {
              beginAtZero: true,
              grace: '20%',
              title: { display: true, text: 'Casos (n)', font: { size: 10, weight: 'bold' } }
            }
          },
          plugins: {
            legend: { display: false },
            datalabels: chartJsBarDataLabels()
          }
        }
      });
    }
  }

  // Reumatología vs Alergias
  const elReuma = document.getElementById('chart-nc-reuma-alergia');
  if (elReuma) {
    if (charts.ncReuma) {
      charts.ncReuma.updateOptions({
        series: [{ name: 'Casos', data: [reumaCnt, alergiasCnt] }]
      });
    } else {
      charts.ncReuma = new ApexCharts(elReuma, {
        chart: { type: 'bar', height: 260, toolbar: { show: false } },
        colors: [PALETTE.purple, PALETTE.teal],
        plotOptions: { bar: { distributed: true, borderRadius: 5 } },
        series: [{ name: 'Casos', data: [reumaCnt, alergiasCnt] }],
        xaxis: { categories: ['Patología Reumatológica / Artritis', 'Alergias Medicamentosas'] },
        legend: { show: false },
        dataLabels: apexCountAndPctDataLabel(),
        tooltip: apexCountTooltip()
      });
      charts.ncReuma.render();
    }
  }
}

// -------------------------------------------------------------
// TAB 7: COVID-19 Y SECUELAS CHARTS
// -------------------------------------------------------------
function renderTabCovid19() {
  const n = filteredRecords.length;
  const sinHosp = filteredRecords.filter(r => r.covid_infeccion && !r.covid_hospitalizacion).length;
  const conHosp = filteredRecords.filter(r => r.covid_hospitalizacion).length;
  const noCovid = filteredRecords.filter(r => !r.covid_infeccion).length;

  const elHist = document.getElementById('chart-cov-historia');
  if (elHist) {
    if (charts.covHist) {
      charts.covHist.updateOptions({
        series: [{ name: 'Casos', data: [sinHosp, conHosp, noCovid] }]
      });
    } else {
      charts.covHist = new ApexCharts(elHist, {
        chart: { type: 'bar', height: 260, toolbar: { show: false } },
        colors: [PALETTE.yellow, PALETTE.emergencyRed, PALETTE.green],
        plotOptions: { bar: { distributed: true, borderRadius: 5 } },
        series: [{ name: 'Casos', data: [sinHosp, conHosp, noCovid] }],
        xaxis: { categories: ['Infección Leve (Sin Hospitalización)', 'Requirió Hospitalización', 'No ha presentado COVID'] },
        legend: { show: false },
        dataLabels: apexCountAndPctDataLabel(),
        tooltip: apexCountTooltip()
      });
      charts.covHist.render();
    }
  }

  // Espectro de Secuelas
  const secCardio = filteredRecords.filter(r => r.covid_secuelas_cardio).length;
  const secResp = filteredRecords.filter(r => r.covid_secuelas_resp).length;
  const secFatiga = filteredRecords.filter(r => r.covid_fatiga_long).length;
  const secNiebla = filteredRecords.filter(r => r.covid_niebla_mental).length;
  const sinSecuelas = filteredRecords.filter(r => r.covid_infeccion && !r.covid_tiene_secuelas).length;

  const ctxSec = document.getElementById('chart-cov-secuelas');
  if (ctxSec) {
    if (charts.covSec) {
      charts.covSec.data.datasets[0].data = [secCardio, secResp, secFatiga, secNiebla, sinSecuelas];
      charts.covSec.update();
    } else {
      charts.covSec = new Chart(ctxSec, {
        type: 'bar',
        data: {
          labels: ['Secuelas Cardiovasculares', 'Secuelas Respiratorias', 'Fatiga Crónica / Long-COVID', 'Niebla Mental', 'Recuperación Asintomática'],
          datasets: [{ label: 'Casos', data: [secCardio, secResp, secFatiga, secNiebla, sinSecuelas], backgroundColor: [PALETTE.emergencyRed, PALETTE.yellow, PALETTE.purple, PALETTE.teal, PALETTE.green], borderRadius: 5 }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: { top: 25, right: 8, bottom: 4, left: 4 } },
          scales: {
            y: {
              beginAtZero: true,
              grace: '20%',
              title: { display: true, text: 'Casos (n)', font: { size: 10, weight: 'bold' } }
            }
          },
          plugins: {
            legend: { display: false },
            datalabels: chartJsBarDataLabels()
          }
        }
      });
    }
  }

  // Infección por Categoría de Personal
  const catNames = [...new Set(filteredRecords.map(r => r.categoria))].filter(Boolean);
  const covPorCat = catNames.map(c => filteredRecords.filter(r => r.categoria === c && r.covid_infeccion).length);
  const hospPorCat = catNames.map(c => filteredRecords.filter(r => r.categoria === c && r.covid_hospitalizacion).length);

  const elPorCat = document.getElementById('chart-cov-por-categoria');
  if (elPorCat) {
    if (charts.covCat) {
      charts.covCat.updateOptions({
        xaxis: { categories: catNames },
        series: [
          { name: 'Infectados COVID', data: covPorCat },
          { name: 'Hospitalizados', data: hospPorCat }
        ]
      });
    } else {
      charts.covCat = new ApexCharts(elPorCat, {
        chart: { type: 'bar', height: 260, toolbar: { show: false } },
        colors: [PALETTE.primaryBlue, PALETTE.emergencyRed],
        plotOptions: { bar: { horizontal: true, barHeight: '65%', borderRadius: 4 } },
        series: [
          { name: 'Infectados COVID', data: covPorCat },
          { name: 'Hospitalizados', data: hospPorCat }
        ],
        xaxis: { categories: catNames },
        yaxis: { title: { text: 'Casos (n)' } },
        legend: { position: 'top' },
        dataLabels: apexCountAndPctDataLabel(),
        tooltip: apexCountTooltip()
      });
      charts.covCat.render();
    }
  }

  // Prevalencia por Sexo (Donut con cantidades y porcentajes)
  const covH = filteredRecords.filter(r => r.sexo === 'Hombre' && r.covid_infeccion).length;
  const covM = filteredRecords.filter(r => r.sexo === 'Mujer' && r.covid_infeccion).length;
  const covTotal = covH + covM;
  const covGenderLegend = [
    `Hombres Infectados: ${covH} (${formatPct(covH, covTotal || 1)}%)`,
    `Mujeres Infectadas: ${covM} (${formatPct(covM, covTotal || 1)}%)`
  ];

  const ctxGen = document.getElementById('chart-cov-por-genero');
  if (ctxGen) {
    if (charts.covGen) {
      charts.covGen.data.labels = covGenderLegend;
      charts.covGen.data.datasets[0].data = [covH, covM];
      charts.covGen.update();
    } else {
      charts.covGen = new Chart(ctxGen, {
        type: 'doughnut',
        data: {
          labels: covGenderLegend,
          datasets: [{ data: [covH, covM], backgroundColor: [PALETTE.primaryBlue, PALETTE.purple] }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'bottom' },
            datalabels: chartJsDonutDataLabels()
          }
        }
      });
    }
  }
}

// -------------------------------------------------------------
// TAB 8: RESULTADOS DEL ELECTROCARDIOGRAMA CHARTS
// -------------------------------------------------------------
function renderTabElectrocardiograma() {
  const n = filteredRecords.length;
  const sinusalCnt = filteredRecords.filter(r => r.ecg_es_sinusal).length;
  const arritmiaCnt = filteredRecords.filter(r => r.ecg_arritmia).length;

  const elRitmo = document.getElementById('chart-ecg-ritmo');
  if (elRitmo) {
    if (charts.ecgRitmo) {
      charts.ecgRitmo.updateOptions({
        series: [sinusalCnt, arritmiaCnt]
      });
    } else {
      charts.ecgRitmo = new ApexCharts(elRitmo, {
        chart: { type: 'donut', height: 260 },
        colors: [PALETTE.green, PALETTE.emergencyRed],
        labels: ['Ritmo Sinusal (Normal)', 'Arritmias / Otros Ritmos'],
        series: [sinusalCnt, arritmiaCnt],
        legend: { position: 'bottom' },
        dataLabels: {
          enabled: true,
          formatter: (val, opt) => {
            const cnt = opt.seriesIndex === 0 ? sinusalCnt : arritmiaCnt;
            return `${cnt} (${val.toFixed(1)}%)`;
          },
          style: { fontSize: '11px', fontWeight: 'bold', colors: ['#1B2A41'] },
          background: {
            enabled: true,
            foreColor: '#FFFFFF',
            borderRadius: 4,
            padding: 4,
            opacity: 0.95,
            borderWidth: 1,
            borderColor: '#0F172A'
          }
        },
        tooltip: apexCountTooltip()
      });
      charts.ecgRitmo.render();
    }
  }

  // Intervalos de Conducción
  const prNorm = filteredRecords.filter(r => r.ecg_pr_cat.includes('Normal')).length;
  const prBloq = filteredRecords.filter(r => r.ecg_pr_cat.includes('Bloqueo')).length;
  const qrsNorm = filteredRecords.filter(r => r.ecg_qrs_cat.includes('Normal')).length;
  const qrsBloq = filteredRecords.filter(r => r.ecg_qrs_cat.includes('Bloqueo') || r.ecg_qrs_cat.includes('Incompleto')).length;
  const qtcNorm = filteredRecords.filter(r => r.ecg_qtc_cat.includes('Normal')).length;
  const qtcProl = filteredRecords.filter(r => r.ecg_qtc_cat.includes('Prolongado')).length;

  const ctxInterv = document.getElementById('chart-ecg-intervalos');
  if (ctxInterv) {
    if (charts.ecgInterv) {
      charts.ecgInterv.data.datasets[0].data = [prNorm, qrsNorm, qtcNorm];
      charts.ecgInterv.data.datasets[1].data = [prBloq, qrsBloq, qtcProl];
      charts.ecgInterv.update();
    } else {
      charts.ecgInterv = new Chart(ctxInterv, {
        type: 'bar',
        data: {
          labels: ['Intervalo PR', 'Duración QRS', 'Intervalo QTc Bazett'],
          datasets: [
            { label: 'Dentro de Límites Normales', data: [prNorm, qrsNorm, qtcNorm], backgroundColor: PALETTE.green },
            { label: 'Prolongado / Bloqueo Conducción', data: [prBloq, qrsBloq, qtcProl], backgroundColor: PALETTE.emergencyRed }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: { top: 15, right: 8, bottom: 4, left: 4 } },
          scales: {
            x: { stacked: true },
            y: {
              stacked: true,
              beginAtZero: true,
              grace: '10%',
              title: { display: true, text: 'Casos (n)', font: { size: 11, weight: 'bold' } }
            }
          },
          plugins: {
            legend: { position: 'bottom' },
            datalabels: {
              display: (ctx) => ctx.dataset.data[ctx.dataIndex] > 0,
              color: '#FFFFFF',
              backgroundColor: '#1B2A41',
              borderRadius: 4,
              padding: { top: 2.5, bottom: 2.5, left: 5, right: 5 },
              borderWidth: 1,
              borderColor: '#0F172A',
              font: { weight: 'bold', size: 9.5 },
              clip: false,
              formatter: (val) => {
                if (!val || val <= 0) return '';
                const n = filteredRecords.length || 1;
                return `${val} (${formatPct(val, n)}%)`;
              }
            }
          }
        }
      });
    }
  }

  // Anomalías de Conducción y Morfología
  const hviCnt = filteredRecords.filter(r => r.ecg_hvi).length;
  const brCnt = filteredRecords.filter(r => r.ecg_bloqueo_rama && r.ecg_bloqueo_rama !== 'Sin bloqueo' && r.ecg_bloqueo_rama.toUpperCase() !== 'NINGUNA').length;
  const repolCnt = filteredRecords.filter(r => r.ecg_repolarizacion).length;
  const sinAnom = filteredRecords.filter(r => !r.ecg_hvi && (!r.ecg_bloqueo_rama || r.ecg_bloqueo_rama === 'Sin bloqueo' || r.ecg_bloqueo_rama.toUpperCase() === 'NINGUNA') && !r.ecg_repolarizacion).length;

  const elAnom = document.getElementById('chart-ecg-anomalias');
  if (elAnom) {
    if (charts.ecgAnom) {
      charts.ecgAnom.updateOptions({
        series: [{ name: 'Casos', data: [sinAnom, brCnt, hviCnt, repolCnt] }]
      });
    } else {
      charts.ecgAnom = new ApexCharts(elAnom, {
        chart: { type: 'bar', height: 260, toolbar: { show: false } },
        colors: [PALETTE.green, PALETTE.yellow, PALETTE.emergencyRed, PALETTE.purple],
        plotOptions: { bar: { distributed: true, borderRadius: 5 } },
        series: [{ name: 'Casos', data: [sinAnom, brCnt, hviCnt, repolCnt] }],
        xaxis: { categories: ['ECG Morfológicamente Normal', 'Bloqueo de Rama', 'Hipertrofia Ventricular (HVI)', 'Alteraciones Repolarización'] },
        legend: { show: false },
        dataLabels: apexCountAndPctDataLabel(),
        tooltip: apexCountTooltip()
      });
      charts.ecgAnom.render();
    }
  }

  // Frecuencia Cardíaca ECG vs Frecuencia Clínica
  const fcEcgMedia = parseFloat(formatMean(filteredRecords.map(r => r.ecg_fc), 0)) || 0;
  const fcClinicaMedia = parseFloat(formatMean(filteredRecords.map(r => r.fc), 0)) || 0;

  const ctxFc = document.getElementById('chart-ecg-fc-comparativa');
  if (ctxFc) {
    if (charts.ecgFc) {
      charts.ecgFc.data.datasets[0].data = [fcEcgMedia, fcClinicaMedia];
      charts.ecgFc.update();
    } else {
      charts.ecgFc = new Chart(ctxFc, {
        type: 'bar',
        data: {
          labels: ['FC por Trazado ECG', 'FC por Auscultación / Pulso'],
          datasets: [{ label: 'Latidos por Minuto (lpm)', data: [fcEcgMedia, fcClinicaMedia], backgroundColor: [PALETTE.primaryBlue, PALETTE.teal], borderRadius: 6 }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: { y: { min: 40, max: 120, title: { display: true, text: 'Frecuencia Cardíaca (lpm)' } } },
          plugins: {
            legend: { display: false },
            datalabels: {
              display: true,
              anchor: 'end',
              align: 'top',
              color: '#1B2A41',
              font: { weight: 'bold', size: 11 },
              color: '#FFFFFF',
              backgroundColor: '#1B2A41',
              borderRadius: 4,
              padding: { top: 3, bottom: 3, left: 6, right: 6 },
              borderWidth: 1,
              borderColor: '#0F172A',
              clip: false,
              formatter: (val) => `${val} lpm`
            }
          }
        }
      });
    }
  }
}

// =============================================================
// MÓDULO DE EXPORTACIÓN (PDF, POWERPOINT, IMAGEN)
// =============================================================
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
  }
}

function closeExportModal() {
  const modal = document.getElementById('modal-export-dashboard');
  if (modal) modal.style.display = 'none';
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

  if (btn) btn.disabled = true;
  if (progBox) progBox.style.display = 'flex';

  const setProgress = (text, pct) => {
    if (progText) progText.textContent = text;
    if (progBar) progBar.style.width = `${pct}%`;
  };

  try {
    if (format === 'image') {
      await exportImage(scope, setProgress);
    } else if (format === 'pptx') {
      await exportPowerPoint(scope, setProgress);
    } else {
      await exportPdf(scope, setProgress);
    }
    setTimeout(() => {
      closeExportModal();
    }, 700);
  } catch (err) {
    console.error('Error durante la exportación:', err);
    alert('Ocurrió un inconveniente al generar la exportación: ' + (err.message || err));
  } finally {
    if (btn) btn.disabled = false;
    if (progBox) progBox.style.display = 'none';
  }
}

// 1. Exportación a Imagen PNG
async function exportImage(scope, setProgress) {
  if (typeof html2canvas === 'undefined') {
    throw new Error('La librería html2canvas no está disponible.');
  }

  const tabsToExport = scope === 'all' ? DASHBOARD_TABS : [DASHBOARD_TABS.find(t => t.id === activeTabId) || DASHBOARD_TABS[0]];
  const total = tabsToExport.length;
  const originalTab = activeTabId;

  for (let i = 0; i < total; i++) {
    const tab = tabsToExport[i];
    setProgress(`Capturando imagen: ${tab.title} (${i + 1}/${total})...`, Math.round(((i + 0.5) / total) * 100));

    switchTab(tab.id, document.querySelector(`.nav-item[onclick*="${tab.id}"]`));
    await new Promise(r => setTimeout(r, 250));

    const targetEl = document.getElementById('tab-' + tab.id);
    if (!targetEl) continue;

    const canvas = await html2canvas(targetEl, {
      scale: 2,
      useCORS: true,
      backgroundColor: '#F8FAFC',
      logging: false
    });

    const link = document.createElement('a');
    const safeTitle = tab.title.toLowerCase().replace(/[^a-z0-9]/g, '_');
    link.download = `CardioUNEMI_${safeTitle}_${new Date().toISOString().slice(0, 10)}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
    await new Promise(r => setTimeout(r, 200));
  }

  switchTab(originalTab, document.querySelector(`.nav-item[onclick*="${originalTab}"]`));
  setProgress('¡Imágenes descargadas con éxito!', 100);
}

// 2. Exportación a Documento PDF Paginado
async function exportPdf(scope, setProgress) {
  const { jsPDF } = window.jspdf || window;
  if (!jsPDF) {
    throw new Error('La librería jsPDF no está disponible.');
  }
  if (typeof html2canvas === 'undefined') {
    throw new Error('La librería html2canvas no está disponible.');
  }

  const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
  const tabsToExport = scope === 'all' ? DASHBOARD_TABS : [DASHBOARD_TABS.find(t => t.id === activeTabId) || DASHBOARD_TABS[0]];
  const total = tabsToExport.length;
  const originalTab = activeTabId;

  const pageWidth = 297;
  const pageHeight = 210;
  const marginX = 10;
  const contentWidth = pageWidth - (marginX * 2);

  const instVal = document.getElementById('slicer-inst')?.value || 'Todas las Instituciones';
  const anoVal = document.getElementById('slicer-ano')?.value || 'Todos los Años';
  const sampleText = `${filteredRecords.length} de ${allRecords.length} evaluados`;
  const todayStr = new Date().toLocaleDateString('es-EC', { year: 'numeric', month: 'long', day: 'numeric' });

  for (let i = 0; i < total; i++) {
    const tab = tabsToExport[i];
    setProgress(`Generando página PDF: ${tab.title} (${i + 1}/${total})...`, Math.round(((i + 0.3) / total) * 100));

    switchTab(tab.id, document.querySelector(`.nav-item[onclick*="${tab.id}"]`));
    await new Promise(r => setTimeout(r, 250));

    const targetEl = document.getElementById('tab-' + tab.id);
    if (!targetEl) continue;

    const canvas = await html2canvas(targetEl, {
      scale: 1.8,
      useCORS: true,
      backgroundColor: '#FFFFFF',
      logging: false
    });

    const imgData = canvas.toDataURL('image/jpeg', 0.92);

    if (i > 0) {
      doc.addPage();
    }

    // Cabecera Institucional
    doc.setFillColor(27, 42, 65); // #1B2A41 Navy
    doc.rect(0, 0, pageWidth, 15, 'F');

    doc.setTextColor(255, 255, 255);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(10.5);
    doc.text('CARDIOUNEMI • VIGILANCIA EPIDEMIOLÓGICA CARDIOVASCULAR', marginX, 9.5);

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8);
    doc.text(`Cohorte: ${sampleText} | ${instVal} - Año ${anoVal} | ${todayStr}`, pageWidth - marginX, 9.5, { align: 'right' });

    // Título de la Sección
    doc.setTextColor(27, 42, 65);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(12);
    doc.text(tab.title, marginX, 23);

    // Renderizado del contenido visual
    const imgAspect = canvas.height / canvas.width;
    const maxImgHeight = pageHeight - 34;
    let renderW = contentWidth;
    let renderH = renderW * imgAspect;
    if (renderH > maxImgHeight) {
      renderH = maxImgHeight;
      renderW = renderH / imgAspect;
    }
    const renderX = marginX + (contentWidth - renderW) / 2;

    doc.addImage(imgData, 'JPEG', renderX, 26, renderW, renderH, undefined, 'FAST');

    // Pie de página
    doc.setTextColor(148, 163, 184);
    doc.setFontSize(7.5);
    doc.text('Universidad Estatal de Milagro (UNEMI) • Departamento de Cardiología', marginX, pageHeight - 4);
    doc.text(`Página ${i + 1} de ${total}`, pageWidth - marginX, pageHeight - 4, { align: 'right' });
  }

  switchTab(originalTab, document.querySelector(`.nav-item[onclick*="${originalTab}"]`));

  setProgress('Guardando documento PDF...', 95);
  const fileName = scope === 'all'
    ? `CardioUNEMI_Reporte_Integral_8_Bloques_${new Date().toISOString().slice(0, 10)}.pdf`
    : `CardioUNEMI_${activeTabId}_${new Date().toISOString().slice(0, 10)}.pdf`;

  doc.save(fileName);
  setProgress('¡PDF generado exitosamente!', 100);
}

// 3. Exportación a Diapositivas PowerPoint (.pptx)
async function exportPowerPoint(scope, setProgress) {
  if (typeof PptxGenJS === 'undefined') {
    throw new Error('La librería PptxGenJS no está disponible.');
  }
  if (typeof html2canvas === 'undefined') {
    throw new Error('La librería html2canvas no está disponible.');
  }

  const pptx = new PptxGenJS();
  pptx.layout = 'LAYOUT_16x9';

  const tabsToExport = scope === 'all' ? DASHBOARD_TABS : [DASHBOARD_TABS.find(t => t.id === activeTabId) || DASHBOARD_TABS[0]];
  const total = tabsToExport.length;
  const originalTab = activeTabId;

  const instVal = document.getElementById('slicer-inst')?.value || 'Todas las Instituciones';
  const anoVal = document.getElementById('slicer-ano')?.value || 'Todos los Años';
  const sampleText = `${filteredRecords.length} de ${allRecords.length} evaluados (100%)`;
  const todayStr = new Date().toLocaleDateString('es-EC', { year: 'numeric', month: 'long', day: 'numeric' });

  // Slide 1: Portada Ejecutiva
  setProgress('Construyendo portada institucional...', 10);
  const slidePortada = pptx.addSlide();
  slidePortada.background = { color: '1B2A41' }; // Navy UNEMI

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
    x: 0.8, y: 3.3, w: 8.4, h: 1.6,
    fill: { color: '142132' },
    line: { color: '3AA0FF', width: 1.5 }
  });

  slidePortada.addText([
    { text: 'Muestra Total Analizada: ', options: { bold: true, color: '3AA0FF' } },
    { text: `${sampleText}\n`, options: { color: 'FFFFFF' } },
    { text: 'Institución / Cohorte: ', options: { bold: true, color: '3AA0FF' } },
    { text: `${instVal} (Año: ${anoVal})\n`, options: { color: 'FFFFFF' } },
    { text: 'Fecha de Emisión: ', options: { bold: true, color: '3AA0FF' } },
    { text: `${todayStr}\n`, options: { color: 'FFFFFF' } },
    { text: 'Alcance del Reporte: ', options: { bold: true, color: '3AA0FF' } },
    { text: scope === 'all' ? 'Informe Integral Completo (8 Bloques Clínicos)' : `Módulo Específico: ${tabsToExport[0].title}`, options: { color: 'FFFFFF' } }
  ], {
    x: 1.05, y: 3.45, w: 7.9, h: 1.3,
    fontSize: 11
  });

  // Slide 2..N: Slides por cada Módulo Clínico
  for (let i = 0; i < total; i++) {
    const tab = tabsToExport[i];
    setProgress(`Generando diapositiva: ${tab.title} (${i + 1}/${total})...`, Math.round(15 + ((i + 1) / total) * 75));

    switchTab(tab.id, document.querySelector(`.nav-item[onclick*="${tab.id}"]`));
    await new Promise(r => setTimeout(r, 250));

    const targetEl = document.getElementById('tab-' + tab.id);
    if (!targetEl) continue;

    const canvas = await html2canvas(targetEl, {
      scale: 1.8,
      useCORS: true,
      backgroundColor: '#FFFFFF',
      logging: false
    });

    const imgData = canvas.toDataURL('image/png');

    const slide = pptx.addSlide();
    slide.background = { color: 'F8FAFC' };

    // Barra Superior
    slide.addShape(pptx.ShapeType.rect, {
      x: 0, y: 0, w: 10, h: 0.65,
      fill: { color: '1B2A41' }
    });

    slide.addText(`CARDIOUNEMI • ${tab.title.toUpperCase()}`, {
      x: 0.5, y: 0.12, w: 7.0, h: 0.4,
      fontSize: 12.5, color: 'FFFFFF', bold: true
    });

    slide.addText(`${todayStr} | N = ${filteredRecords.length}`, {
      x: 7.5, y: 0.14, w: 2.0, h: 0.35,
      fontSize: 9, color: 'CFE9FF', align: 'right'
    });

    // Imagen del Panel de Gráficos
    const imgAspect = canvas.height / canvas.width;
    const maxW = 9.2;
    const maxH = 4.65;
    let w = maxW;
    let h = w * imgAspect;
    if (h > maxH) {
      h = maxH;
      w = h / imgAspect;
    }
    const x = 0.4 + (maxW - w) / 2;
    const y = 0.78 + (maxH - h) / 2;

    slide.addImage({ data: imgData, x: x, y: y, w: w, h: h });

    // Pie de diapositiva
    slide.addText('Universidad Estatal de Milagro • Departamento de Cardiología', {
      x: 0.5, y: 5.35, w: 6.0, h: 0.25,
      fontSize: 8, color: '94A3B8'
    });
    slide.addText(`Diapositiva ${i + 2} de ${total + 1}`, {
      x: 7.5, y: 5.35, w: 2.0, h: 0.25,
      fontSize: 8, color: '94A3B8', align: 'right'
    });
  }

  switchTab(originalTab, document.querySelector(`.nav-item[onclick*="${originalTab}"]`));

  setProgress('Compilando presentación PowerPoint (.pptx)...', 95);
  const fileName = scope === 'all'
    ? `CardioUNEMI_Presentacion_Completa_${new Date().toISOString().slice(0, 10)}.pptx`
    : `CardioUNEMI_${activeTabId}_${new Date().toISOString().slice(0, 10)}.pptx`;

  await pptx.writeFile({ fileName: fileName });
  setProgress('¡Presentación PPTX descargada exitosamente!', 100);
}
