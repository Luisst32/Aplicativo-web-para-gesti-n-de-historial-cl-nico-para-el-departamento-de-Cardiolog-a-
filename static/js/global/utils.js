/**
 * UTILS.JS
 * Funciones utilitarias globales: manejo de DOM, fechas, números y cookies.
 */

// Selector rápido de elementos
const $ = (selector, context = document) => context.querySelector(selector);
const $$ = (selector, context = document) => Array.from(context.querySelectorAll(selector));

// Obtener valor de cookie por nombre (para csrftoken de Django)
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

// Formatear fecha en formato DD/MM/AAAA
function formatDate(dateInput) {
  if (!dateInput) return '-';
  const d = new Date(dateInput);
  if (isNaN(d.getTime())) return String(dateInput);
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = d.getFullYear();
  return `${day}/${month}/${year}`;
}

// Formatear números con separador de miles
function formatNumber(num, decimals = 0) {
  if (num === null || num === undefined || isNaN(num)) return '-';
  return Number(num).toLocaleString('es-EC', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
}

// Debounce para optimizar búsquedas o eventos input
function debounce(func, wait = 300) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// Extraer iniciales de un nombre (omitiendo títulos como 'Dr.', 'Dra.')
function inicialesUsuario(nombre) {
  if (!nombre) return 'U';
  return nombre
    .split(' ')
    .filter(p => !p.endsWith('.') && p.trim().length > 0)
    .map(p => p[0].toUpperCase())
    .slice(0, 2)
    .join('');
}
