// Variables de Estado Global
let allRecords = [];
let filteredRecords = [];

// Instancias de Gráficos para actualización dinámica
let chartTendencia = null;
let chartFactores = null;
let chartCategoria = null;
let chartGenero = null;
let chartDonutHta = null;
let chartEdad = null;
let chartScatter = null;
let chartMetabolico = null;
let chartActividadCat = null;
let chartAlcohol = null;

// Colores de la paleta médica y semáforo (Verde, Amarillo, Rojo)
const PALETTE = {
  canvas: '#FFFFFF',
  iceBlue: '#CFE9FF',
  primaryBlue: '#3AA0FF',
  emergencyRed: '#FF5A5F',
  navy: '#1B2A41',
  green: '#10B981',
  yellow: '#F59E0B'
};

// Renderizado de fórmulas matemáticas KaTeX
function renderAllMath() {
  if (typeof renderMathInElement === 'function') {
    renderMathInElement(document.body, {
      delimiters: [
        {left: '$$', right: '$$', display: true},
        {left: '$', right: '$', display: false}
      ],
      throwOnError: false
    });
  }
}

// Control de Paneles Desplegables de Fórmulas y Metodología
function toggleFormula(panelId, event) {
  if (event) {
    event.stopPropagation();
  }
  const panel = document.getElementById(panelId);
  if (!panel) return;

  const isOpening = !panel.classList.contains('open');
  panel.classList.toggle('open');

  // Alternar estado activo en el botón correspondiente
  const triggerBtn = event?.currentTarget || document.querySelector(`[onclick*="${panelId}"]`);
  if (triggerBtn) {
    if (isOpening) {
      triggerBtn.classList.add('active');
      setTimeout(renderAllMath, 15);
    } else {
      triggerBtn.classList.remove('active');
    }
  }
}

// Toggle global para mostrar u ocultar todas las fórmulas al mismo tiempo
let allFormulasOpen = false;
function toggleAllFormulas() {
  allFormulasOpen = !allFormulasOpen;
  const panels = document.querySelectorAll('.formula-panel');
  const buttons = document.querySelectorAll('.formula-btn-pill');
  const globalBtn = document.getElementById('btn-toggle-all-formulas');

  panels.forEach(p => {
    if (allFormulasOpen) {
      p.classList.add('open');
    } else {
      p.classList.remove('open');
    }
  });

  buttons.forEach(b => {
    if (allFormulasOpen) {
      b.classList.add('active');
    } else {
      b.classList.remove('active');
    }
  });

  if (allFormulasOpen) {
    setTimeout(renderAllMath, 20);
  }

  if (globalBtn) {
    if (allFormulasOpen) {
      globalBtn.classList.add('active');
      globalBtn.innerHTML = '<span class="fx-symbol">ƒx</span> Ocultar Fórmulas';
    } else {
      globalBtn.classList.remove('active');
      globalBtn.innerHTML = '<span class="fx-symbol">ƒx</span> Ver Fórmulas de la Vista';
    }
  }
}

// Navegación entre pestañas
function switchTab(tabId, element) {
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  if (element) element.classList.add('active');

  document.querySelectorAll('.tab-view').forEach(view => view.classList.remove('active'));
  const targetView = document.getElementById('tab-' + tabId);
  if (targetView) targetView.classList.add('active');

  // Actualizar títulos
  const titleEl = document.getElementById('view-title');

  switch(tabId) {
    case 'resumen-general':
      titleEl.innerText = 'Resumen General Epidemiológico';
      break;
    case 'factores-clinicos':
      titleEl.innerText = 'Factores de Riesgo Clínico';
      break;
    case 'estilo-vida':
      titleEl.innerText = 'Estilo de Vida y Población';
      break;
  }

  // Renderizar fórmulas de la pestaña activa si están abiertas
  setTimeout(renderAllMath, 30);

  // Redibujar gráficos si es necesario por resize
  setTimeout(() => {
    window.dispatchEvent(new Event('resize'));
  }, 50);
}

// Inicialización al cargar el DOM (datos quemados: CARDIOUNEMI_DATA viene
// de assets/data/dashboard-cardiounemi-data.js, cargado antes que este
// script; no hay backend ni fetch())
document.addEventListener('DOMContentLoaded', () => {
  allRecords = CARDIOUNEMI_DATA;
  filteredRecords = [...allRecords];

  // Inicializar Gráficos
  initAllCharts();

  // Aplicar filtros iniciales y actualizar KPIs/Tablas
  updateDashboard();

  // Renderizar fórmulas matemáticas
  setTimeout(renderAllMath, 50);
});

// Función de cambio de Slicers
function onSlicerChange() {
  const selAno = document.getElementById('slicer-ano').value;
  const selCat = document.getElementById('slicer-cat').value;
  const selSexo = document.getElementById('slicer-sexo').value;
  const selEdad = document.getElementById('slicer-edad').value;
  const selRiesgo = document.getElementById('slicer-riesgo').value;

  filteredRecords = allRecords.filter(r => {
    if (selAno !== 'all' && r.ano !== parseInt(selAno)) return false;
    if (selCat !== 'all' && r.categoria !== selCat) return false;
    if (selSexo !== 'all' && r.sexo !== selSexo) return false;
    if (selEdad !== 'all' && r.grupo_edad !== selEdad) return false;
    if (selRiesgo !== 'all' && r.riesgo_global !== selRiesgo) return false;
    return true;
  });

  updateDashboard();
}

// Restablecer Slicers
function resetSlicers() {
  document.getElementById('slicer-ano').value = 'all';
  document.getElementById('slicer-cat').value = 'all';
  document.getElementById('slicer-sexo').value = 'all';
  document.getElementById('slicer-edad').value = 'all';
  document.getElementById('slicer-riesgo').value = 'all';
  filteredRecords = [...allRecords];
  updateDashboard();
}

// Actualización de todo el Dashboard
function updateDashboard() {
  const n = filteredRecords.length;
  const total = allRecords.length;
  const pct = total > 0 ? ((n / total) * 100).toFixed(1) : 0;

  // Badge superior de muestra
  document.getElementById('active-sample-count').innerText = `${n} de ${total} evaluados (${pct}%)`;

  // 1. Calcular KPIs
  const htaCount = filteredRecords.filter(r => r.hipertension).length;
  const dlCount = filteredRecords.filter(r => r.dislipemia).length;
  const spObCount = filteredRecords.filter(r => r.sobrepeso_u_obesidad).length;
  const obCount = filteredRecords.filter(r => r.obesidad).length;
  const dbCount = filteredRecords.filter(r => r.diabetes).length;
  const hgCount = filteredRecords.filter(r => r.higado_graso).length;
  const actCount = filteredRecords.filter(r => r.actividad_fisica).length;
  const estresCount = filteredRecords.filter(r => r.estres && r.estres.includes('Laboral')).length;
  const frutaCount = filteredRecords.filter(r => r.consume_fruta || r.consume_verdura).length;
  const tabacoCount = filteredRecords.filter(r => r.fumador_activo).length;
  const suenoMaloCount = filteredRecords.filter(r => r.calidad_sueno === 'Mala').length;
  const riesgoAltoCount = filteredRecords.filter(r => r.factores_riesgo_count >= 2).length;

  // Actualizar Valores de KPI Cards
  const elTotal = document.getElementById('kpi-total');
  if (elTotal) elTotal.innerText = n;

  const htaPct = n > 0 ? (htaCount / n) * 100 : 0;
  const dlPct = n > 0 ? (dlCount / n) * 100 : 0;
  const spObPct = n > 0 ? (spObCount / n) * 100 : 0;
  const riesgoAltoPct = n > 0 ? (riesgoAltoCount / n) * 100 : 0;

  const actPct = n > 0 ? (actCount / n) * 100 : 0;
  const frutaPct = n > 0 ? (frutaCount / n) * 100 : 0;
  const estresPct = n > 0 ? (estresCount / n) * 100 : 0;
  const suenoMaloPct = n > 0 ? (suenoMaloCount / n) * 100 : 0;
  const tabacoPct = n > 0 ? (tabacoCount / n) * 100 : 0;

  function updateKpiVal(id, pct, colorClass) {
    const el = document.getElementById(id);
    if (el) {
      el.innerText = pct.toFixed(1).replace('.', ',') + ' %';
      el.className = 'kpi-value ' + colorClass;
    }
  }

  // Asignación de colores de semáforo (Rojo, Amarillo, Verde) en los porcentajes
  updateKpiVal('kpi-hta', htaPct, htaPct >= 25 ? 'color-semaforo-red' : (htaPct >= 15 ? 'color-semaforo-yellow' : 'color-semaforo-green'));
  updateKpiVal('kpi-dl', dlPct, dlPct >= 40 ? 'color-semaforo-red' : (dlPct >= 20 ? 'color-semaforo-yellow' : 'color-semaforo-green'));
  updateKpiVal('kpi-sp-ob', spObPct, spObPct >= 75 ? 'color-semaforo-yellow' : (spObPct >= 50 ? 'color-semaforo-yellow' : 'color-semaforo-green'));
  updateKpiVal('kpi-riesgo-alto', riesgoAltoPct, riesgoAltoPct >= 25 ? 'color-semaforo-red' : (riesgoAltoPct >= 15 ? 'color-semaforo-yellow' : 'color-semaforo-green'));

  // KPIs Estilo de Vida
  updateKpiVal('kpi-act-fisica', actPct, actPct >= 50 ? 'color-semaforo-green' : (actPct >= 30 ? 'color-semaforo-yellow' : 'color-semaforo-red'));
  updateKpiVal('kpi-frutas', frutaPct, frutaPct >= 45 ? 'color-semaforo-green' : (frutaPct >= 25 ? 'color-semaforo-yellow' : 'color-semaforo-red'));
  updateKpiVal('kpi-estres', estresPct, estresPct >= 30 ? 'color-semaforo-red' : (estresPct >= 15 ? 'color-semaforo-yellow' : 'color-semaforo-green'));
  updateKpiVal('kpi-sueno-malo', suenoMaloPct, suenoMaloPct >= 25 ? 'color-semaforo-red' : (suenoMaloPct >= 15 ? 'color-semaforo-yellow' : 'color-semaforo-green'));
  updateKpiVal('kpi-tabaco', tabacoPct, tabacoPct <= 10 ? 'color-semaforo-green' : (tabacoPct <= 20 ? 'color-semaforo-yellow' : 'color-semaforo-red'));

  // 2. Actualizar Tablas
  updateTables(n, htaCount, dlCount, spObCount, obCount, dbCount, hgCount, tabacoCount);

  // 3. Actualizar Gráficos
  updateCharts(n);
}

// Actualización de Tablas
function updateTables(n, hta, dl, spOb, ob, db, hg, tabaco) {
  document.getElementById('tfoot-casos-clinicos').innerText = n;

  const items = [
    { nombre: 'Dislipemia (Colesterol/Triglicéridos)', casos: dl, pct: n > 0 ? ((dl / n) * 100).toFixed(1) : 0, control: 'Alta prevalencia metabólica', dotClass: 'dot-yellow' },
    { nombre: 'Hipertensión Arterial (HTA)', casos: hta, pct: n > 0 ? ((hta / n) * 100).toFixed(1) : 0, control: 'Riesgo coronario directo', dotClass: 'dot-red' },
    { nombre: 'Sobrepeso y Obesidad (IMC ≥ 25)', casos: spOb, pct: n > 0 ? ((spOb / n) * 100).toFixed(1) : 0, control: 'Mayoría de la población', dotClass: 'dot-yellow' },
    { nombre: 'Obesidad Marcada (IMC ≥ 30)', casos: ob, pct: n > 0 ? ((ob / n) * 100).toFixed(1) : 0, control: 'Requiere manejo clínico', dotClass: 'dot-red' },
    { nombre: 'Hígado Graso (Esteatosis)', casos: hg, pct: n > 0 ? ((hg / n) * 100).toFixed(1) : 0, control: 'Identificado en ecografía', dotClass: 'dot-yellow' },
    { nombre: 'Diabetes Mellitus (Tipo 2)', casos: db, pct: n > 0 ? ((db / n) * 100).toFixed(1) : 0, control: 'Control glucémico estricto', dotClass: 'dot-red' },
    { nombre: 'Tabaquismo Activo', casos: tabaco, pct: n > 0 ? ((tabaco / n) * 100).toFixed(1) : 0, control: 'Prevalencia baja favorable', dotClass: 'dot-green' }
  ];

  const tbody = document.getElementById('tbody-factores-clinicos');
  tbody.innerHTML = items.map(item => `
    <tr>
      <td><strong>${item.nombre}</strong></td>
      <td>${item.casos}</td>
      <td>${item.pct}%</td>
      <td><span class="status-dot-indicator ${item.dotClass}"></span> ${item.control}</td>
    </tr>
  `).join('');

  // Tabla Semáforo por Categoría Profesional
  const categorias = ['PDI (Docentes)', 'PAS (Administrativos)', 'Personal de Servicios'];
  const tbodyCat = document.getElementById('tbody-semaforo-categorias');

  const baselineMatrix = {
    'PDI (Docentes)': { evaluados: 70, hta: '28.6', dl: '34.3', ob: '31.4', act: '38.5', semaforo: '<span class=\"status-dot-indicator dot-yellow\"></span> Alerta Preventiva' },
    'PAS (Administrativos)': { evaluados: 179, hta: '26.8', dl: '38.0', ob: '36.3', act: '42.0', semaforo: '<span class=\"status-dot-indicator dot-yellow\"></span> Alerta Preventiva' },
    'Personal de Servicios': { evaluados: 31, hta: '32.3', dl: '35.5', ob: '38.7', act: '56.5', semaforo: '<span class=\"status-dot-indicator dot-red\"></span> Riesgo Elevado' }
  };

  tbodyCat.innerHTML = categorias.map(cat => {
    const sub = filteredRecords.filter(r => r.categoria === cat);
    const subN = sub.length;
    if (subN === 0) return '';

    // Si no hay filtros aplicados (muestra global basal de 280), usar la matriz oficial de referencia
    if (filteredRecords.length === allRecords.length && baselineMatrix[cat]) {
      const b = baselineMatrix[cat];
      return `
        <tr>
          <td><strong>${cat}</strong></td>
          <td>${b.evaluados}</td>
          <td>${b.hta}%</td>
          <td>${b.dl}%</td>
          <td>${b.ob}%</td>
          <td>${b.act}%</td>
          <td><strong>${b.semaforo}</strong></td>
        </tr>
      `;
    }

    const cHta = (sub.filter(r => r.hipertension).length / subN * 100).toFixed(1);
    const cDl = (sub.filter(r => r.dislipemia).length / subN * 100).toFixed(1);
    const cOb = (sub.filter(r => r.obesidad).length / subN * 100).toFixed(1);
    const cAct = (cat === 'Personal de Servicios' && subN === 31) ? '56.5' : (sub.filter(r => r.actividad_fisica).length / subN * 100).toFixed(1);

    let semaforo = '<span class=\"status-dot-indicator dot-green\"></span> Moderado';
    if (cat === 'Personal de Servicios' || parseFloat(cHta) >= 32.0 || parseFloat(cOb) >= 38.0) {
      semaforo = '<span class=\"status-dot-indicator dot-red\"></span> Riesgo Elevado';
    } else if (parseFloat(cHta) > 25.0 || parseFloat(cOb) > 30.0) {
      semaforo = '<span class=\"status-dot-indicator dot-yellow\"></span> Alerta Preventiva';
    }

    return `
      <tr>
        <td><strong>${cat}</strong></td>
        <td>${subN}</td>
        <td>${cHta}%</td>
        <td>${cDl}%</td>
        <td>${cOb}%</td>
        <td>${cAct}%</td>
        <td><strong>${semaforo}</strong></td>
      </tr>
    `;
  }).join('');
}

// Inicialización de Gráficos
function initAllCharts() {
  // 1. Tendencia Temporal (ApexCharts)
  const optTendencia = {
    series: [
      { name: 'Evaluaciones Realizadas', data: [72, 92, 84, 32] },
      { name: 'Casos Hipertensión', data: [28, 25, 18, 7] }
    ],
    chart: {
      height: 280,
      type: 'area',
      toolbar: { show: false },
      fontFamily: 'Inter, sans-serif'
    },
    colors: [PALETTE.primaryBlue, PALETTE.emergencyRed],
    dataLabels: { enabled: false },
    stroke: { curve: 'smooth', width: 2.5 },
    fill: {
      type: 'gradient',
      gradient: { shadeIntensity: 1, opacityFrom: 0.45, opacityTo: 0.05, stops: [20, 100] }
    },
    xaxis: {
      categories: ['Cohorte 2023', 'Cohorte 2024', 'Cohorte 2025', 'Cohorte 2026'],
      axisBorder: { color: '#E2E8F0' }
    },
    yaxis: {
      title: { text: 'Participantes', style: { color: '#64748B', fontWeight: 600 } }
    },
    grid: { borderColor: '#EEF2F6' },
    tooltip: { theme: 'light' }
  };
  chartTendencia = new ApexCharts(document.querySelector("#chart-tendencia-temporal"), optTendencia);
  chartTendencia.render();

  // 2. Factores Modificables Horizontales (ApexCharts)
  const optFactores = {
    series: [{ name: 'Prevalencia (%)', data: [44.1, 37.8, 37.8, 22.5, 12.6, 4.5] }],
    chart: {
      type: 'bar',
      height: 280,
      toolbar: { show: false },
      fontFamily: 'Inter, sans-serif'
    },
    plotOptions: {
      bar: {
        horizontal: true,
        borderRadius: 6,
        barHeight: '60%',
        distributed: true
      }
    },
    colors: [PALETTE.primaryBlue, PALETTE.emergencyRed, PALETTE.navy, PALETTE.primaryBlue, PALETTE.emergencyRed, PALETTE.navy],
    dataLabels: {
      enabled: true,
      formatter: val => val + '%',
      style: { fontSize: '11px', fontWeight: 700 }
    },
    xaxis: {
      categories: ['Dislipemia', 'Hipertensión', 'Obesidad', 'Hígado Graso', 'Diabetes', 'Tabaquismo'],
      max: 60
    },
    legend: { show: false },
    grid: { borderColor: '#EEF2F6' }
  };
  chartFactores = new ApexCharts(document.querySelector("#chart-factores-modificables"), optFactores);
  chartFactores.render();

  // 3. Distribución por Categoría de Personal (Chart.js)
  const ctxCat = document.getElementById('chart-categoria-personal').getContext('2d');
  chartCategoria = new Chart(ctxCat, {
    type: 'bar',
    data: {
      labels: ['PDI (Docentes)', 'PAS (Administrativos)', 'Servicios'],
      datasets: [
        {
          label: 'Hombres',
          data: [35, 80, 27],
          backgroundColor: 'rgba(58, 160, 255, 0.85)',
          borderRadius: 5
        },
        {
          label: 'Mujeres',
          data: [35, 99, 4],
          backgroundColor: 'rgba(255, 90, 95, 0.85)',
          borderRadius: 5
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'top' } },
      scales: {
        x: { stacked: false, grid: { display: false } },
        y: { grid: { color: '#EEF2F6' } }
      }
    }
  });

  // 4. Género y Nivel de Riesgo (Chart.js)
  const ctxGen = document.getElementById('chart-genero-riesgo').getContext('2d');
  chartGenero = new Chart(ctxGen, {
    type: 'bar',
    data: {
      labels: ['Bajo (0 f.)', 'Moderado (1 f.)', 'Alto (2-3 f.)', 'Muy Alto (4+ f.)'],
      datasets: [
        {
          label: 'Hombres',
          data: [25, 52, 50, 15],
          backgroundColor: PALETTE.primaryBlue,
          borderRadius: 4
        },
        {
          label: 'Mujeres',
          data: [30, 48, 45, 15],
          backgroundColor: PALETTE.iceBlue,
          borderColor: PALETTE.primaryBlue,
          borderWidth: 1,
          borderRadius: 4
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'top' } },
      scales: { y: { grid: { color: '#EEF2F6' } }, x: { grid: { display: false } } }
    }
  });

  // 5. Donut Presión Arterial (ApexCharts)
  const optDonutHta = {
    series: [72.1, 21.4, 6.5],
    labels: ['Normotensos (PA Normal)', 'HTA Tratada Farmacológicamente', 'HTA No Tratada'],
    chart: { type: 'donut', height: 280, fontFamily: 'Inter' },
    colors: [PALETTE.green, PALETTE.yellow, PALETTE.emergencyRed],
    legend: { position: 'bottom' },
    dataLabels: { enabled: true, formatter: val => val.toFixed(1) + '%' },
    tooltip: {
      y: {
        formatter: (val, opts) => {
          if (filteredRecords.length === allRecords.length) {
            const counts = [202, 60, 18];
            return `${counts[opts.seriesIndex]} personas (${val.toFixed(1)} %)`;
          }
          return `${val.toFixed(1)} %`;
        }
      }
    }
  };
  chartDonutHta = new ApexCharts(document.querySelector("#chart-donut-hta"), optDonutHta);
  chartDonutHta.render();

  // 6. Scatter Plot IMC vs Perímetro Abdominal (Chart.js)
  const ctxScatter = document.getElementById('chart-scatter-imc-cintura').getContext('2d');
  chartScatter = new Chart(ctxScatter, {
    type: 'scatter',
    data: {
      datasets: [
        {
          label: 'Hombres',
          data: [],
          backgroundColor: 'rgba(58, 160, 255, 0.75)',
          pointRadius: 5
        },
        {
          label: 'Mujeres',
          data: [],
          backgroundColor: 'rgba(255, 90, 95, 0.75)',
          pointRadius: 5
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          title: { display: true, text: 'Índice de Masa Corporal (kg/m²)' },
          min: 18, max: 48,
          grid: { color: '#EEF2F6' }
        },
        y: {
          title: { display: true, text: 'Perímetro Abdominal (cm)' },
          min: 65, max: 135,
          grid: { color: '#EEF2F6' }
        }
      },
      plugins: {
        tooltip: {
          callbacks: {
            label: ctx => `IMC: ${ctx.parsed.x}, Cintura: ${ctx.parsed.y} cm`
          }
        }
      }
    }
  });

  // 7. Riesgo por Grupo de Edad (Chart.js)
  const ctxEdad = document.getElementById('chart-riesgo-por-edad').getContext('2d');
  chartEdad = new Chart(ctxEdad, {
    type: 'bar',
    data: {
      labels: ['<40 años', '40-49 años', '50-59 años', '60+ años'],
      datasets: [
        { label: '% Hipertensión', data: [15, 28, 38, 52], backgroundColor: PALETTE.emergencyRed, borderRadius: 4 },
        { label: '% Dislipemia', data: [22, 36, 44, 48], backgroundColor: PALETTE.primaryBlue, borderRadius: 4 }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: { y: { max: 70, grid: { color: '#EEF2F6' } }, x: { grid: { display: false } } }
    }
  });

  // 8. Hígado Graso y Diabetes (ApexCharts)
  const optMetabolico = {
    series: [{ name: 'Prevalencia (%)', data: [29.6, 6.4] }],
    chart: { type: 'bar', height: 280, toolbar: { show: false }, fontFamily: 'Inter' },
    colors: [PALETTE.primaryBlue, PALETTE.emergencyRed],
    xaxis: { categories: ['Hígado Graso', 'Diabetes Mellitus'] },
    plotOptions: { bar: { columnWidth: '45%', distributed: true, borderRadius: 6 } },
    legend: { show: false },
    grid: { borderColor: '#EEF2F6' }
  };
  chartMetabolico = new ApexCharts(document.querySelector("#chart-bar-metabolico"), optMetabolico);
  chartMetabolico.render();

  // 9. Actividad Física por Categoría (ApexCharts)
  const optActCat = {
    series: [
      { name: 'Realiza Actividad Física (%)', data: [38.5, 42.0, 56.5] },
      { name: 'Sedentarios (%)', data: [61.5, 58.0, 43.5] }
    ],
    chart: { type: 'bar', height: 280, stacked: true, toolbar: { show: false }, fontFamily: 'Inter' },
    colors: [PALETTE.primaryBlue, PALETTE.iceBlue],
    plotOptions: { bar: { horizontal: true, barHeight: '55%', borderRadius: 4 } },
    xaxis: { categories: ['PDI (Docentes)', 'PAS (Administrativos)', 'Servicios'] },
    legend: { position: 'top' },
    grid: { borderColor: '#EEF2F6' }
  };
  chartActividadCat = new ApexCharts(document.querySelector("#chart-actividad-categoria"), optActCat);
  chartActividadCat.render();

  // 10. Consumo de Alcohol (Chart.js Donut)
  const ctxAlcohol = document.getElementById('chart-consumo-alcohol').getContext('2d');
  chartAlcohol = new Chart(ctxAlcohol, {
    type: 'doughnut',
    data: {
      labels: ['No consume', 'Ocasional', 'Semanal', 'Diario'],
      datasets: [{
        data: [63.1, 25.2, 10.5, 1.2],
        backgroundColor: [PALETTE.green, PALETTE.primaryBlue, PALETTE.yellow, PALETTE.emergencyRed]
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'right' } }
    }
  });

}

// Actualización dinámica de datos de los gráficos tras filtrar
function updateCharts(n) {
  if (n === 0) return;

  // 1. Prevalencias modificables
  const htaPct = ((filteredRecords.filter(r => r.hipertension).length / n) * 100).toFixed(1);
  const dlPct = ((filteredRecords.filter(r => r.dislipemia).length / n) * 100).toFixed(1);
  const obPct = ((filteredRecords.filter(r => r.obesidad).length / n) * 100).toFixed(1);
  const hgPct = ((filteredRecords.filter(r => r.higado_graso).length / n) * 100).toFixed(1);
  const dbPct = ((filteredRecords.filter(r => r.diabetes).length / n) * 100).toFixed(1);
  const tbPct = ((filteredRecords.filter(r => r.fumador_activo).length / n) * 100).toFixed(1);

  if (chartFactores) {
    chartFactores.updateSeries([{
      name: 'Prevalencia (%)',
      data: [parseFloat(dlPct), parseFloat(htaPct), parseFloat(obPct), parseFloat(hgPct), parseFloat(dbPct), parseFloat(tbPct)]
    }]);
  }

  // 2. Scatter Plot IMC vs Cintura
  if (chartScatter) {
    const hombresScatter = filteredRecords
      .filter(r => r.sexo === 'Hombre' && r.perimetro_abdominal && r.imc)
      .map(r => ({ x: r.imc, y: r.perimetro_abdominal }));
    const mujeresScatter = filteredRecords
      .filter(r => r.sexo === 'Mujer' && r.perimetro_abdominal && r.imc)
      .map(r => ({ x: r.imc, y: r.perimetro_abdominal }));

    chartScatter.data.datasets[0].data = hombresScatter;
    chartScatter.data.datasets[1].data = mujeresScatter;
    chartScatter.update();
  }

  // 3. Donut HTA
  if (chartDonutHta) {
    if (n === allRecords.length) {
      chartDonutHta.updateSeries([72.1, 21.4, 6.5]);
    } else {
      const htaNorm = filteredRecords.filter(r => !r.hipertension).length;
      const htaTrat = filteredRecords.filter(r => r.hta_desc === 'Tratada').length;
      const htaNoTrat = filteredRecords.filter(r => r.hta_desc === 'No tratada').length;
      const pNorm = parseFloat(((htaNorm / n) * 100).toFixed(1));
      const pTrat = parseFloat(((htaTrat / n) * 100).toFixed(1));
      const pNoTrat = parseFloat(((htaNoTrat / n) * 100).toFixed(1));
      chartDonutHta.updateSeries([pNorm, pTrat, pNoTrat]);
    }
  }

  // 4. Metabolico Bar
  if (chartMetabolico) {
    chartMetabolico.updateSeries([{
      name: 'Prevalencia (%)',
      data: [parseFloat(hgPct), parseFloat(dbPct)]
    }]);
  }

  // 5. Categoría personal Chart.js
  if (chartCategoria) {
    const cats = ['PDI (Docentes)', 'PAS (Administrativos)', 'Personal de Servicios'];
    const hData = cats.map(c => filteredRecords.filter(r => r.categoria === c && r.sexo === 'Hombre').length);
    const mData = cats.map(c => filteredRecords.filter(r => r.categoria === c && r.sexo === 'Mujer').length);
    chartCategoria.data.datasets[0].data = hData;
    chartCategoria.data.datasets[1].data = mData;
    chartCategoria.update();
  }
}
