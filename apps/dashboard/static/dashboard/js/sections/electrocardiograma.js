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
  const hviCnt = filteredRecords.filter(r => r.ecg_hvi).length;
  const brCnt = filteredRecords.filter(r => r.ecg_bloqueo_rama && r.ecg_bloqueo_rama !== 'Sin bloqueo' && r.ecg_bloqueo_rama.toUpperCase() !== 'NINGUNA').length;
  const repolCnt = filteredRecords.filter(r => r.ecg_repolarizacion).length;
  const sinAnom = filteredRecords.filter(r => !r.ecg_hvi && (!r.ecg_bloqueo_rama || r.ecg_bloqueo_rama === 'Sin bloqueo' || r.ecg_bloqueo_rama.toUpperCase() === 'NINGUNA') && !r.ecg_repolarizacion).length;

  const elAnom = document.getElementById('chart-ecg-anomalias');
  if (elAnom) {
    if (charts.ecgAnom) {
      charts.ecgAnom.updateOptions({
        series: [{ name: 'Casos', data: [sinAnom, brCnt, hviCnt, repolCnt] }]
      });
    } else {
      charts.ecgAnom = createDashboardApexChart(elAnom, {
        chart: { type: 'bar', height: 320, toolbar: { show: false }, animations: { enabled: false } },
        fill: { type: 'solid', opacity: 1 },
        colors: [PALETTE.green, PALETTE.yellow, PALETTE.emergencyRed, PALETTE.purple],
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
        series: [{ name: 'Casos', data: [sinAnom, brCnt, hviCnt, repolCnt] }],
        xaxis: { categories: ['ECG Morfológicamente Normal', 'Bloqueo de Rama', 'Hipertrofia Ventricular (HVI)', 'Alteraciones Repolarización'] },
        legend: { show: false },
        dataLabels: apexCountAndPctDataLabel(),
        tooltip: apexCountTooltip()
      });
      charts.ecgAnom.render();
    }
  }

  // Frecuencia Cardíaca ECG vs Frecuencia Clínica
  const fcEcgMedia = parseFloat(formatMean(filteredRecords.map(r => r.ecg_fc), 0)) || 0;
  const fcClinicaMedia = parseFloat(formatMean(filteredRecords.map(r => r.fc), 0)) || 0;

  const ctxFc = document.getElementById('chart-ecg-fc-comparativa');
  if (ctxFc) {
    if (charts.ecgFc) {
      charts.ecgFc.data.datasets[0].data = [fcEcgMedia, fcClinicaMedia];
      charts.ecgFc.update();
    } else {
      charts.ecgFc = createDashboardChart(ctxFc, {
        type: 'bar',
        data: {
          labels: [['FC por Trazado', 'ECG'], ['FC por Auscultación', 'o Pulso']],
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
              display: true,
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
              formatter: (val) => `${val} lpm`
            }
          }
        }
      });
    }
  }
}

// =============================================================
// MÓDULO DE EXPORTACIÓN (PDF, POWERPOINT, IMAGEN)
// =============================================================

