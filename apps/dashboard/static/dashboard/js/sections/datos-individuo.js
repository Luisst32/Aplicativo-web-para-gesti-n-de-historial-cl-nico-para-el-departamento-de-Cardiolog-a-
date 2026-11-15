function renderTabDatosIndividuo() {
  const n = filteredRecords.length;
  const grupos = ['<40 años', '40-49 años', '50-59 años', '60+ años'];
  const hEdad = grupos.map(g => filteredRecords.filter(r => r.sexo === 'Hombre' && r.grupo_edad === g).length);
  const mEdad = grupos.map(g => filteredRecords.filter(r => r.sexo === 'Mujer' && r.grupo_edad === g).length);
  const hEdadPorcentajes = hEdad.map((conteo) => n > 0 ? Number(((conteo / n) * 100).toFixed(1)) : 0);
  const mEdadPorcentajes = mEdad.map((conteo) => n > 0 ? Number(((conteo / n) * 100).toFixed(1)) : 0);
  const edadMaximo = Math.max(5, Math.ceil(Math.max(...hEdadPorcentajes, ...mEdadPorcentajes, 0) / 5) * 5);

  const elPiramide = document.getElementById('chart-ind-edad-sexo');
  if (elPiramide && dashboardHasChartData('chart-ind-edad-sexo', 'indEdad', n)) {
    const hEdadNeg = hEdad.map(v => -v);
    const maxVal = Math.max(1, ...hEdad, ...mEdad);
    const piramideOptions = {
      chart: { type: 'bar', height: 320, stacked: true, toolbar: { show: false }, animations: { enabled: false }, fontFamily: 'inherit' },
      colors: [PALETTE.primaryBlue, PALETTE.purple],
      plotOptions: {
        bar: {
          horizontal: true,
          barHeight: '75%',
          borderRadius: 4
        }
      },
      dataLabels: {
        enabled: true,
        formatter: (val) => {
          const abs = Math.abs(val);
          return abs > 0 ? `${abs} (${formatPct(abs, n)}%)` : '';
        },
        style: { fontSize: '11px', fontWeight: 'bold', colors: ['#ffffff'] }
      },
      grid: { borderColor: '#e8eef5', strokeDashArray: 4 },
      series: [
        { name: 'Hombres', data: hEdadNeg },
        { name: 'Mujeres', data: mEdad }
      ],
      xaxis: {
        categories: grupos,
        min: -maxVal - 2,
        max: maxVal + 2,
        tickAmount: 6,
        labels: { formatter: val => `${Math.abs(Math.round(val))}` },
        title: { text: '← Hombres | Mujeres →' }
      },
      yaxis: { labels: { style: { fontWeight: 600, colors: '#0f172a' } } },
      tooltip: {
        y: { formatter: (val) => `${Math.abs(val)} de ${n} (${formatPct(Math.abs(val), n)}%)` }
      },
      legend: { position: 'top', horizontalAlign: 'center' }
    };
    if (charts.indEdad) {
      charts.indEdad.updateOptions(piramideOptions);
    } else {
      charts.indEdad = createDashboardApexChart(elPiramide, piramideOptions);
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
      charts.indEdu = createDashboardChart(ctxEdu, {
        type: 'doughnut',
        data: {
          labels: eduLegendLabels,
          datasets: [{
            data: eduVals,
            backgroundColor: [PALETTE.green, PALETTE.primaryBlue, PALETTE.yellow, PALETTE.navy],
            borderColor: '#ffffff',
            borderWidth: 4,
            borderRadius: 5,
            hoverOffset: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '28%',
          layout: { padding: 12 },
          plugins: {
            legend: { position: 'bottom', labels: { usePointStyle: true, pointStyle: 'circle', boxWidth: 10, padding: 18, color: '#0f172a', font: { size: 12, weight: '600' } } },
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
  const civMaximo = Math.max(2, Math.ceil(Math.max(...civVals, 1) * 1.15));

  const ctxCiv = document.getElementById('chart-ind-estado-civil');
  if (ctxCiv) {
    if (charts.indCiv) {
      charts.indCiv.data.labels = civLabels;
      charts.indCiv.data.datasets[0].data = civVals;
      charts.indCiv.update();
    } else {
      charts.indCiv = createDashboardChart(ctxCiv, {
        type: 'bar',
        data: {
          labels: civLabels,
          datasets: [{
            label: 'Personas',
            data: civVals,
            backgroundColor: PALETTE.teal,
            borderRadius: 6,
            maxBarThickness: 76,
            categoryPercentage: 0.8,
            barPercentage: 0.9
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: { top: 25, right: 8, bottom: 4, left: 4 } },
          scales: {
            x: { grid: { display: false }, border: { display: false }, ticks: { color: '#1e293b', font: { size: 12, weight: '600' } } },
            y: {
              beginAtZero: true,
              max: civMaximo,
              grid: { color: '#edf2f7' },
              border: { display: false },
              ticks: { precision: 0, color: '#1e293b', font: { size: 12, weight: '600' } },
              title: { display: true, text: 'Casos (n)', font: { size: 11, weight: 'bold' } }
            }
          },
          plugins: {
            legend: { display: false },
            datalabels: {
              ...chartJsBarDataLabels(),
              color: (ctx) => ctx.dataset.data[ctx.dataIndex] / civMaximo < 0.15 ? '#0f172a' : '#ffffff',
              anchor: 'center',
              align: 'center',
              offset: 0,
              clip: false
            }
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
  const viviendaMaximo = Math.max(2, Math.ceil(Math.max(...vivVals, 1) * 1.15));

  const elViv = document.getElementById('chart-ind-vivienda');
  if (elViv) {
    const viviendaBarOptions = {
      bar: {
        horizontal: true,
        barHeight: '78%',
        borderRadius: 6,
        dataLabels: { position: 'center' },
        colors: { backgroundBarColors: ['#f1f5f9'], backgroundBarRadius: 6 }
      }
    };
    const viviendaDataLabels = {
      enabled: true,
      formatter: (val) => {
        const conteo = Number(val) || 0;
        return conteo > 0 ? `${conteo} (${formatPct(conteo, n)}%)` : '';
      },
      style: {
        fontSize: '11px',
        fontWeight: 'bold',
        colors: ['#ffffff']
      },
      background: { enabled: false },
      dropShadow: { enabled: true, top: 1, left: 0, blur: 1, color: '#0f172a', opacity: 0.45 }
    };
    if (charts.indViv) {
      charts.indViv.updateOptions({
        plotOptions: { bar: viviendaBarOptions.bar },
        xaxis: { categories: vivLabels, min: 0, max: viviendaMaximo, tickAmount: 4, axisBorder: { show: false }, axisTicks: { show: false } },
        series: [{ name: 'Viviendas', data: vivVals }],
        dataLabels: viviendaDataLabels
      });
    } else {
      charts.indViv = createDashboardApexChart(elViv, {
        chart: { type: 'bar', height: 320, toolbar: { show: false }, animations: { enabled: false }, fontFamily: 'inherit', foreColor: '#1e293b', fontSize: '12px' },
        grid: { borderColor: '#e8eef5', strokeDashArray: 4, padding: { right: 16 } },
        fill: { type: 'solid', opacity: 1 },
        colors: [PALETTE.primaryBlue],
        plotOptions: viviendaBarOptions,
        series: [{ name: 'Personas', data: vivVals }],
        xaxis: { categories: vivLabels, min: 0, max: viviendaMaximo, tickAmount: 4, axisBorder: { show: false }, axisTicks: { show: false } },
        dataLabels: viviendaDataLabels,
        tooltip: apexCountTooltip()
      });
      charts.indViv.render();
    }
  }

  // 5. FASE 3: Gradiente de Riesgo según Nivel Educativo
  const eduLevels = ['Secundaria', 'Superior', 'Postgrado'];
  const eduData = eduLevels.map(lvl => {
    const inLvl = filteredRecords.filter(r => r.nivel_estudios === lvl);
    const count = inLvl.length;
    const highRisk = inLvl.filter(r => (r.factores_riesgo_count || 0) >= 2 || (r.riesgo_global && r.riesgo_global.includes('Alto'))).length;
    return {
      lvl,
      count,
      highRisk,
      pct: count > 0 ? Number(((highRisk / count) * 100).toFixed(1)) : 0
    };
  }).filter(d => d.count > 0);

  const elEduGrad = document.getElementById('chart-di-gradiente-educacion');
  if (elEduGrad && dashboardHasChartData('chart-di-gradiente-educacion', 'diEduGrad', eduData.length)) {
    const seriesData = eduData.map(d => d.pct);
    const categories = eduData.map(d => d.lvl);
    if (charts.diEduGrad) {
      charts.diEduGrad.updateOptions({
        xaxis: { categories },
        series: [{ name: '% Riesgo Alto (≥2 Factores)', data: seriesData }]
      });
    } else {
      charts.diEduGrad = createDashboardApexChart(elEduGrad, {
        chart: { type: 'bar', height: 300, toolbar: { show: false }, animations: { enabled: false } },
        plotOptions: { bar: { horizontal: false, columnWidth: '50%', borderRadius: 6, distributed: true, dataLabels: { position: 'center' } } },
        colors: [PALETTE.green, PALETTE.primaryBlue, PALETTE.emergencyRed],
        series: [{ name: '% Riesgo Alto (≥2 Factores)', data: seriesData }],
        xaxis: { categories },
        yaxis: { min: 0, max: 100, labels: { formatter: val => `${Math.round(val)}%` }, title: { text: '% Prevalencia Riesgo Alto' } },
        legend: { show: false },
        dataLabels: {
          enabled: true,
          formatter: (val, opt) => {
            const d = eduData[opt.dataPointIndex];
            return d ? `${d.highRisk} de ${d.count} (${val}%)` : `${val}%`;
          },
          style: { fontSize: '11px', fontWeight: 700, fontFamily: 'inherit', colors: ['#ffffff'] },
          dropShadow: UNIVERSAL_VALUE_LABEL_STYLE.apexDropShadow,
          background: { enabled: false }
        },
        tooltip: {
          y: {
            formatter: (val, opt) => {
              const d = eduData[opt.dataPointIndex];
              return d ? formatWilsonCiLabel(d.highRisk, d.count) : `${val}%`;
            }
          }
        }
      });
      charts.diEduGrad.render();
    }
  }

  // 6. FASE 3: Gradiente de Riesgo según Rango de Ingresos
  const incLevels = ['Menos de $500', '$1001 - $2000'];
  const incData = incLevels.map(rng => {
    const inRng = filteredRecords.filter(r => r.rango_ingresos === rng);
    const count = inRng.length;
    const highRisk = inRng.filter(r => (r.factores_riesgo_count || 0) >= 2 || (r.riesgo_global && r.riesgo_global.includes('Alto'))).length;
    return {
      rng,
      count,
      highRisk,
      pct: count > 0 ? Number(((highRisk / count) * 100).toFixed(1)) : 0
    };
  }).filter(d => d.count > 0);

  const elIncGrad = document.getElementById('chart-di-gradiente-ingresos');
  if (elIncGrad && dashboardHasChartData('chart-di-gradiente-ingresos', 'diIncGrad', incData.length)) {
    const seriesData = incData.map(d => d.pct);
    const categories = incData.map(d => d.rng);
    if (charts.diIncGrad) {
      charts.diIncGrad.updateOptions({
        xaxis: { categories },
        series: [{ name: '% Riesgo Alto (≥2 Factores)', data: seriesData }]
      });
    } else {
      charts.diIncGrad = createDashboardApexChart(elIncGrad, {
        chart: { type: 'bar', height: 300, toolbar: { show: false }, animations: { enabled: false } },
        plotOptions: { bar: { horizontal: false, columnWidth: '45%', borderRadius: 6, distributed: true, dataLabels: { position: 'center' } } },
        colors: [PALETTE.yellow, PALETTE.primaryBlue],
        series: [{ name: '% Riesgo Alto (≥2 Factores)', data: seriesData }],
        xaxis: { categories },
        yaxis: { min: 0, max: 100, labels: { formatter: val => `${Math.round(val)}%` }, title: { text: '% Prevalencia Riesgo Alto' } },
        legend: { show: false },
        dataLabels: {
          enabled: true,
          formatter: (val, opt) => {
            const d = incData[opt.dataPointIndex];
            return d ? `${d.highRisk} de ${d.count} (${val}%)` : `${val}%`;
          },
          style: { fontSize: '11px', fontWeight: 700, fontFamily: 'inherit', colors: ['#ffffff'] },
          dropShadow: UNIVERSAL_VALUE_LABEL_STYLE.apexDropShadow,
          background: { enabled: false }
        },
        tooltip: {
          y: {
            formatter: (val, opt) => {
              const d = incData[opt.dataPointIndex];
              return d ? formatWilsonCiLabel(d.highRisk, d.count) : `${val}%`;
            }
          }
        }
      });
      charts.diIncGrad.render();
    }
  }
}

// -------------------------------------------------------------
// TAB 2: EXPLORACIÓN FÍSICA CHARTS
// -------------------------------------------------------------

