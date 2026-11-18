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
    if (scope === 'all') {
      if (typeof updateAllKPIs === 'function') updateAllKPIs();
      if (Array.isArray(DASHBOARD_TABS) && typeof renderTabCharts === 'function') {
        DASHBOARD_TABS.forEach(t => renderTabCharts(t.id));
      }
    }
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
    root.querySelectorAll('*').forEach(el => {
      if (el.hasAttribute('clip-path')) el.removeAttribute('clip-path');
      if (el.hasAttribute('clipPath')) el.removeAttribute('clipPath');
      if (el.style && el.style.clipPath) el.style.clipPath = 'none';
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
      const fill = el.getAttribute('fill') || el.style?.fill || '';
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

// Configuración de división ejecutiva en 2 partes por sección para garantizar proporción óptima 1:1 en hoja horizontal
function getTabPartsConfig(tabId) {
  const configs = {
    'resumen-general': {
      splitIdx: 3,
      part1Title: 'Resumen General • Indicadores y Distribución Epidemiológica',
      part2Title: 'Resumen General • Análisis Estadístico Avanzado (IC 95%)'
    },
    'datos-individuo': {
      splitIdx: 3,
      part1Title: 'Datos del Individuo • Demografía y Filiación',
      part2Title: 'Datos del Individuo • Gradientes Socioeconómicos de Riesgo'
    },
    'exploracion-fisica': {
      splitIdx: 3,
      part1Title: 'Exploración Física • Antropometría y Presión Arterial',
      part2Title: 'Exploración Física • Análisis Hemodinámico y Correlaciones'
    },
    'factores-modificables': {
      splitIdx: 5,
      part1Title: 'Factores de Riesgo Modificables • Prevalencia y Hábitos',
      part2Title: 'Factores de Riesgo Modificables • Manejo Terapéutico y Co-ocurrencia'
    },
    'factores-emergentes': {
      splitIdx: 3,
      part1Title: 'Factores de Riesgo Emergentes • Sueño, Estrés y Perfil Laboral',
      part2Title: 'Factores de Riesgo Emergentes • Interacción Psicosocial e Hipertensión'
    },
    'antecedentes-familiares': {
      splitIdx: 3,
      part1Title: 'Antecedentes Familiares • Carga Genética y Agregación Familiar',
      part2Title: 'Antecedentes Familiares • Concordancia Genética vs. Diagnóstico Propio'
    },
    'historia-no-cardio': {
      splitIdx: 3,
      part1Title: 'Historia Clínica No Cardiovascular • Comorbilidades Médicas',
      part2Title: 'Historia Clínica No Cardiovascular • Salud Mental y Comorbilidades por Sexo'
    },
    'covid-19': {
      splitIdx: 3,
      part1Title: 'COVID-19 y Secuelas • Prevalencia y Manejo Clínico',
      part2Title: 'COVID-19 y Secuelas • Análisis Epidemiológico con IC 95% y Long-COVID'
    },
    'electrocardiograma': {
      splitIdx: 3,
      part1Title: 'Electrocardiograma • Ritmo y Parámetros Eléctricos',
      part2Title: 'Electrocardiograma • Intervalo QTc Bazett y Análisis Avanzado'
    }
  };

  return configs[tabId] || {
    splitIdx: 3,
    part1Title: 'Indicadores y Distribución Epidemiológica',
    part2Title: 'Análisis Estadístico Avanzado'
  };
}

// Genera lista de ítems a exportar (2 páginas/diapositivas ejecutivas por cada módulo)
function getExportItems(scope) {
  const tabs = scope === 'all'
    ? DASHBOARD_TABS
    : [DASHBOARD_TABS.find(t => t.id === activeTabId) || DASHBOARD_TABS[0]];

  const items = [];
  tabs.forEach(tab => {
    const cfg = getTabPartsConfig(tab.id);
    items.push({
      tab,
      partNumber: 1,
      title: cfg.part1Title,
      suffix: 'parte1_indicadores'
    });
    items.push({
      tab,
      partNumber: 2,
      title: cfg.part2Title,
      suffix: 'parte2_avanzado'
    });
  });
  return items;
}

// Captura una parte específica (Parte 1 o Parte 2) de un módulo usando onclone sin slicing de píxeles
async function renderSectionPartCanvas(h2c, tab, partNumber, scale = 1.1) {
  const targetEl = document.getElementById('tab-' + tab.id);
  if (!targetEl) return null;
  const cfg = getTabPartsConfig(tab.id);
  const splitIdx = cfg.splitIdx || 3;

  return await h2c(targetEl, {
    scale: scale,
    useCORS: true,
    backgroundColor: '#FFFFFF',
    logging: false,
    imageTimeout: 0,
    ignoreElements: (el) => {
      if (!el) return false;
      if (el.id === 'modal-export-dashboard') return true;
      if (el.id === 'slicers-bar' || el.id === 'main-nav' || el.id === 'app-header' || el.classList?.contains('sidebar')) return true;
      if (el.classList && el.classList.contains('tab-view') && el.id !== ('tab-' + tab.id)) return true;
      return false;
    },
    onclone: (clonedDoc) => {
      fixSvgFillsForHtml2Canvas(clonedDoc, tab.id);
      const clonedTarget = clonedDoc.getElementById('tab-' + tab.id);
      if (!clonedTarget) return;

      clonedTarget.style.display = 'flex';
      clonedTarget.style.flexDirection = 'column';
      clonedTarget.style.background = '#FFFFFF';
      clonedTarget.style.padding = '0';
      clonedTarget.style.margin = '0';
      clonedTarget.style.height = 'auto';
      clonedTarget.style.minHeight = '0';
      clonedTarget.style.maxHeight = 'none';

      const rows = Array.from(clonedTarget.children).filter(c =>
        c && c.nodeType === 1 && c.tagName === 'DIV' &&
        (c.classList.contains('kpi-row') || c.classList.contains('grid-row') || c.classList.contains('grid'))
      );

      if (rows.length === 0) return;

      if (partNumber === 1) {
        rows.forEach((r, idx) => {
          if (idx >= splitIdx) {
            r.style.display = 'none';
          }
        });
      } else {
        rows.forEach((r, idx) => {
          if (idx < splitIdx) {
            r.style.display = 'none';
          }
        });
        if (rows[splitIdx]) {
          rows[splitIdx].style.marginTop = '0px';
          rows[splitIdx].style.paddingTop = '0px';
        }
      }
    }
  });
}

// Wrapper retrocompatible
async function renderSectionCanvas(h2c, tab, scale = 1.05) {
  return await renderSectionPartCanvas(h2c, tab, 1, scale);
}

// 1. Exportación a Imagen PNG (Descarga Parte 1 y Parte 2 por sección)
async function exportImage(scope, setProgress) {
  const h2c = window.html2canvas || (typeof html2canvas !== 'undefined' ? html2canvas : null);
  if (!h2c) {
    throw new Error('La librería html2canvas no está disponible.');
  }

  const exportItems = getExportItems(scope);
  const total = exportItems.length;
  const originalTab = activeTabId;
  let currentRenderedTab = null;

  for (let i = 0; i < total; i++) {
    const item = exportItems[i];
    const tab = item.tab;
    setProgress(`Capturando imagen: ${item.title} (${i + 1}/${total})...`, Math.round(((i + 0.3) / total) * 100));
    await new Promise(r => setTimeout(r, 5));

    if (activeTabId !== tab.id) {
      switchTab(tab.id, document.querySelector(`.nav-item[onclick*="${tab.id}"]`));
      await new Promise(r => setTimeout(r, 180));
      currentRenderedTab = tab.id;
    } else if (currentRenderedTab !== tab.id) {
      await new Promise(r => setTimeout(r, 50));
      currentRenderedTab = tab.id;
    }
    await new Promise(r => requestAnimationFrame(r));

    const canvas = await renderSectionPartCanvas(h2c, tab, item.partNumber, 1.25);
    if (!canvas) continue;

    const link = document.createElement('a');
    const safeTitle = tab.title.toLowerCase().replace(/[^a-z0-9]/g, '_');
    link.download = `CardioUNEMI_${safeTitle}_${item.suffix}_${new Date().toISOString().slice(0, 10)}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
    await new Promise(r => setTimeout(r, 60));
  }

  if (activeTabId !== originalTab) {
    switchTab(originalTab, document.querySelector(`.nav-item[onclick*="${originalTab}"]`));
  }
  setProgress('¡Imágenes descargadas con éxito!', 100);
}

// 2. Exportación a Documento PDF Ejecutivo Paginado (2 Páginas por Sección)
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
  const exportItems = getExportItems(scope);
  const total = exportItems.length;
  const originalTab = activeTabId;
  let currentRenderedTab = null;

  const pageWidth = 297;
  const pageHeight = 210;
  const marginX = 10;
  const contentWidth = pageWidth - (marginX * 2); // 277 mm
  const maxImgHeight = 173; // 173 mm (reserva margen seguro para cabecera superior y pie de página)

  const instVal = document.getElementById('slicer-inst')?.value || 'Todas las Instituciones';
  const anoVal = document.getElementById('slicer-ano')?.value || 'Todos los Años';
  const sampleText = `${filteredRecords.length} de ${allRecords.length} evaluados`;
  const todayStr = new Date().toLocaleDateString('es-EC', { year: 'numeric', month: 'long', day: 'numeric' });

  for (let i = 0; i < total; i++) {
    const item = exportItems[i];
    const tab = item.tab;
    setProgress(`Procesando: ${item.title} (${i + 1}/${total})...`, Math.round(((i + 0.1) / total) * 92));
    await new Promise(r => setTimeout(r, 5));

    if (activeTabId !== tab.id) {
      switchTab(tab.id, document.querySelector(`.nav-item[onclick*="${tab.id}"]`));
      await new Promise(r => setTimeout(r, 180));
      currentRenderedTab = tab.id;
    } else if (currentRenderedTab !== tab.id) {
      await new Promise(r => setTimeout(r, 50));
      currentRenderedTab = tab.id;
    }
    await new Promise(r => requestAnimationFrame(r));

    const canvas = await renderSectionPartCanvas(h2c, tab, item.partNumber, 1.1);
    if (!canvas) continue;

    if (i > 0) {
      doc.addPage();
    }

    const imgData = canvas.toDataURL('image/jpeg', 0.94);

    // 1. Cabecera Institucional Superior
    doc.setFillColor(27, 42, 65); // #1B2A41 Navy UNEMI
    doc.rect(0, 0, pageWidth, 15, 'F');

    doc.setTextColor(255, 255, 255);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(10.5);
    doc.text('CARDIOUNEMI • VIGILANCIA EPIDEMIOLÓGICA CARDIOVASCULAR', marginX, 9.5);

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(7.8);
    doc.text(`Cohorte: ${sampleText} | ${instVal} - Año ${anoVal} | ${todayStr}`, pageWidth - marginX, 9.5, { align: 'right' });

    // 2. Título de la Sección y Parte
    doc.setTextColor(27, 42, 65);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(11.5);
    doc.text(item.title, marginX, 22.5);

    // 3. Renderizado del contenido visual a ancho completo
    const imgAspect = canvas.height / canvas.width;
    let renderW = contentWidth;
    let renderH = renderW * imgAspect;
    if (renderH > maxImgHeight) {
      renderH = maxImgHeight;
      renderW = renderH / imgAspect;
    }
    const renderX = marginX + (contentWidth - renderW) / 2;
    const renderY = 26 + (maxImgHeight - renderH) / 2;

    doc.addImage(imgData, 'JPEG', renderX, renderY, renderW, renderH, undefined, 'FAST');

    // 4. Pie de página
    doc.setTextColor(148, 163, 184);
    doc.setFontSize(7.5);
    doc.text('Universidad Estatal de Milagro (UNEMI) • Departamento de Cardiología', marginX, pageHeight - 4.5);
    doc.text(`Página ${i + 1} de ${total}`, pageWidth - marginX, pageHeight - 4.5, { align: 'right' });
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

// 3. Exportación a Diapositivas PowerPoint (.pptx) de Alta Fidelidad (2 Slides por Sección)
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

  const exportItems = getExportItems(scope);
  const total = exportItems.length;
  const originalTab = activeTabId;
  let currentRenderedTab = null;

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
    { text: scope === 'all' ? 'Informe Integral Completo (9 Secciones Clínicas • Formato Ejecutivo)' : `Módulo Específico: ${exportItems[0].tab.title} (2 Diapositivas)`, options: { color: 'FFFFFF' } }
  ], {
    x: 1.05, y: 3.45, w: 7.9, h: 1.3,
    fontSize: 11
  });

  const maxW = 9.2; // pulgadas
  const maxH = 4.55; // pulgadas
  const topY = 0.75; // pulgadas

  // Slide 2..N: Slides por cada Parte de Módulo Clínico
  for (let i = 0; i < total; i++) {
    const item = exportItems[i];
    const tab = item.tab;
    setProgress(`Generando diapositivas: ${item.title} (${i + 1}/${total})...`, Math.round(10 + ((i + 1) / total) * 82));
    await new Promise(r => setTimeout(r, 5));

    if (activeTabId !== tab.id) {
      switchTab(tab.id, document.querySelector(`.nav-item[onclick*="${tab.id}"]`));
      await new Promise(r => setTimeout(r, 180));
      currentRenderedTab = tab.id;
    } else if (currentRenderedTab !== tab.id) {
      await new Promise(r => setTimeout(r, 50));
      currentRenderedTab = tab.id;
    }
    await new Promise(r => requestAnimationFrame(r));

    const canvas = await renderSectionPartCanvas(h2c, tab, item.partNumber, 1.1);
    if (!canvas) continue;

    const imgData = canvas.toDataURL('image/jpeg', 0.94);

    const slide = pptx.addSlide();
    slide.background = { color: 'F8FAFC' };

    // Barra Superior
    slide.addShape(pptx.ShapeType.rect, {
      x: 0, y: 0, w: 10, h: 0.65,
      fill: { color: '1B2A41' }
    });

    slide.addText(`CARDIOUNEMI • ${item.title.toUpperCase()}`, {
      x: 0.5, y: 0.12, w: 7.2, h: 0.4,
      fontSize: 11, color: 'FFFFFF', bold: true
    });

    slide.addText(`${todayStr} | N = ${filteredRecords.length}`, {
      x: 7.7, y: 0.14, w: 1.8, h: 0.35,
      fontSize: 8.5, color: 'CFE9FF', align: 'right'
    });

    // Imagen del Panel de Gráficos Centrada
    const imgAspect = canvas.height / canvas.width;
    let w = maxW;
    let h = w * imgAspect;
    if (h > maxH) {
      h = maxH;
      w = h / imgAspect;
    }
    const x = 0.4 + (maxW - w) / 2;
    const y = topY + (maxH - h) / 2;

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
