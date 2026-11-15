function renderTabHistoriaNoCardio() {
  const n = filteredRecords.length;
  const respCnt = filteredRecords.filter(r => r.asma === true || r.epoc === true).length;
  const mentalCnt = filteredRecords.filter(r => r.ansiedad === true || r.depresion === true).length;
  const reumaCnt = filteredRecords.filter(r => r.enfermedad_reumatologica).length;
  const alergiasCnt = filteredRecords.filter(r => r.alergias_medicamentos).length;
  const cancerCnt = filteredRecords.filter(r => r.cancer).length;
  const ircCnt = filteredRecords.filter(r => r.insuficiencia_renal).length;

  const labels = [
    ['Respiratorio', '(Asma / EPOC)'],
    ['Salud Mental', '(Ansiedad / Depresión)'],
    ['Alergias', 'Medicamentosas'],
    'Reumatológica',
    ['Cáncer /', 'Oncología'],
    ['Insuficiencia', 'Renal']
  ];
  const vals = [respCnt, mentalCnt, alergiasCnt, reumaCnt, cancerCnt, ircCnt];
  const evaluable = [ ['asma','epoc'], ['ansiedad','depresion'], ['alergias_medicamentos'], ['enfermedad_reumatologica'], ['cancer'], ['insuficiencia_renal'] ].map(fields => filteredRecords.filter(r => fields.some(field => r[field] === true) || fields.every(field => r[field] === false)).length);
  const comorbLabel = (value, index) => evaluable[index] ? `${value} (${formatPct(value, evaluable[index])}%)` : 'Sin datos';

  const elComorb = document.getElementById('chart-nc-comorbilidades');
  const comorbValid = filteredRecords.filter(r => ['asma','epoc','ansiedad','depresion','enfermedad_reumatologica','alergias_medicamentos','cancer','insuficiencia_renal'].some(field => typeof r[field] === 'boolean')).length;
  if (dashboardHasChartData('chart-nc-comorbilidades', 'ncComorb', comorbValid)) {
    if (charts.ncComorb) {
      charts.ncComorb.updateOptions({
        series: [{ name: 'Prevalencia Casos', data: vals }],
        xaxis: { categories: labels },
        yaxis: { labels: { maxWidth: 220, style: { fontSize: '11px', fontWeight: 600 } } },
        dataLabels: { ...apexCountAndPctDataLabel(), formatter: (v, o) => v > 0 ? comorbLabel(v, o.dataPointIndex) : '' },
        tooltip: { y: { formatter: (v, o) => comorbLabel(v, o.dataPointIndex) } }
      });
    } else {
      charts.ncComorb = createDashboardApexChart(elComorb, {
        chart: { type: 'bar', height: 340, toolbar: { show: false }, animations: { enabled: false } },
        fill: { type: 'solid', opacity: 1 },
        plotOptions: {
          bar: {
            horizontal: true,
            distributed: true,
            barHeight: '75%',
            borderRadius: 6,
            dataLabels: { position: 'center' },
            colors: { backgroundBarColors: ['#f1f5f9'], backgroundBarRadius: 6 }
          }
        },
        colors: [PALETTE.yellow, PALETTE.purple, PALETTE.teal, PALETTE.primaryBlue, PALETTE.emergencyRed, PALETTE.navy],
        series: [{ name: 'Prevalencia Casos', data: vals }],
        xaxis: { categories: labels },
        yaxis: { labels: { maxWidth: 220, style: { fontSize: '11px', fontWeight: 600 } } },
        legend: { show: false },
        dataLabels: { ...apexCountAndPctDataLabel(), formatter: (v, o) => v > 0 ? comorbLabel(v, o.dataPointIndex) : '' },
        tooltip: { y: { formatter: (v, o) => comorbLabel(v, o.dataPointIndex) } }
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
  renderThreeStateChart('chart-nc-respiratorio','ncResp', [['Asma','asma'],['EPOC','epoc']]);

  // Reumatología vs Alergias
  renderThreeStateChart('chart-nc-reuma-alergia','ncReuma', [["Reumatologia", "enfermedad_reumatologica"], ["Alergias", "alergias_medicamentos"]]);

  // 5. FASE 3: Comorbilidades Médicas y Salud Mental por Sexo y Categoría
  const elNcSexoCat = document.getElementById('chart-nc-sexo-categoria');
  if (elNcSexoCat) {
    const groups = [
      { label: 'Hombres', filter: r => r.sexo === 'Hombre' },
      { label: 'Mujeres', filter: r => r.sexo === 'Mujer' },
      { label: 'PDI Docentes', filter: r => (r.categoria || '').includes('Docente') },
      { label: 'PAS Admin.', filter: r => (r.categoria || '').includes('Admin') },
      { label: 'Servicios*', filter: r => (r.categoria || '').includes('Servicio') },
      { label: 'Estudiantes*', filter: r => (r.categoria || '').includes('Estudiante') }
    ];

    const groupCounts = groups.map(g => {
      const records = filteredRecords.filter(g.filter);
      const mental = records.filter(r => r.ansiedad === true || r.depresion === true).length;
      const resp = records.filter(r => r.asma === true || r.epoc === true).length;
      const inmune = records.filter(r => r.alergias_medicamentos === true || r.enfermedad_reumatologica === true).length;
      return { total: records.length, mental, resp, inmune };
    });

    const hasAny = groupCounts.some(g => g.total > 0 && (g.mental > 0 || g.resp > 0 || g.inmune > 0));
    if (dashboardHasChartData('chart-nc-sexo-categoria', 'ncSexoCat', hasAny ? filteredRecords.length : 0)) {
      const ncSexoCatOptions = {
        chart: { type: 'bar', height: 480, toolbar: { show: false }, animations: { enabled: false } },
        plotOptions: {
          bar: {
            horizontal: true,
            barHeight: '82%',
            borderRadius: 5
          }
        },
        colors: [PALETTE.purple, PALETTE.yellow, PALETTE.teal],
        series: [
          { name: 'Salud Mental (Ansiedad/Dep.)', data: groupCounts.map(g => g.mental) },
          { name: 'Patología Respiratoria (Asma/EPOC)', data: groupCounts.map(g => g.resp) },
          { name: 'Alergias / Inmune', data: groupCounts.map(g => g.inmune) }
        ],
        xaxis: {
          categories: groups.map((g, i) => `${g.label} (n=${groupCounts[i].total})`),
          min: 0,
          max: 5,
          tickAmount: 5,
          labels: { formatter: val => Math.round(val), style: { fontSize: '11.5px', fontWeight: 600 } }
        },
        yaxis: {
          labels: { style: { fontSize: '11.5px', fontWeight: 600 } }
        },
        legend: { position: 'top', horizontalAlign: 'center' },
        dataLabels: {
          enabled: true,
          formatter: (val, opt) => {
            if (!val || val <= 0) return '';
            const gIndex = opt.dataPointIndex;
            const tot = groupCounts[gIndex].total;
            if (tot < 5) return `${val}`; // Regla 8: Con n<5 no mostrar porcentaje
            return `${val} (${formatPct(val, tot)}%)`;
          },
          style: { fontSize: '11px', fontWeight: 700, fontFamily: 'inherit', colors: ['#ffffff'] },
          dropShadow: UNIVERSAL_VALUE_LABEL_STYLE.apexDropShadow,
          background: { enabled: false },
          offsetY: 0
        },
        tooltip: {
          y: {
            formatter: (val, opt) => {
              const gIndex = opt.dataPointIndex;
              const tot = groupCounts[gIndex].total;
              if (tot === 0) return 'Sin evaluados';
              const warn = tot < 10 ? ' [Muestra pequeña]' : '';
              if (tot < 5) return `${val} de ${tot} evaluados${warn}`;
              const ci = wilsonScoreInterval(val, tot);
              return `${val} de ${tot} (${formatPct(val, tot)}%; IC 95%: ${ci.lower.toFixed(1)}-${ci.upper.toFixed(1)}%)${warn}`;
            }
          }
        }
      };

      if (charts.ncSexoCat) {
        charts.ncSexoCat.updateOptions(ncSexoCatOptions);
      } else {
        charts.ncSexoCat = createDashboardApexChart(elNcSexoCat, ncSexoCatOptions);
        charts.ncSexoCat.render();
      }
    }
  }
}

// -------------------------------------------------------------
// TAB 7: COVID-19 Y SECUELAS CHARTS
// -------------------------------------------------------------

