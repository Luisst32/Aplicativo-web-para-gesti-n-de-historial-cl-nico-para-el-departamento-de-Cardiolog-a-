/**
 * SAV_IMPORTER.JS
 * Motor de importación automática de archivos SPSS (.sav / .zsav).
 * Procesa la carga y almacenamiento directamente en PostgreSQL con barra de progreso en tiempo real.
 */

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

  // Resetear estados a la fase inicial
  const fileInput = document.getElementById('savFileInput');
  if (fileInput) fileInput.value = '';

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

// Configuración de Drag & Drop al cargar
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
  if (!fname.endsWith('.sav') && !fname.endsWith('.zsav')) {
    alert('Por favor selecciona un archivo con extensión .sav o .zsav de IBM SPSS.');
    return;
  }

  // 1. Pasar inmediatamente a fase de carga y barra de progreso
  const phaseUpload = document.getElementById('savPhaseUpload');
  const phaseLoading = document.getElementById('savPhaseLoading');
  const phaseSuccess = document.getElementById('savPhaseSuccess');
  const modalFooter = document.getElementById('savModalFooter');

  if (phaseUpload) phaseUpload.style.display = 'none';
  if (phaseSuccess) phaseSuccess.style.display = 'none';
  if (phaseLoading) phaseLoading.style.display = 'block';
  if (modalFooter) modalFooter.style.display = 'none'; // Sin botones durante la carga

  // Iniciar progreso
  updateSavProgress(12, `Subiendo ${file.name}...`, 'Leyendo archivo binario y comprobando correspondencia de variables clínicas...', 'Subiendo y analizando estructura');

  let currentPct = 12;
  const progressTimer = setInterval(() => {
    if (currentPct < 45) {
      currentPct += 4;
      updateSavProgress(currentPct, `Analizando ${file.name}...`, 'Verificando variables clínicas, duplicados y reglas de validación...', 'Analizando variables SPSS');
    }
  }, 250);

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

    // LLAMADA 2: EXECUTE API (Automática sin confirmación manual)
    currentPct = 52;
    updateSavProgress(currentPct, `Importando ${totalRows} pacientes a la base de datos...`, 'Registrando visitas, exámenes antropométricos, factores de riesgo y ECG...', 'Guardando datos en PostgreSQL');

    const saveTimer = setInterval(() => {
      if (currentPct < 92) {
        currentPct += 5;
        updateSavProgress(currentPct, `Guardando registros clínicos (${currentPct}%)...`, 'Creando expedientes y respuestas con integridad transaccional...', 'Registrando pacientes');
      }
    }, 280);

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

    await new Promise(r => setTimeout(r, 450));

    // Mostrar fase de éxito
    if (phaseLoading) phaseLoading.style.display = 'none';
    if (phaseSuccess) phaseSuccess.style.display = 'block';

    const successMsg = document.getElementById('savSuccessMessage');
    if (successMsg) {
      successMsg.textContent = execData.message || `Se importaron ${totalRows} pacientes y registros con éxito.`;
    }

    const detailsBox = document.getElementById('savSuccessDetails');
    if (detailsBox) {
      const nuevos = execData.imported_count || 0;
      const actualizados = execData.updated_count || 0;
      const omitidos = execData.skipped_count || 0;

      detailsBox.innerHTML = `
        <div style="display:flex; justify-content:space-between; padding:5px 0; border-bottom:1px solid #e2e8f0;">
          <span style="color:#64748b; font-weight:600;">Pacientes nuevos creados:</span>
          <strong style="color:#047857; font-size:0.95rem;">${nuevos}</strong>
        </div>
        <div style="display:flex; justify-content:space-between; padding:5px 0; border-bottom:1px solid #e2e8f0;">
          <span style="color:#64748b; font-weight:600;">Pacientes actualizados:</span>
          <strong style="color:#1e40af; font-size:0.95rem;">${actualizados}</strong>
        </div>
        <div style="display:flex; justify-content:space-between; padding:5px 0;">
          <span style="color:#64748b; font-weight:600;">Pacientes omitidos:</span>
          <strong style="color:#334155; font-size:0.95rem;">${omitidos}</strong>
        </div>
        ${execData.errors && execData.errors.length > 0 ? `<div style="margin-top:8px; padding-top:6px; border-top:1px dashed #cbd5e1; color:#b91c1c; font-size:0.75rem;">Aviso: ${execData.errors.join(', ')}</div>` : ''}
      `;
    }

    // Mostrar pie con botón Aceptar
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

function finalizarImportacionSav() {
  cerrarModalImportarSav();
  // Si estamos en el listado de pacientes, recargar para mostrar los nuevos registros
  if (window.location.pathname.includes('/clinical/listado/')) {
    window.location.reload();
  } else {
    // Si estamos en el dashboard o inicio, redirigir al listado de pacientes
    window.location.href = '/clinical/listado/';
  }
}
