function renderTabDatosIndividuo() {
  const n = filteredRecords.length;
  const grupos = ['<40 años', '40-49 años', '50-59 años', '60+ años'];
  const hEdad = grupos.map(g => filteredRecords.filter(r => r.sexo === 'Hombre' && r.grupo_edad === g).length);
  const mEdad = grupos.map(g => filteredRecords.filter(r => r.sexo === 'Mujer' && r.grupo_edad === g).length);
  const hEdadPorcentajes = hEdad.map((conteo) => n > 0 ? Number(((conteo / n) * 100).toFixed(1)) : 0);
  const mEdadPorcentajes = mEdad.map((conteo) => n > 0 ? Number(((conteo / n) * 100).toFixed(1)) : 0);
  const edadMaximo = Math.max(5, Math.ceil(Math.max(...hEdadPorcentajes, ...mEdadPorcentajes, 0) / 5) * 5);

  const elPiramide = document.getElementById('chart-ind-edad-sexo');
  if (elPiramide) {
    const edadBarOptions = {
      bar: {
        horizontal: true,
        barHeight: '78%',
        borderRadius: 6,
        dataLabels: { position: 'center' },
        colors: { backgroundBarColors: ['#f1f5f9'], backgroundBarRadius: 6 }
      }
    };
    const edadDataLabels = {
      enabled: true,
      formatter: (_, { seriesIndex, dataPointIndex }) => {
        const conteo = (seriesIndex === 0 ? hEdad : mEdad)[dataPointIndex] || 0;
        return `${conteo} (${formatPct(conteo, n)}%)`;
      },
      style: {
        fontSize: '11px',
        fontWeight: 'bold',
        colors: [({ seriesIndex, dataPointIndex }) => {
          const porcentaje = (seriesIndex === 0 ? hEdadPorcentajes : mEdadPorcentajes)[dataPointIndex] || 0;
          return porcentaje / edadMaximo < 0.15 ? '#0f172a' : '#ffffff';
        }]
      },
      background: { enabled: false }
    };
    if (charts.indEdad) {
      charts.indEdad.updateOptions({
        plotOptions: { bar: edadBarOptions.bar },
        colors: [PALETTE.primaryBlue, PALETTE.purple],
        xaxis: { categories: grupos, min: 0, max: edadMaximo, tickAmount: 4, axisBorder: { show: false }, axisTicks: { show: false }, labels: { formatter: val => `${Math.round(val)} %` } },
        series: [{ name: 'Hombres', data: hEdadPorcentajes }, { name: 'Mujeres', data: mEdadPorcentajes }],
        dataLabels: edadDataLabels
      });
    } else {
      charts.indEdad = createDashboardApexChart(elPiramide, {
        chart: { type: 'bar', height: 320, toolbar: { show: false }, animations: { enabled: false }, fontFamily: 'inherit', foreColor: '#1e293b', fontSize: '12px' },
        grid: { borderColor: '#e8eef5', strokeDashArray: 4, padding: { right: 16 } },
        fill: { type: 'solid', opacity: 1 },
        colors: [PALETTE.primaryBlue, PALETTE.purple],
        plotOptions: edadBarOptions,
        series: [{ name: 'Hombres', data: hEdadPorcentajes }, { name: 'Mujeres', data: mEdadPorcentajes }],
        xaxis: { categories: grupos, min: 0, max: edadMaximo, tickAmount: 4, axisBorder: { show: false }, axisTicks: { show: false }, labels: { formatter: val => `${Math.round(val)} %` } },
        legend: { position: 'top', horizontalAlign: 'center' },
        dataLabels: edadDataLabels,
        tooltip: {
          y: {
            formatter: (_, { seriesIndex, dataPointIndex }) => {
              const conteo = (seriesIndex === 0 ? hEdad : mEdad)[dataPointIndex] || 0;
              return `${conteo} de ${n} casos (${formatPct(conteo, n)}%)`;
            }
          }
        }
      });
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
}

// -------------------------------------------------------------
// TAB 2: EXPLORACIÓN FÍSICA CHARTS
// -------------------------------------------------------------

