/**
 * SAV_IMPORTER.JS
 * Lógica interactiva para la comprobación y mapeo de columnas SPSS (.sav / .zsav).
 * Comprueba los nombres de cada variable, indica qué datos van en dónde
 * y ejecuta la importación respetando los datos exactos del usuario sin alteraciones.
 */

let currentSavToken = null;
let currentMappings = [];
let currentFilter = 'typos';
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

  // Resetear estados y vistas
  currentSavToken = null;
  currentMappings = [];
  currentFilter = 'typos';
  currentSearchTerm = '';

  const fileInput = document.getElementById('savFileInput');
  if (fileInput) fileInput.value = '';

  const searchInput = document.getElementById('savSearchColumnInput');
  if (searchInput) searchInput.value = '';

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

  // Pasar a fase de carga / análisis
  document.getElementById('savPhaseUpload').style.display = 'none';
  document.getElementById('savPhaseLoading').style.display = 'block';
  document.getElementById('savLoadingTitle').textContent = `Comprobando ${file.name}...`;
  document.getElementById('savLoadingSubtitle').textContent = 'Comprobando nombres de columnas y correspondencia con la base de datos...';

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
    currentMappings = data.column_mappings || [];

    // Actualizar métricas principales
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

    // 2. Sección Comprobación y Mapeo de Columnas (Qué datos van en dónde)
    const typoCount = data.grammatical_errors_count || 0;
    const totalCols = data.total_columns || currentMappings.length;

    document.getElementById('savTypoBadgePill').textContent = `${typoCount} correcciones ortográficas`;
    document.getElementById('savCountTyposTab').textContent = typoCount;
    document.getElementById('savCountAllTab').textContent = totalCols;

    // Si hay correcciones ortográficas, mostrar esa pestaña primero; si no, mostrar todas
    currentFilter = typoCount > 0 ? 'typos' : 'all';
    currentSearchTerm = '';
    const searchInput = document.getElementById('savSearchColumnInput');
    if (searchInput) searchInput.value = '';

    actualizarBotonesFiltroMapeo();
    renderMappingTable();

    // 3. Renderizar tabla de previsualización de datos
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

function filtrarMapeo(tipo) {
  currentFilter = tipo;
  actualizarBotonesFiltroMapeo();
  renderMappingTable();
}

function onBuscarColumna(val) {
  currentSearchTerm = (val || '').toLowerCase().trim();
  renderMappingTable();
}

function actualizarBotonesFiltroMapeo() {
  const btnTypos = document.getElementById('savFilterBtnTypos');
  const btnAll = document.getElementById('savFilterBtnAll');
  if (!btnTypos || !btnAll) return;

  if (currentFilter === 'typos') {
    btnTypos.style.background = 'var(--color-primary-blue, #3AA0FF)';
    btnTypos.style.borderColor = 'var(--color-primary-blue, #3AA0FF)';
    btnTypos.style.color = '#fff';

    btnAll.style.background = '#fff';
    btnAll.style.borderColor = '#cbd5e1';
    btnAll.style.color = '#475569';
  } else {
    btnAll.style.background = 'var(--color-primary-blue, #3AA0FF)';
    btnAll.style.borderColor = 'var(--color-primary-blue, #3AA0FF)';
    btnAll.style.color = '#fff';

    btnTypos.style.background = '#fff';
    btnTypos.style.borderColor = '#cbd5e1';
    btnTypos.style.color = '#475569';
  }
}

function renderMappingTable() {
  const tbody = document.getElementById('savMappingTbody');
  if (!tbody) return;

  tbody.innerHTML = '';

  let filtrados = currentMappings;

  // Filtro por tipo (solo corregidos o todos)
  if (currentFilter === 'typos') {
    filtrados = filtrados.filter(m => m.has_correction);
  }

  // Filtro por texto de búsqueda
  if (currentSearchTerm) {
    filtrados = filtrados.filter(m =>
      (m.spss_column || '').toLowerCase().includes(currentSearchTerm) ||
      (m.corrected_name || '').toLowerCase().includes(currentSearchTerm) ||
      (m.destination_module || '').toLowerCase().includes(currentSearchTerm) ||
      (m.destination_field || '').toLowerCase().includes(currentSearchTerm)
    );
  }

  if (filtrados.length === 0) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td colspan="3" style="padding: 16px; text-align: center; color: #64748b; font-size: 0.78rem;">
        No se encontraron columnas que coincidan con el filtro actual.
      </td>
    `;
    tbody.appendChild(tr);
    return;
  }

  filtrados.forEach(m => {
    const tr = document.createElement('tr');
    tr.style.borderBottom = '1px solid #f1f5f9';

    const colOriginalHtml = m.has_correction
      ? `<code style="color: #be185d; font-weight: 700; background: #fdf2f8; padding: 2px 5px; border-radius: 4px;">${m.spss_column}</code>`
      : `<code style="color: #334155; font-weight: 600;">${m.spss_column}</code>`;

    const colCorregidaHtml = m.has_correction
      ? `<div style="display: flex; flex-direction: column; gap: 2px;">
           <code style="color: #047857; font-weight: 700; background: #ecfdf5; padding: 2px 5px; border-radius: 4px;">${m.corrected_name}</code>
           <span style="font-size: 0.68rem; color: #64748b;">${m.correction_detail || ''}</span>
         </div>`
      : `<span style="color: #94a3b8; font-size: 0.72rem;">Sin errores (Correcto)</span>`;

    const destinoHtml = `
      <div style="display: flex; align-items: center; gap: 6px;">
        <span style="background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; font-size: 0.71rem; font-weight: 700; padding: 1px 6px; border-radius: 4px; white-space: nowrap;">
          ${m.destination_module}
        </span>
        <span style="color: #334155; font-size: 0.74rem;">${m.destination_field}</span>
      </div>
    `;

    tr.innerHTML = `
      <td style="padding: 6px 10px; vertical-align: middle;">${colOriginalHtml}</td>
      <td style="padding: 6px 10px; vertical-align: middle;">${colCorregidaHtml}</td>
      <td style="padding: 6px 10px; vertical-align: middle;">${destinoHtml}</td>
    `;
    tbody.appendChild(tr);
  });
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
  document.getElementById('savLoadingTitle').textContent = 'Guardando datos en PostgreSQL...';
  document.getElementById('savLoadingSubtitle').textContent = 'Creando expedientes, visitas, exámenes y respuestas con integridad transaccional.';

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
      throw new Error(data.error || 'Ocurrió un error al ejecutar la importación.');
    }

    // Fase Éxito
    document.getElementById('savPhaseLoading').style.display = 'none';
    document.getElementById('savPhaseSuccess').style.display = 'block';
    document.getElementById('savSuccessMessage').textContent = data.message || 'Se procesaron todos los registros con éxito.';

    const detailsBox = document.getElementById('savSuccessDetails');
    detailsBox.innerHTML = `
      <div>• <strong>Pacientes nuevos creados:</strong> ${data.imported_count || 0}</div>
      <div>• <strong>Pacientes actualizados:</strong> ${data.updated_count || 0}</div>
      <div>• <strong>Pacientes omitidos:</strong> ${data.skipped_count || 0}</div>
      ${data.errors && data.errors.length > 0 ? `<div style="margin-top:6px; color:#b91c1c;">• <em>Advertencias menores:</em> ${data.errors.join('<br>')}</div>` : ''}
    `;

    document.getElementById('savBtnCancel').style.display = 'inline-block';
    document.getElementById('savBtnCancel').textContent = 'Cerrar';
    document.getElementById('savBtnViewPatients').style.display = 'inline-block';

  } catch (err) {
    alert('Error al importar datos: ' + err.message);
    document.getElementById('savPhaseLoading').style.display = 'none';
    document.getElementById('savPhaseConfirm').style.display = 'block';
    document.getElementById('savBtnConfirm').style.display = 'inline-block';
    document.getElementById('savBtnCancel').style.display = 'inline-block';
  }
}
