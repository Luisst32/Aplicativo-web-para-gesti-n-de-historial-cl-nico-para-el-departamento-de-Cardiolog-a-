// IDs marcados con la palomita de selección para exportar. Persiste
// mientras cambian los filtros (a propósito: permite filtrar por un año,
// marcar algunos, cambiar el filtro y seguir sumando a la selección).
const seleccionados = new Set();

document.addEventListener('DOMContentLoaded', () => {
  renderFormularios();

  document.getElementById('filtroBusqueda').addEventListener('input', renderFormularios);
  document.getElementById('filtroAnio').addEventListener('change', renderFormularios);
  document.getElementById('filtroEstamento').addEventListener('change', renderFormularios);
  document.getElementById('filtroSexo').addEventListener('change', renderFormularios);
  document.getElementById('ordenarPor').addEventListener('change', renderFormularios);

  // Modal compartido "Nuevo Paciente" (js/pacientes.js): al crearlo (o si
  // ya existía) se abre directamente su ficha.
  montarModalAgregarPaciente(abrirFichaDePaciente);
});

// Aplica los filtros/orden activos en la barra sobre la lista de pacientes
// (un paciente = una ficha = una tarjeta).
// La usan tanto el render de tarjetas en pantalla como los 3 exportadores,
// para que "exportar todo lo filtrado" (cuando no hay nada marcado con la
// palomita) respete exactamente lo que el usuario está viendo.
function obtenerFormulariosFiltrados() {
  const q = document.getElementById('filtroBusqueda').value.trim().toLowerCase();
  const anio = document.getElementById('filtroAnio').value;
  const estamento = document.getElementById('filtroEstamento').value;
  const sexo = document.getElementById('filtroSexo').value;
  const orden = document.getElementById('ordenarPor').value;

  const filtrados = pacientes.filter(p => {
    const matchQuery = !q || p.nombre.toLowerCase().includes(q) || p.codigo.toLowerCase().includes(q);
    const matchAnio = anio === 'all' || String(anioDePaciente(p)) === anio;
    const matchEstamento = estamento === 'all' || p.estamento === estamento;
    const matchSexo = sexo === 'all' || p.sexo === sexo;
    return matchQuery && matchAnio && matchEstamento && matchSexo;
  });

  filtrados.sort((a, b) => {
    if (orden === 'codigo') return a.codigo.localeCompare(b.codigo);
    return a.nombre.localeCompare(b.nombre);
  });

  return filtrados;
}

// El "sistema inteligente de exportación": si el usuario marcó formularios
// con la palomita, exporta exactamente esos (sin importar el filtro
// actual); si no marcó ninguno, exporta todos los que están filtrados en
// pantalla en ese momento.
function obtenerFormulariosParaExportar() {
  if (seleccionados.size > 0) {
    return pacientes.filter(p => seleccionados.has(p.id));
  }
  return obtenerFormulariosFiltrados();
}

function renderFormularios() {
  const grid = document.getElementById('formulariosGrid');
  const filtrados = obtenerFormulariosFiltrados();

  grid.innerHTML = '';
  grid.appendChild(crearTarjetaNuevaFicha());

  if (filtrados.length === 0) {
    grid.insertAdjacentHTML('beforeend', '<div class="formularios-empty">No se encontraron formularios que coincidan con los filtros seleccionados.</div>');
  } else {
    filtrados.forEach(p => grid.appendChild(crearTarjetaFormulario(p)));
  }

  actualizarEstadoSeleccion(filtrados);
}

// Tarjeta fija "+": siempre la primera del grid, sin importar filtros ni
// orden. Como cada persona tiene una sola ficha, solo sirve para registrar
// un paciente nuevo; los existentes se editan desde su propia tarjeta.
function crearTarjetaNuevaFicha() {
  const card = document.createElement('button');
  card.type = 'button';
  card.className = 'card card-visual formulario-card formulario-card-nueva';
  card.title = 'Nuevo paciente';
  card.setAttribute('aria-label', 'Nuevo paciente');
  card.addEventListener('click', abrirModalAgregarPaciente);
  card.innerHTML = '<span class="formulario-card-nueva-icono">+</span>';
  return card;
}

function urlFichaDePaciente(p) {
  return 'formulario-clinica.html?paciente=' + encodeURIComponent(p.id);
}

function abrirFichaDePaciente(p) {
  location.href = urlFichaDePaciente(p);
}

function crearTarjetaFormulario(p) {
  const card = document.createElement('div');
  card.className = 'card card-visual formulario-card';

  const inits = inicialesDe(p.nombre);
  const edad = calcAgeStr(p.fechaNac);
  const sexoLabel = p.sexo === 'H' ? 'Hombre' : 'Mujer';

  card.innerHTML = `
    <label class="formulario-card-check">
      <input type="checkbox" data-id="${p.id}" ${seleccionados.has(p.id) ? 'checked' : ''} onchange="toggleSeleccion('${p.id}', this.checked)">
    </label>
    <div class="formulario-card-header">
      <div class="formulario-card-avatar">${inits}</div>
      <div>
        <div class="formulario-card-name">${p.nombre}</div>
        <span class="formulario-card-code">${p.codigo}</span>
      </div>
    </div>
    <div class="formulario-card-badges">
      <span class="formulario-card-badge">${anioDePaciente(p)}</span>
      <span class="formulario-card-badge">${edad}</span>
      <span class="formulario-card-badge">${p.estamento}</span>
      <span class="formulario-card-badge">${sexoLabel}</span>
    </div>
    <div class="formulario-card-meta">
      <span>Facultad: ${p.facultad}</span>
      <span>${[p.ciudad, p.provincia].filter(Boolean).join(', ')}</span>
    </div>
    <div class="formulario-card-footer">
      <button type="button" class="btn" onclick="exportarPDF('${p.id}')">PDF</button>
      <a class="btn btn-primary" href="${urlFichaDePaciente(p)}">Ver Ficha Clínica &rarr;</a>
    </div>
  `;

  return card;
}

// =========================================================================
// SELECCIÓN "CON PALOMITA" (checkbox) para exportar
// =========================================================================

function toggleSeleccion(id, marcado) {
  if (marcado) {
    seleccionados.add(id);
  } else {
    seleccionados.delete(id);
  }
  actualizarEstadoSeleccion(obtenerFormulariosFiltrados());
}

function toggleSeleccionarTodos(marcarTodos) {
  const filtrados = obtenerFormulariosFiltrados();
  filtrados.forEach(p => {
    if (marcarTodos) {
      seleccionados.add(p.id);
    } else {
      seleccionados.delete(p.id);
    }
  });
  renderFormularios();
}

// Sincroniza el checkbox "Seleccionar todos" (incluyendo su estado
// indeterminado) y la pastilla de conteo, que muestra cuántos formularios
// hay filtrados y, si aplica, cuántos están marcados para exportar.
function actualizarEstadoSeleccion(filtrados) {
  const marcadosVisibles = filtrados.filter(p => seleccionados.has(p.id)).length;
  const checkTodos = document.getElementById('seleccionarTodos');
  checkTodos.checked = filtrados.length > 0 && marcadosVisibles === filtrados.length;
  checkTodos.indeterminate = marcadosVisibles > 0 && marcadosVisibles < filtrados.length;

  let texto = `Mostrando ${filtrados.length} de ${pacientes.length} formularios`;
  if (seleccionados.size > 0) {
    texto += ` · ${seleccionados.size} seleccionado(s)`;
  }
  document.getElementById('formulariosCount').textContent = texto;
}

// =========================================================================
// EXPORTACIÓN
// - CSV / SAV ("Exportar lista"): dataset en bloque, sobre
//   obtenerFormulariosParaExportar() -lo marcado con la palomita, o todo
//   lo filtrado si no se marcó nada-. Escala igual a 1 formulario que a
//   500 filas.
// - PDF: cada tarjeta tiene su propio botón "PDF" (exportarPDF(id)); un
//   PDF es siempre el historial clínico de UN solo formulario, así que no
//   usa las palomitas ni ningún selector. Genera el documento -mismo
//   formato de campo-etiqueta/valor de un formulario clínico impreso, no
//   una tabla- en #printFormsContainer y llama a window.print() (el
//   usuario elige "Guardar como PDF" como destino de impresión; ver
//   @media print en formularios-listado.css).
// =========================================================================

function descargarBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ---------- CSV ----------

function csvEscape(value) {
  const str = String(value ?? '');
  if (/[",\n]/.test(str)) {
    return '"' + str.replace(/"/g, '""') + '"';
  }
  return str;
}

function exportCSV() {
  const seleccion = obtenerFormulariosParaExportar();
  const headers = ['Codigo', 'Nombre', 'FechaNacimiento', 'Edad', 'Sexo', 'Estamento', 'Anio', 'Facultad', 'Ciudad', 'Provincia'];
  const lineas = [headers.join(',')];

  seleccion.forEach(p => {
    const fila = [
      p.codigo,
      p.nombre,
      p.fechaNac,
      parseInt(calcAgeStr(p.fechaNac), 10),
      p.sexo === 'H' ? 'Hombre' : 'Mujer',
      p.estamento,
      anioDePaciente(p),
      p.facultad,
      (p.ciudad || ''),
      (p.provincia || '')
    ].map(csvEscape);
    lineas.push(fila.join(','));
  });

  // BOM (﻿) para que Excel detecte UTF-8 y las tildes/ñ se vean bien.
  const contenido = '﻿' + lineas.join('\r\n');
  descargarBlob(new Blob([contenido], { type: 'text/csv;charset=utf-8;' }), 'formularios_cardiounemi.csv');
}

// ---------- SAV (SPSS System File) ----------
// Escritor binario mínimo del formato clásico "$FL2" (sin compresión, sin
// nombres largos): cabecera de 176 bytes + un registro tipo 2 por cada
// variable (con registros de continuación tipo -1 para strings de más de
// 8 caracteres) + terminador de diccionario tipo 999 + los casos en
// bruto. Es el mismo formato que leen SPSS Statistics y PSPP.

class SavByteWriter {
  constructor() {
    this.chunks = [];
  }
  writeInt32(value) {
    const buf = new ArrayBuffer(4);
    new DataView(buf).setInt32(0, value, true);
    this.chunks.push(new Uint8Array(buf));
  }
  writeFloat64(value) {
    const buf = new ArrayBuffer(8);
    new DataView(buf).setFloat64(0, value, true);
    this.chunks.push(new Uint8Array(buf));
  }
  writeFixedString(str, byteLen) {
    const s = (str === null || str === undefined ? '' : String(str)).slice(0, byteLen);
    const arr = new Uint8Array(byteLen).fill(0x20); // relleno con espacios
    for (let i = 0; i < s.length; i++) {
      arr[i] = s.charCodeAt(i) & 0xFF; // Latin-1: cubre tildes/ñ españolas
    }
    this.chunks.push(arr);
  }
  writeZeros(n) {
    this.chunks.push(new Uint8Array(n));
  }
  toBlob() {
    return new Blob(this.chunks, { type: 'application/octet-stream' });
  }
}

function buildSavFile(columns, rows) {
  const w = new SavByteWriter();
  const FMT_A = 1;
  const FMT_F = 5;

  let nominalCaseSize = 0;
  columns.forEach(c => {
    nominalCaseSize += c.type === 'numeric' ? 1 : Math.ceil(c.width / 8);
  });

  // ---- Registro tipo 1: cabecera de archivo (176 bytes) ----
  w.writeFixedString('$FL2', 4);
  w.writeFixedString('@(#) Exportado desde CARDIOUNEMI - Listado de Formularios', 60);
  w.writeInt32(2); // layout_code
  w.writeInt32(nominalCaseSize);
  w.writeInt32(0); // compression: sin comprimir
  w.writeInt32(0); // weight_index: sin variable de ponderación
  w.writeInt32(rows.length); // ncases
  w.writeFloat64(100.0); // bias (solo se usa si hay compresión)

  const ahora = new Date();
  const meses = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const dd = String(ahora.getDate()).padStart(2, '0');
  const mmm = meses[ahora.getMonth()];
  const yy = String(ahora.getFullYear()).slice(-2);
  w.writeFixedString(`${dd} ${mmm} ${yy}`, 9);
  const hh = String(ahora.getHours()).padStart(2, '0');
  const mi = String(ahora.getMinutes()).padStart(2, '0');
  const ss = String(ahora.getSeconds()).padStart(2, '0');
  w.writeFixedString(`${hh}:${mi}:${ss}`, 8);
  w.writeFixedString('Listado de Formularios Clinicos - CARDIOUNEMI', 64);
  w.writeZeros(3); // relleno final de la cabecera (176 bytes en total)

  // ---- Registros tipo 2: un registro por variable ----
  columns.forEach(col => {
    if (col.type === 'numeric') {
      w.writeInt32(2);
      w.writeInt32(0); // type = 0 -> numérica
      w.writeInt32(0); // sin etiqueta de variable
      w.writeInt32(0); // sin valores perdidos declarados
      const fmt = (FMT_F << 24) | (8 << 16) | (2 << 8); // F8.2
      w.writeInt32(fmt); // print format
      w.writeInt32(fmt); // write format
      w.writeFixedString(col.name, 8);
    } else {
      const totalElementos = Math.ceil(col.width / 8);
      // Registro que define la variable (ancho completo declarado en "type")
      w.writeInt32(2);
      w.writeInt32(col.width);
      w.writeInt32(0);
      w.writeInt32(0);
      const fmt = (FMT_A << 24) | (col.width << 16);
      w.writeInt32(fmt);
      w.writeInt32(fmt);
      w.writeFixedString(col.name, 8);
      // Registros de continuación (uno por cada 8 bytes adicionales)
      for (let i = 1; i < totalElementos; i++) {
        w.writeInt32(2);
        w.writeInt32(-1); // marca de continuación
        w.writeInt32(0);
        w.writeInt32(0);
        w.writeInt32(0);
        w.writeInt32(0);
        w.writeFixedString('', 8);
      }
    }
  });

  // ---- Registro tipo 999: fin del diccionario ----
  w.writeInt32(999);
  w.writeInt32(0);

  // ---- Datos: un caso tras otro, sin compresión ----
  rows.forEach(row => {
    columns.forEach(col => {
      const val = row[col.name];
      if (col.type === 'numeric') {
        w.writeFloat64(Number(val) || 0);
      } else {
        w.writeFixedString(val, Math.ceil(col.width / 8) * 8);
      }
    });
  });

  return w.toBlob();
}

function exportSAV() {
  const seleccion = obtenerFormulariosParaExportar();

  const columns = [
    { name: 'CODIGO', type: 'string', width: 12 },
    { name: 'NOMBRE', type: 'string', width: 40 },
    { name: 'FECHANAC', type: 'string', width: 10 },
    { name: 'EDAD', type: 'numeric' },
    { name: 'SEXO', type: 'string', width: 1 },
    { name: 'ESTAMENT', type: 'string', width: 12 },
    { name: 'ANIO', type: 'numeric' },
    { name: 'FACULTAD', type: 'string', width: 40 },
    { name: 'CIUDAD', type: 'string', width: 20 },
    { name: 'PROVINC', type: 'string', width: 20 }
  ];

  const rows = seleccion.map(p => ({
    CODIGO: p.codigo,
    NOMBRE: p.nombre,
    FECHANAC: p.fechaNac,
    EDAD: parseInt(calcAgeStr(p.fechaNac), 10),
    SEXO: p.sexo,
    ESTAMENT: p.estamento,
    ANIO: anioDePaciente(p),
    FACULTAD: p.facultad,
    CIUDAD: (p.ciudad || ''),
    PROVINC: (p.provincia || '')
  }));

  const blob = buildSavFile(columns, rows);
  descargarBlob(blob, 'formularios_cardiounemi.sav');
}

// ---------- Imprimir / PDF (un documento por formulario) ----------

function crearFormularioImprimible(p) {
  return `
    <section class="print-form-page">
      <div class="print-form-brand">CARDIOUNEMI — Sistema de Riesgo Cardiovascular UNEMI</div>
      <h1 class="print-form-heading">Formulario de Registro de Paciente</h1>
      <div class="print-form-grid">
        <div class="print-field">
          <span class="print-field-label">Código</span>
          <span class="print-field-value">${p.codigo}</span>
        </div>
        <div class="print-field">
          <span class="print-field-label">Año</span>
          <span class="print-field-value">${anioDePaciente(p)}</span>
        </div>
        <div class="print-field print-field-full">
          <span class="print-field-label">Nombre y Apellidos</span>
          <span class="print-field-value">${p.nombre}</span>
        </div>
        <div class="print-field">
          <span class="print-field-label">Fecha de Nacimiento</span>
          <span class="print-field-value">${p.fechaNac}</span>
        </div>
        <div class="print-field">
          <span class="print-field-label">Edad</span>
          <span class="print-field-value">${calcAgeStr(p.fechaNac)}</span>
        </div>
        <div class="print-field">
          <span class="print-field-label">Sexo</span>
          <span class="print-field-value">${p.sexo === 'H' ? 'Hombre' : 'Mujer'}</span>
        </div>
        <div class="print-field">
          <span class="print-field-label">Estamento</span>
          <span class="print-field-value">${p.estamento}</span>
        </div>
        <div class="print-field print-field-full">
          <span class="print-field-label">Facultad</span>
          <span class="print-field-value">${p.facultad}</span>
        </div>
        <div class="print-field">
          <span class="print-field-label">Ciudad</span>
          <span class="print-field-value">${(p.ciudad || '')}</span>
        </div>
        <div class="print-field">
          <span class="print-field-label">Provincia</span>
          <span class="print-field-value">${(p.provincia || '')}</span>
        </div>
      </div>
      <div class="print-form-footer">Documento generado el ${new Date().toLocaleString('es-EC')} — CARDIOUNEMI</div>
    </section>
  `;
}

function exportarPDF(id) {
  const p = pacientes.find(f => f.id === id);

  if (!p) {
    alert('No se encontró ese formulario para exportar.');
    return;
  }

  document.getElementById('printFormsContainer').innerHTML = crearFormularioImprimible(p);
  window.print();
}
