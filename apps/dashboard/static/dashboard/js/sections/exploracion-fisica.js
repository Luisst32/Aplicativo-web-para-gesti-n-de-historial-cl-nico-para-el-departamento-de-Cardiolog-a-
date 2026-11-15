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
      charts.expImc = createDashboardApexChart(elImc, {
        chart: { type: 'bar', height: 320, toolbar: { show: false }, animations: { enabled: false } },
        fill: { type: 'solid', opacity: 1 },
        colors: [PALETTE.iceBlue, PALETTE.green, PALETTE.yellow, PALETTE.emergencyRed, '#DC2626', '#991B1B'],
        plotOptions: {
          bar: {
            horizontal: true,
            barHeight: '78%',
            distributed: true,
            borderRadius: 6,
            dataLabels: { position: 'center' },
            colors: { backgroundBarColors: ['#f1f5f9'], backgroundBarRadius: 6 }
          }
        },
        series: [{ name: 'Casos', data: imcCounts }],
        xaxis: { categories: imcCats, min: 0, max: Math.max(2, Math.ceil(Math.max(...imcCounts, 1) * 1.15)), tickAmount: 4 },
        legend: { show: false },
        dataLabels: apexCountAndPctDataLabel(),
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
      charts.expScatter = createDashboardChart(ctxScatter, {
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
      charts.expPa = createDashboardChart(ctxPa, {
        type: 'doughnut',
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
  const auscNorm = filteredRecords.filter(r => r.ausc_pulm_normal && r.ausc_abdom_normal && (r.soplos === false)).length;
  const soplosPres = filteredRecords.filter(r => r.soplos).length;
  const auscAlt = filteredRecords.filter(r => (r.ausc_pulm_normal === false) || (r.ausc_abdom_normal === false)).length;

  renderThreeStateChart('chart-exp-auscultacion','expAusc', [["Pulmonar normal", "ausc_pulm_normal"], ["Abdominal normal", "ausc_abdom_normal"], ["Soplos", "soplos"]]);

  // 5. FASE 3: Dispersión Hemodinámica TAS vs TAD con Zonas ESC/ESH
  const bpValidRecords = filteredRecords.filter(r => typeof r.tas === 'number' && typeof r.tad === 'number' && r.tas > 0 && r.tad > 0);
  const bpHombres = bpValidRecords.filter(r => r.sexo === 'Hombre').map(r => ({ x: r.tad, y: r.tas, code: r.study_code, cat: r.pa_categoria }));
  const bpMujeres = bpValidRecords.filter(r => r.sexo === 'Mujer').map(r => ({ x: r.tad, y: r.tas, code: r.study_code, cat: r.pa_categoria }));

  const elBpScatter = document.getElementById('chart-ef-scatter-tas-tad');
  if (elBpScatter && dashboardHasChartData('chart-ef-scatter-tas-tad', 'efBpScatter', bpValidRecords.length)) {
    const bpOptions = {
      chart: { type: 'scatter', height: 380, toolbar: { show: false }, animations: { enabled: false } },
      colors: [PALETTE.primaryBlue, PALETTE.purple],
      series: [
        { name: 'Hombres', data: bpHombres },
        { name: 'Mujeres', data: bpMujeres }
      ],
      xaxis: {
        title: { text: 'Tensión Arterial Diastólica - TAD (mmHg)', style: { fontWeight: 600 } },
        min: 50,
        max: 115,
        tickAmount: 6,
        labels: { formatter: val => Math.round(val) }
      },
      yaxis: {
        title: { text: 'Tensión Arterial Sistólica - TAS (mmHg)', style: { fontWeight: 600 } },
        min: 85,
        max: 185,
        tickAmount: 5,
        labels: { formatter: val => Math.round(val) }
      },
      annotations: {
        yaxis: [
          {
            y: 130,
            borderColor: '#d97706',
            strokeDashArray: 4,
            label: {
              text: 'TAS Normal-Alta (130 mmHg)',
              position: 'left',
              textAnchor: 'start',
              style: { background: '#d97706', color: '#ffffff', fontSize: '11px', fontWeight: 600, padding: { left: 6, right: 6, top: 2, bottom: 2 } }
            }
          },
          {
            y: 140,
            borderColor: PALETTE.emergencyRed,
            strokeDashArray: 4,
            label: {
              text: 'TAS Corte HTA (140 mmHg)',
              position: 'right',
              textAnchor: 'end',
              style: { background: PALETTE.emergencyRed, color: '#ffffff', fontSize: '11px', fontWeight: 600, padding: { left: 6, right: 6, top: 2, bottom: 2 } }
            }
          }
        ],
        xaxis: [
          {
            x: 80,
            borderColor: '#d97706',
            strokeDashArray: 4,
            label: {
              text: 'TAD Normal-Alta (80 mmHg)',
              orientation: 'horizontal',
              position: 'top',
              offsetY: 0,
              offsetX: -45,
              style: { background: '#d97706', color: '#ffffff', fontSize: '11px', fontWeight: 600, padding: { left: 6, right: 6, top: 2, bottom: 2 } }
            }
          },
          {
            x: 90,
            borderColor: PALETTE.emergencyRed,
            strokeDashArray: 4,
            label: {
              text: 'TAD Corte HTA (90 mmHg)',
              orientation: 'horizontal',
              position: 'top',
              offsetY: 26,
              offsetX: 45,
              style: { background: PALETTE.emergencyRed, color: '#ffffff', fontSize: '11px', fontWeight: 600, padding: { left: 6, right: 6, top: 2, bottom: 2 } }
            }
          }
        ]
      },
      tooltip: {
        custom: function({ seriesIndex, dataPointIndex, w }) {
          const pt = w.config.series[seriesIndex].data[dataPointIndex];
          const gender = seriesIndex === 0 ? 'Hombre' : 'Mujer';
          return `<div style="padding: 8px 12px; font-size: 12px; background: #fff; border: 1px solid #e2e8f0; border-radius: 6px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
            <strong>Ficha #${pt.code || '—'} (${gender})</strong><br/>
            <span style="color: #0284c7;">TAS:</span> ${pt.y} mmHg · <span style="color: #0284c7;">TAD:</span> ${pt.x} mmHg<br/>
            <span style="color: #64748b;">Estratificación:</span> ${pt.cat || 'Evaluado'}
          </div>`;
        }
      }
    };
    if (charts.efBpScatter) {
      charts.efBpScatter.updateOptions(bpOptions);
    } else {
      charts.efBpScatter = createDashboardApexChart(elBpScatter, bpOptions);
      charts.efBpScatter.render();
    }
  }

  // 6. FASE 3: TAS y Perímetro Abdominal según Categoría de IMC y Sexo (Fila Completa, 4 Series)
  const imcGroups = [
    { label: 'Normopeso (IMC < 25)', filter: r => r.imc && r.imc < 25 },
    { label: 'Sobrepeso (25-29.9)', filter: r => r.imc && r.imc >= 25 && r.imc < 30 },
    { label: 'Obesidad (≥ 30)', filter: r => r.imc && r.imc >= 30 }
  ];

  const tasMeanH = imcGroups.map(g => {
    const subset = filteredRecords.filter(r => r.sexo === 'Hombre' && g.filter(r) && typeof r.tas === 'number');
    return subset.length ? Number((subset.reduce((acc, c) => acc + c.tas, 0) / subset.length).toFixed(1)) : 0;
  });
  const tasMeanM = imcGroups.map(g => {
    const subset = filteredRecords.filter(r => r.sexo === 'Mujer' && g.filter(r) && typeof r.tas === 'number');
    return subset.length ? Number((subset.reduce((acc, c) => acc + c.tas, 0) / subset.length).toFixed(1)) : 0;
  });
  const waistMeanH = imcGroups.map(g => {
    const subset = filteredRecords.filter(r => r.sexo === 'Hombre' && g.filter(r) && typeof r.perimetro_abdominal === 'number');
    return subset.length ? Number((subset.reduce((acc, c) => acc + c.perimetro_abdominal, 0) / subset.length).toFixed(1)) : 0;
  });
  const waistMeanM = imcGroups.map(g => {
    const subset = filteredRecords.filter(r => r.sexo === 'Mujer' && g.filter(r) && typeof r.perimetro_abdominal === 'number');
    return subset.length ? Number((subset.reduce((acc, c) => acc + c.perimetro_abdominal, 0) / subset.length).toFixed(1)) : 0;
  });

  const elImcTas = document.getElementById('chart-ef-box-tas-perimetro');
  if (elImcTas && dashboardHasChartData('chart-ef-box-tas-perimetro', 'efImcTas', filteredRecords.filter(r => r.imc && (r.tas || r.perimetro_abdominal)).length)) {
    const imcTasOptions = {
      chart: { type: 'bar', height: 400, toolbar: { show: false }, animations: { enabled: false } },
      plotOptions: {
        bar: {
          horizontal: false,
          columnWidth: '65%',
          borderRadius: 5
        }
      },
      colors: [PALETTE.primaryBlue, PALETTE.purple, PALETTE.teal, PALETTE.yellow],
      series: [
        { name: 'TAS Media Hombres (mmHg)', data: tasMeanH },
        { name: 'TAS Media Mujeres (mmHg)', data: tasMeanM },
        { name: 'Perímetro Abdominal Hombres (cm)', data: waistMeanH },
        { name: 'Perímetro Abdominal Mujeres (cm)', data: waistMeanM }
      ],
      xaxis: {
        categories: imcGroups.map(g => g.label),
        labels: { style: { fontSize: '12px', fontWeight: 600 } }
      },
      yaxis: {
        min: 0,
        max: 160,
        tickAmount: 4,
        title: { text: 'Media Clínica (TAS en mmHg · Perímetro en cm)', style: { fontWeight: 600 } },
        labels: { formatter: val => Math.round(val) }
      },
      dataLabels: {
        enabled: true,
        formatter: (val, opt) => {
          if (!val || val <= 0) return '';
          const sIdx = opt?.seriesIndex ?? 0;
          const unit = sIdx < 2 ? 'mmHg' : 'cm';
          const valNum = Number(val);
          const valStr = Number.isInteger(valNum) ? String(valNum) : valNum.toFixed(1).replace('.', ',');
          return [valStr, unit];
        },
        style: { fontSize: '10px', fontWeight: 700, fontFamily: 'inherit', colors: ['#ffffff'] },
        dropShadow: UNIVERSAL_VALUE_LABEL_STYLE.apexDropShadow,
        background: { enabled: false }
      },
      legend: { position: 'top', horizontalAlign: 'center' }
    };
    if (charts.efImcTas) {
      charts.efImcTas.updateOptions(imcTasOptions);
    } else {
      charts.efImcTas = createDashboardApexChart(elImcTas, imcTasOptions);
      charts.efImcTas.render();
    }
  }

  // 7. FASE 3: Matriz de Correlación de Spearman
  function spearmanRank(xArr, yArr) {
    const pairs = [];
    for (let i = 0; i < xArr.length; i++) {
      if (typeof xArr[i] === 'number' && !isNaN(xArr[i]) && typeof yArr[i] === 'number' && !isNaN(yArr[i])) {
        pairs.push({ x: xArr[i], y: yArr[i] });
      }
    }
    const nPts = pairs.length;
    if (nPts < 5) return 0;

    const rank = (arr, key) => {
      const sorted = arr.map((item, idx) => ({ val: item[key], idx })).sort((a, b) => a.val - b.val);
      const ranks = new Array(nPts);
      let i = 0;
      while (i < nPts) {
        let j = i;
        while (j < nPts - 1 && sorted[j].val === sorted[j + 1].val) j++;
        const avgR = (i + j + 2) / 2;
        for (let k = i; k <= j; k++) ranks[sorted[k].idx] = avgR;
        i = j + 1;
      }
      return ranks;
    };

    const rX = rank(pairs, 'x');
    const rY = rank(pairs, 'y');
    let num = 0, denX = 0, denY = 0;
    const mean = (nPts + 1) / 2;
    for (let i = 0; i < nPts; i++) {
      const dx = rX[i] - mean;
      const dy = rY[i] - mean;
      num += dx * dy;
      denX += dx * dx;
      denY += dy * dy;
    }
    const den = Math.sqrt(denX * denY);
    return den === 0 ? 0 : Number((num / den).toFixed(2));
  }

  const corrVars = [
    { label: 'IMC', getter: r => r.imc },
    { label: 'Perímetro', getter: r => r.perimetro_abdominal },
    { label: 'TAS', getter: r => r.tas },
    { label: 'TAD', getter: r => r.tad },
    { label: 'Edad', getter: r => r.edad },
    { label: 'FC', getter: r => r.fc || r.ecg_fc },
    { label: 'PR (ms)', getter: r => r.ecg_pr_ms },
    { label: 'QTc (ms)', getter: r => r.ecg_qtc_ms },
    { label: 'SatO2', getter: r => r.sat_o2 }
  ];

  const heatmapSeries = corrVars.map(vY => {
    const yVals = filteredRecords.map(vY.getter);
    return {
      name: vY.label,
      data: corrVars.map(vX => {
        const xVals = filteredRecords.map(vX.getter);
        return {
          x: vX.label,
          y: spearmanRank(xVals, yVals)
        };
      })
    };
  });

  const elHeatmap = document.getElementById('chart-ef-heatmap-correlacion');
  if (elHeatmap && dashboardHasChartData('chart-ef-heatmap-correlacion', 'efHeatmap', filteredRecords.length)) {
    const heatOptions = {
      chart: { type: 'heatmap', height: 350, toolbar: { show: false }, animations: { enabled: false } },
      plotOptions: {
        heatmap: {
          radius: 3,
          enableShades: false,
          colorScale: {
            ranges: [
              { from: -1.0, to: -0.21, color: '#3b82f6', name: 'Inversa Moderada/Fuerte (-1.0 a -0.2)' },
              { from: -0.2, to: 0.2, color: '#f8fafc', name: 'Nula / Débil (-0.2 a +0.2)' },
              { from: 0.21, to: 0.59, color: '#f59e0b', name: 'Directa Moderada (+0.2 a +0.6)' },
              { from: 0.6, to: 1.0, color: '#ef4444', name: 'Directa Fuerte (+0.6 a +1.0)' }
            ]
          }
        }
      },
      dataLabels: {
        enabled: true,
        formatter: val => val !== undefined ? val.toFixed(2) : '',
        style: { colors: [({ value }) => (value !== 0 ? '#ffffff' : '#0f172a')], fontSize: '11px', fontWeight: 700, fontFamily: 'inherit' },
        dropShadow: UNIVERSAL_VALUE_LABEL_STYLE.apexDropShadow
      },
      series: heatmapSeries,
      xaxis: { labels: { rotate: -45, style: { fontSize: '11px', fontWeight: 600 } } },
      yaxis: { labels: { style: { fontSize: '11px', fontWeight: 600 } } },
      tooltip: {
        y: { formatter: val => `Spearman r = ${val}` }
      }
    };
    if (charts.efHeatmap) {
      charts.efHeatmap.updateOptions(heatOptions);
    } else {
      charts.efHeatmap = createDashboardApexChart(elHeatmap, heatOptions);
      charts.efHeatmap.render();
    }
  }
}

// -------------------------------------------------------------
// TAB 3: FACTORES DE RIESGO MODIFICABLES CHARTS
// -------------------------------------------------------------

