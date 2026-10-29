let pacienteActual = null;
let historialActual = null;

document.addEventListener('DOMContentLoaded', async () => {
  const urlParams = new URLSearchParams(location.search);
  const idPaciente = urlParams.get('paciente');

  if (!idPaciente) {
    location.replace('/clinical/listado/');
    return;
  }

  try {
    const resp = await fetch(`/clinical/api/ficha/${encodeURIComponent(idPaciente)}/`);
    if (!resp.ok) {
      location.replace('/clinical/listado/');
      return;
    }
    const resData = await resp.json();
    if (!resData.success || !resData.paciente) {
      location.replace('/clinical/listado/');
      return;
    }

    pacienteActual = resData.paciente;
    historialActual = obtenerUltimoHistorial(pacienteActual);

    // Actualizar enlace "Volver al Expediente" para volver directamente a la vista de este paciente
    const btnVolver = document.getElementById('btnVolverListado');
    if (btnVolver) {
      btnVolver.href = `/clinical/listado/?paciente=${encodeURIComponent(pacienteActual.id)}`;
    }

    // Actualizar badge de historial activo en el header
    const badgeTxt = document.getElementById('textoHistorialActivo');
    if (badgeTxt && historialActual) {
      badgeTxt.textContent = `Historial Clínico Único · ${historialActual.fechaVisita || ''}`;
    }

    // Fecha visita por defecto del historial o de hoy
    const fVis = document.getElementById('f_fecha_visita');
    if (fVis) {
      fVis.value = (historialActual && historialActual.fechaVisita) ? historialActual.fechaVisita : new Date().toISOString().split('T')[0];
    }

    // Formulario limpio y luego los datos del paciente e historial
    limpiarFormularioCompleto();
    seleccionarPaciente(pacienteActual, historialActual);

    // Restaurar datos completos de todos los módulos desde la base de datos PostgreSQL (Sprint 4)
    if (resData.datos) {
      restaurarFichaDesdeObjeto(resData.datos);
    }
  } catch (err) {
    console.error('Error al cargar la ficha del paciente:', err);
    alert('No se pudo cargar la información del paciente desde la base de datos.');
  }

  restringirCamposNumericos();
});

// Los campos numéricos deben aceptar solo dígitos. `type="number"` por sí solo
// sigue admitiendo 'e', '+' y '-' al teclear, y `pattern` únicamente valida al
// enviar, así que el filtrado se hace aquí sobre el formulario completo.
function restringirCamposNumericos() {
  const form = document.getElementById('ehrCleanForm');
  if (!form) return;

  form.addEventListener('keydown', (ev) => {
    const el = ev.target;
    if (!el.matches || ev.ctrlKey || ev.metaKey || ev.key.length > 1) return;
    if (el.matches('input[type="number"]')) {
      const decimales = el.step && el.step !== '1';
      const permitido = /[0-9]/.test(ev.key) || (decimales && ev.key === '.' && !el.value.includes('.'));
      if (!permitido) ev.preventDefault();
    } else if (el.matches('input[inputmode="numeric"]')) {
      if (!/[0-9]/.test(ev.key)) ev.preventDefault();
    }
  });

  // Pegado y autocompletado: se limpia lo que no sean dígitos
  form.addEventListener('input', (ev) => {
    const el = ev.target;
    if (!el.matches || !el.matches('input[inputmode="numeric"]')) return;
    const limpio = el.value.replace(/[^0-9]/g, '');
    if (limpio !== el.value) el.value = limpio;
  });

  form.addEventListener('paste', (ev) => {
    const el = ev.target;
    if (!el.matches || !el.matches('input[type="number"]')) return;
    const texto = (ev.clipboardData || window.clipboardData).getData('text');
    if (/[^0-9.,\s]/.test(texto)) ev.preventDefault();
  });
}

// Cuestionario PREDIMED: suma 1 punto por cada pregunta puntuable respondida
// "Sí" y muestra el resultado (Puntuación total: <9 baja adherencia, >=9
// buena adherencia), igual que en el formato de papel.
function calcPredimed() {
  const preguntasPuntuables = [
    'pred_q1', 'pred_q2', 'pred_q3', 'pred_q4', 'pred_q5', 'pred_q6', 'pred_q7',
    'pred_q8', 'pred_q9', 'pred_q10', 'pred_q11', 'pred_q12',
    'pred_q16', 'pred_q17', 'pred_q18', 'pred_q19'
  ];
  const max = preguntasPuntuables.length;
  let total = 0;
  preguntasPuntuables.forEach(name => {
    const marcado = document.querySelector(`input[name="${name}"]:checked`);
    if (marcado && marcado.value === 'Si') total++;
  });

  const campoPuntuacion = document.getElementById('pred_puntuacion_total');
  const campoAdherencia = document.getElementById('pred_adherencia');
  if (!campoPuntuacion || !campoAdherencia) return;

  campoPuntuacion.value = `${total} / ${max}`;
  if (total >= 9) {
    campoAdherencia.textContent = 'Buena adherencia';
    campoAdherencia.style.color = 'var(--color-success-green)';
  } else {
    campoAdherencia.textContent = 'Baja adherencia';
    campoAdherencia.style.color = 'var(--color-emergency-red)';
  }
}

// =========================================================================
// GESTIÓN CENTRALIZADA DE ESTADO: 4.- TABAQUISMO
// =========================================================================
// Estado unificado: 'nunca' | 'exfumador' | 'actual'
let estadoTabaquismo = 'actual';

function setEstadoTabaquismo(origen) {
  const toggleNo = document.getElementById('tabaco_toggle_no');
  const toggleSi = document.getElementById('tabaco_toggle_si');
  const selFrec = document.getElementById('tabaco_frecuencia');
  const inpCant = document.getElementById('tabaco_cantidad');
  const chkEx = document.getElementById('chk_exfumador');
  const chkNunca = document.getElementById('chk_nunca_fumo');
  const rowTabaco = document.getElementById('row_tabaco');

  // 1. Determinar el nuevo estado según el control que originó el evento
  if (origen === 'toggle_no') {
    estadoTabaquismo = 'nunca';
  } else if (origen === 'toggle_si') {
    estadoTabaquismo = (chkEx && chkEx.checked) ? 'exfumador' : 'actual';
  } else if (origen === 'chk_nunca') {
    estadoTabaquismo = (chkNunca && chkNunca.checked) ? 'nunca' : 'actual';
  } else if (origen === 'chk_exfumador') {
    estadoTabaquismo = (chkEx && chkEx.checked) ? 'exfumador' : 'actual';
  } else if (origen === 'nunca' || origen === 'exfumador' || origen === 'actual') {
    estadoTabaquismo = origen;
  }

  // Asegurar que la sección conserve su altura y nunca colapse ni oculte filas
  if (rowTabaco) {
    rowTabaco.classList.add('active-yes');
  }

  // 2. Aplicar lógica de exclusión mutua y actualización de controles
  if (estadoTabaquismo === 'nunca') {
    // Al marcar 'nunca fumó' o poner toggle en 'No':
    // - Desmarcar Exfumador > 1 año
    if (chkEx) chkEx.checked = false;
    // - Marcar nunca fumó
    if (chkNunca) chkNunca.checked = true;
    // - Poner toggle en No
    if (toggleNo) toggleNo.checked = true;
    if (toggleSi) toggleSi.checked = false;

    // - Limpiar y deshabilitar Frecuencia y Cantidad (atenuados, no ocultos)
    if (selFrec) {
      selFrec.value = '';
      selFrec.disabled = true;
      selFrec.style.opacity = '0.45';
      selFrec.style.pointerEvents = 'none';
    }
    if (inpCant) {
      inpCant.value = '';
      inpCant.disabled = true;
      inpCant.style.opacity = '0.45';
      inpCant.style.pointerEvents = 'none';
    }

  } else if (estadoTabaquismo === 'exfumador') {
    // Al marcar 'Exfumador > 1 año':
    // - Desmarcar nunca fumó
    if (chkNunca) chkNunca.checked = false;
    // - Marcar Exfumador
    if (chkEx) chkEx.checked = true;
    // - Poner toggle en Sí
    if (toggleNo) toggleNo.checked = false;
    if (toggleSi) toggleSi.checked = true;

    // - BLOQUEAR FRECUENCIA Y CANTIDAD (Deshabilitados y atenuados)
    if (selFrec) {
      selFrec.disabled = true;
      selFrec.style.opacity = '0.45';
      selFrec.style.pointerEvents = 'none';
    }
    if (inpCant) {
      inpCant.disabled = true;
      inpCant.style.opacity = '0.45';
      inpCant.style.pointerEvents = 'none';
    }

  } else {
    // Estado 'actual' (fumador activo):
    // - Desmarcar nunca fumó y Exfumador
    if (chkNunca) chkNunca.checked = false;
    if (chkEx) chkEx.checked = false;
    // - Poner toggle en Sí
    if (toggleNo) toggleNo.checked = false;
    if (toggleSi) toggleSi.checked = true;

    // - Habilitar Frecuencia y Cantidad
    if (selFrec) {
      selFrec.disabled = false;
      selFrec.style.opacity = '1';
      selFrec.style.pointerEvents = 'auto';
      if (!selFrec.value) selFrec.value = 'Sí, menos de 5 al día';
    }
    if (inpCant) {
      inpCant.disabled = false;
      inpCant.style.opacity = '1';
      inpCant.style.pointerEvents = 'auto';
      if (!inpCant.value) inpCant.value = '3';
    }
  }
}

function onTabacoCantidadInput() {
  const inp = document.getElementById('tabaco_cantidad');
  const sel = document.getElementById('tabaco_frecuencia');
  if (!inp || !sel) return;
  const val = parseInt(inp.value, 10);
  if (isNaN(val) || val < 5) {
    sel.value = 'Sí, menos de 5 al día';
  } else if (val <= 10) {
    sel.value = 'Sí, entre 5 y 10 al día';
  } else if (val <= 20) {
    sel.value = 'Sí, entre 10 y 20 al día';
  } else {
    sel.value = 'Sí, más de 20 al día';
  }
}

function onTabacoFrecuenciaChange() {
  const sel = document.getElementById('tabaco_frecuencia');
  const inp = document.getElementById('tabaco_cantidad');
  if (!inp || !sel) return;
  if (sel.value === 'Sí, menos de 5 al día') inp.value = 3;
  else if (sel.value === 'Sí, entre 5 y 10 al día') inp.value = 8;
  else if (sel.value === 'Sí, entre 10 y 20 al día') inp.value = 15;
  else if (sel.value === 'Sí, más de 20 al día') inp.value = 25;
}

// Gestión de estado Alcohol
function setEstadoAlcohol(origen) {
  const toggleNo = document.getElementById('alcohol_toggle_no');
  const toggleSi = document.getElementById('alcohol_toggle_si');
  const chkEx = document.getElementById('chk_ex_alcohol');
  const selFrec = document.getElementById('alcohol_frecuencia');
  const inpUnid = document.getElementById('alcohol_unidades');

  if (origen === 'toggle_no') {
    toggleCondition('row_alcohol', false);
    if (chkEx) chkEx.checked = false;
  } else if (origen === 'toggle_si') {
    toggleCondition('row_alcohol', true);
    if (selFrec) { selFrec.disabled = false; selFrec.style.opacity = '1'; }
    if (inpUnid) { inpUnid.disabled = false; inpUnid.style.opacity = '1'; }
  } else if (origen === 'chk_ex') {
    if (chkEx && chkEx.checked) {
      if (toggleSi) toggleSi.checked = true;
      if (toggleNo) toggleNo.checked = false;
      toggleCondition('row_alcohol', true);
      if (selFrec) { selFrec.disabled = true; selFrec.style.opacity = '0.45'; }
      if (inpUnid) { inpUnid.disabled = true; inpUnid.style.opacity = '0.45'; }
    } else {
      if (selFrec) { selFrec.disabled = false; selFrec.style.opacity = '1'; }
      if (inpUnid) { inpUnid.disabled = false; inpUnid.style.opacity = '1'; }
    }
  }
}

// Gestión de estado Drogas
function setEstadoDrogas(origen) {
  const toggleNo = document.getElementById('drogas_toggle_no');
  const toggleSi = document.getElementById('drogas_toggle_si');
  const chkEx = document.getElementById('chk_ex_drogas');
  const selFrec = document.getElementById('drogas_frecuencia');
  const inpCuales = document.getElementById('drogas_cuales');

  if (origen === 'toggle_no') {
    toggleCondition('row_drogas', false);
    if (chkEx) chkEx.checked = false;
  } else if (origen === 'toggle_si') {
    toggleCondition('row_drogas', true);
    if (selFrec) { selFrec.disabled = false; selFrec.style.opacity = '1'; }
    if (inpCuales) { inpCuales.disabled = false; inpCuales.style.opacity = '1'; }
  } else if (origen === 'chk_ex') {
    if (chkEx && chkEx.checked) {
      if (toggleSi) toggleSi.checked = true;
      if (toggleNo) toggleNo.checked = false;
      toggleCondition('row_drogas', true);
      if (selFrec) { selFrec.disabled = true; selFrec.style.opacity = '0.45'; }
      if (inpCuales) { inpCuales.disabled = true; inpCuales.style.opacity = '0.45'; }
    } else {
      if (selFrec) { selFrec.disabled = false; selFrec.style.opacity = '1'; }
      if (inpCuales) { inpCuales.disabled = false; inpCuales.style.opacity = '1'; }
    }
  }
}

// Formato exacto de la base de datos (Columna W: TABAQUISMO)
// Valores de la base institucional:
// - "No fuma"
// - "Exfumador hace más de un año"
// - "Sí, menos de 5 al día" (o "Sí, X al día")
function obtenerPayloadTabaquismo() {
  if (estadoTabaquismo === 'nunca') {
    return {
      columna_w_tabaquismo: 'No fuma',
      estado_tabaquismo: 'nunca',
      frecuencia: null,
      cigarrillos_dia: null
    };
  }

  if (estadoTabaquismo === 'exfumador') {
    return {
      columna_w_tabaquismo: 'Exfumador hace más de un año',
      estado_tabaquismo: 'exfumador',
      frecuencia: null,
      cigarrillos_dia: null
    };
  }

  // Fumador activo
  const cant = parseInt(document.getElementById('tabaco_cantidad')?.value, 10);
  const selFrec = document.getElementById('tabaco_frecuencia')?.value || 'Sí, menos de 5 al día';

  return {
    columna_w_tabaquismo: selFrec, // Corresponde al valor exacto de la Columna W: 'TABAQUISMO'
    estado_tabaquismo: 'actual',
    frecuencia: selFrec,
    cigarrillos_dia: isNaN(cant) ? null : cant
  };
}

// TODO: Conectar con la persistencia / guardado en la base de datos (Columna W 'TABAQUISMO'):
// async function guardarRegistroTabaquismo(pacienteId) {
//   const data = obtenerPayloadTabaquismo();
//   console.log("Guardando en Columna W (TABAQUISMO):", data.columna_w_tabaquismo);
//   // await db.pacientes.update(pacienteId, data.columna_w_tabaquismo);
// }

// =============================================================================
// CATÁLOGOS DINÁMICOS EN CASCADA: UNIVERSIDAD-FACULTAD Y PROVINCIA-CANTÓN
// =============================================================================
const FACULTADES_POR_UNIVERSIDAD = {
  'UNEMI': [
    { value: 'FACI', label: 'FACI - Facultad de Ciencias e Ingeniería' },
    { value: 'FACS', label: 'FACS - Facultad de Salud' },
    { value: 'FACSO', label: 'FACSO - Ciencias Sociales, Educación Comercial y Derecho' },
    { value: 'FACE', label: 'FACE - Facultad de Educación' },
    { value: 'POSGRADO', label: 'Posgrado / Dirección de Posgrado' }
  ],
  'ESPOL': [
    { value: 'FIEC', label: 'FIEC - Fac. de Ing. en Electricidad y Computación' },
    { value: 'FCNM', label: 'FCNM - Fac. de Ciencias Naturales y Matemáticas' },
    { value: 'FIMCP', label: 'FIMCP - Fac. de Ing. Mecánica y Ciencias de la Producción' },
    { value: 'FCSH', label: 'FCSH - Fac. de Ciencias Sociales y Humanísticas' },
    { value: 'FCV', label: 'FCV - Facultad de Ciencias de la Vida' },
    { value: 'FIMCM', label: 'FIMCM - Fac. de Ing. Marítima y Ciencias del Mar' },
    { value: 'EDCOM', label: 'EDCOM - Escuela de Diseño y Comunicación Visual' }
  ]
};

const CANTONES_POR_PROVINCIA = {
  'AZUAY': ['Cuenca', 'Camilo Ponce Enríquez', 'Chordeleg', 'El Pan', 'Girón', 'Guachapala', 'Gualaceo', 'Nabón', 'Oña', 'Paute', 'Pucará', 'San Fernando', 'Santa Isabel', 'Sevilla de Oro', 'Sígsig'],
  'BOLIVAR': ['Guaranda', 'Caluma', 'Chillanes', 'Chimbo', 'Echeandía', 'Las Naves', 'San Miguel'],
  'CANAR': ['Azogues', 'Biblián', 'Cañar', 'Déleg', 'El Tambo', 'La Troncal', 'Suscal'],
  'CARCHI': ['Tulcán', 'Bolívar', 'Espejo', 'Mira', 'Montúfar', 'San Pedro de Huaca'],
  'CHIMBORAZO': ['Riobamba', 'Alausí', 'Chambo', 'Chunchi', 'Colta', 'Cumandá', 'Guamote', 'Guano', 'Pallatanga', 'Penipe'],
  'COTOPAXI': ['Latacunga', 'La Maná', 'Pangua', 'Pujilí', 'Salcedo', 'Saquisilí', 'Sigchos'],
  'EL ORO': ['Machala', 'Arenillas', 'Atahualpa', 'Balsas', 'Chilla', 'El Guabo', 'Huaquillas', 'Las Lajas', 'Marcabelí', 'Pasaje', 'Piñas', 'Portovelo', 'Santa Rosa', 'Zaruma'],
  'ESMERALDAS': ['Esmeraldas', 'Atacames', 'Eloy Alfaro', 'Muisne', 'Quinindé', 'Rioverde', 'San Lorenzo'],
  'GALAPAGOS': ['San Cristóbal', 'Isabela', 'Santa Cruz'],
  'GUAYAS': ['Milagro', 'Guayaquil', 'Alfredo Baquerizo Moreno (Juján)', 'Balao', 'Balzar', 'Colimes', 'Daule', 'Durán', 'El Empalme', 'El Triunfo', 'General Antonio Elizalde (Bucay)', 'Isidro Ayora', 'Lomas de Sargentillo', 'Marcelino Maridueña', 'Naranjal', 'Naranjito', 'Nobol', 'Palestina', 'Pedro Carbo', 'Playas (General Villamil)', 'Salitre (Urbina Jado)', 'Samborondón', 'Santa Lucía', 'Simón Bolívar', 'Yaguachi'],
  'IMBABURA': ['Ibarra', 'Antonio Ante', 'Cotacachi', 'Otavalo', 'Pimampiro', 'San Miguel de Urcuquí'],
  'LOJA': ['Loja', 'Calvas', 'Catamayo', 'Celica', 'Chaguarpamba', 'Espíndola', 'Gonzanamá', 'Macará', 'Olmedo', 'Paltas', 'Pindal', 'Puyango', 'Quilanga', 'Saraguro', 'Sozoranga', 'Zapotillo'],
  'LOS RIOS': ['Babahoyo', 'Baba', 'Buena Fe', 'Mocache', 'Montalvo', 'Palenque', 'Puebloviejo', 'Quevedo', 'Quinsaloma', 'Urdaneta', 'Valencia', 'Ventanas', 'Vinces'],
  'MANABI': ['Portoviejo', 'Bolívar (Calceta)', 'Chone', 'El Carmen', 'Flavio Alfaro', 'Jama', 'Jaramijó', 'Jipijapa', 'Junín', 'Manta', 'Montecristi', 'Olmedo', 'Paján', 'Pedernales', 'Pichincha', 'Puerto López', 'Rocafuerte', 'San Vicente', 'Santa Ana', 'Sucre (Bahía de Caráquez)', 'Tosagua', '24 de Mayo'],
  'MORONA SANTIAGO': ['Morona (Macas)', 'Gualaquiza', 'Huamboya', 'Limón Indanza', 'Logroño', 'Pablo Sexto', 'Palora', 'San Juan Bosco', 'Santiago de Méndez', 'Sucúa', 'Taisha', 'Tiwintza'],
  'NAPO': ['Tena', 'Archidona', 'Carlos Julio Arosemena Tola', 'El Chaco', 'Quijos (Baeza)'],
  'ORELLANA': ['Francisco de Orellana (Coca)', 'Aguarico', 'La Joya de los Sachas', 'Loreto'],
  'PASTAZA': ['Pastaza (Puyo)', 'Arajuno', 'Mera', 'Santa Clara'],
  'PICHINCHA': ['Quito', 'Cayambe', 'Mejía', 'Pedro Moncayo', 'Pedro Vicente Maldonado', 'Puerto Quito', 'Rumiñahui', 'San Miguel de Los Bancos'],
  'SANTA ELENA': ['Santa Elena', 'La Libertad', 'Salinas'],
  'SANTO DOMINGO DE LOS TSACHILAS': ['Santo Domingo', 'La Concordia'],
  'SUCUMBIOS': ['Lago Agrio (Nueva Loja)', 'Cascales', 'Cuyabeno', 'Gonzalo Pizarro', 'Putumayo', 'Shushufindi', 'Sucumbíos'],
  'TUNGURAHUA': ['Ambato', 'Baños de Agua Santa', 'Cevallos', 'Mocha', 'Patate', 'Quero', 'San Pedro de Pelileo', 'Santiago de Píllaro', 'Tisaleo'],
  'ZAMORA CHINCHIPE': ['Zamora', 'Centinela del Cóndor', 'Chinchipe', 'El Pangui', 'Nangaritza', 'Palanda', 'Paquisha', 'Yacuambi', 'Yantzaza'],
  'EXTRANJERO': ['Otro país / Exterior']
};

function onUniversidadChange(uni, selectedFacultad) {
  const selFac = document.getElementById('f_facultad');
  if (!selFac) return;

  const cleanUni = (uni || 'UNEMI').toUpperCase().trim();
  const facList = FACULTADES_POR_UNIVERSIDAD[cleanUni] || FACULTADES_POR_UNIVERSIDAD['UNEMI'];

  selFac.innerHTML = '<option value="">-- Seleccionar Facultad --</option>';
  let matched = false;

  facList.forEach(f => {
    const opt = document.createElement('option');
    opt.value = f.value;
    opt.textContent = f.label;
    if (selectedFacultad && (f.value.toLowerCase() === String(selectedFacultad).toLowerCase() || f.label.toLowerCase().includes(String(selectedFacultad).toLowerCase()))) {
      opt.selected = true;
      matched = true;
    }
    selFac.appendChild(opt);
  });

  if (!matched && selectedFacultad) {
    const customOpt = document.createElement('option');
    customOpt.value = selectedFacultad;
    customOpt.textContent = selectedFacultad;
    customOpt.selected = true;
    selFac.appendChild(customOpt);
  } else if (!matched && facList.length > 0 && !selectedFacultad) {
    selFac.value = facList[0].value;
  }

  const heroFac = document.getElementById('heroFacultad');
  if (heroFac) {
    heroFac.textContent = selFac.value || cleanUni;
  }
}

function onProvinciaNacChange(prov, selectedMunicipio) {
  const selMun = document.getElementById('f_municipio');
  if (!selMun) return;

  const provKey = (prov || 'GUAYAS').toUpperCase().trim();
  const cantones = CANTONES_POR_PROVINCIA[provKey] || ['Milagro', 'Guayaquil', 'Durán', 'Daule'];

  selMun.innerHTML = '<option value="">-- Seleccionar Cantón / Municipio --</option>';
  let matched = false;

  cantones.forEach(cant => {
    const opt = document.createElement('option');
    opt.value = cant;
    opt.textContent = cant;
    if (selectedMunicipio && (cant.toLowerCase() === String(selectedMunicipio).toLowerCase())) {
      opt.selected = true;
      matched = true;
    }
    selMun.appendChild(opt);
  });

  if (!matched && selectedMunicipio) {
    const customOpt = document.createElement('option');
    customOpt.value = selectedMunicipio;
    customOpt.textContent = selectedMunicipio;
    customOpt.selected = true;
    selMun.appendChild(customOpt);
  } else if (!matched && cantones.length > 0 && !selectedMunicipio) {
    selMun.value = cantones[0];
  }
}

function onProvinciaResidenciaChange(prov, selectedCiudad) {
  const selCiu = document.getElementById('f_ciudad');
  if (!selCiu) return;

  const provKey = (prov || 'GUAYAS').toUpperCase().trim();
  const cantones = CANTONES_POR_PROVINCIA[provKey] || ['Milagro', 'Guayaquil', 'Durán', 'Daule'];

  selCiu.innerHTML = '<option value="">-- Seleccionar Cantón / Ciudad --</option>';
  let matched = false;

  cantones.forEach(cant => {
    const opt = document.createElement('option');
    opt.value = cant;
    opt.textContent = cant;
    if (selectedCiudad && (cant.toLowerCase() === String(selectedCiudad).toLowerCase())) {
      opt.selected = true;
      matched = true;
    }
    selCiu.appendChild(opt);
  });

  if (!matched && selectedCiudad) {
    const customOpt = document.createElement('option');
    customOpt.value = selectedCiudad;
    customOpt.textContent = selectedCiudad;
    customOpt.selected = true;
    selCiu.appendChild(customOpt);
  } else if (!matched && cantones.length > 0 && !selectedCiudad) {
    selCiu.value = cantones[0];
  }
}

// Acordeón de tarjetas: clic en el título expande/colapsa el contenido
// de esa sección (mismo mecanismo de "clic para desplegar" que ya usan
// los paneles de fórmula del dashboard).
// La base guarda en PROVINCIA_NAC tanto provincias del Ecuador como países
// (CUBA, VENEZUELA, FRANCIA), así que la opción "Otro país" abre un campo libre.
function toggleProvinciaExtranjera() {
  const sel = document.getElementById('f_provincia_nac');
  const campo = document.getElementById('campo_pais_nac');
  if (!sel || !campo) return;
  campo.style.display = sel.value === 'EXTRANJERO' ? '' : 'none';
  if (sel.value !== 'EXTRANJERO') {
    const inp = document.getElementById('f_pais_nac');
    if (inp) inp.value = '';
  }
}

function actualizarNombreCompleto() {
  const partes = ['f_nombre', 'f_apellido1', 'f_apellido2']
    .map(id => (document.getElementById(id) || {}).value || '')
    .map(x => x.trim())
    .filter(Boolean);
  const completo = partes.join(' ');
  const hero = document.getElementById('heroNombre');
  if (hero) hero.textContent = completo || '--';
}

function toggleCard(headerEl) {
  headerEl.closest('.card').classList.toggle('expanded');
}

// Función condicional: mostrar input SOLO si Sí
function toggleCondition(rowId, show) {
  const row = document.getElementById(rowId);
  if (row) {
    row.classList.toggle('active-yes', show);
  }
}

function onBirthDateChange(dateStr) {
  const edadStr = calcAgeStr(dateStr);
  document.getElementById('f_edad').value = edadStr;
  document.getElementById('heroEdad').textContent = edadStr;
  document.getElementById('heroFechaNac').textContent = dateStr;
}

// Cálculo automático de IMC y ASC (provisto globalmente en static/js/global/utils.js)

// SELECCIÓN Y CARGA DE DATOS DEL PACIENTE E HISTORIAL
function seleccionarPaciente(p, h) {

  document.getElementById('heroNombre').textContent = p.nombre;
  const edadStr = calcAgeStr(p.fechaNac);
  document.getElementById('heroEdad').textContent = edadStr;
  document.getElementById('heroCodigo').textContent = (h && h.codigoEstudio) ? h.codigoEstudio : p.codigo;
  document.getElementById('heroFechaNac').textContent = p.fechaNac;
  document.getElementById('heroSexo').textContent = p.sexo === 'H' ? 'Hombre' : 'Mujer';
  document.getElementById('heroEstamento').textContent = p.estamento;
  document.getElementById('heroFacultad').textContent = p.facultad || 'UNEMI';

  const inits = p.nombre.split(' ').map(n => n[0]).slice(0, 2).join('');
  document.getElementById('heroAvatar').textContent = inits;

  document.getElementById('f_codigo').value = (h && h.codigoEstudio) ? h.codigoEstudio : p.codigo;
  const trozos = (p.nombre || '').trim().split(/\s+/);
  document.getElementById('f_nombre').value = trozos.slice(0, trozos.length > 2 ? 1 : 1).join(' ');
  document.getElementById('f_apellido1').value = trozos[1] || '';
  document.getElementById('f_apellido2').value = trozos.slice(2).join(' ');
  document.getElementById('f_fecha_nac').value = p.fechaNac;
  document.getElementById('f_edad').value = edadStr;

  // Universidad y Facultad
  const uniVal = p.universidad || 'UNEMI';
  if (document.getElementById('f_universidad')) {
    document.getElementById('f_universidad').value = uniVal;
  }
  onUniversidadChange(uniVal, p.facultad);

  // Provincia y Cantón de Nacimiento
  const provNacVal = p.provincia_nac || p.provincia || 'GUAYAS';
  if (document.getElementById('f_provincia_nac')) {
    document.getElementById('f_provincia_nac').value = provNacVal;
  }
  onProvinciaNacChange(provNacVal, p.municipio || 'Milagro');

  // Provincia y Cantón de Residencia
  const provResVal = p.provincia || 'GUAYAS';
  if (document.getElementById('f_provincia')) {
    document.getElementById('f_provincia').value = provResVal;
  }
  onProvinciaResidenciaChange(provResVal, p.ciudad || 'Milagro');

  // N.º de Visita
  if (document.getElementById('f_visita')) {
    document.getElementById('f_visita').value = (h && h.numeroVisita) ? h.numeroVisita : (p.numeroVisita || 1);
  }

  document.getElementById('f_telefono').value = p.telefono || '';
  document.getElementById('f_correo').value = p.correo || '';
  if (document.getElementById('f_raza')) document.getElementById('f_raza').value = (p.raza ? p.raza.toUpperCase() : '');
  if (document.getElementById('f_convivientes')) document.getElementById('f_convivientes').value = (p.convivientes !== undefined ? p.convivientes : '');
  if (document.getElementById('f_hijos')) document.getElementById('f_hijos').value = (p.hijos !== undefined ? p.hijos : '');
  if (p.estado_civil && document.getElementById('f_estado_civil')) document.getElementById('f_estado_civil').value = p.estado_civil;
  if (p.convive_con && document.getElementById('f_convive_con')) document.getElementById('f_convive_con').value = p.convive_con;
  if (p.estudios && document.getElementById('f_estudios')) document.getElementById('f_estudios').value = p.estudios;
  if (p.horario && document.getElementById('f_horario')) document.getElementById('f_horario').value = p.horario;
  if (p.profesion && document.getElementById('f_profesion')) document.getElementById('f_profesion').value = p.profesion;
  if (p.vivienda && document.getElementById('f_vivienda')) document.getElementById('f_vivienda').value = p.vivienda;
  if (p.ingresos && document.getElementById('f_ingresos')) document.getElementById('f_ingresos').value = p.ingresos;

  document.getElementById('f_sexo').value = p.sexo;
  document.getElementById('f_estamento').value = p.estamento;

  // Medidas y constantes del historial específico (o de paciente si no hay historial)
  const pesoVal = (h && h.peso) ? h.peso : (p.peso || '');
  const tallaVal = (h && h.talla) ? h.talla : (p.talla || '');
  const perimetroVal = (h && h.perimetro) ? h.perimetro : (p.perimetro || '');
  const tasVal = (h && h.tas) ? h.tas : (p.tas || '');
  const tsiVal = (h && h.tsi) ? h.tsi : (p.tsi || '');
  const satVal = (h && h.satO2) ? h.satO2 : (p.satO2 || '');

  document.getElementById('f_peso').value = pesoVal;
  document.getElementById('f_talla').value = tallaVal;
  document.getElementById('f_perimetro').value = perimetroVal;

  if (document.getElementById('f_sat_o2')) document.getElementById('f_sat_o2').value = satVal;
  if (document.getElementById('f_tas')) document.getElementById('f_tas').value = tasVal;
  if (document.getElementById('f_tsi')) document.getElementById('f_tsi').value = tsiVal;
  if (document.getElementById('heroSatO2')) document.getElementById('heroSatO2').textContent = satVal ? satVal + '%' : '--';
  actualizarHeroPresion();

  calcIMC();

  // Ficha y módulos sincronizados directamente desde PostgreSQL
}

// NAVEGACIÓN Y SCROLL SUAVE ENTRE MÓDULOS UNIFICADOS
function scrollToModule(modId) {
  const el = document.getElementById(modId);
  if (el) {
    const headerOffset = 80;
    const elementPosition = el.getBoundingClientRect().top;
    const offsetPosition = elementPosition + window.pageYOffset - headerOffset;
    window.scrollTo({
      top: offsetPosition,
      behavior: 'smooth'
    });
  }
}

// Actualizar sección activa en el sidebar según el scroll
window.addEventListener('scroll', () => {
  const sections = ['mod-sociodemo', 'mod-exploracion', 'mod-cardio', 'mod-nocardio', 'mod-laboratorio', 'mod-estilovida'];
  const scrollPos = window.scrollY + 120;

  for (let i = sections.length - 1; i >= 0; i--) {
    const sec = document.getElementById(sections[i]);
    if (sec && sec.offsetTop <= scrollPos) {
      document.querySelectorAll('.sidebar-nav .nav-btn').forEach(b => b.classList.remove('active'));
      const btn = document.getElementById('sideBtn-mod' + (i + 1));
      if (btn) btn.classList.add('active');
      break;
    }
  }
});

// ACTUALIZACIÓN DE WIDGET DE PRESIÓN EN TIEMPO REAL
function actualizarHeroPresion() {
  const tasInp = document.getElementById('f_tas');
  const tsiInp = document.getElementById('f_tsi');
  const heroPres = document.getElementById('heroPresion');
  if (!heroPres) return;
  const tasVal = tasInp ? tasInp.value.trim() : '';
  const tsiVal = tsiInp ? tsiInp.value.trim() : '';
  if (tasVal || tsiVal) {
    heroPres.textContent = `${tasVal || '--'} / ${tsiVal || '--'}`;
  } else {
    heroPres.textContent = '--';
  }
}

// PERSISTENCIA COMPLETA: GUARDADO DE LA FICHA CLÍNICA EN POSTGRESQL (Sprint 4 / HU-11, HU-12, HU-13)
async function guardarFichaCompleta() {
  const form = document.getElementById('ehrCleanForm');
  if (!form) return;

  const urlParams = new URLSearchParams(location.search);
  const idPacienteUrl = urlParams.get('paciente');
  const codigo = document.getElementById('f_codigo') ? document.getElementById('f_codigo').value.trim() : '';

  if (!codigo && !pacienteActual && !idPacienteUrl) {
    alert('No hay un paciente o código válido seleccionado.');
    return;
  }

  const btnTop = document.getElementById('btnGuardarFicha');
  if (btnTop) {
    btnTop.disabled = true;
    btnTop.textContent = 'Guardando cambios en BD...';
  }

  // Recopilar todos los elementos del formulario mediante FormData
  const formData = new FormData(form);

  // Asegurar que checkboxes desmarcados se envíen como '0' para persistir el cambio
  form.querySelectorAll('input[type="checkbox"]').forEach(cb => {
    if (cb.name && !cb.checked && !formData.has(cb.name)) {
      formData.append(cb.name, '0');
    }
  });

  // Guardar también campos de cálculo o sólo lectura
  const calculatedIds = ['f_imc', 'f_asc', 'pred_puntuacion_total'];
  calculatedIds.forEach(id => {
    const el = document.getElementById(id);
    if (el) formData.append(id, el.value);
  });

  if (pacienteActual && pacienteActual.id) {
    formData.append('idPaciente', pacienteActual.id);
  } else if (idPacienteUrl) {
    formData.append('idPaciente', idPacienteUrl);
  }

  try {
    const csrfToken = (typeof getCookie === 'function' ? getCookie('csrftoken') : '') || '';
    const resp = await fetch('/clinical/api/ficha/guardar/', {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrfToken,
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: formData
    });

    const resJson = await resp.json();
    if (!resp.ok || !resJson.success) {
      alert('Error al guardar la ficha: ' + (resJson.error || 'Verifique los rangos clínicos y los campos obligatorios.'));
      return;
    }

    // Sincronizar en memoria con los datos persistidos en PostgreSQL
    if (resJson.paciente) {
      pacienteActual = resJson.paciente;
      historialActual = obtenerUltimoHistorial(pacienteActual);
      seleccionarPaciente(pacienteActual, historialActual);
    }
    if (resJson.datos) {
      restaurarFichaDesdeObjeto(resJson.datos);
    }

    const codMostrar = (pacienteActual && pacienteActual.codigo) ? pacienteActual.codigo : codigo;
    mostrarNotificacionToast(`✓ Ficha Clínica #${codMostrar} (${pacienteActual ? pacienteActual.nombre : ''}) guardada exitosamente en la base de datos.`);
  } catch (err) {
    console.error('Error al guardar la ficha en la base de datos:', err);
    alert('Error al conectar con la base de datos: ' + err.message);
  } finally {
    if (btnTop) {
      btnTop.disabled = false;
      btnTop.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg>
        <span>Guardar Cambios</span>
      `;
    }
  }
}

// RESTAURAR FICHA CLÍNICA DESDE OBJETO OBTENIDO DE LA BASE DE DATOS
function restaurarFichaDesdeObjeto(datos) {
  if (!datos) return;
  const form = document.getElementById('ehrCleanForm');
  if (!form) return;

  // Inicializar selectores en cascada antes de iterar campos
  if (datos.f_universidad) {
    if (document.getElementById('f_universidad')) document.getElementById('f_universidad').value = datos.f_universidad;
    onUniversidadChange(datos.f_universidad, datos.f_facultad);
  }
  if (datos.f_provincia_nac) {
    if (document.getElementById('f_provincia_nac')) document.getElementById('f_provincia_nac').value = datos.f_provincia_nac;
    onProvinciaNacChange(datos.f_provincia_nac, datos.f_municipio);
  }
  if (datos.f_provincia) {
    if (document.getElementById('f_provincia')) document.getElementById('f_provincia').value = datos.f_provincia;
    onProvinciaResidenciaChange(datos.f_provincia, datos.f_ciudad);
  }
  if (datos.f_visita && document.getElementById('f_visita')) {
    document.getElementById('f_visita').value = datos.f_visita;
  }
  if (datos.f_fecha_nac && typeof onBirthDateChange === 'function') {
    onBirthDateChange(datos.f_fecha_nac);
  }
  if (datos.f_edad) {
    const elEdad = document.getElementById('f_edad');
    if (elEdad) elEdad.value = datos.f_edad;
    const heroEdad = document.getElementById('heroEdad');
    if (heroEdad) heroEdad.textContent = datos.f_edad + ' años';
  }

  Object.keys(datos).forEach(key => {
    const val = datos[key];
    if (val === null || val === undefined || val === '') return;

    let elements = form.elements[key];
    if (!elements) {
      elements = document.getElementById(key);
      if (!elements) return;
    }

    if (elements instanceof RadioNodeList || (elements.length && elements[0].type === 'radio')) {
      const vNorm = String(val).toLowerCase().trim();
      let matched = false;
      for (let i = 0; i < elements.length; i++) {
        const rVal = elements[i].value.toLowerCase().trim();
        if (rVal === vNorm) {
          elements[i].checked = true;
          if (elements[i].onchange) elements[i].onchange();
          matched = true;
          break;
        }
      }
      if (!matched) {
        const isSi = (vNorm === 'si' || vNorm === 'sí' || vNorm.startsWith('si') || vNorm.startsWith('sí') || vNorm === '1' || vNorm === 'true');
        const isNo = (vNorm === 'no' || vNorm.startsWith('no') || vNorm === '0' || vNorm === 'false');
        const isNormal = (vNorm === 'normal' || vNorm === 'normales' || vNorm.startsWith('normal'));
        const isAlterada = (vNorm === 'alterada' || vNorm === 'alteradas' || vNorm.startsWith('alterad'));
        for (let i = 0; i < elements.length; i++) {
          const rVal = elements[i].value.toLowerCase().trim();
          if ((isSi && (rVal === 'si' || rVal === 'sí')) || 
              (isNo && rVal === 'no') ||
              (isNormal && (rVal === 'normal' || rVal === 'normales')) ||
              (isAlterada && (rVal === 'alterada' || rVal === 'alteradas'))) {
            elements[i].checked = true;
            if (elements[i].onchange) elements[i].onchange();
            matched = true;
            break;
          }
        }
      }
      // Sincronizar visibilidad de contenedor condicional si corresponde
      if (matched) {
        for (let i = 0; i < elements.length; i++) {
          if (elements[i].checked) {
            const row = elements[i].closest('.condition-row');
            if (row) {
              const rVal = elements[i].value.toLowerCase().trim();
              if (rVal === 'si' || rVal === 'sí' || rVal === 'alterada' || rVal === 'alteradas') {
                row.classList.add('active-yes');
              } else if (rVal === 'no' || rVal === 'normal' || rVal === 'normales') {
                row.classList.remove('active-yes');
              }
            }
          }
        }
      }
    } else if (elements.type === 'select-one') {
      elements.value = val;
      if (!elements.value && val) {
        const vLower = String(val).toLowerCase().trim();
        for (let j = 0; j < elements.options.length; j++) {
          const optVal = elements.options[j].value.toLowerCase().trim();
          const optTxt = elements.options[j].text.toLowerCase().trim();
          if (optVal === vLower || optTxt === vLower ||
              (optVal && vLower.startsWith(optVal)) ||
              (optTxt && (optTxt.includes(vLower) || vLower.includes(optTxt)))) {
            elements.selectedIndex = j;
            break;
          }
        }
      }
      if (elements.onchange) elements.onchange();
    } else if (elements.type === 'checkbox') {
      const vLower = String(val).toLowerCase().trim();
      elements.checked = (val === '1' || val === 1 || val === true || vLower === 'si' || vLower === 'sí' || vLower === elements.value.toLowerCase());
      if (elements.onchange) elements.onchange();
    } else if ('value' in elements) {
      elements.value = val;
      if (elements.oninput) elements.oninput();
      if (elements.onchange) elements.onchange();
    }
  });

  calcIMC();
  calcPredimed();
  actualizarHeroPresion();
}

// NOTIFICACIÓN FLOTANTE VISUAL (TOAST)
function mostrarNotificacionToast(msg) {
  let toast = document.getElementById('clinicalToast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'clinicalToast';
    toast.style.position = 'fixed';
    toast.style.bottom = '24px';
    toast.style.right = '24px';
    toast.style.backgroundColor = '#0b69a3';
    toast.style.color = '#ffffff';
    toast.style.padding = '14px 22px';
    toast.style.borderRadius = '8px';
    toast.style.boxShadow = '0 8px 24px rgba(0, 0, 0, 0.25)';
    toast.style.fontFamily = 'Inter, -apple-system, BlinkMacSystemFont, sans-serif';
    toast.style.fontSize = '0.92rem';
    toast.style.fontWeight = '600';
    toast.style.zIndex = '9999';
    toast.style.transition = 'opacity 0.3s cubic-bezier(0.16, 1, 0.3, 1), transform 0.3s cubic-bezier(0.16, 1, 0.3, 1)';
    toast.style.display = 'flex';
    toast.style.alignItems = 'center';
    toast.style.gap = '10px';
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.style.opacity = '1';
  toast.style.transform = 'translateY(0)';
  clearTimeout(toast._timeout);
  toast._timeout = setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(12px)';
  }, 3500);
}

// =============================================================================
// CAPA DE EXPORTACIÓN FORMULARIO CLÍNICO -> BASE CARDIOUNEMI (184 COLUMNAS)
// Contrato de integración estricto con Base_CardioUNEMI_legible.csv (§6 y §7)
// =============================================================================

// Columnas del CSV exportado: las 112 de BASE UNIFICADO ESPOL + UNEMICarolina,
// en su orden exacto, menos SINTOMAS_COVID y USTED_CONSUME_HUEVOS, que el usuario
// descarto por irrelevantes. Es la unica base que se usa como contrato.
//
// Las 69 primeras son de captura y las rellena el formulario. De ahi en adelante
// la base agrupa las derivadas (los recodificados ...LOGI, EdadRangos, ADHDIETMEDIT,
// filter_$, PerimetroAbdominalCAT), que se calculan despues y salen vacias: el
// formulario captura, no calcula estadistica.
const CARDIOUNEMI_ORDEN_EXPORT = [
  "VISITA",
  "PACIENTE",
  "UNIVERSIDAD",
  "AÑO",
  "CODIGO",
  "Categoria_Personal",
  "NOMBRES",
  "APELLIDO1",
  "APELLIDO2",
  "C.I",
  "EDAD",
  "SEXO",
  "NIVEL_ESTUDIOS_OBTENIDO",
  "CATEGORIA_PROFESIONAL",
  "INGRESOS_TOTALES",
  "PESO_KG",
  "TALLA_CM",
  "IMC_KGM2",
  "PERÍMETRO_ABDOMINAL_CM",
  "HIPERTENSION",
  "DIABETES_MELLITUS",
  "DISLIPIDEMIA",
  "TABAQUISMO",
  "ALCOHOL",
  "DROGAS",
  "PESO_CORPORAL",
  "ARRITMIAS",
  "SINCOPES",
  "VASCULOPATÍA",
  "INSUF_RENAL_CRONICA",
  "ANTECEDENTRS_ICTUS",
  "DISFUNCION_ERECTIL",
  "HIGADO_GRASO",
  "APNEA_SUEÑO",
  "CANTIDAD_SUEÑO",
  "CALIDAD_SUEÑO",
  "ESTRES",
  "FACTORES_TIESGO_CARDIOPATIA",
  "OtrosAntecedentesFamiliares",
  "ENFERMEDAD_REUMATOLOGICAS",
  "PROBLEMA_CORAZON",
  "PROBLEMAS_RESPIRATORIOS",
  "SALUD_MENTAL",
  "HISTORIA_COVID",
  "AFECTACION_COVID",
  "LONG_COVID",
  "DOLOR_PECHO",
  "ECG_RITMO",
  "ECG_NORMAL",
  "USA_USTED_ACEITE_DE_OLIVA",
  "USTED_CONSUME_VERDURAS",
  "USTED_CONSUME_FRUTA",
  "USTED_CONSUME_CARNE_ROJA_EMBUTIDOS",
  "USTED_CONSUME_MANTEQUILLA_MARGARINA_NATA",
  "USTED_CONSUME_BEBIDAS_CARBONATADAS",
  "USTED_CONSUME_VINO_TINTO",
  "USTED_CONSUME_LEGUMBRES",
  "USTED_CONSUME_PESCADO_MARISCOS",
  "USTED_CONSUME_PESCADO_AZUL",
  "USTED_CONSUME_REPOSTERIA",
  "USTED_CONSUME_LECHE_DE_VACA",
  "USTED_CONSUME_QUESO",
  "USTED_CONSUME_YOGURT",
  "USTED_CONSUME_FRUTOS_SECOS",
  "USTED_CONSUME_CEREALES",
  "USTED_CONSUME_POLLO_PAVO_O_CONEJO_EN_DE_TERNERA",
  "USTED_CONSUME_ALIMENTOS_CON_SOFRITO",
  "USTED_REALIZA_ACTIVIDAD_FISICA",
  "HACE_DEPORTE",
  // --- derivadas, se emiten vacias ---
  "EdadRangos",
  "CategoriaProfesionalR",
  "HipertensionLOGI",
  "DiabetesLOGI",
  "DislipemiaLOGI",
  "ObesidadLOGI",
  "FactoresCombinados",
  "TabacoLOGI",
  "AlcoholLOGI",
  "DrogasLOGI",
  "ArritmiasLOGI",
  "SincopesLOGI",
  "VasculopatiaLOGI",
  "InsuficienciaRenalCronicaLOGI",
  "OlivaLOGI",
  "VerdurasLOGI",
  "FrutaLOGI",
  "CarneRojaLOGI",
  "MantequillasLOGI",
  "BebidasCarbonatadasLOGI",
  "VinoTintoLOGI",
  "LegumbresLOGI",
  "PescadoMariscosLOGI",
  "PescadoAzulLOGI",
  "ReposteriaLOGI",
  "LecheLOGI",
  "QuesoLOGI",
  "YogurtLOGI",
  "FrutosSecosLOGI",
  "HuevosLOGI",
  "CerealesLOGI",
  "PolloPavoLOGI",
  "AlimentosSofritoLOGI",
  "ADHDIETMEDIT",
  "AdherenciaLOGI2",
  "EstresLOGI",
  "DolorPechoLOGI",
  "HistoriaCovidLOGI",
  "FactoresRiesgoCardiopatiaLOGI",
  "filter_$",
  "PerímetroAbdominalCAT",
];

const CARDIOUNEMI_COLUMNAS_DERIVADAS = CARDIOUNEMI_ORDEN_EXPORT.slice(69);

// Columnas identificadoras que la base unificada (hoja "BASE COMPLETA") sí guarda y que
// la copia legible entrega anonimizadas. Se emiten delante de las 184 del CSV legible,
// de modo que quitando estas primeras columnas se obtiene el CSV legible exacto.
const CARDIOUNEMI_ID_COLUMNS = [
  "VISITA",
  "NOMBRES",
  "APELLIDO1",
  "APELLIDO2",
  "C.I",
];

const CARDIOUNEMI_184_COLUMNS = [
  "UNIVERSIDAD",
  "AÑO",
  "CÓDIGO",
  "Categoria_Personal",
  "FECHA",
  "CIUDAD",
  "PROVINCIA",
  "LUGAR_DE_NACIMIENTO",
  "PROVINCIA_NAC",
  "FECHA_DE_NACIMIENTO",
  "EDAD",
  "SEXO",
  "RAZA",
  "ESTADO_CIVIL",
  "CUANTOS_HIJOS__TIENE",
  "CON_QUIEN_VIVE",
  "CUANTAS_PERSONAS_CONVIVE_CON_USTES_EN_EL_HOGAR",
  "NIVEL_ESTUDIOS_OBTENIDO",
  "HORARIO_DE_TRABAJO",
  "CATEGORIA_PROFESIONAL",
  "SU_VIVIENDA_ES",
  "HORAS_TV",
  "HORAS_DORMIR",
  "HORAS_SIESTA",
  "HORAS_OCIO",
  "HORAS_SENTADOLV",
  "HORAS_SENTADOSD",
  "INGRESOS_TOTALES_MENSUALES",
  "PESO_KG",
  "TALLA_CM",
  "IMC_KGM2",
  "ASC_M2",
  "PERÍMETRO_ABDOMINAL_CM",
  "SATURACIÓN_O2",
  "TAS_TS",
  "TAS_MMHG",
  "SOPLOS_CARDIACOS",
  "EXTRATONO_SINO_TIPO",
  "PULSOSPEDIOS",
  "EXPLORACION_RESPIRATORIA",
  "EXPLORACION_ABDOMINAL",
  "HIPERTENSION",
  "DIABETES_MELLITUS",
  "DISLIPEMIA",
  "TABAQUISMO",
  "ALCOHOL",
  "DROGAS",
  "PESO_CORPORAL",
  "ARRITMIAS",
  "SINCOPES",
  "VASCULOPATÍA",
  "PRUEBA_HOLTER",
  "INSUF_RENAL_CRONICA",
  "ANTECEDENTRS_ICTUS",
  "DISFUNCION_ERECTIL",
  "HIGADO_GRASO",
  "APNEA_SUEÑO",
  "CANTIDAD_SUEÑO",
  "CALIDAD_SUEÑO",
  "CONDICIONES_AMBIENTALES",
  "TRABAJA_CON_TOXICOS",
  "BAJOS_ESTROGENOS",
  "PROTECCION_ANTICONCEPTIVO",
  "ESTRES",
  "MAL_AMBIENTE_LABORAL",
  "PERSONALIDAD_TIPO_A",
  "EXIGENTE",
  "PERFECCIONISTA",
  "HIPERACTIVO",
  "AMBICIOSO",
  "HOSTILIDAD",
  "AISLAMIENTO_SOCIAL",
  "FACTORES_TIESGO_CARDIOPATIA",
  "ANTECEDENTES_FAMILIARES",
  "ANTECEDENTES_PADRES",
  "ANTECEDENTES_MADRES",
  "PROBLEMA_CORAZON",
  "REVASCULARIZACION",
  "INSUFICIENCIA_CARDIACA_VALVULOPATIA",
  "INGRESO_HOSPITALARIO",
  "ENFERMEDAD_REUMATOLOGICAS",
  "HISTORIA_CANCER",
  "TRATAMIENTO_CANCER",
  "PROBLEMAS_RESPIRATORIOS",
  "SALUD_MENTAL",
  "ALERGIAS",
  "OTRAS",
  "HISTORIA_COVID",
  "AFECTACION_COVID",
  "SINTOMAS_COVID",
  "LONG_COVID",
  "DOLOR_PECHO",
  "MOLESTIA_CAMINAR",
  "REACCION_DOLOR_CAMINAR",
  "TIEMPO_DOLOR_CLASE_NYHA",
  "ECG_RITMO",
  "FRECUENCIA_CARDIACA_IPM",
  "EJE_ELECTRICO_A",
  "INTERVALO_RR_SEG",
  "ANCHURA_ONDA_P_MM",
  "INTERVALO_PR_SEG",
  "COMPLEJO_QR_SSEG",
  "INTERVALO_QT_SEG",
  "INTERVALO_CORREGIDO_BASET_MSEG",
  "ONDA_P_MITRAL",
  "BLOQUEO_AV",
  "BLOQUEO_SINOAURICULAR_INTERAURICULAR",
  "HEMIBLOQUEOS",
  "BLOQUEO_DE_RAMA_CUAL",
  "PATRONES",
  "SOBRECARGA_SISTOLICA",
  "DEFLEXION_INTRINSICOIDE_V5V6_SEG",
  "ONDA_DELTA",
  "CUBETA_DIGITALICA",
  "ONDA_Q_PATOLOGICA",
  "T_NEGATIVA",
  "T_NEGATIVA_COMPLEJOS",
  "ASCENSO_ST_PATOLOGICO",
  "DESCENSO_ST_PATOLOGICO",
  "ECG_NORMAL",
  "HEMATIES",
  "HEMOGLOBINA",
  "HEMATOCRITO",
  "VOLUMEN_CORPUSCULAR_MEDIO_VCM",
  "HEMOGLOBINA_CORPUSCULAR_MEDIO_HCM",
  "CONCENTRACION_HEMOGLOBINA_CORPUSCULAR_MEDIA_CHCM",
  "LEUCOCITOS",
  "PLAQUETAS",
  "TIEMPO_PROTOMBINA",
  "TSH_FUNCION_TIROIDEA",
  "UREA_FUNCION_RENAL",
  "GLUCOSA_SANGRE",
  "COLESTEROL_TOTAL_RIESGO_CARDIOVASCULAR",
  "HDL_RIESGO_CARDIOVASCULAR",
  "LDL_RIESGO_CARDIOVASCULAR",
  "TRIGLICERIDOS_RIESGO_CARDIOVASCULAR",
  "GGT_FUNCION_HEPATICA",
  "GPT_ALT_FUNCION_HEPATICA",
  "GOT_AST_FUNCION_HEPATICA",
  "CALCIFICACION_ANILLO_AORTICO",
  "MOVILIDAD_VALVULA_AORTICA",
  "VELOCIDAD_MAXIMA_ESTENOSIS_AORTICA",
  "VENTRICULO_IZQUIERDO_DILATADO",
  "VENTRICULO_IZQUIERDO_HIPERTROFICO",
  "FUNCION_SISTOLICA_VENTRICULO_IZQUIERDO",
  "FUNCION_DIASTOLICA_VENTRICULO_IZQUIERDO",
  "PRESIONES_LLENADO_VENTRICULO_IZQUIERDO",
  "ALTERACIONES_CONTRACTILIDAD",
  "VENTRICULO_DERECHO_DILATADO",
  "VENTRICULO_DERECHO_HIPERTROFICO",
  "FUNCION_SISTOLICA_VENTRICULO_DERECHO",
  "USA_USTED_ACEITE_DE_OLIVA",
  "USTED_CONSUME_VERDURAS",
  "USTED_CONSUME_FRUTA",
  "USTED_CONSUME_CARNE_ROJA_EMBUTIDOS",
  "USTED_CONSUME_MANTEQUILLA_MARGARINA_NATA",
  "USTED_CONSUME_BEBIDAS_CARBONATADAS",
  "USTED_CONSUME_VINO_TINTO",
  "USTED_CONSUME_LEGUMBRES",
  "USTED_CONSUME_PESCADO_MARISCOS",
  "USTED_CONSUME_PESCADO_AZUL",
  "USTED_CONSUME_REPOSTERIA",
  "USTED_CONSUME_LECHE_DE_VACA",
  "USTED_CONSUME_QUESO",
  "USTED_CONSUME_YOGURT",
  "USTED_CONSUME_FRUTOS_SECOS",
  "USTED_CONSUME_HUEVOS",
  "USTED_CONSUME_CEREALES",
  "USTED_CONSUME_POLLO_PAVO_O_CONEJO_EN_DE_TERNERA",
  "USTED_CONSUME_ALIMENTOS_CON_SOFRITO",
  "USTED_REALIZA_ACTIVIDAD_FISICA",
  "USTED_REALIZA_EJERCICIOS_AEROBICOS",
  "CUAL_EJERCICIOS_REALIZA",
  "CUANTAS_VECES_POR_SEMANA",
  "CUANTOS_MINUTOS_AL_DÍA",
  "USTED_REALIZA_EJERCICIOS_ANAEROBICOS",
  "CUAL_EJERCICIO_ANAEROBICO_REALIZA",
  "CUANTAS_VECES_POR_SEMANA_ANAEROBICOSS",
  "HACE_DEPORTE",
  "QUE_TIPO_DE_DEPORTE",
  "CUANTAS_VECES_POR_SEMANA_HACE_DEPORTE",
  "CUANTOS_MINUTOS_AL_DIA_HACE_DEPORTE",
  "USTED_SE_HA_REALIZADO_ESTUDIOS_CLINICOS",
  "USTED_SE_HA_REALIZADO_ESTUDIOS_DE_MAPA"
];

function obtenerValorCampo(id) {
  const el = document.getElementById(id);
  if (!el) return '';
  return (el.value !== undefined && el.value !== null) ? el.value.trim() : '';
}

function obtenerValorRadio(name) {
  const rad = document.querySelector(`input[name="${name}"]:checked`);
  return rad ? rad.value : '';
}

function esCheckboxMarcado(idOrName) {
  const chk = document.getElementById(idOrName) || document.querySelector(`input[name="${idOrName}"]`);
  return chk ? chk.checked : false;
}

function construirBloqueIdentidad() {
  const v = obtenerValorCampo;
  return {
    'VISITA': v('f_visita'),
    'NOMBRES': v('f_nombre').toUpperCase(),
    'APELLIDO1': v('f_apellido1').toUpperCase(),
    'APELLIDO2': v('f_apellido2').toUpperCase(),
    'C.I': v('f_cedula'),
  };
}

function construirRegistroCompleto() {
  const reg = Object.assign(construirBloqueIdentidad(), construirRegistro184Columnas());
  const v = obtenerValorCampo;
  const rad = obtenerValorRadio;

  // --- nombres que la unificada escribe distinto que la base legible ---
  reg['CODIGO'] = reg['CÓDIGO'];
  reg['INGRESOS_TOTALES'] = reg['INGRESOS_TOTALES_MENSUALES'];

  // --- vocabulario propio de la unificada en siete columnas ---
  // SEXO: 'Hombre'/'Mujer' en vez de 'HOMBRE'/'MUJER'
  const sx = v('f_sexo');
  reg['SEXO'] = sx === 'H' ? 'Hombre' : sx === 'M' ? 'Mujer' : '';

  // DISLIPIDEMIA: 'No tiene displemia' (con la errata de la base)
  const dis = rad('r_dislip');
  const disTrat = rad('r_dislip_trat');
  if (dis === 'No') reg['DISLIPIDEMIA'] = 'No tiene displemia';
  else if (dis === 'Si') reg['DISLIPIDEMIA'] = disTrat === 'Si' ? 'SI, tratada con farmacos' : 'SI, no tratada con farmacos';
  else reg['DISLIPIDEMIA'] = '';

  // PESO_CORPORAL: 'pero no obesidad' en vez de 'no tiene obesidad'
  if (reg['PESO_CORPORAL'] === 'Tiene sobrepeso, no tiene obesidad') {
    reg['PESO_CORPORAL'] = 'Tiene sobrepeso, pero no obesidad';
  }

  // VASCULOPATÍA: la unificada guarda 'No tienes vasculopatía'
  if (reg['VASCULOPATÍA'] === 'No tiene vasculopatía') {
    reg['VASCULOPATÍA'] = 'No tienes vasculopatía';
  }

  // LONG_COVID: aquí es solo Sí/No, el síntoma no se guarda
  const lc = rad('longcovid');
  reg['LONG_COVID'] = lc === 'Si' ? 'Sí' : lc === 'No' ? 'No' : '';

  // OtrosAntecedentesFamiliares: la unificada resume los factores, no los describe
  const padre = ['ant_padre_hta', 'ant_padre_dm', 'ant_padre_dislip'].filter(esCheckboxMarcado);
  const madre = ['ant_madre_hta', 'ant_madre_dm', 'ant_madre_dislip'].filter(esCheckboxMarcado);
  const total = padre.length + madre.length;
  if (total === 0) {
    reg['OtrosAntecedentesFamiliares'] = 'Ni padre ni madre tiene antecedentes';
  } else if (padre.includes('ant_padre_hta') && madre.includes('ant_madre_hta') && total === 2) {
    reg['OtrosAntecedentesFamiliares'] = 'Padre y madre HTA';
  } else if (padre.includes('ant_padre_dm') && madre.includes('ant_madre_dm') && total === 2) {
    reg['OtrosAntecedentesFamiliares'] = 'Padre y madre Diabetes';
  } else if (total === 1) {
    const uno = (padre[0] || madre[0]);
    reg['OtrosAntecedentesFamiliares'] = uno.includes('hta') ? 'Solo madre o padre HTA'
      : uno.includes('dm') ? 'Solo madre o padre Diabetes'
      : 'Solo madre o padre Dislipemia';
  } else if (total === 2) {
    reg['OtrosAntecedentesFamiliares'] = '2 factores diferentes';
  } else {
    reg['OtrosAntecedentesFamiliares'] = '3 factores o más';
  }

  // USTED_CONSUME_YOGURT: 'NO' en mayúsculas y 'vez/veces' según la cantidad
  const yog = rad('pred_q15_consume');
  if (yog === 'No') {
    reg['USTED_CONSUME_YOGURT'] = 'NO';
  } else if (yog === 'Si') {
    const cant = parseInt(v('pred_yogurt_cant_sem'), 10);
    const tipo = v('pred_yogurt_tipo') || 'entero';
    reg['USTED_CONSUME_YOGURT'] = (!isNaN(cant) && cant >= 2)
      ? `Sí, 2 o más veces a la semana, ${tipo}`
      : `Sí, 1 vez a la semana, ${tipo}`;
  } else {
    reg['USTED_CONSUME_YOGURT'] = '';
  }

  // PACIENTE es un autonumérico que asigna quien consolida la base
  reg['PACIENTE'] = '';
  CARDIOUNEMI_COLUMNAS_DERIVADAS.forEach(c => { reg[c] = ''; });
  return reg;
}

function construirRegistro184Columnas() {
  const v = obtenerValorCampo;
  const rad = obtenerValorRadio;
  const chk = esCheckboxMarcado;

  const reg = {};

  // 1. UNIVERSIDAD
  reg['UNIVERSIDAD'] = v('f_universidad') || 'UNEMI';

  // 2. AÑO
  const fCod = v('f_codigo');
  const fVis = v('f_fecha_visita');
  if (fCod && fCod.includes('/')) {
    reg['AÑO'] = fCod.split('/')[1];
  } else if (fVis && fVis.includes('-')) {
    reg['AÑO'] = fVis.split('-')[0];
  } else {
    reg['AÑO'] = new Date().getFullYear().toString();
  }

  // 3. CÓDIGO
  reg['CÓDIGO'] = fCod;

  // 4. Categoria_Personal
  const est = v('f_estamento');
  if (est === 'AD' || est === 'PAS') reg['Categoria_Personal'] = 'PAS';
  else if (est === 'PDI') reg['Categoria_Personal'] = 'PDI';
  else if (est === 'SERVICIO') reg['Categoria_Personal'] = 'SERVICIO';
  else if (est === 'ESTUDIANTES') reg['Categoria_Personal'] = 'ESTUDIANTES';
  else reg['Categoria_Personal'] = est || '';

  // 5. FECHA
  reg['FECHA'] = fVis;

  // 6. CIUDAD
  reg['CIUDAD'] = v('f_ciudad').toUpperCase();

  // 7. PROVINCIA
  reg['PROVINCIA'] = v('f_provincia').toUpperCase();

  // 8. LUGAR_DE_NACIMIENTO
  reg['LUGAR_DE_NACIMIENTO'] = v('f_municipio').toUpperCase();

  // 9. PROVINCIA_NAC
  const provNac = v('f_provincia_nac');
  reg['PROVINCIA_NAC'] = (provNac === 'EXTRANJERO'
    ? v('f_pais_nac')
    : (provNac || v('f_provincia'))).toUpperCase();

  // 10. FECHA_DE_NACIMIENTO
  reg['FECHA_DE_NACIMIENTO'] = v('f_fecha_nac');

  // 11. EDAD
  const edadRaw = v('f_edad');
  const edadNum = parseInt(edadRaw, 10);
  reg['EDAD'] = !isNaN(edadNum) ? edadNum : '';

  // 12. SEXO
  const sex = v('f_sexo');
  if (sex === 'H') reg['SEXO'] = 'HOMBRE';
  else if (sex === 'M') reg['SEXO'] = 'MUJER';
  else reg['SEXO'] = '';

  // 13. RAZA
  reg['RAZA'] = v('f_raza');

  // 14. ESTADO_CIVIL
  const ec = v('f_estado_civil');
  if (ec === '1_soltero') reg['ESTADO_CIVIL'] = 'SOLTERO/A';
  else if (ec === '2_casado') reg['ESTADO_CIVIL'] = 'CASADO/A';
  else if (ec === '3_divorciado') reg['ESTADO_CIVIL'] = 'DIVORCIADO/A';
  else if (ec === '4_viudo') reg['ESTADO_CIVIL'] = 'VIUDO/A';
  else if (ec === '5_union_libre') reg['ESTADO_CIVIL'] = 'UNION LIBRE';
  else reg['ESTADO_CIVIL'] = '';

  // 15. CUANTOS_HIJOS__TIENE
  const hij = v('f_hijos');
  if (hij === '0') reg['CUANTOS_HIJOS__TIENE'] = '0 Hijos';
  else if (hij === '1') reg['CUANTOS_HIJOS__TIENE'] = '1 Hijo';
  else if (hij === '2') reg['CUANTOS_HIJOS__TIENE'] = '2 Hijos';
  else if (hij === '3') reg['CUANTOS_HIJOS__TIENE'] = '3 Hijos';
  else if (hij === '4') reg['CUANTOS_HIJOS__TIENE'] = '4 Hijos';
  else if (hij === '5') reg['CUANTOS_HIJOS__TIENE'] = '5 Hijos';
  else if (hij === 'mas') reg['CUANTOS_HIJOS__TIENE'] = 'Más de 5 Hijos';
  else reg['CUANTOS_HIJOS__TIENE'] = '';

  // 16. CON_QUIEN_VIVE
  const cv = v('f_convive_con');
  const mapaConvive = {
    '1': 'Sólo/a',
    '2': 'Con su pareja',
    '3': 'Con su pareja e hijos',
    '4': 'Con sus hijos',
    '5': 'Con su pareja, hijos y otros familiares',
    '6': 'Con sus padres y hermanos/as',
    '7': 'Con otros no familiares'
  };
  reg['CON_QUIEN_VIVE'] = mapaConvive[cv] || '';

  // 17. CUANTAS_PERSONAS_CONVIVE_CON_USTES_EN_EL_HOGAR
  reg['CUANTAS_PERSONAS_CONVIVE_CON_USTES_EN_EL_HOGAR'] = v('f_convivientes');

  // 18. NIVEL_ESTUDIOS_OBTENIDO
  const estu = v('f_estudios');
  const mapaEstudios = {
    '1': 'No sabe leer o escribir',
    '2': 'Preescolar',
    '3': 'Estudios Primarios',
    '4': 'Estudios Secundarios',
    '5': 'Ciclo postbachillerato',
    '6': 'Estudios superiores',
    '7': 'Postgrado'
  };
  reg['NIVEL_ESTUDIOS_OBTENIDO'] = mapaEstudios[estu] || '';

  // 19. HORARIO_DE_TRABAJO
  const hor = v('f_horario');
  const mapaHorario = {
    '1': 'Jornada partida (Mañana/tarde)',
    '2': 'Jornada continua en mañanas y tarde',
    '3': 'Jornada continua en tardes',
    '4': 'Turnos'
  };
  reg['HORARIO_DE_TRABAJO'] = mapaHorario[hor] || '';

  // 20. CATEGORIA_PROFESIONAL
  const prof = v('f_profesion');
  const mapaProf = {
    '1': 'Profesor Permanente',
    '2': 'Profesor no permanente',
    '3': 'Personal de administración',
    '4': 'Personal de servicios',
    '5': 'Otra categoría',
    '6': 'Estudiante',
    '7': 'Jubilado'
  };
  reg['CATEGORIA_PROFESIONAL'] = mapaProf[prof] || '';

  // 21. SU_VIVIENDA_ES
  const viv = v('f_vivienda');
  const mapaViv = {
    '1': 'Propia',
    '2': 'Alquilada',
    '3': 'Vivienda familiar',
    '4': 'Otra'
  };
  reg['SU_VIVIENDA_ES'] = mapaViv[viv] || '';

  // 22 a 27: Horas sedentarias.
  // FUERA DE ALCANCE: no está en el protocolo en papel ni en los formularios del
  // usuario; se exporta siempre vacía por decisión cerrada (ver sección 15 de
  // MAPEO_DATOS_FORMULARIO.md). No reabrir sin pedirlo.
  reg['HORAS_TV'] = '';
  reg['HORAS_DORMIR'] = '';
  reg['HORAS_SIESTA'] = '';
  reg['HORAS_OCIO'] = '';
  reg['HORAS_SENTADOLV'] = '';
  reg['HORAS_SENTADOSD'] = '';

  // 28. INGRESOS_TOTALES_MENSUALES
  const ing = v('f_ingresos');
  const mapaIng = {
    '1': 'Menos de 500 dólares/mes',
    '2': 'Entre 500-1.000 dólares/mes',
    '3': '1001-1500 dolares /mes',
    '4': '1501 -2000 dólares/mes',
    '5': '2001-2500 dólares/mes',
    '6': '2501-3000  dólares/mes',
    '7': '3001-3500…………..dólares/mes',
    '8': 'Otras'
  };
  reg['INGRESOS_TOTALES_MENSUALES'] = mapaIng[ing] || '';

  // 29 a 36: Exploración física
  reg['PESO_KG'] = v('f_peso');
  reg['TALLA_CM'] = v('f_talla');
  reg['IMC_KGM2'] = v('f_imc');
  reg['ASC_M2'] = v('f_asc');
  reg['PERÍMETRO_ABDOMINAL_CM'] = v('f_perimetro');
  reg['SATURACIÓN_O2'] = v('f_sat_o2');
  reg['TAS_TS'] = v('f_tas');
  reg['TAS_MMHG'] = v('f_tsi');

  // 37. SOPLOS_CARDIACOS
  const soplosRad = rad('soplos');
  if (soplosRad === 'No') {
    reg['SOPLOS_CARDIACOS'] = 'No tiene soplo';
  } else if (soplosRad === 'Si') {
    const g = v('soplo_grado');
    const t = v('soplo_tipo');
    if (g || t) reg['SOPLOS_CARDIACOS'] = `Tiene soplos, grado ${g || '1'}, tipo ${t || 'sistólico'}`;
    else reg['SOPLOS_CARDIACOS'] = 'Tiene soplos, no conce grado ni tipo';
  } else {
    reg['SOPLOS_CARDIACOS'] = '';
  }

  // 38. EXTRATONO_SINO_TIPO
  const extRad = rad('extratonos');
  if (extRad === 'No') reg['EXTRATONO_SINO_TIPO'] = 'Ninguno';
  else if (extRad === 'Si') reg['EXTRATONO_SINO_TIPO'] = v('extratonos_detalle') || 'Presentes';
  else reg['EXTRATONO_SINO_TIPO'] = '';

  // 39. PULSOSPEDIOS
  const pPalp = rad('pulsos_palp');
  const pSim = rad('pulsos_sim');
  if (pPalp === 'No') reg['PULSOSPEDIOS'] = 'No';
  else if (pPalp === 'Si') {
    reg['PULSOSPEDIOS'] = (pSim === 'Si') ? 'Palpables, y simétricos' : 'Palpables, pero no simétricos';
  } else {
    reg['PULSOSPEDIOS'] = '';
  }

  // 40. EXPLORACION_RESPIRATORIA
  const rNorm = rad('resp_norm');
  if (rNorm === 'Si') {
    reg['EXPLORACION_RESPIRATORIA'] = 'Exploración respiratoria normal';
  } else if (rNorm === 'No') {
    const sib = rad('sibil') === 'Si';
    const est = rad('estert') === 'Si';
    if (sib && est) reg['EXPLORACION_RESPIRATORIA'] = 'No es normal, con estertores y sibilancias';
    else if (sib) reg['EXPLORACION_RESPIRATORIA'] = 'No es normal, con sibilancias pero sin estertores';
    else if (est) reg['EXPLORACION_RESPIRATORIA'] = 'No es normal, con estertores y sibilancias';
    else reg['EXPLORACION_RESPIRATORIA'] = 'Expliración respiratoria no normal';
  } else {
    reg['EXPLORACION_RESPIRATORIA'] = '';
  }

  // 41. EXPLORACION_ABDOMINAL
  const abNorm = rad('abdom_norm');
  if (abNorm === 'Si') reg['EXPLORACION_ABDOMINAL'] = 'Exploración abdominal normal';
  else if (abNorm === 'No') reg['EXPLORACION_ABDOMINAL'] = v('abd_alteracion_detalle') || 'Exploración abdominal no normal';
  else reg['EXPLORACION_ABDOMINAL'] = '';

  // 42. HIPERTENSION
  const hta = rad('r_hta');
  const htaTrat = rad('r_hta_trat');
  if (hta === 'No') reg['HIPERTENSION'] = 'No';
  else if (hta === 'Si') {
    reg['HIPERTENSION'] = (htaTrat === 'Si') ? 'Si, y si tratada' : 'Si, pero no tratada';
  } else {
    reg['HIPERTENSION'] = '';
  }

  // 43. DIABETES_MELLITUS
  const dm = rad('r_dm');
  if (dm === 'No') reg['DIABETES_MELLITUS'] = 'No tiene diabetes';
  else if (dm === 'Si') reg['DIABETES_MELLITUS'] = v('dm_clasificacion') || 'Tiene diabetes pero no especifica tipo';
  else reg['DIABETES_MELLITUS'] = '';

  // 44. DISLIPEMIA
  const dis = rad('r_dislip');
  const disTrat = rad('r_dislip_trat');
  if (dis === 'No') reg['DISLIPEMIA'] = 'No tiene dislipemia';
  else if (dis === 'Si') {
    reg['DISLIPEMIA'] = (disTrat === 'Si') ? 'SI, tratada con farmacos' : 'SI, pero no tratada con farmacos';
  } else {
    reg['DISLIPEMIA'] = '';
  }

  // 45. TABAQUISMO
  if (chk('chk_nunca_fumo')) {
    reg['TABAQUISMO'] = 'No fuma';
  } else if (chk('chk_exfumador')) {
    reg['TABAQUISMO'] = 'Exfumador hace más de un año';
  } else if (rad('r_tabaco') === 'No') {
    reg['TABAQUISMO'] = 'No fuma';
  } else if (rad('r_tabaco') === 'Si') {
    reg['TABAQUISMO'] = v('tabaco_frecuencia') || 'Sí, menos de 5 al día';
  } else {
    reg['TABAQUISMO'] = '';
  }

  // 46. ALCOHOL
  if (chk('chk_ex_alcohol')) {
    reg['ALCOHOL'] = 'Ex consumidor de alcohol';
  } else if (rad('r_alcohol') === 'No') {
    reg['ALCOHOL'] = 'No consume alcohol';
  } else if (rad('r_alcohol') === 'Si') {
    reg['ALCOHOL'] = v('alcohol_frecuencia') || 'Consume alcohol de manera ocasional';
  } else {
    reg['ALCOHOL'] = '';
  }

  // 47. DROGAS
  if (chk('chk_ex_drogas')) {
    reg['DROGAS'] = 'Ex consumidor de drogas';
  } else if (rad('r_drogas') === 'No') {
    reg['DROGAS'] = 'No consume drogas';
  } else if (rad('r_drogas') === 'Si') {
    reg['DROGAS'] = v('drogas_frecuencia') || 'Consume drogas ocasionalmente';
  } else {
    reg['DROGAS'] = '';
  }

  // 48. PESO_CORPORAL
  // El papel pregunta obesidad (ítem 8) y sobrepeso (ítem 9) por separado, y la base
  // los resume en una sola columna. La obesidad manda sobre el sobrepeso.
  const ob = rad('r_obesidad');
  const sobrepeso = rad('r_sobrepeso');
  if (ob === 'Si') {
    reg['PESO_CORPORAL'] = v('obesidad_grado') || 'Obesidad grado 1 (leve)';
  } else if (sobrepeso === 'Si') {
    reg['PESO_CORPORAL'] = 'Tiene sobrepeso, no tiene obesidad';
  } else if (ob === 'No' || sobrepeso === 'No') {
    reg['PESO_CORPORAL'] = 'No tiene sobrepeso ni obesidad';
  } else {
    reg['PESO_CORPORAL'] = '';
  }

  // 49. ARRITMIAS
  const arr = rad('r_arritmias');
  if (arr === 'No') reg['ARRITMIAS'] = 'No tiene arritmias';
  else if (arr === 'Si') reg['ARRITMIAS'] = v('arritmias_tipo') || 'Sí pero no conoce el tipo';
  else reg['ARRITMIAS'] = '';

  // 50. SINCOPES
  const sinc = rad('r_sincopes');
  if (sinc === 'No') reg['SINCOPES'] = 'No ha tenido síncope';
  else if (sinc === 'Si') reg['SINCOPES'] = v('sincopes_tipo') || 'Sí, no especifica tipo';
  else reg['SINCOPES'] = '';

  // 51. VASCULOPATÍA
  const vPerif = rad('r_vasc_perif') === 'Si';
  const vCarot = rad('r_vasc_carot') === 'Si';
  if (vPerif || vCarot) reg['VASCULOPATÍA'] = 'Si, vasculopatía periférica';
  else if (rad('r_vasc_perif') === 'No' || rad('r_vasc_carot') === 'No') reg['VASCULOPATÍA'] = 'No tiene vasculopatía';
  else reg['VASCULOPATÍA'] = 'No tiene vasculopatía';

  // 52. PRUEBA_HOLTER
  reg['PRUEBA_HOLTER'] = v('r_holter');

  // 53. INSUF_RENAL_CRONICA
  const irc = rad('r_irc');
  if (irc === 'No') reg['INSUF_RENAL_CRONICA'] = 'No tiene insuficiencia renal crónica';
  else if (irc === 'Si') reg['INSUF_RENAL_CRONICA'] = 'Sí, tiene insuficiencia renal crónica, sin diálisis ni trasplante';
  else reg['INSUF_RENAL_CRONICA'] = '';

  // 54. ANTECEDENTRS_ICTUS
  reg['ANTECEDENTRS_ICTUS'] = rad('r_ictus');

  // 55. DISFUNCION_ERECTIL
  reg['DISFUNCION_ERECTIL'] = rad('r_disfunc');

  // 56. HIGADO_GRASO
  reg['HIGADO_GRASO'] = rad('r_higado');

  // 57. APNEA_SUEÑO
  reg['APNEA_SUEÑO'] = rad('r_apnea');

  // 58. CANTIDAD_SUEÑO
  reg['CANTIDAD_SUEÑO'] = v('sueno_cantidad');

  // 59. CALIDAD_SUEÑO
  reg['CALIDAD_SUEÑO'] = v('sueno_calidad');

  // 60. CONDICIONES_AMBIENTALES
  // FUERA DE ALCANCE: no está en el protocolo en papel ni en los formularios del
  // usuario; se exporta siempre vacía por decisión cerrada (ver sección 15 de
  // MAPEO_DATOS_FORMULARIO.md). No reabrir sin pedirlo.
  reg['CONDICIONES_AMBIENTALES'] = '';

  // 61. TRABAJA_CON_TOXICOS
  reg['TRABAJA_CON_TOXICOS'] = rad('em_toxicos');

  // 62. BAJOS_ESTROGENOS
  const estrog = rad('em_estrogenos');
  if (estrog === 'No') {
    reg['BAJOS_ESTROGENOS'] = 'No tiene niveles bajos de estrógenos';
  } else if (estrog === 'Si') {
    // El papel distingue menopausia de otras causas y la base guarda ambas.
    reg['BAJOS_ESTROGENOS'] = chk('em_estrogenos_otras')
      ? 'Sí, tiene niveles bajos de estrógenos por otras causas'
      : 'Sí, tiene niveles bajos de estrógenos debido a la menopausia';
  } else {
    reg['BAJOS_ESTROGENOS'] = '';
  }

  // 63. PROTECCION_ANTICONCEPTIVO
  reg['PROTECCION_ANTICONCEPTIVO'] = rad('em_anticonceptivos');

  // 64. ESTRES
  const eTrab = rad('em_estres_trab') === 'Si';
  const eFam = rad('em_estres_fam') === 'Si';
  if (eTrab && eFam) reg['ESTRES'] = 'Si en el trabajo y en la vida familiar';
  else if (eTrab && !eFam) reg['ESTRES'] = 'Si, estres en el trabajo';
  else if (!eTrab && eFam) reg['ESTRES'] = 'Si, estres en la vida familiar';
  else if (rad('em_estres_trab') === 'No' && rad('em_estres_fam') === 'No') reg['ESTRES'] = 'No';
  else reg['ESTRES'] = '';

  // 65. MAL_AMBIENTE_LABORAL
  reg['MAL_AMBIENTE_LABORAL'] = rad('em_mal_amb');

  // 66. PERSONALIDAD_TIPO_A: la base describe el rasgo dominante en texto
  const persA = rad('em_pers_a');
  const rasgos = [
    ['em_pers_exigente', 'exigente con uno mismo y con los demás'],
    ['em_pers_perfeccionista', 'perfeccionista'],
    ['em_pers_hiperactivo', 'hiperactivo en la consecución de logros'],
    ['em_pers_ambicioso', 'ambicioso'],
    ['em_pers_hostilidad', 'hostilidad'],
    ['em_pers_aislamiento', 'aislamiento social'],
  ];
  if (persA === 'No') {
    reg['PERSONALIDAD_TIPO_A'] = 'No tiene personalidad tipo A';
  } else if (persA === 'Si') {
    const marcados = rasgos.filter(([n]) => rad(n) === 'Si').map(([, etq]) => etq);
    reg['PERSONALIDAD_TIPO_A'] = marcados.length
      ? `Sí, tiene personalidad tipo A: ${marcados.join(' y ')}`
      : 'Sí, tiene personalidad tipo A';
  } else {
    reg['PERSONALIDAD_TIPO_A'] = '';
  }

  // 67 a 72: un rasgo por columna (Sí / No, como los guarda la base)
  const siNoTilde = (name) => {
    const r = rad(name);
    return r === 'Si' ? 'Sí' : r === 'No' ? 'No' : '';
  };
  reg['EXIGENTE'] = siNoTilde('em_pers_exigente');
  reg['PERFECCIONISTA'] = siNoTilde('em_pers_perfeccionista');
  reg['HIPERACTIVO'] = siNoTilde('em_pers_hiperactivo');
  reg['AMBICIOSO'] = siNoTilde('em_pers_ambicioso');
  reg['HOSTILIDAD'] = siNoTilde('em_pers_hostilidad');
  reg['AISLAMIENTO_SOCIAL'] = siNoTilde('em_pers_aislamiento');


  // 73. FACTORES_TIESGO_CARDIOPATIA
  const antCard = rad('nm_cardiopatia');
  const antFall = rad('nm_fallecido');
  if (antCard === 'No') {
    reg['FACTORES_TIESGO_CARDIOPATIA'] = 'No tiene antecedentes familiares de cardiopatía isquémica ni fallecimiento de un familiar por esta causa';
  } else if (antCard === 'Si' && antFall === 'Si') {
    reg['FACTORES_TIESGO_CARDIOPATIA'] = 'Sí, tiene antecedentes y un familiar directo falleció antes de los 55 (varones) o 65 (mujeres)';
  } else if (antCard === 'Si') {
    reg['FACTORES_TIESGO_CARDIOPATIA'] = 'Sí, tiene antecedentes familiares de cardiopatía isquémica, pero no fallecimiento de un familiar directo';
  } else {
    reg['FACTORES_TIESGO_CARDIOPATIA'] = '';
  }

  // 74. ANTECEDENTES_FAMILIARES
  reg['ANTECEDENTES_FAMILIARES'] = v('ant_familiares_cuales');

  // 75. ANTECEDENTES_PADRES
  const pFacts = [];
  if (chk('ant_padre_hta')) pFacts.push('HTA');
  if (chk('ant_padre_dm')) pFacts.push('Diabetes');
  if (chk('ant_padre_dislip')) pFacts.push('Dislipemia');
  if (pFacts.length === 3) reg['ANTECEDENTES_PADRES'] = 'HTA, Diabetes y Dislipemia';
  else if (pFacts.length > 0) reg['ANTECEDENTES_PADRES'] = pFacts.join(' y ');
  else reg['ANTECEDENTES_PADRES'] = '';

  // 76. ANTECEDENTES_MADRES
  const mFacts = [];
  if (chk('ant_madre_hta')) mFacts.push('HTA');
  if (chk('ant_madre_dm')) mFacts.push('Diabetes');
  if (chk('ant_madre_dislip')) mFacts.push('Dislipemia');
  if (mFacts.length === 3) reg['ANTECEDENTES_MADRES'] = 'HTA, Diabetes y Dislipemia';
  else if (mFacts.length > 0) reg['ANTECEDENTES_MADRES'] = mFacts.join(' y ');
  else reg['ANTECEDENTES_MADRES'] = '';

  // 77. PROBLEMA_CORAZON
  const pCor = rad('hc_prob');
  const isq = rad('hc_isquemica');
  const isqTipo = rad('hc_isquemica_tipo');
  if (pCor === 'No' && isq !== 'Si') reg['PROBLEMA_CORAZON'] = 'No tiene problemas del corazón';
  else if (isq === 'Si' && isqTipo === 'infarto') reg['PROBLEMA_CORAZON'] = 'Cardiopatía isquémica: infarto de miocardio';
  else if (isq === 'Si' && isqTipo === 'angina') reg['PROBLEMA_CORAZON'] = 'Cardiopatía isquémica: angina';
  else if (pCor === 'Si') reg['PROBLEMA_CORAZON'] = v('prob_corazon_detalle') || 'Sí, tiene problemas del corazón, sin detalles adicionales';
  else reg['PROBLEMA_CORAZON'] = '';

  // 78. REVASCULARIZACION
  const revasc = rad('hc_revascularizacion');
  if (revasc === 'No') reg['REVASCULARIZACION'] = 'No hubo revascularización';
  else if (revasc === 'Si') {
    const cual = rad('hc_revasc_detalle');
    reg['REVASCULARIZACION'] = cual ? `Revascularización con ${cual}` : 'Si huno revascularización';
  } else reg['REVASCULARIZACION'] = '';

  // 79. INSUFICIENCIA_CARDIACA_VALVULOPATIA
  // El cuestionario las pregunta por separado (ítems 4 y 5) y la base las junta
  const insufCard = rad('hc_insuf_cardiaca');
  const valvulo = rad('hc_valvulopatia');
  if (insufCard === 'Si' && valvulo === 'Si') {
    reg['INSUFICIENCIA_CARDIACA_VALVULOPATIA'] = 'Sí, hay insuficiencia cardíaca y valvulopatía';
  } else if (insufCard === 'Si') {
    reg['INSUFICIENCIA_CARDIACA_VALVULOPATIA'] = 'Sí, hay insuficiencia cardíaca';
  } else if (valvulo === 'Si') {
    reg['INSUFICIENCIA_CARDIACA_VALVULOPATIA'] = 'Sí, hay valvulopatía';
  } else if (insufCard === 'No' || valvulo === 'No') {
    reg['INSUFICIENCIA_CARDIACA_VALVULOPATIA'] = 'No hay insuficiencia cardíaca ni valvulopatía';
  } else {
    reg['INSUFICIENCIA_CARDIACA_VALVULOPATIA'] = '';
  }

  // 80. INGRESO_HOSPITALARIO
  const ingreso = rad('hc_ingreso');
  if (ingreso === 'No') reg['INGRESO_HOSPITALARIO'] = 'No ha estado ingresado por problemas cardíacos';
  else if (ingreso === 'Si') reg['INGRESO_HOSPITALARIO'] = 'Sí, ha estado ingresado por problemas cardíacos';
  else reg['INGRESO_HOSPITALARIO'] = '';

  // 81. ENFERMEDAD_REUMATOLOGICAS
  const reum = rad('nc_reuma');
  if (reum === 'No') reg['ENFERMEDAD_REUMATOLOGICAS'] = 'No tiene enfermedad reumatológica';
  else if (reum === 'Si') reg['ENFERMEDAD_REUMATOLOGICAS'] = 'Tiene enfermedad reumatológica/inmunológica';
  else reg['ENFERMEDAD_REUMATOLOGICAS'] = '';

  // 82. HISTORIA_CANCER
  const canc = rad('nc_cancer');
  if (canc === 'No') reg['HISTORIA_CANCER'] = 'No tiene cancer';
  else if (canc === 'Si') reg['HISTORIA_CANCER'] = v('nc_cancer_tipo') || 'Otro tipo';
  else reg['HISTORIA_CANCER'] = '';

  // 83. TRATAMIENTO_CANCER
  const qt = rad('nc_cancer_qt');
  const rt = rad('nc_cancer_rt');
  if (!qt && !rt) reg['TRATAMIENTO_CANCER'] = '';
  else if (qt === 'Si' && rt === 'Si') reg['TRATAMIENTO_CANCER'] = 'Ha recibido quimioterapia y radioterapia';
  else if (qt === 'Si') reg['TRATAMIENTO_CANCER'] = 'Ha recibido quimioterapia';
  else if (rt === 'Si') reg['TRATAMIENTO_CANCER'] = 'Ha recibido radioterapia';
  else reg['TRATAMIENTO_CANCER'] = 'No ha recibido tratamiento';

  // 84. PROBLEMAS_RESPIRATORIOS
  const tieneAsma = rad('nc_asma');
  const tieneEpoc = rad('nc_epoc');
  if (!tieneAsma && !tieneEpoc) reg['PROBLEMAS_RESPIRATORIOS'] = '';
  else if (tieneAsma === 'Si' && tieneEpoc === 'Si') reg['PROBLEMAS_RESPIRATORIOS'] = 'Tiene tanto EPOC como asma';
  else if (tieneEpoc === 'Si') reg['PROBLEMAS_RESPIRATORIOS'] = 'Tiene EPOC';
  else if (tieneAsma === 'Si') reg['PROBLEMAS_RESPIRATORIOS'] = 'Tiene asma';
  else reg['PROBLEMAS_RESPIRATORIOS'] = 'No tiene EPOC ni asma';

  // 85. SALUD_MENTAL
  const tieneAnsiedad = rad('nc_ansiedad');
  const tieneDepresion = rad('nc_depresion');
  if (!tieneAnsiedad && !tieneDepresion) reg['SALUD_MENTAL'] = '';
  else if (tieneAnsiedad === 'Si' && tieneDepresion === 'Si') reg['SALUD_MENTAL'] = 'Tiene ambas: depresión y ansiedad';
  else if (tieneDepresion === 'Si') reg['SALUD_MENTAL'] = 'Tiene depresión';
  else if (tieneAnsiedad === 'Si') reg['SALUD_MENTAL'] = 'Tiene ansiedad';
  else reg['SALUD_MENTAL'] = 'No tiene depresión NI ansiedad';

  // 86. ALERGIAS
  const alerg = rad('nc_alergia');
  if (alerg === 'No') reg['ALERGIAS'] = 'No tiene alergia a medicamentos';
  else if (alerg === 'Si') reg['ALERGIAS'] = 'Sí tiene alergia a medicamentos';
  else reg['ALERGIAS'] = '';

  // 87. OTRAS
  reg['OTRAS'] = v('otras_enf_detalle');

  // 88. HISTORIA_COVID
  const covP = rad('covid_paso');
  const covIng = rad('covid_ingreso');
  if (covP === 'No') reg['HISTORIA_COVID'] = 'No ha pasado COVID-19';
  else if (covP === 'Si') {
    if (covIng === 'Si') reg['HISTORIA_COVID'] = 'Sí, pasó COVID-19, estuvo ingresado';
    else if (covIng === 'No') reg['HISTORIA_COVID'] = 'Sí, pasó COVID-19, sin ingreso';
    else reg['HISTORIA_COVID'] = 'Sí, paso COVID-19, no especifica';
  } else {
    reg['HISTORIA_COVID'] = '';
  }

  // 89. AFECTACION_COVID
  // La base guarda una sola afectación por registro, pero el papel pregunta por tres
  // (ítem 3 cardiovascular, ítem 4 pulmonar, ítem 5 otras). Si se marca más de una se
  // emite la primera según el orden del papel. El ítem 5 aporta los valores
  // 'neurológica', 'neuromuscular' y 'renal' que la base sí registra.
  const covCv = rad('covid_cv');
  const covPulm = rad('covid_pulm');
  const covOtras = rad('covid_otras');
  if (covCv === 'Si') {
    reg['AFECTACION_COVID'] = 'Sí, afectación cardiovascular';
  } else if (covPulm === 'Si') {
    reg['AFECTACION_COVID'] = 'Sí, afectación pulmonar';
  } else if (covOtras === 'Si') {
    const detalle = v('covid_otras_detalle');
    const d = detalle.toLowerCase();
    reg['AFECTACION_COVID'] =
      d.includes('neuromuscular') ? 'Sí, afectación neuromuscular'
      : d.includes('neurol') ? 'Sí, afectación neurológica'
      : d.includes('renal') ? 'Sí, afectación renal'
      : detalle ? `Sí, afectación ${detalle}`
      : 'Sí, afectación no especificada';
  } else if (covCv === 'No' || covPulm === 'No' || covOtras === 'No' || covP === 'Si') {
    reg['AFECTACION_COVID'] = 'No';
  } else {
    reg['AFECTACION_COVID'] = '';
  }

  // 90. SINTOMAS_COVID
  // FUERA DE ALCANCE: no está en el protocolo en papel ni en los formularios del
  // usuario; se exporta siempre vacía por decisión cerrada (ver sección 15 de
  // MAPEO_DATOS_FORMULARIO.md). No reabrir sin pedirlo.
  reg['SINTOMAS_COVID'] = '';

  // 91. LONG_COVID
  const lCov = rad('longcovid');
  if (lCov === 'No') reg['LONG_COVID'] = 'No presentó sintomas';
  else if (lCov === 'Si') {
    const sint = v('longcovid_sintomas');
    reg['LONG_COVID'] = sint ? `Sí, ${sint}` : 'Sí';
  } else {
    reg['LONG_COVID'] = '';
  }

  // 92. DOLOR_PECHO
  const r1 = rad('rose_1');
  if (r1 === 'No') {
    reg['DOLOR_PECHO'] = 'No tuvo dolor';
  } else if (r1 === 'Si') {
    let zonaActiva = null;
    for (let k = 1; k <= 9; k++) {
      if (chk(`rose_zona_${k}`)) {
        zonaActiva = k;
        break;
      }
    }
    reg['DOLOR_PECHO'] = zonaActiva ? `Sí, lugar ${zonaActiva}` : 'Sí, lugar no especificado';
  } else {
    reg['DOLOR_PECHO'] = '';
  }

  // 93. MOLESTIA_CAMINAR
  const r3 = rad('rose_3');
  const r4 = rad('rose_4');
  if (r3 === 'No' && r4 === 'No') reg['MOLESTIA_CAMINAR'] = 'No tiene molestia';
  else if (r3 === 'Si') reg['MOLESTIA_CAMINAR'] = 'Sí,  cuando camina a paso habitual';
  else if (r4 === 'Si') reg['MOLESTIA_CAMINAR'] = 'Sí, cuando camina cuesta arriba o apurad';
  else reg['MOLESTIA_CAMINAR'] = '';

  // 94. REACCION_DOLOR_CAMINAR
  const r5 = v('rose_5');
  if (r5 === 'se_para') reg['REACCION_DOLOR_CAMINAR'] = 'Se para y el dolor desaparece al quedarse quieto';
  else if (r5 === 'disminuye') reg['REACCION_DOLOR_CAMINAR'] = 'Disminuye la marcha y el dolor desaparece al quedarse quieto';
  else if (r3 === 'No' && r4 === 'No') reg['REACCION_DOLOR_CAMINAR'] = 'No tiene dolor al caminar';
  else reg['REACCION_DOLOR_CAMINAR'] = '';

  // 95. TIEMPO_DOLOR_CLASE_NYHA
  if (r1 === 'No') {
    reg['TIEMPO_DOLOR_CLASE_NYHA'] = 'No tiene dolor';
  } else if (r1 === 'Si') {
    const r7 = v('rose_7');
    const ny = v('nyha_clase') || 'I';
    if (r7 === '10_o_menos') reg['TIEMPO_DOLOR_CLASE_NYHA'] = `Dolor desaparece en menos de 10 minutos, NYHA Clase ${ny}`;
    else if (r7 === 'mas_10') reg['TIEMPO_DOLOR_CLASE_NYHA'] = `Dolor desaparece en más de 10 minutos, NYHA Clase ${ny}`;
    else reg['TIEMPO_DOLOR_CLASE_NYHA'] = `Dolor desaparece en menos de 10 minutos, NYHA Clase ${ny}`;
  } else {
    reg['TIEMPO_DOLOR_CLASE_NYHA'] = '';
  }

  // 96 a 119: electrocardiograma detallado (ítems 1 al 27 del PDF).
  // El vocabulario de cada columna es el que ya usa Base_CardioUNEMI_legible.csv.
  const siNoMayus = (name) => {
    const r = rad(name);
    return r === 'Si' ? 'SI' : r === 'No' ? 'NO' : '';
  };

  reg['ECG_RITMO'] = v('ecg_ritmo');                              // 1
  reg['FRECUENCIA_CARDIACA_IPM'] = v('ecg_frecuencia');           // 2
  reg['EJE_ELECTRICO_A'] = v('ecg_eje');                          // 3
  reg['INTERVALO_RR_SEG'] = v('ecg_rr');                          // 4
  reg['ANCHURA_ONDA_P_MM'] = v('ecg_onda_p_mm');                  // 5
  reg['INTERVALO_PR_SEG'] = v('ecg_pr');                          // 6
  reg['COMPLEJO_QR_SSEG'] = v('ecg_qrs');                         // 7
  reg['INTERVALO_QT_SEG'] = v('ecg_qt');                          // 8
  reg['INTERVALO_CORREGIDO_BASET_MSEG'] = v('ecg_bazet');         // 9
  reg['ONDA_P_MITRAL'] = siNoMayus('ecg_onda_p_mitral');          // 10

  // 11. Bloqueo A-V: la base guarda 'No' o 'Si, <grado>'
  const bav = rad('ecg_bloqueo_av');
  if (bav === 'No') reg['BLOQUEO_AV'] = 'No';
  else if (bav === 'Si') {
    const grado = v('ecg_bloqueo_av_grado');
    reg['BLOQUEO_AV'] = grado ? `Si, ${grado}` : 'Si, primer grado';
  } else reg['BLOQUEO_AV'] = '';

  // 12 y 13: una sola columna en la base para los dos ítems del PDF
  const bSino = rad('ecg_bloqueo_sino');
  const bInter = rad('ecg_bloqueo_inter');
  if (bSino === 'Si') reg['BLOQUEO_SINOAURICULAR_INTERAURICULAR'] = 'Si; bloqueo sinoauricular';
  else if (bInter === 'Si') reg['BLOQUEO_SINOAURICULAR_INTERAURICULAR'] = 'Si, bloqueo interauricular';
  else if (bSino === 'No' || bInter === 'No') reg['BLOQUEO_SINOAURICULAR_INTERAURICULAR'] = 'No bloqueo';
  else reg['BLOQUEO_SINOAURICULAR_INTERAURICULAR'] = '';

  // 14. Hemibloqueos
  const hemi = rad('ecg_hemibloqueos');
  reg['HEMIBLOQUEOS'] = hemi === 'Si' ? 'Sí' : hemi === 'No' ? 'No' : '';

  // 15. Bloqueo de rama: la base guarda el tipo, o 'NINGUNA'
  const rama = rad('ecg_bloqueo_rama');
  if (rama === 'No') reg['BLOQUEO_DE_RAMA_CUAL'] = 'NINGUNA';
  else if (rama === 'Si') reg['BLOQUEO_DE_RAMA_CUAL'] = (v('ecg_bloqueo_rama_cual') || 'SI').toUpperCase();
  else reg['BLOQUEO_DE_RAMA_CUAL'] = '';

  // 16, 17, 18 y 21 se resumen en la columna PATRONES
  const brugada = rad('ecg_brugada');
  const repol = rad('ecg_repol_precoz');
  const hvi = rad('ecg_hvi');
  const hvd = rad('ecg_hvd');
  const hipertrofia = hvi === 'Si' || hvd === 'Si';
  if (!brugada && !repol && !hvi && !hvd) {
    reg['PATRONES'] = '';
  } else if (repol === 'Si' && hipertrofia) {
    reg['PATRONES'] = 'Repolarización precoz presente con hipertrofias';
  } else if (repol === 'Si') {
    reg['PATRONES'] = 'Repolarización precoz presente, sin Patrón Brugada ni hipertrofias';
  } else if (brugada === 'Si' || hipertrofia) {
    reg['PATRONES'] = brugada === 'Si' ? 'Patrón Brugada presente' : 'Hipertrofias presentes';
  } else {
    reg['PATRONES'] = 'Ninguna de las condiciones presentes';
  }

  // 19. Sobrecarga sistólica
  const sobre = rad('ecg_sobrecarga');
  reg['SOBRECARGA_SISTOLICA'] = sobre === 'Si' ? 'Si' : sobre === 'No' ? 'No' : '';

  reg['DEFLEXION_INTRINSICOIDE_V5V6_SEG'] = v('ecg_deflexion');   // 20
  reg['ONDA_DELTA'] = siNoMayus('ecg_onda_delta');                // 22
  reg['CUBETA_DIGITALICA'] = siNoMayus('ecg_cubeta');             // 23
  reg['ONDA_Q_PATOLOGICA'] = siNoMayus('ecg_onda_q');             // 24

  // 25. T negativa: la base distingue la morfología simétrica
  const tneg = rad('ecg_t_negativa');
  if (tneg === 'No') reg['T_NEGATIVA'] = 'NO';
  else if (tneg === 'Si') {
    reg['T_NEGATIVA'] = rad('ecg_t_neg_morfologia') === 'Simetrica'
      ? 'Si, simetrica'
      : 'Sí, no especifica';
  } else reg['T_NEGATIVA'] = '';
  reg['T_NEGATIVA_COMPLEJOS'] = v('ecg_t_neg_complejos');

  // 26 y 27. Segmento ST
  const asc = rad('ecg_ascenso_st');
  reg['ASCENSO_ST_PATOLOGICO'] = asc === 'Si' ? 'Sí' : asc === 'No' ? 'NO' : '';
  const desc = rad('ecg_descenso_st');
  reg['DESCENSO_ST_PATOLOGICO'] = desc === 'Si' ? 'Sí' : desc === 'No' ? 'NO' : '';

  // 120. ECG_NORMAL
  const ecgRes = rad('ecg_normal');
  if (ecgRes === 'Si') reg['ECG_NORMAL'] = 'SI';
  else if (ecgRes === 'No') reg['ECG_NORMAL'] = 'NO';
  else reg['ECG_NORMAL'] = '';

  // 121 a 128: Hemograma
  reg['HEMATIES'] = v('hemo_hematies');
  reg['HEMOGLOBINA'] = v('hemo_hemoglobina');
  reg['HEMATOCRITO'] = v('hemo_hematocrito');
  reg['VOLUMEN_CORPUSCULAR_MEDIO_VCM'] = v('hemo_vcm');
  reg['HEMOGLOBINA_CORPUSCULAR_MEDIO_HCM'] = v('hemo_hcm');
  reg['CONCENTRACION_HEMOGLOBINA_CORPUSCULAR_MEDIA_CHCM'] = v('hemo_chcm');
  reg['LEUCOCITOS'] = v('hemo_leucocitos');
  reg['PLAQUETAS'] = v('hemo_plaquetas');

  // 129. TIEMPO_PROTOMBINA (la hoja de papel pide el tiempo parcial de
  // tromboplastina, que es otra prueba distinta).
  // FUERA DE ALCANCE: no está en el protocolo en papel ni en los formularios del
  // usuario; se exporta siempre vacía por decisión cerrada (ver sección 15 de
  // MAPEO_DATOS_FORMULARIO.md). No reabrir sin pedirlo.
  reg['TIEMPO_PROTOMBINA'] = '';

  // 130 a 139: Bioquímica y Enzimas
  reg['TSH_FUNCION_TIROIDEA'] = v('tiroidea_tsh');
  reg['UREA_FUNCION_RENAL'] = v('renal_urea');
  reg['GLUCOSA_SANGRE'] = v('diab_glucosa');
  reg['COLESTEROL_TOTAL_RIESGO_CARDIOVASCULAR'] = v('riesgo_colesterol');
  reg['HDL_RIESGO_CARDIOVASCULAR'] = v('riesgo_hdl');
  reg['LDL_RIESGO_CARDIOVASCULAR'] = v('riesgo_ldl');
  reg['TRIGLICERIDOS_RIESGO_CARDIOVASCULAR'] = v('riesgo_trigliceridos');
  reg['GGT_FUNCION_HEPATICA'] = v('hepatica_ggt');
  reg['GPT_ALT_FUNCION_HEPATICA'] = v('hepatica_gpt');
  reg['GOT_AST_FUNCION_HEPATICA'] = v('hepatica_got');

  // 140 a 142: Ecocardio aórtico (no capturado)
  reg['CALCIFICACION_ANILLO_AORTICO'] = rad('ea_calcificacion');
  reg['MOVILIDAD_VALVULA_AORTICA'] = v('ea_movilidad');
  reg['VELOCIDAD_MAXIMA_ESTENOSIS_AORTICA'] = v('ea_velocidad_max');

  // 143 a 151: Ecocardiograma capturado
  reg['VENTRICULO_IZQUIERDO_DILATADO'] = rad('res_vi_dilatado');
  reg['VENTRICULO_IZQUIERDO_HIPERTROFICO'] = rad('res_vi_hipertrofico');
  reg['FUNCION_SISTOLICA_VENTRICULO_IZQUIERDO'] = rad('res_fsvi');
  reg['FUNCION_DIASTOLICA_VENTRICULO_IZQUIERDO'] = rad('res_fdvi');
  reg['PRESIONES_LLENADO_VENTRICULO_IZQUIERDO'] =
    rad('res_presiones_vi') === 'Normales' ? 'Normal'
    : rad('res_presiones_vi') === 'Alteradas' ? 'Alterada'
    : '';
  reg['ALTERACIONES_CONTRACTILIDAD'] = rad('res_contractilidad');
  reg['VENTRICULO_DERECHO_DILATADO'] = rad('res_vd_dilatado');
  reg['VENTRICULO_DERECHO_HIPERTROFICO'] = rad('res_vd_hipertrofico');
  reg['FUNCION_SISTOLICA_VENTRICULO_DERECHO'] = rad('res_fsvd');

  // 152 a 170: PREDIMED (19 columnas en la base legible).
  // La base admite dos codificaciones para la misma respuesta: 'Si'/'No' a secas
  // (3 321 registros, el 94 %) y una frase descriptiva del criterio, por ejemplo
  // 'Si, dos o más al día' (228 registros, el 6 %). Se emite la simple, que es la
  // dominante; si no, cada ficha nueva quedaría en la codificación minoritaria.
  // Las de lácteos (163 a 165) sí guardan el detalle y se tratan aparte.
  // 152. USA_USTED_ACEITE_DE_OLIVA
  const pq1 = rad('pred_q1');
  const pq2 = rad('pred_q2');
  // La base usa 'Si'/'No' en 254 de 256 registros; la frase descriptiva aparece 2 veces.
  reg['USA_USTED_ACEITE_DE_OLIVA'] = pq1 || '';

  // 153. USTED_CONSUME_VERDURAS
  const pq3 = rad('pred_q3');
  reg['USTED_CONSUME_VERDURAS'] = pq3 || '';

  // 154. USTED_CONSUME_FRUTA
  const pq4 = rad('pred_q4');
  reg['USTED_CONSUME_FRUTA'] = pq4 || '';

  // 155. USTED_CONSUME_CARNE_ROJA_EMBUTIDOS
  const pq5 = rad('pred_q5');
  reg['USTED_CONSUME_CARNE_ROJA_EMBUTIDOS'] = pq5 || '';

  // 156. USTED_CONSUME_MANTEQUILLA_MARGARINA_NATA
  const pq6 = rad('pred_q6');
  reg['USTED_CONSUME_MANTEQUILLA_MARGARINA_NATA'] = pq6 || '';

  // 157. USTED_CONSUME_BEBIDAS_CARBONATADAS
  const pq7 = rad('pred_q7');
  reg['USTED_CONSUME_BEBIDAS_CARBONATADAS'] = pq7 || '';

  // 158. USTED_CONSUME_VINO_TINTO
  const pq8 = rad('pred_q8_bebe');
  reg['USTED_CONSUME_VINO_TINTO'] = pq8 || '';

  // 159. USTED_CONSUME_LEGUMBRES
  const pq9 = rad('pred_q9');
  reg['USTED_CONSUME_LEGUMBRES'] = pq9 || '';

  // 160. USTED_CONSUME_PESCADO_MARISCOS
  const pq10 = rad('pred_q10');
  reg['USTED_CONSUME_PESCADO_MARISCOS'] = pq10 || '';

  // 161. USTED_CONSUME_PESCADO_AZUL
  const pq11 = rad('pred_q11');
  reg['USTED_CONSUME_PESCADO_AZUL'] = pq11 || '';

  // 162. USTED_CONSUME_REPOSTERIA
  const pq12 = rad('pred_q12');
  reg['USTED_CONSUME_REPOSTERIA'] = pq12 || '';

  // 163. USTED_CONSUME_LECHE_DE_VACA
  const pq13 = rad('pred_q13_consume');
  if (pq13 === 'No') reg['USTED_CONSUME_LECHE_DE_VACA'] = 'No';
  else if (pq13 === 'Si') {
    const tip = v('pred_leche_tipo') || 'entera';
    reg['USTED_CONSUME_LECHE_DE_VACA'] = `Sí, 1 o más vasos al día, ${tip}`;
  } else {
    reg['USTED_CONSUME_LECHE_DE_VACA'] = '';
  }

  // 164. USTED_CONSUME_QUESO
  const pq14 = rad('pred_q14_consume');
  if (pq14 === 'No') reg['USTED_CONSUME_QUESO'] = 'NO';
  else if (pq14 === 'Si') {
    const vq = parseInt(v('pred_queso_veces_sem'), 10);
    reg['USTED_CONSUME_QUESO'] = (!isNaN(vq) && vq >= 2) ? 'Sí, 2 o más veces a la semana' : 'Sí, 1 vez a la semana';
  } else {
    reg['USTED_CONSUME_QUESO'] = '';
  }

  // 165. USTED_CONSUME_YOGURT
  const pq15 = rad('pred_q15_consume');
  if (pq15 === 'No') reg['USTED_CONSUME_YOGURT'] = 'NO';
  else if (pq15 === 'Si') {
    const ty = v('pred_yogurt_tipo') || 'entero';
    reg['USTED_CONSUME_YOGURT'] = `Sí, 1 ves a la semana, ${ty}`;
  } else {
    reg['USTED_CONSUME_YOGURT'] = '';
  }

  // 166. USTED_CONSUME_FRUTOS_SECOS
  const pq16 = rad('pred_q16');
  reg['USTED_CONSUME_FRUTOS_SECOS'] = pq16 || '';

  // 167. USTED_CONSUME_HUEVOS (el PREDIMED en papel termina en el ítem 19).
  // FUERA DE ALCANCE: no está en el protocolo en papel ni en los formularios del
  // usuario; se exporta siempre vacía por decisión cerrada (ver sección 15 de
  // MAPEO_DATOS_FORMULARIO.md). No reabrir sin pedirlo.
  reg['USTED_CONSUME_HUEVOS'] = '';

  // 168. USTED_CONSUME_CEREALES
  const pq17 = rad('pred_q17');
  reg['USTED_CONSUME_CEREALES'] = pq17 || '';

  // 169. USTED_CONSUME_POLLO_PAVO_O_CONEJO_EN_DE_TERNERA
  reg['USTED_CONSUME_POLLO_PAVO_O_CONEJO_EN_DE_TERNERA'] = rad('pred_q18');

  // 170. USTED_CONSUME_ALIMENTOS_CON_SOFRITO
  const pq19 = rad('pred_q19');
  reg['USTED_CONSUME_ALIMENTOS_CON_SOFRITO'] = pq19 || '';

  // 171 a 182: Actividad Física
  const afAct = v('af_actividad');
  // la base guarda estos dos literales sin tildes
  if (/^S/i.test(afAct)) reg['USTED_REALIZA_ACTIVIDAD_FISICA'] = 'Si realiza actividad fisica';
  else if (/^No/i.test(afAct)) reg['USTED_REALIZA_ACTIVIDAD_FISICA'] = 'No realiza ninguna actividad';
  else reg['USTED_REALIZA_ACTIVIDAD_FISICA'] = '';
  reg['USTED_REALIZA_EJERCICIOS_AEROBICOS'] = rad('af_aerobicos');
  reg['CUAL_EJERCICIOS_REALIZA'] = v('af_aero_cual');
  reg['CUANTAS_VECES_POR_SEMANA'] = v('af_aero_veces_sem');
  reg['CUANTOS_MINUTOS_AL_DÍA'] = v('af_aero_minutos_dia');
  reg['USTED_REALIZA_EJERCICIOS_ANAEROBICOS'] = rad('af_anaerobicos');
  reg['CUAL_EJERCICIO_ANAEROBICO_REALIZA'] = v('af_anaero_cual');
  reg['CUANTAS_VECES_POR_SEMANA_ANAEROBICOSS'] = v('af_anaero_veces_sem');
  reg['HACE_DEPORTE'] = rad('af_deporte');
  reg['QUE_TIPO_DE_DEPORTE'] = v('af_dep_tipo');
  reg['CUANTAS_VECES_POR_SEMANA_HACE_DEPORTE'] = v('af_dep_veces_sem');
  reg['CUANTOS_MINUTOS_AL_DIA_HACE_DEPORTE'] = v('af_dep_minutos_dia');

  // 183. USTED_SE_HA_REALIZADO_ESTUDIOS_CLINICOS
  reg['USTED_SE_HA_REALIZADO_ESTUDIOS_CLINICOS'] = rad('est_analisis') === 'Si' ? 'Si' : '';

  // 184. USTED_SE_HA_REALIZADO_ESTUDIOS_DE_MAPA
  // Sí está en el protocolo: es el ítem 2 de Factores de Riesgo en
  // CUESTIONARIO UNEMI_definitivo 2026.pdf. En el escaneo quedó tapado por una marca
  // roja, por eso se había dado por inexistente.
  reg['USTED_SE_HA_REALIZADO_ESTUDIOS_DE_MAPA'] = v('r_mapa') === 'No' ? 'No' : (v('r_mapa') ? 'Si' : '');

  return reg;
}

// FUNCIÓN PRINCIPAL DE EXPORTACIÓN (CSV O JSON)
function exportarRegistroCardioUNEMI(formato = 'csv') {
  const reg = construirRegistroCompleto();
  const codigo = reg['CÓDIGO'] || 'sin_codigo';
  const fecha = reg['FECHA'] || new Date().toISOString().split('T')[0];

  if (formato === 'json') {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(reg, null, 2));
    const dlAnchor = document.createElement('a');
    dlAnchor.setAttribute('href', dataStr);
    dlAnchor.setAttribute('download', `CardioUNEMI_${codigo}_${fecha}.json`);
    document.body.appendChild(dlAnchor);
    dlAnchor.click();
    dlAnchor.remove();
    mostrarNotificacionToast(`✓ Ficha ${codigo} exportada como JSON.`);
    return reg;
  }

  // Formato CSV (con delimitador coma, escapado seguro y BOM UTF-8)
  const headers = CARDIOUNEMI_ORDEN_EXPORT;
  const escapeCsv = (val) => {
    if (val === undefined || val === null) return '';
    const s = String(val);
    if (s.includes(',') || s.includes('"') || s.includes('\n') || s.includes('\r')) {
      return `"${s.replace(/"/g, '""')}"`;
    }
    return s;
  };

  const headerLine = headers.map(escapeCsv).join(',');
  const rowLine = headers.map(h => escapeCsv(reg[h])).join(',');
  const csvContent = '\uFEFF' + headerLine + '\n' + rowLine;

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', `CardioUNEMI_${codigo}_${fecha}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);

  mostrarNotificacionToast(`✓ Ficha ${codigo} exportada a CSV (${headers.length} columnas).`);
  return reg;
}

// LIMPIAR FORMULARIO COMPLETO PARA NUEVO PACIENTE
function limpiarFormularioCompleto() {
  const form = document.getElementById('ehrCleanForm');
  if (form) form.reset();

  // Hero strip neutral
  const setTxt = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };
  setTxt('heroNombre', '--');
  setTxt('heroEdad', '--');
  setTxt('heroCodigo', '--');
  setTxt('heroFechaNac', '--');
  setTxt('heroSexo', '--');
  setTxt('heroEstamento', '--');
  setTxt('heroFacultad', '--');
  setTxt('heroAvatar', '--');
  setTxt('heroPeso', '-- kg');
  setTxt('heroTalla', '-- cm');
  setTxt('heroImc', '--');
  setTxt('heroAsc', '--');
  setTxt('heroPresion', '-- / --');
  setTxt('heroSatO2', '--%');

  // Selects al valor neutro inicial
  const selects = form ? form.querySelectorAll('select') : [];
  selects.forEach(s => s.value = '');

  // Inputs calculados
  const setVal = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.value = val;
  };
  setVal('f_imc', '');
  setVal('f_asc', '');
  setVal('f_edad', '');
  setVal('pred_puntuacion_total', '0 / 16');

  // Fecha visita hoy
  setVal('f_fecha_visita', new Date().toISOString().split('T')[0]);

  // Predimed
  calcPredimed();
}


// Eliminación de Ficha Clínica con confirmación por contraseña
function solicitarEliminarFichaActual() {
  const urlParams = new URLSearchParams(location.search);
  const pId = urlParams.get('paciente') || (pacienteActual ? pacienteActual.id : null);
  const pNom = (pacienteActual ? pacienteActual.nombre : null) || document.getElementById('heroNombre')?.textContent || 'este paciente';
  const pCod = (pacienteActual ? pacienteActual.codigo : null) || document.getElementById('heroCodigo')?.textContent || '';
  if (!pId) {
    alert('No hay una ficha médica seleccionada para eliminar.');
    return;
  }
  if (typeof solicitarEliminarFicha === 'function') {
    solicitarEliminarFicha(pId, pNom, pCod);
  } else {
    alert('Módulo de eliminación no disponible.');
  }
}
