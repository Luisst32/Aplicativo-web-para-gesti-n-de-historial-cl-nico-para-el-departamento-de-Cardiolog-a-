/**
 * SAV_IMPORTER.JS
 * Lógica interactiva para la importación inteligente de archivos SPSS (.sav / .zsav).
 * Gestiona el análisis previo, advertencias, previsualización y confirmación transaccional.
 */

let currentSavToken = null;

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

  // Resetear estados y vistas
  currentSavToken = null;
  const fileInput = document.getElementById('savFileInput');
  if (fileInput) fileInput.value = '';

  document.getElementById('savPhaseUpload').style.display = 'block';
  document.getElementById('savPhaseLoading').style.display = 'none';
  document.getElementById('savPhaseConfirm').style.display = 'none';
  document.getElementById('savPhaseSuccess').style.display = 'none';

  document.getElementById('savBtnCancel').style.display = 'inline-block';
  document.getElementById('savBtnConfirm').style.display = 'none';
  document.getElementById('savBtnViewPatients').style.display = 'none';

  modal.style.display = 'flex';
}

function cerrarModalImportarSav() {
  const modal = document.getElementById('modalImportarSav');
  if (modal) modal.style.display = 'none';
}

function irAListadoPacientes() {
  window.location.href = '/clinical/listado/';
}

// Configuración de Drag & Drop al cargar
document.addEventListener('DOMContentLoaded', () => {
  const dropZone = document.getElementById('savDropZone');
  if (!dropZone) return;

  ['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.style.borderColor = 'var(--color-primary-blue, #3AA0FF)';
      dropZone.style.background = 'var(--blue-card-bg, #f0f7ff)';
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.style.borderColor = '#94a3b8';
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

  // Pasar a fase de carga / análisis
  document.getElementById('savPhaseUpload').style.display = 'none';
  document.getElementById('savPhaseLoading').style.display = 'block';
  document.getElementById('savLoadingTitle').textContent = `Analizando ${file.name}...`;
  document.getElementById('savLoadingSubtitle').textContent = 'Extrayendo etiquetas de valores, mapeando variables clínicas y verificando consistencia...';

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/clinical/api/import-sav/analyze/', {
      method: 'POST',
      body: formData,
      headers: {
        'X-CSRFToken': getCsrfToken()
      }
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.error || 'Error al analizar el archivo.');
    }

    currentSavToken = data.temp_token;

    // Actualizar métricas
    document.getElementById('savMetricRows').textContent = data.total_rows || '0';
    document.getElementById('savMetricNew').textContent = data.duplicates?.new_patients_count ?? (data.total_rows || '0');
    document.getElementById('savMetricDups').textContent = data.duplicates?.db_duplicates_count ?? '0';
    document.getElementById('savMetricTypos').textContent = data.grammatical_errors_count ?? '0';

    // 1. Sección Duplicados en Base de Datos
    const dupsSection = document.getElementById('savDuplicatesSection');
    const dupCount = data.duplicates?.db_duplicates_count || 0;
    if (dupCount > 0) {
      dupsSection.style.display = 'block';
      document.getElementById('savDupCountLabel').textContent = dupCount;
      const dupList = document.getElementById('savDupListContainer');
      const dups = data.duplicates?.db_duplicates || [];
      dupList.innerHTML = dups.map(d => `<div style="padding: 2px 0;">• <strong>Código ${d.code}:</strong> ${d.patient_name}</div>`).join('');
    } else {
      dupsSection.style.display = 'none';
    }

    // 2. Sección Errores Gramaticales y Tipográficos en Columnas
    const typosSection = document.getElementById('savTyposSection');
    const typoCount = data.grammatical_errors_count || 0;
    if (typoCount > 0) {
      typosSection.style.display = 'block';
      document.getElementById('savTypoCountLabel').textContent = typoCount;
      const typoList = document.getElementById('savTypoListContainer');
      const typos = data.grammatical_errors || [];
      typoList.innerHTML = typos.map(t => `
        <div style="padding: 3px 0; border-bottom: 1px dashed #f0abfc; display: flex; justify-content: space-between; gap: 8px;">
          <span>Columna SPSS: <code style="color: #be185d; font-weight: 700;">${t.column}</code> &rarr; Corregida a: <code style="color: #047857; font-weight: 700;">${t.corrected_to}</code></span>
          <span style="color: #64748b; font-size: 0.72rem;">${t.explanation}</span>
        </div>
      `).join('');
    } else {
      typosSection.style.display = 'none';
    }

    // Renderizar advertencias y avisos
    const warnBox = document.getElementById('savWarningsBox');
    warnBox.innerHTML = '';

    if (data.warnings && data.warnings.length > 0) {
      let warnHtml = `
        <div style="background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; padding: 12px 14px;">
          <div style="font-weight: 700; font-size: 0.85rem; color: #b45309; display: flex; align-items: center; gap: 6px; margin-bottom: 6px;">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
            Diagnóstico Asistido y Advertencias
          </div>
          <ul style="margin: 0; padding-left: 20px; font-size: 0.8rem; color: #78350f;">
      `;
      data.warnings.forEach(w => {
        warnHtml += `<li style="margin-bottom: 4px;">${w}</li>`;
      });
      warnHtml += `
          </ul>
        </div>
      `;
      warnBox.innerHTML = warnHtml;
    } else {
      warnBox.innerHTML = `
        <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 10px 14px; font-size: 0.82rem; color: #166534; display: flex; align-items: center; gap: 8px;">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>
          Estructura de variables verificada y consistente con el modelo clínico.
        </div>
      `;
    }

    // Renderizar tabla de previsualización
    const tbody = document.getElementById('savPreviewTbody');
    tbody.innerHTML = '';
    if (data.preview_rows && data.preview_rows.length > 0) {
      data.preview_rows.forEach(r => {
        const tr = document.createElement('tr');
        tr.style.borderBottom = '1px solid #f1f5f9';
        tr.innerHTML = `
          <td style="padding: 6px 10px; font-weight: 700; color: var(--color-primary-blue, #3AA0FF);">${r.codigo || '--'}</td>
          <td style="padding: 6px 10px;">${r.universidad || '--'}</td>
          <td style="padding: 6px 10px;">${r.sexo || '--'}</td>
          <td style="padding: 6px 10px;">${r.edad || '--'}</td>
          <td style="padding: 6px 10px;">${r.ciudad_res || '--'}</td>
          <td style="padding: 6px 10px;">${r.tas || '--'} / ${r.tad || '--'}</td>
          <td style="padding: 6px 10px;">${r.peso || '--'}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    // Actualizar botones del footer
    document.getElementById('savBtnConfirm').textContent = `Confirmar e Importar (${data.total_rows}) Pacientes`;
    document.getElementById('savBtnConfirm').style.display = 'inline-block';

    // Mostrar fase de confirmación
    document.getElementById('savPhaseLoading').style.display = 'none';
    document.getElementById('savPhaseConfirm').style.display = 'block';

  } catch (err) {
    alert('Error al analizar archivo SPSS: ' + err.message);
    document.getElementById('savPhaseLoading').style.display = 'none';
    document.getElementById('savPhaseUpload').style.display = 'block';
  }
}

function toggleSavDupDetails() {
  const container = document.getElementById('savDupListContainer');
  if (container) {
    container.style.display = (container.style.display === 'none' || !container.style.display) ? 'block' : 'none';
  }
}

function toggleSavTypoDetails() {
  const container = document.getElementById('savTypoListContainer');
  if (container) {
    container.style.display = (container.style.display === 'none' || !container.style.display) ? 'block' : 'none';
  }
}

async function ejecutarImportacionSav() {
  if (!currentSavToken) {
    alert('No hay un archivo cargado actualmente para importar.');
    return;
  }

  // Leer la acción elegida por el usuario para duplicados: 'update' (actualizar) o 'skip' (omitir)
  const dupActionRadio = document.querySelector('input[name="savDuplicateAction"]:checked');
  const duplicateAction = dupActionRadio ? dupActionRadio.value : 'update';

  // Pasar a fase de ejecución
  document.getElementById('savPhaseConfirm').style.display = 'none';
  document.getElementById('savBtnConfirm').style.display = 'none';
  document.getElementById('savBtnCancel').style.display = 'none';

  document.getElementById('savPhaseLoading').style.display = 'block';
  document.getElementById('savLoadingTitle').textContent = 'Guardando en la base de datos...';
  document.getElementById('savLoadingSubtitle').textContent = 'Creando expedientes de pacientes, visitas médicas, antropometría, signos vitales, ECG, laboratorio y encuestas...';

  try {
    const res = await fetch('/clinical/api/import-sav/execute/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      },
      body: JSON.stringify({
        temp_token: currentSavToken,
        duplicate_action: duplicateAction
      })
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.error || 'Error al ejecutar la importación.');
    }

    // Mostrar éxito
    document.getElementById('savPhaseLoading').style.display = 'none';
    document.getElementById('savPhaseSuccess').style.display = 'block';
    document.getElementById('savSuccessMessage').textContent = data.message;

    const detailsEl = document.getElementById('savSuccessDetails');
    detailsEl.innerHTML = `
      <div style="margin-bottom: 4px;"><strong>Nuevos pacientes creados:</strong> ${data.imported_count}</div>
      <div style="margin-bottom: 4px;"><strong>Visitas actualizadas:</strong> ${data.updated_count}</div>
      <div style="margin-bottom: 4px;"><strong>Total procesados:</strong> ${data.total_rows}</div>
      <div style="color: #15803d; font-weight: 600; margin-top: 6px;">✓ Todos los módulos clínicos y respuestas de encuestas persistidos en PostgreSQL.</div>
    `;

    document.getElementById('savBtnViewPatients').style.display = 'inline-block';

  } catch (err) {
    alert('Error durante la importación: ' + err.message);
    document.getElementById('savPhaseLoading').style.display = 'none';
    document.getElementById('savPhaseConfirm').style.display = 'block';
    document.getElementById('savBtnConfirm').style.display = 'inline-block';
    document.getElementById('savBtnCancel').style.display = 'inline-block';
  }
}

