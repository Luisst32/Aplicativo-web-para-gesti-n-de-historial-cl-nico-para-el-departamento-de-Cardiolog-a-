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
      charts.ncComorb = createDashboardApexChart(elComorb, {
        chart: { type: 'bar', height: 320, toolbar: { show: false }, animations: { enabled: false } },
        fill: { type: 'solid', opacity: 1 },
        plotOptions: { bar: { horizontal: true, distributed: true, barHeight: '78%', borderRadius: 6, dataLabels: { position: 'center' }, colors: { backgroundBarColors: ['#f1f5f9'], backgroundBarRadius: 6 } } },
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
      charts.ncMental = createDashboardChart(ctxMental, {
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
      charts.ncResp = createDashboardChart(ctxResp, {
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
      charts.ncReuma = createDashboardApexChart(elReuma, {
        chart: { type: 'bar', height: 320, toolbar: { show: false }, animations: { enabled: false } },
        fill: { type: 'solid', opacity: 1 },
        colors: [PALETTE.purple, PALETTE.teal],
        plotOptions: { bar: { horizontal: true, barHeight: '78%', distributed: true, borderRadius: 6, dataLabels: { position: 'center' }, colors: { backgroundBarColors: ['#f1f5f9'], backgroundBarRadius: 6 } } },
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

