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
      charts.emSueno = createDashboardApexChart(elSueno, {
        chart: { type: 'bar', height: 320, toolbar: { show: false }, animations: { enabled: false } },
        fill: { type: 'solid', opacity: 1 },
        colors: [PALETTE.green, PALETTE.emergencyRed, PALETTE.primaryBlue, PALETTE.yellow],
        plotOptions: { bar: { horizontal: true, barHeight: '78%', distributed: true, borderRadius: 6, dataLabels: { position: 'center' }, colors: { backgroundBarColors: ['#f1f5f9'], backgroundBarRadius: 6 } } },
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
      charts.emEstres = createDashboardChart(ctxEstres, {
        type: 'doughnut',
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

  // Personalidad Tipo A (Donut con leyenda detallada y etiquetas de valor blancas canónicas)
  const persSi = filteredRecords.filter(r => r.personalidad_tipo_a === true).length;
  const persNo = filteredRecords.filter(r => r.personalidad_tipo_a === false).length;
  const persTotal = persSi + persNo;
  const persLabels = [
    `Con Personalidad Tipo A: ${persSi} (${formatPct(persSi, persTotal)}%)`,
    `Sin Personalidad Tipo A: ${persNo} (${formatPct(persNo, persTotal)}%)`
  ];

  const ctxPers = document.getElementById('chart-em-personalidad-a');
  if (ctxPers && dashboardHasChartData('chart-em-personalidad-a', 'emPers', persTotal)) {
    if (charts.emPers && typeof charts.emPers.update === 'function' && charts.emPers.config.type === 'doughnut') {
      charts.emPers.data.labels = persLabels;
      charts.emPers.data.datasets[0].data = [persSi, persNo];
      charts.emPers.update();
    } else {
      if (charts.emPers && typeof charts.emPers.destroy === 'function') {
        charts.emPers.destroy();
      }
      charts.emPers = createDashboardChart(ctxPers, {
        type: 'doughnut',
        data: {
          labels: persLabels,
          datasets: [{
            data: [persSi, persNo],
            backgroundColor: [PALETTE.emergencyRed, PALETTE.teal]
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

  // Factores Ginecológicos y Exposición Laboral (Gráfico horizontal individualizado por factor)
  const emItems = [
    { label: 'Mal Clima Laboral', field: 'mal_ambiente_laboral', color: PALETTE.yellow },
    { label: 'Tóxicos Ocupacionales', field: 'toxicos_laboral', color: PALETTE.purple },
    { label: 'Bajos Estrógenos / Menopausia', field: 'bajos_estrogenos', color: PALETTE.emergencyRed },
    { label: 'Anticonceptivos > 35 años', field: 'anticonceptivos_35', color: PALETTE.teal }
  ];

  const emCounts = emItems.map(item => filteredRecords.filter(r => r[item.field] === true).length);
  const emDenominators = emItems.map(item => filteredRecords.filter(r => r[item.field] === true || r[item.field] === false).length);
  const emTotalAnswered = emDenominators.reduce((a, b) => a + b, 0);

  const elHorm = document.getElementById('chart-em-hormonas-ambiente');
  if (elHorm && dashboardHasChartData('chart-em-hormonas-ambiente', 'emHorm', emTotalAnswered)) {
    const maxVal = Math.max(...emCounts, 0);
    const hormOptions = {
      chart: { type: 'bar', height: 360, toolbar: { show: false }, animations: { enabled: false } },
      fill: { type: 'solid', opacity: 1 },
      colors: emItems.map(item => item.color),
      plotOptions: {
        bar: {
          horizontal: true,
          barHeight: '82%',
          distributed: true,
          borderRadius: 6,
          dataLabels: { position: 'center' },
          colors: { backgroundBarColors: ['#f1f5f9'], backgroundBarRadius: 6 }
        }
      },
      series: [{ name: 'Casos', data: emCounts }],
      xaxis: {
        categories: emItems.map(item => item.label),
        min: 0,
        max: Math.max(3, maxVal + 1),
        tickAmount: Math.max(3, maxVal + 1),
        labels: { formatter: val => Math.round(val) }
      },
      legend: { show: false },
      dataLabels: {
        enabled: true,
        formatter: (val, opt) => {
          if (!val || val <= 0) return '';
          const idx = opt?.dataPointIndex ?? 0;
          const valid = emDenominators[idx] || 0;
          const pct = valid > 0 ? ((val / valid) * 100).toFixed(1).replace('.', ',') : '0,0';
          return `${val} (${pct}%)`;
        },
        style: { fontSize: '11px', fontWeight: 'bold', fontFamily: 'inherit', colors: ['#ffffff'] },
        dropShadow: UNIVERSAL_VALUE_LABEL_STYLE.apexDropShadow,
        background: { enabled: false }
      },
      tooltip: {
        y: {
          formatter: (val, opt) => {
            const idx = opt?.dataPointIndex ?? 0;
            const valid = emDenominators[idx] || 0;
            const pct = valid > 0 ? ((val / valid) * 100).toFixed(1).replace('.', ',') : '0,0';
            return `${val} de ${valid} (${pct}%)`;
          }
        }
      }
    };
    if (charts.emHorm && typeof charts.emHorm.updateOptions === 'function') {
      charts.emHorm.updateOptions(hormOptions);
    } else {
      if (charts.emHorm && typeof charts.emHorm.destroy === 'function') {
        charts.emHorm.destroy();
      }
      charts.emHorm = createDashboardApexChart(elHorm, hormOptions);
      charts.emHorm.render();
    }
  }

  // 5. FASE 3: Cruce Estrés x Calidad de Sueño x HTA
  const crossGroups = [
    { label: 'Estrés Alto + Mal Sueño', filter: r => (r.estres === 'Alto' || r.estres_laboral === true || r.estres_familiar === true) && (r.calidad_sueno === 'Mala') },
    { label: 'Estrés Alto + Buen Sueño', filter: r => (r.estres === 'Alto' || r.estres_laboral === true || r.estres_familiar === true) && (r.calidad_sueno === 'Buena') },
    { label: 'Bajo Estrés + Mal Sueño', filter: r => (r.estres !== 'Alto' && !r.estres_laboral && !r.estres_familiar) && (r.calidad_sueno === 'Mala') },
    { label: 'Bajo Estrés + Buen Sueño', filter: r => (r.estres !== 'Alto' && !r.estres_laboral && !r.estres_familiar) && (r.calidad_sueno === 'Buena') }
  ];

  const crossData = crossGroups.map(g => {
    const subset = filteredRecords.filter(r => typeof r.hipertension === 'boolean' || r.hipertension === 'Si' || r.hipertension === 'No').filter(g.filter);
    const cases = subset.filter(r => r.hipertension === true || r.hipertension === 'Si').length;
    const valid = subset.length;
    const pct = valid > 0 ? Number(((cases / valid) * 100).toFixed(1)) : 0;
    return { label: g.label, cases, valid, pct };
  });

  const elCross = document.getElementById('chart-em-estres-sueno-hta');
  if (elCross && dashboardHasChartData('chart-em-estres-sueno-hta', 'emCross', crossData.reduce((a, b) => a + b.valid, 0))) {
    const crossOptions = {
      chart: { type: 'bar', height: 320, toolbar: { show: false }, animations: { enabled: false } },
      plotOptions: { bar: { horizontal: false, columnWidth: '50%', distributed: true, borderRadius: 6, dataLabels: { position: 'center' } } },
      colors: [PALETTE.emergencyRed, PALETTE.yellow, PALETTE.teal, PALETTE.green],
      series: [{ name: '% Hipertensión', data: crossData.map(d => d.pct) }],
      xaxis: { categories: crossData.map(d => d.label) },
      yaxis: { min: 0, max: 100, labels: { formatter: val => `${Math.round(val)}%` }, title: { text: '% Prevalencia HTA' } },
      legend: { show: false },
      dataLabels: {
        enabled: true,
        formatter: (val, opt) => {
          const d = crossData[opt.dataPointIndex];
          return d && d.valid > 0 ? `${d.cases} de ${d.valid} (${val}%)` : '0%';
        },
        style: { fontSize: '11px', fontWeight: 'bold', fontFamily: 'inherit', colors: ['#ffffff'] },
        dropShadow: UNIVERSAL_VALUE_LABEL_STYLE.apexDropShadow,
        background: { enabled: false }
      },
      tooltip: {
        y: {
          formatter: (val, opt) => {
            const d = crossData[opt.dataPointIndex];
            return d ? formatWilsonCiLabel(d.cases, d.valid) : `${val}%`;
          }
        }
      }
    };
    if (charts.emCross) charts.emCross.updateOptions(crossOptions);
    else { charts.emCross = createDashboardApexChart(elCross, crossOptions); charts.emCross.render(); }
  }

  // 6. FASE 3: Distribución de Horas de Descanso Habitual
  const suenoValids = filteredRecords.filter(r => r.cantidad_sueno && r.cantidad_sueno !== 'Sin dato');
  const horasAdecuadas = suenoValids.filter(r => r.cantidad_sueno.includes('7-8')).length;
  const horasInsuficientes = suenoValids.filter(r => r.cantidad_sueno.includes('<6')).length;
  const suenoTotal = suenoValids.length;

  const suenoCategories = ['Adecuada (7-8 h/día)', 'Insuficiente (< 6 h/día)'];
  const suenoCounts = [horasAdecuadas, horasInsuficientes];

  const elHoras = document.getElementById('chart-em-horas-sueno');
  if (elHoras && dashboardHasChartData('chart-em-horas-sueno', 'emHoras', suenoTotal)) {
    const horasOptions = {
      chart: { type: 'bar', height: 320, toolbar: { show: false }, animations: { enabled: false } },
      plotOptions: { bar: { horizontal: true, barHeight: '55%', distributed: true, borderRadius: 6, dataLabels: { position: 'center' } } },
      colors: [PALETTE.green, PALETTE.yellow],
      series: [{ name: 'Evaluados', data: suenoCounts }],
      xaxis: { categories: suenoCategories, labels: { formatter: val => Math.round(val) } },
      legend: { show: false },
      dataLabels: {
        enabled: true,
        formatter: val => `${val} (${formatPct(val, suenoTotal)}%)`,
        style: { fontSize: '11px', fontWeight: 'bold', colors: ['#ffffff'] }
      },
      tooltip: apexCountTooltip(suenoTotal)
    };
    if (charts.emHoras) charts.emHoras.updateOptions(horasOptions);
    else { charts.emHoras = createDashboardApexChart(elHoras, horasOptions); charts.emHoras.render(); }
  }
}

// -------------------------------------------------------------
// TAB 5: ANTECEDENTES FAMILIARES CHARTS
// -------------------------------------------------------------

