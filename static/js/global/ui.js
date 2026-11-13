/**
 * UI.JS
 * Comportamientos de interfaz compartidos: inicialización del menú de usuario,
 * modal universal reutilizable (Mi Perfil, Password, Ajustes), notificaciones (toasts)
 * y diálogos de confirmación institucional.
 */

// Configuración o datos de usuario por defecto
const USUARIO_DEFAULT = {
  nombre: 'Admin UNEMI',
  rol: 'Administrador',
  correo: 'admin@cardiounemi.edu.ec'
};

document.addEventListener('DOMContentLoaded', () => {
  initUserMenu();
  initModals();
  initChatbotVisibilityState();
});

/**
 * Obtener cookie por nombre (CSRF Token de Django)
 */
function getCsrfToken() {
  if (typeof getCookie === 'function') {
    const t = getCookie('csrftoken');
    if (t) return t;
  }
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  if (match) return match[1];
  const inputEl = document.querySelector('[name=csrfmiddlewaretoken]');
  return inputEl ? inputEl.value : '';
}

/**
 * Controla la visibilidad inicial del chatbot según la configuración global
 */
function initChatbotVisibilityState() {
  if (window.CHATBOT_ENABLED === false) {
    const btnChat = document.getElementById('btn-flotante-chat');
    if (btnChat) btnChat.style.display = 'none';
  }
}

/**
 * Inicialización del menú de usuario en la barra superior / sidebar
 */
function initUserMenu() {
  const slot = document.querySelector('[data-user-menu]');
  if (!slot) return;

  const u = window.CURRENT_USER || USUARIO_DEFAULT;
  const iniciales = (typeof inicialesUsuario === 'function') 
    ? inicialesUsuario(u.nombre) 
    : (u.nombre ? u.nombre.split(' ').map(p => p[0]).slice(0, 2).join('').toUpperCase() : 'AU');

  slot.innerHTML = `
    <div class="user-menu" id="userMenu">
      <button type="button" class="user-menu-trigger" aria-haspopup="menu" aria-expanded="false" title="${escapeHtml(u.nombre)}">
        ${escapeHtml(iniciales)}
      </button>
      <div class="user-menu-panel" role="menu">
        <div class="user-menu-info">
          <span class="user-menu-avatar">${escapeHtml(iniciales)}</span>
          <span class="user-menu-texts">
            <span class="user-menu-info-name">${escapeHtml(u.nombre)}</span>
            <span class="user-menu-info-role">${escapeHtml(u.rol)}</span>
            <span class="user-menu-info-mail">${escapeHtml(u.correo)}</span>
          </span>
        </div>
        <a href="#" class="user-menu-option" role="menuitem" onclick="abrirModalPerfil(); return false;">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
          Mi perfil
        </a>
        <a href="#" class="user-menu-option" role="menuitem" onclick="abrirModalAjustes(); return false;">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
          Ajustes
        </a>
        <a href="/security/logout/" class="user-menu-option user-menu-logout" role="menuitem">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
          Cerrar sesión
        </a>
      </div>
    </div>
  `;

  const menu = document.getElementById('userMenu');
  const trigger = menu.querySelector('.user-menu-trigger');

  const alternar = (abrir) => {
    menu.classList.toggle('open', abrir);
    trigger.setAttribute('aria-expanded', abrir);
  };

  trigger.addEventListener('click', (e) => {
    e.stopPropagation();
    alternar(!menu.classList.contains('open'));
  });

  document.addEventListener('click', (e) => {
    if (!menu.contains(e.target)) alternar(false);
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') alternar(false);
  });
}

/**
 * =========================================================================
 * CONTROLADOR DEL MODAL UNIVERSAL REUTILIZABLE (AppModal)
 * Gestiona dinámicamente las vistas de "Mi Perfil", "Password" y "Ajustes".
 * =========================================================================
 */

function cerrarModalUniversal() {
  const modal = document.getElementById('modalUniversal');
  const card = document.getElementById('modalUniversalCard');
  if (modal) {
    modal.style.display = 'none';
    modal.classList.remove('active');
  }
  if (card) {
    card.style.maxWidth = '540px';
  }
}

function cambiarVistaModal(vista) {
  const vPerfil = document.getElementById('vistaModalPerfil');
  const vPassword = document.getElementById('vistaModalPassword');
  const vAjustes = document.getElementById('vistaModalAjustes');
  const vConfirmarPass = document.getElementById('vistaModalConfirmarPasswordPerfil');

  const titulo = document.getElementById('modalUniversalTitulo');
  const subtitulo = document.getElementById('modalUniversalSubtitulo');
  const icono = document.getElementById('modalUniversalIcono');
  const card = document.getElementById('modalUniversalCard');

  // Ajustar ancho panorámico para Ajustes y compacto para Perfil / Password
  if (card) {
    card.style.maxWidth = (vista === 'ajustes') ? '920px' : '540px';
  }

  // Ocultar todas las vistas
  if (vPerfil) vPerfil.style.display = 'none';
  if (vPassword) vPassword.style.display = 'none';
  if (vAjustes) vAjustes.style.display = 'none';
  if (vConfirmarPass) vConfirmarPass.style.display = 'none';

  // Limpiar mensajes previos
  ['perfilErrorMsg', 'perfilSuccessMsg', 'passwordErrorMsg', 'passwordSuccessMsg', 'ajustesErrorMsg', 'ajustesSuccessMsg'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
  });

  if (vista === 'perfil') {
    if (vPerfil) vPerfil.style.display = 'block';
    if (titulo) titulo.textContent = 'Mi Perfil';
    if (subtitulo) {
      subtitulo.textContent = 'Administración de cuenta de usuario';
      subtitulo.style.display = 'block';
    }
    if (icono) {
      icono.style.background = '#f1f5f9';
      icono.style.color = '#1b2a41';
      icono.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>`;
    }
    cargarDatosPerfilEnFormulario();
  } else if (vista === 'password') {
    if (vPassword) vPassword.style.display = 'block';
    if (titulo) titulo.textContent = 'Cambiar Contraseña';
    if (subtitulo) {
      subtitulo.textContent = 'Actualización de credenciales de acceso';
      subtitulo.style.display = 'block';
    }
    if (icono) {
      icono.style.background = '#f1f5f9';
      icono.style.color = '#1b2a41';
      icono.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>`;
    }
    // Limpiar y re-enmascarar inputs de password
    ['passActual', 'passNueva', 'passConfirmar'].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.value = '';
        if (el.dataset.secretInput === 'true') el.classList.add('masked-secret-input');
      }
    });
  } else if (vista === 'ajustes') {
    if (vAjustes) vAjustes.style.display = 'block';
    if (titulo) titulo.textContent = 'Ajustes del Sistema & Credenciales de APIs';
    if (subtitulo) {
      subtitulo.textContent = 'Configuración general de IA, parámetros clínicos e integraciones cloud.';
      subtitulo.style.display = 'block';
    }
    if (icono) {
      icono.style.background = '#f1f5f9';
      icono.style.color = '#1b2a41';
      icono.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>`;
    }
    cambiarSubpestanaAjustes('general');
    cargarAjustesSistema();
  }
}

function abrirModalUniversal(vista = 'perfil') {
  const modal = document.getElementById('modalUniversal');
  const card = document.getElementById('modalUniversalCard');
  if (!modal) return;
  if (card) {
    card.style.maxWidth = (vista === 'ajustes') ? '920px' : '540px';
  }
  modal.style.display = 'flex';
  modal.classList.add('active');
  cambiarVistaModal(vista);
}

function abrirModalPerfil() {
  abrirModalUniversal('perfil');
}

function abrirModalPassword() {
  abrirModalUniversal('password');
}

function abrirModalAjustes() {
  abrirModalUniversal('ajustes');
}

/**
 * Carga los datos del usuario actual en el formulario de Mi Perfil
 */
function cargarDatosPerfilEnFormulario() {
  const u = window.CURRENT_USER || USUARIO_DEFAULT;
  const elNombre = document.getElementById('perfilHeaderNombre');
  const elRol = document.getElementById('perfilHeaderRol');
  const elEmail = document.getElementById('perfilHeaderEmail');
  const elAvatar = document.getElementById('perfilAvatarIniciales');

  if (elNombre) elNombre.textContent = u.nombre || '';
  if (elRol) elRol.textContent = u.rol || 'Usuario';
  if (elEmail) elEmail.textContent = u.correo || '';
  if (elAvatar) {
    elAvatar.textContent = (typeof inicialesUsuario === 'function') 
      ? inicialesUsuario(u.nombre) 
      : (u.nombre ? u.nombre.split(' ').map(p => p[0]).slice(0, 2).join('').toUpperCase() : 'AU');
  }

  // Prellenar inputs
  const inFirst = document.getElementById('perfilFirstName');
  const inLast = document.getElementById('perfilLastName');
  const inSecondLast = document.getElementById('perfilSecondLastName');
  const inUsername = document.getElementById('perfilUsername');
  const inEmail = document.getElementById('perfilEmail');
  const inPassConfirm = document.getElementById('perfilPasswordConfirm');

  if (inFirst) inFirst.value = u.first_name || '';
  if (inLast) inLast.value = u.last_name || '';
  if (inSecondLast) inSecondLast.value = u.second_last_name || '';
  if (inUsername) inUsername.value = u.username || '';
  if (inEmail) inEmail.value = u.correo || '';
  if (inPassConfirm) inPassConfirm.value = '';

  // Consultar datos actualizados del servidor
  fetch('/security/api/profile/', {
    headers: { 'Accept': 'application/json' }
  })
  .then(r => r.json())
  .then(data => {
    if (data.status === 'success' && data.user) {
      const usr = data.user;
      if (inFirst) inFirst.value = usr.first_name || '';
      if (inLast) inLast.value = usr.last_name || '';
      if (inSecondLast) inSecondLast.value = usr.second_last_name || '';
      if (inUsername) inUsername.value = usr.username || '';
      if (inEmail) inEmail.value = usr.email || '';
      if (elNombre) elNombre.textContent = usr.full_name || '';
      if (elEmail) elEmail.textContent = usr.email || '';
    }
  })
  .catch(err => console.error('Error cargando perfil:', err));
}

/**
 * Guardar edición de perfil con confirmación obligatoria de contraseña
 */
/**
 * Paso 1: Al hacer clic en "Guardar cambios" en el perfil,
 * valida los datos del formulario y solicita la contraseña actual.
 */
function solicitarConfirmacionPasswordPerfil(event) {
  if (event) event.preventDefault();

  const errEl = document.getElementById('perfilErrorMsg');
  if (errEl) errEl.style.display = 'none';

  const first_name = document.getElementById('perfilFirstName')?.value.trim();
  const last_name = document.getElementById('perfilLastName')?.value.trim();
  const email = document.getElementById('perfilEmail')?.value.trim();

  if (!first_name || !last_name) {
    if (errEl) {
      errEl.textContent = 'Por favor ingrese nombres y primer apellido obligatorios.';
      errEl.style.display = 'block';
    }
    return;
  }

  if (!email || !email.includes('@')) {
    if (errEl) {
      errEl.textContent = 'Ingrese un correo electrónico válido.';
      errEl.style.display = 'block';
    }
    return;
  }

  // Transicionar al paso de confirmación de contraseña para Perfil
  solicitarConfirmacionPasswordPerfil();
}

// =========================================================================
// MODO DE PRIVACIDAD Y PROTECCIÓN DE DATOS SENSIBLES
// =========================================================================

let accionPendientePassword = null; // { origen: 'perfil'|'privacidad', meta: any }

function esModoPrivacidadActivo() {
  try {
    return localStorage.getItem('cardio_privacy_mode') === 'true';
  } catch (e) {
    return false;
  }
}

function setModoPrivacidad(activo) {
  try {
    localStorage.setItem('cardio_privacy_mode', activo ? 'true' : 'false');
  } catch (e) {}
  actualizarBadgeSwitchPrivacidad(activo);
  window.dispatchEvent(new CustomEvent('cardio_privacy_mode_changed', { detail: { enabled: activo } }));
}

function censurarCedula(cedula) {
  if (!cedula) return '09******00';
  const c = String(cedula).trim();
  if (c.length <= 4) return '******';
  return c.slice(0, 2) + '******' + c.slice(-2);
}

function censurarNombre(nombre, codigo) {
  if (esModoPrivacidadActivo()) {
    return `Paciente ${codigo || 'N/A'}`;
  }
  return nombre || 'Paciente';
}

function actualizarBadgeSwitchPrivacidad(activo) {
  const badge = document.getElementById('badgePrivacidadEstado');
  const slider = document.getElementById('sliderSwitchPrivacidad');
  const circulo = document.getElementById('circuloSwitchPrivacidad');
  const switchEl = document.getElementById('switchModoPrivacidad');

  if (switchEl) switchEl.checked = activo;

  if (badge) {
    badge.textContent = activo ? 'ACTIVO' : 'INACTIVO';
    badge.style.background = activo ? '#dcfce7' : '#f1f5f9';
    badge.style.color = activo ? '#15803d' : '#64748b';
  }
  if (slider) {
    slider.style.backgroundColor = activo ? '#166534' : '#cbd5e1';
  }
  if (circulo) {
    circulo.style.transform = activo ? 'translateX(22px)' : 'translateX(0)';
  }
}

function solicitarToggleModoPrivacidad(checkboxEl) {
  const targetChecked = checkboxEl.checked;
  // Revertir temporalmente el switch visual en DOM hasta autenticar con contraseña
  checkboxEl.checked = !targetChecked;

  accionPendientePassword = {
    origen: 'privacidad',
    targetChecked: targetChecked,
    checkboxEl: checkboxEl
  };

  // Reutilizar el modal universal de confirmación con contraseña
  const vAjustes = document.getElementById('vistaModalAjustes');
  const vConfirmar = document.getElementById('vistaModalConfirmarPasswordPerfil');
  const titleEl = document.getElementById('confirmPasswordModalTitle');
  const descEl = document.getElementById('confirmPasswordModalDesc');
  const btnTextEl = document.getElementById('btnEjecutarPasswordTexto');
  const passInp = document.getElementById('perfilPasswordConfirmModal');
  const errPass = document.getElementById('confirmPasswordErrorMsg');
  const card = document.getElementById('modalUniversalCard');

  if (card) card.style.maxWidth = '520px';
  if (vAjustes) vAjustes.style.display = 'none';
  if (vConfirmar) vConfirmar.style.display = 'block';

  if (titleEl) {
    titleEl.textContent = targetChecked ? 'Activar Modo de Privacidad' : 'Desactivar Modo de Privacidad';
  }
  if (descEl) {
    descEl.textContent = targetChecked
      ? 'Por protección de datos, ingrese su contraseña actual para anonimizar los pacientes en pantalla y censurar datos sensibles.'
      : 'Ingrese su contraseña actual para desactivar el modo de privacidad y mostrar los datos identificativos del paciente.';
  }
  if (btnTextEl) {
    btnTextEl.textContent = targetChecked ? 'Autorizar y Activar' : 'Autorizar y Desactivar';
  }

  if (errPass) errPass.style.display = 'none';
  if (passInp) {
    passInp.value = '';
    if (passInp.dataset.secretInput === 'true') passInp.classList.add('masked-secret-input');
    setTimeout(() => passInp.focus(), 100);
  }
}

function cancelarAccionConPassword() {
  const vConfirmar = document.getElementById('vistaModalConfirmarPasswordPerfil');
  if (vConfirmar) vConfirmar.style.display = 'none';

  if (accionPendientePassword && accionPendientePassword.origen === 'privacidad') {
    const vAjustes = document.getElementById('vistaModalAjustes');
    const card = document.getElementById('modalUniversalCard');
    if (card) card.style.maxWidth = '920px';
    if (vAjustes) vAjustes.style.display = 'block';
    actualizarBadgeSwitchPrivacidad(esModoPrivacidadActivo());
  } else {
    // Por defecto vuelve al perfil
    const vPerfil = document.getElementById('vistaModalPerfil');
    const card = document.getElementById('modalUniversalCard');
    if (card) card.style.maxWidth = '540px';
    if (vPerfil) vPerfil.style.display = 'block';
  }
  accionPendientePassword = null;
}

function volverAFormularioPerfil() {
  cancelarAccionConPassword();
}

function solicitarConfirmacionPasswordPerfil(event) {
  if (event) event.preventDefault();
  accionPendientePassword = { origen: 'perfil' };

  const vPerfil = document.getElementById('vistaModalPerfil');
  const vConfirmar = document.getElementById('vistaModalConfirmarPasswordPerfil');
  const titleEl = document.getElementById('confirmPasswordModalTitle');
  const descEl = document.getElementById('confirmPasswordModalDesc');
  const btnTextEl = document.getElementById('btnEjecutarPasswordTexto');
  const passInp = document.getElementById('perfilPasswordConfirmModal');
  const errPass = document.getElementById('confirmPasswordErrorMsg');
  const card = document.getElementById('modalUniversalCard');

  if (card) card.style.maxWidth = '540px';
  if (vPerfil) vPerfil.style.display = 'none';
  if (vConfirmar) vConfirmar.style.display = 'block';

  if (titleEl) titleEl.textContent = 'Confirmar actualización de datos';
  if (descEl) descEl.textContent = 'Por seguridad institucional, ingrese su contraseña actual para autorizar la actualización de sus datos.';
  if (btnTextEl) btnTextEl.textContent = 'Confirmar y Guardar';

  if (errPass) errPass.style.display = 'none';
  if (passInp) {
    passInp.value = '';
    if (passInp.dataset.secretInput === 'true') passInp.classList.add('masked-secret-input');
    setTimeout(() => passInp.focus(), 100);
  }
}

async function ejecutarAccionConPassword(event) {
  if (event) event.preventDefault();

  const errPass = document.getElementById('confirmPasswordErrorMsg');
  const btnEjecutar = document.getElementById('btnEjecutarGuardarPerfil');
  const passInp = document.getElementById('perfilPasswordConfirmModal');
  const password = passInp?.value;

  if (errPass) errPass.style.display = 'none';

  if (!password) {
    if (errPass) {
      errPass.textContent = 'Debe ingresar su contraseña actual para autorizar la acción.';
      errPass.style.display = 'block';
    }
    return;
  }

  // Caso 1: Modo de Privacidad
  if (accionPendientePassword && accionPendientePassword.origen === 'privacidad') {
    if (btnEjecutar) {
      btnEjecutar.disabled = true;
      btnEjecutar.textContent = 'Verificando...';
    }

    try {
      const res = await fetch('/security/api/verify-password/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ password })
      });
      const data = await res.json();

      if (res.ok && data.status === 'success') {
        const targetChecked = accionPendientePassword.targetChecked;
        setModoPrivacidad(targetChecked);
        showToast(`Modo de privacidad ${targetChecked ? 'activado' : 'desactivado'} exitosamente.`, 'success');

        if (passInp) passInp.value = '';
        cancelarAccionConPassword(); // Vuelve a Ajustes con switch actualizado
      } else {
        if (errPass) {
          errPass.textContent = data.message || 'Contraseña incorrecta. Intente nuevamente.';
          errPass.style.display = 'block';
        }
        if (passInp) {
          passInp.select();
          passInp.focus();
        }
      }
    } catch (err) {
      console.error('Error verificando contraseña para privacidad:', err);
      if (errPass) {
        errPass.textContent = 'Error de conexión con el servidor.';
        errPass.style.display = 'block';
      }
    } finally {
      if (btnEjecutar) {
        btnEjecutar.disabled = false;
        const btnTextEl = document.getElementById('btnEjecutarPasswordTexto');
        btnEjecutar.textContent = btnTextEl ? btnTextEl.textContent : 'Confirmar';
      }
    }
    return;
  }

  // Caso 2: Guardado de Perfil (código original)
  await ejecutarGuardadoPerfilConPassword(event);
}

/**
 * Paso 2: Ejecuta el guardado enviando la contraseña actual
 */
async function ejecutarGuardadoPerfilConPassword(event) {
  if (event) event.preventDefault();

  const errPass = document.getElementById('confirmPasswordErrorMsg');
  const btnEjecutar = document.getElementById('btnEjecutarGuardarPerfil');
  const passInp = document.getElementById('perfilPasswordConfirmModal');
  const current_password = passInp?.value;

  if (errPass) errPass.style.display = 'none';

  if (!current_password) {
    if (errPass) {
      errPass.textContent = 'Debe ingresar su contraseña actual para autorizar los cambios.';
      errPass.style.display = 'block';
    }
    return;
  }

  const first_name = document.getElementById('perfilFirstName')?.value.trim();
  const last_name = document.getElementById('perfilLastName')?.value.trim();
  const second_last_name = document.getElementById('perfilSecondLastName')?.value.trim();
  const email = document.getElementById('perfilEmail')?.value.trim();

  if (btnEjecutar) {
    btnEjecutar.disabled = true;
    btnEjecutar.textContent = 'Verificando...';
  }

  try {
    const res = await fetch('/security/api/profile/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      },
      body: JSON.stringify({
        first_name,
        last_name,
        second_last_name,
        email,
        current_password
      })
    });

    const data = await res.json();

    if (res.ok && data.status === 'success') {
      // Actualizar estado en memoria y DOM
      if (window.CURRENT_USER && data.user) {
        window.CURRENT_USER.nombre = data.user.full_name;
        window.CURRENT_USER.correo = data.user.email;
        window.CURRENT_USER.first_name = data.user.first_name;
        window.CURRENT_USER.last_name = data.user.last_name;
        window.CURRENT_USER.second_last_name = data.user.second_last_name;
      }

      // Re-renderizar slot de menú de usuario
      initUserMenu();

      showToast('Perfil actualizado correctamente.', 'success');
      if (passInp) passInp.value = '';

      cerrarModalUniversal();
    } else {
      if (errPass) {
        errPass.textContent = data.message || 'Contraseña incorrecta. Verifique sus credenciales.';
        errPass.style.display = 'block';
      }
      if (passInp) {
        passInp.select();
        passInp.focus();
      }
    }
  } catch (err) {
    console.error('Error guardando perfil:', err);
    if (errPass) {
      errPass.textContent = 'Error de conexión al guardar los datos.';
      errPass.style.display = 'block';
    }
  } finally {
    if (btnEjecutar) {
      btnEjecutar.disabled = false;
      btnEjecutar.textContent = 'Confirmar y Guardar';
    }
  }
}

/**
 * Guardar nueva contraseña
 */
async function guardarNuevaPassword(event) {
  if (event) event.preventDefault();

  const errEl = document.getElementById('passwordErrorMsg');
  const succEl = document.getElementById('passwordSuccessMsg');
  const btnGuardar = document.getElementById('btnGuardarPassword');

  if (errEl) errEl.style.display = 'none';
  if (succEl) succEl.style.display = 'none';

  const old_password = document.getElementById('passActual')?.value;
  const new_password = document.getElementById('passNueva')?.value;
  const confirm_password = document.getElementById('passConfirmar')?.value;

  if (!old_password || !new_password || !confirm_password) {
    if (errEl) {
      errEl.textContent = 'Complete todos los campos de contraseña.';
      errEl.style.display = 'block';
    }
    return;
  }

  if (new_password.length < 8) {
    if (errEl) {
      errEl.textContent = 'La nueva contraseña debe tener al menos 8 caracteres.';
      errEl.style.display = 'block';
    }
    return;
  }

  if (new_password !== confirm_password) {
    if (errEl) {
      errEl.textContent = 'Las nuevas contraseñas no coinciden.';
      errEl.style.display = 'block';
    }
    return;
  }

  if (btnGuardar) {
    btnGuardar.disabled = true;
    btnGuardar.textContent = 'Actualizando...';
  }

  try {
    const res = await fetch('/security/api/change-password/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      },
      body: JSON.stringify({
        old_password,
        new_password,
        confirm_password
      })
    });

    const data = await res.json();

    if (res.ok && data.status === 'success') {
      if (succEl) {
        succEl.textContent = data.message || 'Contraseña actualizada con éxito.';
        succEl.style.display = 'block';
      }
      showToast('Contraseña actualizada exitosamente.', 'success');

      ['passActual', 'passNueva', 'passConfirmar'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
      });

      setTimeout(() => {
        cerrarModalUniversal();
      }, 1300);
    } else {
      if (errEl) {
        errEl.textContent = data.message || 'Error al cambiar la contraseña.';
        errEl.style.display = 'block';
      }
    }
  } catch (err) {
    console.error('Error cambiando contraseña:', err);
    if (errEl) {
      errEl.textContent = 'Error de conexión. Intente nuevamente.';
      errEl.style.display = 'block';
    }
  } finally {
    if (btnGuardar) {
      btnGuardar.disabled = false;
      btnGuardar.textContent = 'Actualizar contraseña';
    }
  }
}

/**
 * =========================================================================
 * AJUSTES GLOBALES DEL SISTEMA & GESTIÓN DE APIS (PANORÁMICO)
 * =========================================================================
 */

function cambiarSubpestanaAjustes(subpestana) {
  const btnGeneral = document.getElementById('tabBtnAjustesGeneral');
  const btnApis = document.getElementById('tabBtnAjustesApis');
  const secGeneral = document.getElementById('subseccionAjustesGeneral');
  const secApis = document.getElementById('subseccionAjustesApis');

  if (subpestana === 'general') {
    if (btnGeneral) {
      btnGeneral.style.background = '#1b2a41';
      btnGeneral.style.color = '#ffffff';
      btnGeneral.style.borderColor = '#1b2a41';
      btnGeneral.style.fontWeight = '700';
    }
    if (btnApis) {
      btnApis.style.background = '#ffffff';
      btnApis.style.color = '#64748b';
      btnApis.style.borderColor = '#cbd5e1';
      btnApis.style.fontWeight = '600';
    }
    if (secGeneral) secGeneral.style.display = 'block';
    if (secApis) secApis.style.display = 'none';
  } else if (subpestana === 'apis') {
    if (btnApis) {
      btnApis.style.background = '#1b2a41';
      btnApis.style.color = '#ffffff';
      btnApis.style.borderColor = '#1b2a41';
      btnApis.style.fontWeight = '700';
    }
    if (btnGeneral) {
      btnGeneral.style.background = '#ffffff';
      btnGeneral.style.color = '#64748b';
      btnGeneral.style.borderColor = '#cbd5e1';
      btnGeneral.style.fontWeight = '600';
    }
    if (secGeneral) secGeneral.style.display = 'none';
    if (secApis) secApis.style.display = 'block';
  }
}

function seleccionarProveedorIA(provider) {
  const radioGemini = document.getElementById('radioProviderGemini');
  const radioOpenAI = document.getElementById('radioProviderOpenAI');
  const radioClaude = document.getElementById('radioProviderClaude');

  const cardGemini = document.getElementById('cardSelectorGemini');
  const cardOpenAI = document.getElementById('cardSelectorOpenAI');
  const cardClaude = document.getElementById('cardSelectorClaude');

  const items = [
    { key: 'gemini', radio: radioGemini, card: cardGemini },
    { key: 'openai', radio: radioOpenAI, card: cardOpenAI },
    { key: 'claude', radio: radioClaude, card: cardClaude }
  ];

  items.forEach(item => {
    if (item.key === provider) {
      if (item.radio) item.radio.checked = true;
      if (item.card) {
        item.card.style.border = '2px solid #1b2a41';
        item.card.style.background = '#eff6ff';
        item.card.style.boxShadow = '0 2px 6px rgba(27, 42, 65, 0.12)';
      }
    } else {
      if (item.radio) item.radio.checked = false;
      if (item.card) {
        item.card.style.border = '2px solid #e2e8f0';
        item.card.style.background = '#ffffff';
        item.card.style.boxShadow = 'none';
      }
    }
  });
}

function filtrarTarjetasApi(apiFiltro, btnEl) {
  const contenedorFiltros = document.getElementById('contenedorFiltrosApis');
  if (contenedorFiltros) {
    contenedorFiltros.querySelectorAll('.btn-filtro-api').forEach(btn => {
      btn.style.background = '#ffffff';
      btn.style.color = '#475569';
      btn.style.borderColor = '#e2e8f0';
      btn.style.fontWeight = '500';
    });
  }
  if (btnEl) {
    btnEl.style.background = '#1b2a41';
    btnEl.style.color = '#ffffff';
    btnEl.style.borderColor = '#1b2a41';
    btnEl.style.fontWeight = '600';
  }

  const mapa = {
    gemini: document.getElementById('cardApiGemini'),
    openai: document.getElementById('cardApiOpenAI'),
    claude: document.getElementById('cardApiClaude'),
    gmail: document.getElementById('cardApiGmail')
  };

  Object.keys(mapa).forEach(k => {
    const el = mapa[k];
    if (!el) return;
    if (apiFiltro === 'todas' || apiFiltro === k) {
      el.style.display = 'flex';
    } else {
      el.style.display = 'none';
    }
  });
}

function actualizarBadgeEstadoApi(badgeId, configurada, habilitada) {
  const badge = document.getElementById(badgeId);
  if (!badge) return;
  const isHab = typeof habilitada === 'undefined' ? true : Boolean(habilitada);
  if (!configurada) {
    badge.innerHTML = '<span style="width: 6px; height: 6px; border-radius: 50%; background: #94a3b8; display: inline-block;"></span>Sin configurar';
    badge.style.background = '#f8fafc';
    badge.style.color = '#64748b';
    badge.style.border = '1px solid #e2e8f0';
    badge.style.fontWeight = '500';
  } else if (!isHab) {
    badge.innerHTML = '<span style="width: 6px; height: 6px; border-radius: 50%; background: #f59e0b; display: inline-block;"></span>Deshabilitada';
    badge.style.background = '#fffbeb';
    badge.style.color = '#b45309';
    badge.style.border = '1px solid #fde68a';
    badge.style.fontWeight = '600';
  } else {
    badge.innerHTML = '<span style="width: 6px; height: 6px; border-radius: 50%; background: #16a34a; display: inline-block;"></span>Habilitada';
    badge.style.background = '#f0fdf4';
    badge.style.color = '#166534';
    badge.style.border = '1px solid #bbf7d0';
    badge.style.fontWeight = '600';
  }
}

/**
 * Cargar configuración global del sistema y credenciales de APIs
 */
async function cargarAjustesSistema() {
  // Inicializar estado del Modo de Privacidad en Ajustes
  actualizarBadgeSwitchPrivacidad(esModoPrivacidadActivo());

  const switchChatbot = document.getElementById('switchChatbotActivo');

  // Gemini
  const inputGeminiKey = document.getElementById('inputAjusteApiKey');
  const selectGeminiModel = document.getElementById('selectAjusteModelo');
  const switchGeminiEnabled = document.getElementById('switchGeminiEnabled');

  // OpenAI
  const inputOpenAIKey = document.getElementById('inputOpenAIApiKey');
  const selectOpenAIModel = document.getElementById('selectOpenAIModelo');
  const switchOpenAIEnabled = document.getElementById('switchOpenAIEnabled');

  // Claude
  const inputClaudeKey = document.getElementById('inputClaudeApiKey');
  const selectClaudeModel = document.getElementById('selectClaudeModelo');
  const switchClaudeEnabled = document.getElementById('switchClaudeEnabled');

  // Gmail
  const inputGmailSender = document.getElementById('inputGmailSenderEmail');
  const inputGmailClientId = document.getElementById('inputGmailClientId');
  const inputGmailSecret = document.getElementById('inputGmailClientSecret');
  const inputGmailRefresh = document.getElementById('inputGmailRefreshToken');
  const inputGmailRedirect = document.getElementById('inputGmailRedirectUri');
  const switchGmailEnabled = document.getElementById('switchGmailEnabled');

  try {
    const res = await fetch(`/security/api/settings/?_=${escapeHtml(Date.now())}`, {
      headers: { 'Accept': 'application/json' },
      cache: 'no-store'
    });
    const data = await res.json();

    if (res.ok && data.status === 'success') {
      // 1. Chatbot Master
      const activo = Boolean(data.chatbot_enabled);
      if (switchChatbot) {
        switchChatbot.checked = activo;
        actualizarBadgeSwitchChatbot(activo);
      }

      // 2. Active LLM Provider
      const activeProvider = data.active_llm_provider || 'gemini';
      seleccionarProveedorIA(activeProvider);

      // 3. Gemini
      if (selectGeminiModel && data.gemini_model) {
        selectGeminiModel.value = data.gemini_model;
      }
      if (inputGeminiKey) {
        inputGeminiKey.value = data.gemini_api_key_masked || data.api_key_masked || '';
      }
      window._geminiConfigurada = Boolean(data.gemini_api_key_configured);
      const geminiHab = Boolean(data.gemini_enabled);
      if (switchGeminiEnabled) {
        switchGeminiEnabled.checked = geminiHab;
      }
      actualizarBadgeEstadoApi('badgeEstadoGemini', window._geminiConfigurada, geminiHab);

      // 4. OpenAI
      if (selectOpenAIModel && data.openai_model) {
        selectOpenAIModel.value = data.openai_model;
      }
      if (inputOpenAIKey) {
        inputOpenAIKey.value = data.openai_api_key_masked || '';
      }
      window._openaiConfigurada = Boolean(data.openai_api_key_configured);
      const openaiHab = Boolean(data.openai_enabled);
      if (switchOpenAIEnabled) {
        switchOpenAIEnabled.checked = openaiHab;
      }
      actualizarBadgeEstadoApi('badgeEstadoOpenAI', window._openaiConfigurada, openaiHab);

      // 5. Claude
      if (selectClaudeModel && data.claude_model) {
        selectClaudeModel.value = data.claude_model;
      }
      if (inputClaudeKey) {
        inputClaudeKey.value = data.claude_api_key_masked || '';
      }
      window._claudeConfigurada = Boolean(data.claude_api_key_configured);
      const claudeHab = Boolean(data.claude_enabled);
      if (switchClaudeEnabled) {
        switchClaudeEnabled.checked = claudeHab;
      }
      actualizarBadgeEstadoApi('badgeEstadoClaude', window._claudeConfigurada, claudeHab);

      // 6. Gmail SMTP
      if (inputGmailSender) inputGmailSender.value = data.gmail_sender_email || '';
      if (inputGmailSecret) inputGmailSecret.value = data.gmail_secret_masked || '';
      window._gmailConfigurada = Boolean(data.gmail_sender_email && data.gmail_secret_configured);
      const gmailHab = Boolean(data.gmail_api_enabled);
      if (switchGmailEnabled) {
        switchGmailEnabled.checked = gmailHab;
      }
      actualizarBadgeEstadoApi('badgeEstadoGmail', window._gmailConfigurada, gmailHab);

      // Listeners de cambio en tiempo real para badges
      if (switchGeminiEnabled && !switchGeminiEnabled._listenerAdded) {
        switchGeminiEnabled._listenerAdded = true;
        switchGeminiEnabled.addEventListener('change', () => {
          actualizarBadgeEstadoApi('badgeEstadoGemini', window._geminiConfigurada, switchGeminiEnabled.checked);
        });
      }
      if (switchOpenAIEnabled && !switchOpenAIEnabled._listenerAdded) {
        switchOpenAIEnabled._listenerAdded = true;
        switchOpenAIEnabled.addEventListener('change', () => {
          actualizarBadgeEstadoApi('badgeEstadoOpenAI', window._openaiConfigurada, switchOpenAIEnabled.checked);
        });
      }
      if (switchClaudeEnabled && !switchClaudeEnabled._listenerAdded) {
        switchClaudeEnabled._listenerAdded = true;
        switchClaudeEnabled.addEventListener('change', () => {
          actualizarBadgeEstadoApi('badgeEstadoClaude', window._claudeConfigurada, switchClaudeEnabled.checked);
        });
      }
      if (switchGmailEnabled && !switchGmailEnabled._listenerAdded) {
        switchGmailEnabled._listenerAdded = true;
        switchGmailEnabled.addEventListener('change', () => {
          actualizarBadgeEstadoApi('badgeEstadoGmail', window._gmailConfigurada, switchGmailEnabled.checked);
        });
      }
    }
  } catch (err) {
    console.error('Error cargando ajustes:', err);
  }
}

function actualizarBadgeSwitchChatbot(activo) {
  const badge = document.getElementById('badgeChatbotEstado');
  const slider = document.getElementById('sliderSwitchChatbot');
  const circulo = document.getElementById('circuloSwitchChatbot');

  if (badge) {
    badge.textContent = activo ? 'ACTIVO' : 'DESACTIVADO';
    badge.style.background = activo ? '#dcfce7' : '#fee2e2';
    badge.style.color = activo ? '#15803d' : '#b91c1c';
  }
  if (slider) {
    slider.style.backgroundColor = activo ? '#3aa0ff' : '#cbd5e1';
  }
  if (circulo) {
    circulo.style.transform = activo ? 'translateX(22px)' : 'translateX(0)';
  }
}

function limpiarApiKeyAjustes() {
  const input = document.getElementById('inputAjusteApiKey');
  if (input) {
    input.value = '';
    input.placeholder = 'Pegue su nueva clave de Gemini aquí...';
    input.focus();
  }
}

function limpiarOpenAIApiKey() {
  const input = document.getElementById('inputOpenAIApiKey');
  if (input) {
    input.value = '';
    input.placeholder = 'sk-proj-...';
    input.focus();
  }
}

function limpiarClaudeApiKey() {
  const input = document.getElementById('inputClaudeApiKey');
  if (input) {
    input.value = '';
    input.placeholder = 'sk-ant-api03-...';
    input.focus();
  }
}

function limpiarGmailSecret() {
  const input = document.getElementById('inputGmailClientSecret');
  if (input) {
    input.value = '';
    input.placeholder = 'GOCSPX-...';
    input.focus();
  }
}

function limpiarGmailRefresh() {
  const input = document.getElementById('inputGmailRefreshToken');
  if (input) {
    input.value = '';
    input.placeholder = '1//04...';
    input.focus();
  }
}

/**
 * Guardar todos los ajustes del sistema y credenciales de APIs
 */
async function guardarAjustesSistema(event) {
  if (event) event.preventDefault();

  const errEl = document.getElementById('ajustesErrorMsg');
  const succEl = document.getElementById('ajustesSuccessMsg');
  const btnGuardar = document.getElementById('btnGuardarAjustes');

  if (errEl) errEl.style.display = 'none';
  if (succEl) succEl.style.display = 'none';

  // Recopilar valores
  const chatbot_enabled = document.getElementById('switchChatbotActivo')?.checked;
  const active_llm_provider = document.querySelector('input[name="radioActiveProvider"]:checked')?.value || 'gemini';

  // Gemini
  const gemini_api_key = document.getElementById('inputAjusteApiKey')?.value.trim();
  const gemini_model = document.getElementById('selectAjusteModelo')?.value;
  const gemini_enabled = document.getElementById('switchGeminiEnabled')?.checked;

  // OpenAI
  const openai_api_key = document.getElementById('inputOpenAIApiKey')?.value.trim();
  const openai_model = document.getElementById('selectOpenAIModelo')?.value;
  const openai_enabled = document.getElementById('switchOpenAIEnabled')?.checked;

  // Claude
  const claude_api_key = document.getElementById('inputClaudeApiKey')?.value.trim();
  const claude_model = document.getElementById('selectClaudeModelo')?.value;
  const claude_enabled = document.getElementById('switchClaudeEnabled')?.checked;

  // Gmail
  const gmail_sender_email = document.getElementById('inputGmailSenderEmail')?.value.trim();
  const gmail_client_secret = document.getElementById('inputGmailClientSecret')?.value.trim();
  const switchGmailEnabled = document.getElementById('switchGmailEnabled');
  const gmail_api_enabled = switchGmailEnabled ? switchGmailEnabled.checked : true;

  if (btnGuardar) {
    btnGuardar.disabled = true;
    btnGuardar.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin-icon" style="animation: spin 1s linear infinite;"><path d="M21 12a9 9 0 1 1-6.219-8.56"></path></svg>
      Guardando ajustes...
    `;
  }

  try {
    const payload = {
      chatbot_enabled,
      active_llm_provider,
      gemini_api_key,
      gemini_model,
      gemini_enabled,
      openai_api_key,
      openai_model,
      openai_enabled,
      claude_api_key,
      claude_model,
      claude_enabled,
      gmail_sender_email,
      gmail_client_secret,
      gmail_api_enabled
    };

    const res = await fetch('/security/api/settings/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      },
      body: JSON.stringify(payload)
    });

    const data = await res.json();

    if (res.ok && data.status === 'success') {
      // Actualizar estado en tiempo real en la interfaz
      window.CHATBOT_ENABLED = Boolean(data.chatbot_enabled);
      const btnFlotante = document.getElementById('btn-flotante-chat');
      if (btnFlotante) {
        btnFlotante.style.display = data.chatbot_enabled ? 'flex' : 'none';
      }

      // Sincronizar checkboxes con la respuesta real del servidor
      const sGemini = document.getElementById('switchGeminiEnabled');
      if (sGemini && typeof data.gemini_enabled !== 'undefined') sGemini.checked = Boolean(data.gemini_enabled);
      const sOpenAI = document.getElementById('switchOpenAIEnabled');
      if (sOpenAI && typeof data.openai_enabled !== 'undefined') sOpenAI.checked = Boolean(data.openai_enabled);
      const sClaude = document.getElementById('switchClaudeEnabled');
      if (sClaude && typeof data.claude_enabled !== 'undefined') sClaude.checked = Boolean(data.claude_enabled);
      const sGmail = document.getElementById('switchGmailEnabled');
      if (sGmail && typeof data.gmail_api_enabled !== 'undefined') sGmail.checked = Boolean(data.gmail_api_enabled);

      // Actualizar badges con estado y habilitación
      if (typeof data.gemini_api_key_configured !== 'undefined') {
        window._geminiConfigurada = Boolean(data.gemini_api_key_configured);
        actualizarBadgeEstadoApi('badgeEstadoGemini', window._geminiConfigurada, Boolean(data.gemini_enabled));
      }
      if (typeof data.openai_api_key_configured !== 'undefined') {
        window._openaiConfigurada = Boolean(data.openai_api_key_configured);
        actualizarBadgeEstadoApi('badgeEstadoOpenAI', window._openaiConfigurada, Boolean(data.openai_enabled));
      }
      if (typeof data.claude_api_key_configured !== 'undefined') {
        window._claudeConfigurada = Boolean(data.claude_api_key_configured);
        actualizarBadgeEstadoApi('badgeEstadoClaude', window._claudeConfigurada, Boolean(data.claude_enabled));
      }
      if (typeof data.gmail_secret_configured !== 'undefined') {
        window._gmailConfigurada = Boolean(data.gmail_secret_configured);
        actualizarBadgeEstadoApi('badgeEstadoGmail', window._gmailConfigurada, Boolean(data.gmail_api_enabled));
      }

      // Solo mantener la notificación flotante (toast) a la derecha
      showToast('Ajustes y credenciales de APIs guardados correctamente.', 'success');
      cerrarModalUniversal();
    } else {
      if (errEl) {
        errEl.textContent = data.message || 'Error al guardar los ajustes.';
        errEl.style.display = 'block';
      }
    }
  } catch (err) {
    console.error('Error guardando ajustes:', err);
    if (errEl) {
      errEl.textContent = 'Error de conexión con el servidor al guardar ajustes.';
      errEl.style.display = 'block';
    }
  } finally {
    if (btnGuardar) {
      btnGuardar.disabled = false;
      btnGuardar.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg>
        Guardar todos los ajustes
      `;
    }
  }
}

/**
 * Utilidad para alternar visibilidad de contraseña (eye toggle)
 */
function togglePasswordVisibility(inputId, btnEl) {
  const input = document.getElementById(inputId);
  if (!input) return;

  let revealed = false;
  if (input.dataset.secretInput === 'true') {
    const isMasked = input.classList.contains('masked-secret-input');
    input.classList.toggle('masked-secret-input', !isMasked);
    revealed = isMasked;
  } else {
    const isPass = input.type === 'password';
    input.type = isPass ? 'text' : 'password';
    revealed = isPass;
  }

  if (btnEl) {
    btnEl.innerHTML = revealed 
      ? `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>`
      : `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>`;
  }
}

/**
 * Control común para cierre de modales con botón [data-modal-close] o tecla Escape
 */
function initModals() {
  document.addEventListener('click', (e) => {
    const closeBtn = e.target.closest('[data-modal-close]');
    if (closeBtn) {
      const modal = closeBtn.closest('.modal-overlay');
      if (modal) closeModal(modal);
    }
    // Cierre al hacer clic en el backdrop del modal universal
    if (e.target.id === 'modalUniversal') {
      cerrarModalUniversal();
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      cerrarModalUniversal();
      const activeModal = document.querySelector('.modal-overlay.active');
      if (activeModal && activeModal.id !== 'modalUniversal') closeModal(activeModal);
    }
  });
}

function openModal(modalEl) {
  if (typeof modalEl === 'string') modalEl = document.querySelector(modalEl);
  if (modalEl) modalEl.classList.add('active');
}

function closeModal(modalEl) {
  if (typeof modalEl === 'string') modalEl = document.querySelector(modalEl);
  if (modalEl) modalEl.classList.remove('active');
}

/**
 * Sistema simple de notificaciones Toast
 */
function showToast(message, type = 'info', duration = 3000) {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:99999;display:flex;flex-direction:column;gap:10px;';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `alert alert-${type}`;
  toast.style.cssText = 'box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); padding: 12px 18px; border-radius: 8px; font-size: 0.88rem; font-weight: 600; display: flex; align-items: center; gap: 8px; animation: fadeIn 0.2s ease; z-index: 99999;';

  if (type === 'success') {
    toast.style.background = '#dcfce7';
    toast.style.border = '1px solid #86efac';
    toast.style.color = '#15803d';
  } else if (type === 'error') {
    toast.style.background = '#fee2e2';
    toast.style.border = '1px solid #fca5a5';
    toast.style.color = '#b91c1c';
  } else {
    toast.style.background = '#e0f2fe';
    toast.style.border = '1px solid #7dd3fc';
    toast.style.color = '#0369a1';
  }

  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

/**
 * API Global Unificada AppModal para reutilización en cualquier parte del sistema
 */
window.AppModal = {
  open: function(view = 'perfil') {
    abrirModalUniversal(view);
  },
  close: function() {
    cerrarModalUniversal();
  },
  profile: function() {
    abrirModalPerfil();
  },
  password: function() {
    abrirModalPassword();
  },
  settings: function() {
    abrirModalAjustes();
  }
};
