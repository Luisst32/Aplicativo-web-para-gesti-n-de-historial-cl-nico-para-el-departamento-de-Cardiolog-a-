// =========================================================================
// PACIENTES Y GESTIÓN DE HISTORIALES CLÍNICOS - CARDIOUNEMI
// Estructura: 1 Paciente puede tener múltiples Historiales Clínicos (Visitas)
// =========================================================================

let pacientesBase = [
  {
    id: "p1",
    codigo: "0482/2026",
    cedula: "0923485712",
    nombre: "Alejandro Reyes",
    fechaNac: "1985-02-09",
    sexo: "H",
    estamento: "PDI",
    facultad: "Salud y Servicios Sociales",
    ciudad: "Milagro",
    provincia: "Guayas",
    telefono: "0987654321",
    correo: "areyes@unemi.edu.ec",
    municipio: "Milagro",
    raza: "Mestizo",
    convivientes: "4",
    peso: 74,
    talla: 172,
    tas: 120,
    tsi: 80,
    satO2: 98,
    perimetro: 88,
    historiales: [
      {
        id: "h_p1_2",
        numeroVisita: 2,
        codigoEstudio: "0482/2026",
        fechaVisita: "2026-02-10",
        tipo: "Control de Seguimiento",
        motivo: "Control Anual Cardiovascular & Dieta Mediterránea",
        medico: "Dra. María Pérez - Cardiología UNEMI",
        estado: "Completada",
        peso: 74,
        talla: 172,
        imc: 25.0,
        asc: 1.88,
        tas: 120,
        tsi: 80,
        satO2: 98,
        perimetro: 88,
        riesgoGlobal: "Bajo",
        diagnostico: "Evolución favorable, PA controlada en metas terapéuticas. ECG con ritmo sinusal normal. Adherencia a dieta mediterránea alta."
      },
      {
        id: "h_p1_1",
        numeroVisita: 1,
        codigoEstudio: "0482/2024",
        fechaVisita: "2024-03-15",
        tipo: "Evaluación Inicial",
        motivo: "Chequeo Cardiovascular Institucional Docente",
        medico: "Dr. Roberto Cedeño - Cardiología UNEMI",
        estado: "Completada",
        peso: 78,
        talla: 172,
        imc: 26.4,
        asc: 1.93,
        tas: 135,
        tsi: 88,
        satO2: 97,
        perimetro: 92,
        riesgoGlobal: "Moderado",
        diagnostico: "Prehipertensión reactiva a estrés laboral, sobrepeso grado I. Se indica control higiénico-dietético y seguimiento semestral."
      }
    ]
  },
  {
    id: "p2",
    codigo: "0483/2025",
    cedula: "0918745236",
    nombre: "Carlos Mendoza Paredes",
    fechaNac: "1984-06-15",
    sexo: "H",
    estamento: "PDI",
    facultad: "Ciencias e Ingeniería",
    ciudad: "Guayaquil",
    provincia: "Guayas",
    telefono: "0991234567",
    correo: "cmendoza@unemi.edu.ec",
    municipio: "Guayaquil",
    raza: "Mestizo",
    convivientes: "5",
    peso: 82,
    talla: 175,
    tas: 130,
    tsi: 85,
    satO2: 97,
    perimetro: 94,
    historiales: [
      {
        id: "h_p2_2",
        numeroVisita: 2,
        codigoEstudio: "0483/2025",
        fechaVisita: "2025-05-18",
        tipo: "Control Periódico",
        motivo: "Reevaluación de Factores de Riesgo Cardiovascular",
        medico: "Dra. María Pérez - Cardiología UNEMI",
        estado: "Completada",
        peso: 82,
        talla: 175,
        imc: 26.8,
        asc: 2.00,
        tas: 130,
        tsi: 85,
        satO2: 97,
        perimetro: 94,
        riesgoGlobal: "Moderado",
        diagnostico: "HTA grado 1 controlada con cambios de estilo de vida, perfil lipídico con mejoría progresiva. Sin signos de disfunción ventricular."
      },
      {
        id: "h_p2_1",
        numeroVisita: 1,
        codigoEstudio: "0483/2023",
        fechaVisita: "2023-11-20",
        tipo: "Evaluación Inicial",
        motivo: "Ingreso al Programa CARDIOUNEMI",
        medico: "Dr. Roberto Cedeño - Cardiología UNEMI",
        estado: "Completada",
        peso: 85,
        talla: 175,
        imc: 27.8,
        asc: 2.03,
        tas: 142,
        tsi: 92,
        satO2: 96,
        perimetro: 97,
        riesgoGlobal: "Alto",
        diagnostico: "Hipertensión arterial debutante, dislipemia mixta con HDL disminuido. Se recomienda monitoreo ambulatorio de presión arterial (MAPA)."
      }
    ]
  },
  {
    id: "p3",
    codigo: "0484/2026",
    cedula: "0934125890",
    nombre: "Ana Lucía Torres Moreira",
    fechaNac: "1992-11-20",
    sexo: "M",
    estamento: "AD",
    facultad: "Educación",
    ciudad: "Milagro",
    provincia: "Guayas",
    telefono: "0988776655",
    correo: "atorres@unemi.edu.ec",
    municipio: "Milagro",
    raza: "Mestizo",
    convivientes: "1",
    peso: 58,
    talla: 162,
    tas: 110,
    tsi: 70,
    satO2: 99,
    perimetro: 72,
    historiales: [
      {
        id: "h_p3_2",
        numeroVisita: 2,
        codigoEstudio: "0484/2026",
        fechaVisita: "2026-01-22",
        tipo: "Control Anual",
        motivo: "Vigilancia de Salud Ocupacional Administrativa",
        medico: "Dra. María Pérez - Cardiología UNEMI",
        estado: "Completada",
        peso: 58,
        talla: 162,
        imc: 22.1,
        asc: 1.62,
        tas: 110,
        tsi: 70,
        satO2: 99,
        perimetro: 72,
        riesgoGlobal: "Bajo",
        diagnostico: "Normotensa, excelente índice de masa corporal y parámetros hemodinámicos estables. Sin factores de riesgo mayores."
      },
      {
        id: "h_p3_1",
        numeroVisita: 1,
        codigoEstudio: "0484/2025",
        fechaVisita: "2025-02-14",
        tipo: "Evaluación Inicial",
        motivo: "Examen Cardiovascular de Rutina",
        medico: "Dr. Roberto Cedeño - Cardiología UNEMI",
        estado: "Completada",
        peso: 60,
        talla: 162,
        imc: 22.9,
        asc: 1.64,
        tas: 115,
        tsi: 75,
        satO2: 98,
        perimetro: 74,
        riesgoGlobal: "Bajo",
        diagnostico: "Examen físico cardiovascular normal, ruidos cardíacos rítmicos sin soplos. Adecuada capacidad funcional."
      }
    ]
  },
  {
    id: "p4",
    codigo: "0485/2024",
    cedula: "0915623489",
    nombre: "Beatriz Elena Gómez Castro",
    fechaNac: "1978-04-12",
    sexo: "M",
    estamento: "PDI",
    facultad: "Ciencias Sociales",
    ciudad: "Milagro",
    provincia: "Guayas",
    telefono: "0976543210",
    correo: "bgomez@unemi.edu.ec",
    municipio: "Milagro",
    raza: "Mestizo",
    convivientes: "3",
    peso: 68,
    talla: 165,
    tas: 125,
    tsi: 82,
    satO2: 98,
    perimetro: 82,
    historiales: [
      {
        id: "h_p4_1",
        numeroVisita: 1,
        codigoEstudio: "0485/2024",
        fechaVisita: "2024-06-11",
        tipo: "Evaluación Inicial",
        motivo: "Tamizaje Cardiovascular en Personal Docente",
        medico: "Dr. Roberto Cedeño - Cardiología UNEMI",
        estado: "Completada",
        peso: 68,
        talla: 165,
        imc: 25.0,
        asc: 1.76,
        tas: 125,
        tsi: 82,
        satO2: 98,
        perimetro: 82,
        riesgoGlobal: "Moderado",
        diagnostico: "Presión arterial limítrofe, antecedentes familiares de hipertensión y diabetes. Se recomienda incremento de actividad física aeróbica."
      }
    ]
  },
  {
    id: "p5",
    codigo: "0486/2025",
    cedula: "0927891234",
    nombre: "David Fernando Zambrano",
    fechaNac: "1990-08-30",
    sexo: "H",
    estamento: "SERVICIO",
    facultad: "Mantenimiento General",
    ciudad: "Yaguachi",
    provincia: "Guayas",
    telefono: "0965432109",
    correo: "dzambrano@unemi.edu.ec",
    municipio: "Yaguachi",
    raza: "Mestizo",
    convivientes: "4",
    peso: 79,
    talla: 170,
    tas: 135,
    tsi: 88,
    satO2: 96,
    perimetro: 90,
    historiales: [
      {
        id: "h_p5_2",
        numeroVisita: 2,
        codigoEstudio: "0486/2025",
        fechaVisita: "2025-09-04",
        tipo: "Control Periódico",
        motivo: "Monitoreo Tensional y Esfuerzo Físico Laboral",
        medico: "Dra. María Pérez - Cardiología UNEMI",
        estado: "Completada",
        peso: 79,
        talla: 170,
        imc: 27.3,
        asc: 1.93,
        tas: 135,
        tsi: 88,
        satO2: 96,
        perimetro: 90,
        riesgoGlobal: "Moderado",
        diagnostico: "Sobrepeso grado I persistente, presión sistólica en rango limítrofe. Se enfatiza reducción en ingesta sódica y pausas activas."
      },
      {
        id: "h_p5_1",
        numeroVisita: 1,
        codigoEstudio: "0486/2024",
        fechaVisita: "2024-08-19",
        tipo: "Evaluación Inicial",
        motivo: "Chequeo Ocupacional de Personal de Servicio",
        medico: "Dr. Roberto Cedeño - Cardiología UNEMI",
        estado: "Completada",
        peso: 81,
        talla: 170,
        imc: 28.0,
        asc: 1.95,
        tas: 138,
        tsi: 90,
        satO2: 96,
        perimetro: 92,
        riesgoGlobal: "Moderado",
        diagnostico: "Prehipertensión arterial, perímetro abdominal aumentado. Riesgo metabólico intermedio."
      }
    ]
  },
  {
    id: "p6",
    codigo: "0487/2026",
    cedula: "0945612378",
    nombre: "Gabriela Sofía Andrade Solís",
    fechaNac: "2001-03-25",
    sexo: "M",
    estamento: "ESTUDIANTES",
    facultad: "Salud y Servicios Sociales",
    ciudad: "Milagro",
    provincia: "Guayas",
    telefono: "0954321098",
    correo: "gandrade@unemi.edu.ec",
    municipio: "Milagro",
    raza: "Mestizo",
    convivientes: "3",
    peso: 54,
    talla: 160,
    tas: 115,
    tsi: 75,
    satO2: 99,
    perimetro: 68,
    historiales: [
      {
        id: "h_p6_1",
        numeroVisita: 1,
        codigoEstudio: "0487/2026",
        fechaVisita: "2026-03-01",
        tipo: "Evaluación Inicial",
        motivo: "Estudio Cardiovascular en Comunidad Estudiantil",
        medico: "Dra. María Pérez - Cardiología UNEMI",
        estado: "Completada",
        peso: 54,
        talla: 160,
        imc: 21.1,
        asc: 1.55,
        tas: 115,
        tsi: 75,
        satO2: 99,
        perimetro: 68,
        riesgoGlobal: "Bajo",
        diagnostico: "Excelente condición cardiovascular. Normotensa, no fumadora, actividad física adecuada. Sin factores de riesgo."
      }
    ]
  },
  {
    id: "p7",
    codigo: "0488/2023",
    cedula: "0908123456",
    nombre: "Jorge Luis Cárdenas Vega",
    fechaNac: "1969-12-05",
    sexo: "H",
    estamento: "PDI",
    facultad: "Ciencias e Ingeniería",
    ciudad: "Durán",
    provincia: "Guayas",
    telefono: "0943210987",
    correo: "jcardenas@unemi.edu.ec",
    municipio: "Durán",
    raza: "Mestizo",
    convivientes: "2",
    peso: 86,
    talla: 174,
    tas: 140,
    tsi: 90,
    satO2: 96,
    perimetro: 98,
    historiales: [
      {
        id: "h_p7_3",
        numeroVisita: 3,
        codigoEstudio: "0488/2025",
        fechaVisita: "2025-10-14",
        tipo: "Control Semestral",
        motivo: "Ajuste de Tratamiento Antihipertensivo",
        medico: "Dra. María Pérez - Cardiología UNEMI",
        estado: "Completada",
        peso: 84,
        talla: 174,
        imc: 27.7,
        asc: 2.01,
        tas: 138,
        tsi: 88,
        satO2: 97,
        perimetro: 96,
        riesgoGlobal: "Moderado",
        diagnostico: "Mejoría en el control de cifras tensionales con régimen actual. Se mantiene esquema farmacológico y dieta hiposódica."
      },
      {
        id: "h_p7_2",
        numeroVisita: 2,
        codigoEstudio: "0488/2024",
        fechaVisita: "2024-04-22",
        tipo: "Seguimiento Clínico",
        motivo: "Control de HTA y Adherencia al Tratamiento",
        medico: "Dr. Roberto Cedeño - Cardiología UNEMI",
        estado: "Completada",
        peso: 86,
        talla: 174,
        imc: 28.4,
        asc: 2.04,
        tas: 145,
        tsi: 92,
        satO2: 96,
        perimetro: 98,
        riesgoGlobal: "Alto",
        diagnostico: "HTA estadio 1 insuficientemente controlada, hipercolesterolemia. Se ajusta dosis de IECA y se solicita ecocardiograma transtorácico."
      },
      {
        id: "h_p7_1",
        numeroVisita: 1,
        codigoEstudio: "0488/2023",
        fechaVisita: "2023-01-18",
        tipo: "Evaluación Inicial",
        motivo: "Ingreso al Estudio Cardiovascular UNEMI",
        medico: "Dr. Roberto Cedeño - Cardiología UNEMI",
        estado: "Completada",
        peso: 88,
        talla: 174,
        imc: 29.1,
        asc: 2.06,
        tas: 150,
        tsi: 95,
        satO2: 95,
        perimetro: 100,
        riesgoGlobal: "Alto",
        diagnostico: "Hipertensión arterial Grado 2, sobrepeso importante, hábito tabáquico previo. Alto riesgo cardiovascular a 10 años."
      }
    ]
  },
  {
    id: "p8",
    codigo: "0489/2024",
    cedula: "0921478563",
    nombre: "Mariana Isabel Palacios Romero",
    fechaNac: "1982-07-19",
    sexo: "M",
    estamento: "AD",
    facultad: "Talento Humano",
    ciudad: "Milagro",
    provincia: "Guayas",
    telefono: "0932109876",
    correo: "mpalacios@unemi.edu.ec",
    municipio: "Milagro",
    raza: "Mestizo",
    convivientes: "4",
    peso: 65,
    talla: 163,
    tas: 120,
    tsi: 78,
    satO2: 98,
    perimetro: 80,
    historiales: [
      {
        id: "h_p8_1",
        numeroVisita: 1,
        codigoEstudio: "0489/2024",
        fechaVisita: "2024-11-05",
        tipo: "Evaluación Inicial",
        motivo: "Control de Salud Preventiva en Talento Humano",
        medico: "Dr. Roberto Cedeño - Cardiología UNEMI",
        estado: "Completada",
        peso: 65,
        talla: 163,
        imc: 24.5,
        asc: 1.71,
        tas: 120,
        tsi: 78,
        satO2: 98,
        perimetro: 80,
        riesgoGlobal: "Bajo",
        diagnostico: "Parámetros biométricos y hemodinámicos normales. Normotensa, glucemia y lípidos dentro de rangos normales."
      }
    ]
  },
  {
    id: "p9",
    codigo: "0493/2026",
    cedula: "0914872391",
    nombre: "Elena Villacrés Saldaña",
    fechaNac: "1988-06-18",
    sexo: "M",
    estamento: "PDI",
    facultad: "Educación",
    ciudad: "Milagro",
    provincia: "Guayas",
    telefono: "0991234567",
    correo: "evillacres@unemi.edu.ec",
    municipio: "Milagro",
    raza: "Mestizo",
    convivientes: "3",
    peso: 62,
    talla: 165,
    tas: 118,
    tsi: 75,
    satO2: 99,
    perimetro: 76,
    historiales: [
      {
        id: "h_p9_1",
        numeroVisita: 1,
        codigoEstudio: "0493/2026",
        fechaVisita: "2026-02-05",
        tipo: "Evaluación Periódica Anual",
        motivo: "Chequeo Cardiovascular de Rutina",
        medico: "Dra. María Pérez - Cardiología UNEMI",
        estado: "Completada",
        peso: 62,
        talla: 165,
        imc: 22.8,
        asc: 1.68,
        tas: 118,
        tsi: 75,
        satO2: 99,
        perimetro: 76,
        riesgoGlobal: "Bajo",
        diagnostico: "Paciente asintomática. Auscultación cardíaca normal. Estilo de vida activo."
      }
    ]
  },
  {
    id: "p10",
    codigo: "0494/2026",
    cedula: "0925781932",
    nombre: "Jorge Washington Caicedo",
    fechaNac: "1974-09-30",
    sexo: "H",
    estamento: "SERVICIO",
    facultad: "Servicios Generales",
    ciudad: "Milagro",
    provincia: "Guayas",
    telefono: "0982345678",
    correo: "jcaicedo@unemi.edu.ec",
    municipio: "Milagro",
    raza: "Afroecuatoriano",
    convivientes: "2",
    peso: 82,
    talla: 175,
    tas: 125,
    tsi: 82,
    satO2: 98,
    perimetro: 92,
    historiales: [
      {
        id: "h_p10_1",
        numeroVisita: 1,
        codigoEstudio: "0494/2026",
        fechaVisita: "2026-01-18",
        tipo: "Evaluación Inicial",
        motivo: "Control de Salud Ocupacional",
        medico: "Dr. Roberto Cedeño - Cardiología UNEMI",
        estado: "Completada",
        peso: 82,
        talla: 175,
        imc: 26.8,
        asc: 1.99,
        tas: 125,
        tsi: 82,
        satO2: 98,
        perimetro: 92,
        riesgoGlobal: "Bajo",
        diagnostico: "Sobrepeso leve sin alteraciones cardiovasculares mayores. Se indica actividad física regular."
      }
    ]
  },
  {
    id: "p11",
    codigo: "0495/2025",
    cedula: "0941982734",
    nombre: "Diana Marcela Zambrano",
    fechaNac: "1994-12-04",
    sexo: "M",
    estamento: "AD",
    facultad: "Vinculación",
    ciudad: "Milagro",
    provincia: "Guayas",
    telefono: "0973456789",
    correo: "dzambrano@unemi.edu.ec",
    municipio: "Milagro",
    raza: "Mestizo",
    convivientes: "1",
    peso: 56,
    talla: 160,
    tas: 110,
    tsi: 70,
    satO2: 99,
    perimetro: 70,
    historiales: [
      {
        id: "h_p11_1",
        numeroVisita: 1,
        codigoEstudio: "0495/2025",
        fechaVisita: "2025-11-20",
        tipo: "Evaluación Inicial",
        motivo: "Revisión Preventiva de Ingreso",
        medico: "Dra. María Pérez - Cardiología UNEMI",
        estado: "Completada",
        peso: 56,
        talla: 160,
        imc: 21.9,
        asc: 1.57,
        tas: 110,
        tsi: 70,
        satO2: 99,
        perimetro: 70,
        riesgoGlobal: "Bajo",
        diagnostico: "Excelente estado cardiovascular general. Presión arterial óptima."
      }
    ]
  },
  {
    id: "p12",
    codigo: "0496/2025",
    cedula: "0938219485",
    nombre: "Fernando Javier Morales",
    fechaNac: "1980-04-12",
    sexo: "H",
    estamento: "PDI",
    facultad: "Salud y Servicios Sociales",
    ciudad: "Milagro",
    provincia: "Guayas",
    telefono: "0964567890",
    correo: "fmorales@unemi.edu.ec",
    municipio: "Milagro",
    raza: "Mestizo",
    convivientes: "4",
    peso: 76,
    talla: 170,
    tas: 122,
    tsi: 80,
    satO2: 98,
    perimetro: 86,
    historiales: [
      {
        id: "h_p12_1",
        numeroVisita: 1,
        codigoEstudio: "0496/2025",
        fechaVisita: "2025-09-14",
        tipo: "Control de Seguimiento",
        motivo: "Control de Presión Arterial y Factores de Riesgo",
        medico: "Dr. Roberto Cedeño - Cardiología UNEMI",
        estado: "Completada",
        peso: 76,
        talla: 170,
        imc: 26.3,
        asc: 1.89,
        tas: 122,
        tsi: 80,
        satO2: 98,
        perimetro: 86,
        riesgoGlobal: "Bajo",
        diagnostico: "Control adecuado de presión arterial. Plan de nutrición cardioprotectora en curso."
      }
    ]
  }
];

// Claves de persistencia en localStorage
const CLAVE_PACIENTES_NUEVOS = 'cardiounemi_pacientes_nuevos';
const CLAVE_HISTORIALES_MODIFICADOS = 'cardiounemi_historiales_pacientes';

function leerPacientesNuevos() {
  try {
    return JSON.parse(localStorage.getItem(CLAVE_PACIENTES_NUEVOS)) || [];
  } catch (err) {
    return [];
  }
}

function leerHistorialesModificados() {
  try {
    return JSON.parse(localStorage.getItem(CLAVE_HISTORIALES_MODIFICADOS)) || {};
  } catch (err) {
    return {};
  }
}

// Inicialización de la lista de pacientes con clonación profunda
let pacientes = leerPacientesNuevos().concat(JSON.parse(JSON.stringify(pacientesBase)));

// Aplicar historiales personalizados/modificados guardados en localStorage
(function aplicarHistorialesGuardados() {
  const modifs = leerHistorialesModificados();
  pacientes.forEach(p => {
    if (modifs[p.id]) {
      p.historiales = modifs[p.id];
      // Sincronizar signos vitales raíz con el último historial
      const ult = p.historiales[0];
      if (ult) {
        if (ult.peso) p.peso = ult.peso;
        if (ult.talla) p.talla = ult.talla;
        if (ult.tas) p.tas = ult.tas;
        if (ult.tsi) p.tsi = ult.tsi;
        if (ult.satO2) p.satO2 = ult.satO2;
        if (ult.perimetro) p.perimetro = ult.perimetro;
      }
    }
  });
})();

// Guardar los historiales modificados para un paciente
function persistirHistorialesPaciente(pacienteId, listaHistoriales) {
  try {
    const modifs = leerHistorialesModificados();
    modifs[pacienteId] = listaHistoriales;
    localStorage.setItem(CLAVE_HISTORIALES_MODIFICADOS, JSON.stringify(modifs));

    // Si es un paciente nuevo agregado por modal, actualizarlo en su lista
    const nuevos = leerPacientesNuevos();
    const idx = nuevos.findIndex(p => p.id === pacienteId);
    if (idx !== -1) {
      nuevos[idx].historiales = listaHistoriales;
      localStorage.setItem(CLAVE_PACIENTES_NUEVOS, JSON.stringify(nuevos));
    }
  } catch (err) {
    console.error('Error al persistir historiales:', err);
  }
}

// =========================================================================
// FUNCIONES AUXILIARES DE HISTORIALES Y PACIENTES
// =========================================================================

// Obtiene todos los historiales de un paciente ordenados por fecha descendente
function obtenerHistorialesPaciente(p) {
  if (!p) return [];
  if (!p.historiales || !Array.isArray(p.historiales) || p.historiales.length === 0) {
    // Si no tiene historiales (por ejemplo, paciente creado antes de este formato),
    // creamos uno inicial por defecto con sus datos actuales
    const primerH = {
      id: `h_${p.id}_1`,
      numeroVisita: 1,
      codigoEstudio: p.codigo || siguienteCodigoPaciente(),
      fechaVisita: `${anioDePaciente(p)}-01-15`,
      tipo: "Evaluación Inicial",
      motivo: "Chequeo Cardiovascular de Ingreso",
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
      riesgoGlobal: "Bajo",
      diagnostico: "Evaluación cardiovascular clínica sin hallazgos patológicos agudos."
    };
    p.historiales = [primerH];
  }

  // Ordenar: más reciente primero (por fecha o numeroVisita descendente)
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

// Crea y registra un nuevo historial clínico para un paciente
function crearNuevoHistorial(pacienteId, datosHistorial) {
  const p = pacientes.find(item => item.id === pacienteId);
  if (!p) return null;

  if (!p.historiales) p.historiales = [];

  const nuevoNumero = p.historiales.length + 1;
  const hoyStr = new Date().toISOString().split('T')[0];
  const anioActual = new Date().getFullYear();

  const nuevoHistorial = {
    id: `h_${pacienteId}_${Date.now()}`,
    numeroVisita: nuevoNumero,
    codigoEstudio: `${p.codigo.split('/')[0]}/${anioActual}`,
    fechaVisita: datosHistorial.fechaVisita || hoyStr,
    tipo: datosHistorial.tipo || (nuevoNumero === 1 ? "Evaluación Inicial" : "Control de Seguimiento"),
    motivo: datosHistorial.motivo || "Consulta Cardiológica y Control de Factores de Riesgo",
    medico: datosHistorial.medico || "Dra. María Pérez - Cardiología UNEMI",
    estado: "En proceso",
    peso: parseFloat(datosHistorial.peso) || p.peso || 70,
    talla: parseFloat(datosHistorial.talla) || p.talla || 170,
    tas: parseInt(datosHistorial.tas, 10) || p.tas || 120,
    tsi: parseInt(datosHistorial.tsi, 10) || p.tsi || 80,
    satO2: parseInt(datosHistorial.satO2, 10) || p.satO2 || 98,
    perimetro: parseFloat(datosHistorial.perimetro) || p.perimetro || 85,
    riesgoGlobal: datosHistorial.riesgoGlobal || "Bajo",
    diagnostico: datosHistorial.diagnostico || "Nueva consulta médica registrada. Pendiente completar exploración y cuestionarios."
  };

  nuevoHistorial.imc = calcIMCValor(nuevoHistorial.peso, nuevoHistorial.talla);
  nuevoHistorial.asc = calcASCValor(nuevoHistorial.peso, nuevoHistorial.talla);

  // Colocar como el más reciente al inicio
  p.historiales.unshift(nuevoHistorial);

  // Sincronizar signos vitales raíz del paciente
  p.peso = nuevoHistorial.peso;
  p.talla = nuevoHistorial.talla;
  p.tas = nuevoHistorial.tas;
  p.tsi = nuevoHistorial.tsi;
  p.satO2 = nuevoHistorial.satO2;
  p.perimetro = nuevoHistorial.perimetro;

  persistirHistorialesPaciente(pacienteId, p.historiales);
  return nuevoHistorial;
}

// Cálculos matemáticos
function calcIMCValor(peso, talla) {
  if (!peso || !talla) return 0;
  const tM = talla / 100;
  return parseFloat((peso / (tM * tM)).toFixed(1));
}

function calcASCValor(peso, talla) {
  if (!peso || !talla) return 0;
  return parseFloat(Math.sqrt((talla * peso) / 3600).toFixed(2));
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
            <label class="field-label">Número de Cédula</label>
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

  ['m_nombre', 'm_fecha_nac'].forEach(id => {
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

  const existente = buscarPacienteExistente(nombre, fn);
  if (existente) {
    document.getElementById('m_duplicado_texto').textContent =
      `${existente.nombre} ya tiene expediente registrado (${existente.codigo}).`;
    document.getElementById('btnAbrirExistente').onclick = () => {
      cerrarModalAgregarPaciente();
      if (typeof alTerminarModalPaciente === 'function') {
        alTerminarModalPaciente(existente);
      }
    };
    document.getElementById('m_duplicado').classList.add('visible');
    return;
  }

  const hoyStr = new Date().toISOString().split('T')[0];
  const nuevoCodigo = siguienteCodigoPaciente();
  const nuevoId = 'p' + Date.now();

  const nuevo = {
    id: nuevoId,
    codigo: nuevoCodigo,
    cedula: document.getElementById('m_cedula').value.trim() || '0900000000',
    nombre: nombre,
    fechaNac: fn,
    sexo: document.getElementById('m_sexo').value,
    estamento: document.getElementById('m_estamento').value,
    facultad: document.getElementById('m_facultad').value.trim() || 'UNEMI',
    telefono: document.getElementById('m_telefono').value.trim() || '',
    correo: document.getElementById('m_correo').value.trim() || '',
    ciudad: 'Milagro',
    provincia: 'Guayas',
    peso: 70,
    talla: 170,
    tas: 120,
    tsi: 80,
    satO2: 98,
    perimetro: 85,
    historiales: [
      {
        id: `h_${nuevoId}_1`,
        numeroVisita: 1,
        codigoEstudio: nuevoCodigo,
        fechaVisita: hoyStr,
        tipo: "Evaluación Inicial",
        motivo: "Chequeo Cardiovascular de Ingreso",
        medico: "Dra. María Pérez - Cardiología UNEMI",
        estado: "En proceso",
        peso: 70,
        talla: 170,
        imc: 24.2,
        asc: 1.82,
        tas: 120,
        tsi: 80,
        satO2: 98,
        perimetro: 85,
        riesgoGlobal: "Bajo",
        diagnostico: "Paciente registrado en el sistema. Pendiente completar evaluación de riesgo y hábitos."
      }
    ]
  };

  pacientes.unshift(nuevo);
  try {
    localStorage.setItem(CLAVE_PACIENTES_NUEVOS, JSON.stringify([nuevo].concat(leerPacientesNuevos())));
  } catch (err) {
    console.error('Error al guardar el paciente en localStorage:', err);
  }

  cerrarModalAgregarPaciente();
  if (typeof alTerminarModalPaciente === 'function') {
    alTerminarModalPaciente(nuevo);
  }
}
