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
      charts.covHist = createDashboardApexChart(elHist, {
        chart: { type: 'bar', height: 320, toolbar: { show: false }, animations: { enabled: false } },
        fill: { type: 'solid', opacity: 1 },
        colors: [PALETTE.yellow, PALETTE.emergencyRed, PALETTE.green],
        plotOptions: {
          bar: {
            horizontal: true,
            barHeight: '78%',
            distributed: true,
            borderRadius: 6,
            dataLabels: { position: 'center' }
          }
        },
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
      charts.covSec = createDashboardChart(ctxSec, {
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
      charts.covCat = createDashboardApexChart(elPorCat, {
        chart: { type: 'bar', height: 320, toolbar: { show: false }, animations: { enabled: false } },
        fill: { type: 'solid', opacity: 1 },
        colors: [PALETTE.primaryBlue, PALETTE.emergencyRed],
        plotOptions: { bar: { horizontal: true, barHeight: '78%', borderRadius: 6, dataLabels: { position: 'center' }, colors: { backgroundBarColors: ['#f1f5f9'], backgroundBarRadius: 6 } } },
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
      charts.covGen = createDashboardChart(ctxGen, {
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

