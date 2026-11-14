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
    if (charts.famPadres) {
      charts.famPadres.updateOptions({
        series: [
          { name: 'Rama Paterna', data: [padreHta, padreDm, padreDlp, padreIam] },
          { name: 'Rama Materna', data: [madreHta, madreDm, madreDlp, madreIam] }
        ],
        dataLabels: apexCountAndPctDataLabel()
      });
    } else {
      charts.famPadres = createDashboardApexChart(elPadres, {
        chart: { type: 'bar', height: 320, toolbar: { show: false }, animations: { enabled: false } },
        fill: { type: 'solid', opacity: 1 },
        colors: [PALETTE.primaryBlue, PALETTE.purple],
        plotOptions: { bar: { horizontal: true, barHeight: '78%', borderRadius: 6, dataLabels: { position: 'center' }, colors: { backgroundBarColors: ['#f1f5f9'], backgroundBarRadius: 6 } } },
        series: [
          { name: 'Rama Paterna', data: [padreHta, padreDm, padreDlp, padreIam] },
          { name: 'Rama Materna', data: [madreHta, madreDm, madreDlp, madreIam] }
        ],
        xaxis: { categories: ['Hipertensión', 'Diabetes', 'Dislipemia', 'Infarto / Ictus'] },
        legend: { position: 'top' },
        dataLabels: apexCountAndPctDataLabel(),
        tooltip: apexCountTooltip()
      });
      charts.famPadres.render();
    }
  }

  // Agregación de Carga Familiar
  let c0 = 0, c1 = 0, c2 = 0, c3 = 0;
  filteredRecords.forEach(r => {
    let fCount = (r.ant_fam_hta ? 1 : 0) + (r.ant_fam_dm ? 1 : 0) + (r.ant_fam_dlp ? 1 : 0) + (r.ant_fam_cv_mayor ? 1 : 0);
    if (fCount === 0) c0++;
    else if (fCount === 1) c1++;
    else if (fCount === 2) c2++;
    else c3++;
  });

  const cargaLabels = [
    `Sin Antecedentes: ${c0} (${formatPct(c0, n)}%)`,
    `1 Antecedente: ${c1} (${formatPct(c1, n)}%)`,
    `2 Antecedentes: ${c2} (${formatPct(c2, n)}%)`,
    `≥3 Antecedentes: ${c3} (${formatPct(c3, n)}%)`
  ];

  const ctxCarga = document.getElementById('chart-fam-carga-global');
  if (ctxCarga) {
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
  const ninguno = filteredRecords.filter(r => !r.ant_fam_hta && !r.ant_fam_dm).length;

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
}

// -------------------------------------------------------------
// TAB 6: HISTORIA NO CARDIOVASCULAR CHARTS
// -------------------------------------------------------------

