const DASHBOARD_TABS = [
  { id: 'resumen-general', title: 'Resumen General Epidemiológico' },
  { id: 'datos-individuo', title: 'Datos del Individuo y Filiación' },
  { id: 'exploracion-fisica', title: 'Exploración Física y Antropometría' },
  { id: 'factores-modificables', title: 'Factores de Riesgo Modificables' },
  { id: 'factores-emergentes', title: 'Factores de Riesgo Emergentes' },
  { id: 'antecedentes-familiares', title: 'Antecedentes Familiares Cardiovasculares' },
  { id: 'historia-no-cardio', title: 'Historia Clínica No Cardiovascular' },
  { id: 'covid-19', title: 'COVID-19 y Secuelas Post-Infección' },
  { id: 'electrocardiograma', title: 'Resultados del Electrocardiograma (ECG)' }
];

function openExportModal() {
  const modal = document.getElementById('modal-export-dashboard');
  if (modal) {
    modal.style.display = 'flex';
    const curTab = DASHBOARD_TABS.find(t => t.id === activeTabId) || DASHBOARD_TABS[0];
    const lbl = document.getElementById('export-current-tab-name');
    if (lbl) lbl.textContent = curTab.title;
    const prog = document.getElementById('export-progress-container');
    if (prog) prog.style.display = 'none';
    const btn = document.getElementById('btn-do-export');
    if (btn) btn.disabled = false;
  } else {
    console.warn('Modal de exportación #modal-export-dashboard no encontrado en el DOM.');
  }
}

// Exposición explícita global para llamadas inline y listeners
window.openExportModal = openExportModal;
window.closeExportModal = closeExportModal;
window.startExport = startExport;

// Enlace defensivo directo al botón de exportar
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.btn-export-dashboard').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      openExportModal();
    });
  });
});

function closeExportModal() {
  const modal = document.getElementById('modal-export-dashboard');
  if (modal) modal.style.display = 'none';
}

// Controlador de inicio de exportación
async function startExport() {
  const formatEl = document.querySelector('input[name="export-format"]:checked');
  const scopeEl = document.querySelector('input[name="export-scope"]:checked');
  const format = formatEl ? formatEl.value : 'pdf';
  const scope = scopeEl ? scopeEl.value : 'current';

  const btn = document.getElementById('btn-do-export');
  const progBox = document.getElementById('export-progress-container');
  const progText = document.getElementById('export-progress-text');
  const progBar = document.getElementById('export-progress-bar');

  if (btn) btn.disabled = true;
  if (progBox) progBox.style.display = 'flex';

  const setProgress = (text, pct) => {
    if (progText) progText.textContent = text;
    if (progBar) progBar.style.width = `${pct}%`;
  };

  try {
    if (format === 'image') {
      await exportImage(scope, setProgress);
    } else if (format === 'pptx') {
      await exportPowerPoint(scope, setProgress);
    } else {
      await exportPdf(scope, setProgress);
    }
    setTimeout(() => {
      closeExportModal();
    }, 700);
  } catch (err) {
    console.error('Error durante la exportación:', err);
    alert('Ocurrió un inconveniente al generar la exportación: ' + (err.message || err));
  } finally {
    if (btn) btn.disabled = false;
    if (progBox) progBox.style.display = 'none';
  }
}

// 1. Exportación a Imagen PNG
// Helper para normalizar gradientes y asegurar visibilidad de rellenos SVG en html2canvas
function fixSvgFillsForHtml2Canvas(clonedDoc) {
  if (!clonedDoc) return;
  try {
    const svgElements = clonedDoc.querySelectorAll('svg [fill*="url("]');
    svgElements.forEach(el => {
      const fillAttr = el.getAttribute('fill') || '';
      const match = fillAttr.match(/url\(#?([^)]+)\)/);
      if (match) {
        const gradId = match[1].replace(/["']/g, '');
        const grad = clonedDoc.getElementById(gradId) || document.getElementById(gradId);
        if (grad) {
          const stop = grad.querySelector('stop');
          if (stop) {
            const color = stop.getAttribute('stop-color') || stop.style.stopColor;
            if (color) {
              el.setAttribute('fill', color);
              el.style.fill = color;
              el.setAttribute('fill-opacity', '1');
              el.style.fillOpacity = '1';
            }
          }
        }
      }
    });

    clonedDoc.querySelectorAll('.apexcharts-bar-area, .apexcharts-series path, .apexcharts-area').forEach(el => {
      const fill = el.getAttribute('fill') || '';
      if (fill.startsWith('url(')) {
        const match = fill.match(/url\(#?([^)]+)\)/);
        if (match) {
          const gradId = match[1].replace(/["']/g, '');
          const grad = clonedDoc.getElementById(gradId) || document.getElementById(gradId);
          if (grad) {
            const stop = grad.querySelector('stop');
            if (stop) {
              const color = stop.getAttribute('stop-color') || stop.style.stopColor;
              if (color) {
                el.setAttribute('fill', color);
                el.style.fill = color;
                el.setAttribute('fill-opacity', '1');
                el.style.fillOpacity = '1';
              }
            }
          }
        }
      }
    });
  } catch (err) {
    console.warn('Advertencia en fixSvgFillsForHtml2Canvas:', err);
  }
}

async function exportImage(scope, setProgress) {
  const h2c = window.html2canvas || (typeof html2canvas !== 'undefined' ? html2canvas : null);
  if (!h2c) {
    throw new Error('La librería html2canvas no está disponible.');
  }

  const tabsToExport = scope === 'all' ? DASHBOARD_TABS : [DASHBOARD_TABS.find(t => t.id === activeTabId) || DASHBOARD_TABS[0]];
  const total = tabsToExport.length;
  const originalTab = activeTabId;

  for (let i = 0; i < total; i++) {
    const tab = tabsToExport[i];
    setProgress(`Capturando imagen: ${tab.title} (${i + 1}/${total})...`, Math.round(((i + 0.5) / total) * 100));

    switchTab(tab.id, document.querySelector(`.nav-item[onclick*="${tab.id}"]`));
    await new Promise(r => setTimeout(r, 450));

    const targetEl = document.getElementById('tab-' + tab.id);
    if (!targetEl) continue;
    const canvas = await h2c(targetEl, {
      scale: 2,
      useCORS: true,
      backgroundColor: '#F8FAFC',
      logging: false,
      onclone: (clonedDoc) => fixSvgFillsForHtml2Canvas(clonedDoc)
    });

    const link = document.createElement('a');
    const safeTitle = tab.title.toLowerCase().replace(/[^a-z0-9]/g, '_');
    link.download = `CardioUNEMI_${safeTitle}_${new Date().toISOString().slice(0, 10)}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
    await new Promise(r => setTimeout(r, 200));
  }

  switchTab(originalTab, document.querySelector(`.nav-item[onclick*="${originalTab}"]`));
  setProgress('¡Imágenes descargadas con éxito!', 100);
}

// 2. Exportación a Documento PDF Paginado
async function exportPdf(scope, setProgress) {
  const { jsPDF } = window.jspdf || window;
  if (!jsPDF) {
    throw new Error('La librería jsPDF no está disponible.');
  }
  const h2c = window.html2canvas || (typeof html2canvas !== 'undefined' ? html2canvas : null);
  if (!h2c) {
    throw new Error('La librería html2canvas no está disponible.');
  }

  const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
  const tabsToExport = scope === 'all' ? DASHBOARD_TABS : [DASHBOARD_TABS.find(t => t.id === activeTabId) || DASHBOARD_TABS[0]];
  const total = tabsToExport.length;
  const originalTab = activeTabId;

  const pageWidth = 297;
  const pageHeight = 210;
  const marginX = 10;
  const contentWidth = pageWidth - (marginX * 2);

  const instVal = document.getElementById('slicer-inst')?.value || 'Todas las Instituciones';
  const anoVal = document.getElementById('slicer-ano')?.value || 'Todos los Años';
  const sampleText = `${filteredRecords.length} de ${allRecords.length} evaluados`;
  const todayStr = new Date().toLocaleDateString('es-EC', { year: 'numeric', month: 'long', day: 'numeric' });

  for (let i = 0; i < total; i++) {
    const tab = tabsToExport[i];
    setProgress(`Generando página PDF: ${tab.title} (${i + 1}/${total})...`, Math.round(((i + 0.3) / total) * 100));

    switchTab(tab.id, document.querySelector(`.nav-item[onclick*="${tab.id}"]`));
    await new Promise(r => setTimeout(r, 450));

    const targetEl = document.getElementById('tab-' + tab.id);
    if (!targetEl) continue;

    const canvas = await h2c(targetEl, {
      scale: 2,
      useCORS: true,
      backgroundColor: '#FFFFFF',
      logging: false,
      onclone: (clonedDoc) => fixSvgFillsForHtml2Canvas(clonedDoc)
    });

    const imgData = canvas.toDataURL('image/png');

    if (i > 0) {
      doc.addPage();
    }

    // Cabecera Institucional
    doc.setFillColor(27, 42, 65); // #1B2A41 Navy
    doc.rect(0, 0, pageWidth, 15, 'F');

    doc.setTextColor(255, 255, 255);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(10.5);
    doc.text('CARDIOUNEMI • VIGILANCIA EPIDEMIOLÓGICA CARDIOVASCULAR', marginX, 9.5);

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8);
    doc.text(`Cohorte: ${sampleText} | ${instVal} - Año ${anoVal} | ${todayStr}`, pageWidth - marginX, 9.5, { align: 'right' });

    // Título de la Sección
    doc.setTextColor(27, 42, 65);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(12);
    doc.text(tab.title, marginX, 23);

    // Renderizado del contenido visual
    const imgAspect = canvas.height / canvas.width;
    const maxImgHeight = pageHeight - 34;
    let renderW = contentWidth;
    let renderH = renderW * imgAspect;
    if (renderH > maxImgHeight) {
      renderH = maxImgHeight;
      renderW = renderH / imgAspect;
    }
    const renderX = marginX + (contentWidth - renderW) / 2;

    doc.addImage(imgData, 'PNG', renderX, 26, renderW, renderH, undefined, 'SLOW');

    // Pie de página
    doc.setTextColor(148, 163, 184);
    doc.setFontSize(7.5);
    doc.text('Universidad Estatal de Milagro (UNEMI) • Departamento de Cardiología', marginX, pageHeight - 4);
    doc.text(`Página ${i + 1} de ${total}`, pageWidth - marginX, pageHeight - 4, { align: 'right' });
  }

  switchTab(originalTab, document.querySelector(`.nav-item[onclick*="${originalTab}"]`));

  setProgress('Guardando documento PDF...', 95);
  const fileName = scope === 'all'
    ? `CardioUNEMI_Reporte_Integral_8_Bloques_${new Date().toISOString().slice(0, 10)}.pdf`
    : `CardioUNEMI_${activeTabId}_${new Date().toISOString().slice(0, 10)}.pdf`;

  doc.save(fileName);
  setProgress('¡PDF generado exitosamente!', 100);
}

// 3. Exportación a Diapositivas PowerPoint (.pptx)
async function exportPowerPoint(scope, setProgress) {
  const pptxClass = window.PptxGenJS || (typeof PptxGenJS !== 'undefined' ? PptxGenJS : null);
  if (!pptxClass) {
    throw new Error('La librería PptxGenJS no está disponible.');
  }
  const h2c = window.html2canvas || (typeof html2canvas !== 'undefined' ? html2canvas : null);
  if (!h2c) {
    throw new Error('La librería html2canvas no está disponible.');
  }

  const pptx = new pptxClass();
  pptx.layout = 'LAYOUT_16x9';

  const tabsToExport = scope === 'all' ? DASHBOARD_TABS : [DASHBOARD_TABS.find(t => t.id === activeTabId) || DASHBOARD_TABS[0]];
  const total = tabsToExport.length;
  const originalTab = activeTabId;

  const instVal = document.getElementById('slicer-inst')?.value || 'Todas las Instituciones';
  const anoVal = document.getElementById('slicer-ano')?.value || 'Todos los Años';
  const sampleText = `${filteredRecords.length} de ${allRecords.length} evaluados (100%)`;
  const todayStr = new Date().toLocaleDateString('es-EC', { year: 'numeric', month: 'long', day: 'numeric' });

  // Slide 1: Portada Ejecutiva
  setProgress('Construyendo portada institucional...', 10);
  const slidePortada = pptx.addSlide();
  slidePortada.background = { color: '1B2A41' }; // Navy UNEMI

  slidePortada.addText('UNIVERSIDAD ESTATAL DE MILAGRO', {
    x: 0.8, y: 1.0, w: 8.4, h: 0.4,
    fontSize: 13, color: '3AA0FF', bold: true
  });

  slidePortada.addText('CARDIOUNEMI • INFORME EPIDEMIOLÓGICO', {
    x: 0.8, y: 1.45, w: 8.4, h: 1.0,
    fontSize: 27, color: 'FFFFFF', bold: true
  });

  slidePortada.addText('Vigilancia de Salud Cardiovascular y Factores de Riesgo Clínico', {
    x: 0.8, y: 2.5, w: 8.4, h: 0.5,
    fontSize: 14, color: 'CFE9FF'
  });

  slidePortada.addShape(pptx.ShapeType.rect, {
    x: 0.8, y: 3.3, w: 8.4, h: 1.6,
    fill: { color: '142132' },
    line: { color: '3AA0FF', width: 1.5 }
  });

  slidePortada.addText([
    { text: 'Muestra Total Analizada: ', options: { bold: true, color: '3AA0FF' } },
    { text: `${sampleText}\n`, options: { color: 'FFFFFF' } },
    { text: 'Institución / Cohorte: ', options: { bold: true, color: '3AA0FF' } },
    { text: `${instVal} (Año: ${anoVal})\n`, options: { color: 'FFFFFF' } },
    { text: 'Fecha de Emisión: ', options: { bold: true, color: '3AA0FF' } },
    { text: `${todayStr}\n`, options: { color: 'FFFFFF' } },
    { text: 'Alcance del Reporte: ', options: { bold: true, color: '3AA0FF' } },
    { text: scope === 'all' ? 'Informe Integral Completo (8 Bloques Clínicos)' : `Módulo Específico: ${tabsToExport[0].title}`, options: { color: 'FFFFFF' } }
  ], {
    x: 1.05, y: 3.45, w: 7.9, h: 1.3,
    fontSize: 11
  });

  // Slide 2..N: Slides por cada Módulo Clínico
  for (let i = 0; i < total; i++) {
    const tab = tabsToExport[i];
    setProgress(`Generando diapositiva: ${tab.title} (${i + 1}/${total})...`, Math.round(15 + ((i + 1) / total) * 75));

    switchTab(tab.id, document.querySelector(`.nav-item[onclick*="${tab.id}"]`));
    await new Promise(r => setTimeout(r, 450));

    const targetEl = document.getElementById('tab-' + tab.id);
    if (!targetEl) continue;

    const canvas = await h2c(targetEl, {
      scale: 2,
      useCORS: true,
      backgroundColor: '#FFFFFF',
      logging: false,
      onclone: (clonedDoc) => fixSvgFillsForHtml2Canvas(clonedDoc)
    });

    const imgData = canvas.toDataURL('image/png');

    const slide = pptx.addSlide();
    slide.background = { color: 'F8FAFC' };

    // Barra Superior
    slide.addShape(pptx.ShapeType.rect, {
      x: 0, y: 0, w: 10, h: 0.65,
      fill: { color: '1B2A41' }
    });

    slide.addText(`CARDIOUNEMI • ${tab.title.toUpperCase()}`, {
      x: 0.5, y: 0.12, w: 7.0, h: 0.4,
      fontSize: 12.5, color: 'FFFFFF', bold: true
    });

    slide.addText(`${todayStr} | N = ${filteredRecords.length}`, {
      x: 7.5, y: 0.14, w: 2.0, h: 0.35,
      fontSize: 9, color: 'CFE9FF', align: 'right'
    });

    // Imagen del Panel de Gráficos
    const imgAspect = canvas.height / canvas.width;
    const maxW = 9.2;
    const maxH = 4.65;
    let w = maxW;
    let h = w * imgAspect;
    if (h > maxH) {
      h = maxH;
      w = h / imgAspect;
    }
    const x = 0.4 + (maxW - w) / 2;
    const y = 0.78 + (maxH - h) / 2;

    slide.addImage({ data: imgData, x: x, y: y, w: w, h: h });

    // Pie de diapositiva
    slide.addText('Universidad Estatal de Milagro • Departamento de Cardiología', {
      x: 0.5, y: 5.35, w: 6.0, h: 0.25,
      fontSize: 8, color: '94A3B8'
    });
    slide.addText(`Diapositiva ${i + 2} de ${total + 1}`, {
      x: 7.5, y: 5.35, w: 2.0, h: 0.25,
      fontSize: 8, color: '94A3B8', align: 'right'
    });
  }

  switchTab(originalTab, document.querySelector(`.nav-item[onclick*="${originalTab}"]`));

  setProgress('Compilando presentación PowerPoint (.pptx)...', 95);
  const fileName = scope === 'all'
    ? `CardioUNEMI_Presentacion_Completa_${new Date().toISOString().slice(0, 10)}.pptx`
    : `CardioUNEMI_${activeTabId}_${new Date().toISOString().slice(0, 10)}.pptx`;

  await pptx.writeFile({ fileName: fileName });
  setProgress('¡Presentación PPTX descargada exitosamente!', 100);
}

