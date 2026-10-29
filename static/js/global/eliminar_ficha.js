/**
 * ELIMINAR_FICHA.JS
 * Lógica transversal para la eliminación protegida por contraseña de Fichas Clínicas
 * (individual y selección múltiple / por lote).
 */

let _targetIdsEliminar = [];

function getCsrfTokenEliminar() {
  const cookieVal = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1];
  if (cookieVal) return cookieVal;
  const inputEl = document.querySelector('[name=csrfmiddlewaretoken]');
  return inputEl ? inputEl.value : '';
}

/**
 * Abre el modal para eliminar una ficha individual o un conjunto de fichas.
 * @param {string|number|Array} target - ID de paciente o arreglo de IDs
 * @param {string} [pacienteNombre] - Nombre para mostrar en caso individual
 * @param {string} [codigo] - Código de estudio para mostrar
 */
function solicitarEliminarFicha(target, pacienteNombre, codigo) {
  const modal = document.getElementById('modalEliminarFicha');
  if (!modal) return;

  const isMultiple = Array.isArray(target) || (target instanceof Set);
  _targetIdsEliminar = isMultiple ? Array.from(target) : [target];

  const modalTitulo = document.getElementById('deleteModalTitulo') || modal.querySelector('h3');
  const msgP = document.getElementById('deleteModalMensaje');
  const advSpan = document.getElementById('deleteModalAdvertencia');

  if (isMultiple && _targetIdsEliminar.length > 1) {
    if (modalTitulo) modalTitulo.textContent = `Eliminar ${_targetIdsEliminar.length} Fichas Seleccionadas`;
    if (msgP) {
      msgP.innerHTML = `¿Está seguro de que desea eliminar permanentemente las <strong>${_targetIdsEliminar.length} fichas clínicas seleccionadas</strong>?`;
    }
    if (advSpan) {
      advSpan.textContent = `Esta acción es definitiva e irreversible. Se borrarán permanentemente los antecedentes, exámenes y respuestas de las ${_targetIdsEliminar.length} fichas seleccionadas.`;
    }
  } else {
    const singleId = _targetIdsEliminar[0];
    if (modalTitulo) modalTitulo.textContent = 'Eliminar Ficha Clínica';
    let nombreMostrar = pacienteNombre;
    if (!nombreMostrar && typeof pacientes !== 'undefined' && Array.isArray(pacientes)) {
      const pFound = pacientes.find(p => String(p.id) === String(singleId));
      if (pFound) nombreMostrar = pFound.nombre;
    }
    if (msgP) {
      msgP.innerHTML = `¿Está seguro de que desea eliminar la ficha clínica de <strong style="color: #0f172a;">${nombreMostrar || 'este paciente'}</strong>${codigo ? ` (Código: #${codigo})` : ''}?`;
    }
    if (advSpan) {
      advSpan.textContent = 'Esta acción es definitiva. Se borrarán permanentemente los antecedentes, exámenes y respuestas de la ficha.';
    }
  }

  const pwdInput = document.getElementById('deleteModalPassword');
  if (pwdInput) pwdInput.value = '';

  const errDiv = document.getElementById('deleteModalError');
  if (errDiv) {
    errDiv.style.display = 'none';
    errDiv.textContent = '';
  }

  const btnConfirm = document.getElementById('btnConfirmarEliminarFicha');
  if (btnConfirm) {
    btnConfirm.disabled = false;
    btnConfirm.textContent = isMultiple && _targetIdsEliminar.length > 1
      ? `Eliminar (${_targetIdsEliminar.length}) definitivamente`
      : 'Eliminar definitivamente';
  }

  modal.style.display = 'flex';
  setTimeout(() => pwdInput && pwdInput.focus(), 80);
}

/**
 * Disparador para la acción de selección múltiple desde la barra de herramientas
 */
function solicitarEliminarSeleccionados() {
  if (typeof seleccionados === 'undefined' || !seleccionados || seleccionados.size === 0) {
    alert('Por favor seleccione al menos una ficha para eliminar.');
    return;
  }
  solicitarEliminarFicha(Array.from(seleccionados));
}

function cerrarModalEliminarFicha() {
  const modal = document.getElementById('modalEliminarFicha');
  if (modal) modal.style.display = 'none';
  _targetIdsEliminar = [];
}

async function ejecutarEliminacionFicha() {
  if (!_targetIdsEliminar || _targetIdsEliminar.length === 0) return;

  const pwdInput = document.getElementById('deleteModalPassword');
  const errDiv = document.getElementById('deleteModalError');
  const btnConfirm = document.getElementById('btnConfirmarEliminarFicha');

  const password = pwdInput ? pwdInput.value.trim() : '';
  if (!password) {
    if (errDiv) {
      errDiv.textContent = 'Debe ingresar su contraseña para confirmar la eliminación.';
      errDiv.style.display = 'block';
    }
    if (pwdInput) pwdInput.focus();
    return;
  }

  if (btnConfirm) {
    btnConfirm.disabled = true;
    btnConfirm.textContent = 'Verificando y eliminando...';
  }

  try {
    const res = await fetch('/clinical/api/ficha/eliminar/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfTokenEliminar()
      },
      body: JSON.stringify({
        patient_ids: _targetIdsEliminar,
        password: password
      })
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      if (errDiv) {
        errDiv.textContent = data.error || 'Contraseña incorrecta o error al eliminar.';
        errDiv.style.display = 'block';
      }
      if (btnConfirm) {
        btnConfirm.disabled = false;
        btnConfirm.textContent = 'Eliminar definitivamente';
      }
      if (pwdInput) pwdInput.select();
      return;
    }

    // Éxito: cerrar modal
    const eliminadosSet = new Set((data.deleted_ids || _targetIdsEliminar).map(x => String(x)));
    cerrarModalEliminarFicha();

    // Si estamos en la página del formulario / ficha médica, regresar al listado
    if (window.location.pathname.includes('/clinical/formulario/')) {
      alert(data.message || 'Ficha clínica eliminada exitosamente.');
      window.location.href = '/clinical/listado/';
      return;
    }

    // Si estamos en el listado general de pacientes
    if (typeof pacientes !== 'undefined' && Array.isArray(pacientes)) {
      pacientes = pacientes.filter(p => !eliminadosSet.has(String(p.id)));
      if (typeof seleccionados !== 'undefined') {
        eliminadosSet.forEach(id => {
          seleccionados.delete(id);
          seleccionados.delete(Number(id));
        });
      }
      if (typeof volverAListadoPacientes === 'function') {
        volverAListadoPacientes();
      }
      if (typeof renderPacientesTabla === 'function') {
        renderPacientesTabla();
      }
      if (typeof actualizarStatsCards === 'function') {
        actualizarStatsCards();
      }
      const filtrados = typeof obtenerPacientesFiltrados === 'function' ? obtenerPacientesFiltrados() : pacientes;
      if (typeof actualizarEstadoSeleccion === 'function') {
        actualizarEstadoSeleccion(filtrados);
      }
    }

    // Notificación flotante
    mostrarToastEliminacion(data.message || 'Fichas clínicas eliminadas.');

  } catch (err) {
    if (errDiv) {
      errDiv.textContent = 'Error de conexión: ' + err.message;
      errDiv.style.display = 'block';
    }
    if (btnConfirm) {
      btnConfirm.disabled = false;
      btnConfirm.textContent = 'Eliminar definitivamente';
    }
  }
}

function mostrarToastEliminacion(msg) {
  let toast = document.getElementById('toastFichaEliminada');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'toastFichaEliminada';
    toast.style.position = 'fixed';
    toast.style.bottom = '24px';
    toast.style.right = '24px';
    toast.style.background = '#0f172a';
    toast.style.color = '#ffffff';
    toast.style.padding = '12px 20px';
    toast.style.borderRadius = '8px';
    toast.style.boxShadow = '0 10px 15px -3px rgba(0, 0, 0, 0.3)';
    toast.style.fontSize = '0.86rem';
    toast.style.fontWeight = '600';
    toast.style.zIndex = '10000';
    toast.style.transition = 'all 0.3s ease';
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.style.opacity = '1';
  toast.style.transform = 'translateY(0)';
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
  }, 3500);
}
