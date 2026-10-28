import datetime
from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import (
    Country, Province, Canton, Institution,
    Sex, Ethnicity, StaffCategory, ProfessionalCategory,
    EducationLevel, IncomeRange, MaritalStatus,
    LivingSituation, HousingType, WorkSchedule,
    EcgRhythm, QuestionnaireSection, Question, AnswerOption
)
from security.models import User
from clinical.models import Patient, Visit, Anthropometry, VitalSigns


class Command(BaseCommand):
    help = "Seeds initial catalogs, questionnaire sections/questions, and baseline patients into the database."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando carga de catálogos y datos iniciales (Sprint 4 / HU-10)..."))

        # 1. Geografía
        ecuador, _ = Country.objects.get_or_create(iso_alpha3="ECU", defaults={"name": "Ecuador"})

        provincias_info = [
            ("EC-A", "Azuay", "01"),
            ("EC-B", "Bolívar", "02"),
            ("EC-F", "Cañar", "03"),
            ("EC-C", "Carchi", "04"),
            ("EC-X", "Cotopaxi", "05"),
            ("EC-H", "Chimborazo", "06"),
            ("EC-O", "El Oro", "07"),
            ("EC-E", "Esmeraldas", "08"),
            ("EC-G", "Guayas", "09"),
            ("EC-I", "Imbabura", "10"),
            ("EC-L", "Loja", "11"),
            ("EC-R", "Los Ríos", "12"),
            ("EC-M", "Manabí", "13"),
            ("EC-S", "Morona Santiago", "14"),
            ("EC-N", "Napo", "15"),
            ("EC-Y", "Pastaza", "16"),
            ("EC-P", "Pichincha", "17"),
            ("EC-T", "Tungurahua", "18"),
            ("EC-Z", "Zamora Chinchipe", "19"),
            ("EC-W", "Galápagos", "20"),
            ("EC-U", "Sucumbíos", "21"),
            ("EC-D", "Orellana", "22"),
            ("EC-SD", "Santo Domingo de los Tsáchilas", "23"),
            ("EC-SE", "Santa Elena", "24"),
        ]
        provincias = {}
        prov_dpa_map = {}
        for iso, nombre, dpa_pref in provincias_info:
            prov, _ = Province.objects.get_or_create(
                country=ecuador, iso_code=iso, defaults={"name": nombre}
            )
            provincias[nombre] = prov
            prov_dpa_map[nombre] = dpa_pref

        cantones_dict = {
            'Azuay': ['Cuenca', 'Camilo Ponce Enríquez', 'Chordeleg', 'El Pan', 'Girón', 'Guachapala', 'Gualaceo', 'Nabón', 'Oña', 'Paute', 'Pucará', 'San Fernando', 'Santa Isabel', 'Sevilla de Oro', 'Sígsig'],
            'Bolívar': ['Guaranda', 'Caluma', 'Chillanes', 'Chimbo', 'Echeandía', 'Las Naves', 'San Miguel'],
            'Cañar': ['Azogues', 'Biblián', 'Cañar', 'Déleg', 'El Tambo', 'La Troncal', 'Suscal'],
            'Carchi': ['Tulcán', 'Bolívar', 'Espejo', 'Mira', 'Montúfar', 'San Pedro de Huaca'],
            'Cotopaxi': ['Latacunga', 'La Maná', 'Pangua', 'Pujilí', 'Salcedo', 'Saquisilí', 'Sigchos'],
            'Chimborazo': ['Riobamba', 'Alausí', 'Chambo', 'Chunchi', 'Colta', 'Cumandá', 'Guamote', 'Guano', 'Pallatanga', 'Penipe'],
            'El Oro': ['Machala', 'Arenillas', 'Atahualpa', 'Balsas', 'Chilla', 'El Guabo', 'Huaquillas', 'Las Lajas', 'Marcabelí', 'Pasaje', 'Piñas', 'Portovelo', 'Santa Rosa', 'Zaruma'],
            'Esmeraldas': ['Esmeraldas', 'Atacames', 'Eloy Alfaro', 'Muisne', 'Quinindé', 'Rioverde', 'San Lorenzo'],
            'Galápagos': ['San Cristóbal', 'Isabela', 'Santa Cruz'],
            'Guayas': ['Milagro', 'Guayaquil', 'Alfredo Baquerizo Moreno (Juján)', 'Balao', 'Balzar', 'Colimes', 'Daule', 'Durán', 'El Empalme', 'El Triunfo', 'General Antonio Elizalde (Bucay)', 'Isidro Ayora', 'Lomas de Sargentillo', 'Marcelino Maridueña', 'Naranjal', 'Naranjito', 'Nobol', 'Palestina', 'Pedro Carbo', 'Playas (General Villamil)', 'Salitre (Urbina Jado)', 'Samborondón', 'Santa Lucía', 'Simón Bolívar', 'Yaguachi'],
            'Imbabura': ['Ibarra', 'Antonio Ante', 'Cotacachi', 'Otavalo', 'Pimampiro', 'San Miguel de Urcuquí'],
            'Loja': ['Loja', 'Calvas', 'Catamayo', 'Celica', 'Chaguarpamba', 'Espíndola', 'Gonzanamá', 'Macará', 'Olmedo', 'Paltas', 'Pindal', 'Puyango', 'Quilanga', 'Saraguro', 'Sozoranga', 'Zapotillo'],
            'Los Ríos': ['Babahoyo', 'Baba', 'Buena Fe', 'Mocache', 'Montalvo', 'Palenque', 'Puebloviejo', 'Quevedo', 'Quinsaloma', 'Urdaneta', 'Valencia', 'Ventanas', 'Vinces'],
            'Manabí': ['Portoviejo', 'Bolívar (Calceta)', 'Chone', 'El Carmen', 'Flavio Alfaro', 'Jama', 'Jaramijó', 'Jipijapa', 'Junín', 'Manta', 'Montecristi', 'Olmedo', 'Paján', 'Pedernales', 'Pichincha', 'Puerto López', 'Rocafuerte', 'San Vicente', 'Santa Ana', 'Sucre (Bahía de Caráquez)', 'Tosagua', '24 de Mayo'],
            'Morona Santiago': ['Morona (Macas)', 'Gualaquiza', 'Huamboya', 'Limón Indanza', 'Logroño', 'Pablo Sexto', 'Palora', 'San Juan Bosco', 'Santiago de Méndez', 'Sucúa', 'Taisha', 'Tiwintza'],
            'Napo': ['Tena', 'Archidona', 'Carlos Julio Arosemena Tola', 'El Chaco', 'Quijos (Baeza)'],
            'Orellana': ['Francisco de Orellana (Coca)', 'Aguarico', 'La Joya de los Sachas', 'Loreto'],
            'Pastaza': ['Pastaza (Puyo)', 'Arajuno', 'Mera', 'Santa Clara'],
            'Pichincha': ['Quito', 'Cayambe', 'Mejía', 'Pedro Moncayo', 'Pedro Vicente Maldonado', 'Puerto Quito', 'Rumiñahui', 'San Miguel de Los Bancos'],
            'Santa Elena': ['Santa Elena', 'La Libertad', 'Salinas'],
            'Santo Domingo de los Tsáchilas': ['Santo Domingo', 'La Concordia'],
            'Sucumbíos': ['Lago Agrio (Nueva Loja)', 'Cascales', 'Cuyabeno', 'Gonzalo Pizarro', 'Putumayo', 'Shushufindi', 'Sucumbíos'],
            'Tungurahua': ['Ambato', 'Baños de Agua Santa', 'Cevallos', 'Mocha', 'Patate', 'Quero', 'San Pedro de Pelileo', 'Santiago de Píllaro', 'Tisaleo'],
            'Zamora Chinchipe': ['Zamora', 'Centinela del Cóndor', 'Chinchipe', 'El Pangui', 'Nangaritza', 'Palanda', 'Paquisha', 'Yacuambi', 'Yantzaza']
        }
        cantones = {}
        for prov_nombre, c_list in cantones_dict.items():
            prov = provincias.get(prov_nombre)
            if not prov:
                continue
            dpa_pref = prov_dpa_map.get(prov_nombre, "99")
            existing_dpas = set(Canton.objects.filter(province=prov).values_list('dpa_code', flat=True))
            for idx, nombre in enumerate(c_list, start=1):
                cant = Canton.objects.filter(province=prov, name=nombre).first()
                if not cant:
                    dpa_code = None
                    for num in range(1, 100):
                        cand = f"{dpa_pref}{num:02d}"
                        if cand not in existing_dpas:
                            dpa_code = cand
                            existing_dpas.add(cand)
                            break
                    cant = Canton.objects.create(
                        province=prov, dpa_code=dpa_code or f"{dpa_pref}99", name=nombre
                    )
                cantones[nombre] = cant

        # 2. Institución
        unemi, _ = Institution.objects.get_or_create(
            acronym="UNEMI",
            defaults={"name": "Universidad Estatal de Milagro", "status": Institution.Status.ACTIVE}
        )
        espol, _ = Institution.objects.get_or_create(
            acronym="ESPOL",
            defaults={"name": "Escuela Superior Politécnica del Litoral", "status": Institution.Status.ACTIVE}
        )

        # 3. Sociodemográficos
        sex_h, _ = Sex.objects.get_or_create(sex_id=1, defaults={"name": "Hombre", "status": Sex.Status.ACTIVE})
        sex_m, _ = Sex.objects.get_or_create(sex_id=2, defaults={"name": "Mujer", "status": Sex.Status.ACTIVE})

        etnias = ["Mestizo", "Blanco", "Afroecuatoriano", "Indígena", "Montuvio", "Otro"]
        for e in etnias:
            Ethnicity.objects.get_or_create(name=e, defaults={"status": Ethnicity.Status.ACTIVE})

        estamentos = ["PDI", "PAS", "AD", "SERVICIO", "ESTUDIANTES"]
        for st in estamentos:
            StaffCategory.objects.get_or_create(name=st, defaults={"status": StaffCategory.Status.ACTIVE})

        cat_prof = ["Docente Titular", "Docente Ocasional", "Servidor Público", "Auxiliar de Servicios", "Estudiante", "Otro"]
        for cp in cat_prof:
            ProfessionalCategory.objects.get_or_create(name=cp, defaults={"status": ProfessionalCategory.Status.ACTIVE})

        niveles_estudio = [
            "Primaria", "Secundaria", "Tercer Nivel (Grado)", "Cuarto Nivel (Postgrado)", "Doctorado (PhD)"
        ]
        for ne in niveles_estudio:
            EducationLevel.objects.get_or_create(name=ne, defaults={"status": EducationLevel.Status.ACTIVE})

        ingresos = ["Menos de $500", "$500 - $1000", "$1001 - $2000", "Más de $2000"]
        for ing in ingresos:
            IncomeRange.objects.get_or_create(name=ing, defaults={"status": IncomeRange.Status.ACTIVE})

        estados_civiles = ["Soltero/a", "Casado/a", "Unión de hecho", "Divorciado/a", "Viudo/a"]
        for ec in estados_civiles:
            MaritalStatus.objects.get_or_create(name=ec, defaults={"status": MaritalStatus.Status.ACTIVE})

        convivencia = ["Solo", "Con pareja", "Con familia", "Con amigos/compañeros"]
        for sc in convivencia:
            LivingSituation.objects.get_or_create(name=sc, defaults={"status": LivingSituation.Status.ACTIVE})

        vivienda = ["Propia", "Arrendada", "Prestada", "Familiar"]
        for tv in vivienda:
            HousingType.objects.get_or_create(name=tv, defaults={"status": HousingType.Status.ACTIVE})

        jornadas = ["Tiempo Completo (40h)", "Medio Tiempo (20h)", "Turnos / Rotativo", "Parcial"]
        for j in jornadas:
            WorkSchedule.objects.get_or_create(name=j, defaults={"status": WorkSchedule.Status.ACTIVE})

        ritmos_ecg = [
            "Ritmo Sinusal (RS)",
            "Fibrilación Auricular (ACxFA)",
            "Taquicardia Sinusal",
            "Bradicardia Sinusal",
            "Bloqueo AV",
            "Otro"
        ]
        for re in ritmos_ecg:
            EcgRhythm.objects.get_or_create(name=re, defaults={"status": EcgRhythm.Status.ACTIVE})

        # 4. Secciones de Cuestionario
        secciones_def = [
            ("MOD_3_FACTORES_MOD", "Módulo 3: Factores Modificables", 1),
            ("MOD_3_FACTORES_EMERG", "Módulo 3: Factores Emergentes", 2),
            ("MOD_3_ANTECEDENTES_FAM", "Módulo 3: Antecedentes Familiares", 3),
            ("MOD_4_HISTORIA_CARDIO", "Módulo 4: Historia Cardiovascular y Rose", 4),
            ("MOD_4_HISTORIA_NO_CARDIO", "Módulo 4: Historia No Cardiovascular", 5),
            ("MOD_4_COVID", "Módulo 4: COVID-19 y Secuelas", 6),
            ("MOD_6_PREDIMED", "Módulo 6: Cuestionario PREDIMED", 7),
            ("MOD_6_ACTIVIDAD_FISICA", "Módulo 6: Actividad Física", 8),
        ]
        secciones = {}
        for code, name, order in secciones_def:
            sec, _ = QuestionnaireSection.objects.get_or_create(
                code=code, defaults={"name": name, "display_order": order, "status": QuestionnaireSection.Status.ACTIVE}
            )
            secciones[code] = sec

        # 5. Preguntas y Opciones
        preguntas_def = [
            # Factores modificables
            ("MOD_3_FACTORES_MOD", "hta", "¿Padece Hipertensión Arterial (HTA)?", "OPCION", 1, [("No", False), ("Sí", False)]),
            ("MOD_3_FACTORES_MOD", "hta_tto", "Tratamiento HTA", "TEXTO", 2, []),
            ("MOD_3_FACTORES_MOD", "dm", "¿Padece Diabetes Mellitus?", "OPCION", 3, [("No", False), ("Sí", False)]),
            ("MOD_3_FACTORES_MOD", "dm_tto", "Tratamiento Diabetes", "TEXTO", 4, []),
            ("MOD_3_FACTORES_MOD", "dlp", "¿Padece Dislipemia / Colesterol elevado?", "OPCION", 5, [("No", False), ("Sí", False)]),
            ("MOD_3_FACTORES_MOD", "dlp_tto", "Tratamiento Dislipemia", "TEXTO", 6, []),
            ("MOD_3_FACTORES_MOD", "tabaco", "¿Fuma o ha fumado tabaco?", "OPCION", 7, [("No fumador", False), ("Exfumador", False), ("Fumador activo", False)]),
            ("MOD_3_FACTORES_MOD", "alcohol", "Consumo de bebidas alcohólicas", "OPCION", 8, [("Nunca", False), ("Ocasional", False), ("Semanal", False), ("Diario", False)]),
            ("MOD_3_FACTORES_MOD", "drogas", "Consumo de sustancias o drogas", "OPCION", 9, [("No", False), ("Sí", False)]),
            ("MOD_3_FACTORES_MOD", "sobrepeso", "Sobrepeso u obesidad diagnosticada", "OPCION", 10, [("No", False), ("Sí", False)]),
            ("MOD_3_FACTORES_MOD", "irc", "Insuficiencia Renal Crónica", "OPCION", 11, [("No", False), ("Sí", False)]),
            ("MOD_3_FACTORES_MOD", "higado_graso", "Hígado graso no alcohólico", "OPCION", 12, [("No", False), ("Sí", False)]),
            ("MOD_3_FACTORES_MOD", "apnea", "Apnea del sueño diagnosticada", "OPCION", 13, [("No", False), ("Sí", False)]),

            # Factores emergentes
            ("MOD_3_FACTORES_EMERG", "sueno_calidad", "Calidad subjetiva del sueño", "OPCION", 1, [("Buena", False), ("Regular", False), ("Mala", False)]),
            ("MOD_3_FACTORES_EMERG", "sueno_horas", "Horas habituales de sueño diario", "NUMERICO", 2, []),
            ("MOD_3_FACTORES_EMERG", "toxicos_laboral", "Exposición laboral a tóxicos o químicos", "OPCION", 3, [("No", False), ("Sí", False)]),
            ("MOD_3_FACTORES_EMERG", "estres_laboral", "Nivel de estrés laboral", "OPCION", 4, [("Bajo", False), ("Medio", False), ("Alto", False)]),
            ("MOD_3_FACTORES_EMERG", "estres_familiar", "Nivel de estrés familiar", "OPCION", 5, [("Bajo", False), ("Medio", False), ("Alto", False)]),
            ("MOD_3_FACTORES_EMERG", "personalidad_tipo_a", "Rasgos de personalidad Tipo A", "OPCION", 6, [("No", False), ("Sí", False)]),

            # Antecedentes familiares
            ("MOD_3_ANTECEDENTES_FAM", "af_cardiopatia_prematura", "Cardiopatía isquémica prematura en familiar (<55v / <65m)", "OPCION", 1, [("No", False), ("Sí", False)]),
            ("MOD_3_ANTECEDENTES_FAM", "af_muerte_subita", "Muerte súbita en familiares directos", "OPCION", 2, [("No", False), ("Sí", False)]),
            ("MOD_3_ANTECEDENTES_FAM", "af_padre_hta", "Padre con Hipertensión Arterial", "OPCION", 3, [("No", False), ("Sí", False)]),
            ("MOD_3_ANTECEDENTES_FAM", "af_madre_hta", "Madre con Hipertensión Arterial", "OPCION", 4, [("No", False), ("Sí", False)]),
            ("MOD_3_ANTECEDENTES_FAM", "af_padre_dm", "Padre con Diabetes Mellitus", "OPCION", 5, [("No", False), ("Sí", False)]),
            ("MOD_3_ANTECEDENTES_FAM", "af_madre_dm", "Madre con Diabetes Mellitus", "OPCION", 6, [("No", False), ("Sí", False)]),
            ("MOD_3_ANTECEDENTES_FAM", "af_padre_dlp", "Padre con Dislipemia", "OPCION", 7, [("No", False), ("Sí", False)]),
            ("MOD_3_ANTECEDENTES_FAM", "af_madre_dlp", "Madre con Dislipemia", "OPCION", 8, [("No", False), ("Sí", False)]),

            # Historia cardiovascular y Rose
            ("MOD_4_HISTORIA_CARDIO", "ant_iam", "Infarto Agudo de Miocardio previo", "OPCION", 1, [("No", False), ("Sí", False)]),
            ("MOD_4_HISTORIA_CARDIO", "ant_angina", "Angina de pecho diagnosticada", "OPCION", 2, [("No", False), ("Sí", False)]),
            ("MOD_4_HISTORIA_CARDIO", "ant_acv", "Accidente Cerebrovascular (ACV / Ictus)", "OPCION", 3, [("No", False), ("Sí", False)]),
            ("MOD_4_HISTORIA_CARDIO", "ant_eap", "Enfermedad Arterial Periférica", "OPCION", 4, [("No", False), ("Sí", False)]),
            ("MOD_4_HISTORIA_CARDIO", "rose_dolor_pecho", "Rose 1: ¿Ha sentido alguna vez dolor o malestar en el pecho?", "OPCION", 5, [("No", False), ("Sí", False)]),
            ("MOD_4_HISTORIA_CARDIO", "rose_dolor_caminar", "Rose 2: ¿Aparece el dolor al caminar deprisa o subir pendientes?", "OPCION", 6, [("No", False), ("Sí", False)]),
            ("MOD_4_HISTORIA_CARDIO", "rose_detenerse", "Rose 3: ¿Se detiene o disminuye la marcha cuando aparece?", "OPCION", 7, [("No", False), ("Sí", False)]),
            ("MOD_4_HISTORIA_CARDIO", "rose_alivio", "Rose 4: ¿Se calma el dolor en menos de 10 minutos al detenerse?", "OPCION", 8, [("No", False), ("Sí", False)]),
            ("MOD_4_HISTORIA_CARDIO", "rose_claudicacion", "Rose 5: ¿Dolor en gemelos al caminar que obliga a detenerse?", "OPCION", 9, [("No", False), ("Sí", False)]),

            # Historia no cardiovascular
            ("MOD_4_HISTORIA_NO_CARDIO", "ant_cancer", "Antecedente de Cáncer / Neoplasia", "OPCION", 1, [("No", False), ("Sí", False)]),
            ("MOD_4_HISTORIA_NO_CARDIO", "ant_epoc", "Enfermedad Pulmonar Obstructiva Crónica (EPOC)", "OPCION", 2, [("No", False), ("Sí", False)]),
            ("MOD_4_HISTORIA_NO_CARDIO", "ant_asma", "Asma bronquial", "OPCION", 3, [("No", False), ("Sí", False)]),
            ("MOD_4_HISTORIA_NO_CARDIO", "ant_reuma", "Patología reumática / artritis", "OPCION", 4, [("No", False), ("Sí", False)]),
            ("MOD_4_HISTORIA_NO_CARDIO", "ant_depresion", "Depresión diagnosticada", "OPCION", 5, [("No", False), ("Sí", False)]),
            ("MOD_4_HISTORIA_NO_CARDIO", "ant_ansiedad", "Trastorno de ansiedad", "OPCION", 6, [("No", False), ("Sí", False)]),
            ("MOD_4_HISTORIA_NO_CARDIO", "ant_alergias", "Alergias a medicamentos o fármacos", "OPCION", 7, [("No", False), ("Sí", False)]),

            # COVID-19
            ("MOD_4_COVID", "covid_infeccion", "¿Ha tenido infección confirmada por COVID-19?", "OPCION", 1, [("No", False), ("Sí", False)]),
            ("MOD_4_COVID", "covid_hosp", "¿Requirió hospitalización por COVID-19?", "OPCION", 2, [("No", False), ("Sí", False)]),
            ("MOD_4_COVID", "covid_secuelas_cardio", "Secuelas cardiovasculares post-COVID", "OPCION", 3, [("No", False), ("Sí", False)]),
            ("MOD_4_COVID", "covid_secuelas_resp", "Secuelas respiratorias o disnea persistente", "OPCION", 4, [("No", False), ("Sí", False)]),
            ("MOD_4_COVID", "covid_niebla", "Niebla mental o dificultad de concentración post-COVID", "OPCION", 5, [("No", False), ("Sí", False)]),
            ("MOD_4_COVID", "covid_fatiga", "Fatiga crónica o cansancio post-COVID (Long-COVID)", "OPCION", 6, [("No", False), ("Sí", False)]),

            # PREDIMED (14 Preguntas puntuables: 'Si' suma 1 punto para adherencia)
            ("MOD_6_PREDIMED", "pred_q1", "1. ¿Usa el aceite de oliva como principal grasa culinaria?", "OPCION", 1, [("No", False), ("Si", True)]),
            ("MOD_6_PREDIMED", "pred_q2", "2. ¿Consume 4 o más cucharadas soperas de aceite de oliva al día?", "OPCION", 2, [("No", False), ("Si", True)]),
            ("MOD_6_PREDIMED", "pred_q3", "3. ¿Consume 2 o más raciones de verdura al día?", "OPCION", 3, [("No", False), ("Si", True)]),
            ("MOD_6_PREDIMED", "pred_q4", "4. ¿Consume 3 o más piezas de fruta al día?", "OPCION", 4, [("No", False), ("Si", True)]),
            ("MOD_6_PREDIMED", "pred_q5", "5. ¿Consume menos de 1 ración de carnes rojas o embutidos al día?", "OPCION", 5, [("No", False), ("Si", True)]),
            ("MOD_6_PREDIMED", "pred_q6", "6. ¿Consume menos de 1 porción de mantequilla, margarina o nata al día?", "OPCION", 6, [("No", False), ("Si", True)]),
            ("MOD_6_PREDIMED", "pred_q7", "7. ¿Consume menos de 1 bebida carbonatada o azucarada al día?", "OPCION", 7, [("No", False), ("Si", True)]),
            ("MOD_6_PREDIMED", "pred_q8", "8. ¿Bebe 7 o más copas de vino a la semana?", "OPCION", 8, [("No", False), ("Si", True)]),
            ("MOD_6_PREDIMED", "pred_q9", "9. ¿Consume 3 o más raciones de legumbres a la semana?", "OPCION", 9, [("No", False), ("Si", True)]),
            ("MOD_6_PREDIMED", "pred_q10", "10. ¿Consume 3 o más raciones de pescado o marisco a la semana?", "OPCION", 10, [("No", False), ("Si", True)]),
            ("MOD_6_PREDIMED", "pred_q11", "11. ¿Consume menos de 3 veces a la semana repostería industrial?", "OPCION", 11, [("No", False), ("Si", True)]),
            ("MOD_6_PREDIMED", "pred_q12", "12. ¿Consume 3 o más raciones de frutos secos a la semana?", "OPCION", 12, [("No", False), ("Si", True)]),
            ("MOD_6_PREDIMED", "pred_q16", "13. ¿Prefiere consumir carne de ave antes que carnes rojas?", "OPCION", 13, [("No", False), ("Si", True)]),
            ("MOD_6_PREDIMED", "pred_q17", "14. ¿Consume sofrito de tomate, ajo y cebolla 2 o más veces por semana?", "OPCION", 14, [("No", False), ("Si", True)]),

            # Actividad Física
            ("MOD_6_ACTIVIDAD_FISICA", "af_camina", "1. ¿Camina regularmente como ejercicio?", "OPCION", 1, [("No", False), ("Sí", False)]),
            ("MOD_6_ACTIVIDAD_FISICA", "af_camina_minutos_dia", "Caminar: Minutos por día", "NUMERICO", 2, []),
            ("MOD_6_ACTIVIDAD_FISICA", "af_camina_dias_sem", "Caminar: Días por semana", "NUMERICO", 3, []),
            ("MOD_6_ACTIVIDAD_FISICA", "af_aerobicos", "2. ¿Realiza ejercicios aeróbicos (bici, natación, trote)?", "OPCION", 4, [("No", False), ("Sí", False)]),
            ("MOD_6_ACTIVIDAD_FISICA", "af_aero_veces_sem", "Aeróbicos: Veces por semana", "NUMERICO", 5, []),
            ("MOD_6_ACTIVIDAD_FISICA", "af_aero_minutos_dia", "Aeróbicos: Minutos por día", "NUMERICO", 6, []),
            ("MOD_6_ACTIVIDAD_FISICA", "af_anaerobicos", "3. ¿Realiza ejercicios de fuerza / pesas?", "OPCION", 7, [("No", False), ("Sí", False)]),
            ("MOD_6_ACTIVIDAD_FISICA", "af_anaero_veces_sem", "Fuerza: Veces por semana", "NUMERICO", 8, []),
            ("MOD_6_ACTIVIDAD_FISICA", "af_anaero_minutos_dia", "Fuerza: Minutos por día", "NUMERICO", 9, []),
            ("MOD_6_ACTIVIDAD_FISICA", "af_deporte", "4. ¿Practica algún deporte organizado?", "OPCION", 10, [("No", False), ("Sí", False)]),
            ("MOD_6_ACTIVIDAD_FISICA", "af_dep_tipo", "Deporte: Tipo", "TEXTO", 11, []),
        ]

        for sec_code, q_code, q_text, resp_type, order, opts in preguntas_def:
            sec = secciones[sec_code]
            q, _ = Question.objects.get_or_create(
                code=q_code,
                defaults={
                    "section": sec,
                    "text": q_text,
                    "response_type": resp_type,
                    "display_order": order,
                    "status": Question.Status.ACTIVE,
                }
            )
            for opt_order, (lbl, scores) in enumerate(opts, start=1):
                AnswerOption.objects.get_or_create(
                    question=q,
                    display_order=opt_order,
                    defaults={
                        "label": lbl,
                        "scores_predimed": scores,
                        "status": AnswerOption.Status.ACTIVE,
                    }
                )

        # 6. Pacientes iniciales basados en la cohorte clínica institucional
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.first()

        milagro = cantones.get("Milagro")
        guayaquil = cantones.get("Guayaquil")
        mestizo = Ethnicity.objects.filter(name="Mestizo").first()
        pdi = StaffCategory.objects.filter(name="PDI").first()
        docente = ProfessionalCategory.objects.first()
        sinusal = EcgRhythm.objects.filter(name__icontains="Sinusal").first() or EcgRhythm.objects.first()

        pacientes_base = [
            {
                "cedula": "0923485712",
                "first_names": "Alejandro",
                "last_name1": "Reyes",
                "last_name2": "Morán",
                "birth_date": "1985-02-09",
                "sex": sex_h,
                "email": "areyes@unemi.edu.ec",
                "phone": "0987654321",
                "study_code": "1",
                "visit_date": "2026-02-10",
                "facultad": "Salud y Servicios Sociales",
                "peso": 74.0,
                "talla": 172.0,
                "perimetro": 88.0,
                "tas": 120,
                "tad": 80,
                "sat_o2": 98,
                "fc": 72,
                "canton": milagro
            },
            {
                "cedula": "0918745236",
                "first_names": "Carlos",
                "last_name1": "Mendoza",
                "last_name2": "Paredes",
                "birth_date": "1984-06-15",
                "sex": sex_h,
                "email": "cmendoza@unemi.edu.ec",
                "phone": "0991234567",
                "study_code": "2",
                "visit_date": "2025-05-18",
                "facultad": "Ciencias e Ingeniería",
                "peso": 82.0,
                "talla": 175.0,
                "perimetro": 94.0,
                "tas": 130,
                "tad": 85,
                "sat_o2": 97,
                "fc": 75,
                "canton": guayaquil
            },
            {
                "cedula": "0934125890",
                "first_names": "Ana Lucía",
                "last_name1": "Torres",
                "last_name2": "Moreira",
                "birth_date": "1990-11-23",
                "sex": sex_m,
                "email": "atorres@unemi.edu.ec",
                "phone": "0984567890",
                "study_code": "3",
                "visit_date": "2026-01-14",
                "facultad": "Ciencias Sociales y Humanas",
                "peso": 61.0,
                "talla": 160.0,
                "perimetro": 75.0,
                "tas": 115,
                "tad": 75,
                "sat_o2": 99,
                "fc": 68,
                "canton": milagro
            },
            {
                "cedula": "0921458796",
                "first_names": "Mariana",
                "last_name1": "Villacrés",
                "last_name2": "Sánchez",
                "birth_date": "1978-04-30",
                "sex": sex_m,
                "email": "mvillacres@unemi.edu.ec",
                "phone": "0998741235",
                "study_code": "4",
                "visit_date": "2024-09-08",
                "facultad": "Educación",
                "peso": 68.0,
                "talla": 158.0,
                "perimetro": 82.0,
                "tas": 125,
                "tad": 80,
                "sat_o2": 98,
                "fc": 70,
                "canton": milagro
            },
            {
                "cedula": "0915632478",
                "first_names": "Roberto",
                "last_name1": "Zambrano",
                "last_name2": "Castro",
                "birth_date": "1972-08-19",
                "sex": sex_h,
                "email": "rzambrano@unemi.edu.ec",
                "phone": "0978965412",
                "study_code": "5",
                "visit_date": "2026-03-02",
                "facultad": "Ciencias de la Salud",
                "peso": 88.0,
                "talla": 170.0,
                "perimetro": 102.0,
                "tas": 140,
                "tad": 90,
                "sat_o2": 96,
                "fc": 80,
                "canton": milagro
            }
        ]

        pacientes_creados = 0
        for pdata in pacientes_base:
            if Patient.objects.filter(id_card=pdata["cedula"]).exists():
                continue

            paciente = Patient.objects.create(
                institution=unemi,
                id_card=pdata["cedula"],
                first_names=pdata["first_names"],
                last_name1=pdata["last_name1"],
                last_name2=pdata["last_name2"],
                birth_date=datetime.date.fromisoformat(pdata["birth_date"]),
                sex=pdata["sex"],
                ethnicity=mestizo,
                birth_canton=pdata["canton"] or milagro,
                email=pdata["email"],
                phone=pdata["phone"],
                status=Patient.Status.ACTIVE,
                created_by=admin_user,
            )

            visita = Visit.objects.create(
                patient=paciente,
                evaluator=admin_user,
                visit_number=1,
                study_code=pdata["study_code"],
                visit_date=datetime.date.fromisoformat(pdata["visit_date"]),
                staff_category=pdi,
                professional_category=docente,
                residence_canton=pdata["canton"] or milagro,
                faculty=pdata["facultad"],
                status=Visit.Status.COMPLETED
            )

            Anthropometry.objects.create(
                visit=visita,
                weight_kg=pdata["peso"],
                height_cm=pdata["talla"],
                waist_circumference_cm=pdata["perimetro"]
            )

            VitalSigns.objects.create(
                visit=visita,
                systolic_bp=pdata["tas"],
                diastolic_bp=pdata["tad"],
                oxygen_saturation=pdata["sat_o2"],
                heart_rate=pdata["fc"],
                pulmonary_auscultation_normal=True,
                abdominal_auscultation_normal=True
            )

            pacientes_creados += 1

        self.stdout.write(self.style.SUCCESS(
            f"[OK] Carga completada exitosamente: {Question.objects.count()} preguntas, "
            f"{AnswerOption.objects.count()} opciones, {pacientes_creados} pacientes clinicos creados en PostgreSQL."
        ))
