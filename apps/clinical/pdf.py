import io
import os
import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, Image, HRFlowable
)
from reportlab.pdfgen import canvas
from clinical.models import Visit


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and display total page numbers,
    running headers, and running footers on all pages.
    """
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#475569"))
        
        # Header on later pages
        if self._pageNumber > 1:
            self.drawString(28, 818, "CARDIOUNEMI · Estudio Cardiovascular en Profesorado y PAS UNEMI (Cuestionario Oficial)")
            if hasattr(self, '_study_code') and self._study_code:
                self.drawRightString(567, 818, f"Código: {self._study_code}")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(28, 812, 567, 812)

        # Footer on all pages
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(28, 28, 567, 28)
        
        info_left = "Universidad Estatal de Milagro (UNEMI) · Departamento de Cardiología"
        if hasattr(self, '_patient_info') and self._patient_info:
            info_left += f" · {self._patient_info}"
        self.drawString(28, 18, info_left)
        
        page_str = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(567, 18, page_str)
        self.restoreState()


def clean_int_str(val_str):
    if val_str is None:
        return ""
    s = str(val_str).strip()
    if not s:
        return ""
    if '.' in s:
        parts = s.split('.')
        if len(parts) == 2 and parts[1].replace('0', '') == '':
            return parts[0]
    try:
        f = float(s)
        if f.is_integer():
            return str(int(f))
    except (ValueError, TypeError):
        pass
    return s

def generate_clinical_sheet_pdf(visit: Visit = None, is_blank: bool = False) -> bytes:
    """
    Generates the official UNEMI cardiovascular study clinical questionnaire PDF report,
    strictly following the visual design, headings, checkboxes, and structure of
    'CUESTIONARIO UNEMI_definitivo 2026.pdf' (escaneo).
    
    Includes only the clinical questions and variables implemented in the application.
    Supports exporting filled patient evaluation records or blank interview templates.
    """
    from clinical.views import _build_form_datos

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=28,
        rightMargin=28,
        topMargin=28,
        bottomMargin=36
    )

    # Prepare data dictionary from visit / patient
    if visit and not is_blank:
        datos = _build_form_datos(visit.patient, visit)
    else:
        datos = {}

    def val(key, default=""):
        if is_blank:
            return ""
        raw = datos.get(key, "")
        if raw is None:
            return default
        v = clean_int_str(raw)
        return v if v else default

    def is_yes(key):
        if is_blank:
            return False
        v = str(datos.get(key, "") or "").lower().strip()
        return any(y in v for y in ['si', 'sí', 'true', '1', 'positivo', 'presente'])

    def is_no(key):
        if is_blank:
            return False
        v = str(datos.get(key, "") or "").lower().strip()
        return any(n in v for n in ['no', 'false', '0', 'negativo', 'ausente', 'ningun'])

    def chk(checked):
        if checked:
            return '<b><font color="#0284c7" size="8.5">[X]</font></b>'
        return '<font color="#94a3b8" size="8.5">[&nbsp;&nbsp;]</font>'

    def field_txt(text, underline_len=24):
        if text:
            return f'<u><b><font color="#0f172a">{text}</font></b></u>'
        return f'<u>{"&nbsp;" * underline_len}</u>'

    # Typography & Styles
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11.5,
        leading=14,
        textColor=colors.HexColor('#1b73bc')
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#475569')
    )
    banner_style = ParagraphStyle(
        'BannerTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.8, leading=11.5,
        textColor=colors.white
    )
    q_style = ParagraphStyle(
        'QStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.8, leading=10.2,
        textColor=colors.HexColor('#1e293b')
    )
    q_bold = ParagraphStyle(
        'QBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.8, leading=10.2,
        textColor=colors.HexColor('#0f172a')
    )

    def section_banner(title_text):
        p = Paragraph(f"<b>{title_text.upper()}</b>", banner_style)
        t = Table([[p]], colWidths=[539])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1b73bc')),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        return t

    elements = []

    def add_section(banner_title, table):
        elements.append(KeepTogether([
            section_banner(banner_title),
            Spacer(1, 3.5),
            table
        ]))
        elements.append(Spacer(1, 6.0))

    # 1. INSTITUTIONAL HEADER & LOGO
    logo_path = 'apps/clinical/static/clinical/images/unemi_logo.png'
    if not os.path.exists(logo_path):
        logo_path = 'static/assets/images/unemi_logo.png'

    logo_img = ""
    if os.path.exists(logo_path):
        logo_img = Image(logo_path, width=85, height=38)

    estamento_val = val('f_estamento', '').upper()
    chk_pdi = chk('PDI' in estamento_val or 'DOCENTE' in estamento_val or 'PROFESOR' in estamento_val)
    chk_ad = chk('ADMIN' in estamento_val or 'SERVIDOR' in estamento_val or 'PAS' in estamento_val or estamento_val == 'AD')
    chk_serv = chk('SERVICIO' in estamento_val or 'AUXILIAR' in estamento_val)
    chk_est = chk('ESTUDIANTE' in estamento_val or 'ALUMNO' in estamento_val)

    codigo_str = val('f_codigo', '0001')
    fecha_vis_str = val('f_fecha_visita', '2026-01-01')
    facultad_str = val('f_facultad', 'UNEMI')
    universidad_str = val('f_universidad', 'UNEMI')

    header_cell = [
        Paragraph("<b>ESTUDIO CARDIOVASCULAR EN PROFESORADO y PAS UNEMI</b>", title_style),
        Paragraph("Departamento de Cardiología · Sistema Clínico Epidemiológico Cardiovascular", subtitle_style),
        Spacer(1, 3),
        Paragraph(
            f"<b>Estamento:</b> PDI {chk_pdi} &nbsp;&nbsp; AD {chk_ad} &nbsp;&nbsp; SERVICIO {chk_serv} &nbsp;&nbsp; ESTUDIANTES {chk_est} "
            f"&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp; <b>Código:</b> <u><b>{codigo_str}</b></u> / 2026",
            q_style
        ),
        Paragraph(
            f"<b>Fecha visita (Día/mes/año):</b> <u><b>{fecha_vis_str}</b></u> &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp; "
            f"<b>Facultad:</b> <u><b>{facultad_str}</b></u> &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp; <b>Universidad:</b> <u><b>{universidad_str}</b></u>",
            q_style
        )
    ]

    header_table = Table([[logo_img if logo_img else "", header_cell]], colWidths=[95, 444])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(header_table)
    elements.append(HRFlowable(width="100%", thickness=1.2, color=colors.HexColor('#1b73bc'), spaceBefore=3, spaceAfter=6))

    # =========================================================================
    # 1. DATOS DEL INDIVIDUO
    # =========================================================================
    nom_comp = f"{val('f_nombre')} {val('f_apellido1')} {val('f_apellido2')}".strip()
    mod1_rows = [
        [
            Paragraph(f"<b>1.- Nombre y Apellidos del paciente:</b> {field_txt(nom_comp, 30)}", q_style),
            Paragraph(f"<b>5.- Nº de cédula:</b> {field_txt(val('f_cedula'), 15)}", q_style)
        ],
        [
            Paragraph(f"<b>2.- Ciudad de residencia:</b> {field_txt(val('f_ciudad'), 14)} &nbsp;&nbsp; <b>Provincia:</b> {field_txt(val('f_provincia'), 14)}", q_style),
            Paragraph(f"<b>3.- Teléfono:</b> {field_txt(val('f_telefono'), 15)}", q_style)
        ],
        [
            Paragraph(f"<b>4.- Correo electrónico:</b> {field_txt(val('f_correo'), 32)}", q_style),
            Paragraph(f"<b>Visita Nº:</b> {field_txt(val('f_visita', '1'), 4)}", q_style)
        ]
    ]
    t_mod1 = Table(mod1_rows, colWidths=[355, 184])
    t_mod1.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    add_section("Datos del Individuo", t_mod1)

    # =========================================================================
    # 2. CUESTIONARIO SOCIODEMOGRÁFICO
    # =========================================================================
    sex_val = val('f_sexo', '').upper()
    chk_h = chk(sex_val.startswith('H') or sex_val == '1')
    chk_m = chk(sex_val.startswith('M') or sex_val.startswith('F') or sex_val == '2')

    ec_val = val('f_estado_civil', '').upper()
    chk_solt = chk('SOLT' in ec_val)
    chk_cas = chk('CAS' in ec_val)
    chk_div = chk('DIV' in ec_val or 'SEP' in ec_val)
    chk_viu = chk('VIU' in ec_val)
    chk_unl = chk('UNION' in ec_val or 'LIBRE' in ec_val or 'HECHO' in ec_val)

    estudios_val = val('f_estudios', '').upper()
    chk_est_sin = chk('SIN' in estudios_val or 'LEER' in estudios_val or 'ANALF' in estudios_val)
    chk_est_prim = chk('PRIM' in estudios_val)
    chk_est_sec = chk('SEC' in estudios_val or 'BACH' in estudios_val)
    chk_est_sup = chk('TERCER' in estudios_val or 'SUPERIOR' in estudios_val or 'UNIV' in estudios_val)
    chk_est_post = chk('CUARTO' in estudios_val or 'POST' in estudios_val or 'MASTER' in estudios_val or 'PHD' in estudios_val)

    horario_val = val('f_horario', '').upper()
    chk_jorn_part = chk('PART' in horario_val or 'MAÑANA/TARDE' in horario_val)
    chk_jorn_cont = chk('CONT' in horario_val or 'COMPLETA' in horario_val)

    viv_val = val('f_vivienda', '').upper()
    chk_viv_prop = chk('PROP' in viv_val or viv_val == '1')
    chk_viv_alq = chk('ALQ' in viv_val or viv_val == '2')
    chk_viv_fam = chk('FAM' in viv_val or viv_val == '3')
    chk_viv_otro = chk('OTR' in viv_val or viv_val == '4')

    ing_map = {
        '1': '1.- Menos de 500 $/mes',
        '2': '2.- 500 - 1.000 $/mes',
        '3': '3.- 1.001 - 1.500 $/mes',
        '4': '4.- 1.501 - 2.000 $/mes',
        '5': '5.- 2.001 - 2.500 $/mes',
        '6': '6.- 2.501 - 3.000 $/mes',
        '7': '7.- 3.001 - 3.500 $/mes',
        '8': '8.- Otras'
    }
    raw_ing = str(val('f_ingresos', '')).strip()
    ing_label = ing_map.get(raw_ing, raw_ing if raw_ing else '')

    mod2_rows = [
        [
            Paragraph(f"<b>1.- Lugar de nacimiento: Municipio:</b> {field_txt(val('f_municipio'), 14)} &nbsp; <b>Provincia:</b> {field_txt(val('f_provincia_nac'), 14)}", q_style),
            Paragraph(f"<b>2.- Fecha nacimiento:</b> {field_txt(val('f_fecha_nac'), 10)} &nbsp; <b>Edad:</b> {field_txt(val('f_edad'), 4)} años", q_style)
        ],
        [
            Paragraph(f"<b>4.- Sexo:</b> {chk_h} H &nbsp;&nbsp; {chk_m} M &nbsp;&nbsp;&nbsp;&nbsp; <b>5.- Etnia/Raza:</b> {field_txt(val('f_raza'), 16)}", q_style),
            Paragraph(f"<b>7.- Hijos:</b> {field_txt(val('f_hijos', '0'), 5)} &nbsp;&nbsp; <b>9.- Convivientes hogar:</b> {field_txt(val('f_convivientes', '1'), 4)}", q_style)
        ],
        [
            Paragraph(f"<b>6.- Estado Civil:</b> {chk_solt} Soltero/a &nbsp; {chk_cas} Casado/a &nbsp; {chk_div} Divorc./Sep. &nbsp; {chk_viu} Viudo/a &nbsp; {chk_unl} Unión libre", q_style),
            Paragraph(f"<b>8.- Con quién vive:</b> {field_txt(val('f_convive_con', 'Familia'), 20)}", q_style)
        ],
        [
            Paragraph(f"<b>10.- Mayor nivel de estudios:</b> {chk_est_sin} Sin est. &nbsp; {chk_est_prim} Primarios &nbsp; {chk_est_sec} Secundarios &nbsp; {chk_est_sup} Superiores &nbsp; {chk_est_post} Postgrado", q_style),
            Paragraph(f"<b>11.- Horario de trabajo:</b> {chk_jorn_part} Partida &nbsp;&nbsp; {chk_jorn_cont} Continua", q_style)
        ],
        [
            Paragraph(f"<b>12.- Categoría profesión:</b> {field_txt(val('f_profesion', val('f_estamento')), 26)}", q_style),
            Paragraph(f"<b>13.- Vivienda:</b> {chk_viv_prop} Propia &nbsp; {chk_viv_alq} Alquilada &nbsp; {chk_viv_fam} Familiar &nbsp; {chk_viv_otro} Otro", q_style)
        ],
        [
            Paragraph(f"<b>14.- Ingresos mensuales familiares sin descuentos (USD):</b> {field_txt(ing_label, 32)}", q_style),
            Paragraph("", q_style)
        ]
    ]
    t_mod2 = Table(mod2_rows, colWidths=[325, 214])
    t_mod2.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    add_section("Cuestionario Sociodemográfico", t_mod2)

    # =========================================================================
    # 3. EXPLORACIÓN FÍSICA
    # =========================================================================
    soplos_si = is_yes('soplos') or is_yes('f_soplo_sistolico') or is_yes('f_soplo_diastolico')
    extratonos_si = is_yes('extratonos')
    pulsos_si = not is_no('pulsos_palp')
    pulsos_sim_si = not is_no('pulsos_sim')
    resp_norm_si = not is_no('resp_norm')
    abd_norm_si = not is_no('abdom_norm')

    mod3_rows = [
        [
            Paragraph(f"<b>1.- Peso:</b> {field_txt(val('f_peso'), 6)} kg &nbsp;&nbsp; <b>2.- Talla:</b> {field_txt(val('f_talla'), 6)} cm &nbsp;&nbsp; <b>3.- IMC:</b> {field_txt(val('f_imc'), 6)} kg/m² &nbsp;&nbsp; <b>4.- ASC:</b> {field_txt(val('f_asc'), 5)} m²", q_style),
            Paragraph(f"<b>5.- Perímetro Abdominal:</b> {field_txt(val('f_perimetro'), 6)} cm", q_style)
        ],
        [
            Paragraph(f"<b>6.- Saturación O2:</b> {field_txt(val('f_sat_o2'), 5)} % &nbsp;&nbsp; <b>7.- TAS:</b> {field_txt(val('f_tas'), 5)} mmHg &nbsp;&nbsp; <b>TAD (TSI):</b> {field_txt(val('f_tsi'), 5)} mmHg", q_style),
            Paragraph(f"<b>Frecuencia Cardíaca:</b> {field_txt(val('f_fc'), 5)} lpm", q_style)
        ],
        [
            Paragraph(f"<b>8.- Soplos cardíacos:</b> {chk(not soplos_si)} No &nbsp; {chk(soplos_si)} Sí &nbsp;&nbsp; <b>Grado:</b> {field_txt(val('soplo_grado', val('f_grado_soplo')), 4)} &nbsp;&nbsp; <b>Tipo:</b> {field_txt(val('soplo_tipo'), 10)}", q_style),
            Paragraph(f"<b>9.- Extra-tonos:</b> {chk(not extratonos_si)} No &nbsp; {chk(extratonos_si)} Sí &nbsp; <b>Detalle:</b> {field_txt(val('extratonos_detalle'), 10)}", q_style)
        ],
        [
            Paragraph(f"<b>10.- Pulsos pedios palpables:</b> {chk(pulsos_si)} Sí &nbsp; {chk(not pulsos_si)} No &nbsp;&nbsp;&nbsp; <b>Simétricos:</b> {chk(pulsos_sim_si)} Sí &nbsp; {chk(not pulsos_sim_si)} No", q_style),
            Paragraph(f"<b>11.- Exploración respiratoria normal:</b> {chk(resp_norm_si)} Sí &nbsp; {chk(not resp_norm_si)} No", q_style)
        ],
        [
            Paragraph(f"<b>12.- Exploración abdominal normal:</b> {chk(abd_norm_si)} Sí &nbsp; {chk(not abd_norm_si)} No &nbsp;&nbsp; <b>Detalle:</b> {field_txt(val('abd_alteracion_detalle'), 10)}", q_style),
            Paragraph(f"<b>Hepatomegalia:</b> {chk(is_yes('hepatomegalia'))} Sí &nbsp; {chk(not is_yes('hepatomegalia'))} No &nbsp;&nbsp; <b>Organomegalia:</b> {chk(is_yes('organomegalia'))} Sí", q_style)
        ]
    ]
    t_mod3 = Table(mod3_rows, colWidths=[345, 194])
    t_mod3.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    add_section("Exploración Física", t_mod3)

    # =========================================================================
    # 4. FACTORES DE RIESGO MODIFICABLES
    # =========================================================================
    hta_si = is_yes('r_hta') or is_yes('hipertension')
    dm_si = is_yes('r_dm') or is_yes('diabetes_mellitus')
    dlp_si = is_yes('r_dislip') or is_yes('dislipemia')
    tab_si = is_yes('r_tabaco') or is_yes('tabaquismo')
    alc_si = is_yes('r_alcohol') or (val('alcohol') != '' and not is_no('alcohol'))
    drogas_si = is_yes('r_drogas') or is_yes('drogas')
    drog_sust = val('drogas_cuales')
    drog_frec = val('drogas_frecuencia').lower()
    drog_diaria = is_yes('drogas_dosis_diaria') or 'diaria' in drog_frec or (val('drogas_dosis_diaria') != '' and not is_no('drogas_dosis_diaria'))
    drog_semanal = is_yes('drogas_dosis_semanal') or 'semanal' in drog_frec or (val('drogas_dosis_semanal') != '' and not is_no('drogas_dosis_semanal'))
    drog_ocasional = is_yes('drogas_dosis_ocasional') or 'ocasional' in drog_frec or (val('drogas_dosis_ocasional') != '' and not is_no('drogas_dosis_ocasional'))
    drog_ex = is_yes('chk_ex_drogas')
    obes_si = is_yes('r_obesidad') or 'obesidad' in val('r_sobrepeso').lower()
    sp_si = is_yes('r_sobrepeso') or 'sobrepeso' in val('r_sobrepeso').lower()
    arrit_si = is_yes('r_arritmias') or (val('arritmias') != '' and not is_no('arritmias'))
    sinc_si = is_yes('r_sincopes') or (val('sincopes') != '' and not is_no('sincopes'))
    irc_si = is_yes('r_irc') or is_yes('insuf_renal_cronica')
    ictus_si = is_yes('r_ictus') or is_yes('antecedentrs_ictus')
    disfunc_si = is_yes('r_disfunc') or is_yes('disfuncion_erectil')
    higado_si = is_yes('r_higado') or is_yes('higado_graso')
    apnea_si = is_yes('r_apnea') or is_yes('apnea_sueno')

    mod4_rows = [
        [
            Paragraph(f"<b>1.- Hipertensión (HTA):</b> {chk(not hta_si)} No &nbsp; {chk(hta_si)} Sí &nbsp;&nbsp; <b>Fármacos:</b> {field_txt(val('hta_medicamentos', val('hta_tto')), 14)}", q_style),
            Paragraph(f"<b>2.- Prueba de MAPA:</b> {chk(is_no('mapa'))} No &nbsp; {chk(is_yes('mapa'))} Sí &nbsp; {chk(not is_yes('mapa_alt'))} Normal &nbsp; {chk(is_yes('mapa_alt'))} Alterada", q_style)
        ],
        [
            Paragraph(f"<b>3.- Diabetes mellitus:</b> {chk(not dm_si)} No &nbsp; {chk(dm_si)} Sí &nbsp;&nbsp; <b>Fármacos:</b> {field_txt(val('dm_farmacos', val('dm_clasificacion')), 10)} &nbsp; <b>Insulina:</b> {chk(is_yes('dm_insulina'))} Sí", q_style),
            Paragraph(f"<b>4.- Dislipemia:</b> {chk(not dlp_si)} No &nbsp; {chk(dlp_si)} Sí &nbsp;&nbsp; <b>Tipo:</b> {field_txt(val('dislip_tipo'), 6)} &nbsp; <b>Fármacos:</b> {field_txt(val('dislip_farmacos', val('dlp_tto')), 10)}", q_style)
        ],
        [
            Paragraph(f"<b>5.- Tabaquismo:</b> {chk(not tab_si)} No &nbsp; {chk(tab_si)} Sí &nbsp;&nbsp; <b>Cigarrillos/día:</b> {field_txt(val('tabaco_cantidad'), 4)} &nbsp; {chk(is_yes('chk_exfumador'))} Exfumador", q_style),
            Paragraph(f"<b>6.- Alcohol:</b> {chk(not alc_si)} No &nbsp; {chk(alc_si)} Sí &nbsp;&nbsp; <b>Frecuencia/Unidades:</b> {field_txt(val('alcohol_unidades', val('alcohol_frecuencia')), 10)}", q_style)
        ],
        [
            Paragraph(
                f"<b>7.- Consumo sustancias / drogas:</b> {chk(not drogas_si)} No &nbsp; {chk(drogas_si)} Sí &nbsp;&nbsp; <b>Cuáles:</b> {field_txt(drog_sust, 10)}<br/>"
                f"&nbsp;&nbsp;&nbsp;&nbsp;{chk(drog_diaria)} Diaria &nbsp; {chk(drog_semanal)} Semanal &nbsp; {chk(drog_ocasional)} Ocasional &nbsp; {chk(drog_ex)} Ex-consumidor &gt; 1 año",
                q_style
            ),
            Paragraph(f"<b>8.- Obesidad:</b> {chk(not obes_si)} No &nbsp; {chk(obes_si)} Sí &nbsp;&nbsp; <b>9.- Sobrepeso:</b> {chk(not sp_si)} No &nbsp; {chk(sp_si)} Sí", q_style)
        ],
        [
            Paragraph(f"<b>Otros factores de riesgo:</b> {field_txt(val('otros_factores_detalle'), 28)}", q_style),
            Paragraph("", q_style)
        ],
        [
            Paragraph(f"<b>10.- Arritmias:</b> {chk(not arrit_si)} No &nbsp; {chk(arrit_si)} Sí &nbsp;&nbsp; <b>Tipo:</b> {field_txt(val('arritmias_tipo'), 12)}", q_style),
            Paragraph(f"<b>11.- Síncopes:</b> {chk(not sinc_si)} No &nbsp; {chk(sinc_si)} Sí &nbsp;&nbsp; <b>12.- Holter 24h:</b> {chk(is_yes('holter'))} Sí &nbsp; {chk(not is_yes('holter'))} No", q_style)
        ],
        [
            Paragraph(f"<b>13.- Vasculopatía periférica:</b> {chk(not is_yes('r_vasc_perif'))} No &nbsp; {chk(is_yes('r_vasc_perif'))} Sí", q_style),
            Paragraph(f"<b>14.- Vasculopatía carotídea / femoral:</b> {chk(not is_yes('r_vasc_carot'))} No &nbsp; {chk(is_yes('r_vasc_carot'))} Sí", q_style)
        ],
        [
            Paragraph(f"<b>15.- Insuficiencia renal crónica (IRC):</b> {chk(not irc_si)} No &nbsp; {chk(irc_si)} Sí &nbsp;&nbsp; {chk(is_yes('irc_dialisis'))} Diálisis &nbsp; {chk(is_yes('irc_trasplante'))} Trasplante", q_style),
            Paragraph(f"<b>16.- Antecedentes ictus / AIT:</b> {chk(not ictus_si)} No &nbsp; {chk(ictus_si)} Sí", q_style)
        ],
        [
            Paragraph(f"<b>17.- Disfunción eréctil:</b> {chk(not disfunc_si)} No &nbsp; {chk(disfunc_si)} Sí", q_style),
            Paragraph(f"<b>18.- Hígado graso:</b> {chk(not higado_si)} No &nbsp; {chk(higado_si)} Sí &nbsp;&nbsp;&nbsp; <b>19.- Apnea sueño:</b> {chk(not apnea_si)} No &nbsp; {chk(apnea_si)} Sí", q_style)
        ]
    ]
    t_mod4 = Table(mod4_rows, colWidths=[295, 244])
    t_mod4.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    add_section("Factores de Riesgo Modificables", t_mod4)

    # =========================================================================
    # 5. FACTORES EMERGENTES
    # =========================================================================
    sueno_cant_buena = 'buena' in val('sueno_cantidad', 'buena').lower()
    sueno_cal_buena = 'buena' in val('sueno_calidad', 'buena').lower()
    toxicos_si = is_yes('em_toxicos') or is_yes('trabaja_con_toxicos')
    estres_trab_si = is_yes('em_estres_trab') or 'trabajo' in val('estres').lower()
    estres_fam_si = is_yes('em_estres_fam') or 'familiar' in val('estres').lower()
    mal_amb_si = is_yes('em_mal_amb') or is_yes('mal_ambiente_laboral')
    pers_a_si = is_yes('em_pers_a') or is_yes('em_personalidad_a') or is_yes('personalidad_tipo_a')

    mod5_rows = [
        [
            Paragraph(f"<b>1.- Cantidad de sueño:</b> {chk(sueno_cant_buena)} Buena &nbsp; {chk(not sueno_cant_buena)} Mala", q_style),
            Paragraph(f"<b>2.- Calidad del sueño:</b> {chk(sueno_cal_buena)} Buena &nbsp; {chk(not sueno_cal_buena)} Mala", q_style)
        ],
        [
            Paragraph(f"<b>3.- Trabaja con tóxicos:</b> {chk(not toxicos_si)} No &nbsp; {chk(toxicos_si)} Sí &nbsp;&nbsp; <b>Cuáles:</b> {field_txt(val('toxicos_cuales'), 12)}", q_style),
            Paragraph(f"<b>4.- Estrógenos bajos / Menopausia:</b> {chk(not is_yes('estrogenos_bajos'))} No &nbsp; {chk(is_yes('estrogenos_bajos'))} Sí", q_style)
        ],
        [
            Paragraph(f"<b>5.- Anticonceptivos > 35 años:</b> {chk(not is_yes('anticonceptivos'))} No &nbsp; {chk(is_yes('anticonceptivos'))} Sí", q_style),
            Paragraph(f"<b>6.- Estrés en el trabajo:</b> {chk(not estres_trab_si)} No &nbsp; {chk(estres_trab_si)} Sí", q_style)
        ],
        [
            Paragraph(f"<b>7.- Estrés en la vida familiar:</b> {chk(not estres_fam_si)} No &nbsp; {chk(estres_fam_si)} Sí", q_style),
            Paragraph(f"<b>8.- Mal ambiente laboral:</b> {chk(not mal_amb_si)} No &nbsp; {chk(mal_amb_si)} Sí", q_style)
        ],
        [
            Paragraph(
                f"<b>9.- Personalidad tipo A:</b> {chk(not pers_a_si)} No &nbsp; {chk(pers_a_si)} Sí "
                f"({chk(is_yes('em_exigente') or is_yes('exigente'))} Exigente &nbsp; {chk(is_yes('em_perfeccionista') or is_yes('perfeccionista'))} Perfeccionista &nbsp; "
                f"{chk(is_yes('em_hiperactivo'))} Hiperactivo &nbsp; {chk(is_yes('em_ambicioso'))} Ambicioso &nbsp; "
                f"{chk(is_yes('em_hostilidad'))} Hostilidad &nbsp; {chk(is_yes('em_aislamiento'))} Aislamiento)",
                q_style
            ),
            Paragraph("", q_style)
        ]
    ]
    t_mod5 = Table(mod5_rows, colWidths=[295, 244])
    t_mod5.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    add_section("Factores Emergentes", t_mod5)

    # =========================================================================
    # 6. OTROS FACTORES NO MODIFICABLES Y ANTECEDENTES FAMILIARES
    # =========================================================================
    ant_fam_cardio_si = is_yes('nm_cardiopatia') or is_yes('af_cardiopatia_prematura')
    ant_fam_fall_si = is_yes('nm_fallecido') or is_yes('af_muerte_subita')
    padre_hta = is_yes('padre_hta') or 'hta' in val('ant_fam_padre').lower()
    padre_dm = is_yes('padre_dm') or 'dm' in val('ant_fam_padre').lower() or 'diabetes' in val('ant_fam_padre').lower()
    padre_dlp = is_yes('padre_dlp') or 'dlp' in val('ant_fam_padre').lower() or 'dislip' in val('ant_fam_padre').lower()
    madre_hta = is_yes('madre_hta') or 'hta' in val('ant_fam_madre').lower()
    madre_dm = is_yes('madre_dm') or 'dm' in val('ant_fam_madre').lower() or 'diabetes' in val('ant_fam_madre').lower()
    madre_dlp = is_yes('madre_dlp') or 'dlp' in val('ant_fam_madre').lower() or 'dislip' in val('ant_fam_madre').lower()

    mod6_rows = [
        [
            Paragraph(f"<b>1.- Antecedentes familiares cardiopatía isquémica (Angina, IAM, muerte súbita):</b> {chk(not ant_fam_cardio_si)} No &nbsp; {chk(ant_fam_cardio_si)} Sí", q_style),
            Paragraph(f"<b>2.- Familiar directo fallecido antes de 55a (varón) o 65a (mujer):</b> {chk(not ant_fam_fall_si)} No &nbsp; {chk(ant_fam_fall_si)} Sí", q_style)
        ],
        [
            Paragraph(f"<b>3.- Padre con:</b> {chk(padre_hta)} HTA &nbsp;&nbsp; {chk(padre_dm)} Diabetes &nbsp;&nbsp; {chk(padre_dlp)} Dislipemia", q_style),
            Paragraph(f"<b>4.- Madre con:</b> {chk(madre_hta)} HTA &nbsp;&nbsp; {chk(madre_dm)} Diabetes &nbsp;&nbsp; {chk(madre_dlp)} Dislipemia", q_style)
        ],
        [
            Paragraph(f"<b>5.- Otras enfermedades familiares directas:</b> {field_txt(val('ant_familiares_cuales'), 36)}", q_style),
            Paragraph("", q_style)
        ]
    ]
    t_mod6 = Table(mod6_rows, colWidths=[315, 224])
    t_mod6.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    add_section("Otros Factores de Riesgo No Modificables y Antecedentes Familiares", t_mod6)

    # =========================================================================
    # 7. HISTORIA CLÍNICA ACTUAL CARDIOVASCULAR
    # =========================================================================
    hc_prob_si = is_yes('hc_prob') or (val('prob_corazon_detalle') != '')
    cardio_isq_si = is_yes('hc_isquemica') or is_yes('hc_cardiopatia_isq') or is_yes('ant_iam') or is_yes('ant_angina') or is_yes('hc_isquemica_angina') or is_yes('hc_isquemica_infarto')
    revasc_si = is_yes('hc_revasc') or is_yes('hc_revascularizacion') or (val('hc_revasc_tipo') != '')
    ic_si = is_yes('hc_insuf_cardiaca') or is_yes('hc_insuficiencia_card')
    valv_si = is_yes('hc_valvulopatia') or (val('hc_valvulopatia_cuales') != '')
    ingr_card_si = is_yes('hc_ingresado') or is_yes('hc_ingreso_card') or (val('hc_ingresado_cual') != '')

    revasc_det = val('hc_revasc_tipo', '').lower()
    is_angio = is_yes('revasc_angioplastia') or 'angioplastia' in revasc_det
    is_bypass = is_yes('revasc_bypass') or 'bypass' in revasc_det
    is_ambas = 'ambas' in revasc_det or (is_angio and is_bypass)

    valv_det = val('hc_valvulopatia_cuales') or val('valvulopatia_detalle')
    valv_op = is_yes('hc_valvulopatia_operado') or is_yes('valv_operado')

    mod7_rows = [
        [
            Paragraph(f"<b>1.- Problema previo del corazón:</b> {chk(not hc_prob_si)} No &nbsp; {chk(hc_prob_si)} Sí &nbsp;&nbsp; <b>Detalle:</b> {field_txt(val('prob_corazon_detalle'), 14)}", q_style),
            Paragraph(f"<b>2.- Cardiopatía isquémica:</b> {chk(not cardio_isq_si)} No &nbsp; {chk(cardio_isq_si)} Sí &nbsp;&nbsp; {chk(is_yes('hc_isquemica_angina') or is_yes('ant_angina'))} Angina &nbsp; {chk(is_yes('hc_isquemica_infarto') or is_yes('ant_iam'))} Infarto de miocardio", q_style)
        ],
        [
            Paragraph(f"<b>3.- Revascularización coronaria:</b> {chk(not revasc_si)} No &nbsp; {chk(revasc_si)} Sí &nbsp;&nbsp; {chk(is_angio)} Con Angioplastia &nbsp; {chk(is_bypass)} Con Bypass &nbsp; {chk(is_ambas)} Con ambas", q_style),
            Paragraph(f"<b>4.- Insuficiencia cardíaca diagnosticada:</b> {chk(not ic_si)} No &nbsp; {chk(ic_si)} Sí", q_style)
        ],
        [
            Paragraph(f"<b>5.- Valvulopatía:</b> {chk(not valv_si)} No &nbsp; {chk(valv_si)} Sí {f'({field_txt(valv_det, 10)})' if valv_det else ''} &nbsp;&nbsp; <b>Operado por este motivo:</b> {chk(not valv_op)} No &nbsp; {chk(valv_op)} Sí", q_style),
            Paragraph(f"<b>6.- Ingresado en hospital por problema cardíaco:</b> {chk(not ingr_card_si)} No &nbsp; {chk(ingr_card_si)} Sí {(' &nbsp;<b>Motivo:</b> ' + field_txt(val('hc_ingresado_cual'), 12)) if val('hc_ingresado_cual') else ''}", q_style)
        ]
    ]
    t_mod7 = Table(mod7_rows, colWidths=[315, 224])
    t_mod7.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    add_section("Historia Clínica Actual Cardiovascular", t_mod7)

    # =========================================================================
    # 8. HISTORIA CLÍNICA NO CARDIOVASCULAR
    # =========================================================================
    reuma_si = is_yes('ant_reuma') or is_yes('nc_reuma') or (val('reuma_detalle') != '')
    cancer_si = (
        is_yes('nc_cancer') or is_yes('hc_cancer') or (val('cancer_tipo') != '') or
        any(is_yes(c) for c in ['cancer_pulmon', 'cancer_prostata', 'cancer_colon', 'cancer_mama', 'cancer_vejiga', 'cancer_utero', 'cancer_ovario', 'cancer_otro'])
    )
    cancer_tipos = []
    for c_key, c_name in [('cancer_pulmon', 'Pulmón'), ('cancer_prostata', 'Próstata'), ('cancer_colon', 'Colon'), ('cancer_mama', 'Mama'), ('cancer_vejiga', 'Vejiga'), ('cancer_utero', 'Útero'), ('cancer_ovario', 'Ovario')]:
        if is_yes(c_key): cancer_tipos.append(c_name)
    if is_yes('cancer_otro') and val('cancer_otro_detalle'):
        cancer_tipos.append(val('cancer_otro_detalle'))
    cancer_desc = ", ".join(cancer_tipos) if cancer_tipos else val('cancer_tipo')

    epoc_si = is_yes('nc_epoc') or is_yes('ant_epoc')
    asma_si = is_yes('nc_asma') or is_yes('ant_asma')
    depr_si = is_yes('nc_depresion') or is_yes('ant_depresion')
    ans_si = is_yes('nc_ansiedad') or is_yes('ant_ansiedad')
    alergia_si = is_yes('nc_alergia') or (val('alergia_medicamento', val('alergia_medicamentos')) != '' and not is_no('alergia_medicamento'))

    mod8_rows = [
        [
            Paragraph(f"<b>1.- Enfermedad reumatológica / inmune:</b> {chk(not reuma_si)} No &nbsp; {chk(reuma_si)} Sí &nbsp;&nbsp; <b>Cuáles:</b> {field_txt(val('reuma_detalle'), 14)}", q_style),
            Paragraph(f"<b>2.- Historia de cáncer:</b> {chk(not cancer_si)} No &nbsp; {chk(cancer_si)} Sí &nbsp;&nbsp; <b>Tipo:</b> {field_txt(cancer_desc, 12)}", q_style)
        ],
        [
            Paragraph(f"<b>¿Recibió Quimioterapia (Qt)?:</b> {chk(is_yes('cancer_qt'))} Sí &nbsp; {chk(not is_yes('cancer_qt'))} No &nbsp;&nbsp;&nbsp;&nbsp; <b>¿Radioterapia (Rt)?:</b> {chk(is_yes('cancer_rt'))} Sí &nbsp; {chk(not is_yes('cancer_rt'))} No", q_style),
            Paragraph(f"<b>3.- EPOC:</b> {chk(not epoc_si)} No &nbsp; {chk(epoc_si)} Sí &nbsp;&nbsp;&nbsp;&nbsp; <b>4.- Asma:</b> {chk(not asma_si)} No &nbsp; {chk(asma_si)} Sí", q_style)
        ],
        [
            Paragraph(f"<b>5.- Depresión diagnosticada:</b> {chk(not depr_si)} No &nbsp; {chk(depr_si)} Sí &nbsp;&nbsp;&nbsp;&nbsp; <b>6.- Trastorno de ansiedad:</b> {chk(not ans_si)} No &nbsp; {chk(ans_si)} Sí", q_style),
            Paragraph(f"<b>7.- Alergia a fármacos:</b> {chk(not alergia_si)} No &nbsp; {chk(alergia_si)} Sí &nbsp;&nbsp; <b>Cuáles:</b> {field_txt(val('alergia_medicamento', val('alergia_medicamentos')), 10)}", q_style)
        ],
        [
            Paragraph(f"<b>8.- Otras patologías relevantes:</b> {field_txt(val('otras_enf_detalle', val('otras_no_cardio')), 36)}", q_style),
            Paragraph("", q_style)
        ]
    ]
    t_mod8 = Table(mod8_rows, colWidths=[315, 224])
    t_mod8.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    add_section("Historia Clínica No Cardiovascular", t_mod8)

    # =========================================================================
    # 9. COVID-19 Y LONG-COVID
    # =========================================================================
    covid_paso_si = is_yes('covid_paso') or is_yes('covid_infeccion')
    covid_ingr_si = is_yes('covid_ingreso')
    covid_cv_si = is_yes('covid_cv') or is_yes('covid_secuelas_cardio')
    covid_pulm_si = is_yes('covid_pulm')
    long_covid_si = is_yes('longcovid') or (val('long_covid') != '' and not is_no('long_covid'))

    mod9_rows = [
        [
            Paragraph(f"<b>1.- Ha pasado el COVID-19:</b> {chk(not covid_paso_si)} No &nbsp; {chk(covid_paso_si)} Sí", q_style),
            Paragraph(f"<b>2.- Estuvo ingresado en el hospital:</b> {chk(not covid_ingr_si)} No &nbsp; {chk(covid_ingr_si)} Sí", q_style)
        ],
        [
            Paragraph(f"<b>3.- Afectación cardiovascular debida al COVID-19:</b> {chk(not covid_cv_si)} No &nbsp; {chk(covid_cv_si)} Sí &nbsp; <b>Detalle:</b> {field_txt(val('covid_cv_detalle'), 10)}", q_style),
            Paragraph(f"<b>4.- Afectación pulmonar debida al COVID-19:</b> {chk(not covid_pulm_si)} No &nbsp; {chk(covid_pulm_si)} Sí &nbsp; <b>Detalle:</b> {field_txt(val('covid_pulm_detalle'), 10)}", q_style)
        ],
        [
            Paragraph(f"<b>5.- Otras secuelas COVID:</b> {field_txt(val('covid_otras_detalle', val('covid_otras')), 28)}", q_style),
            Paragraph(f"<b>6.- Long-COVID (síntomas persistentes):</b> {chk(not long_covid_si)} No &nbsp; {chk(long_covid_si)} Sí &nbsp; <b>Síntomas:</b> {field_txt(val('long_covid_sintomas', val('long_covid')), 10)}", q_style)
        ]
    ]
    t_mod9 = Table(mod9_rows, colWidths=[295, 244])
    t_mod9.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    add_section("COVID-19 y Long-COVID", t_mod9)

    # =========================================================================
    # 10. CUESTIONARIO DE DOLOR DE PECHO DE G. ROSE Y CLASIFICACIÓN NYHA
    # =========================================================================
    rose_dolor_si = is_yes('rose_1') or is_yes('dolor_pecho') or is_yes('rose_dolor_pecho')
    rose_habitual_si = is_yes('rose_3')
    rose_cuesta_si = is_yes('rose_4')
    rose_desap_si = is_yes('rose_6')
    rose_pos_si = is_yes('rose_8') or is_yes('rose_positivo')

    nyha_clase = val('nyha_clase', '1')
    chk_nyha1 = chk('1' in nyha_clase or 'i' == nyha_clase.lower())
    chk_nyha2 = chk('2' in nyha_clase or 'ii' == nyha_clase.lower())
    chk_nyha3 = chk('3' in nyha_clase or 'iii' == nyha_clase.lower())
    chk_nyha4 = chk('4' in nyha_clase or 'iv' == nyha_clase.lower())

    mod10_rows = [
        [
            Paragraph(f"<b>1.- ¿Tiene dolor o molestia en el pecho?:</b> {chk(rose_dolor_si)} Sí &nbsp; {chk(not rose_dolor_si)} No &nbsp;&nbsp;&nbsp; <b>2.- Localización (cuadrantes 1-9):</b> {field_txt(val('rose_2'), 10)}", q_style),
            Paragraph(f"<b>Clasificación Funcional NYHA:</b>", q_bold)
        ],
        [
            Paragraph(f"<b>3.- Al caminar a paso habitual produce molestia:</b> {chk(rose_habitual_si)} Sí &nbsp; {chk(not rose_habitual_si)} No", q_style),
            Paragraph(f"{chk_nyha1} <b>Clase I:</b> Sin limitación en actividad ordinaria.", q_style)
        ],
        [
            Paragraph(f"<b>4.- Al caminar cuesta arriba o apurado:</b> {chk(rose_cuesta_si)} Sí &nbsp; {chk(not rose_cuesta_si)} No", q_style),
            Paragraph(f"{chk_nyha2} <b>Clase II:</b> Ligera limitación. Confortable en reposo.", q_style)
        ],
        [
            Paragraph(f"<b>5.- Al tener dolor caminando:</b> {val('rose_5', 'Se para / Disminuye marcha')}", q_style),
            Paragraph(f"{chk_nyha3} <b>Clase III:</b> Marcada limitación. Síntomas con actividad menor.", q_style)
        ],
        [
            Paragraph(f"<b>6.- Desaparece al quedarse quieto:</b> {chk(rose_desap_si)} Sí &nbsp; {chk(not rose_desap_si)} No &nbsp;&nbsp;&nbsp; <b>7.- Tiempo:</b> {val('rose_7', '<= 10 minutos')}", q_style),
            Paragraph(f"{chk_nyha4} <b>Clase IV:</b> Incapacidad total. Síntomas en reposo.", q_style)
        ],
        [
            Paragraph(f"<b>8.- Cuestionario de dolor de pecho de G. Rose:</b> {chk(rose_pos_si)} <b>POSITIVO</b> &nbsp;&nbsp;&nbsp; {chk(not rose_pos_si)} <b>NEGATIVO</b>", q_bold),
            Paragraph("", q_style)
        ]
    ]
    t_mod10 = Table(mod10_rows, colWidths=[315, 224])
    t_mod10.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    add_section("Cuestionario de Dolor de Pecho de G. Rose y Clasificación NYHA", t_mod10)

    # =========================================================================
    # 11. RESULTADOS DEL ELECTROCARDIOGRAMA (ECG) - 27 ÍTEMS COMPLETOS
    # =========================================================================
    ecg_norm_si = not is_no('ecg_normal')
    hvi_si = is_yes('ecg_hvi')
    hvd_si = is_yes('ecg_hvd')
    onda_p_si = is_yes('ecg_p_mitral') or is_yes('onda_p_mitral')
    bloqueo_av_si = is_yes('ecg_bloqueo_av') or is_yes('bloqueo_av')
    bloqueo_sa_si = is_yes('ecg_bloqueo_sa') or is_yes('bloqueo_sa')
    bloqueo_ia_si = is_yes('ecg_bloqueo_ia') or is_yes('bloqueo_ia')
    hemibloqueo_si = is_yes('ecg_hemibloqueo') or is_yes('hemibloqueo')
    bloqueo_rama_si = is_yes('ecg_bloqueo_rama_sn') or is_yes('bloqueo_rama') or (val('ecg_bloqueo_rama') != '' and not is_no('ecg_bloqueo_rama'))
    brugada_si = is_yes('ecg_brugada') or is_yes('patron_brugada')
    repol_si = is_yes('ecg_repolarizacion_precoz') or is_yes('repolarizacion_precoz')
    sobrecarga_si = is_yes('ecg_sobrecarga_sistolica') or is_yes('sobrecarga_sistolica')
    onda_delta_si = is_yes('ecg_onda_delta')
    cubeta_si = is_yes('ecg_cubeta_digitalica') or is_yes('cubeta_digitalica')
    onda_q_si = is_yes('ecg_onda_q') or is_yes('onda_q_patologica')
    t_neg_si = is_yes('ecg_t_negativa')
    st_asc_si = is_yes('ecg_st_ascenso') or is_yes('ascenso_st_patologico')
    st_desc_si = is_yes('ecg_st_descenso') or is_yes('descenso_st_patologico')
    alt_repol_si = is_yes('ecg_alt_repolarizacion')

    mod11_rows = [
        [
            Paragraph(f"<b>1.- Ritmo:</b> {field_txt(val('ecg_ritmo', 'Ritmo Sinusal (RS)'), 12)} &nbsp;&nbsp; <b>2.- FC:</b> {field_txt(val('ecg_fc'), 4)} lpm &nbsp;&nbsp; <b>3.- Eje ÂQRS:</b> {field_txt(val('ecg_eje'), 4)} °", q_style),
            Paragraph(f"<b>4.- Intervalo RR:</b> {field_txt(val('ecg_rr'), 4)} s &nbsp;&nbsp; <b>5.- Onda P:</b> {field_txt(val('ecg_p_mm'), 4)} mm", q_style)
        ],
        [
            Paragraph(f"<b>6.- Intervalo PR:</b> {field_txt(val('ecg_pr'), 4)} ms &nbsp;&nbsp; <b>7.- Complejo QRS:</b> {field_txt(val('ecg_qrs'), 4)} ms", q_style),
            Paragraph(f"<b>8.- Intervalo QT:</b> {field_txt(val('ecg_qt'), 4)} ms &nbsp;&nbsp; <b>9.- QTc (Bazett):</b> {field_txt(val('ecg_qtc'), 4)} ms", q_style)
        ],
        [
            Paragraph(f"<b>10.- Onda P mitral:</b> {chk(not onda_p_si)} No &nbsp; {chk(onda_p_si)} Sí", q_style),
            Paragraph(f"<b>11.- Bloqueo A-V:</b> {chk(not bloqueo_av_si)} No &nbsp; {chk(bloqueo_av_si)} Sí &nbsp; <b>Grado:</b> {field_txt(val('ecg_bloqueo_av_grado'), 10)}", q_style)
        ],
        [
            Paragraph(f"<b>12.- Bloqueo sinoauricular (SA):</b> {chk(not bloqueo_sa_si)} No &nbsp; {chk(bloqueo_sa_si)} Sí", q_style),
            Paragraph(f"<b>13.- Bloqueo Interauricular (IA):</b> {chk(not bloqueo_ia_si)} No &nbsp; {chk(bloqueo_ia_si)} Sí", q_style)
        ],
        [
            Paragraph(f"<b>14.- Hemibloqueos:</b> {chk(not hemibloqueo_si)} No &nbsp; {chk(hemibloqueo_si)} Sí &nbsp; <b>Cuál:</b> {field_txt(val('ecg_hemibloqueo_cual'), 10)}", q_style),
            Paragraph(f"<b>15.- Bloqueo de rama:</b> {chk(not bloqueo_rama_si)} No &nbsp; {chk(bloqueo_rama_si)} Sí &nbsp; <b>Tipo:</b> {field_txt(val('ecg_bloqueo_rama', val('bloqueo_de_rama_cual')), 10)}", q_style)
        ],
        [
            Paragraph(f"<b>16.- Patrón Brugada:</b> {chk(not brugada_si)} No &nbsp; {chk(brugada_si)} Sí", q_style),
            Paragraph(f"<b>17.- Repolarización precoz:</b> {chk(not repol_si)} No &nbsp; {chk(repol_si)} Sí &nbsp;&nbsp; <b>18.- Criterios HVI:</b> {chk(not hvi_si)} No &nbsp; {chk(hvi_si)} Sí", q_style)
        ],
        [
            Paragraph(f"<b>19.- Sobrecarga sistólica:</b> {chk(not sobrecarga_si)} No &nbsp; {chk(sobrecarga_si)} Sí &nbsp; <b>Compl.:</b> {field_txt(val('ecg_sobrecarga_complejos'), 8)}", q_style),
            Paragraph(f"<b>20.- Deflexión intrinsicoide V5-V6:</b> {field_txt(val('ecg_deflexion_intrinsicoide'), 4)} s &nbsp;&nbsp; <b>21.- HVD:</b> {chk(not hvd_si)} No &nbsp; {chk(hvd_si)} Sí", q_style)
        ],
        [
            Paragraph(f"<b>22.- Onda Delta:</b> {chk(not onda_delta_si)} No &nbsp; {chk(onda_delta_si)} Sí", q_style),
            Paragraph(f"<b>23.- Cubeta digitálica:</b> {chk(not cubeta_si)} No &nbsp; {chk(cubeta_si)} Sí", q_style)
        ],
        [
            Paragraph(f"<b>24.- Onda Q patológica:</b> {chk(not onda_q_si)} No &nbsp; {chk(onda_q_si)} Sí &nbsp; <b>Ampl.:</b> {field_txt(val('ecg_onda_q_amplitud'), 5)} &nbsp; <b>Volt.:</b> {field_txt(val('ecg_onda_q_voltaje'), 4)} mV &nbsp; <b>Compl.:</b> {field_txt(val('ecg_onda_q_complejos'), 6)}", q_style),
            Paragraph(f"<b>25.- T negativa:</b> {chk(not t_neg_si)} No &nbsp; {chk(t_neg_si)} Sí &nbsp; <b>Compl.:</b> {field_txt(val('ecg_t_negativa_complejos'), 6)} (Sim.: {chk(is_yes('ecg_t_simetrica'))} Asim.: {chk(is_yes('ecg_t_asimetrica'))})", q_style)
        ],
        [
            Paragraph(f"<b>26.- Ascenso ST patológico:</b> {chk(not st_asc_si)} No &nbsp; {chk(st_asc_si)} Sí &nbsp; <b>Elev.:</b> {field_txt(val('ecg_st_ascenso_mm'), 4)} mm &nbsp; <b>Compl.:</b> {field_txt(val('ecg_st_ascenso_complejos'), 6)}", q_style),
            Paragraph(f"<b>27.- Descenso ST:</b> {chk(not st_desc_si)} No &nbsp; {chk(st_desc_si)} Sí &nbsp; <b>Depr.:</b> {field_txt(val('ecg_st_descenso_mm'), 4)} mm &nbsp; <b>Compl.:</b> {field_txt(val('ecg_st_descenso_complejos'), 6)}", q_style)
        ],
        [
            Paragraph(f"<b>ECG Normal:</b> {chk(ecg_norm_si)} Sí &nbsp; {chk(not ecg_norm_si)} No &nbsp;&nbsp;&nbsp; <b>Comentario ECG:</b> {field_txt(val('ecg_comentario'), 20)}", q_style),
            Paragraph(f"<b>Alteraciones de la repolarización:</b> {chk(not alt_repol_si)} No &nbsp; {chk(alt_repol_si)} Sí", q_style)
        ]
    ]
    t_mod11 = Table(mod11_rows, colWidths=[315, 224])
    t_mod11.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    add_section("Resultados del Electrocardiograma", t_mod11)

    # =========================================================================
    # 12. ANÁLISIS CLÍNICOS / LABORATORIO
    # =========================================================================
    lab_realizada_si = not is_no('ac_prueba')
    lab_norm_si = not is_no('ac_resultado')

    mod12_rows = [
        [
            Paragraph(f"<b>Prueba realizada:</b> {chk(lab_realizada_si)} Sí &nbsp; {chk(not lab_realizada_si)} No &nbsp;&nbsp;&nbsp;&nbsp; <b>Resultado:</b> {chk(lab_norm_si)} Normal &nbsp; {chk(not lab_norm_si)} Alterada", q_bold),
            Paragraph("", q_style)
        ],
        [
            Paragraph(f"<b>Hemograma:</b> Hematíes: {field_txt(val('hemo_hematies'), 4)} M/uL &nbsp;|&nbsp; Hb: {field_txt(val('hemo_hemoglobina'), 4)} g/dL &nbsp;|&nbsp; Hto: {field_txt(val('hemo_hematocrito'), 4)} % &nbsp;|&nbsp; VCM: {field_txt(val('hemo_vcm'), 4)} fL", q_style),
            Paragraph(f"Leucocitos: {field_txt(val('hemo_leucocitos'), 4)} /uL &nbsp;|&nbsp; Plaquetas: {field_txt(val('hemo_plaquetas'), 4)} /uL &nbsp;|&nbsp; INR: {field_txt(val('hemo_inr'), 4)}", q_style)
        ],
        [
            Paragraph(f"<b>Parámetros Diabéticos:</b> Glucosa basal: {field_txt(val('diab_glucosa'), 5)} mg/dL &nbsp;|&nbsp; HbA1c: {field_txt(val('diab_hba1c'), 4)} % &nbsp;|&nbsp; HOMA-IR: {field_txt(val('diab_homair'), 4)} &nbsp;|&nbsp; Insulina: {field_txt(val('diab_insulina'), 4)}", q_style),
            Paragraph(f"<b>Función Tiroidea:</b> TSH: {field_txt(val('tiroidea_tsh'), 4)} uIU/mL &nbsp;|&nbsp; T4: {field_txt(val('tiroidea_t4'), 4)}", q_style)
        ],
        [
            Paragraph(f"<b>Perfil Lipídico:</b> Colesterol Total: {field_txt(val('riesgo_colesterol'), 5)} mg/dL &nbsp;|&nbsp; HDL: {field_txt(val('riesgo_hdl'), 4)} mg/dL &nbsp;|&nbsp; LDL: {field_txt(val('riesgo_ldl'), 4)} mg/dL &nbsp;|&nbsp; Triglicéridos: {field_txt(val('riesgo_trigliceridos'), 5)} mg/dL", q_style),
            Paragraph(f"<b>Función Renal:</b> Creatinina: {field_txt(val('renal_creatinina'), 4)} mg/dL &nbsp;|&nbsp; Urea: {field_txt(val('renal_urea'), 4)} mg/dL", q_style)
        ]
    ]
    t_mod12 = Table(mod12_rows, colWidths=[335, 204])
    t_mod12.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    add_section("Analisis Clinicos", t_mod12)

    # =========================================================================
    # 13. RESULTADOS ECOCARDIOGRÁFICOS Y PERICARDIO
    # =========================================================================
    eco_norm_si = not is_no('res_eco_normal')
    vi_dilat_si = is_yes('res_vi_dilatado')
    vi_hipert_si = is_yes('res_vi_hipertrofico')
    fdvi_norm_si = not is_no('res_fdvi')
    derrame_si = is_yes('res_derrame_pericardico') or is_yes('derrame_pericardico')

    mod13_rows = [
        [
            Paragraph(f"<b>1.- Fracción de Eyección (FEVI %):</b> {field_txt(val('eco_fey', '60'), 4)} % &nbsp;&nbsp;&nbsp; <b>2.- DDVI:</b> {field_txt(val('eco_ddvi'), 4)} mm", q_style),
            Paragraph(f"<b>3.- Ventrículo Izquierdo Dilatado:</b> {chk(not vi_dilat_si)} No &nbsp; {chk(vi_dilat_si)} Sí", q_style)
        ],
        [
            Paragraph(f"<b>4.- Ventrículo Izquierdo Hipertrófico:</b> {chk(not vi_hipert_si)} No &nbsp; {chk(vi_hipert_si)} Sí &nbsp;&nbsp; <b>Tipo:</b> {field_txt(val('res_vi_hipertrofico_tipo'), 10)}", q_style),
            Paragraph(f"<b>5.- Función Diastólica VI:</b> {chk(fdvi_norm_si)} Normal &nbsp; {chk(not fdvi_norm_si)} Alterada", q_style)
        ],
        [
            Paragraph(f"<b>6.- Valvulopatía detectada:</b> {chk(is_yes('valvulopatia'))} Sí &nbsp; {chk(not is_yes('valvulopatia'))} No &nbsp;&nbsp; <b>Detalle:</b> {field_txt(val('valvulopatia_tipo_detalle'), 16)}", q_style),
            Paragraph(f"<b>7.- Derrame pericárdico:</b> {chk(not derrame_si)} No &nbsp; {chk(derrame_si)} Sí", q_style)
        ],
        [
            Paragraph(f"<b>ECOCARDIOGRAFÍA NORMAL:</b> {chk(eco_norm_si)} Sí &nbsp; {chk(not eco_norm_si)} No &nbsp;&nbsp;&nbsp; <b>Comentario:</b> {field_txt(val('res_eco_comentario'), 24)}", q_style),
            Paragraph("", q_style)
        ]
    ]
    t_mod13 = Table(mod13_rows, colWidths=[315, 224])
    t_mod13.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    add_section("Resultados Ecocardiográficos y Pericardio", t_mod13)

    # =========================================================================
    # 14. CUESTIONARIO PREDIMED (DIETA MEDITERRÁNEA)
    # =========================================================================
    p1 = is_yes('pred_q1') or is_yes('usa_usted_aceite_de_oliva')
    p2 = is_yes('pred_q2') or is_yes('cuanto_aceite_de_oliva_consume')
    p3 = is_yes('pred_q3') or is_yes('usted_consume_verduras')
    p4 = is_yes('pred_q4') or is_yes('usted_consume_fruta')
    p5 = is_yes('pred_q5') or is_yes('usted_consume_carne_roja_embut')
    p6 = is_yes('pred_q6') or is_yes('usted_consume_mantequilla_marg')
    p7 = is_yes('pred_q7') or is_yes('usted_consume_bebidas_carbonat')
    p8 = is_yes('pred_q8') or is_yes('pred_q8_bebe') or is_yes('usted_consume_vino_tinto')
    p9 = is_yes('pred_q9') or is_yes('usted_consume_legumbres')
    p10 = is_yes('pred_q10') or is_yes('usted_consume_pescado_mariscos')
    p11 = is_yes('pred_q11') or is_yes('usted_consume_pescado_azul')
    p12 = is_yes('pred_q12') or is_yes('usted_consume_reposteria')
    p13 = is_yes('pred_q13') or is_yes('usted_consume_frutos_secos')
    p14 = is_yes('pred_q14') or is_yes('usted_consume_sofrito') or is_yes('pred_q19')

    pred_score = sum([p1, p2, p3, p4, p5, p6, p7, p8, p9, p10, p11, p12, p13, p14])
    adherencia_str = "Buena adherencia (>= 9 puntos)" if pred_score >= 9 else "Baja adherencia (< 9 puntos)"

    leche_si = is_yes('pred_q13_consume') or val('pred_leche_tipo') != '' or val('pred_leche_vasos_dia') != ''
    queso_si = is_yes('pred_q14_consume') or val('pred_queso_gramos') != '' or val('pred_queso_veces_sem') != ''
    yogurt_si = is_yes('pred_q15_consume') or val('pred_yogurt_tipo') != '' or val('pred_yogurt_cant_sem') != ''
    sofrito_si = is_yes('pred_q19') or p14

    pred_rows = [
        [
            Paragraph(f"<b>1. ¿Usa aceite de oliva principalmente para cocinar?:</b> {chk(not p1)} No &nbsp; {chk(p1)} Sí", q_style),
            Paragraph(f"<b>2. ¿Aceite de oliva en total >= 2 cucharadas al día?:</b> {chk(not p2)} No &nbsp; {chk(p2)} Sí", q_style)
        ],
        [
            Paragraph(f"<b>3. ¿Raciones de verduras u hortalizas >= 2 al día?:</b> {chk(not p3)} No &nbsp; {chk(p3)} Sí", q_style),
            Paragraph(f"<b>4. ¿Piezas de fruta (o zumo) >= 3 al día?:</b> {chk(not p4)} No &nbsp; {chk(p4)} Sí", q_style)
        ],
        [
            Paragraph(f"<b>5. ¿Carnes rojas, embutidos o hamburguesas < 1 al día?:</b> {chk(not p5)} No &nbsp; {chk(p5)} Sí", q_style),
            Paragraph(f"<b>6. ¿Mantequilla, margarina o nata < 1 al día?:</b> {chk(not p6)} No &nbsp; {chk(p6)} Sí", q_style)
        ],
        [
            Paragraph(f"<b>7. ¿Bebidas carbonatadas / azucaradas < 1 al día?:</b> {chk(not p7)} No &nbsp; {chk(p7)} Sí", q_style),
            Paragraph(f"<b>8. ¿Vino tinto >= 3 vasos por semana?:</b> {chk(not p8)} No &nbsp; {chk(p8)} Sí", q_style)
        ],
        [
            Paragraph(f"<b>9. ¿Raciones de legumbres >= 3 por semana?:</b> {chk(not p9)} No &nbsp; {chk(p9)} Sí", q_style),
            Paragraph(f"<b>10. ¿Pescados o mariscos >= 3 por semana?:</b> {chk(not p10)} No &nbsp; {chk(p10)} Sí", q_style)
        ],
        [
            Paragraph(f"<b>11. ¿Pescado azul (salmón, atún, sardinas) >= 2 por semana?:</b> {chk(not p11)} No &nbsp; {chk(p11)} Sí", q_style),
            Paragraph(f"<b>12. ¿Repostería comercial o pasteles < 3 por semana?:</b> {chk(not p12)} No &nbsp; {chk(p12)} Sí", q_style)
        ],
        [
            Paragraph(f"<b>13. ¿Frutos secos (ración 30g) >= 2 por semana?:</b> {chk(not p13)} No &nbsp; {chk(p13)} Sí", q_style),
            Paragraph(f"<b>14. ¿Platos aderezados con sofrito casero >= 2 por semana?:</b> {chk(not p14)} No &nbsp; {chk(p14)} Sí", q_style)
        ],
        [
            Paragraph(f"<b>PUNTUACIÓN TOTAL PREDIMED:</b> <u><b>{pred_score} / 14 puntos</b></u> &nbsp;&nbsp;&nbsp;&nbsp; <b>Nivel de Adherencia:</b> <u><b>{adherencia_str}</b></u>", q_bold),
            Paragraph(f"<b>19. ¿Consume sofrito casero &gt;= 2 veces/sem?:</b> {chk(not sofrito_si)} No &nbsp; {chk(sofrito_si)} Sí", q_style)
        ],
        [
            Paragraph("<b>Registro Nutricional Complementario: Lácteos (Cuestionario UNEMI 2026):</b>", q_bold),
            Paragraph("", q_style)
        ],
        [
            Paragraph(f"<b>13. Leche de vaca:</b> {chk(not leche_si)} No &nbsp; {chk(leche_si)} Sí &nbsp;&nbsp; <b>Vasos/día:</b> {field_txt(val('pred_leche_vasos_dia'), 3)} &nbsp; <b>Vasos/sem:</b> {field_txt(val('pred_leche_vasos_sem'), 3)} &nbsp; <b>Tipo:</b> {field_txt(val('pred_leche_tipo'), 8)}", q_style),
            Paragraph(f"<b>14. Queso:</b> {chk(not queso_si)} No &nbsp; {chk(queso_si)} Sí &nbsp;&nbsp; <b>Veces/sem:</b> {field_txt(val('pred_queso_veces_sem'), 3)} &nbsp; <b>Gramos:</b> {field_txt(val('pred_queso_gramos'), 4)}", q_style)
        ],
        [
            Paragraph(f"<b>15. Yogurt:</b> {chk(not yogurt_si)} No &nbsp; {chk(yogurt_si)} Sí &nbsp;&nbsp; <b>Unidades/sem:</b> {field_txt(val('pred_yogurt_cant_sem'), 3)} &nbsp; <b>Tipo:</b> {field_txt(val('pred_yogurt_tipo'), 10)}", q_style),
            Paragraph("", q_style)
        ]
    ]
    t_pred = Table(pred_rows, colWidths=[270, 269])
    t_pred.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    add_section("Cuestionario PREDIMED: Cuestionario de Adherencia a la Dieta Mediterránea", t_pred)

    # =========================================================================
    # 15. CUESTIONARIO DE ACTIVIDAD FÍSICA
    # =========================================================================
    af_realiza_si = is_yes('af_realiza') or not is_no('af_camina')
    af_aero_si = is_yes('af_aerobico')
    af_anaero_si = is_yes('af_anaerobico')
    af_deporte_si = is_yes('af_deporte')

    mod15_rows = [
        [
            Paragraph(f"<b>1.- ¿Actividad física en su tiempo libre en el ÚLTIMO MES?:</b> {chk(not af_realiza_si)} No realiza &nbsp; {chk(af_realiza_si)} Sí realiza actividad física", q_style),
            Paragraph("", q_style)
        ],
        [
            Paragraph(f"<b>2.- Ejercicios aeróbicos (caminar, correr, bici, piscina):</b> {chk(not af_aero_si)} No &nbsp; {chk(af_aero_si)} Sí &nbsp;&nbsp; <b>Cuál:</b> {field_txt(val('af_aerobico_cual'), 10)}", q_style),
            Paragraph(f"<b>Veces/semana:</b> {field_txt(val('af_aerobico_veces'), 3)} &nbsp; <b>Minutos/día:</b> {field_txt(val('af_aerobico_min'), 4)} min", q_style)
        ],
        [
            Paragraph(f"<b>3.- Ejercicios de fuerza (pesas, gimnasio):</b> {chk(not af_anaero_si)} No &nbsp; {chk(af_anaero_si)} Sí &nbsp;&nbsp; <b>Cuál:</b> {field_txt(val('af_anaerobico_cual'), 10)}", q_style),
            Paragraph(f"<b>Veces/semana:</b> {field_txt(val('af_anaerobico_veces'), 3)} &nbsp; <b>Minutos/día:</b> {field_txt(val('af_anaerobico_min'), 4)} min", q_style)
        ],
        [
            Paragraph(f"<b>4.- ¿Practica algún deporte formal?:</b> {chk(not af_deporte_si)} No &nbsp; {chk(af_deporte_si)} Sí &nbsp;&nbsp; <b>Cuál:</b> {field_txt(val('af_deporte_tipo'), 10)}", q_style),
            Paragraph(f"<b>Veces/semana:</b> {field_txt(val('af_deporte_veces'), 3)} &nbsp; <b>Minutos/día:</b> {field_txt(val('af_deporte_min'), 4)} min", q_style)
        ]
    ]
    t_mod15 = Table(mod15_rows, colWidths=[315, 224])
    t_mod15.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    add_section("Cuestionario de Actividad Física", t_mod15)

    # =========================================================================
    # 16. ESTUDIOS QUE SE LE HA MANDADO AL PACIENTE (CATÁLOGO OFICIAL 2026: 8 ÍTEMS + OBSERVACIONES)
    # =========================================================================
    est_analisis = is_yes('est_analisis_clinicos') or is_yes('sol_analisis') or not is_no('ac_prueba')
    est_ergo = is_yes('est_ergometria_spect') or is_yes('sol_ergometria') or is_yes('estudios_ergometria')
    est_tac = is_yes('est_tac_cardiaco') or is_yes('sol_tac') or is_yes('estudios_tac')
    est_rnm = is_yes('est_rnm_cardiaco') or is_yes('sol_rnm') or is_yes('estudios_rnm')
    est_ef = is_yes('est_electrofisiologia') or is_yes('sol_electrofisiologia') or is_yes('estudios_electrofisiologia')
    est_eco = is_yes('est_ecocardiograma') or is_yes('est_eco') or is_yes('sol_eco') or is_yes('estudios_ecocardiograma')
    est_holter = is_yes('est_holter') or is_yes('sol_holter') or is_yes('estudios_holter') or is_yes('estudios_holter_ecg')
    est_mapa = is_yes('est_mapa') or is_yes('sol_mapa') or is_yes('estudios_mapa') or is_yes('usted_se_ha_realizado_estudios_de_mapa')
    est_obs = val('est_otros_detalle', val('estudios_observaciones', val('otros_estudios')))

    mod16_rows = [
        [
            Paragraph(f"<b>1.- Estudios de Análisis Clínicos:</b> {chk(not est_analisis)} No &nbsp; {chk(est_analisis)} Sí", q_style),
            Paragraph(f"<b>2.- Ergometría con SPECT:</b> {chk(not est_ergo)} No &nbsp; {chk(est_ergo)} Sí", q_style)
        ],
        [
            Paragraph(f"<b>3.- Estudios de TAC cardíaco:</b> {chk(not est_tac)} No &nbsp; {chk(est_tac)} Sí", q_style),
            Paragraph(f"<b>4.- Estudios de RNM cardíaco:</b> {chk(not est_rnm)} No &nbsp; {chk(est_rnm)} Sí", q_style)
        ],
        [
            Paragraph(f"<b>5.- Estudios de Electrofisiología Cardíaca:</b> {chk(not est_ef)} No &nbsp; {chk(est_ef)} Sí", q_style),
            Paragraph(f"<b>6.- Ecocardiografía:</b> {chk(not est_eco)} No &nbsp; {chk(est_eco)} Sí", q_style)
        ],
        [
            Paragraph(f"<b>7.- Holter ECG:</b> {chk(not est_holter)} No &nbsp; {chk(est_holter)} Sí", q_style),
            Paragraph(f"<b>8.- MAPA:</b> {chk(not est_mapa)} No &nbsp; {chk(est_mapa)} Sí", q_style)
        ],
        [
            Paragraph(f"<b>Observaciones / Otros estudios:</b> {field_txt(est_obs, 40)}", q_style),
            Paragraph("", q_style)
        ]
    ]
    t_mod16 = Table(mod16_rows, colWidths=[270, 269])
    t_mod16.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    add_section("Estudios Prescritos", t_mod16)

    # Bloque de firmas removido a petición del usuario

    doc.build(elements, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer.getvalue()
