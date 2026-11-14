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
        chart: { type: 'area', height: 320, toolbar: { show: false }, fontFamily: 'inherit', foreColor: '#1e293b', fontSize: '12px' },
        grid: { borderColor: '#e8eef5', strokeDashArray: 4 },
        markers: { size: 4, strokeWidth: 3, strokeColors: '#ffffff', hover: { size: 6 } },
        yaxis: { min: 0, labels: { formatter: val => Math.round(val) } },
        colors: [PALETTE.primaryBlue],
        stroke: { curve: 'smooth', width: 3 },
        fill: { type: 'gradient', gradient: { shadeIntensity: 0, opacityFrom: 0.22, opacityTo: 0.02 } },
        series: [{ name: 'Evaluados', data: yearData }],
        xaxis: { categories: years.map(y => `Año ${y}`) },
        dataLabels: {
          enabled: true,
          formatter: val => `${val} (${formatPct(val, filteredRecords.length)}%)`,
          offsetY: -10,
          style: { fontSize: '12px', fontWeight: 700, colors: ['#0f172a'] },
          background: { enabled: false }
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
        chart: { type: 'bar', height: 320, toolbar: { show: false }, animations: { enabled: false }, fontFamily: 'inherit', foreColor: '#1e293b', fontSize: '12px' },
        grid: { borderColor: '#e8eef5', strokeDashArray: 4, padding: { right: 16 } },
        fill: { type: 'solid', opacity: 1 },
        plotOptions: { bar: { horizontal: true, distributed: true, borderRadius: 6, barHeight: '48%', colors: { backgroundBarColors: ['#f1f5f9'], backgroundBarRadius: 6 } } },
        colors: [PALETTE.emergencyRed, PALETTE.yellow, PALETTE.yellow, PALETTE.primaryBlue, PALETTE.green, PALETTE.purple],
        series: [{ name: 'Prevalencia (%)', data: fData }],
        xaxis: { categories: fLabels, max: 100, tickAmount: 4, axisBorder: { show: false }, axisTicks: { show: false }, labels: { formatter: val => `${Math.round(val)} %` } },
        legend: { show: false },
        dataLabels: {
          enabled: true,
          formatter: (val) => {
            const total = filteredRecords.length || 1;
            const casos = Math.round((parseFloat(val) * total) / 100);
            return `${casos} (${val}%)`;
          },
          style: { fontSize: '12px', fontWeight: 700, colors: ['#0f172a'] },
          background: { enabled: false }
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
            backgroundColor: [PALETTE.primaryBlue, PALETTE.yellow, PALETTE.green, PALETTE.purple, PALETTE.navy],
            borderColor: '#ffffff', borderWidth: 4, borderRadius: 5, hoverOffset: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '52%',
          layout: { padding: 12 },
          plugins: {
            legend: { position: 'bottom', labels: { usePointStyle: true, pointStyle: 'circle', boxWidth: 10, padding: 18, color: '#0f172a', font: { size: 12, weight: '600' } } },
            datalabels: {
              ...chartJsDonutDataLabels(),
              color: '#ffffff',
              anchor: 'center', align: 'center', textAlign: 'center',
              font: { size: 12, weight: 'bold' },
              formatter: (val, ctx) => {
                const total = ctx.dataset.data.reduce((sum, value) => sum + value, 0);
                return [String(val), `${formatPct(val, total)} %`];
              }
            }
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
            { label: 'Hombres', data: hRiesgo, backgroundColor: PALETTE.primaryBlue, maxBarThickness: 76, categoryPercentage: 0.8, barPercentage: 0.9, borderRadius: 4 },
            { label: 'Mujeres', data: mRiesgo, backgroundColor: PALETTE.purple, maxBarThickness: 76, categoryPercentage: 0.8, barPercentage: 0.9, borderRadius: 4 }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: { top: 25, right: 8, bottom: 4, left: 4 } },
          scales: {
            x: { stacked: true, grid: { display: false }, border: { display: false }, ticks: { color: '#1e293b', font: { size: 12, weight: '600' } } },
            y: {
              stacked: true,
              grid: { color: '#edf2f7' },
              border: { display: false },
              ticks: { precision: 0, color: '#1e293b', font: { size: 12, weight: '600' } },
              beginAtZero: true,
              grace: '20%',
              title: { display: true, text: 'Casos (n)', font: { size: 11, weight: 'bold' } }
            }
          },
          plugins: {
            legend: { position: 'bottom', labels: { usePointStyle: true, pointStyle: 'circle', padding: 20, boxWidth: 10, color: '#0f172a', font: { size: 13, weight: '600' } } },
            datalabels: {
              display: (ctx) => ctx.dataset.data[ctx.dataIndex] > 0,
              color: '#ffffff',
              anchor: 'center',
              align: 'center',
              backgroundColor: 'transparent',
              borderRadius: 0,
              padding: { top: 1, bottom: 1, left: 2, right: 2 },
              borderWidth: 0,
              font: { weight: 'bold', size: 11 },
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

