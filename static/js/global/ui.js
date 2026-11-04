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
      <button type="button" class="user-menu-trigger" aria-haspopup="menu" aria-expanded="false" title="${u.nombre}">
        ${iniciales}
      </button>
      <div class="user-menu-panel" role="menu">
        <div class="user-menu-info">
          <span class="user-menu-avatar">${iniciales}</span>
          <span class="user-menu-texts">
            <span class="user-menu-info-name">${u.nombre}</span>
            <span class="user-menu-info-role">${u.rol}</span>
            <span class="user-menu-info-mail">${u.correo}</span>
          </span>
        </div>
        <a href="#" class="user-menu-option" role="menuitem" onclick="abrirModalPerfil(); return false;">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
          Mi perfil
        </a>
        <a href="#" class="user-menu-option" role="menuitem" onclick="abrirModalPassword(); return false;">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
          Cambiar contraseña
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
  if (modal) {
    modal.style.display = 'none';
    modal.classList.remove('active');
  }
}

function cambiarVistaModal(vista) {
  const vPerfil = document.getElementById('vistaModalPerfil');
  const vPassword = document.getElementById('vistaModalPassword');
  const vAjustes = document.getElementById('vistaModalAjustes');

  const titulo = document.getElementById('modalUniversalTitulo');
  const subtitulo = document.getElementById('modalUniversalSubtitulo');
  const icono = document.getElementById('modalUniversalIcono');

  // Ocultar todas las vistas
  if (vPerfil) vPerfil.style.display = 'none';
  if (vPassword) vPassword.style.display = 'none';
  if (vAjustes) vAjustes.style.display = 'none';

  // Limpiar mensajes previos
  ['perfilErrorMsg', 'perfilSuccessMsg', 'passwordErrorMsg', 'passwordSuccessMsg', 'ajustesErrorMsg', 'ajustesSuccessMsg'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
  });

  if (vista === 'perfil') {
    if (vPerfil) vPerfil.style.display = 'block';
    if (titulo) titulo.textContent = 'Mi Perfil';
    if (subtitulo) subtitulo.textContent = 'Administración de cuenta de usuario';
    if (icono) {
      icono.style.background = '#eff6ff';
      icono.style.color = '#3aa0ff';
      icono.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>`;
    }
    cargarDatosPerfilEnFormulario();
  } else if (vista === 'password') {
    if (vPassword) vPassword.style.display = 'block';
    if (titulo) titulo.textContent = 'Cambiar Contraseña';
    if (subtitulo) subtitulo.textContent = 'Actualización de credenciales de acceso';
    if (icono) {
      icono.style.background = '#f0fdf4';
      icono.style.color = '#10b981';
      icono.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>`;
    }
    // Limpiar inputs de password
    ['passActual', 'passNueva', 'passConfirmar'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
  } else if (vista === 'ajustes') {
    if (vAjustes) vAjustes.style.display = 'block';
    if (titulo) titulo.textContent = 'Ajustes del Sistema';
    if (subtitulo) subtitulo.textContent = 'Configuración global y conexión con Inteligencia Artificial';
    if (icono) {
      icono.style.background = '#f1f5f9';
      icono.style.color = '#1e293b';
      icono.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>`;
    }
    cargarAjustesSistema();
  }
}

function abrirModalUniversal(vista = 'perfil') {
  const modal = document.getElementById('modalUniversal');
  if (!modal) return;
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
async function guardarPerfilUsuario(event) {
  if (event) event.preventDefault();

  const errEl = document.getElementById('perfilErrorMsg');
  const succEl = document.getElementById('perfilSuccessMsg');
  const btnGuardar = document.getElementById('btnGuardarPerfil');

  if (errEl) errEl.style.display = 'none';
  if (succEl) succEl.style.display = 'none';

  const first_name = document.getElementById('perfilFirstName')?.value.trim();
  const last_name = document.getElementById('perfilLastName')?.value.trim();
  const second_last_name = document.getElementById('perfilSecondLastName')?.value.trim();
  const email = document.getElementById('perfilEmail')?.value.trim();
  const current_password = document.getElementById('perfilPasswordConfirm')?.value;

  if (!current_password) {
    if (errEl) {
      errEl.textContent = 'Debe ingresar su contraseña actual para confirmar los cambios.';
      errEl.style.display = 'block';
    }
    return;
  }

  if (btnGuardar) {
    btnGuardar.disabled = true;
    btnGuardar.textContent = 'Guardando...';
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
      if (succEl) {
        succEl.textContent = data.message || 'Perfil actualizado correctamente.';
        succEl.style.display = 'block';
      }

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
      const passInp = document.getElementById('perfilPasswordConfirm');
      if (passInp) passInp.value = '';

      setTimeout(() => {
        cerrarModalUniversal();
      }, 1200);
    } else {
      if (errEl) {
        errEl.textContent = data.message || 'Error al actualizar el perfil.';
        errEl.style.display = 'block';
      }
    }
  } catch (err) {
    console.error('Error guardando perfil:', err);
    if (errEl) {
      errEl.textContent = 'Error de conexión con el servidor. Intente nuevamente.';
      errEl.style.display = 'block';
    }
  } finally {
    if (btnGuardar) {
      btnGuardar.disabled = false;
      btnGuardar.textContent = 'Guardar cambios';
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
 * Cargar configuración global del sistema (Ajustes)
 */
async function cargarAjustesSistema() {
  const switchChatbot = document.getElementById('switchChatbotActivo');
  const inputApiKey = document.getElementById('inputAjusteApiKey');
  const selectModelo = document.getElementById('selectAjusteModelo');
  const lblEstado = document.getElementById('lblApiKeyEstado');

  if (lblEstado) lblEstado.textContent = 'Consultando base de datos...';

  try {
    const res = await fetch('/security/api/settings/', {
      headers: { 'Accept': 'application/json' }
    });
    const data = await res.json();

    if (res.ok && data.status === 'success') {
      if (switchChatbot) {
        switchChatbot.checked = Boolean(data.chatbot_enabled);
        actualizarBadgeSwitchChatbot(switchChatbot.checked);
      }
      if (selectModelo && data.gemini_model) {
        selectModelo.value = data.gemini_model;
      }
      if (inputApiKey) {
        inputApiKey.value = data.api_key_masked || '';
      }
      if (lblEstado) {
        lblEstado.textContent = data.api_key_configured 
          ? `Clave guardada y cifrada en BD (${data.api_key_masked})` 
          : 'Sin clave configurada. Ingrésela arriba.';
      }
    }
  } catch (err) {
    console.error('Error cargando ajustes:', err);
    if (lblEstado) lblEstado.textContent = 'No se pudo cargar el estado de la clave.';
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

/**
 * Guardar ajustes del sistema (switch chatbot + API Key encriptada)
 */
async function guardarAjustesSistema(event) {
  if (event) event.preventDefault();

  const errEl = document.getElementById('ajustesErrorMsg');
  const succEl = document.getElementById('ajustesSuccessMsg');
  const btnGuardar = document.getElementById('btnGuardarAjustes');

  if (errEl) errEl.style.display = 'none';
  if (succEl) succEl.style.display = 'none';

  const chatbot_enabled = document.getElementById('switchChatbotActivo')?.checked;
  const gemini_api_key = document.getElementById('inputAjusteApiKey')?.value.trim();
  const gemini_model = document.getElementById('selectAjusteModelo')?.value;

  if (btnGuardar) {
    btnGuardar.disabled = true;
    btnGuardar.textContent = 'Guardando...';
  }

  try {
    const res = await fetch('/security/api/settings/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      },
      body: JSON.stringify({
        chatbot_enabled,
        gemini_api_key,
        gemini_model
      })
    });

    const data = await res.json();

    if (res.ok && data.status === 'success') {
      if (succEl) {
        succEl.textContent = data.message || 'Ajustes guardados correctamente.';
        succEl.style.display = 'block';
      }

      // Actualizar estado en tiempo real en la página
      window.CHATBOT_ENABLED = Boolean(data.chatbot_enabled);
      const btnFlotante = document.getElementById('btn-flotante-chat');
      if (btnFlotante) {
        btnFlotante.style.display = data.chatbot_enabled ? 'flex' : 'none';
      }

      showToast('Ajustes del sistema actualizados en base de datos.', 'success');

      setTimeout(() => {
        cerrarModalUniversal();
      }, 1200);
    } else {
      if (errEl) {
        errEl.textContent = data.message || 'Error al guardar ajustes.';
        errEl.style.display = 'block';
      }
    }
  } catch (err) {
    console.error('Error guardando ajustes:', err);
    if (errEl) {
      errEl.textContent = 'Error de conexión con el servidor.';
      errEl.style.display = 'block';
    }
  } finally {
    if (btnGuardar) {
      btnGuardar.disabled = false;
      btnGuardar.textContent = 'Guardar ajustes';
    }
  }
}

/**
 * Utilidad para alternar visibilidad de contraseña (eye toggle)
 */
function togglePasswordVisibility(inputId, btnEl) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const isPass = input.type === 'password';
  input.type = isPass ? 'text' : 'password';

  if (btnEl) {
    btnEl.innerHTML = isPass 
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
