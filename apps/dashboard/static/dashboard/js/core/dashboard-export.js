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
  const modalBackdrop = document.getElementById('modal-export-dashboard');

  if (btn) btn.disabled = true;
  if (progBox) progBox.style.display = 'flex';
  if (modalBackdrop) {
    modalBackdrop.style.background = 'rgba(15, 23, 42, 0.94)';
  }
  document.body.style.overflow = 'hidden';

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
    }, 500);
  } catch (err) {
    console.error('Error durante la exportación:', err);
    alert('Ocurrió un inconveniente al generar la exportación: ' + (err.message || err));
  } finally {
    if (btn) btn.disabled = false;
    if (progBox) progBox.style.display = 'none';
    if (modalBackdrop) {
      modalBackdrop.style.background = 'rgba(15, 23, 42, 0.72)';
    }
    document.body.style.overflow = '';
  }
}

// Helper para normalizar gradientes, desactivar clipPath problemáticos y asegurar visibilidad de rellenos SVG en html2canvas
function fixSvgFillsForHtml2Canvas(clonedDoc, tabId) {
  if (!clonedDoc) return;
  try {
    const root = (tabId ? clonedDoc.getElementById('tab-' + tabId) : null) || clonedDoc;

    // 1. Desactivar clip-path SVG que html2canvas no soporta y oculta las barras de ApexCharts
    root.querySelectorAll('svg [clip-path], svg [clipPath]').forEach(el => {
      el.removeAttribute('clip-path');
      el.removeAttribute('clipPath');
      el.style.clipPath = 'none';
    });
    root.querySelectorAll('.apexcharts-canvas path, .apexcharts-canvas rect, .apexcharts-canvas g').forEach(el => {
      if (el.style.clipPath) el.style.clipPath = 'none';
    });

    // 2. Normalizar rellenos con gradientes url(#...)
    const svgElements = root.querySelectorAll('svg [fill*="url("]');
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

    root.querySelectorAll('.apexcharts-bar-area, .apexcharts-series path, .apexcharts-area').forEach(el => {
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

// Helper para calcular cortes limpios de filas de una sección sin dividir tarjetas a la mitad
function getTabRowSlices(targetEl, canvas, maxSlicePx) {
  if (!targetEl || !canvas) return [{ startY: 0, endY: canvas ? canvas.height : 0 }];

  const children = Array.from(targetEl.children).filter(c => c.offsetHeight > 0);
  if (!children.length) {
    return [{ startY: 0, endY: canvas.height }];
  }

  const scale = canvas.width / (targetEl.offsetWidth || 1);
  const rows = children.map(c => ({
    top: Math.round((c.offsetTop - targetEl.offsetTop) * scale),
    bottom: Math.round(((c.offsetTop - targetEl.offsetTop) + c.offsetHeight) * scale)
  }));

  const slices = [];
  let curStart = 0;
  let curEnd = 0;

  for (let i = 0; i < rows.length; i++) {
    const r = rows[i];
    if (r.bottom - curStart <= maxSlicePx) {
      curEnd = r.bottom;
    } else {
      if (curEnd > curStart) {
        slices.push({ startY: curStart, endY: curEnd });
        curStart = curEnd;
      }
      curEnd = r.bottom;
    }
  }
  if (curEnd > curStart) {
    slices.push({ startY: curStart, endY: curEnd });
  }

  return slices.length > 0 ? slices : [{ startY: 0, endY: canvas.height }];
}

// Helper para extraer un sub-canvas nítido
function createSliceCanvas(sourceCanvas, startY, sliceH) {
  const sCanvas = document.createElement('canvas');
  sCanvas.width = sourceCanvas.width;
  sCanvas.height = sliceH;
  const sCtx = sCanvas.getContext('2d');
  sCtx.fillStyle = '#FFFFFF';
  sCtx.fillRect(0, 0, sCanvas.width, sliceH);
  sCtx.drawImage(sourceCanvas, 0, startY, sourceCanvas.width, sliceH, 0, 0, sourceCanvas.width, sliceH);
  return sCanvas;
}

// Motor de captura ultra-optimizado por pestaña: aísla el DOM e ignora los otros 8 bloques
async function renderSectionCanvas(h2c, tab, scale = 1.15) {
  const targetEl = document.getElementById('tab-' + tab.id);
  if (!targetEl) return null;

  return await h2c(targetEl, {
    scale: scale,
    useCORS: false,
    backgroundColor: '#FFFFFF',
    logging: false,
    imageTimeout: 500,
    ignoreElements: (el) => {
      if (!el) return false;
      if (el.id === 'modal-export-dashboard') return true;
      if (el.id === 'slicers-bar' || el.id === 'main-nav' || el.id === 'app-header' || el.classList?.contains('sidebar')) return true;
      if (el.classList && el.classList.contains('tab-view') && el.id !== ('tab-' + tab.id)) return true;
      return false;
    },
    onclone: (clonedDoc) => fixSvgFillsForHtml2Canvas(clonedDoc, tab.id)
  });
}

// 1. Exportación a Imagen PNG
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
    setProgress(`Capturando imagen: ${tab.title} (${i + 1}/${total})...`, Math.round(((i + 0.3) / total) * 100));
    await new Promise(r => setTimeout(r, 5));

    if (activeTabId !== tab.id) {
      switchTab(tab.id, document.querySelector(`.nav-item[onclick*="${tab.id}"]`));
      await new Promise(r => setTimeout(r, 180));
    } else {
      await new Promise(r => setTimeout(r, 50));
    }
    await new Promise(r => requestAnimationFrame(r));

    const canvas = await renderSectionCanvas(h2c, tab, 1.2);
    if (!canvas) continue;

    const link = document.createElement('a');
    const safeTitle = tab.title.toLowerCase().replace(/[^a-z0-9]/g, '_');
    link.download = `CardioUNEMI_${safeTitle}_${new Date().toISOString().slice(0, 10)}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
    await new Promise(r => setTimeout(r, 60));
  }

  if (activeTabId !== originalTab) {
    switchTab(originalTab, document.querySelector(`.nav-item[onclick*="${originalTab}"]`));
  }
  setProgress('¡Imágenes descargadas con éxito!', 100);
}

// 2. Exportación a Documento PDF Paginado de Alta Fidelidad y Velocidad
async function exportPdf(scope, setProgress) {
  const { jsPDF } = window.jspdf || window;
  if (!jsPDF) {
    throw new Error('La librería jsPDF no está disponible.');
  }
  const h2c = window.html2canvas || (typeof html2canvas !== 'undefined' ? html2canvas : null);
  if (!h2c) {
    throw new Error('La librería html2canvas no está disponible.');
  }

  const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4', compress: true });
  const tabsToExport = scope === 'all' ? DASHBOARD_TABS : [DASHBOARD_TABS.find(t => t.id === activeTabId) || DASHBOARD_TABS[0]];
  const total = tabsToExport.length;
  const originalTab = activeTabId;

  const pageWidth = 297;
  const pageHeight = 210;
  const marginX = 10;
  const contentWidth = pageWidth - (marginX * 2); // 277 mm
  const maxImgHeight = pageHeight - 34; // 176 mm

  const instVal = document.getElementById('slicer-inst')?.value || 'Todas las Instituciones';
  const anoVal = document.getElementById('slicer-ano')?.value || 'Todos los Años';
  const sampleText = `${filteredRecords.length} de ${allRecords.length} evaluados`;
  const todayStr = new Date().toLocaleDateString('es-EC', { year: 'numeric', month: 'long', day: 'numeric' });

  let pageCount = 0;

  for (let i = 0; i < total; i++) {
    const tab = tabsToExport[i];
    setProgress(`Procesando: ${tab.title} (${i + 1}/${total})...`, Math.round(((i + 0.1) / total) * 90));
    await new Promise(r => setTimeout(r, 5));

    if (activeTabId !== tab.id) {
      switchTab(tab.id, document.querySelector(`.nav-item[onclick*="${tab.id}"]`));
      await new Promise(r => setTimeout(r, 180));
    } else {
      await new Promise(r => setTimeout(r, 50));
    }
    await new Promise(r => requestAnimationFrame(r));

    const targetEl = document.getElementById('tab-' + tab.id);
    const canvas = await renderSectionCanvas(h2c, tab, 1.15);
    if (!canvas) continue;

    const maxSlicePx = Math.floor(maxImgHeight * (canvas.width / contentWidth));
    const slices = getTabRowSlices(targetEl, canvas, maxSlicePx);

    for (let s = 0; s < slices.length; s++) {
      const slice = slices[s];
      const sliceH = slice.endY - slice.startY;
      if (sliceH <= 0) continue;

      if (pageCount > 0) {
        doc.addPage();
      }
      pageCount++;

      const sCanvas = createSliceCanvas(canvas, slice.startY, sliceH);
      const imgData = sCanvas.toDataURL('image/jpeg', 0.92);

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
      const partSuffix = slices.length > 1 ? ` (Parte ${s + 1} de ${slices.length})` : '';
      doc.text(tab.title + partSuffix, marginX, 23);

      // Renderizado del contenido visual a ancho completo
      const imgAspect = sliceH / canvas.width;
      const renderW = contentWidth;
      const renderH = renderW * imgAspect;
      const renderX = marginX;

      doc.addImage(imgData, 'JPEG', renderX, 26, renderW, renderH, undefined, 'FAST');

      // Pie de página
      doc.setTextColor(148, 163, 184);
      doc.setFontSize(7.5);
      doc.text('Universidad Estatal de Milagro (UNEMI) • Departamento de Cardiología', marginX, pageHeight - 4);
      doc.text(`Página ${pageCount}`, pageWidth - marginX, pageHeight - 4, { align: 'right' });
    }
  }

  if (activeTabId !== originalTab) {
    switchTab(originalTab, document.querySelector(`.nav-item[onclick*="${originalTab}"]`));
  }

  setProgress('Compilando archivo PDF final...', 96);
  await new Promise(r => setTimeout(r, 10));
  const fileName = scope === 'all'
    ? `CardioUNEMI_Reporte_Integral_9_Secciones_${new Date().toISOString().slice(0, 10)}.pdf`
    : `CardioUNEMI_${activeTabId}_${new Date().toISOString().slice(0, 10)}.pdf`;

  doc.save(fileName);
  setProgress('¡PDF generado exitosamente!', 100);
}

// 3. Exportación a Diapositivas PowerPoint (.pptx) de Alta Fidelidad y Velocidad
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
  setProgress('Construyendo portada institucional...', 5);
  await new Promise(r => setTimeout(r, 5));
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
    { text: scope === 'all' ? 'Informe Integral Completo (9 Secciones Clínicas)' : `Módulo Específico: ${tabsToExport[0].title}`, options: { color: 'FFFFFF' } }
  ], {
    x: 1.05, y: 3.45, w: 7.9, h: 1.3,
    fontSize: 11
  });

  let slideCount = 1;
  const maxW = 9.2; // pulgadas
  const maxH = 4.55; // pulgadas

  // Slide 2..N: Slides por cada Módulo Clínico
  for (let i = 0; i < total; i++) {
    const tab = tabsToExport[i];
    setProgress(`Generando diapositivas: ${tab.title} (${i + 1}/${total})...`, Math.round(10 + ((i + 1) / total) * 82));
    await new Promise(r => setTimeout(r, 5));

    if (activeTabId !== tab.id) {
      switchTab(tab.id, document.querySelector(`.nav-item[onclick*="${tab.id}"]`));
      await new Promise(r => setTimeout(r, 180));
    } else {
      await new Promise(r => setTimeout(r, 50));
    }
    await new Promise(r => requestAnimationFrame(r));

    const targetEl = document.getElementById('tab-' + tab.id);
    const canvas = await renderSectionCanvas(h2c, tab, 1.15);
    if (!canvas) continue;

    const maxSlidePx = Math.floor(maxH * (canvas.width / maxW));
    const slices = getTabRowSlices(targetEl, canvas, maxSlidePx);

    for (let s = 0; s < slices.length; s++) {
      const slice = slices[s];
      const sliceH = slice.endY - slice.startY;
      if (sliceH <= 0) continue;
      slideCount++;

      const sCanvas = createSliceCanvas(canvas, slice.startY, sliceH);
      const imgData = sCanvas.toDataURL('image/jpeg', 0.92);

      const slide = pptx.addSlide();
      slide.background = { color: 'F8FAFC' };

      // Barra Superior
      slide.addShape(pptx.ShapeType.rect, {
        x: 0, y: 0, w: 10, h: 0.65,
        fill: { color: '1B2A41' }
      });

      const partSuffix = slices.length > 1 ? ` (PARTE ${s + 1}/${slices.length})` : '';
      slide.addText(`CARDIOUNEMI • ${tab.title.toUpperCase()}${partSuffix}`, {
        x: 0.5, y: 0.12, w: 7.0, h: 0.4,
        fontSize: 12.5, color: 'FFFFFF', bold: true
      });

      slide.addText(`${todayStr} | N = ${filteredRecords.length}`, {
        x: 7.5, y: 0.14, w: 2.0, h: 0.35,
        fontSize: 9, color: 'CFE9FF', align: 'right'
      });

      // Imagen del Panel de Gráficos
      const imgAspect = sliceH / canvas.width;
      let w = maxW;
      let h = w * imgAspect;
      if (h > maxH) {
        h = maxH;
        w = h / imgAspect;
      }
      const x = 0.4 + (maxW - w) / 2;
      const y = 0.78;

      slide.addImage({ data: imgData, x: x, y: y, w: w, h: h });

      // Pie de diapositiva
      slide.addText('Universidad Estatal de Milagro • Departamento de Cardiología', {
        x: 0.5, y: 5.35, w: 6.0, h: 0.25,
        fontSize: 8, color: '94A3B8'
      });
      slide.addText(`Diapositiva ${slideCount}`, {
        x: 7.5, y: 5.35, w: 2.0, h: 0.25,
        fontSize: 8, color: '94A3B8', align: 'right'
      });
    }
  }

  if (activeTabId !== originalTab) {
    switchTab(originalTab, document.querySelector(`.nav-item[onclick*="${originalTab}"]`));
  }

  setProgress('Compilando presentación PowerPoint (.pptx)...', 96);
  await new Promise(r => setTimeout(r, 10));
  const fileName = scope === 'all'
    ? `CardioUNEMI_Presentacion_Completa_${new Date().toISOString().slice(0, 10)}.pptx`
    : `CardioUNEMI_${activeTabId}_${new Date().toISOString().slice(0, 10)}.pptx`;

  await pptx.writeFile({ fileName: fileName });
  setProgress('¡Presentación PPTX descargada exitosamente!', 100);
}


