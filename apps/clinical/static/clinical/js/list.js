// =========================================================================
// FORMULARIOS-LISTADO.JS
// Gestión de Lista Ordenada de Pacientes y Expedientes de Historiales Clínicos
// (Vista integrada en página, sin modal y sin saturación visual)
// CARDIOUNEMI - Departamento de Cardiología
// =========================================================================

// IDs de pacientes marcados con checkbox para exportación masiva
const seleccionados = new Set();

// Estado de ordenamiento (Código 1, 2, 3, 4, 5... por defecto)
let columnaOrdenActual = 'codigo';
let direccionOrdenActual = 'asc';

// Paginación: 10 pacientes por página
const PACIENTES_POR_PAGINA = 10;
let paginaActual = 1;

// Paciente activo mostrado en el expediente
let pacienteActivoExpediente = null;

document.addEventListener('DOMContentLoaded', async () => {
  // Listeners de búsqueda y filtros (resetean a la página 1)
  document.getElementById('filtroBusqueda').addEventListener('input', () => {
    paginaActual = 1;
    renderPacientesTabla();
  });
  document.getElementById('filtroAnio').addEventListener('change', () => {
    paginaActual = 1;
    renderPacientesTabla();
  });
  document.getElementById('filtroEstamento').addEventListener('change', () => {
    paginaActual = 1;
    renderPacientesTabla();
  });
  document.getElementById('filtroSexo').addEventListener('change', () => {
    paginaActual = 1;
    renderPacientesTabla();
  });
  document.getElementById('ordenarPor').addEventListener('change', (e) => {
    paginaActual = 1;
    aplicarOrdenDesdeSelect(e.target.value);
  });

  // Modal compartido "Nuevo Paciente"
  montarModalAgregarPaciente((nuevoPaciente) => {
    renderPacientesTabla();
    abrirHistorialesPaciente(nuevoPaciente.id);
  });

  // Cargar cohorte real desde base de datos PostgreSQL (HU-15)
  await cargarPacientesDesdeServidor();

  // Si la URL contiene ?paciente=<id>, abrir directamente la vista de su expediente (sin modal)
  const params = new URLSearchParams(window.location.search);
  const idPacienteUrl = params.get('paciente');
  if (idPacienteUrl) {
    const pacienteEncontrado = pacientes.find(p => p.id === idPacienteUrl);
    if (pacienteEncontrado) {
      abrirHistorialesPaciente(idPacienteUrl);
    } else {
      renderPacientesTabla();
    }
  } else {
    renderPacientesTabla();
  }

  // Cerrar modales con Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      cerrarModalNuevoHistorial();
      cerrarModalExportar();
    }
  });
});

// =========================================================================
// FILTRADO Y ORDENAMIENTO DE PACIENTES
// =========================================================================

function obtenerPacientesFiltrados() {
  const q = document.getElementById('filtroBusqueda').value.trim().toLowerCase();
  const anio = document.getElementById('filtroAnio').value;
  const estamento = document.getElementById('filtroEstamento').value;
  const sexo = document.getElementById('filtroSexo').value;

  const filtrados = pacientes.filter(p => {
    const cedula = (p.cedula || '').toLowerCase();
    const codigo = (p.codigo || '').toLowerCase();
    const nombre = (p.nombre || '').toLowerCase();
    const facultad = (p.facultad || '').toLowerCase();

    const matchQuery = !q || nombre.includes(q) || codigo.includes(q) || cedula.includes(q) || facultad.includes(q);

    const anioPac = String(anioDePaciente(p));
    const historiales = p.historiales || [];
    const matchAnio = anio === 'all' || anioPac === anio || historiales.some(h => (h.fechaVisita || '').startsWith(anio));

    const matchEstamento = estamento === 'all' || p.estamento === estamento;
    const matchSexo = sexo === 'all' || p.sexo === sexo;

    return matchQuery && matchAnio && matchEstamento && matchSexo;
  });

  // Ordenar lista según columna activa
  filtrados.sort((a, b) => {
    let factor = direccionOrdenActual === 'asc' ? 1 : -1;

    switch (columnaOrdenActual) {
      case 'codigo': {
        const cA = parseInt(a.codigo, 10) || 0;
        const cB = parseInt(b.codigo, 10) || 0;
        return factor * (cA - cB);
      }

      case 'nombre':
        return factor * a.nombre.localeCompare(b.nombre);

      case 'historiales': {
        const cantA = (a.historiales || []).length;
        const cantB = (b.historiales || []).length;
        return factor * (cantA - cantB);
      }

      case 'fecha': {
        const ultA = obtenerUltimoHistorial(a);
        const ultB = obtenerUltimoHistorial(b);
        const fA = ultA && ultA.fechaVisita ? new Date(ultA.fechaVisita).getTime() : 0;
        const fB = ultB && ultB.fechaVisita ? new Date(ultB.fechaVisita).getTime() : 0;
        return factor * (fA - fB);
      }

      default:
        return factor * a.nombre.localeCompare(b.nombre);
    }
  });

  return filtrados;
}

function cambiarOrdenPorColumna(columna) {
  if (columnaOrdenActual === columna) {
    direccionOrdenActual = direccionOrdenActual === 'asc' ? 'desc' : 'asc';
  } else {
    columnaOrdenActual = columna;
    direccionOrdenActual = 'asc';
  }

  // Sincronizar el select de orden
  const select = document.getElementById('ordenarPor');
  if (select) {
    const valBuscado = `${columna}_${direccionOrdenActual}`;
    const existeOpcion = Array.from(select.options).some(o => o.value === valBuscado);
    if (existeOpcion) {
      select.value = valBuscado;
    }
  }

  renderPacientesTabla();
}

function aplicarOrdenDesdeSelect(valor) {
  const trozos = valor.split('_');
  if (trozos.length === 2) {
    columnaOrdenActual = trozos[0];
    direccionOrdenActual = trozos[1];
    renderPacientesTabla();
  }
}

function actualizarIconosOrdenCabeceras() {
  const columnas = ['nombre'];
  columnas.forEach(col => {
    const th = document.querySelector(`.th-sortable[data-sort="${col}"]`);
    const icono = document.getElementById(`sort-icon-${col}`);
    if (th && icono) {
      th.classList.remove('sorted-asc', 'sorted-desc');
      if (col === columnaOrdenActual) {
        th.classList.add(direccionOrdenActual === 'asc' ? 'sorted-asc' : 'sorted-desc');
        icono.textContent = direccionOrdenActual === 'asc' ? '▲' : '▼';
      } else {
        icono.textContent = '⇅';
      }
    }
  });
}

// =========================================================================
// RENDERIZADO DE TABLA Y ESTADÍSTICAS
// =========================================================================

function renderPacientesTabla() {
  const tbody = document.getElementById('pacientesTbody');
  const emptyMsg = document.getElementById('tablaVaciaMensaje');
  const filtrados = obtenerPacientesFiltrados();

  tbody.innerHTML = '';
  actualizarIconosOrdenCabeceras();
  actualizarStatsCards();

  const totalItems = filtrados.length;
  const totalPaginas = Math.ceil(totalItems / PACIENTES_POR_PAGINA) || 1;

  if (paginaActual > totalPaginas) paginaActual = totalPaginas;
  if (paginaActual < 1) paginaActual = 1;

  if (totalItems === 0) {
    emptyMsg.classList.remove('oculto');
  } else {
    emptyMsg.classList.add('oculto');
    const inicio = (paginaActual - 1) * PACIENTES_POR_PAGINA;
    const fin = inicio + PACIENTES_POR_PAGINA;
    const pacientesPagina = filtrados.slice(inicio, fin);

    pacientesPagina.forEach(p => {
      tbody.appendChild(crearFilaPaciente(p));
    });
  }

  actualizarControlesPaginacion(totalItems, totalPaginas);
  actualizarEstadoSeleccion(filtrados);
}

function actualizarControlesPaginacion(totalItems, totalPaginas) {
  const bar = document.getElementById('paginacionBar');
  if (!bar) return;

  if (totalItems === 0) {
    bar.classList.add('oculto');
    return;
  }
  bar.classList.remove('oculto');

  const resumen = document.getElementById('paginacionResumen');
  const btnAnt = document.getElementById('btnPagAnt');
  const btnSig = document.getElementById('btnPagSig');
  const numCont = document.getElementById('paginacionNumeros');

  const desde = (paginaActual - 1) * PACIENTES_POR_PAGINA + 1;
  const hasta = Math.min(paginaActual * PACIENTES_POR_PAGINA, totalItems);

  if (resumen) {
    resumen.textContent = `Página ${paginaActual} de ${totalPaginas} · Mostrando ${desde}-${hasta} de ${totalItems} pacientes (10 por pág.)`;
  }

  if (btnAnt) {
    btnAnt.disabled = paginaActual <= 1;
  }
  if (btnSig) {
    btnSig.disabled = paginaActual >= totalPaginas;
  }

  if (numCont) {
    numCont.innerHTML = '';
    for (let i = 1; i <= totalPaginas; i++) {
      const btnNum = document.createElement('button');
      btnNum.type = 'button';
      btnNum.className = `btn-pag-num ${i === paginaActual ? 'activa' : ''}`;
      btnNum.textContent = i;
      btnNum.title = `Ir a página ${i}`;
      btnNum.onclick = () => cambiarPagina(i);
      numCont.appendChild(btnNum);
    }
  }
}

function cambiarPagina(nuevaPagina) {
  const filtrados = obtenerPacientesFiltrados();
  const totalPaginas = Math.ceil(filtrados.length / PACIENTES_POR_PAGINA) || 1;
  if (nuevaPagina < 1 || nuevaPagina > totalPaginas) return;
  paginaActual = nuevaPagina;
  renderPacientesTabla();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function actualizarStatsCards() {
  const totalPacientes = pacientes.length;
  const elTotalP = document.getElementById('statTotalPacientes');
  if (elTotalP) elTotalP.textContent = totalPacientes;
}

function formatearFechaLegible(fechaStr) {
  if (!fechaStr) return '--';
  const partes = fechaStr.split('-');
  if (partes.length !== 3) return fechaStr;
  const meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
  const anio = partes[0];
  const mes = meses[parseInt(partes[1], 10) - 1] || partes[1];
  const dia = parseInt(partes[2], 10);
  return `${dia} ${mes} ${anio}`;
}

function crearFilaPaciente(p) {
  const tr = document.createElement('tr');
  tr.className = 'paciente-fila';
  if (seleccionados.has(p.id)) {
    tr.classList.add('seleccionada');
  }

  const inits = inicialesDe(p.nombre);
  const historiales = obtenerHistorialesPaciente(p);
  const ultHistorial = historiales[0] || null;
  const fechaUltima = ultHistorial ? formatearFechaLegible(ultHistorial.fechaVisita) : '--';

  tr.innerHTML = `
    <td class="td-check" onclick="event.stopPropagation()">
      <input type="checkbox" data-id="${p.id}" ${seleccionados.has(p.id) ? 'checked' : ''} onchange="toggleSeleccion('${p.id}', this.checked)">
    </td>
    <td>
      <div class="celda-paciente">
        <div class="avatar-paciente">${inits}</div>
        <div class="info-paciente">
          <span class="nombre-paciente" title="Haga clic para ver el expediente y ficha médica de este paciente"><span style="display:inline-block; min-width:24px; padding:2px 8px; margin-right:8px; border-radius:6px; background:#eff6ff; color:#1d4ed8; font-size:0.82rem; font-weight:800; border:1px solid #bfdbfe;">#${p.codigo}</span>${p.nombre}</span>
          <div class="meta-secundaria">
            <span>C.I: ${p.cedula || '0900000000'}</span>
            <span>·</span>
            <span>${p.correo || (p.telefono ? 'Tel: ' + p.telefono : 'UNEMI')}</span>
          </div>
        </div>
      </div>
    </td>
  `;

  // Al hacer clic en la fila se abre el expediente en la página (sin modal)
  tr.addEventListener('click', () => {
    abrirHistorialesPaciente(p.id);
  });

  return tr;
}

// =========================================================================
// GESTIÓN DEL EXPEDIENTE E HISTORIALES CLÍNICOS DEL PACIENTE
// (VISTA EN PÁGINA, SIN MODAL Y SIN SATURACIÓN VISUAL)
// =========================================================================

function abrirHistorialesPaciente(pacienteId) {
  const p = pacientes.find(item => item.id === pacienteId);
  if (!p) return;

  pacienteActivoExpediente = p;

  // 1. Ocultar la tabla de listado y la barra de herramientas, y mostrar la vista de expediente
  const vistaListado = document.getElementById('vistaListadoPacientes');
  const vistaExpediente = document.getElementById('vistaExpedientePaciente');
  const slicers = document.getElementById('slicersFiltros');
  const topBarActions = document.getElementById('topBarActions');

  if (vistaListado) vistaListado.classList.add('oculto');
  if (vistaExpediente) vistaExpediente.classList.remove('oculto');
  if (slicers) slicers.classList.add('oculto');
  if (topBarActions) topBarActions.classList.add('oculto');

  // Actualizar título superior
  document.getElementById('topPageTitle').textContent = `Expediente Clínico · ${p.nombre}`;

  // 2. Llenar datos limpios del encabezado del paciente (sin código ni datos saturados)
  const inits = inicialesDe(p.nombre);
  document.getElementById('expAvatar').textContent = inits;
  document.getElementById('expNombre').textContent = p.nombre;
  document.getElementById('expEdadSexo').textContent = `${calcAgeStr(p.fechaNac)} · ${p.sexo === 'H' ? 'Hombre' : 'Mujer'}`;
  document.getElementById('expEstamentoFacultad').textContent = `${p.estamento} · ${p.facultad || 'UNEMI'}`;

  // 3. Renderizar el historial clínico (despejado y ordenado)
  const historiales = obtenerHistorialesPaciente(p);
  const containerTimeline = document.getElementById('timelineHistoriales');
  containerTimeline.innerHTML = '';

  historiales.forEach((h) => {
    const cardH = document.createElement('div');
    cardH.className = 'historial-fila-limpia';

    const fechaFmt = formatearFechaLegible(h.fechaVisita);

    cardH.innerHTML = `
      <div class="historial-info-principal">
        <div class="historial-encabezado-linea">
          <span class="historial-tag-numero">Historial Clínico Único</span>
          <span style="font-size:0.84rem; color:var(--color-text-muted); font-weight:600;">Última atención: ${fechaFmt}</span>
          <span style="font-size:0.75rem; background:var(--color-ice-blue); color:var(--color-primary-blue); padding:2px 8px; border-radius:4px; font-weight:600;">Ficha Médica Activa</span>
        </div>

        <div class="historial-evaluador-linea">
          <span><strong>Evaluador:</strong> ${h.medico || 'Dra. María Pérez - Cardiología UNEMI'}</span>
        </div>
      </div>

      <div class="historial-acciones-derecha">
        <button type="button" class="btn btn-sm" onclick="exportarPDFHistorial('${p.id}', '${h.id}')" title="Imprimir reporte en PDF">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9V2h12v7"></path><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path><rect x="6" y="14" width="12" height="8"></rect></svg>
          <span>PDF</span>
        </button>
        <a class="btn btn-sm btn-primary" href="/clinical/formulario/?paciente=${encodeURIComponent(p.id)}" title="Abrir la ficha médica completa para analizar antecedentes y registrar atención">
          <span>Abrir Ficha Médica Completa &rarr;</span>
        </a>
      </div>
    `;

    containerTimeline.appendChild(cardH);
  });

  // 4. Actualizar URL de forma limpia en el historial del navegador
  try {
    history.replaceState(null, '', `/clinical/listado/?paciente=${encodeURIComponent(p.id)}`);
  } catch (err) {}

  // Scroll suave al inicio
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Volver de la vista de expediente al listado ordenado de pacientes
function volverAListadoPacientes() {
  const vistaListado = document.getElementById('vistaListadoPacientes');
  const vistaExpediente = document.getElementById('vistaExpedientePaciente');
  const slicers = document.getElementById('slicersFiltros');
  const topBarActions = document.getElementById('topBarActions');

  if (vistaExpediente) vistaExpediente.classList.add('oculto');
  if (vistaListado) vistaListado.classList.remove('oculto');
  if (slicers) slicers.classList.remove('oculto');
  if (topBarActions) topBarActions.classList.remove('oculto');

  // Restaurar título
  document.getElementById('topPageTitle').textContent = 'Directorio de Pacientes y Fichas Clínicas';

  pacienteActivoExpediente = null;

  try {
    history.replaceState(null, '', '/clinical/listado/');
  } catch (err) {}

  renderPacientesTabla();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Al atender al paciente se navega directamente a su ficha clínica para consultar antecedentes
function abrirModalNuevoHistorial(pacienteId) {
  const p = pacienteId ? pacientes.find(item => item.id === pacienteId) : pacienteActivoExpediente;
  if (!p) {
    alert('Por favor seleccione un paciente.');
    return;
  }
  window.location.href = `/clinical/formulario/?paciente=${encodeURIComponent(p.id)}`;
}

function cerrarModalNuevoHistorial() {
  const modal = document.getElementById('modalNuevoHistorial');
  if (modal) {
    modal.classList.remove('active');
  }
}

function confirmarNuevoHistorial() {
  if (!pacienteActivoExpediente) return;
  window.location.href = `/clinical/formulario/?paciente=${encodeURIComponent(pacienteActivoExpediente.id)}`;
}

// =========================================================================
// SELECCIÓN CON CHECKBOX PARA EXPORTACIÓN MASIVA
// =========================================================================

function toggleSeleccion(id, marcado) {
  if (marcado) {
    seleccionados.add(id);
  } else {
    seleccionados.delete(id);
  }
  const filtrados = obtenerPacientesFiltrados();
  actualizarEstadoSeleccion(filtrados);

  const row = document.querySelector(`input[data-id="${id}"]`)?.closest('tr');
  if (row) {
    row.classList.toggle('seleccionada', marcado);
  }
}

function toggleSeleccionarTodos(marcarTodos) {
  const filtrados = obtenerPacientesFiltrados();
  filtrados.forEach(p => {
    if (marcarTodos) {
      seleccionados.add(p.id);
    } else {
      seleccionados.delete(p.id);
    }
  });
  renderPacientesTabla();
}

function actualizarEstadoSeleccion(filtrados) {
  const marcadosVisibles = filtrados.filter(p => seleccionados.has(p.id)).length;
  const checkTodosTop = document.getElementById('seleccionarTodos');
  const checkTodosTabla = document.getElementById('seleccionarTodosTabla');

  const esCompleto = filtrados.length > 0 && marcadosVisibles === filtrados.length;
  const esIndeterminado = marcadosVisibles > 0 && marcadosVisibles < filtrados.length;

  if (checkTodosTop) {
    checkTodosTop.checked = esCompleto;
    checkTodosTop.indeterminate = esIndeterminado;
  }
  if (checkTodosTabla) {
    checkTodosTabla.checked = esCompleto;
    checkTodosTabla.indeterminate = esIndeterminado;
  }

  const countEl = document.getElementById('formulariosCount');
  if (countEl) {
    let texto = `Mostrando ${filtrados.length} de ${pacientes.length} pacientes`;
    if (seleccionados.size > 0) {
      texto += ` · ${seleccionados.size} seleccionado(s)`;
    }
    countEl.textContent = texto;
  }
}

function obtenerPacientesParaExportar() {
  if (seleccionados.size > 0) {
    return pacientes.filter(p => seleccionados.has(p.id));
  }
  return obtenerPacientesFiltrados();
}

// =========================================================================
// SISTEMA DE EXPORTACIÓN INTELIGENTE (MODAL AVANZADO: CSV, SPSS SAV, JSON)
// Permite elegir alcance (todos, filtrados, seleccionados, página),
// formato de salida, estructura (pacientes o historiales longitudinales) y módulos.
// =========================================================================

function abrirModalExportar() {
  const modal = document.getElementById('modalExportarInteligente');
  if (!modal) return;

  const totalPacientes = pacientes.length;
  const filtrados = obtenerPacientesFiltrados();
  const cantFiltrados = filtrados.length;
  const cantSeleccionados = seleccionados.size;

  const inicio = (paginaActual - 1) * PACIENTES_POR_PAGINA;
  const fin = inicio + PACIENTES_POR_PAGINA;
  const cantPagina = filtrados.slice(inicio, fin).length;

  // Actualizar píldoras de conteo en tiempo real
  const elPillTodos = document.getElementById('pillAlcanceTodos');
  const elPillFilt = document.getElementById('pillAlcanceFiltrados');
  const elPillSel = document.getElementById('pillAlcanceSeleccionados');
  const elPillPag = document.getElementById('pillAlcancePagina');

  if (elPillTodos) elPillTodos.textContent = totalPacientes;
  if (elPillFilt) elPillFilt.textContent = cantFiltrados;
  if (elPillSel) elPillSel.textContent = cantSeleccionados;
  if (elPillPag) elPillPag.textContent = cantPagina;

  // Si no hay seleccionados, ajustar selección por defecto
  const radioSel = document.querySelector('input[name="exportAlcance"][value="seleccionados"]');
  const cardSel = document.getElementById('lblAlcanceSeleccionados');
  if (radioSel && cardSel) {
    if (cantSeleccionados === 0) {
      radioSel.disabled = true;
      cardSel.style.opacity = '0.55';
      cardSel.style.cursor = 'not-allowed';
      if (radioSel.checked) {
        const rTodos = document.querySelector('input[name="exportAlcance"][value="todos"]');
        if (rTodos) rTodos.checked = true;
      }
    } else {
      radioSel.disabled = false;
      cardSel.style.opacity = '1';
      cardSel.style.cursor = 'pointer';
    }
  }

  actualizarResumenExportacion();
  modal.classList.add('active');
}

function cerrarModalExportar() {
  const modal = document.getElementById('modalExportarInteligente');
  if (modal) {
    modal.classList.remove('active');
  }
}

function obtenerPacientesSegunAlcance() {
  const alcance = document.querySelector('input[name="exportAlcance"]:checked')?.value || 'todos';
  const filtrados = obtenerPacientesFiltrados();

  switch (alcance) {
    case 'todos':
      return pacientes;

    case 'filtrados':
      return filtrados;

    case 'seleccionados':
      return pacientes.filter(p => seleccionados.has(p.id));

    case 'pagina': {
      const inicio = (paginaActual - 1) * PACIENTES_POR_PAGINA;
      const fin = inicio + PACIENTES_POR_PAGINA;
      return filtrados.slice(inicio, fin);
    }

    default:
      return pacientes;
  }
}

function actualizarResumenExportacion() {
  const pacs = obtenerPacientesSegunAlcance();
  const formato = document.querySelector('input[name="exportFormato"]:checked')?.value || 'csv';
  const totalRegistros = pacs.length;

  const preview = document.getElementById('exportPreviewText');
  if (preview) {
    const etiquetaFormato = formato === 'csv' ? 'Excel / CSV (.csv)' : 'SPSS Statistics (.sav)';
    preview.innerHTML = `Se exportarán <strong>${totalRegistros} paciente(s)</strong> en formato <strong>${etiquetaFormato}</strong> con su expediente clínico consolidado y variables cardiovasculares.`;
  }
}

function ejecutarExportacionInteligente() {
  const pacs = obtenerPacientesSegunAlcance();
  if (!pacs || pacs.length === 0) {
    alert('No hay pacientes que coincidan con el alcance seleccionado.');
    return;
  }

  const formato = document.querySelector('input[name="exportFormato"]:checked')?.value || 'csv';
  const estructura = 'pacientes';
  const mods = { modFiliacion: true, modBiometria: true, modClinico: true };
  const fechaIso = new Date().toISOString().split('T')[0];

  if (formato === 'csv') {
    generarExportacionCSV(pacs, estructura, mods, fechaIso);
  } else if (formato === 'sav') {
    generarExportacionSAV(pacs, estructura, mods, fechaIso);
  }

  // Feedback en botón
  const btnTxt = document.getElementById('btnTxtDescargar');
  if (btnTxt) {
    const original = btnTxt.textContent;
    btnTxt.textContent = '¡Exportado!';
    setTimeout(() => {
      btnTxt.textContent = original;
      cerrarModalExportar();
    }, 600);
  } else {
    cerrarModalExportar();
  }
}

function generarExportacionCSV(pacs, estructura, mods, fechaIso) {
  const cols = [];
  if (mods.modFiliacion) {
    cols.push('Codigo', 'Cedula', 'Nombre', 'FechaNacimiento', 'Edad', 'Sexo', 'Estamento', 'Facultad', 'Ciudad');
  }
  if (estructura === 'historiales') {
    if (mods.modClinico) cols.push('NumeroVisita', 'FechaVisita', 'TipoEvaluacion', 'Motivo', 'Medico', 'EstadoConsulta');
    if (mods.modBiometria) cols.push('TAS', 'TSI', 'Peso', 'Talla', 'IMC', 'ASC', 'SatO2', 'Perimetro', 'RiesgoGlobal');
  } else {
    cols.push('TotalHistoriales');
    if (mods.modClinico) cols.push('UltimaVisita', 'TipoUltimaVisita', 'Medico', 'RiesgoGlobal');
    if (mods.modBiometria) cols.push('TAS', 'TSI', 'Peso', 'Talla', 'IMC', 'ASC', 'Perimetro');
  }

  const lineas = [cols.join(',')];

  pacs.forEach(p => {
    const historiales = obtenerHistorialesPaciente(p);

    if (estructura === 'historiales') {
      historiales.forEach(h => {
        const fila = [];
        if (mods.modFiliacion) {
          fila.push(p.codigo, p.cedula || '', p.nombre, p.fechaNac, parseInt(calcAgeStr(p.fechaNac), 10), p.sexo, p.estamento, p.facultad, p.ciudad || '');
        }
        if (mods.modClinico) {
          fila.push(h.numeroVisita, h.fechaVisita, h.tipo || '', h.motivo || '', h.medico || '', h.estado || '');
        }
        if (mods.modBiometria) {
          fila.push(h.tas || p.tas || '', h.tsi || p.tsi || '', h.peso || p.peso || '', h.talla || p.talla || '', h.imc || calcIMCValor(h.peso, h.talla) || '', h.asc || calcASCValor(h.peso, h.talla) || '', h.satO2 || 98, h.perimetro || p.perimetro || '', h.riesgoGlobal || 'Bajo');
        }
        lineas.push(fila.map(csvEscape).join(','));
      });
    } else {
      const ult = historiales[0] || null;
      const fila = [];
      if (mods.modFiliacion) {
        fila.push(p.codigo, p.cedula || '', p.nombre, p.fechaNac, parseInt(calcAgeStr(p.fechaNac), 10), p.sexo, p.estamento, p.facultad, p.ciudad || '');
      }
      fila.push(historiales.length);
      if (mods.modClinico) {
        fila.push(ult ? ult.fechaVisita : '', ult ? (ult.tipo || '') : '', ult ? (ult.medico || '') : '', ult ? (ult.riesgoGlobal || 'Bajo') : 'Bajo');
      }
      if (mods.modBiometria) {
        fila.push(ult ? ult.tas : (p.tas || ''), ult ? ult.tsi : (p.tsi || ''), ult ? ult.peso : (p.peso || ''), ult ? ult.talla : (p.talla || ''), ult ? (ult.imc || calcIMCValor(ult.peso, ult.talla)) : '', ult ? (ult.asc || calcASCValor(ult.peso, ult.talla)) : '', ult ? ult.perimetro : (p.perimetro || ''));
      }
      lineas.push(fila.map(csvEscape).join(','));
    }
  });

  const contenido = '\uFEFF' + lineas.join('\r\n');
  const filename = `cardiounemi_${estructura}_${fechaIso}.csv`;
  descargarBlob(new Blob([contenido], { type: 'text/csv;charset=utf-8;' }), filename);
}

function generarExportacionSAV(pacs, estructura, mods, fechaIso) {
  const columns = [];
  if (mods.modFiliacion) {
    columns.push(
      { name: 'CODIGO', type: 'string', width: 12 },
      { name: 'CEDULA', type: 'string', width: 12 },
      { name: 'NOMBRE', type: 'string', width: 40 },
      { name: 'EDAD', type: 'numeric' },
      { name: 'SEXO', type: 'string', width: 1 },
      { name: 'ESTAMENT', type: 'string', width: 14 }
    );
  }

  if (estructura === 'historiales') {
    if (mods.modClinico) {
      columns.push(
        { name: 'NUMVISIT', type: 'numeric' },
        { name: 'FECHAVIS', type: 'string', width: 10 },
        { name: 'TIPOVIS', type: 'string', width: 30 }
      );
    }
    if (mods.modBiometria) {
      columns.push(
        { name: 'TAS', type: 'numeric' },
        { name: 'TSI', type: 'numeric' },
        { name: 'PESO', type: 'numeric' },
        { name: 'TALLA', type: 'numeric' },
        { name: 'IMC', type: 'numeric' }
      );
    }
  } else {
    columns.push({ name: 'NHISTOR', type: 'numeric' });
    if (mods.modBiometria) {
      columns.push(
        { name: 'TAS', type: 'numeric' },
        { name: 'TSI', type: 'numeric' },
        { name: 'IMC', type: 'numeric' }
      );
    }
    if (mods.modClinico) {
      columns.push({ name: 'RIESGO', type: 'string', width: 10 });
    }
  }

  const rows = [];
  pacs.forEach(p => {
    const historiales = obtenerHistorialesPaciente(p);

    if (estructura === 'historiales') {
      historiales.forEach(h => {
        const r = {};
        if (mods.modFiliacion) {
          r.CODIGO = p.codigo;
          r.CEDULA = p.cedula || '';
          r.NOMBRE = p.nombre;
          r.EDAD = parseInt(calcAgeStr(p.fechaNac), 10);
          r.SEXO = p.sexo;
          r.ESTAMENT = p.estamento;
        }
        if (mods.modClinico) {
          r.NUMVISIT = h.numeroVisita || 1;
          r.FECHAVIS = h.fechaVisita || '';
          r.TIPOVIS = h.tipo || '';
        }
        if (mods.modBiometria) {
          r.TAS = h.tas || p.tas || 120;
          r.TSI = h.tsi || p.tsi || 80;
          r.PESO = h.peso || p.peso || 70;
          r.TALLA = h.talla || p.talla || 170;
          r.IMC = h.imc || calcIMCValor(r.PESO, r.TALLA) || 24;
        }
        rows.push(r);
      });
    } else {
      const ult = historiales[0] || null;
      const r = {};
      if (mods.modFiliacion) {
        r.CODIGO = p.codigo;
        r.CEDULA = p.cedula || '';
        r.NOMBRE = p.nombre;
        r.EDAD = parseInt(calcAgeStr(p.fechaNac), 10);
        r.SEXO = p.sexo;
        r.ESTAMENT = p.estamento;
      }
      r.NHISTOR = historiales.length;
      if (mods.modBiometria) {
        r.TAS = ult ? (ult.tas || 120) : (p.tas || 120);
        r.TSI = ult ? (ult.tsi || 80) : (p.tsi || 80);
        r.IMC = ult ? (ult.imc || 24) : 24;
      }
      if (mods.modClinico) {
        r.RIESGO = ult ? (ult.riesgoGlobal || 'Bajo') : 'Bajo';
      }
      rows.push(r);
    }
  });

  const blob = buildSavFile(columns, rows);
  const filename = `cardiounemi_${estructura}_${fechaIso}.sav`;
  descargarBlob(blob, filename);
}

function generarExportacionJSON(pacs, estructura, mods, fechaIso) {
  const dataset = {
    institucion: "CARDIOUNEMI - Universidad Estatal de Milagro",
    departamento: "Departamento de Cardiología",
    fechaExportacion: new Date().toISOString(),
    totalPacientes: pacs.length,
    estructura: estructura,
    registros: pacs.map(p => {
      const r = {};
      if (mods.modFiliacion) {
        r.id = p.id;
        r.codigo = p.codigo;
        r.cedula = p.cedula;
        r.nombre = p.nombre;
        r.fechaNac = p.fechaNac;
        r.edad = parseInt(calcAgeStr(p.fechaNac), 10);
        r.sexo = p.sexo;
        r.estamento = p.estamento;
        r.facultad = p.facultad;
        r.correo = p.correo;
        r.telefono = p.telefono;
        r.ciudad = p.ciudad;
      }
      if (mods.modClinico || mods.modBiometria) {
        const historiales = obtenerHistorialesPaciente(p);
        if (estructura === 'historiales') {
          r.historiales = historiales;
        } else {
          r.totalHistoriales = historiales.length;
          r.ultimaEvaluacion = historiales[0] || null;
        }
      }
      return r;
    })
  };

  const contenido = JSON.stringify(dataset, null, 2);
  const filename = `cardiounemi_dataset_${fechaIso}.json`;
  descargarBlob(new Blob([contenido], { type: 'application/json;charset=utf-8;' }), filename);
}

// SPSS SAV Writer binario
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
    const arr = new Uint8Array(byteLen).fill(0x20);
    for (let i = 0; i < s.length; i++) {
      arr[i] = s.charCodeAt(i) & 0xFF;
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

  w.writeFixedString('$FL2', 4);
  w.writeFixedString('@(#) Exportado desde CARDIOUNEMI - Directorio de Pacientes', 60);
  w.writeInt32(2);
  w.writeInt32(nominalCaseSize);
  w.writeInt32(0);
  w.writeInt32(0);
  w.writeInt32(rows.length);
  w.writeFloat64(100.0);

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
  w.writeFixedString('Directorio de Pacientes e Historiales - CARDIOUNEMI', 64);
  w.writeZeros(3);

  columns.forEach(col => {
    if (col.type === 'numeric') {
      w.writeInt32(2);
      w.writeInt32(0);
      w.writeInt32(0);
      w.writeInt32(0);
      const fmt = (FMT_F << 24) | (8 << 16) | (2 << 8);
      w.writeInt32(fmt);
      w.writeInt32(fmt);
      w.writeFixedString(col.name, 8);
    } else {
      const totalElementos = Math.ceil(col.width / 8);
      w.writeInt32(2);
      w.writeInt32(col.width);
      w.writeInt32(0);
      w.writeInt32(0);
      const fmt = (FMT_A << 24) | (col.width << 16);
      w.writeInt32(fmt);
      w.writeInt32(fmt);
      w.writeFixedString(col.name, 8);
      for (let i = 1; i < totalElementos; i++) {
        w.writeInt32(2);
        w.writeInt32(-1);
        w.writeInt32(0);
        w.writeInt32(0);
        w.writeInt32(0);
        w.writeInt32(0);
        w.writeFixedString('', 8);
      }
    }
  });

  w.writeInt32(999);
  w.writeInt32(0);

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
  const seleccion = obtenerPacientesParaExportar();
  const columns = [
    { name: 'CODIGO', type: 'string', width: 12 },
    { name: 'CEDULA', type: 'string', width: 12 },
    { name: 'NOMBRE', type: 'string', width: 40 },
    { name: 'FECHANAC', type: 'string', width: 10 },
    { name: 'EDAD', type: 'numeric' },
    { name: 'SEXO', type: 'string', width: 1 },
    { name: 'ESTAMENT', type: 'string', width: 12 },
    { name: 'FACULTAD', type: 'string', width: 40 },
    { name: 'HISTORLS', type: 'numeric' },
    { name: 'TAS', type: 'numeric' },
    { name: 'TSI', type: 'numeric' }
  ];

  const rows = seleccion.map(p => {
    const historiales = obtenerHistorialesPaciente(p);
    const ult = historiales[0] || null;
    return {
      CODIGO: p.codigo,
      CEDULA: p.cedula || '',
      NOMBRE: p.nombre,
      FECHANAC: p.fechaNac,
      EDAD: parseInt(calcAgeStr(p.fechaNac), 10),
      SEXO: p.sexo,
      ESTAMENT: p.estamento,
      FACULTAD: p.facultad,
      HISTORLS: historiales.length,
      TAS: ult ? (ult.tas || 0) : (p.tas || 0),
      TSI: ult ? (ult.tsi || 0) : (p.tsi || 0)
    };
  });

  const blob = buildSavFile(columns, rows);
  descargarBlob(blob, 'directorio_pacientes_cardiounemi.sav');
}

// Impresión y descarga oficial en PDF de la Ficha Clínica (HU-17)
function exportarPDFHistorial(pacienteId, historialId) {
  // Descarga directa del PDF oficial generado por el backend
  window.open(`/clinical/ficha/pdf/?paciente=${encodeURIComponent(pacienteId)}`, '_blank');
}

// Impresión PDF del resumen del paciente con sus historiales
function exportarPDFPaciente(pacienteId) {
  const p = pacientes.find(item => item.id === pacienteId);
  if (!p) return;

  const historiales = obtenerHistorialesPaciente(p);
  const printContainer = document.getElementById('printFormsContainer');

  const filasHistoriales = historiales.map(h => `
    <tr style="border-bottom:1px solid #e2e8f0;">
      <td style="padding:8px 6px;"><strong>#${h.numeroVisita}</strong></td>
      <td style="padding:8px 6px;">${formatearFechaLegible(h.fechaVisita)}</td>
      <td style="padding:8px 6px;">${h.tipo}</td>
      <td style="padding:8px 6px;">${h.tas || '--'}/${h.tsi || '--'} mmHg</td>
      <td style="padding:8px 6px;">${h.peso || '--'} kg</td>
      <td style="padding:8px 6px;">${h.imc || calcIMCValor(h.peso, h.talla)}</td>
      <td style="padding:8px 6px;"><strong>${h.riesgoGlobal || 'Bajo'}</strong></td>
    </tr>
  `).join('');

  printContainer.innerHTML = `
    <section class="print-form-page">
      <div class="print-form-brand">CARDIOUNEMI — Universidad Estatal de Milagro · Departamento de Cardiología</div>
      <h1 class="print-form-heading">Expediente Clínico del Paciente y Cronología de Consultas</h1>

      <div class="print-form-grid" style="margin-bottom:20px;">
        <div class="print-field">
          <span class="print-field-label">Código del Paciente</span>
          <span class="print-field-value">${p.codigo}</span>
        </div>
        <div class="print-field">
          <span class="print-field-label">Cédula</span>
          <span class="print-field-value">${p.cedula || '0900000000'}</span>
        </div>
        <div class="print-field print-field-full">
          <span class="print-field-label">Nombre y Apellidos</span>
          <span class="print-field-value">${p.nombre}</span>
        </div>
        <div class="print-field">
          <span class="print-field-label">Edad / Sexo</span>
          <span class="print-field-value">${calcAgeStr(p.fechaNac)} · ${p.sexo === 'H' ? 'Hombre' : 'Mujer'}</span>
        </div>
        <div class="print-field">
          <span class="print-field-label">Estamento / Facultad</span>
          <span class="print-field-value">${p.estamento} · ${p.facultad}</span>
        </div>
        <div class="print-field print-field-full">
          <span class="print-field-label">Contacto</span>
          <span class="print-field-value">${p.telefono || 'Sin teléfono'} · ${p.correo || 'Sin correo'}</span>
        </div>
      </div>

      <h3 style="font-size:1.05rem; color:#0f172a; border-bottom:1.5px solid #cbd5e1; padding-bottom:6px; margin-top:20px;">
        Historial Clínico Único (Ficha Médica)
      </h3>

      <table style="width:100%; border-collapse:collapse; font-size:0.82rem; margin-top:10px;">
        <thead>
          <tr style="background:#f8fafc; border-bottom:2px solid #cbd5e1; text-align:left;">
            <th style="padding:6px;">Historial</th>
            <th style="padding:6px;">Fecha</th>
            <th style="padding:6px;">Tipo de Ficha</th>
            <th style="padding:6px;">PA</th>
            <th style="padding:6px;">Peso</th>
            <th style="padding:6px;">IMC</th>
            <th style="padding:6px;">Riesgo</th>
          </tr>
        </thead>
        <tbody>
          ${filasHistoriales}
        </tbody>
      </table>

      <div class="print-form-footer">Documento generado el ${new Date().toLocaleString('es-EC')} — Sistema CARDIOUNEMI</div>
    </section>
  `;

  window.print();
}

function exportarPDFPacienteActivo() {
  if (pacienteActivoExpediente) {
    exportarPDFPaciente(pacienteActivoExpediente.id);
  }
}
