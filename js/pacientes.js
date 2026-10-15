
let pacientes = [
  {
    id: "p1",
    codigo: "0482/2026",
    nombre: "Alejandro Reyes",
    fechaNac: "1985-02-09",
    sexo: "H",
    estamento: "PDI",
    facultad: "Salud y Servicios Sociales",
    ciudad: "Milagro",
    provincia: "Guayas",
    telefono: "09876543210000",
    correo: "areyes@unemi.edu.ec",
    municipio: "Milagro",
    raza: "Mestizo",
    convivientes: "4",
    peso: 74,
    talla: 172,
    tas: 120,
    tsi: 80,
    satO2: 98,
    perimetro: 88
  },
  {
    id: "p2",
    codigo: "0483/2025",
    nombre: "Carlos Mendoza Paredes",
    fechaNac: "1984-06-15",
    sexo: "H",
    estamento: "PDI",
    facultad: "Ciencias e Ingeniería",
    ciudad: "Guayaquil",
    provincia: "Guayas",
    telefono: "09912345670000",
    correo: "cmendoza@unemi.edu.ec",
    municipio: "Guayaquil",
    raza: "Mestizo",
    convivientes: "5",
    peso: 82,
    talla: 175,
    tas: 130,
    tsi: 85,
    satO2: 97,
    perimetro: 94
  },
  {
    id: "p3",
    codigo: "0484/2026",
    nombre: "Ana Lucía Torres Moreira",
    fechaNac: "1992-11-20",
    sexo: "M",
    estamento: "AD",
    facultad: "Educación",
    ciudad: "Milagro",
    provincia: "Guayas",
    telefono: "09887766550000",
    correo: "atorres@unemi.edu.ec",
    municipio: "Milagro",
    raza: "Mestizo",
    convivientes: "1",
    peso: 58,
    talla: 162,
    tas: 110,
    tsi: 70,
    satO2: 99,
    perimetro: 72
  },
  {
    id: "p4",
    codigo: "0485/2024",
    nombre: "Beatriz Elena Gómez Castro",
    fechaNac: "1978-04-12",
    sexo: "M",
    estamento: "PDI",
    facultad: "Ciencias Sociales",
    ciudad: "Milagro",
    provincia: "Guayas",
    telefono: "09765432100000",
    correo: "bgomez@unemi.edu.ec",
    municipio: "Milagro",
    raza: "Mestizo",
    convivientes: "3",
    peso: 68,
    talla: 165,
    tas: 125,
    tsi: 82,
    satO2: 98,
    perimetro: 82
  },
  {
    id: "p5",
    codigo: "0486/2025",
    nombre: "David Fernando Zambrano",
    fechaNac: "1990-08-30",
    sexo: "H",
    estamento: "SERVICIO",
    facultad: "Mantenimiento General",
    ciudad: "Yaguachi",
    provincia: "Guayas",
    telefono: "09654321090000",
    correo: "dzambrano@unemi.edu.ec",
    municipio: "Yaguachi",
    raza: "Mestizo",
    convivientes: "4",
    peso: 79,
    talla: 170,
    tas: 135,
    tsi: 88,
    satO2: 96,
    perimetro: 90
  },
  {
    id: "p6",
    codigo: "0487/2026",
    nombre: "Gabriela Sofía Andrade Solís",
    fechaNac: "2001-03-25",
    sexo: "M",
    estamento: "ESTUDIANTES",
    facultad: "Salud y Servicios Sociales",
    ciudad: "Milagro",
    provincia: "Guayas",
    telefono: "09543210980000",
    correo: "gandrade@unemi.edu.ec",
    municipio: "Milagro",
    raza: "Mestizo",
    convivientes: "3",
    peso: 54,
    talla: 160,
    tas: 115,
    tsi: 75,
    satO2: 99,
    perimetro: 68
  },
  {
    id: "p7",
    codigo: "0488/2023",
    nombre: "Jorge Luis Cárdenas Vega",
    fechaNac: "1969-12-05",
    sexo: "H",
    estamento: "PDI",
    facultad: "Ciencias e Ingeniería",
    ciudad: "Durán",
    provincia: "Guayas",
    telefono: "09432109870000",
    correo: "jcardenas@unemi.edu.ec",
    municipio: "Durán",
    raza: "Mestizo",
    convivientes: "2",
    peso: 86,
    talla: 174,
    tas: 140,
    tsi: 90,
    satO2: 96,
    perimetro: 98
  },
  {
    id: "p8",
    codigo: "0489/2024",
    nombre: "Mariana Isabel Palacios Romero",
    fechaNac: "1982-07-19",
    sexo: "M",
    estamento: "AD",
    facultad: "Talento Humano",
    ciudad: "Milagro",
    provincia: "Guayas",
    telefono: "09321098760000",
    correo: "mpalacios@unemi.edu.ec",
    municipio: "Milagro",
    raza: "Mestizo",
    convivientes: "4",
    peso: 65,
    talla: 163,
    tas: 120,
    tsi: 78,
    satO2: 98,
    perimetro: 80
  }
];

// Los pacientes agregados desde el modal se guardan en este navegador para
// que sigan existiendo al pasar del listado a la ficha clínica.
const CLAVE_PACIENTES_NUEVOS = 'cardiounemi_pacientes_nuevos';

function leerPacientesNuevos() {
  try {
    return JSON.parse(localStorage.getItem(CLAVE_PACIENTES_NUEVOS)) || [];
  } catch (err) {
    return [];
  }
}

pacientes = leerPacientesNuevos().concat(pacientes);

// Año de la ficha: sale del código (0482/2026 -> 2026).
function anioDePaciente(p) {
  return parseInt(p.codigo.split('/')[1], 10);
}

// Cálculo exacto de edad a partir de fecha
function calcAgeStr(dateStr) {
  if (!dateStr) return '';
  const b = new Date(dateStr);
  const hoy = new Date();
  let age = hoy.getFullYear() - b.getFullYear();
  const m = hoy.getMonth() - b.getMonth();
  if (m < 0 || (m === 0 && hoy.getDate() < b.getDate())) {
    age--;
  }
  return age >= 0 ? `${age} años` : '0 años';
}

function inicialesDe(nombre) {
  return nombre.split(' ').map(n => n[0]).slice(0, 2).join('');
}

// Cada persona tiene UNA sola ficha: se considera el mismo paciente si
// coinciden nombre (sin importar mayúsculas, tildes ni espacios) y fecha
// de nacimiento.
function normalizarNombre(nombre) {
  return nombre.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/\s+/g, ' ').trim();
}

function buscarPacienteExistente(nombre, fechaNac) {
  const n = normalizarNombre(nombre);
  return pacientes.find(p => p.fechaNac === fechaNac && normalizarNombre(p.nombre) === n);
}

// MODAL AGREGAR PACIENTE. onListo(p) recibe el paciente recién creado o,
// si ya existía, el existente (botón "Abrir su ficha").
let alTerminarModalPaciente = null;

function montarModalAgregarPaciente(onListo) {
  alTerminarModalPaciente = onListo;
  document.body.insertAdjacentHTML('beforeend', `
  <div class="modal-overlay" id="modalAdd">
    <div class="modal-card">
      <div class="modal-header">
        <span class="modal-title">+ Nuevo Paciente</span>
        <button class="modal-close-btn" id="btnCancelX">&times;</button>
      </div>
      <div class="modal-body">
        <div class="form-field">
          <label class="field-label">Nombre y Apellidos</label>
          <input type="text" class="form-input" id="m_nombre" placeholder="Ej: Carmen Villacrés Moreira" name="m_nombre">
        </div>
        <div class="grid form-grid-2">
          <div class="form-field">
            <label class="field-label">Fecha de Nacimiento <small>(Calendario)</small></label>
            <input type="date" class="form-input" id="m_fecha_nac" oninput="document.getElementById('m_edad').value = calcAgeStr(this.value)" name="m_fecha_nac">
          </div>
          <div class="form-field">
            <label class="field-label">Edad <small>(Auto-calculada)</small></label>
            <input type="text" class="form-input calc" id="m_edad" readonly placeholder="Calculando..." name="m_edad">
          </div>
        </div>
        <div class="grid form-grid-2">
          <div class="form-field">
            <label class="field-label">Sexo</label>
            <select class="form-select" id="m_sexo" name="m_sexo">
              <option value="H">Hombre (H)</option>
              <option value="M">Mujer (M)</option>
            </select>
          </div>
          <div class="form-field">
            <label class="field-label">Estamento UNEMI</label>
            <select class="form-select" id="m_estamento" name="m_estamento">
              <option value="PDI">PDI (Profesor)</option>
              <option value="AD">AD (Administrativo)</option>
              <option value="SERVICIO">SERVICIO</option>
              <option value="ESTUDIANTES">ESTUDIANTES</option>
            </select>
          </div>
        </div>
        <div class="form-field">
          <label class="field-label">Facultad</label>
          <input type="text" class="form-input" id="m_facultad" placeholder="Ej: Ciencias de la Salud" name="m_facultad">
        </div>
        <div class="modal-aviso" id="m_duplicado">
          <span id="m_duplicado_texto"></span>
          <button type="button" class="btn btn-primary" id="btnAbrirExistente">Abrir su ficha</button>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn" id="btnCancelModal">Cancelar</button>
        <button class="btn btn-primary" id="btnSaveModal">Crear y Abrir Ficha</button>
      </div>
    </div>
  </div>
  `);

  document.getElementById('btnCancelX').addEventListener('click', cerrarModalAgregarPaciente);
  document.getElementById('btnCancelModal').addEventListener('click', cerrarModalAgregarPaciente);
  document.getElementById('btnSaveModal').addEventListener('click', guardarPacienteDelModal);
  // Si cambian el nombre o la fecha, el aviso de duplicado deja de aplicar.
  ['m_nombre', 'm_fecha_nac'].forEach(id => {
    document.getElementById(id).addEventListener('input', () => {
      document.getElementById('m_duplicado').classList.remove('visible');
    });
  });
}

function abrirModalAgregarPaciente() {
  document.getElementById('modalAdd').classList.add('active');
  document.getElementById('m_nombre').focus();
}

function cerrarModalAgregarPaciente() {
  document.getElementById('modalAdd').classList.remove('active');
  document.getElementById('m_duplicado').classList.remove('visible');
  document.getElementById('m_nombre').value = '';
  document.getElementById('m_fecha_nac').value = '';
  document.getElementById('m_edad').value = '';
  document.getElementById('m_facultad').value = '';
}

// Siguiente código libre del año en curso (formato 0482/2026).
function siguienteCodigoPaciente() {
  const anio = new Date().getFullYear();
  const mayor = pacientes.reduce((max, p) => Math.max(max, parseInt(p.codigo, 10) || 0), 0);
  return `${String(mayor + 1).padStart(4, '0')}/${anio}`;
}

function guardarPacienteDelModal() {
  const nombre = document.getElementById('m_nombre').value.trim();
  const fn = document.getElementById('m_fecha_nac').value;
  if (!nombre || !fn) {
    alert('Por favor ingrese al menos el nombre y la fecha de nacimiento.');
    return;
  }

  // Una persona = una ficha: si ya existe, no se crea otra.
  const existente = buscarPacienteExistente(nombre, fn);
  if (existente) {
    document.getElementById('m_duplicado_texto').textContent =
      `${existente.nombre} ya tiene ficha (${existente.codigo}).`;
    document.getElementById('btnAbrirExistente').onclick = () => {
      cerrarModalAgregarPaciente();
      alTerminarModalPaciente(existente);
    };
    document.getElementById('m_duplicado').classList.add('visible');
    return;
  }

  const nuevo = {
    id: 'p' + Date.now(),
    codigo: siguienteCodigoPaciente(),
    nombre: nombre,
    fechaNac: fn,
    sexo: document.getElementById('m_sexo').value,
    estamento: document.getElementById('m_estamento').value,
    facultad: document.getElementById('m_facultad').value || 'UNEMI'
  };

  pacientes.unshift(nuevo);
  try {
    localStorage.setItem(CLAVE_PACIENTES_NUEVOS, JSON.stringify([nuevo].concat(leerPacientesNuevos())));
  } catch (err) {
    console.error('Error al guardar el paciente en localStorage:', err);
  }

  cerrarModalAgregarPaciente();
  alTerminarModalPaciente(nuevo);
}
