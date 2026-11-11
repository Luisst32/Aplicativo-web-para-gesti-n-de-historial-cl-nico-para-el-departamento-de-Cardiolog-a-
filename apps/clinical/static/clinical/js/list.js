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
    actualizarOpcionesFiltrosDinamicos();
    renderPacientesTabla();
    abrirHistorialesPaciente(nuevoPaciente.id);
  });

  // Cargar cohorte real desde base de datos PostgreSQL (HU-15)
  await cargarPacientesDesdeServidor();
  actualizarOpcionesFiltrosDinamicos();

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
      cerrarModalExportar();
    }
  });
});

// =========================================================================
// FILTRADO Y ORDENAMIENTO DE PACIENTES
// =========================================================================

/**
 * Detecta dinámicamente los años, estamentos y opciones presentes en la cohorte
 * y en el formulario clínico, asegurando que años futuros (ej. 2027) o años
 * agregados aparezcan automáticamente en los desplegables de filtrado.
 */
function actualizarOpcionesFiltrosDinamicos() {
  const selAnio = document.getElementById('filtroAnio');
  const selEstamento = document.getElementById('filtroEstamento');
  if (!selAnio && !selEstamento) return;

  // 1. DINAMISMO PARA FILTRO DE AÑO
  if (selAnio) {
    const anioSeleccionado = selAnio.value || 'all';
    const aniosSet = new Set();

    // Años estándar base: año actual y año siguiente (ej. 2026, 2027)
    const curYear = new Date().getFullYear();
    aniosSet.add(curYear);
    aniosSet.add(curYear + 1);

    // Leer opciones ya precargadas en el DOM
    Array.from(selAnio.options).forEach(opt => {
      const valInt = parseInt(opt.value, 10);
      if (!isNaN(valInt) && valInt > 1900 && valInt < 2200) {
        aniosSet.add(valInt);
      }
    });

    // Detectar años existentes en la cohorte de pacientes
    if (Array.isArray(pacientes)) {
      pacientes.forEach(p => {
        const yP = anioDePaciente(p);
        if (yP && !isNaN(yP) && yP > 1900 && yP < 2200) {
          aniosSet.add(yP);
        }
        if (Array.isArray(p.historiales)) {
          p.historiales.forEach(h => {
            if (h && h.fechaVisita) {
              const yH = parseInt(String(h.fechaVisita).substring(0, 4), 10);
              if (!isNaN(yH) && yH > 1900 && yH < 2200) {
                aniosSet.add(yH);
              }
            }
          });
        }
        if (p.codigo && p.codigo.includes('/')) {
          const yCod = parseInt(p.codigo.split('/')[1], 10);
          if (!isNaN(yCod) && yCod > 1900 && yCod < 2200) {
            aniosSet.add(yCod);
          }
        }
      });
    }

    const aniosOrdenados = Array.from(aniosSet).sort((a, b) => b - a);

    selAnio.innerHTML = '<option value="all">Todos los Años</option>';
    aniosOrdenados.forEach(a => {
      const opt = document.createElement('option');
      opt.value = String(a);
      opt.textContent = String(a);
      selAnio.appendChild(opt);
    });

    if (anioSeleccionado && Array.from(selAnio.options).some(o => o.value === anioSeleccionado)) {
      selAnio.value = anioSeleccionado;
    } else {
      selAnio.value = 'all';
    }
  }

  // 2. DINAMISMO PARA FILTRO DE ESTAMENTO
  if (selEstamento) {
    const estamentoSeleccionado = (selEstamento.value || 'all').toUpperCase();
    const estamentosMap = new Map();

    const labelsConocidos = {
      'PDI': 'PDI (Docentes)',
      'AD': 'AD (Administrativos)',
      'PAS': 'PAS (Personal de Adm. y Servicios)',
      'SERVICIO': 'SERVICIO (Apoyo)',
      'ESTUDIANTES': 'ESTUDIANTES'
    };

    ['PDI', 'AD', 'PAS', 'SERVICIO', 'ESTUDIANTES'].forEach(code => {
      estamentosMap.set(code, labelsConocidos[code] || code);
    });

    // Leer opciones ya precargadas en el DOM
    Array.from(selEstamento.options).forEach(opt => {
      if (opt.value && opt.value !== 'all') {
        const cod = opt.value.trim().toUpperCase();
        if (!estamentosMap.has(cod)) {
          estamentosMap.set(cod, opt.textContent.trim() || cod);
        }
      }
    });

    // Detectar estamentos presentes en los pacientes cargados
    if (Array.isArray(pacientes)) {
      pacientes.forEach(p => {
        if (p && p.estamento && typeof p.estamento === 'string') {
          const cod = p.estamento.trim().toUpperCase();
          if (cod && !estamentosMap.has(cod)) {
            estamentosMap.set(cod, labelsConocidos[cod] || cod);
          }
        }
      });
    }

    const sortedCodes = Array.from(estamentosMap.keys()).sort();

    selEstamento.innerHTML = '<option value="all">Todos los Estamentos</option>';
    sortedCodes.forEach(code => {
      const opt = document.createElement('option');
      opt.value = code;
      opt.textContent = estamentosMap.get(code) || code;
      selEstamento.appendChild(opt);
    });

    if (estamentoSeleccionado && Array.from(selEstamento.options).some(o => o.value.toUpperCase() === estamentoSeleccionado)) {
      selEstamento.value = estamentoSeleccionado;
    } else {
      selEstamento.value = 'all';
    }
  }
}

function obtenerPacientesFiltrados() {
  const q = document.getElementById('filtroBusqueda').value.trim().toLowerCase();
  const anio = document.getElementById('filtroAnio').value;
  const estamento = (document.getElementById('filtroEstamento').value || 'all').toUpperCase();
  const sexo = (document.getElementById('filtroSexo').value || 'all').toUpperCase();

  const filtrados = pacientes.filter(p => {
    const cedula = (p.cedula || '').toLowerCase();
    const codigo = (p.codigo || '').toLowerCase();
    const nombre = (p.nombre || '').toLowerCase();
    const facultad = (p.facultad || '').toLowerCase();

    const matchQuery = !q || nombre.includes(q) || codigo.includes(q) || cedula.includes(q) || facultad.includes(q);

    const anioPac = String(anioDePaciente(p));
    const historiales = p.historiales || [];
    const matchAnio = anio === 'all' || anioPac === anio || historiales.some(h => (h.fechaVisita || '').startsWith(anio));

    const pEstamento = (p.estamento || '').trim().toUpperCase();
    const matchEstamento = estamento === 'all' || pEstamento === estamento;

    const pSexo = (p.sexo || '').trim().toUpperCase();
    const matchSexo = sexo === 'all' || pSexo === sexo;

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
    <td class="td-acciones" style="text-align: right; padding-right: 18px;" onclick="event.stopPropagation()">
      <button type="button" class="btn btn-sm btn-icon-eliminar" onclick="solicitarEliminarFicha('${p.id}', '${p.nombre}', '${p.codigo}')" title="Eliminar ficha clínica de ${p.nombre}">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
      </button>
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
          <span><strong>Evaluador:</strong> ${h.medico || 'Médico Especialista'}</span>
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
        <button type="button" class="btn btn-sm btn-outline-danger" onclick="solicitarEliminarFicha('${p.id}', '${p.nombre}', '${p.codigo}')" title="Eliminar ficha clínica">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
          <span>Eliminar Ficha</span>
        </button>
      </div>
    `;

    containerTimeline.appendChild(cardH);
  });

  // 4. Actualizar URL de forma limpia en el historial del navegador
  try {
    const baseListPath = window.location.pathname === '/' ? '/' : '/clinical/listado/';
    history.replaceState(null, '', `${baseListPath}?paciente=${encodeURIComponent(p.id)}`);
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
    const baseListPath = window.location.pathname === '/' ? '/' : '/clinical/listado/';
    history.replaceState(null, '', baseListPath);
  } catch (err) {}

  renderPacientesTabla();
  window.scrollTo({ top: 0, behavior: 'smooth' });
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

  const btnEliminarSel = document.getElementById('btnEliminarSeleccionados');
  const countEliminarSel = document.getElementById('countSeleccionadosEliminar');
  if (btnEliminarSel) {
    if (seleccionados.size > 0) {
      btnEliminarSel.style.display = 'inline-flex';
      if (countEliminarSel) countEliminarSel.textContent = seleccionados.size;
    } else {
      btnEliminarSel.style.display = 'none';
    }
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
  const formato = document.querySelector('input[name="exportFormato"]:checked')?.value || 'sav';
  const totalRegistros = pacs.length;

  const preview = document.getElementById('exportPreviewText');
  if (preview) {
    const etiquetaFormato = formato === 'sav' ? 'SPSS Statistics (.sav)' : 'Excel / CSV (.csv)';
    preview.innerHTML = `Se exportarán <strong>${totalRegistros} paciente(s)</strong> en formato <strong>${etiquetaFormato}</strong> con las <strong>342 columnas completas</strong> de la base de datos de Cardiología UNEMI.`;
  }
}

async function ejecutarExportacionInteligente() {
  const pacs = obtenerPacientesSegunAlcance();
  if (!pacs || pacs.length === 0) {
    alert('No hay pacientes que coincidan con el alcance seleccionado.');
    return;
  }

  const formato = document.querySelector('input[name="exportFormato"]:checked')?.value || 'sav';
  const alcance = document.querySelector('input[name="exportAlcance"]:checked')?.value || 'todos';
  const patientIds = alcance === 'todos' ? [] : pacs.map(p => p.id);

  const btnTxt = document.getElementById('btnTxtDescargar');
  const btn = document.querySelector('.btn-ejecutar-exportacion');
  if (btn) btn.disabled = true;
  if (btnTxt) btnTxt.textContent = 'Generando dataset oficial (342 columnas)...';

  try {
    const csrfToken = (typeof getCsrfToken === 'function') ? getCsrfToken() : (
      document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
      document.cookie.split('; ').find(r => r.startsWith('csrftoken='))?.split('=')[1] || ''
    );

    const res = await fetch('/clinical/api/export-dataset/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify({
        patient_ids: patientIds,
        format: formato,
        scope: alcance
      })
    });

    if (!res.ok) {
      const errJson = await res.json().catch(() => null);
      throw new Error((errJson && errJson.error) || `Error HTTP ${res.status}`);
    }

    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition') || '';
    let filename = formato === 'sav' ? 'Base_datos_Unemi_CardioUnemi.sav' : 'Base_datos_Unemi_CardioUnemi.csv';
    const match = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
    if (match && match[1]) {
      filename = match[1].replace(/['"]/g, '').trim();
    }

    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    a.remove();

    if (btnTxt) btnTxt.textContent = '¡Descarga lista!';
    setTimeout(() => {
      if (btnTxt) btnTxt.textContent = 'Descargar Archivo';
      if (btn) btn.disabled = false;
      cerrarModalExportar();
    }, 700);

  } catch (err) {
    alert('Error al exportar dataset: ' + err.message);
    if (btnTxt) btnTxt.textContent = 'Descargar Archivo';
    if (btn) btn.disabled = false;
  }
}

// Impresión y descarga oficial en PDF de la Ficha Clínica (HU-17)
function exportarPDFHistorial(pacienteId, historialId) {
  let url = `/clinical/ficha/pdf/?paciente=${encodeURIComponent(pacienteId)}`;
  if (historialId) {
    url += `&historial=${encodeURIComponent(historialId)}`;
  }
  window.open(url, '_blank');
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
