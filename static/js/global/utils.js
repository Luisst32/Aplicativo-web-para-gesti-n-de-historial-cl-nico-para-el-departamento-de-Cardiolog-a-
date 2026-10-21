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

/**
 * Cálculo matemático de Índice de Masa Corporal (IMC)
 * Si se pasan (peso, talla), calcula y retorna el IMC numérico.
 * Si se llama sin argumentos (desde eventos DOM del formulario), lee f_peso y f_talla y actualiza el DOM.
 * @param {number} [peso] - Peso en kilogramos
 * @param {number} [talla] - Talla en centímetros
 * @returns {number} IMC calculado
 */
function calcIMC(peso, talla) {
  if (peso === undefined && typeof document !== 'undefined') {
    const elPeso = document.getElementById('f_peso');
    const elTalla = document.getElementById('f_talla');
    if (elPeso && elTalla) {
      const p = parseFloat(elPeso.value) || 0;
      const t = parseFloat(elTalla.value) || 0;
      const heroP = document.getElementById('heroPeso');
      const heroT = document.getElementById('heroTalla');
      const fImc = document.getElementById('f_imc');
      const fAsc = document.getElementById('f_asc');
      const heroImc = document.getElementById('heroImc');
      const heroAsc = document.getElementById('heroAsc');
      if (heroP) heroP.textContent = p ? `${p} kg` : '--';
      if (heroT) heroT.textContent = t ? `${t} cm` : '--';
      if (p > 20 && t > 50) {
        const imcVal = (p / ((t / 100) * (t / 100))).toFixed(2);
        const ascVal = Math.sqrt((p * t) / 3600).toFixed(2);
        if (fImc) fImc.value = imcVal;
        if (fAsc) fAsc.value = ascVal;
        if (heroImc) heroImc.textContent = imcVal;
        if (heroAsc) heroAsc.textContent = ascVal;
        return parseFloat(imcVal);
      } else {
        if (fImc) fImc.value = '--';
        if (fAsc) fAsc.value = '--';
        if (heroImc) heroImc.textContent = '--';
        if (heroAsc) heroAsc.textContent = '--';
        return 0;
      }
    }
  }
  if (!peso || !talla) return 0;
  const tM = talla / 100;
  return parseFloat((peso / (tM * tM)).toFixed(2));
}

/**
 * Cálculo matemático de Área de Superficie Corporal (ASC - Mosteller)
 * @param {number} peso - Peso en kilogramos
 * @param {number} talla - Talla en centímetros
 * @returns {number} ASC en m²
 */
function calcASC(peso, talla) {
  if (!peso || !talla) return 0;
  return parseFloat(Math.sqrt((talla * peso) / 3600).toFixed(2));
}

// Alias de retrocompatibilidad
const calcIMCValor = calcIMC;
const calcASCValor = calcASC;
