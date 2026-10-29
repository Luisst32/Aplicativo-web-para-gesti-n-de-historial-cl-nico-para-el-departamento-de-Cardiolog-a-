/**
 * ELIMINAR_FICHA.JS
 * Lógica transversal para la eliminación protegida por contraseña de Fichas Clínicas.
 */

let _targetPacienteIdEliminar = null;

function getCsrfTokenEliminar() {
  const cookieVal = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1];
  if (cookieVal) return cookieVal;
  const inputEl = document.querySelector('[name=csrfmiddlewaretoken]');
  return inputEl ? inputEl.value : '';
}

function solicitarEliminarFicha(pacienteId, pacienteNombre, codigo) {
  const modal = document.getElementById('modalEliminarFicha');
  if (!modal) return;

  _targetPacienteIdEliminar = pacienteId;

  const lblNombre = document.getElementById('deleteModalPacienteNombre');
  if (lblNombre) {
    lblNombre.textContent = pacienteNombre || (codigo ? `Paciente Código #${codigo}` : 'este paciente');
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
    btnConfirm.textContent = 'Eliminar definitivamente';
  }

  modal.style.display = 'flex';
  setTimeout(() => pwdInput && pwdInput.focus(), 80);
}

function cerrarModalEliminarFicha() {
  const modal = document.getElementById('modalEliminarFicha');
  if (modal) modal.style.display = 'none';
  _targetPacienteIdEliminar = null;
}

async function ejecutarEliminacionFicha() {
  if (!_targetPacienteIdEliminar) return;

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
        patient_id: _targetPacienteIdEliminar,
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
    const idEliminado = _targetPacienteIdEliminar;
    cerrarModalEliminarFicha();

    // Si estamos en la página del formulario / ficha médica, regresar al listado
    if (window.location.pathname.includes('/clinical/formulario/')) {
      alert(data.message || 'Ficha clínica eliminada exitosamente.');
      window.location.href = '/clinical/listado/';
      return;
    }

    // Si estamos en el listado general de pacientes
    if (typeof pacientes !== 'undefined' && Array.isArray(pacientes)) {
      pacientes = pacientes.filter(p => String(p.id) !== String(idEliminado));
      if (typeof seleccionados !== 'undefined') {
        seleccionados.delete(String(idEliminado));
        seleccionados.delete(Number(idEliminado));
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
    }

    // Notificación flotante
    mostrarToastEliminacion(data.message || 'Ficha clínica eliminada.');

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
