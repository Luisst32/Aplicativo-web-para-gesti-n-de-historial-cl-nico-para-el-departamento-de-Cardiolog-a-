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
    window.location.assign(`/clinical/formulario/?paciente=${encodeURIComponent(nuevoPaciente.id)}`);
  });

  // Cargar cohorte real desde base de datos PostgreSQL (HU-15)
  await cargarPacientesDesdeServidor();
  actualizarOpcionesFiltrosDinamicos();

  // Si la URL contiene ?paciente=<id>, filtrar en el buscador del listado sin bucle de redirección
  const params = new URLSearchParams(window.location.search);
  const idPacienteUrl = params.get('paciente');
  if (idPacienteUrl) {
    const pacienteEncontrado = pacientes.find(p => p.id === idPacienteUrl);
    const filtroInp = document.getElementById('filtroBusqueda');
    if (pacienteEncontrado && filtroInp) {
      filtroInp.value = pacienteEncontrado.codigo || pacienteEncontrado.nombre;
    }
  }
  renderPacientesTabla();

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
 * Detecta de forma inteligente y exclusiva los años y estamentos presentes
 * en las fechas y registros de los pacientes que existen en la cohorte.
 * Si no hay pacientes de 2027, 2027 NO aparece; si se agrega uno con 2027,
 * se incorpora de inmediato.
 */
function actualizarOpcionesFiltrosDinamicos() {
  const selAnio = document.getElementById('filtroAnio');
  const selEstamento = document.getElementById('filtroEstamento');
  if (!selAnio && !selEstamento) return;

  // 1. DINAMISMO INTELIGENTE PARA FILTRO DE AÑO
  // Solo se agregan los años reales de las visitas/fichas de pacientes que existen
  if (selAnio) {
    const anioSeleccionado = selAnio.value || 'all';
    const aniosSet = new Set();

    // Detectar exclusivamente años presentes en los pacientes y sus historiales
    if (Array.isArray(pacientes) && pacientes.length > 0) {
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
    } else {
      // Si aún no se cargaron pacientes, tomar las opciones del HTML renderizado por el servidor
      Array.from(selAnio.options).forEach(opt => {
        const valInt = parseInt(opt.value, 10);
        if (!isNaN(valInt) && valInt > 1900 && valInt < 2200) {
          aniosSet.add(valInt);
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

  // 2. DINAMISMO INTELIGENTE PARA FILTRO DE ESTAMENTO
  // Solo se agregan los estamentos reales de los pacientes que existen
  if (selEstamento) {
    const rawVal = selEstamento.value ? selEstamento.value.trim() : 'all';
    const estamentoSeleccionado = (!rawVal || rawVal.toLowerCase() === 'all') ? 'all' : rawVal;
    const estamentosMap = new Map();

    const labelsConocidos = {
      'PDI': 'PDI (Docentes)',
      'AD': 'AD (Administrativos)',
      'PAS': 'PAS (Personal de Adm. y Servicios)',
      'SERVICIO': 'SERVICIO (Apoyo)',
      'ESTUDIANTES': 'ESTUDIANTES'
    };

    // Detectar estamentos presentes en los pacientes existentes
    if (Array.isArray(pacientes) && pacientes.length > 0) {
      pacientes.forEach(p => {
        if (p && p.estamento && typeof p.estamento === 'string') {
          const cod = p.estamento.trim();
          if (cod && !estamentosMap.has(cod.toUpperCase())) {
            estamentosMap.set(cod.toUpperCase(), {
              code: cod,
              label: labelsConocidos[cod.toUpperCase()] || cod
            });
          }
        }
      });
    } else {
      // Tomar opciones del HTML renderizado por el servidor
      Array.from(selEstamento.options).forEach(opt => {
        if (opt.value && opt.value.toLowerCase() !== 'all') {
          const cod = opt.value.trim();
          if (!estamentosMap.has(cod.toUpperCase())) {
            estamentosMap.set(cod.toUpperCase(), {
              code: cod,
              label: opt.textContent.trim() || labelsConocidos[cod.toUpperCase()] || cod
            });
          }
        }
      });
    }

    selEstamento.innerHTML = '<option value="all">Todos los Estamentos</option>';
    Array.from(estamentosMap.values()).sort((a, b) => a.code.localeCompare(b.code)).forEach(item => {
      const opt = document.createElement('option');
      opt.value = item.code;
      opt.textContent = item.label;
      selEstamento.appendChild(opt);
    });

    if (estamentoSeleccionado !== 'all') {
      const matchOpt = Array.from(selEstamento.options).find(o => o.value.toUpperCase() === estamentoSeleccionado.toUpperCase());
      if (matchOpt) {
        selEstamento.value = matchOpt.value;
      } else {
        selEstamento.value = 'all';
      }
    } else {
      selEstamento.value = 'all';
    }
  }
}

function obtenerPacientesFiltrados() {
  const q = document.getElementById('filtroBusqueda').value.trim().toLowerCase();
  const anio = (document.getElementById('filtroAnio').value || 'all').trim();
  const rawEstamento = (document.getElementById('filtroEstamento').value || 'all').trim();
  const rawSexo = (document.getElementById('filtroSexo').value || 'all').trim();

  const isEstamentoAll = !rawEstamento || rawEstamento.toLowerCase() === 'all';
  const isSexoAll = !rawSexo || rawSexo.toLowerCase() === 'all';
  const isAnioAll = !anio || anio.toLowerCase() === 'all';

  const estamento = isEstamentoAll ? 'all' : rawEstamento.toUpperCase();
  const sexo = isSexoAll ? 'all' : rawSexo.toUpperCase();

  const filtrados = pacientes.filter(p => {
    const cedula = (p.cedula || '').toLowerCase();
    const codigo = (p.codigo || '').toLowerCase();
    const nombre = (p.nombre || '').toLowerCase();
    const facultad = (p.facultad || '').toLowerCase();

    const matchQuery = !q || nombre.includes(q) || codigo.includes(q) || cedula.includes(q) || facultad.includes(q);

    const anioPac = String(anioDePaciente(p));
    const historiales = p.historiales || [];
    const matchAnio = isAnioAll || anioPac === anio || historiales.some(h => (h.fechaVisita || '').startsWith(anio));

    const pEstamento = (p.estamento || '').trim().toUpperCase();
    const matchEstamento = isEstamentoAll || pEstamento === estamento;

    const pSexo = (p.sexo || '').trim().toUpperCase();
    const matchSexo = isSexoAll || pSexo === sexo || (sexo === 'H' && pSexo.startsWith('H')) || (sexo === 'M' && pSexo.startsWith('M'));

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

  const privacidad = typeof esModoPrivacidadActivo === 'function' && esModoPrivacidadActivo();
  const nombreMostrar = privacidad ? `Paciente ${p.codigo || p.id}` : p.nombre;
  const inits = privacidad ? `P${p.codigo || ''}` : inicialesDe(p.nombre);
  const cedulaMostrar = privacidad ? (typeof censurarCedula === 'function' ? censurarCedula(p.cedula) : '09******00') : (p.cedula || '0900000000');
  const contactoMostrar = privacidad ? '' : (p.correo || (p.telefono ? 'Tel: ' + p.telefono : 'UNEMI'));

  const historiales = obtenerHistorialesPaciente(p);
  const ultHistorial = historiales[0] || null;
  const fechaUltima = ultHistorial ? formatearFechaLegible(ultHistorial.fechaVisita) : '--';

  tr.innerHTML = `
    <td class="td-check" onclick="event.stopPropagation()">
      <input type="checkbox" data-id="${escapeHtml(p.id)}" ${seleccionados.has(p.id) ? 'checked' : ''}>
    </td>
    <td>
      <div class="celda-paciente">
        <div class="avatar-paciente">${escapeHtml(inits)}</div>
        <div class="info-paciente">
          <span class="nombre-paciente" title="Abrir ficha clínica de este paciente"><span style="display:inline-block; min-width:24px; padding:2px 8px; margin-right:8px; border-radius:6px; background:#eff6ff; color:#1d4ed8; font-size:0.82rem; font-weight:800; border:1px solid #bfdbfe;">#${escapeHtml(p.codigo)}</span>${escapeHtml(nombreMostrar)}</span>
          <div class="meta-secundaria">
            <span>C.I: ${escapeHtml(cedulaMostrar)}</span>
            ${privacidad ? '' : `<span>·</span><span>${escapeHtml(contactoMostrar)}</span>`}
          </div>
        </div>
      </div>
    </td>
    <td class="td-acciones" style="text-align: right; padding-right: 18px;" onclick="event.stopPropagation()">
      <button type="button" class="btn btn-sm btn-icon-eliminar" data-clinical-action="delete" title="Eliminar ficha clínica de ${escapeHtml(nombreMostrar)}">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
      </button>
    </td>
  `;

  // Al hacer clic en la fila se abre el expediente en la página (sin modal)
  tr.querySelector('input[type="checkbox"]').addEventListener('change', event => {
    toggleSeleccion(p.id, event.target.checked);
  });
  tr.querySelector('[data-clinical-action="delete"]').addEventListener('click', () => {
    solicitarEliminarFicha(p.id, p.nombre, p.codigo);
  });
  tr.addEventListener('click', () => {
    window.location.assign(`/clinical/formulario/?paciente=${encodeURIComponent(p.id)}`);
  });

  return tr;
}

function abrirHistorialesPaciente(pacienteId) {
  const p = pacientes.find(item => item.id === pacienteId);
  if (!p) return;
  const containerTimeline = document.getElementById('timelineHistoriales');
  if (containerTimeline) {
    containerTimeline.innerHTML = '';
    const historiales = obtenerHistorialesPaciente(p);
    historiales.forEach(h => {
      const cardH = document.createElement('div');
      cardH.className = 'historial-card-item';
      cardH.innerHTML = `
        <span class="historial-tag-numero">${escapeHtml(h.numeroVisita)}</span>
        <span>${escapeHtml(h.medico || '')}</span>
        <button type="button" data-clinical-action="export">PDF</button>
        <button type="button" data-clinical-action="delete">Eliminar</button>
      `;
      cardH.querySelector('[data-clinical-action="delete"]').addEventListener('click', () => {
        if (typeof solicitarEliminarFicha === 'function') solicitarEliminarFicha(p.id, p.nombre, p.codigo);
      });
      containerTimeline.appendChild(cardH);
    });
  }
}
window.abrirHistorialesPaciente = abrirHistorialesPaciente;

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

  const btnEnviarCorreo = document.getElementById('btnEnviarCorreoSeleccionados');
  const countEnviarCorreo = document.getElementById('countSeleccionadosCorreo');
  if (btnEnviarCorreo) {
    if (seleccionados.size > 0) {
      btnEnviarCorreo.style.display = 'inline-flex';
      if (countEnviarCorreo) countEnviarCorreo.textContent = seleccionados.size;
    } else {
      btnEnviarCorreo.style.display = 'none';
    }
  }

  const btnDescargarZip = document.getElementById('btnDescargarPdfsSeleccionados');
  const countDescargarZip = document.getElementById('countSeleccionadosDescargar');
  if (btnDescargarZip) {
    if (seleccionados.size > 0) {
      btnDescargarZip.style.display = 'inline-flex';
      if (countDescargarZip) countDescargarZip.textContent = seleccionados.size;
    } else {
      btnDescargarZip.style.display = 'none';
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

// Descarga en lote de las fichas clínicas seleccionadas en PDF o ZIP
function descargarPDFsSeleccionados() {
  const arr = Array.from(seleccionados);
  if (arr.length === 0) {
    if (typeof mostrarNotificacion === 'function') {
      mostrarNotificacion('Seleccione al menos una ficha clínica para descargar.', 'warning');
    } else {
      alert('Seleccione al menos una ficha clínica para descargar.');
    }
    return;
  }
  const url = `/clinical/api/ficha/descargar-seleccionados/?patient_ids=${encodeURIComponent(arr.join(','))}`;
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
      <td style="padding:8px 6px;"><strong>#${escapeHtml(h.numeroVisita)}</strong></td>
      <td style="padding:8px 6px;">${escapeHtml(formatearFechaLegible(h.fechaVisita))}</td>
      <td style="padding:8px 6px;">${escapeHtml(h.tipo)}</td>
      <td style="padding:8px 6px;">${escapeHtml(h.tas || '--')}/${escapeHtml(h.tsi || '--')} mmHg</td>
      <td style="padding:8px 6px;">${escapeHtml(h.peso || '--')} kg</td>
      <td style="padding:8px 6px;">${escapeHtml(h.imc || calcIMCValor(h.peso, h.talla))}</td>
      <td style="padding:8px 6px;"><strong>${escapeHtml(h.riesgoGlobal || 'Bajo')}</strong></td>
    </tr>
  `).join('');

  printContainer.innerHTML = `
    <section class="print-form-page">
      <div class="print-form-brand">CARDIOUNEMI — Universidad Estatal de Milagro · Departamento de Cardiología</div>
      <h1 class="print-form-heading">Expediente Clínico del Paciente y Cronología de Consultas</h1>

      <div class="print-form-grid" style="margin-bottom:20px;">
        <div class="print-field">
          <span class="print-field-label">Código del Paciente</span>
          <span class="print-field-value">${escapeHtml(p.codigo)}</span>
        </div>
        <div class="print-field">
          <span class="print-field-label">Cédula</span>
          <span class="print-field-value">${escapeHtml(p.cedula || '0900000000')}</span>
        </div>
        <div class="print-field print-field-full">
          <span class="print-field-label">Nombre y Apellidos</span>
          <span class="print-field-value">${escapeHtml(p.nombre)}</span>
        </div>
        <div class="print-field">
          <span class="print-field-label">Edad / Sexo</span>
          <span class="print-field-value">${escapeHtml(calcAgeStr(p.fechaNac))} · ${escapeHtml(p.sexo === 'H' ? 'Hombre' : 'Mujer')}</span>
        </div>
        <div class="print-field">
          <span class="print-field-label">Estamento / Facultad</span>
          <span class="print-field-value">${escapeHtml(p.estamento)} · ${escapeHtml(p.facultad)}</span>
        </div>
        <div class="print-field print-field-full">
          <span class="print-field-label">Contacto</span>
          <span class="print-field-value">${escapeHtml(p.telefono || 'Sin teléfono')} · ${escapeHtml(p.correo || 'Sin correo')}</span>
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

      <div class="print-form-footer">Documento generado el ${escapeHtml(new Date().toLocaleString('es-EC'))} — Sistema CARDIOUNEMI</div>
    </section>
  `;

  window.print();
}

// =========================================================================
// ENVÍO DE ENLACE SEGURO CON CÓDIGO TEMPORAL (FLUJO SECURE SHARE)
// =========================================================================

// Memoria estrictamente efímera de códigos (NUNCA en localStorage/sessionStorage)
let codigosAccesoEnMemoria = [];
let codigosCopiadosSet = new Set();

function actualizarContadorNotas(textarea) {
  const countEl = document.getElementById('correoNotasCharCount');
  if (countEl && textarea) {
    countEl.textContent = `${textarea.value.length} / 300`;
  }
}

function limpiarMemoriaCodigos() {
  codigosAccesoEnMemoria = [];
  codigosCopiadosSet.clear();
  const listEl = document.getElementById('listaCodigosGenerados');
  if (listEl) listEl.innerHTML = '';
}

function abrirModalEnviarCorreo() {
  const modal = document.getElementById('modalEnviarFichaCorreo');
  if (!modal) return;

  const arrSeleccionados = Array.from(seleccionados);
  if (arrSeleccionados.length === 0) {
    if (typeof mostrarNotificacion === 'function') {
      mostrarNotificacion('Seleccione una ficha clínica para generar el enlace seguro.', 'warning');
    } else {
      alert('Seleccione una ficha clínica para generar el enlace seguro.');
    }
    return;
  }

  // Limpiar códigos previos en memoria y reiniciar vistas
  limpiarMemoriaCodigos();
  const vistaForm = document.getElementById('vistaFormularioEnvioCorreo');
  const vistaRes = document.getElementById('vistaResultadosCodigos');
  if (vistaForm) vistaForm.style.display = 'flex';
  if (vistaRes) vistaRes.style.display = 'none';

  const resumenEl = document.getElementById('correoResumenFichas');
  const inputDest = document.getElementById('correoDestinatariosInput');
  const inputAsunto = document.getElementById('correoAsuntoInput');
  const inputNotas = document.getElementById('correoNotasInput');
  const selectCad = document.getElementById('correoCaducidadSelect');
  const alerta = document.getElementById('correoAlertaEstado');

  if (alerta) alerta.style.display = 'none';
  if (selectCad) selectCad.value = '48';
  if (inputNotas) {
    inputNotas.value = '';
    actualizarContadorNotas(inputNotas);
  }

  // Asunto estrictamente GENÉRICO (sin datos del participante)
  if (inputAsunto) {
    inputAsunto.value = 'Documento disponible en portal seguro';
  }

  if (arrSeleccionados.length === 1) {
    const pSel = pacientes.find(p => String(p.id) === String(arrSeleccionados[0]));
    if (resumenEl) {
      resumenEl.innerHTML = `Se generará un enlace protegido con código de acceso para <strong>1 ficha clínica</strong>.`;
    }
    if (inputDest) {
      inputDest.value = (pSel && (pSel.correo || pSel.email)) ? (pSel.correo || pSel.email) : '';
    }
  } else {
    if (resumenEl) {
      resumenEl.innerHTML = `Se generarán enlaces protegidos con código de acceso para <strong>${arrSeleccionados.length} fichas clínicas</strong> (descargables en .ZIP comprimido o por separado).`;
    }
    if (inputDest) {
      const correos = pacientes
        .filter(p => (seleccionados.has(p.id) || seleccionados.has(String(p.id))) && (p.correo || p.email))
        .map(p => p.correo || p.email)
        .slice(0, 5);
      inputDest.value = correos.join(', ');
    }
  }

  modal.style.display = 'flex';
  if (inputDest) setTimeout(() => inputDest.focus(), 150);
}

function cerrarModalEnviarCorreo() {
  limpiarMemoriaCodigos();
  const modal = document.getElementById('modalEnviarFichaCorreo');
  if (modal) modal.style.display = 'none';
}

async function ejecutarEnvioCorreoFicha() {
  const inputDest = document.getElementById('correoDestinatariosInput');
  const inputAsunto = document.getElementById('correoAsuntoInput');
  const inputNotas = document.getElementById('correoNotasInput');
  const selectCad = document.getElementById('correoCaducidadSelect');
  const btnEnviar = document.getElementById('btnEjecutarEnvioCorreo');
  const btnTxt = document.getElementById('btnTxtEnviarCorreo');
  const alerta = document.getElementById('correoAlertaEstado');

  const destVal = (inputDest?.value || '').trim();
  if (!destVal) {
    if (alerta) {
      alerta.style.display = 'block';
      alerta.style.background = '#fef2f2';
      alerta.style.color = '#991b1b';
      alerta.style.border = '1px solid #fecaca';
      alerta.textContent = 'Por favor ingrese al menos una dirección de correo válida.';
    }
    inputDest?.focus();
    return;
  }

  const destinatarios = destVal.split(',').map(s => s.trim()).filter(Boolean);
  if (destinatarios.length > 5) {
    if (alerta) {
      alerta.style.display = 'block';
      alerta.style.background = '#fef2f2';
      alerta.style.color = '#991b1b';
      alerta.style.border = '1px solid #fecaca';
      alerta.textContent = 'No puede ingresar más de 5 correos destinatarios por envío.';
    }
    inputDest?.focus();
    return;
  }

  const arrSeleccionados = Array.from(seleccionados);
  const durationHours = parseInt(selectCad?.value || '48', 10);
  const notasSanitizadas = (inputNotas?.value || '').slice(0, 300);

  // Estado de carga en el botón
  if (btnEnviar) btnEnviar.disabled = true;
  if (btnTxt) btnTxt.textContent = 'Generando enlaces y enviando...';
  if (alerta) {
    alerta.style.display = 'block';
    alerta.style.background = '#f0f9ff';
    alerta.style.color = '#0369a1';
    alerta.style.border = '1px solid #bae6fd';
    alerta.textContent = 'Creando tokens con hash SHA-256, códigos de 6 dígitos y enviando notificaciones seguras...';
  }

  try {
    const csrftoken = (document.cookie.split('; ').find(row => row.startsWith('csrftoken=')) || '').split('=')[1] || '';

    const resp = await fetch('/clinical/api/ficha/enviar-correo/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrftoken
      },
      body: JSON.stringify({
        patient_ids: arrSeleccionados,
        recipients: destinatarios,
        duration_hours: durationHours,
        subject: inputAsunto?.value || 'Documento disponible en portal seguro',
        notes: notasSanitizadas
      })
    });

    let data = null;
    try {
      data = await resp.json();
    } catch (parseErr) {
      const errText = await resp.text().catch(() => '');
      throw new Error(`Error del servidor (${resp.status}): ${errText || 'No se pudo procesar la respuesta'}`);
    }

    if (resp.ok && data && data.success) {
      // Guardar códigos estrictamente en memoria volátil
      codigosAccesoEnMemoria = data.results || [];
      codigosCopiadosSet.clear();

      // Renderizar vista de resultados con códigos
      renderizarResultadosCodigos(data.results || []);

      // Cambiar a Vista 2 dentro del modal
      const vistaForm = document.getElementById('vistaFormularioEnvioCorreo');
      const vistaRes = document.getElementById('vistaResultadosCodigos');
      if (vistaForm) vistaForm.style.display = 'none';
      if (vistaRes) vistaRes.style.display = 'flex';

      if (typeof mostrarNotificacion === 'function') {
        mostrarNotificacion(data.message || 'Enlaces seguros generados exitosamente.', 'success');
      }
    } else {
      throw new Error((data && data.error) || 'Ocurrió un error al despachar los enlaces seguros.');
    }
  } catch (err) {
    if (alerta) {
      alerta.style.display = 'block';
      alerta.style.background = '#fef2f2';
      alerta.style.color = '#991b1b';
      alerta.style.border = '1px solid #fecaca';
      alerta.textContent = `Error: ${err.message}`;
    }
  } finally {
    if (btnEnviar) btnEnviar.disabled = false;
    if (btnTxt) btnTxt.textContent = 'Enviar enlace seguro';
  }
}

function renderizarResultadosCodigos(results) {
  const container = document.getElementById('listaCodigosGenerados');
  if (!container) return;

  container.innerHTML = '';

  results.forEach((r, idx) => {
    const card = document.createElement('div');
    card.style.cssText = 'background: #f8fafc; border: 1.5px solid #e2e8f0; border-radius: 10px; padding: 14px 16px; display: flex; flex-direction: column; gap: 8px;';

    if (r.success && r.code) {
      card.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
          <div style="font-size:0.84rem; font-weight:700; color:#1e293b;">
            ✉️ ${escapeHtml(r.email)}
          </div>
          <span style="font-size:0.75rem; color:#059669; background:#ecfdf5; border:1px solid #a7f3d0; padding:2px 8px; border-radius:12px; font-weight:600;">
            Enviado con éxito
          </span>
        </div>

        <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; background:#ffffff; border:1px solid #cbd5e1; border-radius:8px; padding:10px 14px;">
          <div>
            <div style="font-size:0.7rem; color:#64748b; font-weight:700; text-transform:uppercase; letter-spacing:0.5px;">Código de Acceso</div>
            <div style="font-family:'JetBrains Mono', monospace, courier; font-size:1.6rem; font-weight:800; letter-spacing:5px; color:#0f172a;" id="codeText_${escapeHtml(idx)}">
              ${escapeHtml(r.code)}
            </div>
          </div>
          <button type="button" class="btn" data-copy-code style="display:inline-flex; align-items:center; gap:6px; padding:8px 14px; font-size:0.82rem; font-weight:700; border-radius:6px; border:1px solid #0284c7; background:#0284c7; color:#ffffff; cursor:pointer; transition:all 0.15s ease;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
            <span>Copiar código</span>
          </button>
        </div>

        <div style="display:flex; justify-content:space-between; font-size:0.74rem; color:#64748b;">
          <span>⏱️ Caduca el: <strong>${escapeHtml(r.expires_display || '48 horas')}</strong></span>
          <span>Máx. 5 intentos · 3 descargas</span>
        </div>
      `;
    } else {
      card.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <div style="font-size:0.84rem; font-weight:700; color:#1e293b;">
            ✉️ ${escapeHtml(r.email)}
          </div>
          <span style="font-size:0.75rem; color:#dc2626; background:#fef2f2; border:1px solid #fecaca; padding:2px 8px; border-radius:12px; font-weight:600;">
            Error de envío
          </span>
        </div>
        <div style="font-size:0.78rem; color:#991b1b; background:#fff1f2; padding:8px 12px; border-radius:6px;">
          No se generó código para este destinatario debido al fallo de entrega: ${escapeHtml(r.error || 'Fallo de entrega SMTP')}.
        </div>
      `;
    }

    const copyButton = card.querySelector('[data-copy-code]');
    if (copyButton) copyButton.addEventListener('click', () => copiarCodigoAcceso(copyButton, r.code, r.email));
    container.appendChild(card);
  });
}

function copiarCodigoAcceso(btn, codigo, email) {
  if (!codigo) return;
  navigator.clipboard.writeText(codigo).then(() => {
    codigosCopiadosSet.add(email);
    const span = btn.querySelector('span');
    const originalText = span ? span.textContent : 'Copiar código';
    btn.style.background = '#059669';
    btn.style.borderColor = '#059669';
    if (span) span.textContent = '✓ ¡Copiado!';
    setTimeout(() => {
      btn.style.background = '#0284c7';
      btn.style.borderColor = '#0284c7';
      if (span) span.textContent = originalText;
    }, 2000);
  }).catch(() => {
    prompt('Copie manualmente el código:', codigo);
    codigosCopiadosSet.add(email);
  });
}

function ocultarYLimpiarCodigos() {
  const exitosos = codigosAccesoEnMemoria.filter(c => c.success);
  const algunoCopiado = exitosos.length > 0 && exitosos.some(c => codigosCopiadosSet.has(c.email));

  if (exitosos.length > 0 && !algunoCopiado) {
    const confirmar = confirm('¿Está seguro de ocultar y limpiar los códigos sin haberlos copiado? No se podrán recuperar después.');
    if (!confirmar) return;
  }

  limpiarMemoriaCodigos();
  cerrarModalEnviarCorreo();
}

function enviarOtraFichaDesdeModal() {
  limpiarMemoriaCodigos();
  const inputDest = document.getElementById('correoDestinatariosInput');
  const inputNotas = document.getElementById('correoNotasInput');
  const alerta = document.getElementById('correoAlertaEstado');

  if (inputDest) inputDest.value = '';
  if (inputNotas) {
    inputNotas.value = '';
    actualizarContadorNotas(inputNotas);
  }
  if (alerta) alerta.style.display = 'none';

  const vistaForm = document.getElementById('vistaFormularioEnvioCorreo');
  const vistaRes = document.getElementById('vistaResultadosCodigos');
  if (vistaForm) vistaForm.style.display = 'flex';
  if (vistaRes) vistaRes.style.display = 'none';

  if (inputDest) setTimeout(() => inputDest.focus(), 150);
}

// Reactividad inmediata al cambiar el Modo de Privacidad en Ajustes
window.addEventListener('cardio_privacy_mode_changed', () => {
  renderPacientesTabla();
});
