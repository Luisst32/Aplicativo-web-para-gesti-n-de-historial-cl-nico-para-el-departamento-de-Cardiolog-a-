// =========================================================================
// PACIENTES Y GESTIÓN DE HISTORIALES CLÍNICOS - CARDIOUNEMI
// Estructura: 1 Paciente tiene un ÚNICO Historial Clínico (Ficha Médica).
// Persistencia: Base de datos relacional PostgreSQL / Django ORM (Sprint 4)
// =========================================================================

let pacientes = [];

/**
 * Carga la cohorte activa de pacientes desde la base de datos PostgreSQL
 * a través de la API REST /clinical/api/pacientes/
 */
async function cargarPacientesDesdeServidor(filtros = {}) {
  try {
    const params = new URLSearchParams(filtros);
    const resp = await fetch(`/clinical/api/pacientes/?${params.toString()}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    if (data.success && Array.isArray(data.pacientes)) {
      pacientes = data.pacientes;
      return pacientes;
    }
    return [];
  } catch (err) {
    console.error('Error al cargar pacientes desde el servidor:', err);
    return [];
  }
}

// =========================================================================
// FUNCIONES AUXILIARES DE HISTORIALES Y PACIENTES
// =========================================================================

// Obtiene todos los historiales de un paciente ordenados por fecha descendente
function obtenerHistorialesPaciente(p) {
  if (!p) return [];
  if (!p.historiales || !Array.isArray(p.historiales) || p.historiales.length === 0) {
    const primerH = {
      id: `h_${p.id}`,
      numeroVisita: 1,
      codigoEstudio: p.codigo || '0001/2026',
      fechaVisita: `${anioDePaciente(p)}-01-15`,
      tipo: "Historial Clínico",
      motivo: "Control Anual Cardiovascular & Dieta Mediterránea",
      medico: "Dra. María Pérez - Cardiología UNEMI",
      estado: "Completada",
      peso: p.peso || 70,
      talla: p.talla || 170,
      imc: calcIMCValor(p.peso, p.talla),
      asc: calcASCValor(p.peso, p.talla),
      tas: p.tas || 120,
      tsi: p.tsi || 80,
      satO2: p.satO2 || 98,
      perimetro: p.perimetro || 85,
      riesgoGlobal: "Bajo"
    };
    p.historiales = [primerH];
  }
  return [...p.historiales].sort((a, b) => new Date(b.fechaVisita) - new Date(a.fechaVisita));
}

// Retorna el historial más reciente
function obtenerUltimoHistorial(p) {
  const lista = obtenerHistorialesPaciente(p);
  return lista.length > 0 ? lista[0] : null;
}

// Busca un historial específico por paciente e ID
function obtenerHistorialPorId(pacienteId, historialId) {
  const p = pacientes.find(item => item.id === pacienteId);
  if (!p) return null;
  const historiales = obtenerHistorialesPaciente(p);
  return historiales.find(h => h.id === historialId) || null;
}

// Año de la ficha: sale del código (0482/2026 -> 2026) o del último historial
function anioDePaciente(p) {
  if (!p) return new Date().getFullYear();
  if (p.historiales && p.historiales.length > 0) {
    const ult = p.historiales[0];
    if (ult.fechaVisita) {
      return new Date(ult.fechaVisita).getFullYear();
    }
  }
  if (p.codigo && p.codigo.includes('/')) {
    return parseInt(p.codigo.split('/')[1], 10);
  }
  return new Date().getFullYear();
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
  if (!nombre) return '--';
  return nombre.split(' ').filter(Boolean).map(n => n[0]).slice(0, 2).join('').toUpperCase();
}

function normalizarNombre(nombre) {
  return (nombre || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/\s+/g, ' ').trim();
}

function buscarPacienteExistente(nombre, fechaNac) {
  const n = normalizarNombre(nombre);
  return pacientes.find(p => p.fechaNac === fechaNac && normalizarNombre(p.nombre) === n);
}

// =========================================================================
// MODAL AGREGAR NUEVO PACIENTE
// =========================================================================

let alTerminarModalPaciente = null;

function montarModalAgregarPaciente(onListo) {
  alTerminarModalPaciente = onListo;
  if (document.getElementById('modalAdd')) return; // Evitar duplicar

  document.body.insertAdjacentHTML('beforeend', `
  <div class="modal-overlay" id="modalAdd">
    <div class="modal-card">
      <div class="modal-header">
        <div style="display:flex; align-items:center; gap:8px;">
          <span style="display:inline-flex; align-items:center; justify-content:center; width:28px; height:28px; border-radius:6px; background:var(--color-ice-blue); color:var(--color-primary-blue);">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><line x1="19" y1="8" x2="19" y2="14"></line><line x1="22" y1="11" x2="16" y2="11"></line></svg>
          </span>
          <span class="modal-title">Registrar Nuevo Paciente</span>
        </div>
        <button class="modal-close-btn" id="btnCancelX" title="Cerrar">&times;</button>
      </div>
      <div class="modal-body">
        <div class="form-field">
          <label class="field-label">Nombre y Apellidos Completos *</label>
          <input type="text" class="form-input" id="m_nombre" placeholder="Ej: Carmen Villacrés Moreira" name="m_nombre" required>
        </div>
        <div class="grid form-grid-2">
          <div class="form-field">
            <label class="field-label">Número de Cédula (10 dígitos ecuatoriana)</label>
            <input type="text" class="form-input" id="m_cedula" placeholder="Ej: 0928475612" maxlength="10" name="m_cedula">
          </div>
          <div class="form-field">
            <label class="field-label">Fecha de Nacimiento *</label>
            <input type="date" class="form-input" id="m_fecha_nac" oninput="document.getElementById('m_edad').value = calcAgeStr(this.value)" name="m_fecha_nac" required>
          </div>
        </div>
        <div class="grid form-grid-2">
          <div class="form-field">
            <label class="field-label">Edad <small>(Auto-calculada)</small></label>
            <input type="text" class="form-input calc" id="m_edad" readonly placeholder="Calculando..." name="m_edad">
          </div>
          <div class="form-field">
            <label class="field-label">Sexo *</label>
            <select class="form-select" id="m_sexo" name="m_sexo">
              <option value="H">Hombre (H)</option>
              <option value="M">Mujer (M)</option>
            </select>
          </div>
        </div>
        <div class="grid form-grid-2">
          <div class="form-field">
            <label class="field-label">Estamento UNEMI *</label>
            <select class="form-select" id="m_estamento" name="m_estamento">
              <option value="PDI">PDI (Profesor)</option>
              <option value="AD">AD (Administrativo)</option>
              <option value="SERVICIO">SERVICIO (Mantenimiento / Apoyo)</option>
              <option value="ESTUDIANTES">ESTUDIANTES</option>
            </select>
          </div>
          <div class="form-field">
            <label class="field-label">Facultad / Dependencia</label>
            <input type="text" class="form-input" id="m_facultad" placeholder="Ej: Ciencias de la Salud" name="m_facultad">
          </div>
        </div>
        <div class="grid form-grid-2">
          <div class="form-field">
            <label class="field-label">Teléfono Móvil</label>
            <input type="tel" class="form-input" id="m_telefono" placeholder="Ej: 0987654321" name="m_telefono">
          </div>
          <div class="form-field">
            <label class="field-label">Correo Electrónico</label>
            <input type="email" class="form-input" id="m_correo" placeholder="Ej: cvillacres@unemi.edu.ec" name="m_correo">
          </div>
        </div>
        <div class="modal-aviso" id="m_duplicado">
          <span id="m_duplicado_texto"></span>
          <button type="button" class="btn btn-primary" id="btnAbrirExistente">Abrir su expediente</button>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn" id="btnCancelModal">Cancelar</button>
        <button class="btn btn-primary" id="btnSaveModal">Crear y Abrir Expediente</button>
      </div>
    </div>
  </div>
  `);

  document.getElementById('btnCancelX').addEventListener('click', cerrarModalAgregarPaciente);
  document.getElementById('btnCancelModal').addEventListener('click', cerrarModalAgregarPaciente);
  document.getElementById('btnSaveModal').addEventListener('click', guardarPacienteDelModal);

  ['m_nombre', 'm_fecha_nac', 'm_cedula'].forEach(id => {
    document.getElementById(id).addEventListener('input', () => {
      document.getElementById('m_duplicado').classList.remove('visible');
    });
  });
}

function abrirModalAgregarPaciente() {
  const modal = document.getElementById('modalAdd');
  if (modal) {
    modal.classList.add('active');
    document.getElementById('m_nombre').focus();
  }
}

function cerrarModalAgregarPaciente() {
  const modal = document.getElementById('modalAdd');
  if (modal) {
    modal.classList.remove('active');
    document.getElementById('m_duplicado').classList.remove('visible');
    document.getElementById('m_nombre').value = '';
    document.getElementById('m_cedula').value = '';
    document.getElementById('m_fecha_nac').value = '';
    document.getElementById('m_edad').value = '';
    document.getElementById('m_facultad').value = '';
    document.getElementById('m_telefono').value = '';
    document.getElementById('m_correo').value = '';
  }
}

/**
 * Registra un nuevo paciente directamente en la base de datos PostgreSQL
 * enviando una petición POST a /clinical/api/pacientes/crear/ (Sprint 4 / HU-15).
 */
async function guardarPacienteDelModal() {
  const nombre = document.getElementById('m_nombre').value.trim();
  const fn = document.getElementById('m_fecha_nac').value;
  const cedula = document.getElementById('m_cedula').value.trim();
  const sexo = document.getElementById('m_sexo').value;
  const estamento = document.getElementById('m_estamento').value;
  const facultad = document.getElementById('m_facultad').value.trim();
  const telefono = document.getElementById('m_telefono').value.trim();
  const correo = document.getElementById('m_correo').value.trim();

  if (!nombre || !fn) {
    alert('Por favor ingrese al menos el nombre y la fecha de nacimiento.');
    return;
  }

  const payload = {
    nombre: nombre,
    cedula: cedula,
    fecha_nac: fn,
    sexo: sexo,
    estamento: estamento,
    facultad: facultad,
    telefono: telefono,
    correo: correo
  };

  const btnSave = document.getElementById('btnSaveModal');
  btnSave.disabled = true;
  btnSave.textContent = 'Guardando en BD...';

  try {
    const csrfToken = (typeof getCookie === 'function' ? getCookie('csrftoken') : '') || '';
    const resp = await fetch('/clinical/api/pacientes/crear/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken,
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: JSON.stringify(payload)
    });

    const data = await resp.json();

    if (!resp.ok) {
      if (data.duplicado && data.existente) {
        document.getElementById('m_duplicado_texto').textContent = data.error;
        document.getElementById('btnAbrirExistente').onclick = () => {
          cerrarModalAgregarPaciente();
          if (typeof alTerminarModalPaciente === 'function') {
            alTerminarModalPaciente(data.existente);
          }
        };
        document.getElementById('m_duplicado').classList.add('visible');
        return;
      }
      alert('Error: ' + (data.error || 'No se pudo guardar el paciente.'));
      return;
    }

    if (data.success && data.paciente) {
      const nuevo = data.paciente;
      pacientes.unshift(nuevo);
      cerrarModalAgregarPaciente();
      if (typeof alTerminarModalPaciente === 'function') {
        alTerminarModalPaciente(nuevo);
      }
    }
  } catch (err) {
    console.error('Error al registrar paciente:', err);
    alert('Error al conectar con la base de datos.');
  } finally {
    btnSave.disabled = false;
    btnSave.textContent = 'Crear y Abrir Expediente';
  }
}
