/**
 * CARDIOUNEMI - Dashboard Epidemiológico y Clínico.
 * Motor dinámico de analítica y agregación estadística en tiempo real.
 * Consume registros clínicos reales generados desde PostgreSQL.
 */

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

// Paleta de colores institucional y semafórica
const PALETTE = {
  canvas: '#FFFFFF',
  iceBlue: '#CFE9FF',
  primaryBlue: '#3AA0FF',
  emergencyRed: '#FF5A5F',
  navy: '#1B2A41',
  green: '#10B981',
  yellow: '#F59E0B'
};

// Navegación entre pestañas temáticas
function switchTab(tabId, element) {
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  if (element) element.classList.add('active');

  document.querySelectorAll('.tab-view').forEach(view => view.classList.remove('active'));
  const targetView = document.getElementById('tab-' + tabId);
  if (targetView) targetView.classList.add('active');

  // Actualizar título de vista activa
  const titleEl = document.getElementById('view-title');
  if (titleEl) {
    switch (tabId) {
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
  }

  // Redibujar gráficos si es necesario por resize del contenedor
  setTimeout(() => {
    window.dispatchEvent(new Event('resize'));
  }, 60);
}

// Inicialización al cargar el DOM
document.addEventListener('DOMContentLoaded', async () => {
  // Intentar cargar datos desde el script JSON embebido
  const embeddedDataEl = document.getElementById('dashboard-records-data');
  if (embeddedDataEl && embeddedDataEl.textContent.trim()) {
    try {
      allRecords = JSON.parse(embeddedDataEl.textContent);
    } catch (e) {
      console.warn('Error al parsear datos embebidos, solicitando vía API:', e);
    }
  }

  // Si no había datos embebidos o estaban vacíos, consultar la API REST
  if (!allRecords || allRecords.length === 0) {
    try {
      const response = await fetch('/dashboard/api/data/');
      if (response.ok) {
        const payload = await response.json();
        allRecords = payload.records || [];
      }
    } catch (err) {
      console.error('Error al consultar /dashboard/api/data/:', err);
    }
  }

  // Sincronizar opciones dinámicas de slicers con los datos reales
  syncSlicerOptions();

  // Inicializar registros filtrados con la muestra completa
  filteredRecords = [...allRecords];

  // Inicializar gráficos
  initAllCharts();

  // Actualizar KPIs, tablas y series con datos reales
  updateDashboard();
});

// Sincroniza dinámicamente los selectores con las cohortes reales existentes
function syncSlicerOptions() {
  if (!allRecords || allRecords.length === 0) return;

  // Años
  const yearSelect = document.getElementById('slicer-ano');
  if (yearSelect) {
    const existingYears = Array.from(yearSelect.options).map(o => o.value);
    const uniqueYears = [...new Set(allRecords.map(r => r.ano))].filter(Boolean).sort((a, b) => b - a);
    uniqueYears.forEach(y => {
      const valStr = String(y);
      if (!existingYears.includes(valStr)) {
        const opt = document.createElement('option');
        opt.value = valStr;
        opt.textContent = `Año ${y}`;
        yearSelect.appendChild(opt);
      }
    });
  }

  // Categorías
  const catSelect = document.getElementById('slicer-cat');
  if (catSelect) {
    const existingCats = Array.from(catSelect.options).map(o => o.value);
    const uniqueCats = [...new Set(allRecords.map(r => r.categoria))].filter(Boolean).sort();
    uniqueCats.forEach(c => {
      if (!existingCats.includes(c)) {
        const opt = document.createElement('option');
        opt.value = c;
        opt.textContent = c;
        catSelect.appendChild(opt);
      }
    });
  }
}

// Controlador de cambio de Slicers interactivos
function onSlicerChange() {
  const selAno = document.getElementById('slicer-ano') ? document.getElementById('slicer-ano').value : 'all';
  const selCat = document.getElementById('slicer-cat') ? document.getElementById('slicer-cat').value : 'all';
  const selSexo = document.getElementById('slicer-sexo') ? document.getElementById('slicer-sexo').value : 'all';
  const selEdad = document.getElementById('slicer-edad') ? document.getElementById('slicer-edad').value : 'all';
  const selRiesgo = document.getElementById('slicer-riesgo') ? document.getElementById('slicer-riesgo').value : 'all';

  filteredRecords = allRecords.filter(r => {
    if (selAno !== 'all' && r.ano !== parseInt(selAno, 10)) return false;
    if (selCat !== 'all' && r.categoria !== selCat) return false;
    if (selSexo !== 'all' && r.sexo !== selSexo) return false;
    if (selEdad !== 'all' && r.grupo_edad !== selEdad) return false;
    if (selRiesgo !== 'all' && r.riesgo_global !== selRiesgo) return false;
    return true;
  });

  updateDashboard();
}

// Restablecer Slicers a vista global
function resetSlicers() {
  if (document.getElementById('slicer-ano')) document.getElementById('slicer-ano').value = 'all';
  if (document.getElementById('slicer-cat')) document.getElementById('slicer-cat').value = 'all';
  if (document.getElementById('slicer-sexo')) document.getElementById('slicer-sexo').value = 'all';
  if (document.getElementById('slicer-edad')) document.getElementById('slicer-edad').value = 'all';
  if (document.getElementById('slicer-riesgo')) document.getElementById('slicer-riesgo').value = 'all';
  filteredRecords = [...allRecords];
  updateDashboard();
}

// Actualización de todo el Dashboard
function updateDashboard() {
  const n = filteredRecords.length;
  const total = allRecords.length;
  const pct = total > 0 ? ((n / total) * 100).toFixed(1) : 0;

  // Badge superior de muestra activa
  const sampleBadge = document.getElementById('active-sample-count');
  if (sampleBadge) {
    sampleBadge.innerText = `${n} de ${total} evaluados (${pct}%)`;
  }

  // 1. Cálculos de Factores Clínicos y Estilo de Vida
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

  // Actualizar Tarjetas KPI Principales
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

  function updateKpiVal(id, valPct, colorClass) {
    const el = document.getElementById(id);
    if (el) {
      el.innerText = valPct.toFixed(1).replace('.', ',') + ' %';
      el.className = 'kpi-value ' + colorClass;
    }
  }

  // Semáforo epidemiológico en tarjetas de factores clínicos
  updateKpiVal('kpi-hta', htaPct, htaPct >= 25 ? 'color-semaforo-red' : (htaPct >= 15 ? 'color-semaforo-yellow' : 'color-semaforo-green'));
  updateKpiVal('kpi-dl', dlPct, dlPct >= 40 ? 'color-semaforo-red' : (dlPct >= 20 ? 'color-semaforo-yellow' : 'color-semaforo-green'));
  updateKpiVal('kpi-sp-ob', spObPct, spObPct >= 75 ? 'color-semaforo-red' : (spObPct >= 50 ? 'color-semaforo-yellow' : 'color-semaforo-green'));
  updateKpiVal('kpi-riesgo-alto', riesgoAltoPct, riesgoAltoPct >= 25 ? 'color-semaforo-red' : (riesgoAltoPct >= 15 ? 'color-semaforo-yellow' : 'color-semaforo-green'));

  // Semáforo epidemiológico en estilo de vida
  updateKpiVal('kpi-act-fisica', actPct, actPct >= 50 ? 'color-semaforo-green' : (actPct >= 30 ? 'color-semaforo-yellow' : 'color-semaforo-red'));
  updateKpiVal('kpi-frutas', frutaPct, frutaPct >= 45 ? 'color-semaforo-green' : (frutaPct >= 25 ? 'color-semaforo-yellow' : 'color-semaforo-red'));
  updateKpiVal('kpi-estres', estresPct, estresPct >= 30 ? 'color-semaforo-red' : (estresPct >= 15 ? 'color-semaforo-yellow' : 'color-semaforo-green'));
  updateKpiVal('kpi-sueno-malo', suenoMaloPct, suenoMaloPct >= 25 ? 'color-semaforo-red' : (suenoMaloPct >= 15 ? 'color-semaforo-yellow' : 'color-semaforo-green'));
  updateKpiVal('kpi-tabaco', tabacoPct, tabacoPct <= 10 ? 'color-semaforo-green' : (tabacoPct <= 20 ? 'color-semaforo-yellow' : 'color-semaforo-red'));

  // 2. Actualizar Tablas Dinámicas
  updateTables(n, htaCount, dlCount, spObCount, obCount, dbCount, hgCount, tabacoCount);

  // 3. Actualizar Gráficos Visuales
  updateCharts(n);
}

// Actualización de Tablas Dinámicas
function updateTables(n, hta, dl, spOb, ob, db, hg, tabaco) {
  const tfootEl = document.getElementById('tfoot-casos-clinicos');
  if (tfootEl) tfootEl.innerText = n;

  const items = [
    { nombre: 'Dislipemia (Colesterol/Triglicéridos)', casos: dl, pct: n > 0 ? ((dl / n) * 100).toFixed(1) : '0.0', control: 'Alta prevalencia metabólica', dotClass: 'dot-yellow' },
    { nombre: 'Hipertensión Arterial (HTA)', casos: hta, pct: n > 0 ? ((hta / n) * 100).toFixed(1) : '0.0', control: 'Riesgo coronario directo', dotClass: 'dot-red' },
    { nombre: 'Sobrepeso y Obesidad (IMC ≥ 25)', casos: spOb, pct: n > 0 ? ((spOb / n) * 100).toFixed(1) : '0.0', control: 'Mayoría de la población', dotClass: 'dot-yellow' },
    { nombre: 'Obesidad Marcada (IMC ≥ 30)', casos: ob, pct: n > 0 ? ((ob / n) * 100).toFixed(1) : '0.0', control: 'Requiere manejo clínico', dotClass: 'dot-red' },
    { nombre: 'Hígado Graso (Esteatosis)', casos: hg, pct: n > 0 ? ((hg / n) * 100).toFixed(1) : '0.0', control: 'Identificado en ecografía', dotClass: 'dot-yellow' },
    { nombre: 'Diabetes Mellitus (Tipo 2)', casos: db, pct: n > 0 ? ((db / n) * 100).toFixed(1) : '0.0', control: 'Control glucémico estricto', dotClass: 'dot-red' },
    { nombre: 'Tabaquismo Activo', casos: tabaco, pct: n > 0 ? ((tabaco / n) * 100).toFixed(1) : '0.0', control: 'Prevalencia baja favorable', dotClass: 'dot-green' }
  ];

  const tbody = document.getElementById('tbody-factores-clinicos');
  if (tbody) {
    tbody.innerHTML = items.map(item => `
      <tr>
        <td><strong>${item.nombre}</strong></td>
        <td>${item.casos}</td>
        <td>${item.pct}%</td>
        <td><span class="status-dot-indicator ${item.dotClass}"></span> ${item.control}</td>
      </tr>
    `).join('');
  }

  // Tabla Semáforo por Categoría Profesional calculada con datos reales
  const categorias = ['PDI (Docentes)', 'PAS (Administrativos)', 'Personal de Servicios', 'Estudiantes'];
  const tbodyCat = document.getElementById('tbody-semaforo-categorias');

  if (tbodyCat) {
    tbodyCat.innerHTML = categorias.map(cat => {
      const sub = filteredRecords.filter(r => r.categoria === cat);
      const subN = sub.length;
      if (subN === 0) return '';

      const cHta = (sub.filter(r => r.hipertension).length / subN * 100).toFixed(1);
      const cDl = (sub.filter(r => r.dislipemia).length / subN * 100).toFixed(1);
      const cOb = (sub.filter(r => r.obesidad).length / subN * 100).toFixed(1);
      const cAct = (sub.filter(r => r.actividad_fisica).length / subN * 100).toFixed(1);

      let semaforo = '<span class="status-dot-indicator dot-green"></span> Moderado';
      if (parseFloat(cHta) >= 32.0 || parseFloat(cOb) >= 38.0) {
        semaforo = '<span class="status-dot-indicator dot-red"></span> Riesgo Elevado';
      } else if (parseFloat(cHta) > 25.0 || parseFloat(cOb) > 30.0) {
        semaforo = '<span class="status-dot-indicator dot-yellow"></span> Alerta Preventiva';
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
}

// Inicialización de Gráficos
function initAllCharts() {
  // 1. Tendencia Temporal (ApexCharts)
  const optTendencia = {
    series: [
      { name: 'Evaluaciones Realizadas', data: [] },
      { name: 'Casos Hipertensión', data: [] }
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
      categories: [],
      axisBorder: { color: '#E2E8F0' }
    },
    yaxis: {
      title: { text: 'Participantes', style: { color: '#64748B', fontWeight: 600 } }
    },
    grid: { borderColor: '#EEF2F6' },
    tooltip: { theme: 'light' }
  };
  const elTendencia = document.querySelector("#chart-tendencia-temporal");
  if (elTendencia) {
    chartTendencia = new ApexCharts(elTendencia, optTendencia);
    chartTendencia.render();
  }

  // 2. Factores Modificables Horizontales (ApexCharts)
  const optFactores = {
    series: [{ name: 'Prevalencia (%)', data: [0, 0, 0, 0, 0, 0] }],
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
      max: 100
    },
    legend: { show: false },
    grid: { borderColor: '#EEF2F6' }
  };
  const elFactores = document.querySelector("#chart-factores-modificables");
  if (elFactores) {
    chartFactores = new ApexCharts(elFactores, optFactores);
    chartFactores.render();
  }

  // 3. Distribución por Categoría de Personal (Chart.js)
  const ctxCat = document.getElementById('chart-categoria-personal');
  if (ctxCat) {
    chartCategoria = new Chart(ctxCat.getContext('2d'), {
      type: 'bar',
      data: {
        labels: ['PDI (Docentes)', 'PAS (Administrativos)', 'Servicios', 'Estudiantes'],
        datasets: [
          {
            label: 'Hombres',
            data: [0, 0, 0, 0],
            backgroundColor: 'rgba(58, 160, 255, 0.85)',
            borderRadius: 5
          },
          {
            label: 'Mujeres',
            data: [0, 0, 0, 0],
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
          y: { grid: { color: '#EEF2F6' }, beginAtZero: true }
        }
      }
    });
  }

  // 4. Género y Nivel de Riesgo (Chart.js)
  const ctxGen = document.getElementById('chart-genero-riesgo');
  if (ctxGen) {
    chartGenero = new Chart(ctxGen.getContext('2d'), {
      type: 'bar',
      data: {
        labels: ['Bajo (0 f.)', 'Moderado (1 f.)', 'Alto (2-3 f.)', 'Muy Alto (4+ f.)'],
        datasets: [
          {
            label: 'Hombres',
            data: [0, 0, 0, 0],
            backgroundColor: PALETTE.primaryBlue,
            borderRadius: 4
          },
          {
            label: 'Mujeres',
            data: [0, 0, 0, 0],
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
        scales: { y: { grid: { color: '#EEF2F6' }, beginAtZero: true }, x: { grid: { display: false } } }
      }
    });
  }

  // 5. Donut Presión Arterial (ApexCharts)
  const optDonutHta = {
    series: [100, 0, 0],
    labels: ['Normotensos (PA Normal)', 'HTA Tratada Farmacológicamente', 'HTA No Tratada'],
    chart: { type: 'donut', height: 280, fontFamily: 'Inter' },
    colors: [PALETTE.green, PALETTE.yellow, PALETTE.emergencyRed],
    legend: { position: 'bottom' },
    dataLabels: { enabled: true, formatter: val => val.toFixed(1) + '%' },
    tooltip: {
      y: {
        formatter: (val) => `${val.toFixed(1)} %`
      }
    }
  };
  const elDonutHta = document.querySelector("#chart-donut-hta");
  if (elDonutHta) {
    chartDonutHta = new ApexCharts(elDonutHta, optDonutHta);
    chartDonutHta.render();
  }

  // 6. Scatter Plot IMC vs Perímetro Abdominal (Chart.js)
  const ctxScatter = document.getElementById('chart-scatter-imc-cintura');
  if (ctxScatter) {
    chartScatter = new Chart(ctxScatter.getContext('2d'), {
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
            grid: { color: '#EEF2F6' }
          },
          y: {
            title: { display: true, text: 'Perímetro Abdominal (cm)' },
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
  }

  // 7. Riesgo por Grupo de Edad (Chart.js)
  const ctxEdad = document.getElementById('chart-riesgo-por-edad');
  if (ctxEdad) {
    chartEdad = new Chart(ctxEdad.getContext('2d'), {
      type: 'bar',
      data: {
        labels: ['<40 años', '40-49 años', '50-59 años', '60+ años'],
        datasets: [
          { label: '% Hipertensión', data: [0, 0, 0, 0], backgroundColor: PALETTE.emergencyRed, borderRadius: 4 },
          { label: '% Dislipemia', data: [0, 0, 0, 0], backgroundColor: PALETTE.primaryBlue, borderRadius: 4 }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { y: { max: 100, beginAtZero: true, grid: { color: '#EEF2F6' } }, x: { grid: { display: false } } }
      }
    });
  }

  // 8. Hígado Graso y Diabetes (ApexCharts)
  const optMetabolico = {
    series: [{ name: 'Prevalencia (%)', data: [0, 0] }],
    chart: { type: 'bar', height: 280, toolbar: { show: false }, fontFamily: 'Inter' },
    colors: [PALETTE.primaryBlue, PALETTE.emergencyRed],
    xaxis: { categories: ['Hígado Graso', 'Diabetes Mellitus'] },
    plotOptions: { bar: { columnWidth: '45%', distributed: true, borderRadius: 6 } },
    legend: { show: false },
    grid: { borderColor: '#EEF2F6' }
  };
  const elMetabolico = document.querySelector("#chart-bar-metabolico");
  if (elMetabolico) {
    chartMetabolico = new ApexCharts(elMetabolico, optMetabolico);
    chartMetabolico.render();
  }

  // 9. Actividad Física por Categoría (ApexCharts)
  const optActCat = {
    series: [
      { name: 'Realiza Actividad Física (%)', data: [0, 0, 0] },
      { name: 'Sedentarios (%)', data: [0, 0, 0] }
    ],
    chart: { type: 'bar', height: 280, stacked: true, toolbar: { show: false }, fontFamily: 'Inter' },
    colors: [PALETTE.primaryBlue, PALETTE.iceBlue],
    plotOptions: { bar: { horizontal: true, barHeight: '55%', borderRadius: 4 } },
    xaxis: { categories: ['PDI (Docentes)', 'PAS (Administrativos)', 'Servicios'] },
    legend: { position: 'top' },
    grid: { borderColor: '#EEF2F6' }
  };
  const elActCat = document.querySelector("#chart-actividad-categoria");
  if (elActCat) {
    chartActividadCat = new ApexCharts(elActCat, optActCat);
    chartActividadCat.render();
  }

  // 10. Consumo de Alcohol (Chart.js Donut)
  const ctxAlcohol = document.getElementById('chart-consumo-alcohol');
  if (ctxAlcohol) {
    chartAlcohol = new Chart(ctxAlcohol.getContext('2d'), {
      type: 'doughnut',
      data: {
        labels: ['No consume', 'Ocasional', 'Semanal', 'Diario'],
        datasets: [{
          data: [100, 0, 0, 0],
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
}

// Actualización dinámica de datos de los gráficos con base en filteredRecords
function updateCharts(n) {
  if (n === 0) {
    // Si la muestra filtrada está vacía, limpiar series
    if (chartFactores) chartFactores.updateSeries([{ name: 'Prevalencia (%)', data: [0, 0, 0, 0, 0, 0] }]);
    if (chartDonutHta) chartDonutHta.updateSeries([0, 0, 0]);
    if (chartMetabolico) chartMetabolico.updateSeries([{ name: 'Prevalencia (%)', data: [0, 0] }]);
    return;
  }

  // 1. Tendencia Temporal
  if (chartTendencia) {
    const years = [...new Set(allRecords.map(r => r.ano))].filter(Boolean).sort((a, b) => a - b);
    const evalData = years.map(y => filteredRecords.filter(r => r.ano === y).length);
    const htaData = years.map(y => filteredRecords.filter(r => r.ano === y && r.hipertension).length);

    chartTendencia.updateOptions({
      xaxis: { categories: years.map(y => `Cohorte ${y}`) }
    });
    chartTendencia.updateSeries([
      { name: 'Evaluaciones Realizadas', data: evalData },
      { name: 'Casos Hipertensión', data: htaData }
    ]);
  }

  // 2. Factores de Riesgo Modificables
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

  // 3. Distribución por Categoría de Personal (Chart.js)
  if (chartCategoria) {
    const cats = ['PDI (Docentes)', 'PAS (Administrativos)', 'Personal de Servicios', 'Estudiantes'];
    const hData = cats.map(c => filteredRecords.filter(r => r.categoria === c && r.sexo === 'Hombre').length);
    const mData = cats.map(c => filteredRecords.filter(r => r.categoria === c && r.sexo === 'Mujer').length);

    chartCategoria.data.labels = cats;
    chartCategoria.data.datasets[0].data = hData;
    chartCategoria.data.datasets[1].data = mData;
    chartCategoria.update();
  }

  // 4. Género y Nivel de Riesgo (Chart.js)
  if (chartGenero) {
    const riskLevels = ['Bajo (0 factores)', 'Moderado (1 factor)', 'Alto (2-3 factores)', 'Muy Alto (4+ factores)'];
    const hRisk = riskLevels.map(lvl => filteredRecords.filter(r => r.riesgo_global === lvl && r.sexo === 'Hombre').length);
    const mRisk = riskLevels.map(lvl => filteredRecords.filter(r => r.riesgo_global === lvl && r.sexo === 'Mujer').length);

    chartGenero.data.datasets[0].data = hRisk;
    chartGenero.data.datasets[1].data = mRisk;
    chartGenero.update();
  }

  // 5. Donut Presión Arterial (ApexCharts)
  if (chartDonutHta) {
    const htaNorm = filteredRecords.filter(r => !r.hipertension).length;
    const htaTrat = filteredRecords.filter(r => r.hta_desc === 'Tratada').length;
    const htaNoTrat = filteredRecords.filter(r => r.hta_desc === 'No tratada').length;

    const pNorm = parseFloat(((htaNorm / n) * 100).toFixed(1));
    const pTrat = parseFloat(((htaTrat / n) * 100).toFixed(1));
    const pNoTrat = parseFloat(((htaNoTrat / n) * 100).toFixed(1));

    chartDonutHta.updateSeries([pNorm, pTrat, pNoTrat]);
  }

  // 6. Scatter Plot IMC vs Perímetro Abdominal (Chart.js)
  if (chartScatter) {
    const hombresScatter = filteredRecords
      .filter(r => r.sexo === 'Hombre' && r.perimetro_abdominal && r.imc && r.imc > 0)
      .map(r => ({ x: r.imc, y: r.perimetro_abdominal }));
    const mujeresScatter = filteredRecords
      .filter(r => r.sexo === 'Mujer' && r.perimetro_abdominal && r.imc && r.imc > 0)
      .map(r => ({ x: r.imc, y: r.perimetro_abdominal }));

    chartScatter.data.datasets[0].data = hombresScatter;
    chartScatter.data.datasets[1].data = mujeresScatter;
    chartScatter.update();
  }

  // 7. Riesgo por Grupo de Edad (Chart.js)
  if (chartEdad) {
    const cohorts = ['<40 años', '40-49 años', '50-59 años', '60+ años'];
    const htaCohortData = cohorts.map(cohort => {
      const sub = filteredRecords.filter(r => r.grupo_edad === cohort);
      return sub.length > 0 ? parseFloat(((sub.filter(r => r.hipertension).length / sub.length) * 100).toFixed(1)) : 0;
    });
    const dlCohortData = cohorts.map(cohort => {
      const sub = filteredRecords.filter(r => r.grupo_edad === cohort);
      return sub.length > 0 ? parseFloat(((sub.filter(r => r.dislipemia).length / sub.length) * 100).toFixed(1)) : 0;
    });

    chartEdad.data.datasets[0].data = htaCohortData;
    chartEdad.data.datasets[1].data = dlCohortData;
    chartEdad.update();
  }

  // 8. Hígado Graso y Diabetes (ApexCharts)
  if (chartMetabolico) {
    chartMetabolico.updateSeries([{
      name: 'Prevalencia (%)',
      data: [parseFloat(hgPct), parseFloat(dbPct)]
    }]);
  }

  // 9. Actividad Física por Categoría (ApexCharts)
  if (chartActividadCat) {
    const actCats = ['PDI (Docentes)', 'PAS (Administrativos)', 'Personal de Servicios'];
    const actData = actCats.map(cat => {
      const sub = filteredRecords.filter(r => r.categoria === cat);
      return sub.length > 0 ? parseFloat(((sub.filter(r => r.actividad_fisica).length / sub.length) * 100).toFixed(1)) : 0;
    });
    const sedData = actData.map(v => parseFloat((100 - v).toFixed(1)));

    chartActividadCat.updateOptions({
      xaxis: { categories: actCats }
    });
    chartActividadCat.updateSeries([
      { name: 'Realiza Actividad Física (%)', data: actData },
      { name: 'Sedentarios (%)', data: sedData }
    ]);
  }

  // 10. Consumo de Alcohol (Chart.js Donut)
  if (chartAlcohol) {
    const alcLabels = ['No consume', 'Ocasional', 'Semanal', 'Diario'];
    const alcData = alcLabels.map(lvl => {
      const count = filteredRecords.filter(r => r.alcohol === lvl).length;
      return n > 0 ? parseFloat(((count / n) * 100).toFixed(1)) : 0;
    });

    chartAlcohol.data.datasets[0].data = alcData;
    chartAlcohol.update();
  }
}
