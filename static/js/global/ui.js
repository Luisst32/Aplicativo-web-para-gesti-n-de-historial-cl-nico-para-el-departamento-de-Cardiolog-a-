/**
 * UI.JS
 * Comportamientos de interfaz compartidos: inicialización del menú de usuario,
 * modales, notificaciones (toasts) y diálogos de confirmación.
 */

// Configuración o datos de usuario por defecto
const USUARIO_DEFAULT = {
  nombre: 'Dra. María Pérez',
  rol: 'Médico evaluador',
  correo: 'mperez@unemi.edu.ec'
};

document.addEventListener('DOMContentLoaded', () => {
  initUserMenu();
  initModals();
});

/**
 * Inicialización del menú de usuario en la barra superior / sidebar
 */
function initUserMenu() {
  const slot = document.querySelector('[data-user-menu]');
  if (!slot) return;

  const u = window.CURRENT_USER || USUARIO_DEFAULT;
  const iniciales = inicialesUsuario(u.nombre);

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
        <a href="#" class="user-menu-option" role="menuitem">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
          Mi perfil
        </a>
        <a href="#" class="user-menu-option" role="menuitem">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
          Cambiar contraseña
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

  menu.querySelectorAll('.user-menu-option[href="#"]').forEach(op => {
    op.addEventListener('click', (e) => {
      e.preventDefault();
      alternar(false);
    });
  });
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
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      const activeModal = document.querySelector('.modal-overlay.active');
      if (activeModal) closeModal(activeModal);
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
    container.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:10px;';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `alert alert-${type}`;
  toast.style.cssText = 'box-shadow:var(--shadow-lg);padding:12px 18px;border-radius:var(--radius-sm);animation:fadeIn 0.2s ease;';
  toast.textContent = message;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}
