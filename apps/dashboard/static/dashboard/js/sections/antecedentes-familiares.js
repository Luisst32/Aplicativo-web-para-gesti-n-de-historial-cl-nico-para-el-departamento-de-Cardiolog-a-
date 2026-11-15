function renderTabAntecedentesFamiliares() {
  const n = filteredRecords.length;
  const padreHta = filteredRecords.filter(r => r.ant_padre_hta).length;
  const madreHta = filteredRecords.filter(r => r.ant_madre_hta).length;
  const padreDm = filteredRecords.filter(r => r.ant_padre_dm).length;
  const madreDm = filteredRecords.filter(r => r.ant_madre_dm).length;
  const padreDlp = filteredRecords.filter(r => r.ant_padre_dlp).length;
  const madreDlp = filteredRecords.filter(r => r.ant_madre_dlp).length;
  const padreIam = filteredRecords.filter(r => r.ant_padre_iam).length;
  const madreIam = filteredRecords.filter(r => r.ant_madre_iam).length;

  const elPadres = document.getElementById('chart-fam-padres-madres');
  if (elPadres) {
    const famPadresOptions = {
      chart: { type: 'bar', height: 320, toolbar: { show: false }, animations: { enabled: false } },
      fill: { type: 'solid', opacity: 1 },
      colors: [PALETTE.primaryBlue, PALETTE.purple],
      plotOptions: {
        bar: {
          horizontal: true,
          barHeight: '78%',
          borderRadius: 6,
          dataLabels: { position: 'center' },
          colors: { backgroundBarColors: ['#f1f5f9'], backgroundBarRadius: 6 }
        }
      },
      series: [
        { name: 'Rama Paterna', data: [padreHta, padreDm, padreDlp, padreIam] },
        { name: 'Rama Materna', data: [madreHta, madreDm, madreDlp, madreIam] }
      ],
      xaxis: { categories: ['Hipertensión', 'Diabetes', 'Dislipemia', 'Infarto / Ictus'] },
      legend: { position: 'top' },
      dataLabels: apexCountAndPctDataLabel(),
      tooltip: apexCountTooltip()
    };
    if (charts.famPadres) {
      charts.famPadres.updateOptions(famPadresOptions);
    } else {
      charts.famPadres = createDashboardApexChart(elPadres, famPadresOptions);
      charts.famPadres.render();
    }
  }

  // Agregación de Carga Familiar
  let c0 = 0, c1 = 0, c2 = 0, c3 = 0;
  const familyFields = ['ant_fam_hta','ant_fam_dm','ant_fam_dlp','ant_fam_cv_mayor'];
  const familyRows = filteredRecords.filter(r => familyFields.some(field => typeof r[field] === 'boolean'));
  familyRows.forEach(r => {
    let fCount = (r.ant_fam_hta ? 1 : 0) + (r.ant_fam_dm ? 1 : 0) + (r.ant_fam_dlp ? 1 : 0) + (r.ant_fam_cv_mayor ? 1 : 0);
    if (fCount === 0) c0++;
    else if (fCount === 1) c1++;
    else if (fCount === 2) c2++;
    else c3++;
  });

  const cargaLabels = [
    `Sin Antecedentes: ${c0} (${formatPct(c0, familyRows.length)}%)`,
    `1 Antecedente: ${c1} (${formatPct(c1, familyRows.length)}%)`,
    `2 Antecedentes: ${c2} (${formatPct(c2, familyRows.length)}%)`,
    `≥3 Antecedentes: ${c3} (${formatPct(c3, familyRows.length)}%)`
  ];

  const ctxCarga = document.getElementById('chart-fam-carga-global');
  if (dashboardHasChartData('chart-fam-carga-global', 'famCarga', familyRows.length)) {
    if (charts.famCarga) {
      charts.famCarga.data.labels = cargaLabels;
      charts.famCarga.data.datasets[0].data = [c0, c1, c2, c3];
      charts.famCarga.update();
    } else {
      charts.famCarga = createDashboardChart(ctxCarga, {
        type: 'doughnut',
        data: {
          labels: cargaLabels,
          datasets: [{ data: [c0, c1, c2, c3], backgroundColor: [PALETTE.green, PALETTE.teal, PALETTE.yellow, PALETTE.emergencyRed] }]
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

  // Antecedentes por Grupo Etario
  const grupos = ['<40 años', '40-49 años', '50-59 años', '60+ años'];
  const htaPorEdad = grupos.map(g => filteredRecords.filter(r => r.grupo_edad === g && r.ant_fam_hta).length);
  const dmPorEdad = grupos.map(g => filteredRecords.filter(r => r.grupo_edad === g && r.ant_fam_dm).length);

  const elEdad = document.getElementById('chart-fam-por-edad');
  if (elEdad) {
    if (charts.famEdad) {
      charts.famEdad.updateOptions({
        series: [
          { name: 'HTA Familiar', data: htaPorEdad },
          { name: 'Diabetes Familiar', data: dmPorEdad }
        ]
      });
    } else {
      charts.famEdad = createDashboardApexChart(elEdad, {
        chart: { type: 'bar', height: 320, toolbar: { show: false }, animations: { enabled: false } },
        fill: { type: 'solid', opacity: 1 },
        colors: [PALETTE.emergencyRed, PALETTE.yellow],
        plotOptions: { bar: { horizontal: true, barHeight: '78%', borderRadius: 6, dataLabels: { position: 'center' }, colors: { backgroundBarColors: ['#f1f5f9'], backgroundBarRadius: 6 } } },
        series: [
          { name: 'HTA Familiar', data: htaPorEdad },
          { name: 'Diabetes Familiar', data: dmPorEdad }
        ],
        xaxis: { categories: grupos },
        yaxis: { title: { text: 'Casos (n)' } },
        legend: { position: 'top' },
        dataLabels: apexCountAndPctDataLabel(),
        tooltip: apexCountTooltip()
      });
      charts.famEdad.render();
    }
  }

  // Coexistencia HTA y Diabetes
  const soloHta = filteredRecords.filter(r => r.ant_fam_hta && !r.ant_fam_dm).length;
  const soloDm = filteredRecords.filter(r => !r.ant_fam_hta && r.ant_fam_dm).length;
  const ambos = filteredRecords.filter(r => r.ant_fam_hta && r.ant_fam_dm).length;
  const ninguno = filteredRecords.filter(r => (r.ant_fam_hta === false) && (r.ant_fam_dm === false)).length;

  const ctxCoex = document.getElementById('chart-fam-coexistencia');
  if (ctxCoex) {
    if (charts.famCoex) {
      charts.famCoex.data.datasets[0].data = [soloHta, soloDm, ambos, ninguno];
      charts.famCoex.update();
    } else {
      charts.famCoex = createDashboardChart(ctxCoex, {
        type: 'bar',
        data: {
          labels: ['Solo HTA Familiar', 'Solo Diabetes Familiar', 'Ambas Coexistentes', 'Sin Estos Antecedentes'],
          datasets: [{ label: 'Casos', data: [soloHta, soloDm, ambos, ninguno], backgroundColor: [PALETTE.emergencyRed, PALETTE.yellow, PALETTE.purple, PALETTE.green], borderRadius: 5 }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: { top: 25, right: 8, bottom: 4, left: 4 } },
          scales: {
            y: {
              beginAtZero: true,
              grace: '20%',
              title: { display: true, text: 'Casos (n)', font: { size: 10, weight: 'bold' } }
            }
          },
          plugins: {
            legend: { display: false },
            datalabels: chartJsBarDataLabels()
          }
        }
      });
    }
  }

  // 5. FASE 3: Antecedente Familiar vs Diagnóstico Propio
  const htaResp = filteredRecords.filter(r => (typeof r.hipertension === 'boolean' || r.hipertension === 'Si' || r.hipertension === 'No') && (typeof r.ant_fam_hta === 'boolean' || r.ant_padre_hta || r.ant_madre_hta));
  const htaConFam = htaResp.filter(r => r.ant_fam_hta === true || r.ant_padre_hta || r.ant_madre_hta);
  const htaConFamCasos = htaConFam.filter(r => r.hipertension === true || r.hipertension === 'Si').length;
  const htaConFamPct = htaConFam.length > 0 ? Number(((htaConFamCasos / htaConFam.length) * 100).toFixed(1)) : 0;

  const htaSinFam = htaResp.filter(r => r.ant_fam_hta === false && !r.ant_padre_hta && !r.ant_madre_hta);
  const htaSinFamCasos = htaSinFam.filter(r => r.hipertension === true || r.hipertension === 'Si').length;
  const htaSinFamPct = htaSinFam.length > 0 ? Number(((htaSinFamCasos / htaSinFam.length) * 100).toFixed(1)) : 0;

  const dlpResp = filteredRecords.filter(r => (typeof r.dislipemia === 'boolean' || r.dislipemia === 'Si' || r.dislipemia === 'No') && (typeof r.ant_fam_dlp === 'boolean' || r.ant_padre_dlp || r.ant_madre_dlp));
  const dlpConFam = dlpResp.filter(r => r.ant_fam_dlp === true || r.ant_padre_dlp || r.ant_madre_dlp);
  const dlpConFamCasos = dlpConFam.filter(r => r.dislipemia === true || r.dislipemia === 'Si').length;
  const dlpConFamPct = dlpConFam.length > 0 ? Number(((dlpConFamCasos / dlpConFam.length) * 100).toFixed(1)) : 0;

  const dlpSinFam = dlpResp.filter(r => r.ant_fam_dlp === false && !r.ant_padre_dlp && !r.ant_madre_dlp);
  const dlpSinFamCasos = dlpSinFam.filter(r => r.dislipemia === true || r.dislipemia === 'Si').length;
  const dlpSinFamPct = dlpSinFam.length > 0 ? Number(((dlpSinFamCasos / dlpSinFam.length) * 100).toFixed(1)) : 0;

  const elFamPropio = document.getElementById('chart-af-familiar-vs-propio');
  if (elFamPropio && dashboardHasChartData('chart-af-familiar-vs-propio', 'afFamPropio', htaResp.length + dlpResp.length)) {
    const famPropioOptions = {
      chart: { type: 'bar', height: 320, toolbar: { show: false }, animations: { enabled: false } },
      plotOptions: { bar: { horizontal: false, columnWidth: '50%', borderRadius: 5, dataLabels: { position: 'center' } } },
      colors: [PALETTE.emergencyRed, PALETTE.primaryBlue],
      series: [
        { name: 'Con Antecedente Familiar', data: [htaConFamPct, dlpConFamPct] },
        { name: 'Sin Antecedente Familiar', data: [htaSinFamPct, dlpSinFamPct] }
      ],
      xaxis: { categories: ['Hipertensión Arterial (HTA)', 'Dislipemia'] },
      yaxis: { min: 0, max: 100, labels: { formatter: val => `${Math.round(val)}%` }, title: { text: '% Prevalencia Diagnóstico Propio' } },
      legend: { position: 'top', horizontalAlign: 'center' },
      dataLabels: {
        enabled: true,
        formatter: (val, opt) => {
          const sIdx = opt.seriesIndex;
          const dIdx = opt.dataPointIndex;
          if (dIdx === 0) {
            return sIdx === 0 ? `${htaConFamCasos}/${htaConFam.length} (${val}%)` : `${htaSinFamCasos}/${htaSinFam.length} (${val}%)`;
          } else {
            return sIdx === 0 ? `${dlpConFamCasos}/${dlpConFam.length} (${val}%)` : `${dlpSinFamCasos}/${dlpSinFam.length} (${val}%)`;
          }
        },
        style: { fontSize: '11px', fontWeight: 'bold', fontFamily: 'inherit', colors: ['#ffffff'] },
        dropShadow: UNIVERSAL_VALUE_LABEL_STYLE.apexDropShadow,
        background: { enabled: false }
      },
      tooltip: {
        y: {
          formatter: (val, opt) => {
            const sIdx = opt.seriesIndex;
            const dIdx = opt.dataPointIndex;
            if (dIdx === 0) {
              return sIdx === 0 ? formatWilsonCiLabel(htaConFamCasos, htaConFam.length) : formatWilsonCiLabel(htaSinFamCasos, htaSinFam.length);
            } else {
              return sIdx === 0 ? formatWilsonCiLabel(dlpConFamCasos, dlpConFam.length) : formatWilsonCiLabel(dlpSinFamCasos, dlpSinFam.length);
            }
          }
        }
      }
    };
    if (charts.afFamPropio) charts.afFamPropio.updateOptions(famPropioOptions);
    else { charts.afFamPropio = createDashboardApexChart(elFamPropio, famPropioOptions); charts.afFamPropio.render(); }
  }
}

// -------------------------------------------------------------
// TAB 6: HISTORIA NO CARDIOVASCULAR CHARTS
// -------------------------------------------------------------

