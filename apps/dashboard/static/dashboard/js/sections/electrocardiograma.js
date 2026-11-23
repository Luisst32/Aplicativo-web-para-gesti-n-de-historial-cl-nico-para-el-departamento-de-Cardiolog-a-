function renderTabElectrocardiograma() {
  const n = filteredRecords.length;
  const sinusalCnt = filteredRecords.filter(r => r.ecg_es_sinusal).length;
  const arritmiaCnt = filteredRecords.filter(r => r.ecg_arritmia).length;

  const elRitmo = document.getElementById('chart-ecg-ritmo');
  if (elRitmo) {
    if (charts.ecgRitmo) {
      charts.ecgRitmo.updateOptions({
        series: [sinusalCnt, arritmiaCnt]
      });
    } else {
      charts.ecgRitmo = createDashboardApexChart(elRitmo, {
        chart: { type: 'donut', height: 320, animations: { enabled: false } },
        fill: { type: 'solid', opacity: 1 },
        colors: [PALETTE.green, PALETTE.emergencyRed],
        labels: ['Ritmo Sinusal (Normal)', 'Arritmias / Otros Ritmos'],
        series: [sinusalCnt, arritmiaCnt],
        legend: { position: 'bottom' },
        dataLabels: {
          enabled: true,
          formatter: (val, opt) => {
            const cnt = opt.seriesIndex === 0 ? sinusalCnt : arritmiaCnt;
            return `${cnt} (${val.toFixed(1)}%)`;
          },
          style: { fontSize: '11px', fontWeight: 'bold', colors: ['#ffffff'] },
          background: {
            enabled: false
          },
          dropShadow: { enabled: true, top: 1, left: 0, blur: 1, color: '#0f172a', opacity: 0.45 }
        },
        tooltip: apexCountTooltip()
      });
      charts.ecgRitmo.render();
    }
  }

  // Intervalos de Conducción
  const prNorm = filteredRecords.filter(r => r.ecg_pr_cat.includes('Normal')).length;
  const prBloq = filteredRecords.filter(r => r.ecg_pr_cat.includes('Bloqueo')).length;
  const qrsNorm = filteredRecords.filter(r => r.ecg_qrs_cat.includes('Normal')).length;
  const qrsBloq = filteredRecords.filter(r => r.ecg_qrs_cat.includes('Bloqueo') || r.ecg_qrs_cat.includes('Incompleto')).length;
  const qtcNorm = filteredRecords.filter(r => r.ecg_qtc_cat.includes('Normal')).length;
  const qtcProl = filteredRecords.filter(r => r.ecg_qtc_cat.includes('Prolongado')).length;

  const ctxInterv = document.getElementById('chart-ecg-intervalos');
  if (ctxInterv) {
    if (charts.ecgInterv) {
      charts.ecgInterv.data.datasets[0].data = [prNorm, qrsNorm, qtcNorm];
      charts.ecgInterv.data.datasets[1].data = [prBloq, qrsBloq, qtcProl];
      charts.ecgInterv.update();
    } else {
      charts.ecgInterv = createDashboardChart(ctxInterv, {
        type: 'bar',
        data: {
          labels: ['Intervalo PR', 'Duración QRS', 'Intervalo QTc Bazett'],
          datasets: [
            { label: 'Dentro de Límites Normales', data: [prNorm, qrsNorm, qtcNorm], backgroundColor: PALETTE.green },
            { label: 'Prolongado / Bloqueo Conducción', data: [prBloq, qrsBloq, qtcProl], backgroundColor: PALETTE.emergencyRed }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: { top: 25, right: 8, bottom: 4, left: 4 } },
          scales: {
            x: { stacked: true },
            y: {
              stacked: true,
              beginAtZero: true,
              grace: '20%',
              title: { display: true, text: 'Casos (n)', font: { size: 11, weight: 'bold' } }
            }
          },
          plugins: {
            legend: { position: 'bottom' },
            datalabels: {
              display: (ctx) => ctx.dataset.data[ctx.dataIndex] > 0,
              color: '#ffffff',
              anchor: 'center',
              align: 'center',
              backgroundColor: 'transparent',
              borderRadius: 0,
              padding: { top: 1, bottom: 1, left: 2, right: 2 },
              borderWidth: 0,
              font: { weight: 'bold', size: 9.5 },
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

  // Anomalías de Conducción y Morfología
  renderThreeStateChart('chart-ecg-anomalias','ecgAnom', [['HVI','ecg_hvi'],['Bloqueo de rama','ecg_bloqueo_presente'],['Repolarizacion','ecg_repolarizacion']]);

  // Frecuencia Cardíaca ECG vs Frecuencia Clínica
  const meanOrNull = field => {
    const values = filteredRecords
      .map(record => record[field])
      .filter(value => typeof value === 'number' && Number.isFinite(value));
    return values.length
      ? Math.round(values.reduce((total, value) => total + value, 0) / values.length)
      : null;
  };
  const fcEcgMedia = meanOrNull('ecg_fc');
  const fcClinicaMedia = meanOrNull('fc');
  const fcLabels = [
    fcEcgMedia === null ? ['FC por Trazado', 'ECG (sin dato)'] : ['FC por Trazado', 'ECG'],
    fcClinicaMedia === null ? ['FC por Auscultación', 'Pulso (sin dato)'] : ['FC por Auscultación', 'o Pulso']
  ];

  const ctxFc = document.getElementById('chart-ecg-fc-comparativa');
  if (ctxFc) {
    if (charts.ecgFc) {
      charts.ecgFc.data.datasets[0].data = [fcEcgMedia, fcClinicaMedia];
      charts.ecgFc.data.labels = fcLabels;
      charts.ecgFc.update();
    } else {
      charts.ecgFc = createDashboardChart(ctxFc, {
        type: 'bar',
        data: {
          labels: fcLabels,
          datasets: [{
            label: 'Latidos por Minuto (lpm)',
            data: [fcEcgMedia, fcClinicaMedia],
            backgroundColor: [PALETTE.primaryBlue, PALETTE.teal],
            borderRadius: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: {
            padding: { top: 16, right: 12, bottom: 8, left: 8 }
          },
          scales: {
            x: {
              grid: { display: false },
              border: { display: false },
              ticks: { maxRotation: 0, minRotation: 0, color: '#1e293b', font: { size: 12, weight: '600' } }
            },
            y: {
              min: 40,
              max: 120,
              beginAtZero: false,
              grid: { color: '#edf2f7' },
              border: { display: false },
              ticks: { precision: 0, color: '#1e293b', font: { size: 12, weight: '600' } },
              title: { display: true, text: 'Frecuencia Cardíaca (lpm)' }
            }
          },
          plugins: {
            legend: { display: false },
            datalabels: {
              display: (context) => typeof context.dataset.data[context.dataIndex] === 'number',
              anchor: 'end',
              align: 'bottom',
              offset: 16,
              font: { weight: 'bold', size: 12, family: 'inherit' },
              color: '#ffffff',
              textStrokeColor: 'rgba(15, 23, 42, 0.50)',
              textStrokeWidth: 2,
              textShadowBlur: 3,
              textShadowColor: 'rgba(0, 0, 0, 0.35)',
              backgroundColor: 'transparent',
              clip: false,
              formatter: (val) => typeof val === 'number' ? `${val} lpm` : ''
            }
          }
        }
      });
    }
  }

  // -------------------------------------------------------------
  // FASE 3: 4 NUEVAS GRÁFICAS DE ELECTROCARDIOGRAMA
  // -------------------------------------------------------------

  // 1. Histograma QTc con líneas de corte clínico (450 ms ♂ / 460 ms ♀)
  const elHistQtc = document.getElementById('chart-ecg-hist-qtc');
  if (elHistQtc) {
    const validEcg = filteredRecords.filter(r => r.ecg_qtc_ms !== null && r.ecg_qtc_ms !== undefined);
    const bins = [
      { label: '< 390 ms', filter: q => q < 390 },
      { label: '390-409 ms', filter: q => q >= 390 && q < 410 },
      { label: '410-429 ms', filter: q => q >= 410 && q < 430 },
      { label: '430-449 ms', filter: q => q >= 430 && q < 450 },
      { label: '450-459 ms', filter: q => q >= 450 && q < 460 },
      { label: '≥ 460 ms', filter: q => q >= 460 }
    ];

    const hRecords = validEcg.filter(r => r.sexo === 'Hombre');
    const mRecords = validEcg.filter(r => r.sexo === 'Mujer');

    const hCounts = bins.map(b => hRecords.filter(r => b.filter(r.ecg_qtc_ms)).length);
    const mCounts = bins.map(b => mRecords.filter(r => b.filter(r.ecg_qtc_ms)).length);

    if (dashboardHasChartData('chart-ecg-hist-qtc', 'ecgHistQtc', validEcg.length)) {
      const histOptions = {
        chart: { type: 'bar', height: 360, toolbar: { show: false }, animations: { enabled: false } },
        plotOptions: {
          bar: {
            horizontal: false,
            columnWidth: '88%',
            borderRadius: 6,
            colors: {
              backgroundBarColors: []
            }
          }
        },
        colors: [PALETTE.primaryBlue, PALETTE.purple],
        series: [
          { name: `Hombres (n=${hRecords.length})`, data: hCounts },
          { name: `Mujeres (n=${mRecords.length})`, data: mCounts }
        ],
        xaxis: {
          categories: bins.map(b => b.label),
          title: { text: 'Intervalo QTc Bazett (ms)', style: { fontSize: '11px', fontWeight: 700 } }
        },
        yaxis: {
          title: { text: 'Evaluados (n)', style: { fontSize: '11px', fontWeight: 700 } },
          min: 0,
          forceNiceScale: true
        },
        legend: { position: 'top', horizontalAlign: 'center' },
        annotations: {
          xaxis: [
            {
              x: '450-459 ms',
              borderColor: PALETTE.primaryBlue,
              strokeDashArray: 4,
              borderWidth: 2,
              label: {
                borderColor: PALETTE.primaryBlue,
                orientation: 'horizontal',
                position: 'top',
                offsetY: 0,
                style: { color: '#ffffff', background: PALETTE.primaryBlue, fontSize: '11px', fontWeight: 700, padding: { left: 6, right: 6, top: 2, bottom: 2 } },
                text: 'Corte ♂ (450 ms)'
              }
            },
            {
              x: '≥ 460 ms',
              borderColor: PALETTE.purple,
              strokeDashArray: 4,
              borderWidth: 2,
              label: {
                borderColor: PALETTE.purple,
                orientation: 'horizontal',
                position: 'top',
                offsetY: 0,
                style: { color: '#ffffff', background: PALETTE.purple, fontSize: '11px', fontWeight: 700, padding: { left: 6, right: 6, top: 2, bottom: 2 } },
                text: 'Corte ♀ (460 ms)'
              }
            }
          ]
        },
        dataLabels: {
          enabled: true,
          formatter: (v, opt) => {
            if (!v || v <= 0) return '';
            const isH = opt.seriesIndex === 0;
            const tot = isH ? hRecords.length : mRecords.length;
            return `${v} (${formatPct(v, tot)}%)`;
          },
          style: { fontSize: '11px', fontWeight: 700, fontFamily: 'inherit', colors: ['#ffffff'] },
          dropShadow: UNIVERSAL_VALUE_LABEL_STYLE.apexDropShadow,
          background: { enabled: false }
        },
        tooltip: {
          y: {
            formatter: (v, opt) => {
              const isH = opt.seriesIndex === 0;
              const tot = isH ? hRecords.length : mRecords.length;
              const ci = wilsonScoreInterval(v, tot);
              return `${v} de ${tot} (${formatPct(v, tot)}%; IC 95%: ${ci.lower.toFixed(1)}-${ci.upper.toFixed(1)}%)`;
            }
          }
        }
      };

      if (charts.ecgHistQtc) {
        charts.ecgHistQtc.updateOptions(histOptions);
      } else {
        charts.ecgHistQtc = createDashboardApexChart(elHistQtc, histOptions);
        charts.ecgHistQtc.render();
      }
    }
  }

  // 2. Boxplots de PR, QRS y QTc por sexo
  const elBoxEcg = document.getElementById('chart-ecg-box-pr-qrs-qtc');
  if (elBoxEcg) {
    function calcBoxStats(arr) {
      if (!arr || arr.length === 0) return [0, 0, 0, 0, 0];
      const s = [...arr].sort((a, b) => a - b);
      const q = p => {
        const pos = (s.length - 1) * p;
        const b = Math.floor(pos);
        const r = pos - b;
        return s[b + 1] !== undefined ? Math.round(s[b] + r * (s[b + 1] - s[b])) : s[b];
      };
      return [s[0], q(0.25), q(0.5), q(0.75), s[s.length - 1]];
    }

    const hEcg = filteredRecords.filter(r => r.sexo === 'Hombre' && r.ecg_qtc_ms !== null);
    const mEcg = filteredRecords.filter(r => r.sexo === 'Mujer' && r.ecg_qtc_ms !== null);

    const hPR = hEcg.map(r => r.ecg_pr_ms).filter(v => v !== null && v !== undefined);
    const mPR = mEcg.map(r => r.ecg_pr_ms).filter(v => v !== null && v !== undefined);

    const hQRS = hEcg.map(r => r.ecg_qrs_ms).filter(v => v !== null && v !== undefined);
    const mQRS = mEcg.map(r => r.ecg_qrs_ms).filter(v => v !== null && v !== undefined);

    const hQTc = hEcg.map(r => r.ecg_qtc_ms).filter(v => v !== null && v !== undefined);
    const mQTc = mEcg.map(r => r.ecg_qtc_ms).filter(v => v !== null && v !== undefined);

    if (dashboardHasChartData('chart-ecg-box-pr-qrs-qtc', 'ecgBox', hQTc.length + mQTc.length)) {
      const boxOptions = {
        chart: { type: 'boxPlot', height: 320, toolbar: { show: false }, animations: { enabled: false } },
        colors: [PALETTE.primaryBlue, PALETTE.purple],
        plotOptions: {
          boxPlot: {
            colors: {
              upper: PALETTE.primaryBlue,
              lower: PALETTE.purple
            }
          }
        },
        series: [
          {
            name: `Hombres (n=${hEcg.length})`,
            type: 'boxPlot',
            data: [
              { x: 'Intervalo PR', y: calcBoxStats(hPR) },
              { x: 'Duración QRS', y: calcBoxStats(hQRS) },
              { x: 'Intervalo QTc', y: calcBoxStats(hQTc) }
            ]
          },
          {
            name: `Mujeres (n=${mEcg.length})`,
            type: 'boxPlot',
            data: [
              { x: 'Intervalo PR', y: calcBoxStats(mPR) },
              { x: 'Duración QRS', y: calcBoxStats(mQRS) },
              { x: 'Intervalo QTc', y: calcBoxStats(mQTc) }
            ]
          }
        ],
        xaxis: {
          categories: ['Intervalo PR', 'Duración QRS', 'Intervalo QTc']
        },
        yaxis: {
          title: { text: 'Milisegundos (ms)', style: { fontSize: '11px', fontWeight: 700 } },
          min: 60,
          max: 480
        },
        legend: { position: 'top', horizontalAlign: 'center' },
        tooltip: {
          shared: false,
          intersect: true
        }
      };

      if (charts.ecgBox) {
        charts.ecgBox.updateOptions(boxOptions);
      } else {
        charts.ecgBox = createDashboardApexChart(elBoxEcg, boxOptions);
        charts.ecgBox.render();
      }
    }
  }

  // 3. Dispersión: Edad vs. Intervalo QTc Bazett por Sexo
  const elScatterQtc = document.getElementById('chart-ecg-scatter-edad-qtc');
  if (elScatterQtc) {
    const hScatter = filteredRecords
      .filter(r => r.sexo === 'Hombre' && r.edad && r.ecg_qtc_ms)
      .map(r => [r.edad, r.ecg_qtc_ms]);
    const mScatter = filteredRecords
      .filter(r => r.sexo === 'Mujer' && r.edad && r.ecg_qtc_ms)
      .map(r => [r.edad, r.ecg_qtc_ms]);

    if (dashboardHasChartData('chart-ecg-scatter-edad-qtc', 'ecgScatter', hScatter.length + mScatter.length)) {
      const scatterOptions = {
        chart: { type: 'scatter', height: 320, toolbar: { show: false }, animations: { enabled: false } },
        colors: [PALETTE.primaryBlue, PALETTE.purple],
        series: [
          { name: `Hombres (n=${hScatter.length})`, data: hScatter },
          { name: `Mujeres (n=${mScatter.length})`, data: mScatter }
        ],
        xaxis: {
          title: { text: 'Edad (años)', style: { fontSize: '11px', fontWeight: 700 } },
          min: 20,
          max: 75,
          tickAmount: 6
        },
        yaxis: {
          title: { text: 'QTc Bazett (ms)', style: { fontSize: '11px', fontWeight: 700 } },
          min: 350,
          max: 480,
          tickAmount: 6
        },
        markers: { size: 6, strokeWidth: 1.5, strokeColors: '#ffffff' },
        legend: { position: 'top', horizontalAlign: 'center' },
        annotations: {
          yaxis: [
            {
              y: 450,
              borderColor: PALETTE.primaryBlue,
              strokeDashArray: 4,
              borderWidth: 2,
              label: {
                borderColor: PALETTE.primaryBlue,
                style: { color: '#ffffff', background: PALETTE.primaryBlue, fontSize: '10px', fontWeight: 700 },
                text: 'Límite Normal ♂ (450 ms)'
              }
            },
            {
              y: 460,
              borderColor: PALETTE.purple,
              strokeDashArray: 4,
              borderWidth: 2,
              label: {
                borderColor: PALETTE.purple,
                style: { color: '#ffffff', background: PALETTE.purple, fontSize: '10px', fontWeight: 700 },
                text: 'Límite Normal ♀ (460 ms)'
              }
            }
          ]
        },
        tooltip: {
          custom: function({ series, seriesIndex, dataPointIndex, w }) {
            const pt = w.config.series[seriesIndex].data[dataPointIndex];
            const sexLabel = seriesIndex === 0 ? 'Hombre' : 'Mujer';
            return `<div style="padding: 8px 12px; font-size: 11px;">
              <strong>${sexLabel}</strong><br/>
              Edad: <strong>${pt[0]} años</strong><br/>
              QTc: <strong>${pt[1]} ms</strong>
            </div>`;
          }
        }
      };

      if (charts.ecgScatter) {
        charts.ecgScatter.updateOptions(scatterOptions);
      } else {
        charts.ecgScatter = createDashboardApexChart(elScatterQtc, scatterOptions);
        charts.ecgScatter.render();
      }
    }
  }

  // 4. Prevalencia de ECG Anormal según Factores de Riesgo Cardiovascular
  const elAbnFact = document.getElementById('chart-ecg-anormal-factores');
  if (elAbnFact) {
    const riskFactors = [
      { name: 'HTA Diagnosticada', has: r => r.hipertension === true, lacks: r => r.hipertension === false },
      { name: 'Dislipemia', has: r => r.dislipemia === true, lacks: r => r.dislipemia === false },
      { name: 'Sobrepeso / Obesidad', has: r => r.sobrepeso_u_obesidad === true, lacks: r => r.sobrepeso_u_obesidad === false },
      { name: 'Edad ≥ 50 años', has: r => (r.edad || 0) >= 50, lacks: r => (r.edad || 0) < 50 }
    ];

    const validEcg = filteredRecords.filter(r => r.ecg_anormal !== null && r.ecg_anormal !== undefined);

    const factData = riskFactors.map(f => {
      const groupWith = validEcg.filter(f.has);
      const groupWithout = validEcg.filter(f.lacks);

      const abnWith = groupWith.filter(r => r.ecg_anormal === true).length;
      const abnWithout = groupWithout.filter(r => r.ecg_anormal === true).length;

      const pctWith = groupWith.length ? (abnWith / groupWith.length * 100) : 0;
      const pctWithout = groupWithout.length ? (abnWithout / groupWithout.length * 100) : 0;

      return {
        name: f.name,
        nWith: groupWith.length,
        abnWith,
        pctWith,
        nWithout: groupWithout.length,
        abnWithout,
        pctWithout
      };
    });

    if (dashboardHasChartData('chart-ecg-anormal-factores', 'ecgAbnFact', validEcg.length)) {
      const abnFactOptions = {
        chart: { type: 'bar', height: 320, toolbar: { show: false }, animations: { enabled: false } },
        plotOptions: {
          bar: {
            horizontal: true,
            barHeight: '62%',
            borderRadius: 5
          }
        },
        colors: [PALETTE.emergencyRed, PALETTE.teal],
        series: [
          { name: 'Con Factor de Riesgo', data: factData.map(d => parseFloat(d.pctWith.toFixed(1))) },
          { name: 'Sin Factor de Riesgo', data: factData.map(d => parseFloat(d.pctWithout.toFixed(1))) }
        ],
        xaxis: {
          categories: factData.map(d => d.name),
          title: { text: 'Prevalencia de ECG Anormal (%)', style: { fontSize: '11px', fontWeight: 700 } },
          min: 0,
          max: 60,
          labels: { formatter: v => `${v}%` }
        },
        yaxis: {
          labels: { maxWidth: 170, style: { fontSize: '11px', fontWeight: 600 } }
        },
        legend: { position: 'top', horizontalAlign: 'center' },
        dataLabels: {
          enabled: true,
          textAnchor: 'start',
          formatter: (v, opt) => {
            const isWith = opt.seriesIndex === 0;
            const d = factData[opt.dataPointIndex];
            const cnt = isWith ? d.abnWith : d.abnWithout;
            const tot = isWith ? d.nWith : d.nWithout;
            if (tot < 5) return `${cnt} de ${tot} (${v.toFixed(1)}%)*`;
            return `${cnt} de ${tot} (${v.toFixed(1)}%)`;
          },
          style: { fontSize: '10px', fontWeight: 700, colors: ['#0f172a'] },
          offsetX: 6
        },
        tooltip: {
          y: {
            formatter: (v, opt) => {
              const isWith = opt.seriesIndex === 0;
              const d = factData[opt.dataPointIndex];
              const cnt = isWith ? d.abnWith : d.abnWithout;
              const tot = isWith ? d.nWith : d.nWithout;
              const ci = wilsonScoreInterval(cnt, tot);
              return `${cnt} de ${tot} (${formatPct(cnt, tot)}%; IC 95%: ${ci.lower.toFixed(1)}-${ci.upper.toFixed(1)}%)`;
            }
          }
        }
      };

      if (charts.ecgAbnFact) {
        charts.ecgAbnFact.updateOptions(abnFactOptions);
      } else {
        charts.ecgAbnFact = createDashboardApexChart(elAbnFact, abnFactOptions);
        charts.ecgAbnFact.render();
      }
    }
  }
}

// =============================================================
// MÓDULO DE EXPORTACIÓN (PDF, POWERPOINT, IMAGEN)
// =============================================================

