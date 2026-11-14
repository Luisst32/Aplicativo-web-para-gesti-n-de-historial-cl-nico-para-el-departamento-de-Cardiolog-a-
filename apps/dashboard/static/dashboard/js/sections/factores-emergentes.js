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
        chart: { type: 'bar', height: 380, toolbar: { show: false }, animations: { enabled: false } },
        fill: { type: 'solid', opacity: 1 },
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
        chart: { type: 'bar', height: 380, toolbar: { show: false }, animations: { enabled: false } },
        fill: { type: 'solid', opacity: 1 },
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

