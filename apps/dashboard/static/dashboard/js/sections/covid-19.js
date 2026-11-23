function renderTabCovid19() {
  const n = filteredRecords.length;
  const sinHosp = filteredRecords.filter(r => r.covid_infeccion && (r.covid_hospitalizacion === false)).length;
  const conHosp = filteredRecords.filter(r => r.covid_hospitalizacion).length;
  const noCovid = filteredRecords.filter(r => (r.covid_infeccion === false)).length;

  renderThreeStateChart('chart-cov-historia','covHist', [["Infeccion", "covid_infeccion"], ["Hospitalizacion", "covid_hospitalizacion"]]);

  // Espectro de Secuelas
  const secCardio = filteredRecords.filter(r => r.covid_secuelas_cardio).length;
  const secResp = filteredRecords.filter(r => r.covid_secuelas_resp).length;
  const secFatiga = filteredRecords.filter(r => r.covid_fatiga_long).length;
  const secNiebla = filteredRecords.filter(r => r.covid_niebla_mental).length;
  const sinSecuelas = filteredRecords.filter(r => r.covid_infeccion && (r.covid_tiene_secuelas === false)).length;

  renderThreeStateChart('chart-cov-secuelas','covSec', [["Secuelas", "covid_tiene_secuelas"], ["Fatiga", "covid_fatiga_long"]]);

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

  // 5. FASE 3: Prevalencia COVID-19 con IC 95% por Categoría de Personal
  const elCovIc = document.getElementById('chart-covid-prevalencia-ic');
  if (elCovIc) {
    const cats = ['PDI (Docentes)', 'Código de trabajo', 'Personal de Servicios', 'Estudiantes'];
    const catData = cats.map(c => {
      const sub = filteredRecords.filter(r => r.categoria === c);
      const inf = sub.filter(r => r.covid_infeccion === true).length;
      const valid = sub.filter(r => typeof r.covid_infeccion === 'boolean').length;
      const ci = valid > 0 ? wilsonScoreInterval(inf, valid) : { lower: 0, upper: 0 };
      return { cat: c, total: valid, inf, pct: valid ? (inf / valid * 100) : 0, ci };
    }).filter(d => d.total > 0);

    if (dashboardHasChartData('chart-covid-prevalencia-ic', 'covIc', catData.length)) {
      const covIcOptions = {
        chart: { type: 'bar', height: 340, toolbar: { show: false }, animations: { enabled: false } },
        plotOptions: {
          bar: {
            horizontal: true,
            barHeight: '65%',
            borderRadius: 6,
            distributed: true,
            dataLabels: { position: 'center', hideOverflowingLabels: false },
            colors: { backgroundBarColors: ['#f8fafc'], backgroundBarRadius: 6 }
          }
        },
        colors: [PALETTE.primaryBlue, PALETTE.purple, PALETTE.teal, PALETTE.yellow],
        series: [{
          name: 'Prevalencia (%)',
          data: catData.map(d => ({
            x: d.cat,
            y: parseFloat(d.pct.toFixed(1)),
            goals: d.total >= 5 ? [
              { name: 'IC 95% Inf', value: parseFloat(d.ci.lower.toFixed(1)), strokeWidth: 3.5, strokeHeight: 12, strokeColor: '#0f172a' },
              { name: 'IC 95% Sup', value: parseFloat(d.ci.upper.toFixed(1)), strokeWidth: 3.5, strokeHeight: 12, strokeColor: '#0f172a' }
            ] : []
          }))
        }],
        xaxis: {
          title: { text: 'Prevalencia de Infección (%)', style: { fontSize: '11px', fontWeight: 700 } },
          min: 0,
          max: 100,
          tickAmount: 10,
          labels: { formatter: v => `${Math.round(v)}%` }
        },
        yaxis: {
          labels: {
            maxWidth: 180,
            style: { fontSize: '11.5px', fontWeight: 600 }
          }
        },
        legend: { show: false },
        dataLabels: {
          enabled: true,
          formatter: (val, opt) => {
            const d = catData[opt.dataPointIndex];
            if (!d) return '';
            const pStr = d.pct.toFixed(1).replace('.', ',');
            const lowStr = d.ci.lower.toFixed(1).replace('.', ',');
            const upStr = d.ci.upper.toFixed(1).replace('.', ',');
            if (d.total < 5) return `${d.inf} de ${d.total} (${pStr}%)*`;
            return [
              `${d.inf} de ${d.total} · ${pStr}%`,
              `IC 95%: ${lowStr}–${upStr}%`
            ];
          },
          style: { fontSize: '11px', fontWeight: 700, fontFamily: 'inherit', colors: ['#ffffff'] },
          dropShadow: UNIVERSAL_VALUE_LABEL_STYLE.apexDropShadow,
          background: { enabled: false },
          offsetX: 0
        },
        tooltip: {
          y: {
            formatter: (val, opt) => {
              const d = catData[opt.dataPointIndex];
              if (!d) return '';
              const warn = d.total < 10 ? ' [Muestra pequeña]' : '';
              if (d.total < 5) return `${d.inf} de ${d.total} casos${warn} (sin % por n<5)`;
              return `${d.inf} de ${d.total} (${d.pct.toFixed(1)}%; IC 95%: ${d.ci.lower.toFixed(1)}-${d.ci.upper.toFixed(1)}%)${warn}`;
            }
          }
        }
      };

      if (charts.covIc) {
        charts.covIc.updateOptions(covIcOptions);
      } else {
        charts.covIc = createDashboardApexChart(elCovIc, covIcOptions);
        charts.covIc.render();
      }
    }
  }

  // 6. FASE 3: Espectro de Secuelas Persistentes (Long-COVID) con aviso de muestra pequeña
  const elLongCov = document.getElementById('chart-covid-long-covid');
  if (elLongCov) {
    const infectedPatients = filteredRecords.filter(r => r.covid_infeccion === true);
    const nInf = infectedPatients.length;
    const symptoms = [
      { label: ['Fatiga Persistente', '(Long-COVID)'], field: 'covid_fatiga_long' },
      { label: 'Niebla Mental / Cognitiva', field: 'covid_niebla_mental' },
      { label: 'Secuelas Respiratorias', field: 'covid_secuelas_resp' },
      { label: 'Secuelas Cardiovasculares', field: 'covid_secuelas_cardio' }
    ];

    const symData = symptoms.map(s => {
      const cnt = infectedPatients.filter(r => r[s.field] === true).length;
      return { label: s.label, count: cnt };
    });

    const totalSymCount = symData.reduce((acc, s) => acc + s.count, 0);
    const maxSymCount = Math.max(...symData.map(s => s.count), 0);
    // Escala dinámica con margen holgado para que las barras no topen el borde derecho
    const covLongMax = Math.max(10, Math.ceil((maxSymCount + 4) / 5) * 5);

    if (dashboardHasChartData('chart-covid-long-covid', 'covLong', nInf > 0 ? nInf : 0)) {
      const covLongOptions = {
        chart: { type: 'bar', height: 320, toolbar: { show: false }, animations: { enabled: false } },
        plotOptions: {
          bar: {
            horizontal: true,
            barHeight: '55%',
            borderRadius: 6,
            distributed: true,
            colors: { backgroundBarColors: ['#f8fafc'], backgroundBarRadius: 6 }
          }
        },
        colors: [PALETTE.emergencyRed, PALETTE.purple, PALETTE.yellow, PALETTE.primaryBlue],
        series: [{
          name: 'Casos Reportados',
          data: symData.map(s => s.count)
        }],
        xaxis: {
          categories: symData.map(s => s.label),
          title: { text: `Casos en Cohorte Infectada (n=${nInf})` },
          min: 0,
          max: covLongMax,
          tickAmount: 5,
          labels: { formatter: v => `${Math.round(v)}` }
        },
        yaxis: {
          labels: {
            maxWidth: 240,
            style: { fontSize: '11.5px', fontWeight: 600 }
          }
        },
        legend: { show: false },
        dataLabels: {
          enabled: true,
          textAnchor: 'start',
          formatter: (val, opt) => {
            if (val === 0) return '0 casos (0,0%)';
            return `${val} de ${nInf} (${formatPct(val, nInf)}%)`;
          },
          style: { fontSize: '10.5px', fontWeight: 700, colors: ['#0f172a'] },
          offsetX: 6
        },
        tooltip: {
          y: {
            formatter: (val, opt) => {
              const ci = wilsonScoreInterval(val, nInf);
              return `${val} de ${nInf} (${formatPct(val, nInf)}%; IC 95%: ${ci.lower.toFixed(1)}-${ci.upper.toFixed(1)}%) · Aviso: Muestra pequeña (n < 10)`;
            }
          }
        }
      };

      if (charts.covLong) {
        charts.covLong.updateOptions(covLongOptions);
      } else {
        charts.covLong = createDashboardApexChart(elLongCov, covLongOptions);
        charts.covLong.render();
      }
    }
  }
}

// -------------------------------------------------------------
// TAB 8: RESULTADOS DEL ELECTROCARDIOGRAMA CHARTS
// -------------------------------------------------------------

