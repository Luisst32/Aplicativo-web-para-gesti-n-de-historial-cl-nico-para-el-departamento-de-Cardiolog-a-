/**
 * CARDIOUNEMI - Dashboard Epidemiológico y Clínico.
 * Motor dinámico de analítica y agregación estadística en tiempo real.
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

// Formateador numérico en formato local
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

// Navegación entre pestañas temáticas

// Helpers para tooltips con porcentaje tanto en ApexCharts como en Chart.js
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

if (typeof Chart !== 'undefined' && Chart.defaults) {
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

function switchTab(tabId, element) {
  activeTabId = tabId;
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  if (element) element.classList.add('active');

  document.querySelectorAll('.tab-view').forEach(view => view.classList.remove('active'));
  const targetView = document.getElementById('tab-' + tabId);
  if (targetView) targetView.classList.add('active');

  // Actualizar título de vista activa
  const titleEl = document.getElementById('view-title');
  if (titleEl) {
    const titles = {
      'resumen-general': 'Resumen General Epidemiológico',
      'datos-individuo': '1. Datos del Individuo y Filiación',
      'exploracion-fisica': '2. Exploración Física y Antropometría',
      'factores-modificables': '3. Factores de Riesgo Modificables',
      'factores-emergentes': '4. Factores de Riesgo Emergentes',
      'antecedentes-familiares': '5. Antecedentes Familiares Cardiovasculares',
      'historia-no-cardio': '6. Historia Clínica No Cardiovascular',
      'covid-19': '7. COVID-19 y Secuelas Post-Infección',
      'electrocardiograma': '8. Resultados del Electrocardiograma (ECG)'
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
        dataLabels: { enabled: true }
      ,
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
        dataLabels: { enabled: true, formatter: val => `${val}%` }
      ,
        tooltip: apexPctTooltip()
      });
      charts.factores.render();
    }
  }

  // 3. Distribución por Categoría de Personal (Chart.js Donut)
  const catCounts = {};
  filteredRecords.forEach(r => { catCounts[r.categoria] = (catCounts[r.categoria] || 0) + 1; });
  const catLabels = Object.keys(catCounts);
  const catVals = catLabels.map(k => catCounts[k]);

  const ctxCat = document.getElementById('chart-categoria-personal');
  if (ctxCat) {
    if (charts.categoria) {
      charts.categoria.data.labels = catLabels;
      charts.categoria.data.datasets[0].data = catVals;
      charts.categoria.update();
    } else {
      charts.categoria = new Chart(ctxCat, {
        type: 'doughnut',
        data: {
          labels: catLabels,
          datasets: [{
            data: catVals,
            backgroundColor: [PALETTE.primaryBlue, PALETTE.yellow, PALETTE.green, PALETTE.purple, PALETTE.navy]
          }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
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
          scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } },
          plugins: { legend: { position: 'bottom' } }
        }
      });
    }
  }
}

// -------------------------------------------------------------
// TAB 1: DATOS DEL INDIVIDUO CHARTS
// -------------------------------------------------------------
function renderTabDatosIndividuo() {
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
        ]
      });
    } else {
      charts.indEdad = new ApexCharts(elPiramide, {
        chart: { type: 'bar', height: 260, toolbar: { show: false } },
        colors: [PALETTE.primaryBlue, PALETTE.purple],
        plotOptions: { bar: { horizontal: false, columnWidth: '55%', borderRadius: 4 } },
        series: [
          { name: 'Hombres', data: hEdad },
          { name: 'Mujeres', data: mEdad }
        ],
        xaxis: { categories: grupos },
        legend: { position: 'top' }
      ,
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

  const ctxEdu = document.getElementById('chart-ind-educacion');
  if (ctxEdu) {
    if (charts.indEdu) {
      charts.indEdu.data.labels = eduLabels;
      charts.indEdu.data.datasets[0].data = eduVals;
      charts.indEdu.update();
    } else {
      charts.indEdu = new Chart(ctxEdu, {
        type: 'doughnut',
        data: {
          labels: eduLabels,
          datasets: [{ data: eduVals, backgroundColor: [PALETTE.green, PALETTE.primaryBlue, PALETTE.yellow, PALETTE.navy] }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
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
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
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
        xaxis: { categories: vivLabels }
      ,
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
        legend: { show: false }
      ,
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
          }
        }
      });
    }
  }

  // Clasificación Presión Arterial
  const paCats = ['PA Normal (<130/<80)', 'PA Elevada (130-139/80-89)', 'HTA Grado 1 (140-159/90-99)', 'HTA Grado 2 (≥140/90)'];
  const paVals = paCats.map(c => filteredRecords.filter(r => r.pa_categoria === c).length);

  const ctxPa = document.getElementById('chart-exp-pa-cat');
  if (ctxPa) {
    if (charts.expPa) {
      charts.expPa.data.datasets[0].data = paVals;
      charts.expPa.update();
    } else {
      charts.expPa = new Chart(ctxPa, {
        type: 'pie',
        data: {
          labels: ['Normal', 'Elevada / Limítrofe', 'HTA Grado 1', 'HTA Grado 2'],
          datasets: [{ data: paVals, backgroundColor: [PALETTE.green, PALETTE.yellow, PALETTE.emergencyRed, '#991B1B'] }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
      });
    }
  }

  // Hallazgos Auscultación
  const auscNorm = filteredRecords.filter(r => r.ausc_pulm_normal && r.ausc_abdom_normal).length;
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
        legend: { show: false }
      ,
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
        legend: { position: 'top' }
      ,
        tooltip: apexCountTooltip()
      });
      charts.modControl.render();
    }
  }

  // Hábitos Tóxicos (Tabaquismo y Alcohol)
  const tabCats = ['No fuma', 'Exfumador', 'Fumador Activo'];
  const tabVals = tabCats.map(c => filteredRecords.filter(r => r.tabaquismo === c).length);

  const ctxTox = document.getElementById('chart-mod-toxicos');
  if (ctxTox) {
    if (charts.modTox) {
      charts.modTox.data.datasets[0].data = tabVals;
      charts.modTox.update();
    } else {
      charts.modTox = new Chart(ctxTox, {
        type: 'bar',
        data: {
          labels: tabCats,
          datasets: [{ label: 'Personas', data: tabVals, backgroundColor: [PALETTE.green, PALETTE.yellow, PALETTE.emergencyRed], borderRadius: 5 }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
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
        legend: { position: 'top' }
      ,
        tooltip: apexCountTooltip()
      });
      charts.modActCat.render();
    }
  }

  // Dieta Mediterránea PREDIMED
  const predimedAlta = filteredRecords.filter(r => r.predimed_adherencia === 'Buena Adherencia').length;
  const predimedBaja = filteredRecords.filter(r => r.predimed_adherencia !== 'Buena Adherencia').length;

  const ctxPred = document.getElementById('chart-mod-predimed');
  if (ctxPred) {
    if (charts.modPred) {
      charts.modPred.data.datasets[0].data = [predimedAlta, predimedBaja];
      charts.modPred.update();
    } else {
      charts.modPred = new Chart(ctxPred, {
        type: 'doughnut',
        data: {
          labels: ['Buena Adherencia Mediterránea', 'Adherencia Moderada / Baja'],
          datasets: [{ data: [predimedAlta, predimedBaja], backgroundColor: [PALETTE.green, PALETTE.yellow] }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
      });
    }
  }
}

// -------------------------------------------------------------
// TAB 4: FACTORES EMERGENTES CHARTS
// -------------------------------------------------------------
function renderTabFactoresEmergentes() {
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
        legend: { show: false }
      ,
        tooltip: apexCountTooltip()
      });
      charts.emSueno.render();
    }
  }

  // Espectro de Estrés
  const estLab = filteredRecords.filter(r => r.estres === 'Estrés Laboral').length;
  const estFam = filteredRecords.filter(r => r.estres === 'Estrés Familiar').length;
  const estAmbos = filteredRecords.filter(r => r.estres === 'Laboral y Familiar').length;
  const estSin = filteredRecords.filter(r => r.estres === 'Sin estrés significativo').length;

  const ctxEstres = document.getElementById('chart-em-estres');
  if (ctxEstres) {
    if (charts.emEstres) {
      charts.emEstres.data.datasets[0].data = [estLab, estFam, estAmbos, estSin];
      charts.emEstres.update();
    } else {
      charts.emEstres = new Chart(ctxEstres, {
        type: 'pie',
        data: {
          labels: ['Estrés Laboral', 'Estrés Familiar', 'Ambos Factores', 'Sin Estrés Significativo'],
          datasets: [{ data: [estLab, estFam, estAmbos, estSin], backgroundColor: [PALETTE.yellow, PALETTE.purple, PALETTE.emergencyRed, PALETTE.green] }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
      });
    }
  }

  // Personalidad Tipo A
  const persSi = filteredRecords.filter(r => r.personalidad_tipo_a).length;
  const persNo = filteredRecords.filter(r => !r.personalidad_tipo_a).length;

  const ctxPers = document.getElementById('chart-em-personalidad-a');
  if (ctxPers) {
    if (charts.emPers) {
      charts.emPers.data.datasets[0].data = [persSi, persNo];
      charts.emPers.update();
    } else {
      charts.emPers = new Chart(ctxPers, {
        type: 'doughnut',
        data: {
          labels: ['Presenta Personalidad Tipo A (Alta Autoexigencia)', 'Sin Personalidad Tipo A'],
          datasets: [{ data: [persSi, persNo], backgroundColor: [PALETTE.emergencyRed, PALETTE.teal] }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
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
        legend: { show: false }
      ,
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
        ]
      });
    } else {
      charts.famPadres = new ApexCharts(elPadres, {
        chart: { type: 'bar', height: 260, toolbar: { show: false } },
        colors: [PALETTE.primaryBlue, PALETTE.purple],
        plotOptions: { bar: { horizontal: false, columnWidth: '55%', borderRadius: 4 } },
        series: [
          { name: 'Rama Paterna', data: [padreHta, padreDm, padreDlp, padreIam] },
          { name: 'Rama Materna', data: [madreHta, madreDm, madreDlp, madreIam] }
        ],
        xaxis: { categories: ['Hipertensión', 'Diabetes', 'Dislipemia', 'Infarto / Ictus'] },
        legend: { position: 'top' }
      ,
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

  const ctxCarga = document.getElementById('chart-fam-carga-global');
  if (ctxCarga) {
    if (charts.famCarga) {
      charts.famCarga.data.datasets[0].data = [c0, c1, c2, c3];
      charts.famCarga.update();
    } else {
      charts.famCarga = new Chart(ctxCarga, {
        type: 'doughnut',
        data: {
          labels: ['Sin Antecedentes', '1 Antecedente', '2 Antecedentes', '3 o más Antecedentes'],
          datasets: [{ data: [c0, c1, c2, c3], backgroundColor: [PALETTE.green, PALETTE.teal, PALETTE.yellow, PALETTE.emergencyRed] }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
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
        plotOptions: { bar: { horizontal: false, borderRadius: 4 } },
        series: [
          { name: 'HTA Familiar', data: htaPorEdad },
          { name: 'Diabetes Familiar', data: dmPorEdad }
        ],
        xaxis: { categories: grupos },
        legend: { position: 'top' }
      ,
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
          labels: ['Solo HTA Familiar', 'Solo Diabetes Familiar', 'Ambas Patologías Coexistentes', 'Sin Estos Antecedentes'],
          datasets: [{ label: 'Casos', data: [soloHta, soloDm, ambos, ninguno], backgroundColor: [PALETTE.emergencyRed, PALETTE.yellow, PALETTE.purple, PALETTE.green], borderRadius: 5 }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
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

  const labels = ['Respiratorio (Asma/EPOC)', 'Salud Mental (Ansiedad/Depresión)', 'Alergias Medicamentosas', 'Reumatológica', 'Cáncer / Oncología', 'Insuficiencia Renal'];
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
        legend: { show: false }
      ,
        tooltip: apexCountTooltip()
      });
      charts.ncComorb.render();
    }
  }

  // Salud Mental Donut
  const ansSolo = filteredRecords.filter(r => r.salud_mental_desc === 'Ansiedad').length;
  const depSolo = filteredRecords.filter(r => r.salud_mental_desc === 'Depresión').length;
  const ambMental = filteredRecords.filter(r => r.salud_mental_desc.includes('Ansiedad y Depresión')).length;
  const sinMental = filteredRecords.filter(r => r.salud_mental_desc.includes('Sin trastorno')).length;

  const ctxMental = document.getElementById('chart-nc-salud-mental');
  if (ctxMental) {
    if (charts.ncMental) {
      charts.ncMental.data.datasets[0].data = [ansSolo, depSolo, ambMental, sinMental];
      charts.ncMental.update();
    } else {
      charts.ncMental = new Chart(ctxMental, {
        type: 'doughnut',
        data: {
          labels: ['Solo Ansiedad', 'Solo Depresión', 'Ansiedad y Depresión', 'Sin Trastorno'],
          datasets: [{ data: [ansSolo, depSolo, ambMental, sinMental], backgroundColor: [PALETTE.yellow, PALETTE.purple, PALETTE.emergencyRed, PALETTE.green] }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
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
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
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
        legend: { show: false }
      ,
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
        legend: { show: false }
      ,
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
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
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
        plotOptions: { bar: { horizontal: false, borderRadius: 4 } },
        series: [
          { name: 'Infectados COVID', data: covPorCat },
          { name: 'Hospitalizados', data: hospPorCat }
        ],
        xaxis: { categories: catNames },
        legend: { position: 'top' }
      ,
        tooltip: apexCountTooltip()
      });
      charts.covCat.render();
    }
  }

  // Prevalencia por Sexo
  const covH = filteredRecords.filter(r => r.sexo === 'Hombre' && r.covid_infeccion).length;
  const covM = filteredRecords.filter(r => r.sexo === 'Mujer' && r.covid_infeccion).length;

  const ctxGen = document.getElementById('chart-cov-por-genero');
  if (ctxGen) {
    if (charts.covGen) {
      charts.covGen.data.datasets[0].data = [covH, covM];
      charts.covGen.update();
    } else {
      charts.covGen = new Chart(ctxGen, {
        type: 'doughnut',
        data: {
          labels: ['Hombres Infectados', 'Mujeres Infectadas'],
          datasets: [{ data: [covH, covM], backgroundColor: [PALETTE.primaryBlue, PALETTE.purple] }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
      });
    }
  }
}

// -------------------------------------------------------------
// TAB 8: RESULTADOS DEL ELECTROCARDIOGRAMA CHARTS
// -------------------------------------------------------------
function renderTabElectrocardiograma() {
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
        legend: { position: 'bottom' }
      ,
        tooltip: apexCountTooltip()
      });
      charts.ecgRitmo.render();
    }
  }

  // Intervalos de Conducción
  const prNorm = filteredRecords.filter(r => r.ecg_pr_cat.includes('Normal')).length;
  const prBloq = filteredRecords.filter(r => r.ecg_pr_cat.includes('Bloqueo')).length;
  const qrsNorm = filteredRecords.filter(r => r.ecg_qrs_cat.includes('Normal')).length;
  const qrsBloq = filteredRecords.filter(r => r.ecg_qrs_cat.includes('Bloqueo')).length;
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
          scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } },
          plugins: { legend: { position: 'bottom' } }
        }
      });
    }
  }

  // Anomalías de Conducción y Morfología
  const hviCnt = filteredRecords.filter(r => r.ecg_hvi).length;
  const brCnt = filteredRecords.filter(r => r.ecg_bloqueo_rama && r.ecg_bloqueo_rama !== 'Sin bloqueo').length;
  const repolCnt = filteredRecords.filter(r => r.ecg_repolarizacion).length;
  const sinAnom = filteredRecords.filter(r => !r.ecg_hvi && (!r.ecg_bloqueo_rama || r.ecg_bloqueo_rama === 'Sin bloqueo') && !r.ecg_repolarizacion).length;

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
        legend: { show: false }
      ,
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
          plugins: { legend: { display: false } }
        }
      });
    }
  }
}
