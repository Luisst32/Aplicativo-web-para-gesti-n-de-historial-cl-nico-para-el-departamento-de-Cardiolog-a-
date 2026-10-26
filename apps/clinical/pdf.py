import io
import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
)

from clinical.models import Visit


def generate_clinical_sheet_pdf(visit: Visit) -> bytes:
    """
    Generates a professional clinical evaluation PDF report for CARDIOUNEMI
    respecting institutional headers and all 6 clinical modules (HU-17).
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    header_title_style = ParagraphStyle(
        'HeaderTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#1d4ed8')
    )
    header_sub_style = ParagraphStyle(
        'HeaderSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#475569')
    )
    section_title_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#0f172a'),
        spaceBefore=8,
        spaceAfter=4
    )
    cell_label_style = ParagraphStyle(
        'CellLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#334155')
    )
    cell_val_style = ParagraphStyle(
        'CellVal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#0f172a')
    )

    elements = []

    # Institutional Header
    header_data = [
        [
            Paragraph("<b>CARDIOUNEMI — UNIVERSIDAD ESTATAL DE MILAGRO</b>", header_title_style),
            Paragraph(f"<b>Fecha:</b> {visit.visit_date.strftime('%d/%m/%Y')}<br/><b>Código:</b> {visit.study_code}", header_sub_style)
        ],
        [
            Paragraph("Departamento de Cardiología · Sistema Clínico Epidemiológico Cardiovascular", header_sub_style),
            Paragraph(f"<b>Estado:</b> {visit.get_status_display()}", header_sub_style)
        ]
    ]
    t_header = Table(header_data, colWidths=[380, 160])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(t_header)
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1d4ed8'), spaceAfter=10, spaceBefore=4))

    # Módulo 1: Identificación y Datos Sociodemográficos
    patient = visit.patient
    elements.append(Paragraph("MÓDULO 1: IDENTIFICACIÓN Y DATOS SOCIODEMOGRÁFICOS", section_title_style))

    mod1_data = [
        [
            Paragraph("Apellidos y Nombres:", cell_label_style),
            Paragraph(patient.full_name, cell_val_style),
            Paragraph("Cédula de Identidad:", cell_label_style),
            Paragraph(patient.id_card, cell_val_style),
        ],
        [
            Paragraph("Fecha de Nacimiento:", cell_label_style),
            Paragraph(patient.birth_date.strftime('%d/%m/%Y'), cell_val_style),
            Paragraph("Sexo / Etnia:", cell_label_style),
            Paragraph(f"{patient.sex.name} / {patient.ethnicity.name if patient.ethnicity else '--'}", cell_val_style),
        ],
        [
            Paragraph("Estamento UNEMI:", cell_label_style),
            Paragraph(visit.staff_category.name if visit.staff_category else '--', cell_val_style),
            Paragraph("Facultad / Dpto.:", cell_label_style),
            Paragraph(visit.faculty or '--', cell_val_style),
        ],
        [
            Paragraph("Ciudad / Cantón:", cell_label_style),
            Paragraph(visit.residence_canton.name if visit.residence_canton else '--', cell_val_style),
            Paragraph("Teléfono / Correo:", cell_label_style),
            Paragraph(f"{patient.phone or '--'} / {patient.email or '--'}", cell_val_style),
        ]
    ]
    t_mod1 = Table(mod1_data, colWidths=[110, 160, 110, 160])
    t_mod1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_mod1)

    # Módulo 2: Exploración Física y Signos Vitales
    elements.append(Paragraph("MÓDULO 2: EXPLORACIÓN FÍSICA Y SIGNOS VITALES", section_title_style))
    ant = getattr(visit, 'anthropometry', None)
    vs = getattr(visit, 'vital_signs', None)

    mod2_data = [
        [
            Paragraph("Peso:", cell_label_style),
            Paragraph(f"{ant.weight_kg} kg" if ant else '--', cell_val_style),
            Paragraph("Talla:", cell_label_style),
            Paragraph(f"{ant.height_cm} cm" if ant else '--', cell_val_style),
            Paragraph("Perímetro Abdominal:", cell_label_style),
            Paragraph(f"{ant.waist_circumference_cm} cm" if (ant and ant.waist_circumference_cm) else '--', cell_val_style),
        ],
        [
            Paragraph("IMC (kg/m²):", cell_label_style),
            Paragraph(f"<b>{ant.bmi}</b>" if ant else '--', cell_val_style),
            Paragraph("ASC (m²):", cell_label_style),
            Paragraph(f"{ant.body_surface_area}" if ant else '--', cell_val_style),
            Paragraph("Presión Arterial:", cell_label_style),
            Paragraph(f"<b>{vs.systolic_bp} / {vs.diastolic_bp} mmHg</b>" if vs else '--', cell_val_style),
        ],
        [
            Paragraph("Frecuencia Cardíaca:", cell_label_style),
            Paragraph(f"{vs.heart_rate} lpm" if (vs and vs.heart_rate) else '--', cell_val_style),
            Paragraph("Saturación O2:", cell_label_style),
            Paragraph(f"{vs.oxygen_saturation} %" if (vs and vs.oxygen_saturation) else '--', cell_val_style),
            Paragraph("Auscultación Pulmonar:", cell_label_style),
            Paragraph("Normal" if (vs and vs.pulmonary_auscultation_normal) else "Alterada", cell_val_style),
        ]
    ]
    t_mod2 = Table(mod2_data, colWidths=[90, 90, 90, 90, 90, 90])
    t_mod2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_mod2)

    # Módulos 3 y 4: Factores de Riesgo e Historia Clínica
    elements.append(Paragraph("MÓDULOS 3 Y 4: FACTORES DE RIESGO E HISTORIA CLÍNICA", section_title_style))

    # Cargar respuestas dinámicas
    respuestas = {ans.question.code: ans for ans in visit.answers.select_related('question', 'selected_option').all()}

    def get_ans(code, default='No'):
        ans = respuestas.get(code)
        if not ans:
            return default
        if ans.selected_option:
            return ans.selected_option.label
        if ans.text_value:
            return ans.text_value
        if ans.numeric_value is not None:
            return str(ans.numeric_value)
        return default

    mod34_data = [
        [
            Paragraph("Hipertensión (HTA):", cell_label_style),
            Paragraph(get_ans('hta'), cell_val_style),
            Paragraph("Diabetes Mellitus:", cell_label_style),
            Paragraph(get_ans('dm'), cell_val_style),
            Paragraph("Dislipemia / Colesterol:", cell_label_style),
            Paragraph(get_ans('dlp'), cell_val_style),
        ],
        [
            Paragraph("Tabaquismo:", cell_label_style),
            Paragraph(get_ans('tabaco', 'No fumador'), cell_val_style),
            Paragraph("Consumo Alcohol:", cell_label_style),
            Paragraph(get_ans('alcohol', 'Nunca'), cell_val_style),
            Paragraph("Calidad del Sueño:", cell_label_style),
            Paragraph(get_ans('sueno_calidad', 'Buena'), cell_val_style),
        ],
        [
            Paragraph("Cardiopatía Familiar:", cell_label_style),
            Paragraph(get_ans('af_cardiopatia_prematura'), cell_val_style),
            Paragraph("Muerte Súbita Fam.:", cell_label_style),
            Paragraph(get_ans('af_muerte_subita'), cell_val_style),
            Paragraph("Rose Dolor Pecho:", cell_label_style),
            Paragraph(get_ans('rose_dolor_pecho'), cell_val_style),
        ],
        [
            Paragraph("Infección COVID-19:", cell_label_style),
            Paragraph(get_ans('covid_infeccion'), cell_val_style),
            Paragraph("Secuelas Post-COVID:", cell_label_style),
            Paragraph(get_ans('covid_secuelas_cardio'), cell_val_style),
            Paragraph("Fatiga Post-COVID:", cell_label_style),
            Paragraph(get_ans('covid_fatiga'), cell_val_style),
        ]
    ]
    t_mod34 = Table(mod34_data, colWidths=[90, 90, 90, 90, 90, 90])
    t_mod34.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_mod34)

    # Módulo 5: Exámenes Complementarios (ECG, Ecocardiograma y Laboratorio)
    elements.append(Paragraph("MÓDULO 5: EXÁMENES COMPLEMENTARIOS (ECG, ECO Y LABORATORIO)", section_title_style))
    ecg = getattr(visit, 'electrocardiogram', None)
    echo = getattr(visit, 'echocardiogram', None)
    lab = getattr(visit, 'laboratory', None)

    mod5_data = [
        [
            Paragraph("Ritmo ECG:", cell_label_style),
            Paragraph(ecg.rhythm.name if (ecg and ecg.rhythm) else "Ritmo Sinusal", cell_val_style),
            Paragraph("FC ECG:", cell_label_style),
            Paragraph(f"{ecg.heart_rate} lpm" if (ecg and ecg.heart_rate) else '--', cell_val_style),
            Paragraph("HVI en ECG:", cell_label_style),
            Paragraph("Sí" if (ecg and ecg.left_ventricular_hypertrophy) else "No", cell_val_style),
        ],
        [
            Paragraph("FEVI (Eco %):", cell_label_style),
            Paragraph(f"{echo.lvef_percentage}%" if (echo and echo.lvef_percentage) else '--', cell_val_style),
            Paragraph("Glucosa basal:", cell_label_style),
            Paragraph(f"{lab.glucose_mg_dl} mg/dL" if (lab and lab.glucose_mg_dl) else '--', cell_val_style),
            Paragraph("Creatinina:", cell_label_style),
            Paragraph(f"{lab.creatinine_mg_dl} mg/dL" if (lab and lab.creatinine_mg_dl) else '--', cell_val_style),
        ],
        [
            Paragraph("Colesterol Total:", cell_label_style),
            Paragraph(f"{lab.total_cholesterol_mg_dl} mg/dL" if (lab and lab.total_cholesterol_mg_dl) else '--', cell_val_style),
            Paragraph("Colesterol HDL:", cell_label_style),
            Paragraph(f"{lab.hdl_mg_dl} mg/dL" if (lab and lab.hdl_mg_dl) else '--', cell_val_style),
            Paragraph("Triglicéridos:", cell_label_style),
            Paragraph(f"{lab.triglycerides_mg_dl} mg/dL" if (lab and lab.triglycerides_mg_dl) else '--', cell_val_style),
        ]
    ]
    t_mod5 = Table(mod5_data, colWidths=[90, 90, 90, 90, 90, 90])
    t_mod5.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_mod5)

    # Módulo 6: PREDIMED y Actividad Física
    elements.append(Paragraph("MÓDULO 6: ESTILO DE VIDA, DIETA PREDIMED Y ACTIVIDAD FÍSICA", section_title_style))

    # Calcular score predimed de las respuestas
    pred_score = sum(
        1 for ans in visit.answers.all()
        if ans.selected_option and ans.selected_option.scores_predimed
    )
    adherencia = "Buena adherencia" if pred_score >= 9 else "Baja adherencia"

    mod6_data = [
        [
            Paragraph("Puntuación PREDIMED:", cell_label_style),
            Paragraph(f"<b>{pred_score} / 14 puntos</b>", cell_val_style),
            Paragraph("Nivel de Adherencia:", cell_label_style),
            Paragraph(f"<b>{adherencia}</b>", cell_val_style),
            Paragraph("Camina Regularmente:", cell_label_style),
            Paragraph(get_ans('af_camina', 'Sí'), cell_val_style),
        ]
    ]
    t_mod6 = Table(mod6_data, colWidths=[90, 90, 90, 90, 90, 90])
    t_mod6.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_mod6)

    # Firmas
    elements.append(Spacer(1, 20))
    evaluador_nombre = visit.evaluator.full_name or visit.evaluator.username if visit.evaluator else "Médico Especialista"
    sign_data = [
        [
            Paragraph(f"____________________________________________<br/><b>Evaluador Responsable:</b> {evaluador_nombre}<br/>Departamento de Cardiología UNEMI", ParagraphStyle('Sign1', parent=styles['Normal'], alignment=1, fontSize=8)),
            Paragraph(f"____________________________________________<br/><b>Paciente Evaluado:</b> {patient.full_name}<br/>C.I. {patient.id_card}", ParagraphStyle('Sign2', parent=styles['Normal'], alignment=1, fontSize=8))
        ]
    ]
    t_sign = Table(sign_data, colWidths=[270, 270])
    elements.append(t_sign)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
