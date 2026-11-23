function renderTabResumenGeneral() {
  const n = filteredRecords.length;

  // 1. Tendencia Temporal por Año
  const yearCounts = {};
  const yearHtaCounts = {};
  const yearHtaValidCounts = {};
  filteredRecords.forEach(r => {
    yearCounts[r.ano] = (yearCounts[r.ano] || 0) + 1;
    if (r.hipertension === true) {
      yearHtaCounts[r.ano] = (yearHtaCounts[r.ano] || 0) + 1;
    }
    if (r.hipertension === true || r.hipertension === false) {
      yearHtaValidCounts[r.ano] = (yearHtaValidCounts[r.ano] || 0) + 1;
    }
  });
  const years = Object.keys(yearCounts).sort();
  const yearData = years.map(y => yearCounts[y]);
  const yearHtaData = years.map(y => yearHtaCounts[y] || 0);
  const yearHtaValidData = years.map(y => yearHtaValidCounts[y] || 0);
  const trendDataLabelFormatter = (val, opts) => {
    const seriesIndex = opts?.seriesIndex ?? 0;
    const dataIndex = opts?.dataPointIndex ?? 0;
    const denominator = seriesIndex === 1 ? yearHtaValidData[dataIndex] : filteredRecords.length;
    return `${val} (${formatPct(val, denominator)}%)`;
  };
  const trendTooltip = {
    shared: true,
    intersect: false,
    y: {
      formatter: (val, opts) => {
        const seriesIndex = opts?.seriesIndex ?? 0;
        const dataIndex = opts?.dataPointIndex ?? 0;
        const denominator = seriesIndex === 1 ? yearHtaValidData[dataIndex] : filteredRecords.length;
        const suffix = seriesIndex === 1 ? ' casos HTA' : ' evaluados';
        return `${val}${suffix} (${formatPct(val, denominator)}%)`;
      }
    }
  };

  const elTendencia = document.getElementById('chart-tendencia-temporal');
  if (elTendencia) {
    if (charts.tendencia) {
      charts.tendencia.updateOptions({
        xaxis: { categories: years.map(y => `Año ${y}`) },
        series: [
          { name: 'Evaluados', data: yearData },
          { name: 'HTA detectada', data: yearHtaData }
        ],
        dataLabels: { formatter: trendDataLabelFormatter },
        tooltip: trendTooltip
      });
    } else {
      charts.tendencia = createDashboardApexChart(elTendencia, {
        chart: { type: 'area', height: 320, toolbar: { show: false }, fontFamily: 'inherit', foreColor: '#1e293b', fontSize: '12px' },
        grid: { borderColor: '#e8eef5', strokeDashArray: 4 },
        markers: { size: 4, strokeWidth: 3, strokeColors: '#ffffff', hover: { size: 6 } },
        yaxis: { min: 0, labels: { formatter: val => Math.round(val) } },
        colors: [PALETTE.primaryBlue, PALETTE.emergencyRed],
        stroke: { curve: 'smooth', width: [3, 3] },
        fill: { type: 'gradient', gradient: { shadeIntensity: 0, opacityFrom: 0.22, opacityTo: 0.02 } },
        series: [
          { name: 'Evaluados', data: yearData },
          { name: 'HTA detectada', data: yearHtaData }
        ],
        xaxis: { categories: years.map(y => `Año ${y}`) },
        dataLabels: {
          enabled: true,
          formatter: trendDataLabelFormatter,
          offsetY: -10,
          style: { fontSize: '12px', fontWeight: 700, colors: ['#0f172a'] },
          background: { enabled: false }
        },
        tooltip: trendTooltip
      });
      charts.tendencia.render();
    }
  }

  // 2. Factores Modificables Globales (Barra horizontal)
  const factorStats = [
    ['hipertension', 'yes'],
    ['dislipemia', 'yes'],
    ['obesidad', 'yes'],
    ['diabetes', 'yes'],
    ['fumador_activo', 'yes'],
    ['actividad_fisica', 'no']
  ].map(([field, response]) => {
    const counts = threeStateCounts(field);
    return {
      cases: response === 'no' ? counts.no : counts.yes,
      valid: counts.answered
    };
  });

  const fLabels = ['Hipertensión', 'Dislipemia', 'Obesidad', 'Diabetes', 'Tabaquismo', 'Sedentarismo'];
  const fData = factorStats.map(({cases, valid}) => (
    valid ? Number(((cases / valid) * 100).toFixed(1)) : 0
  ));
  const factorDataLabelFormatter = (value, opts) => {
    const stat = factorStats[opts?.dataPointIndex ?? 0];
    return stat?.valid ? `${stat.cases} (${formatPct(stat.cases, stat.valid)}%)` : '';
  };
  const factorTooltip = {
    y: {
      formatter: (value, opts) => {
        const stat = factorStats[opts?.dataPointIndex ?? 0];
        if (!stat?.valid) return 'Sin respuestas válidas';
        return `${stat.cases} casos de ${stat.valid} respuestas válidas (${formatPct(stat.cases, stat.valid)}%)`;
      }
    }
  };

  const elFactores = document.getElementById('chart-factores-modificables');
  if (elFactores) {
    if (charts.factores) {
      charts.factores.updateOptions({
        series: [{ name: 'Prevalencia (%)', data: fData }],
        dataLabels: { formatter: factorDataLabelFormatter },
        tooltip: factorTooltip
      });
    } else {
      charts.factores = createDashboardApexChart(elFactores, {
        chart: { type: 'bar', height: 350, toolbar: { show: false }, animations: { enabled: false }, fontFamily: 'inherit', foreColor: '#1e293b', fontSize: '12px' },
        grid: { borderColor: '#e8eef5', strokeDashArray: 4, padding: { right: 16 } },
        fill: { type: 'solid', opacity: 1 },
        plotOptions: { bar: { horizontal: true, distributed: true, borderRadius: 6, barHeight: '82%', dataLabels: { position: 'center' }, colors: { backgroundBarColors: ['#f1f5f9'], backgroundBarRadius: 6 } } },
        colors: [PALETTE.emergencyRed, PALETTE.yellow, PALETTE.yellow, PALETTE.primaryBlue, PALETTE.green, PALETTE.purple],
        series: [{ name: 'Prevalencia (%)', data: fData }],
        xaxis: { categories: fLabels, min: 0, max: 100, tickAmount: 4, axisBorder: { show: false }, axisTicks: { show: false }, labels: { formatter: val => `${Math.round(val)} %` } },
        legend: { show: false },
        dataLabels: {
          enabled: true,
          formatter: factorDataLabelFormatter,
          style: {
            fontSize: '11px', fontWeight: 700,
            colors: ['#ffffff']
          },
          dropShadow: UNIVERSAL_VALUE_LABEL_STYLE.apexDropShadow,
          background: { enabled: false }
        },
        tooltip: factorTooltip
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
      charts.categoria = createDashboardChart(ctxCat, {
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
      charts.genero = createDashboardChart(ctxGen, {
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

  // 5. FASE 3: Forest Plot de Prevalencias Clave con IC 95% Wilson
  const totalSample = filteredRecords.length;

  const rawConditions = [
    {
      conditionName: 'Antecedente de COVID-19',
      cases: filteredRecords.filter(r => r.covid_infeccion === true).length,
      valid: filteredRecords.filter(r => typeof r.covid_infeccion === 'boolean').length
    },
    {
      conditionName: 'Hígado Graso',
      cases: filteredRecords.filter(r => r.higado_graso === true).length,
      valid: filteredRecords.filter(r => typeof r.higado_graso === 'boolean').length
    },
    {
      conditionName: 'Dislipemia',
      cases: threeStateCounts('dislipemia').yes,
      valid: threeStateCounts('dislipemia').answered
    },
    {
      conditionName: 'Hipertensión',
      cases: threeStateCounts('hipertension').yes,
      valid: threeStateCounts('hipertension').answered
    },
    {
      conditionName: 'Obesidad (IMC ≥ 30)',
      cases: filteredRecords.filter(r => r.imc !== null && r.imc !== undefined && !isNaN(Number(r.imc)) && Number(r.imc) >= 30).length,
      valid: filteredRecords.filter(r => r.imc !== null && r.imc !== undefined && !isNaN(Number(r.imc))).length
    },
    {
      conditionName: 'Tabaquismo Activo',
      cases: threeStateCounts('fumador_activo').yes,
      valid: threeStateCounts('fumador_activo').answered
    },
    {
      conditionName: 'Salud Mental (Ans/Dep)',
      cases: filteredRecords.filter(r => r.ansiedad === true || r.depresion === true).length,
      valid: filteredRecords.filter(r => typeof r.ansiedad === 'boolean' || typeof r.depresion === 'boolean').length
    }
  ].filter(item => item.valid > 0);

  // 1. Ordenar las condiciones de mayor a menor prevalencia
  rawConditions.sort((a, b) => {
    const pA = a.valid > 0 ? (a.cases / a.valid) : 0;
    const pB = b.valid > 0 ? (b.cases / b.valid) : 0;
    return pB - pA;
  });

  const forestData = rawConditions.map(item => {
    const ci = wilsonScoreInterval(item.cases, item.valid);
    const pPct = Number((ci.p * 100).toFixed(1));
    const low = Number(ci.lower.toFixed(1));
    const up = Number(ci.upper.toFixed(1));
    const negatives = Math.max(0, item.valid - item.cases);
    const missing = Math.max(0, totalSample - item.valid);
    const negPct = item.valid > 0 ? Number(((negatives / item.valid) * 100).toFixed(1)) : 0;
    const missingPct = totalSample > 0 ? Number(((missing / totalSample) * 100).toFixed(1)) : 0;

    return {
      // 4 & 6. Mostrar número de pacientes evaluados por condición y diferenciar "Antecedente de COVID-19"
      x: `${item.conditionName} (n = ${item.valid})`,
      y: [low, up],
      goals: [{
        name: 'Prevalencia Puntual',
        value: pPct,
        strokeHeight: 14,
        strokeColor: PALETTE.navy,
        strokeWidth: 4
      }],
      conditionName: item.conditionName,
      cases: item.cases,
      valid: item.valid,
      negatives: negatives,
      missing: missing,
      pPct: pPct,
      negPct: negPct,
      missingPct: missingPct,
      low: low,
      up: up
    };
  });

  const elForest = document.getElementById('chart-rg-forest-prevalencias');
  if (elForest && dashboardHasChartData('chart-rg-forest-prevalencias', 'rgForest', rawConditions.length)) {
    const forestChartOptions = {
      chart: { type: 'rangeBar', height: 460, toolbar: { show: false }, animations: { enabled: false } },
      plotOptions: {
        bar: {
          horizontal: true,
          barHeight: '10%', // 2. Sustituir rectángulos por líneas delgadas de confianza
          borderRadius: 2,
          isDumbbell: false,
          dataLabels: {
            position: 'top',
            hideOverflowingLabels: false
          }
        }
      },
      colors: ['#2563EB'],
      series: [{ name: 'IC 95% Wilson', data: forestData }],
      xaxis: {
        min: 0,
        max: 100,
        tickAmount: 10,
        labels: {
          formatter: val => `${Math.round(val)}%`,
          style: { fontSize: '12px', fontWeight: 600, colors: '#64748B' }
        },
        title: {
          text: 'Prevalencia (%) e Intervalo de Confianza al 95% (Método de Wilson)',
          style: { fontSize: '12.5px', fontWeight: 700, color: '#1E293B' }
        }
      },
      yaxis: {
        labels: {
          maxWidth: 280,
          style: {
            fontSize: '12.5px', // 3. Aumentar ligeramente tamaño de etiquetas
            fontWeight: 700,
            colors: '#1E293B',
            fontFamily: 'Inter, system-ui, sans-serif'
          }
        }
      },
      dataLabels: {
        enabled: true,
        formatter: (val, opt) => {
          const d = forestData[opt.dataPointIndex];
          if (!d) return '';
          const pStr = d.pPct.toFixed(1).replace('.', ',');
          const lowStr = d.low.toFixed(1).replace('.', ',');
          const upStr = d.up.toFixed(1).replace('.', ',');
          return [
            `${pStr}% (IC 95%: ${lowStr}–${upStr}%)`,
            `${d.cases} de ${d.valid} pacientes`
          ];
        },
        style: {
          fontSize: '12px', // 3. Aumentar tamaño de etiqueta de datos
          fontWeight: 700,
          fontFamily: 'Inter, system-ui, sans-serif',
          colors: ['#0F172A']
        },
        dropShadow: { enabled: false },
        background: { enabled: false },
        offsetX: 14
      },
      tooltip: {
        custom: function({ seriesIndex, dataPointIndex, w }) {
          const d = forestData[dataPointIndex];
          if (!d) return '';
          const posPctStr = d.pPct.toFixed(1).replace('.', ',');
          const negPctStr = d.negPct.toFixed(1).replace('.', ',');
          const missPctStr = d.missingPct.toFixed(1).replace('.', ',');
          const lowStr = d.low.toFixed(1).replace('.', ',');
          const upStr = d.up.toFixed(1).replace('.', ',');

          // 5. Tooltip con casos positivos, negativos y datos faltantes
          return `<div style="padding: 12px 14px; font-size: 12px; font-family: Inter, system-ui, -apple-system, sans-serif; background: #FFFFFF; border: 1.5px solid #CBD5E1; border-radius: 8px; box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.15); min-width: 250px; color: #1E293B; line-height: 1.5;">
            <div style="font-weight: 700; color: #0F172A; font-size: 13.5px; margin-bottom: 8px; padding-bottom: 6px; border-bottom: 1.5px solid #E2E8F0;">
              ${d.conditionName}
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
              <span style="color: #475569;">Muestra evaluada:</span>
              <strong style="color: #0F172A;">${d.valid} de ${totalSample} (${totalSample > 0 ? Math.round((d.valid / totalSample) * 100) : 0}%)</strong>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
              <span style="color: #16A34A; font-weight: 600;">● Casos positivos:</span>
              <strong style="color: #16A34A;">${d.cases} (${posPctStr}%)</strong>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
              <span style="color: #2563EB; font-weight: 600;">● Casos negativos:</span>
              <strong style="color: #2563EB;">${d.negatives} (${negPctStr}%)</strong>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
              <span style="color: #94A3B8; font-weight: 600;">○ Datos faltantes:</span>
              <strong style="color: #64748B;">${d.missing} (${missPctStr}%)</strong>
            </div>
            <div style="border-top: 1px dashed #CBD5E1; padding-top: 6px; margin-top: 6px; font-size: 11.5px; color: #334155; background: #F8FAFC; margin-left: -14px; margin-right: -14px; margin-bottom: -12px; padding-left: 14px; padding-right: 14px; padding-bottom: 8px; border-radius: 0 0 7px 7px;">
              <strong>IC 95% Wilson:</strong> [${lowStr}%, ${upStr}%]
            </div>
          </div>`;
        }
      }
    };

    if (charts.rgForest) {
      charts.rgForest.updateOptions(forestChartOptions);
    } else {
      charts.rgForest = createDashboardApexChart(elForest, forestChartOptions);
      charts.rgForest.render();
    }
  }

  // 6. FASE 3: Histograma de Factores de Riesgo por Persona
  const riskCounts = [0, 0, 0, 0, 0, 0]; // 0, 1, 2, 3, 4, 5+
  let riskDenominator = 0;
  filteredRecords.forEach(r => {
    const factors = [r.hipertension, r.dislipemia, r.obesidad, r.diabetes, r.fumador_activo, r.higado_graso];
    if (factors.some(factor => factor !== true && factor !== false)) return;
    const fCount = factors.filter(factor => factor === true).length;
    const idx = Math.min(fCount, 5);
    riskCounts[idx]++;
    riskDenominator++;
  });

  const riskDataLabels = {
    enabled: true,
    formatter: val => val > 0 ? [`${val}`, `${formatPct(val, riskDenominator)}%`] : '',
    style: { fontSize: '11px', fontWeight: 700, fontFamily: 'inherit', colors: ['#ffffff'] },
    dropShadow: UNIVERSAL_VALUE_LABEL_STYLE.apexDropShadow,
    background: { enabled: false }
  };
  const riskTooltip = apexCountTooltip(riskDenominator);

  const histLabels = ['0 Factores', '1 Factor', '2 Factores', '3 Factores', '4 Factores', '≥ 5 Factores'];
  const elHist = document.getElementById('chart-rg-hist-factores');
  if (elHist && dashboardHasChartData('chart-rg-hist-factores', 'rgHist', riskDenominator)) {
    if (charts.rgHist) {
      charts.rgHist.updateOptions({
        series: [{ name: 'Evaluados', data: riskCounts }],
        yaxis: { max: Math.max(...riskCounts) + 4 },
        dataLabels: riskDataLabels,
        tooltip: riskTooltip
      });
    } else {
      charts.rgHist = createDashboardApexChart(elHist, {
        chart: { type: 'bar', height: 340, toolbar: { show: false }, animations: { enabled: false } },
        plotOptions: {
          bar: {
            horizontal: false,
            columnWidth: '58%',
            borderRadius: 6,
            distributed: true,
            dataLabels: { position: 'center' }
          }
        },
        colors: [PALETTE.green, PALETTE.teal, PALETTE.yellow, PALETTE.yellow, PALETTE.emergencyRed, PALETTE.emergencyRed],
        series: [{ name: 'Evaluados', data: riskCounts }],
        xaxis: {
          categories: histLabels,
          labels: { style: { fontSize: '11.5px', fontWeight: 600 } }
        },
        yaxis: {
          title: { text: 'Número de Pacientes (n)', style: { fontSize: '11px', fontWeight: 700 } },
          min: 0,
          max: Math.max(...riskCounts) + 4,
          forceNiceScale: true,
          labels: { formatter: val => Math.round(val) }
        },
        legend: { show: false },
        dataLabels: {
          ...riskDataLabels
        },
        tooltip: riskTooltip
      });
      charts.rgHist.render();
    }
  }
}

// -------------------------------------------------------------
// TAB 1: DATOS DEL INDIVIDUO CHARTS
// -------------------------------------------------------------

