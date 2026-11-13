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
        chart: { type: 'bar', height: 260, toolbar: { show: false }, animations: { enabled: false } },
        fill: { type: 'solid', opacity: 1 },
        colors: [PALETTE.iceBlue, PALETTE.green, PALETTE.yellow, PALETTE.emergencyRed, '#DC2626', '#991B1B'],
        plotOptions: {
          bar: {
            distributed: true,
            borderRadius: 5,
            dataLabels: { position: 'top' }
          }
        },
        series: [{ name: 'Casos', data: imcCounts }],
        xaxis: { categories: imcCats },
        yaxis: {
          max: (maxVal) => Math.ceil(maxVal * 1.25)
        },
        legend: { show: false },
        dataLabels: apexCountAndPctDataLabel(null, { offsetY: -20 }),
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
        chart: { type: 'bar', height: 260, toolbar: { show: false }, animations: { enabled: false } },
        fill: { type: 'solid', opacity: 1 },
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

