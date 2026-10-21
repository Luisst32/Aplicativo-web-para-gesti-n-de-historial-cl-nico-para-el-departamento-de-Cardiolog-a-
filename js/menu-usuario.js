// MENÚ DE USUARIO (plantilla, datos de ejemplo): círculo con las iniciales
// en la esquina superior derecha de listado, ficha clínica y dashboard
// (contenedor marcado con data-user-menu). Al darle clic se despliega hacia
// abajo con sus opciones. Aún no hay sesión real: "Cerrar sesión" solo
// vuelve a la pantalla de login.

const USUARIO_EJEMPLO = {
  nombre: 'Dra. María Pérez',
  rol: 'Médico evaluador',
  correo: 'mperez@unemi.edu.ec'
};

document.addEventListener('DOMContentLoaded', () => {
  const slot = document.querySelector('[data-user-menu]');
  if (!slot) return;

  const u = USUARIO_EJEMPLO;
  const iniciales = inicialesUsuario(u.nombre);
  slot.insertAdjacentHTML('beforeend', `
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
        <a href="login-minimalista.html" class="user-menu-option user-menu-logout" role="menuitem">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
          Cerrar sesión
        </a>
      </div>
    </div>
  `);

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
  // "Mi perfil" y "Cambiar contraseña" aún no llevan a ninguna página.
  menu.querySelectorAll('.user-menu-option[href="#"]').forEach(op => {
    op.addEventListener('click', (e) => {
      e.preventDefault();
      alternar(false);
    });
  });
});

// Iniciales sin el título ("Dra. María Pérez" -> "MP").
function inicialesUsuario(nombre) {
  return nombre.split(' ').filter(p => !p.endsWith('.')).map(p => p[0]).slice(0, 2).join('');
}
