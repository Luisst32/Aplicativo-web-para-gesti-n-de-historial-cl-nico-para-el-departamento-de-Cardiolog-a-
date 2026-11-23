function renderTabFactoresModificables() {
  const n = filteredRecords.length;

  // Control Terapéutico
  const htaTto = filteredRecords.filter(r => r.hta_desc === 'Tratada').length;
  const htaNoTto = filteredRecords.filter(r => r.hta_desc === 'No tratada').length;
  const dmTto = filteredRecords.filter(r => r.db_desc.includes('tratada')).length;
  const dmNoTto = filteredRecords.filter(r => r.db_desc.includes('Diabetes') && !r.db_desc.includes('tratada')).length;
  const dlTto = filteredRecords.filter(r => r.dl_desc === 'Tratada').length;
  const dlNoTto = filteredRecords.filter(r => r.dl_desc === 'No tratada').length;

  const elControl = document.getElementById('chart-mod-control-tto');
  if (elControl) {
    if (charts.modControl) {
      charts.modControl.data.datasets[0].data = [htaTto, dmTto, dlTto];
      charts.modControl.data.datasets[1].data = [htaNoTto, dmNoTto, dlNoTto];
      charts.modControl.update();
    } else {
      charts.modControl = createDashboardChart(elControl, {
        type: 'bar',
        data: {
          labels: ['Hipertensión', 'Diabetes', 'Dislipemia'],
          datasets: [
            { label: 'Bajo Tratamiento Farmacológico', data: [htaTto, dmTto, dlTto], backgroundColor: PALETTE.green, maxBarThickness: 76, categoryPercentage: 0.8, barPercentage: 0.9, borderRadius: 4 },
            { label: 'Sin Tratamiento / Sin Control', data: [htaNoTto, dmNoTto, dlNoTto], backgroundColor: PALETTE.emergencyRed, maxBarThickness: 76, categoryPercentage: 0.8, barPercentage: 0.9, borderRadius: 4 }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: { top: 16, right: 8, bottom: 4, left: 4 } },
          scales: {
            x: { stacked: true, grid: { display: false }, border: { display: false },
              ticks: { maxRotation: 0, minRotation: 0, autoSkip: false, color: '#1e293b', font: { size: 12, weight: '600' } } },
            y: { stacked: true, beginAtZero: true, grace: '20%',
              grid: { color: '#edf2f7' }, border: { display: false },
              ticks: { precision: 0, color: '#1e293b', font: { size: 12, weight: '600' } },
              title: { display: true, text: 'Casos (n)' } }
          },
          plugins: {
            legend: { position: 'bottom', labels: { usePointStyle: true, pointStyle: 'circle', padding: 16, boxWidth: 10, color: '#0f172a', font: { size: 12, weight: '600' } } },
            datalabels: chartJsBarDataLabels()
          }
        }
      });
    }
  }

  // Hábitos Tóxicos (Tabaquismo y Alcohol)
  const tobaccoValid = filteredRecords.filter(r => ['No fuma', 'Exfumador', 'Fumador Activo'].includes(r.tabaquismo));
  const tabNo = tobaccoValid.filter(r => r.tabaquismo === 'No fuma').length;
  const tabEx = tobaccoValid.filter(r => r.tabaquismo === 'Exfumador').length;
  const tabAct = tobaccoValid.filter(r => r.tabaquismo === 'Fumador Activo').length;

  const alcoholValid = filteredRecords.filter(r => ['No consume', 'Ocasional', 'Semanal', 'Diario'].includes(r.alcohol));
  const alcNo = alcoholValid.filter(r => r.alcohol === 'No consume').length;
  const alcOcas = alcoholValid.filter(r => r.alcohol === 'Ocasional').length;
  const alcReg = alcoholValid.filter(r => r.alcohol === 'Semanal' || r.alcohol === 'Diario').length;

  const drugsValid = filteredRecords.filter(r => ['No consume', 'Ex consumidor', 'Ocasional', 'Semanal', 'Diario', 'Activo'].includes(r.drogas));
  const drugNo = drugsValid.filter(r => r.drogas === 'No consume').length;
  const drugOccasionalOrFormer = drugsValid.filter(r => r.drogas === 'Ocasional' || r.drogas === 'Ex consumidor').length;
  const drugActiveOrRegular = drugsValid.filter(r => ['Semanal', 'Diario', 'Activo'].includes(r.drogas)).length;

  const toxCats = ['Sin Consumo / No Fuma', 'Consumo Ocasional / Ex', 'Consumo Activo / Regular'];
  const toxData = [
    [tabNo, tabEx, tabAct],
    [alcNo, alcOcas, alcReg],
    [drugNo, drugOccasionalOrFormer, drugActiveOrRegular]
  ];
  const toxDenominators = [tobaccoValid.length, alcoholValid.length, drugsValid.length];
  const toxDataLabels = chartJsBarDataLabels();
  toxDataLabels.formatter = (value, context) => {
    if (typeof value !== 'number' || value <= 0) return '';
    const denominator = toxDenominators[context.datasetIndex] || 0;
    const pct = denominator > 0 ? ((value / denominator) * 100).toFixed(1).replace('.', ',') : '0,0';
    return `${value} (${pct}%)`;
  };

  const ctxTox = document.getElementById('chart-mod-toxicos');
  if (ctxTox) {
    if (charts.modTox) {
      charts.modTox.data.labels = toxCats;
      charts.modTox.data.datasets[0].data = toxData[0];
      charts.modTox.data.datasets[1].data = toxData[1];
      charts.modTox.data.datasets[2].data = toxData[2];
      charts.modTox.update();
    } else {
      charts.modTox = createDashboardChart(ctxTox, {
        type: 'bar',
        data: {
          labels: toxCats,
          datasets: [
            { label: 'Tabaquismo', data: toxData[0], backgroundColor: PALETTE.emergencyRed, borderRadius: 5 },
            { label: 'Consumo de Alcohol', data: toxData[1], backgroundColor: PALETTE.primaryBlue, borderRadius: 5 },
            { label: 'Consumo de Drogas', data: toxData[2], backgroundColor: PALETTE.purple, borderRadius: 5 }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: { top: 25, right: 8, bottom: 4, left: 4 } },
          scales: {
            y: {
              beginAtZero: true,
              grace: '20%',
              title: { display: true, text: 'Casos (n)', font: { size: 11, weight: 'bold' } }
            }
          },
          plugins: {
            legend: { display: true, position: 'top' },
            datalabels: toxDataLabels
          }
        }
      });
    }
  }

  // Actividad Física por Categoría
  const catNames = [...new Set(filteredRecords.map(r => r.categoria))].filter(Boolean);
  const actSi = catNames.map(c => filteredRecords.filter(r => r.categoria === c && r.actividad_fisica).length);
  const actNo = catNames.map(c => filteredRecords.filter(r => r.categoria === c && (r.actividad_fisica === false)).length);

  const elActCat = document.getElementById('chart-mod-actividad-cat');
  if (elActCat) {
    if (charts.modActCat) {
      charts.modActCat.updateOptions({
        xaxis: { categories: catNames },
        series: [
          { name: 'Activos Físicamente', data: actSi },
          { name: 'Sedentarios', data: actNo }
        ]
      });
    } else {
      charts.modActCat = createDashboardApexChart(elActCat, {
        chart: { type: 'bar', height: 400, toolbar: { show: false }, stacked: true, animations: { enabled: false } },
        fill: { type: 'solid', opacity: 1 },
        colors: [PALETTE.green, PALETTE.emergencyRed],
        plotOptions: { bar: { horizontal: false, columnWidth: '68%', borderRadius: 6, dataLabels: { position: 'center' }, colors: { backgroundBarColors: ['#f1f5f9'], backgroundBarRadius: 6 } } },
        series: [
          { name: 'Activos Físicamente', data: actSi },
          { name: 'Sedentarios', data: actNo }
        ],
        xaxis: { categories: catNames },
        yaxis: { labels: { style: { colors: '#1e293b', fontSize: '12px', fontWeight: 600 } } },
        legend: { position: 'top' },
        dataLabels: apexCountAndPctDataLabel(),
        tooltip: apexCountTooltip()
      });
      charts.modActCat.render();
    }
  }

  // Dieta Mediterránea PREDIMED (Donut con leyenda detallada)
  const predimedAlta = filteredRecords.filter(r => r.predimed_adherencia === 'Buena Adherencia').length;
  const predimedBaja = filteredRecords.filter(r => r.predimed_adherencia === 'Adherencia Moderada/Baja').length;
  const predValid = predimedAlta + predimedBaja;
  const predLegend = [
    `Buena Adherencia Mediterránea: ${predimedAlta} (${formatPct(predimedAlta, predValid)}%)`,
    `Adherencia Moderada / Baja: ${predimedBaja} (${formatPct(predimedBaja, predValid)}%)`
  ];

  const ctxPred = document.getElementById('chart-mod-predimed');
  if (dashboardHasChartData('chart-mod-predimed', 'modPred', predValid)) {
    if (charts.modPred) {
      charts.modPred.data.labels = predLegend;
      charts.modPred.data.datasets[0].data = [predimedAlta, predimedBaja];
      charts.modPred.update();
    } else {
      charts.modPred = createDashboardChart(ctxPred, {
        type: 'doughnut',
        data: {
          labels: predLegend,
          datasets: [{ data: [predimedAlta, predimedBaja], backgroundColor: [PALETTE.green, PALETTE.yellow] }]
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
  const mandatory = [
    ['Hígado graso', 'higado_graso', filteredRecords],
    ['Apnea del sueño', 'apnea_sueno', filteredRecords],
    ['Disfunción eréctil', 'disfuncion_erectil', filteredRecords.filter(r => r.sexo === 'Hombre')],
  ];
  const mandatoryDenominators = mandatory.map(([, field, records]) =>
    records.filter(r => r[field] !== null && r[field] !== undefined).length
  );
  const mandatoryCounts = mandatory.map(([, field, records]) => records.filter(r => r[field] === true).length);
  const mandatoryLabels = mandatory.map(([label]) => label);
  const mandatoryTotalValid = mandatoryDenominators.reduce((a, b) => a + b, 0);

  const elMandatory = document.getElementById('chart-mod-obligatorios');
  if (elMandatory && dashboardHasChartData('chart-mod-obligatorios', 'modMandatory', mandatoryTotalValid)) {
    const options = {
      chart: { type: 'bar', height: 360, toolbar: { show: false } },
      fill: { type: 'solid', opacity: 1 },
      plotOptions: {
        bar: {
          horizontal: false,
          columnWidth: '75%',
          borderRadius: 6,
          dataLabels: { position: 'center' },
          colors: { backgroundBarColors: ['#f1f5f9'], backgroundBarRadius: 6 }
        }
      },
      series: [{ name: 'Casos', data: mandatoryCounts }],
      xaxis: {
        categories: mandatoryLabels,
        labels: {
          rotate: 0,
          rotateAlways: false,
          trim: false,
          style: { fontSize: '12px', fontWeight: 600, colors: '#1e293b' }
        }
      },
      legend: { show: false },
      dataLabels: apexCountAndPctDataLabel(mandatoryDenominators)
    };
    if (charts.modMandatory) charts.modMandatory.updateOptions(options);
    else { charts.modMandatory = createDashboardApexChart(elMandatory, options); charts.modMandatory.render(); }
  }

  const vascular = [
    ['Periférica', 'vasculopatia_periferica'],
    ['Carotídea', 'vasculopatia_carotidea'],
    ['Femoral', 'vasculopatia_femoral'],
    ['Cualquiera', 'vasculopatia_cualquiera']
  ];
  // Omitir subcampos sin ninguna respuesta respondida (n=0)
  const validVascular = vascular.filter(([, field]) => {
    return filteredRecords.some(r => r[field] !== null && r[field] !== undefined);
  });
  const vascularDenominators = validVascular.map(([, field]) =>
    filteredRecords.filter(r => r[field] !== null && r[field] !== undefined).length
  );
  const vascularCounts = validVascular.map(([, field]) => filteredRecords.filter(r => r[field] === true).length);
  const vascularLabels = validVascular.map(([label]) => label);
  const vascularTotalValid = vascularDenominators.reduce((a, b) => a + b, 0);
  const vascularDataLabels = apexCountAndPctDataLabel(vascularDenominators);
  const formatPositiveVascularLabel = vascularDataLabels.formatter;
  vascularDataLabels.formatter = function(val, opt) {
    const value = typeof val === 'number' ? val : parseFloat(val);
    if (!Number.isFinite(value)) return '';
    if (value === 0) {
      const denominator = vascularDenominators[opt?.dataPointIndex ?? 0] || 0;
      return denominator ? `0 (${(0).toFixed(1).replace('.', ',')}%)` : '';
    }
    return formatPositiveVascularLabel(val, opt);
  };
  vascularDataLabels.offsetY = -12;
  vascularDataLabels.style = { ...vascularDataLabels.style, colors: ['#1e293b'] };

  const elVascular = document.getElementById('chart-mod-vasculopatia');
  if (elVascular && dashboardHasChartData('chart-mod-vasculopatia', 'modVasc', vascularTotalValid)) {
    const options = {
      chart: { type: 'bar', height: 360, toolbar: { show: false } },
      fill: { type: 'solid', opacity: 1 },
      plotOptions: {
        bar: {
          horizontal: false,
          columnWidth: '75%',
          borderRadius: 6,
          dataLabels: { position: 'top' },
          colors: { backgroundBarColors: ['#f1f5f9'], backgroundBarRadius: 6 }
        }
      },
      series: [{ name: 'Casos', data: vascularCounts }],
      xaxis: {
        categories: vascularLabels,
        labels: {
          rotate: 0,
          rotateAlways: false,
          trim: false,
          style: { fontSize: '11px', fontWeight: 600, colors: '#1e293b' }
        }
      },
      legend: { show: false },
      dataLabels: vascularDataLabels
    };
    if (charts.modVascular) charts.modVascular.updateOptions(options);
    else { charts.modVascular = createDashboardApexChart(elVascular, options); charts.modVascular.render(); }
  }

  // 6. FASE 3: Cascada de Cuidado de la Hipertensión
  const htaEvaluados = filteredRecords.filter(r => typeof r.hipertension === 'boolean' || r.hipertension === 'Si' || r.hipertension === 'No').length;
  const htaDiag = filteredRecords.filter(r => r.hipertension === true || r.hipertension === 'Si').length;
  const htaTratados = filteredRecords.filter(r => (r.hipertension === true || r.hipertension === 'Si') && r.hta_desc === 'Tratada').length;
  const htaControlados = filteredRecords.filter(r => (r.hipertension === true || r.hipertension === 'Si') && r.hta_desc === 'Tratada' && typeof r.tas === 'number' && typeof r.tad === 'number' && r.tas < 140 && r.tad < 90).length;

  const cascadaCategories = ['Población Evaluada', 'Diagnóstico HTA', 'Tratamiento Farmacológico', 'Control Terapéutico (PA < 140/90)'];
  const cascadaValues = [htaEvaluados, htaDiag, htaTratados, htaControlados];
  const cascadaPcts = [
    100,
    htaEvaluados > 0 ? Number(((htaDiag / htaEvaluados) * 100).toFixed(1)) : 0,
    htaDiag > 0 ? Number(((htaTratados / htaDiag) * 100).toFixed(1)) : 0,
    htaTratados > 0 ? Number(((htaControlados / htaTratados) * 100).toFixed(1)) : 0
  ];

  const elCascada = document.getElementById('chart-mod-cascada-hta');
  if (elCascada && dashboardHasChartData('chart-mod-cascada-hta', 'modCascada', htaEvaluados)) {
    const cascadaMax = htaEvaluados > 0 ? Math.ceil(htaEvaluados * 1.05) : 60;
    const cascadaOptions = {
      chart: { type: 'bar', height: 360, toolbar: { show: false }, animations: { enabled: false } },
      plotOptions: {
        bar: {
          horizontal: true,
          barHeight: '82%',
          distributed: true,
          borderRadius: 6
        }
      },
      colors: [PALETTE.primaryBlue, PALETTE.yellow, PALETTE.teal, PALETTE.green],
      series: [{ name: 'Casos', data: cascadaValues }],
      xaxis: {
        categories: cascadaCategories,
        min: 0,
        max: cascadaMax,
        labels: { formatter: val => Math.round(val) }
      },
      dataLabels: {
        enabled: true,
        formatter: (val, opt) => {
          if (!val || val <= 0) return '';
          const idx = opt.dataPointIndex;
          const pStr = cascadaPcts[idx].toFixed(1).replace('.', ',');
          return `${val} (${pStr}%)`;
        },
        style: { fontSize: '11px', fontWeight: 'bold', colors: ['#ffffff'] }
      },
      legend: { show: false },
      tooltip: {
        custom: function({ dataPointIndex }) {
          const cat = cascadaCategories[dataPointIndex];
          const val = cascadaValues[dataPointIndex];
          const pct = cascadaPcts[dataPointIndex];
          return `<div style="padding: 8px 12px; font-size: 12px; background: #fff; border: 1px solid #e2e8f0; border-radius: 6px;">
            <strong>${cat}</strong><br/>
            <span>Casos:</span> <strong>${val}</strong> (${pct}%)
          </div>`;
        }
      }
    };
    if (charts.modCascada) charts.modCascada.updateOptions(cascadaOptions);
    else { charts.modCascada = createDashboardApexChart(elCascada, cascadaOptions); charts.modCascada.render(); }
  }

  // 7. FASE 3: Hígado Graso según Estado Nutricional y Perímetro Abdominal
  const hgImcGroups = [
    { label: 'Normopeso (IMC < 25)', filter: r => r.imc && r.imc < 25 },
    { label: 'Sobrepeso (25 - 29.9)', filter: r => r.imc && r.imc >= 25 && r.imc < 30 },
    { label: 'Obesidad (≥ 30)', filter: r => r.imc && r.imc >= 30 },
    { label: 'Perímetro Abdom. Riesgo', filter: r => r.abd_riesgo === true }
  ];

  const hgData = hgImcGroups.map(g => {
    const subset = filteredRecords.filter(r => typeof r.higado_graso === 'boolean' && g.filter(r));
    const cases = subset.filter(r => r.higado_graso === true).length;
    const valid = subset.length;
    const pct = valid > 0 ? Number(((cases / valid) * 100).toFixed(1)) : 0;
    return { label: g.label, cases, valid, pct };
  });

  const elHgImc = document.getElementById('chart-mod-higado-imc-perimetro');
  if (elHgImc && dashboardHasChartData('chart-mod-higado-imc-perimetro', 'modHgImc', filteredRecords.filter(r => typeof r.higado_graso === 'boolean').length)) {
    const hgOptions = {
      chart: { type: 'bar', height: 380, toolbar: { show: false }, animations: { enabled: false } },
      plotOptions: {
        bar: {
          horizontal: false,
          columnWidth: '78%',
          distributed: true,
          borderRadius: 6,
          dataLabels: { position: 'center' }
        }
      },
      colors: [PALETTE.green, PALETTE.yellow, PALETTE.emergencyRed, PALETTE.purple],
      series: [{ name: 'Prevalencia Hígado Graso (%)', data: hgData.map(d => d.pct) }],
      xaxis: {
        categories: hgData.map(d => d.label),
        labels: {
          rotate: -20,
          rotateAlways: true,
          style: { fontSize: '11px', fontWeight: 600, colors: '#1e293b' }
        }
      },
      yaxis: { min: 0, max: 100, labels: { formatter: val => `${Math.round(val)}%` }, title: { text: 'Prevalencia Hígado Graso (%)', style: { fontSize: '11px', fontWeight: 700 } } },
      legend: { show: false },
      dataLabels: {
        enabled: true,
        formatter: (val, opt) => {
          const d = hgData[opt.dataPointIndex];
          if (!d || !d.valid || d.valid === 0) return '';
          const pStr = Number(val).toFixed(1).replace('.', ',');
          return [`${d.cases} de ${d.valid}`, `${pStr}%`];
        },
        style: { fontSize: '11px', fontWeight: 700, fontFamily: 'inherit', colors: ['#ffffff'] },
        dropShadow: UNIVERSAL_VALUE_LABEL_STYLE.apexDropShadow,
        background: { enabled: false }
      },
      tooltip: {
        y: {
          formatter: (val, opt) => {
            const d = hgData[opt.dataPointIndex];
            return d ? formatWilsonCiLabel(d.cases, d.valid) : `${val}%`;
          }
        }
      }
    };
    if (charts.modHgImc) charts.modHgImc.updateOptions(hgOptions);
    else { charts.modHgImc = createDashboardApexChart(elHgImc, hgOptions); charts.modHgImc.render(); }
  }

  // 8. FASE 3: Matriz de Co-ocurrencia de Factores Mayores
  const riskMatrixFactors = [
    { label: 'HTA', check: r => r.hipertension === true },
    { label: 'Dislipemia', check: r => r.dislipemia === true },
    { label: 'Obesidad', check: r => r.imc >= 30 },
    { label: 'Sedentarismo', check: r => r.actividad_fisica === false },
    { label: 'Tabaquismo', check: r => r.fumador_activo === true },
    { label: 'Hígado Graso', check: r => r.higado_graso === true },
    { label: 'Mal Sueño', check: r => r.calidad_sueno === 'Mala' || (r.cantidad_sueno && r.cantidad_sueno.includes('<6')) },
    { label: 'Estrés Alto', check: r => r.estres === 'Alto' || r.estres_laboral === true || r.estres_familiar === true }
  ];

  const coocSeries = riskMatrixFactors.map(f1 => ({
    name: f1.label,
    data: riskMatrixFactors.map(f2 => {
      const both = filteredRecords.filter(r => f1.check(r) && f2.check(r)).length;
      return { x: f2.label, y: both };
    })
  }));

  const elCooc = document.getElementById('chart-mod-coocurrencia');
  if (elCooc && dashboardHasChartData('chart-mod-coocurrencia', 'modCooc', filteredRecords.length)) {
    const coocOptions = {
      chart: { type: 'heatmap', height: 350, toolbar: { show: false }, animations: { enabled: false } },
      plotOptions: {
        heatmap: {
          radius: 4,
          enableShades: true,
          colorScale: {
            ranges: [
              { from: 0, to: 0, color: '#f8fafc', name: '0 casos' },
              { from: 1, to: 5, color: '#bfdbfe', name: '1-5 casos' },
              { from: 6, to: 15, color: '#60a5fa', name: '6-15 casos' },
              { from: 16, to: 25, color: '#f59e0b', name: '16-25 casos' },
              { from: 26, to: 60, color: '#ef4444', name: '>25 casos' }
            ]
          }
        }
      },
      dataLabels: {
        enabled: true,
        formatter: val => val > 0 ? val : '0',
        style: { colors: [({ value }) => (Number(value) > 0 ? '#ffffff' : '#0f172a')], fontSize: '11px', fontWeight: 'bold', fontFamily: 'inherit' },
        dropShadow: UNIVERSAL_VALUE_LABEL_STYLE.apexDropShadow
      },
      series: coocSeries,
      xaxis: { labels: { rotate: -45, style: { fontSize: '11px', fontWeight: 600 } } },
      yaxis: { labels: { style: { fontSize: '11px', fontWeight: 600 } } },
      tooltip: {
        y: { formatter: val => `${val} de ${filteredRecords.length} evaluados (${formatPct(val, filteredRecords.length)}%)` }
      }
    };
    if (charts.modCooc) charts.modCooc.updateOptions(coocOptions);
    else { charts.modCooc = createDashboardApexChart(elCooc, coocOptions); charts.modCooc.render(); }
  }

  // 9. FASE 3: Cumplimiento Ítem por Ítem PREDIMED
  const predimedItems = [
    { label: 'Aceite de oliva para cocinar', check: r => r.consume_oliva === true || r.binary_answers?.pred_q1 === true || r.binary_answers?.usa_usted_aceite_de_oliva === true },
    { label: '≥ 2 cdas aceite oliva/día', check: r => r.binary_answers?.pred_q2 === true },
    { label: '≥ 2 raciones verduras/día', check: r => r.consume_verdura === true || r.binary_answers?.pred_q3 === true || r.binary_answers?.usted_consume_verduras === true },
    { label: '≥ 3 piezas fruta/día', check: r => r.consume_fruta === true || r.binary_answers?.pred_q4 === true || r.binary_answers?.usted_consume_fruta === true },
    { label: '< 1 ración carne roja/día', check: r => r.binary_answers?.pred_q5 === true || r.binary_answers?.usted_consume_carne_roja_embut === false },
    { label: '< 1 ración mantequilla/día', check: r => r.binary_answers?.pred_q6 === true || r.binary_answers?.usted_consume_mantequilla_marg === false },
    { label: '< 1 bebida azucarada/día', check: r => r.binary_answers?.pred_q7 === true || r.binary_answers?.usted_consume_bebidas_carbonat === false },
    { label: '≥ 3 raciones legumbres/sem', check: r => r.binary_answers?.pred_q9 === true || r.binary_answers?.usted_consume_legumbres === true },
    { label: '≥ 3 raciones pescado/sem', check: r => r.binary_answers?.pred_q10 === true || r.binary_answers?.usted_consume_pescado_mariscos === true },
    { label: '< 3 veces repostería/sem', check: r => r.binary_answers?.pred_q12 === true || r.binary_answers?.usted_consume_reposteria === false },
    { label: 'Sofrito ≥ 2 veces/sem', check: r => r.binary_answers?.pred_q19 === true || r.binary_answers?.usted_consume_alimentos_con_so === true }
  ];

  const pItemData = predimedItems.map(item => {
    const valid = filteredRecords.filter(r => r.binary_answers && Object.keys(r.binary_answers).length > 0).length || filteredRecords.length;
    const cases = filteredRecords.filter(item.check).length;
    const pct = valid > 0 ? Number(((cases / valid) * 100).toFixed(1)) : 0;
    return { label: item.label, cases, valid, pct };
  });

  const elPItems = document.getElementById('chart-mod-predimed-items');
  if (elPItems && dashboardHasChartData('chart-mod-predimed-items', 'modPItems', pItemData.length)) {
    const pItemOptions = {
      chart: { type: 'bar', height: 520, toolbar: { show: false }, animations: { enabled: false } },
      plotOptions: {
        bar: {
          horizontal: true,
          barHeight: '82%',
          borderRadius: 6,
          distributed: false,
          dataLabels: { position: 'center' }
        }
      },
      colors: [PALETTE.teal],
      series: [{ name: 'Cumplimiento (%)', data: pItemData.map(d => d.pct) }],
      xaxis: { categories: pItemData.map(d => d.label), min: 0, max: 100, labels: { formatter: val => `${Math.round(val)}%` } },
      yaxis: {
        labels: {
          maxWidth: 220,
          style: { fontSize: '11px', fontWeight: 600 }
        }
      },
      legend: { show: false },
      dataLabels: {
        enabled: true,
        formatter: (val, opt) => {
          const d = pItemData[opt.dataPointIndex];
          if (!d || !d.cases || d.cases <= 0) return '';
          const pStr = Number(val).toFixed(1).replace('.', ',');
          return `${d.cases} de ${d.valid} (${pStr}%)`;
        },
        style: { fontSize: '11px', fontWeight: 'bold', colors: ['#ffffff'] }
      },
      tooltip: {
        y: {
          formatter: (val, opt) => {
            const d = pItemData[opt.dataPointIndex];
            return d ? formatWilsonCiLabel(d.cases, d.valid) : `${val}%`;
          }
        }
      }
    };
    if (charts.modPItems) charts.modPItems.updateOptions(pItemOptions);
    else { charts.modPItems = createDashboardApexChart(elPItems, pItemOptions); charts.modPItems.render(); }
  }
}

// -------------------------------------------------------------
// TAB 4: FACTORES EMERGENTES CHARTS
// -------------------------------------------------------------

