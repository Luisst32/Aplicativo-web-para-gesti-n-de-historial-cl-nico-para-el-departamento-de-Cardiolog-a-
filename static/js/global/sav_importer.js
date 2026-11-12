/**
 * SAV_IMPORTER.JS
 * Motor de importación inteligente y automática de archivos SPSS (.sav / .zsav).
 * Ejecuta análisis y persistencia en PostgreSQL a ultra-alta velocidad
 * y presenta el diagnóstico completo de correcciones ortográficas y métricas.
 */

let currentColumnMappings = [];
let currentMappingFilter = 'errors'; // 'errors' o 'all'
let currentSearchTerm = '';

function getCsrfToken() {
  const cookieVal = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1];
  if (cookieVal) return cookieVal;
  const inputEl = document.querySelector('[name=csrfmiddlewaretoken]');
  return inputEl ? inputEl.value : '';
}

function abrirModalImportarSav() {
  const modal = document.getElementById('modalImportarSav');
  if (!modal) return;

  // Cerrar menú de usuario si está abierto
  const userMenu = document.getElementById('userMenu');
  if (userMenu) userMenu.classList.remove('open');

  // Resetear estados a la fase inicial compacta
  const fileInput = document.getElementById('savFileInput');
  if (fileInput) fileInput.value = '';

  const modalCard = document.getElementById('savModalCard');
  if (modalCard) modalCard.style.maxWidth = '560px';

  const phaseUpload = document.getElementById('savPhaseUpload');
  const phaseLoading = document.getElementById('savPhaseLoading');
  const phaseSuccess = document.getElementById('savPhaseSuccess');
  const modalFooter = document.getElementById('savModalFooter');
  const btnCancel = document.getElementById('savBtnCancel');
  const btnSuccessOk = document.getElementById('savBtnSuccessOk');

  if (phaseUpload) phaseUpload.style.display = 'block';
  if (phaseLoading) phaseLoading.style.display = 'none';
  if (phaseSuccess) phaseSuccess.style.display = 'none';

  if (modalFooter) modalFooter.style.display = 'flex';
  if (btnCancel) {
    btnCancel.style.display = 'inline-flex';
    btnCancel.textContent = 'Cancelar';
  }
  if (btnSuccessOk) btnSuccessOk.style.display = 'none';

  currentColumnMappings = [];
  currentMappingFilter = 'errors';
  currentSearchTerm = '';

  const dupsSection = document.getElementById('savDuplicatesSection');
  if (dupsSection) dupsSection.style.display = 'none';
  const dupsWrapper = document.getElementById('savDupsTableWrapper');
  if (dupsWrapper) dupsWrapper.style.display = 'none';
  const btnText = document.getElementById('savToggleDupsBtnText');
  if (btnText) btnText.textContent = 'Ver detalle de duplicados';
  const arrow = document.getElementById('savToggleDupsArrow');
  if (arrow) arrow.style.transform = 'rotate(0deg)';

  // Resetear barra de progreso
  updateSavProgress(0, 'Importando archivo SPSS...', 'Procesando y guardando datos automáticamente en la base de datos...', 'Progreso de importación');

  modal.style.display = 'flex';
}

function cerrarModalImportarSav() {
  const modal = document.getElementById('modalImportarSav');
  if (modal) modal.style.display = 'none';
}

function updateSavProgress(pct, title, subtitle, stepText) {
  const progressBar = document.getElementById('savProgressBar');
  const progressPct = document.getElementById('savProgressPct');
  const loadingTitle = document.getElementById('savLoadingTitle');
  const loadingSubtitle = document.getElementById('savLoadingSubtitle');
  const stepTextEl = document.getElementById('savProgressStepText');

  const safePct = Math.min(100, Math.max(0, Math.round(pct)));

  if (progressBar) progressBar.style.width = safePct + '%';
  if (progressPct) progressPct.textContent = safePct + '%';
  if (title && loadingTitle) loadingTitle.textContent = title;
  if (subtitle && loadingSubtitle) loadingSubtitle.textContent = subtitle;
  if (stepText && stepTextEl) stepTextEl.textContent = stepText;
}

// Configuración de Drag & Drop al cargar el documento
document.addEventListener('DOMContentLoaded', () => {
  const dropZone = document.getElementById('savDropZone');
  if (!dropZone) return;

  ['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.style.borderColor = '#3AA0FF';
      dropZone.style.background = '#f0f7ff';
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.style.borderColor = '#cbd5e1';
      dropZone.style.background = '#f8fafc';
    }, false);
  });

  dropZone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files && files.length > 0) {
      onSavFileSelected(files[0]);
    }
  }, false);
});

async function onSavFileSelected(file) {
  if (!file) return;

  const fname = file.name.toLowerCase();
  const validExts = ['.sav', '.zsav', '.rds', '.rdata', '.rda', '.csv'];
  if (!validExts.some(ext => fname.endsWith(ext))) {
    alert('Por favor selecciona un archivo SPSS (.sav, .zsav), RStudio (.rds, .RData) o CSV.');
    return;
  }

  // 1. Pasar inmediatamente a fase de carga y barra de progreso (sin botones bloqueantes)
  const phaseUpload = document.getElementById('savPhaseUpload');
  const phaseLoading = document.getElementById('savPhaseLoading');
  const phaseSuccess = document.getElementById('savPhaseSuccess');
  const modalFooter = document.getElementById('savModalFooter');

  if (phaseUpload) phaseUpload.style.display = 'none';
  if (phaseSuccess) phaseSuccess.style.display = 'none';
  if (phaseLoading) phaseLoading.style.display = 'block';
  if (modalFooter) modalFooter.style.display = 'none';

  // Iniciar progreso
  updateSavProgress(15, `Subiendo ${file.name}...`, 'Analizando variables clínicas, reglas de correspondencia y correcciones ortográficas...', 'Subiendo y analizando estructura');

  let currentPct = 15;
  const progressTimer = setInterval(() => {
    if (currentPct < 45) {
      currentPct += 5;
      updateSavProgress(currentPct, `Diagnosticando ${file.name}...`, 'Detectando columnas clínicas, tipografías y reglas de validación...', 'Analizando variables SPSS');
    }
  }, 180);

  const formData = new FormData();
  formData.append('file', file);

  try {
    // LLAMADA 1: ANALYZE API
    const analyzeRes = await fetch('/clinical/api/import-sav/analyze/', {
      method: 'POST',
      body: formData,
      headers: {
        'X-CSRFToken': getCsrfToken()
      }
    });

    clearInterval(progressTimer);

    const analyzeData = await analyzeRes.json();
    if (!analyzeRes.ok || !analyzeData.success) {
      throw new Error(analyzeData.error || 'Error al analizar el archivo SPSS.');
    }

    const tempToken = analyzeData.temp_token;
    const totalRows = analyzeData.total_rows || 0;

    // LLAMADA 2: EXECUTE API (Ultra-rápida, con transacción atómica y bulk_create)
    currentPct = 55;
    updateSavProgress(currentPct, `Guardando ${totalRows} pacientes en PostgreSQL...`, 'Registrando visitas, exámenes antropométricos, factores de riesgo y ECG...', 'Guardando en base de datos');

    const saveTimer = setInterval(() => {
      if (currentPct < 90) {
        currentPct += 6;
        updateSavProgress(currentPct, `Guardando registros clínicos (${currentPct}%)...`, 'Sincronizando modelos con integridad referencial...', 'Registrando pacientes');
      }
    }, 150);

    const execRes = await fetch('/clinical/api/import-sav/execute/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      },
      body: JSON.stringify({
        temp_token: tempToken,
        duplicate_action: 'update'
      })
    });

    clearInterval(saveTimer);

    const execData = await execRes.json();
    if (!execRes.ok || !execData.success) {
      throw new Error(execData.error || 'Ocurrió un error al ejecutar la importación.');
    }

    // 100% Completado
    updateSavProgress(100, '¡Importación completada!', 'Todos los pacientes y registros se han guardado con éxito.', 'Completado al 100%');

    await new Promise(r => setTimeout(r, 300));

    // Expandir el modal a vista panorámica para mostrar el diagnóstico completo
    const modalCard = document.getElementById('savModalCard');
    if (modalCard) modalCard.style.maxWidth = '880px';

    // Rellenar métricas inteligentes
    const metricRows = document.getElementById('savMetricRows');
    const metricNew = document.getElementById('savMetricNew');
    const metricDups = document.getElementById('savMetricDups');
    const metricTypos = document.getElementById('savMetricTypos');
    const errorsTabCount = document.getElementById('savErrorsTabCount');
    const totalColsBadge = document.getElementById('savTotalColsBadge');
    const successMsg = document.getElementById('savSuccessMessage');

    const rowsCount = execData.total_rows || analyzeData.total_rows || 0;
    const newCount = execData.imported_count || 0;
    const dupsCount = execData.duplicate_count !== undefined ? execData.duplicate_count : (execData.updated_count || 0);
    const typosCount = analyzeData.grammatical_errors_count || 0;

    if (metricRows) metricRows.textContent = rowsCount;
    if (metricNew) metricNew.textContent = newCount;
    if (metricDups) metricDups.textContent = dupsCount;
    if (metricTypos) metricTypos.textContent = typosCount;
    if (errorsTabCount) errorsTabCount.textContent = typosCount;
    if (totalColsBadge) totalColsBadge.textContent = `${analyzeData.total_columns || 0} variables analizadas`;

    // Estilo y etiqueta dinámica para tarjeta de Duplicados
    const cardDups = document.getElementById('savCardDups');
    const labelDups = document.getElementById('savMetricDupsLabel');
    if (cardDups && labelDups) {
      if (dupsCount > 0) {
        cardDups.style.background = '#fffbeb';
        cardDups.style.borderColor = '#fde68a';
        metricDups.style.color = '#b45309';
        labelDups.style.color = '#92400e';
        labelDups.textContent = `${dupsCount} Duplicados en BD`;
      } else {
        cardDups.style.background = '#f8fafc';
        cardDups.style.borderColor = '#e2e8f0';
        metricDups.style.color = '#15803d';
        labelDups.style.color = '#166534';
        labelDups.textContent = 'Sin Duplicados (0)';
      }
    }

    if (successMsg) {
      successMsg.textContent = execData.message || `Se importaron ${rowsCount} pacientes y registros con éxito.`;
    }

    // Gestionar Sección Inteligente de Duplicados en el Resumen
    const dupsSection = document.getElementById('savDuplicatesSection');
    const dupsCountBadge = document.getElementById('savDupsCountBadge');
    const dupsDesc = document.getElementById('savDuplicatesDesc');
    const dupsTableBody = document.getElementById('savDupsTableBody');
    const internalNotice = document.getElementById('savInternalDupsNotice');
    const internalText = document.getElementById('savInternalDupsText');

    const duplicateRecords = execData.duplicate_records || [];
    const internalDuplicates = analyzeData.duplicates?.internal_duplicates || [];

    if (dupsSection) {
      if (dupsCount > 0 || internalDuplicates.length > 0) {
        dupsSection.style.display = 'block';
        if (dupsCountBadge) dupsCountBadge.textContent = dupsCount;
        if (dupsDesc) {
          dupsDesc.textContent = `Se detectaron ${dupsCount} paciente(s) que ya existían previamente en esta cohorte. Sus datos clínicos fueron actualizados y sincronizados sin alterar su identificador.`;
        }

        // Renderizar tabla de duplicados
        if (dupsTableBody) {
          if (duplicateRecords.length > 0) {
            dupsTableBody.innerHTML = duplicateRecords.map(d => `
              <tr style="border-bottom: 1px solid #fef3c7;">
                <td style="padding: 6px 10px; color: #64748b;">${escapeHtml(d.row || '--')}</td>
                <td style="padding: 6px 10px; font-weight: 700; color: #92400e;">${escapeHtml(d.code || '--')}</td>
                <td style="padding: 6px 10px; color: #475569;">${escapeHtml(d.institution || 'UNEMI')}</td>
                <td style="padding: 6px 10px; color: #1e293b; font-weight: 600;">${escapeHtml(d.patient_name || 'Paciente')} ${d.id_card ? `<span style="font-size:0.7rem; color:#64748b;">(${escapeHtml(d.id_card)})</span>` : ''}</td>
                <td style="padding: 6px 10px; text-align: center;">
                  <span style="background: #fef3c7; color: #b45309; font-weight: 700; padding: 2px 7px; border-radius: 4px; font-size: 0.72rem; border: 1px solid #fde68a;">
                    ${escapeHtml(d.action || 'Actualizado en BD')}
                  </span>
                </td>
              </tr>
            `).join('');
          } else {
            dupsTableBody.innerHTML = `
              <tr>
                <td colspan="5" style="text-align: center; padding: 12px; color: #94a3b8; font-style: italic;">
                  No hay detalles individuales de duplicados para mostrar.
                </td>
              </tr>
            `;
          }
        }

        // Aviso si hay duplicidad interna dentro del archivo SPSS
        if (internalNotice && internalText) {
          if (internalDuplicates.length > 0) {
            internalNotice.style.display = 'block';
            const codList = internalDuplicates.map(idup => `Código ${idup.code} (${idup.institution}, filas ${idup.rows.join(' y ')})`).join(', ');
            internalText.textContent = `Se detectaron códigos repetidos en distintas filas dentro del archivo: ${codList}.`;
          } else {
            internalNotice.style.display = 'none';
          }
        }
      } else {
        dupsSection.style.display = 'none';
      }
    }

    // Guardar lista de mapeo de columnas para renderizar y filtrar
    currentColumnMappings = analyzeData.column_mappings || [];
    currentMappingFilter = typosCount > 0 ? 'errors' : 'all';
    filtrarMapeo(currentMappingFilter);

    // Rellenar previsualización de pacientes importados
    const previewTbody = document.getElementById('savPreviewTbody');
    if (previewTbody && analyzeData.preview_rows) {
      previewTbody.innerHTML = analyzeData.preview_rows.map(r => {
        const isDup = r.is_duplicate;
        const statusBadge = isDup
          ? `<span style="background: #fef3c7; color: #b45309; font-weight: 700; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; border: 1px solid #fde68a;">Duplicado (Actualizado)</span>`
          : `<span style="background: #ecfdf5; color: #047857; font-weight: 700; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; border: 1px solid #a7f3d0;">Nuevo</span>`;
        return `
          <tr style="border-bottom: 1px solid #f1f5f9;">
            <td style="padding: 6px 10px; font-weight: 700; color: #1e293b;">${escapeHtml(r.codigo || '--')}</td>
            <td style="padding: 6px 10px; color: #475569;">${escapeHtml(r.universidad || 'UNEMI')}</td>
            <td style="padding: 6px 10px; color: #475569;">${escapeHtml(r.sexo || '--')}</td>
            <td style="padding: 6px 10px; color: #475569;">${escapeHtml(r.edad || '--')}</td>
            <td style="padding: 6px 10px; color: #475569;">${escapeHtml(r.ciudad_res || '--')}</td>
            <td style="padding: 6px 10px; color: #475569;">${escapeHtml(r.tas || '--')} / ${escapeHtml(r.tad || '--')}</td>
            <td style="padding: 6px 10px; color: #475569;">${escapeHtml(r.peso || '--')}</td>
            <td style="padding: 6px 10px; text-align: center;">${statusBadge}</td>
          </tr>
        `;
      }).join('');
    }

    // Mostrar fase de éxito
    if (phaseLoading) phaseLoading.style.display = 'none';
    if (phaseSuccess) phaseSuccess.style.display = 'block';

    // Mostrar pie de modal con botón unificado de estilo idéntico al de ajustes
    if (modalFooter) modalFooter.style.display = 'flex';
    const btnCancel = document.getElementById('savBtnCancel');
    const btnSuccessOk = document.getElementById('savBtnSuccessOk');
    if (btnCancel) btnCancel.style.display = 'none';
    if (btnSuccessOk) btnSuccessOk.style.display = 'inline-flex';

  } catch (err) {
    alert('Error al importar archivo SPSS: ' + err.message);
    if (phaseLoading) phaseLoading.style.display = 'none';
    if (phaseUpload) phaseUpload.style.display = 'block';
    if (modalFooter) modalFooter.style.display = 'flex';
    const btnCancel = document.getElementById('savBtnCancel');
    if (btnCancel) {
      btnCancel.style.display = 'inline-flex';
      btnCancel.textContent = 'Cancelar';
    }
  }
}

function filtrarMapeo(tipo) {
  currentMappingFilter = tipo;

  const btnErrors = document.getElementById('savTabBtnErrors');
  const btnAll = document.getElementById('savTabBtnAll');

  if (btnErrors && btnAll) {
    if (tipo === 'errors') {
      btnErrors.style.background = '#f5f3ff';
      btnErrors.style.borderColor = '#ddd6fe';
      btnErrors.style.color = '#6d28d9';
      btnAll.style.background = '#ffffff';
      btnAll.style.borderColor = '#cbd5e1';
      btnAll.style.color = '#475569';
    } else {
      btnAll.style.background = '#eff6ff';
      btnAll.style.borderColor = '#bfdbfe';
      btnAll.style.color = '#1d4ed8';
      btnErrors.style.background = '#ffffff';
      btnErrors.style.borderColor = '#cbd5e1';
      btnErrors.style.color = '#475569';
    }
  }

  renderMappingTable();
}

function onBuscarColumna(val) {
  currentSearchTerm = (val || '').toLowerCase().trim();
  renderMappingTable();
}

function renderMappingTable() {
  const tbody = document.getElementById('savMappingTbody');
  if (!tbody) return;

  let items = currentColumnMappings;

  // Filtro por pestaña
  if (currentMappingFilter === 'errors') {
    items = items.filter(m => m.has_correction);
  }

  // Filtro por término de búsqueda
  if (currentSearchTerm) {
    items = items.filter(m =>
      (m.spss_column || '').toLowerCase().includes(currentSearchTerm) ||
      (m.corrected_name || '').toLowerCase().includes(currentSearchTerm) ||
      (m.destination_label || '').toLowerCase().includes(currentSearchTerm) ||
      (m.correction_detail || '').toLowerCase().includes(currentSearchTerm)
    );
  }

  if (items.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="3" style="text-align: center; padding: 18px; color: #94a3b8; font-style: italic;">
          ${currentMappingFilter === 'errors' ? 'No se detectaron errores ortográficos adicionales en las columnas.' : 'No se encontraron variables con el término buscado.'}
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = items.map(m => {
    const isCorregido = m.has_correction;
    const spssBadge = isCorregido
      ? `<span style="font-family: monospace; font-weight: 700; color: #b91c1c; text-decoration: line-through; background: #fee2e2; padding: 2px 6px; border-radius: 4px;">${escapeHtml(m.spss_column)}</span>`
      : `<span style="font-family: monospace; font-weight: 600; color: #334155;">${escapeHtml(m.spss_column)}</span>`;

    const corrBadge = isCorregido
      ? `<div style="display: flex; flex-direction: column; gap: 2px;">
           <span style="font-family: monospace; font-weight: 700; color: #047857; background: #dcfce7; padding: 2px 6px; border-radius: 4px; display: inline-block;">${escapeHtml(m.corrected_name)}</span>
           <span style="font-size: 0.7rem; color: #6d28d9; font-style: italic;">${escapeHtml(m.correction_detail || 'Corregido ortográficamente')}</span>
         </div>`
      : `<span style="font-family: monospace; color: #64748b;">${escapeHtml(m.corrected_name)}</span>`;

    const destBadge = `<div style="display: flex; align-items: center; gap: 6px;">
        <span style="background: #eff6ff; color: #1e40af; font-size: 0.7rem; font-weight: 700; padding: 2px 6px; border-radius: 4px; white-space: nowrap;">${escapeHtml(m.destination_module || 'Clínico')}</span>
        <span style="color: #334155; font-size: 0.74rem;">${escapeHtml(m.destination_field || m.destination_label)}</span>
      </div>`;

    return `
      <tr style="border-bottom: 1px solid #f1f5f9; ${isCorregido ? 'background: #faf5ff;' : ''}">
        <td style="padding: 6px 10px;">${spssBadge}</td>
        <td style="padding: 6px 10px;">${corrBadge}</td>
        <td style="padding: 6px 10px;">${destBadge}</td>
      </tr>
    `;
  }).join('');
}

function finalizarImportacionSav() {
  cerrarModalImportarSav();
  // Si estamos en el listado de pacientes, recargar para mostrar los nuevos registros
  if (window.location.pathname === '/' || window.location.pathname.includes('/clinical/listado/')) {
    window.location.reload();
  } else {
    // Si estamos en otra vista, redirigir a la raíz (listado de pacientes)
    window.location.href = '/';
  }
}

function toggleDetalleDuplicados() {
  const wrapper = document.getElementById('savDupsTableWrapper');
  const btnText = document.getElementById('savToggleDupsBtnText');
  const arrow = document.getElementById('savToggleDupsArrow');
  if (!wrapper) return;

  const isHidden = wrapper.style.display === 'none' || wrapper.style.display === '';
  wrapper.style.display = isHidden ? 'block' : 'none';
  if (btnText) {
    btnText.textContent = isHidden ? 'Ocultar detalle de duplicados' : 'Ver detalle de duplicados';
  }
  if (arrow) {
    arrow.style.transform = isHidden ? 'rotate(180deg)' : 'rotate(0deg)';
  }
}

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
