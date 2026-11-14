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
      charts.modControl.updateOptions({
        series: [
          { name: 'Bajo Tratamiento Farmacológico', data: [htaTto, dmTto, dlTto] },
          { name: 'Sin Tratamiento / Sin Control', data: [htaNoTto, dmNoTto, dlNoTto] }
        ]
      });
    } else {
      charts.modControl = new ApexCharts(elControl, {
        chart: { type: 'bar', height: 320, toolbar: { show: false }, animations: { enabled: false } },
        fill: { type: 'solid', opacity: 1 },
        colors: [PALETTE.green, PALETTE.emergencyRed],
        plotOptions: { bar: { horizontal: false, columnWidth: '55%', borderRadius: 4 } },
        series: [
          { name: 'Bajo Tratamiento Farmacológico', data: [htaTto, dmTto, dlTto] },
          { name: 'Sin Tratamiento / Sin Control', data: [htaNoTto, dmNoTto, dlNoTto] }
        ],
        xaxis: { categories: ['Hipertensión (HTA)', 'Diabetes Mellitus', 'Dislipemia'] },
        legend: { position: 'top' },
        dataLabels: apexCountAndPctDataLabel(),
        tooltip: apexCountTooltip()
      });
      charts.modControl.render();
    }
  }

  // Hábitos Tóxicos (Tabaquismo y Alcohol)
  const tabNo = filteredRecords.filter(r => r.tabaquismo === 'No fuma').length;
  const tabEx = filteredRecords.filter(r => r.tabaquismo === 'Exfumador').length;
  const tabAct = filteredRecords.filter(r => r.tabaquismo === 'Fumador Activo').length;

  const alcNo = filteredRecords.filter(r => r.alcohol === 'No consume').length;
  const alcOcas = filteredRecords.filter(r => r.alcohol === 'Ocasional').length;
  const alcReg = filteredRecords.filter(r => r.alcohol === 'Semanal' || r.alcohol === 'Diario').length;

  const toxCats = ['Sin Consumo / No Fuma', 'Consumo Ocasional / Ex', 'Consumo Activo / Regular'];

  const ctxTox = document.getElementById('chart-mod-toxicos');
  if (ctxTox) {
    if (charts.modTox) {
      charts.modTox.data.labels = toxCats;
      charts.modTox.data.datasets[0].data = [tabNo, tabEx, tabAct];
      charts.modTox.data.datasets[1].data = [alcNo, alcOcas, alcReg];
      charts.modTox.update();
    } else {
      charts.modTox = new Chart(ctxTox, {
        type: 'bar',
        data: {
          labels: toxCats,
          datasets: [
            { label: 'Tabaquismo', data: [tabNo, tabEx, tabAct], backgroundColor: PALETTE.emergencyRed, borderRadius: 5 },
            { label: 'Consumo de Alcohol', data: [alcNo, alcOcas, alcReg], backgroundColor: PALETTE.primaryBlue, borderRadius: 5 }
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
            datalabels: chartJsBarDataLabels()
          }
        }
      });
    }
  }

  // Actividad Física por Categoría
  const catNames = [...new Set(filteredRecords.map(r => r.categoria))].filter(Boolean);
  const actSi = catNames.map(c => filteredRecords.filter(r => r.categoria === c && r.actividad_fisica).length);
  const actNo = catNames.map(c => filteredRecords.filter(r => r.categoria === c && !r.actividad_fisica).length);

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
      charts.modActCat = new ApexCharts(elActCat, {
        chart: { type: 'bar', height: 320, toolbar: { show: false }, stacked: true, animations: { enabled: false } },
        fill: { type: 'solid', opacity: 1 },
        colors: [PALETTE.green, PALETTE.emergencyRed],
        plotOptions: { bar: { horizontal: false, borderRadius: 4 } },
        series: [
          { name: 'Activos Físicamente', data: actSi },
          { name: 'Sedentarios', data: actNo }
        ],
        xaxis: { categories: catNames },
        yaxis: { title: { text: 'Casos (n)' } },
        legend: { position: 'top' },
        dataLabels: apexCountAndPctDataLabel(),
        tooltip: apexCountTooltip()
      });
      charts.modActCat.render();
    }
  }

  // Dieta Mediterránea PREDIMED (Donut con leyenda detallada)
  const predimedAlta = filteredRecords.filter(r => r.predimed_adherencia === 'Buena Adherencia').length;
  const predimedBaja = filteredRecords.filter(r => r.predimed_adherencia !== 'Buena Adherencia').length;
  const predLegend = [
    `Buena Adherencia Mediterránea: ${predimedAlta} (${formatPct(predimedAlta, n)}%)`,
    `Adherencia Moderada / Baja: ${predimedBaja} (${formatPct(predimedBaja, n)}%)`
  ];

  const ctxPred = document.getElementById('chart-mod-predimed');
  if (ctxPred) {
    if (charts.modPred) {
      charts.modPred.data.labels = predLegend;
      charts.modPred.data.datasets[0].data = [predimedAlta, predimedBaja];
      charts.modPred.update();
    } else {
      charts.modPred = new Chart(ctxPred, {
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
    ['Disfunción eréctil (hombres)', 'disfuncion_erectil', filteredRecords.filter(r => r.sexo === 'Hombre')],
  ];
  const mandatoryCounts = mandatory.map(([, field, records]) => records.filter(r => r[field]).length);
  const mandatoryLabels = mandatory.map(([label, field, records], index) => {
    const valid = records.filter(r => r[field] !== null && r[field] !== undefined).length;
    return `${label}: ${mandatoryCounts[index]} (${formatPct(mandatoryCounts[index], valid)}%) · ${valid} válidos de ${records.length}; ${records.length - valid} sin dato`;
  });
  const elMandatory = document.getElementById('chart-mod-obligatorios');
  if (elMandatory) {
    const options = { chart: { type: 'bar', height: 320, toolbar: { show: false } }, series: [{ name: 'Casos', data: mandatoryCounts }], xaxis: { categories: mandatoryLabels }, legend: { show: false }, dataLabels: apexCountAndPctDataLabel() };
    if (charts.modMandatory) charts.modMandatory.updateOptions(options);
    else { charts.modMandatory = new ApexCharts(elMandatory, options); charts.modMandatory.render(); }
  }

  const vascular = [['Periférica', 'vasculopatia_periferica'], ['Carotídea', 'vasculopatia_carotidea'], ['Femoral', 'vasculopatia_femoral'], ['Cualquier vasculopatía', 'vasculopatia_cualquiera']];
  const vascularCounts = vascular.map(([, field]) => filteredRecords.filter(r => r[field]).length);
  const vascularLabels = vascular.map(([label, field], index) => {
    const valid = recordsWithValue(field).length;
    return `${label}: ${vascularCounts[index]} (${formatPct(vascularCounts[index], valid)}%) · ${valid} válidos de ${filteredRecords.length}; ${filteredRecords.length - valid} sin dato`;
  });
  const elVascular = document.getElementById('chart-mod-vasculopatia');
  if (elVascular) {
    const options = { chart: { type: 'bar', height: 320, toolbar: { show: false } }, series: [{ name: 'Casos', data: vascularCounts }], xaxis: { categories: vascularLabels }, legend: { show: false }, dataLabels: apexCountAndPctDataLabel() };
    if (charts.modVascular) charts.modVascular.updateOptions(options);
    else { charts.modVascular = new ApexCharts(elVascular, options); charts.modVascular.render(); }
  }
}

// -------------------------------------------------------------
// TAB 4: FACTORES EMERGENTES CHARTS
// -------------------------------------------------------------

