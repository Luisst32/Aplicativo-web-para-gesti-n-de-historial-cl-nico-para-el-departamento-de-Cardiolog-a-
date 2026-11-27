import io
import os
import re
import unicodedata
from xml.sax.saxutils import escape as xml_escape

from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from clinical.models import Visit

PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT_MARGIN = 26
RIGHT_MARGIN = 26
TOP_MARGIN = 32
BOTTOM_MARGIN = 34


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to render running headers, footers, and exact 'Página X de Y'
    across every page of the clinical questionnaire PDF.
    """

    def __init__(self, *args, study_code="", patient_info="", is_blank=False, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self._study_code = study_code
        self._patient_info = patient_info
        self._is_blank = is_blank

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 7.3)
        self.setFillColor(colors.HexColor("#475569"))

        if self._pageNumber > 1:
            self.setFont("Helvetica-Bold", 7.5)
            self.setFillColor(colors.HexColor("#1e3a8a"))
            self.drawString(LEFT_MARGIN, PAGE_HEIGHT - 20, "CARDIOUNEMI · Cuestionario Clínico Cardiovascular")
            self.setFont("Helvetica", 7.3)
            self.setFillColor(colors.HexColor("#475569"))
            if self._is_blank:
                self.drawRightString(PAGE_WIDTH - RIGHT_MARGIN, PAGE_HEIGHT - 20, "Plantilla Oficial en Blanco")
            elif self._study_code:
                self.drawRightString(PAGE_WIDTH - RIGHT_MARGIN, PAGE_HEIGHT - 20, f"N.° Ficha Clínica: {self._study_code}")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.6)
            self.line(LEFT_MARGIN, PAGE_HEIGHT - 24, PAGE_WIDTH - RIGHT_MARGIN, PAGE_HEIGHT - 24)

        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(LEFT_MARGIN, 25, PAGE_WIDTH - RIGHT_MARGIN, 25)

        info_left = "Universidad Estatal de Milagro (UNEMI) · Departamento de Cardiología"
        if self._patient_info and not self._is_blank:
            info_left += f" · {self._patient_info}"
        self.drawString(LEFT_MARGIN, 14, info_left[:135])
        self.drawRightString(PAGE_WIDTH - RIGHT_MARGIN, 14, f"Página {self._pageNumber} de {page_count}")
        self.restoreState()


def clean_int_str(val_str):
    if val_str is None:
        return ""
    s = str(val_str).strip()
    if not s:
        return ""
    if re.match(r"^-?\d+\.\d+$", s):
        trimmed = s.rstrip("0").rstrip(".")
        return trimmed if trimmed not in {"", "-"} else "0"
    return s


def _fold_text(value: str) -> str:
    if not value:
        return ""
    norm = unicodedata.normalize("NFD", str(value))
    return "".join(ch for ch in norm if unicodedata.category(ch) != "Mn").lower().strip()


def _is_negative_boilerplate(value: str) -> bool:
    s = _fold_text(value)
    if not s:
        return True
    return s in {"no", "ninguna", "ninguno", "sin alteraciones", "0"} or s.startswith(
        ("no tiene", "no ha tenido", "no presenta", "no consume", "no realiza", "sin ")
    )


def _build_rose_torso_drawing() -> Drawing:
    """
    Compact, clean vector anatomical diagram of the 9 G. Rose chest pain zones,
    mirroring the SVG diagram in module_4_nocardio.html.
    """
    d = Drawing(140, 108)

    stroke_anatomy = colors.HexColor("#1e293b")
    stroke_guide = colors.HexColor("#64748b")
    accent_num = colors.HexColor("#0f172a")

    d.add(PolyLine([64, 96, 66, 90], strokeColor=stroke_anatomy, strokeWidth=1.1))
    d.add(PolyLine([76, 96, 74, 90], strokeColor=stroke_anatomy, strokeWidth=1.1))
    d.add(PolyLine([60, 98, 56, 89, 43, 81, 33, 71, 29, 53, 27, 14], strokeColor=stroke_anatomy, strokeWidth=1.2))
    d.add(PolyLine([80, 98, 84, 89, 97, 81, 107, 71, 111, 53, 113, 14], strokeColor=stroke_anatomy, strokeWidth=1.2))

    d.add(PolyLine([42, 56, 40, 34, 39, 14], strokeColor=stroke_anatomy, strokeWidth=1.1))
    d.add(PolyLine([98, 56, 100, 34, 101, 14], strokeColor=stroke_anatomy, strokeWidth=1.1))

    d.add(PolyLine([42, 56, 50, 51, 60, 56, 70, 59, 80, 56, 90, 51, 98, 56], strokeColor=stroke_anatomy, strokeWidth=1.0))
    d.add(PolyLine([50, 22, 60, 30, 70, 39, 80, 30, 90, 22], strokeColor=stroke_anatomy, strokeWidth=1.0))
    d.add(Circle(70, 81, 1.5, strokeColor=stroke_anatomy, fillColor=colors.white, strokeWidth=0.9))

    for x_pos, y_top in ((44, 73), (60, 96), (80, 96), (96, 73)):
        d.add(Line(x_pos, y_top, x_pos, 14, strokeColor=stroke_guide, strokeWidth=0.6, strokeDashArray=[2, 2]))
    d.add(Line(32, 20, 108, 20, strokeColor=stroke_guide, strokeWidth=0.6, strokeDashArray=[2, 2]))
    d.add(Line(42, 52, 98, 52, strokeColor=stroke_guide, strokeWidth=0.6, strokeDashArray=[2, 2]))

    d.add(String(14, 62, "Der.", fontName="Helvetica-Bold", fontSize=6.5, fillColor=colors.HexColor("#475569"), textAnchor="middle"))
    d.add(String(126, 62, "Izq.", fontName="Helvetica-Bold", fontSize=6.5, fillColor=colors.HexColor("#475569"), textAnchor="middle"))

    zone_coords = [
        ("1", 70, 86),
        ("2", 36, 61),
        ("3", 52, 64),
        ("4", 70, 64),
        ("5", 88, 64),
        ("6", 104, 61),
        ("7", 52, 35),
        ("8", 70, 35),
        ("9", 88, 35),
    ]
    for label, zx, zy in zone_coords:
        d.add(String(zx, zy, label, fontName="Helvetica-Bold", fontSize=7.5, fillColor=accent_num, textAnchor="middle"))

    return d


def generate_clinical_sheet_pdf(visit: Visit = None, is_blank: bool = False) -> bytes:
    """
    Generates the official UNEMI cardiovascular study clinical questionnaire PDF report.
    Mirrors 100% of the questions, module structure, item order, and 3-state clinical
    answers implemented in the web questionnaire (Modules 1 through 7).
    """
    from clinical.views import _build_form_datos

    W = 542  # Total table width in points (fits inside A4 with 26pt margins)

    buffer = io.BytesIO()

    if visit and not is_blank:
        datos = dict(_build_form_datos(visit.patient, visit))
        has_ecg_record = bool(getattr(visit, "electrocardiogram", None))
        has_ecg_ritmo_ans = (
            not has_ecg_record
            and hasattr(visit, "answers")
            and visit.answers.filter(question__code__iexact="ecg_ritmo")
            .exclude(text_value__isnull=True, numeric_value__isnull=True, selected_option__isnull=True)
            .exists()
        )
        if not has_ecg_record and not has_ecg_ritmo_ans:
            datos["ecg_ritmo"] = ""
    else:
        datos = {}
        is_blank = True if visit is None else is_blank

    study_code_header = ""
    patient_footer = ""
    if visit and not is_blank:
        study_code_header = str(datos.get("f_codigo") or visit.study_code or "").strip()
        full_nom = f"{datos.get('f_nombre', '')} {datos.get('f_apellido1', '')} {datos.get('f_apellido2', '')}".strip()
        ced = str(datos.get("f_cedula") or "").strip()
        patient_footer = f"{full_nom} ({ced})" if ced else full_nom

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=LEFT_MARGIN,
        rightMargin=RIGHT_MARGIN,
        topMargin=TOP_MARGIN,
        bottomMargin=BOTTOM_MARGIN,
        title=(
            "Cuestionario Clínico Cardiovascular UNEMI (Plantilla)"
            if is_blank
            else f"Cuestionario Clínico UNEMI - Ficha {study_code_header or 'S/N'}"
        ),
    )

    # -------------------------------------------------------------------------
    # Safe Data & Three-State Clinical Helpers
    # -------------------------------------------------------------------------
    def raw_val(*keys) -> str:
        if is_blank:
            return ""
        for k in keys:
            v = datos.get(k)
            if v is not None:
                cleaned = clean_int_str(v)
                if cleaned != "":
                    return cleaned
        return ""

    def val(*keys, default: str = "", suppress_if_no: bool = False) -> str:
        res = raw_val(*keys)
        if suppress_if_no and _is_negative_boilerplate(res):
            res = ""
        return xml_escape(res) if res != "" else xml_escape(default)

    def tri_bool(*keys):
        """
        Strict 3-state clinical boolean resolver:
          - True  -> Explicit affirmative ('Si', 'Sí', '1', 'True', 'Positivo', etc.)
          - False -> Explicit negative ('No', '0', 'False', 'Negativo', etc.)
          - None  -> Unanswered / NULL / blank template
        """
        if is_blank:
            return None
        for k in keys:
            raw = datos.get(k)
            if raw is None:
                continue
            s = _fold_text(raw)
            if not s:
                continue
            if (
                s in {"si", "true", "1", "1.0", "positivo", "presente", "on", "checked", "x", "s"}
                or re.match(r"^(si|true|1(\.0)?|positivo)\b", s)
            ):
                return True
            if (
                s in {"no", "false", "0", "0.0", "negativo", "ausente", "ninguno", "ninguna", "n"}
                or re.match(r"^(no|false|0(\.0)?|negativo|ningun[oa]?s?)\b", s)
                or s.startswith(("sin antecedentes", "sin patologia", "sin ingreso", "sin trastorno"))
            ):
                return False
        return None

    def chk(checked: bool) -> str:
        if checked:
            return '<b><font color="#0369a1">[X]</font></b>'
        return '<font color="#94a3b8">[&nbsp;&nbsp;&nbsp;]</font>'

    def yn_pair(*keys, no_label="No", yes_label="Sí", force_state=...) -> str:
        state = tri_bool(*keys) if force_state is ... else force_state
        c_no = chk(state is False)
        c_si = chk(state is True)
        no_esc = xml_escape(no_label).replace(" ", "&nbsp;")
        yes_esc = xml_escape(yes_label).replace(" ", "&nbsp;")
        lbl_no = f"<b>{no_esc}</b>" if state is False else no_esc
        lbl_si = f"<b>{yes_esc}</b>" if state is True else yes_esc
        return f"{c_no}&nbsp;{lbl_no} &nbsp;&nbsp; {c_si}&nbsp;{lbl_si}"

    def choice_boxes(value_str: str, options, exact=False, disabled=False) -> str:
        v_fold = "" if (is_blank or disabled) else _fold_text(value_str)
        parts = []
        for matcher, label in options:
            matched = False
            if v_fold:
                if callable(matcher):
                    matched = bool(matcher(v_fold))
                elif isinstance(matcher, (list, tuple, set)):
                    if exact:
                        matched = v_fold in {_fold_text(m) for m in matcher}
                    else:
                        matched = any(
                            v_fold == _fold_text(m) or _fold_text(m) in v_fold
                            for m in matcher
                        )
                else:
                    m_fold = _fold_text(matcher)
                    matched = (v_fold == m_fold) if exact else (v_fold == m_fold or m_fold in v_fold)
            lbl_esc = xml_escape(label)
            txt = f"<b>{lbl_esc}</b>" if matched else lbl_esc
            parts.append(f"{chk(matched)}&nbsp;{txt}")
        return " &nbsp;&nbsp; ".join(parts)

    def line_val(text_escaped: str, blank_spaces: int = 18, unit: str = "") -> str:
        suffix = f"&nbsp;<font color='#475569'>{xml_escape(unit)}</font>" if unit else ""
        if text_escaped:
            return f'<b><font color="#0f172a"><u>&nbsp;{text_escaped}&nbsp;</u></font></b>{suffix}'
        return f'<font color="#cbd5e1"><u>{"&nbsp;" * blank_spaces}</u></font>{suffix}'

    # -------------------------------------------------------------------------
    # Typography & Visual Styles
    # -------------------------------------------------------------------------
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11.5,
        leading=14,
        textColor=colors.HexColor("#0f172a"),
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.8,
        leading=10,
        textColor=colors.HexColor("#475569"),
    )
    mod_tag_style = ParagraphStyle(
        "ModTag",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.4,
        leading=11,
        textColor=colors.white,
        keepWithNext=True,
    )
    sec_banner_style = ParagraphStyle(
        "SecBanner",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.1,
        leading=10.5,
        textColor=colors.white,
        keepWithNext=True,
    )
    sub_hdr_style = ParagraphStyle(
        "SubHdr",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.6,
        textColor=colors.HexColor("#1e40af"),
    )
    q_style = ParagraphStyle(
        "QStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.45,
        leading=10.1,
        textColor=colors.HexColor("#1e293b"),
    )
    q_small = ParagraphStyle(
        "QSmall",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.05,
        leading=9.4,
        textColor=colors.HexColor("#334155"),
    )
    ans_right = ParagraphStyle(
        "AnsRight",
        parent=q_style,
        alignment=2,
    )

    elements = []

    def add_module_header(mod_num: str, mod_title: str):
        p = Paragraph(
            f'<font color="#93c5fd">{xml_escape(mod_num)}</font> &nbsp;&bull;&nbsp; {xml_escape(mod_title.upper())}',
            mod_tag_style,
        )
        t = Table([[p]], colWidths=[W], spaceBefore=3.5, spaceAfter=2.5)
        t.keepWithNext = True
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
                    ("TOPPADDING", (0, 0), (-1, -1), 3.8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3.8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        elements.append(t)

    def build_section_banner(badge: str, title_text: str) -> Table:
        p = Paragraph(
            f'<b><font color="#ffffff">{xml_escape(badge)}</font></b> &nbsp;&nbsp; '
            f'<b><font color="#ffffff">{xml_escape(title_text)}</font></b>',
            sec_banner_style,
        )
        t = Table([[p]], colWidths=[W])
        t.keepWithNext = True
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1b73bc")),
                    ("TOPPADDING", (0, 0), (-1, -1), 3.2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        return t

    def styled_grid_table(rows, col_widths, zebra=True, subheader_rows=None, highlight_rows=None) -> Table:
        subheader_rows = set(subheader_rows or [])
        highlight_rows = set(highlight_rows or [])
        t = Table(rows, colWidths=col_widths, splitByRow=1)
        cmds = [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.3),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("BOX", (0, 0), (-1, -1), 0.65, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
        ]
        for r_idx in range(len(rows)):
            if r_idx in subheader_rows:
                cmds.append(("SPAN", (0, r_idx), (-1, r_idx)))
                cmds.append(("BACKGROUND", (0, r_idx), (-1, r_idx), colors.HexColor("#eff6ff")))
                cmds.append(("TOPPADDING", (0, r_idx), (-1, r_idx), 2.8))
                cmds.append(("BOTTOMPADDING", (0, r_idx), (-1, r_idx), 2.8))
            elif r_idx in highlight_rows:
                cmds.append(("BACKGROUND", (0, r_idx), (-1, r_idx), colors.HexColor("#f0f9ff")))
            elif zebra and r_idx % 2 == 1:
                cmds.append(("BACKGROUND", (0, r_idx), (-1, r_idx), colors.HexColor("#f8fafc")))
            else:
                cmds.append(("BACKGROUND", (0, r_idx), (-1, r_idx), colors.white))
        t.setStyle(TableStyle(cmds))
        return t

    def add_section(badge: str, title_text: str, table_or_flowables, keep_together: bool = False):
        banner = build_section_banner(badge, title_text)
        items = table_or_flowables if isinstance(table_or_flowables, list) else [table_or_flowables]
        if keep_together:
            elements.append(KeepTogether([banner, *items]))
        else:
            elements.append(banner)
            for item in items:
                elements.append(item)
        elements.append(Spacer(1, 5))

    def subhdr_row(label: str, num_cols: int):
        row = [Paragraph(f"<b>{xml_escape(label.upper())}</b>", sub_hdr_style)]
        row.extend([""] * (num_cols - 1))
        return row

    def lab_cell(label: str, *keys, unit: str = "") -> Paragraph:
        v = val(*keys)
        return Paragraph(f"<b>{xml_escape(label)}:</b> {line_val(v, 9, unit)}", q_small)

    # =========================================================================
    # ENCABEZADO INSTITUCIONAL
    # =========================================================================
    logo_candidates = [
        "apps/clinical/static/clinical/images/unemi_logo.png",
        "static/assets/images/unemi_logo.png",
    ]
    logo_img = ""
    for lp in logo_candidates:
        if os.path.exists(lp):
            logo_img = Image(lp, width=84, height=36)
            break

    badge_status = (
        '<b><font color="#475569" size="8">PLANTILLA OFICIAL EN BLANCO</font></b>'
        if is_blank
        else f'<b><font color="#0369a1" size="8.5">FICHA CLÍNICA N.° {val("f_codigo", default="S/N")}</font></b>'
    )

    header_center = [
        Paragraph("CUESTIONARIO CLÍNICO CARDIOVASCULAR", title_style),
        Paragraph("Departamento de Cardiología · Vigilancia y Gestión de Historial Clínico", subtitle_style),
    ]
    header_right = [
        Paragraph(badge_status, ans_right),
        Paragraph(
            f'<font color="#64748b" size="7.2">Fecha visita: {line_val(val("f_fecha_visita"), 12)}</font>',
            ans_right,
        ),
    ]

    header_table = Table([[logo_img, header_center, header_right]], colWidths=[92, 300, 150])
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    elements.append(header_table)
    elements.append(
        HRFlowable(
            width="100%",
            thickness=1.4,
            color=colors.HexColor("#1b73bc"),
            spaceBefore=2,
            spaceAfter=4,
        )
    )

    # =========================================================================
    # MÓDULO 1: FICHA Y SOCIODEMOGRÁFICO
    # =========================================================================
    add_module_header("MÓDULO 1", "Ficha y Sociodemográfico")

    # --- 1.1 Datos del Individuo ---
    raw_nombres = raw_val("f_nombre")
    if raw_nombres:
        partes_nom = raw_nombres.split(None, 1)
        primer_nombre = xml_escape(partes_nom[0])
        segundo_nombre = xml_escape(partes_nom[1]) if len(partes_nom) > 1 else ""
    else:
        primer_nombre = ""
        segundo_nombre = ""

    estamento_boxes = choice_boxes(
        raw_val("f_estamento"),
        [
            (lambda s: s == "pdi" or "docente" in s or "profesor" in s, "PDI"),
            (lambda s: s in {"ad", "pas"} or "codigo de trabajo" in s or "admin" in s, "Código de Trabajo"),
            (lambda s: "servicio" in s or "auxiliar" in s, "SERVICIO"),
            (lambda s: "estudiante" in s or "alumno" in s, "ESTUDIANTES"),
        ],
    )

    rows_1_1 = [
        subhdr_row("Identificación Institucional", 4),
        [
            Paragraph(f"<b>Universidad:</b> {line_val(val('f_universidad'), 16)}", q_style),
            Paragraph(f"<b>Facultad de la Universidad:</b> {line_val(val('f_facultad'), 24)}", q_style),
            "",
            "",
        ],
        [
            Paragraph(f"<b>Estamento UNEMI:</b> &nbsp; {estamento_boxes}", q_style),
            "",
            "",
            "",
        ],
        [
            Paragraph(f"<b>&bull; N.° Ficha Clínica:</b> {line_val(val('f_codigo'), 10)}", q_style),
            Paragraph(f"<b>N.° de visita:</b> {line_val(val('f_visita'), 6)}", q_style),
            Paragraph(f"<b>Fecha visita:</b> {line_val(val('f_fecha_visita'), 14)}", q_style),
            "",
        ],
        subhdr_row("Identificación Personal, Residencia y Contacto", 4),
        [
            Paragraph(f"<b>1.- Primer nombre:</b><br/>{line_val(primer_nombre, 16)}", q_style),
            Paragraph(f"<b>- Segundo nombre:</b><br/>{line_val(segundo_nombre, 16)}", q_style),
            Paragraph(f"<b>- Primer apellido:</b><br/>{line_val(val('f_apellido1'), 16)}", q_style),
            Paragraph(f"<b>- Segundo apellido:</b><br/>{line_val(val('f_apellido2'), 16)}", q_style),
        ],
        [
            Paragraph(f"<b>- Provincia de residencia:</b> {line_val(val('f_provincia'), 18)}", q_style),
            "",
            Paragraph(f"<b>2.- Ciudad de residencia / Cantón:</b> {line_val(val('f_ciudad'), 18)}", q_style),
            "",
        ],
        [
            Paragraph(f"<b>- C.I. / Cédula:</b> {line_val(val('f_cedula'), 14)}", q_style),
            Paragraph(f"<b>3.- Teléfono (con prefijo):</b> {line_val(val('f_telefono'), 14)}", q_style),
            Paragraph(f"<b>4.- Correo electrónico:</b> {line_val(val('f_correo'), 24)}", q_style),
            "",
        ],
    ]
    t_1_1 = styled_grid_table(rows_1_1, [135, 136, 135, 136], subheader_rows={0, 4})
    t_1_1.setStyle(
        TableStyle(
            [
                ("SPAN", (1, 1), (3, 1)),
                ("SPAN", (0, 2), (3, 2)),
                ("SPAN", (2, 3), (3, 3)),
                ("SPAN", (0, 6), (1, 6)),
                ("SPAN", (2, 6), (3, 6)),
                ("SPAN", (2, 7), (3, 7)),
            ]
        )
    )
    add_section("1.1", "Datos del Individuo", t_1_1, keep_together=True)

    # --- 1.2 Cuestionario Sociodemográfico (Ítems 1 al 14 en orden exacto) ---
    sexo_boxes = choice_boxes(
        raw_val("f_sexo"),
        [
            (lambda s: s in {"h", "1", "hombre", "masculino"} or s.startswith("h"), "H (Hombre)"),
            (lambda s: s in {"m", "2", "mujer", "femenino"} or s.startswith(("m", "f")), "M (Mujer)"),
        ],
    )
    raza_boxes = choice_boxes(
        raw_val("f_raza"),
        [
            (lambda s: "mestiz" in s, "Mestizo/a"),
            (lambda s: "afro" in s or "african" in s, "Afroecuatoriano/a"),
            (lambda s: "blanc" in s, "Blanco/a"),
            (lambda s: "indig" in s, "Indígena"),
            (lambda s: "montub" in s or "montuv" in s, "Montubio/a"),
            (lambda s: "otra" in s or s == "otro", "Otra"),
        ],
    )
    ec_boxes = choice_boxes(
        raw_val("f_estado_civil"),
        [
            (lambda s: s in {"1", "1_soltero"} or "solter" in s, "1 Soltero/a"),
            (lambda s: s in {"2", "2_casado"} or "casad" in s, "2 Casado/a"),
            (lambda s: s in {"3", "3_divorciado"} or "divorc" in s or "separad" in s, "3 Divorciado/a o separado/a"),
            (lambda s: s in {"4", "4_viudo"} or "viud" in s, "4 Viudo/a"),
            (lambda s: s in {"5", "5_union_libre"} or "union" in s or "libre" in s or "conviv" in s, "5 Unión Libre / Conviviente"),
        ],
    )
    convive_boxes = choice_boxes(
        raw_val("f_convive_con"),
        [
            (lambda s: s == "1" or "solo" in s or "sola" in s, "1 Sólo/a"),
            (lambda s: s == "2" or s == "con su pareja" or s == "con pareja", "2 Con su pareja"),
            (lambda s: s == "3" or "pareja e hijo" in s, "3 Con su pareja e hijos"),
            (lambda s: s == "4" or s == "con sus hijos", "4 Con sus hijos"),
            (lambda s: s == "5" or "otros familiares" in s, "5 Con pareja, hijos y otros fam."),
            (lambda s: s == "6" or "padres" in s or "hermanos" in s, "6 Con padres y hermanos/as"),
            (lambda s: s == "7" or "no familiares" in s or "amigos" in s, "7 Con otros no familiares"),
        ],
    )
    estudios_boxes = choice_boxes(
        raw_val("f_estudios"),
        [
            (lambda s: s == "1" or "no sabe" in s or "analf" in s, "1 No sabe leer/escribir"),
            (lambda s: s == "2" or "preescolar" in s, "2 Preescolar"),
            (lambda s: s == "3" or "primari" in s, "3 Estudios Primarios"),
            (lambda s: s == "4" or "secundari" in s, "4 Estudios secundarios"),
            (lambda s: s == "5" or "post-bachiller" in s or "bachiller" in s, "5 Ciclo post-bachillerato"),
            (lambda s: s == "6" or "superior" in s or "tercer" in s or "grado" in s, "6 Estudios superiores"),
            (lambda s: s == "7" or "postgrad" in s or "posgrad" in s or "cuarto" in s or "phd" in s, "7 Postgrado"),
        ],
    )
    horario_boxes = choice_boxes(
        raw_val("f_horario"),
        [
            (lambda s: s == "1" or "partida" in s, "1 Jornada partida (Mañana/tarde)"),
            (lambda s: s == "2" or ("continua" in s and "manana" in s), "2 Jornada continua (mañanas y tarde)"),
            (lambda s: s == "3" or ("continua" in s and "tarde" in s), "3 Jornada continua en tardes"),
            (lambda s: s == "4" or "rotativ" in s or "turno" in s, "4 Turnos rotativos"),
        ],
    )
    profesion_boxes = choice_boxes(
        raw_val("f_profesion"),
        [
            (lambda s: s == "1" or "profesor permanente" in s or "titular" in s, "1 Profesor permanente"),
            (lambda s: s == "2" or "no permanente" in s or "ocasional" in s, "2 Profesor no permanente"),
            (lambda s: s == "3" or "administra" in s or "servidor" in s, "3 Personal de administración"),
            (lambda s: s == "4" or "servicio" in s or "auxiliar" in s, "4 Personal de servicios"),
            (lambda s: s == "5" or "otra" in s or s == "otro", "5 Otra categoría"),
            (lambda s: s == "6" or "estudiante" in s, "6 Estudiante"),
            (lambda s: s == "7" or "jubilad" in s, "7 Jubilado"),
        ],
    )
    vivienda_boxes = choice_boxes(
        raw_val("f_vivienda"),
        [
            (lambda s: s == "1" or "propi" in s, "1 Propia"),
            (lambda s: s == "2" or "alquil" in s or "arrend" in s, "2 Alquilada"),
            (lambda s: s == "3" or "familiar" in s, "3 Vivienda familiar"),
            (lambda s: s == "4" or "otro" in s or "presta" in s, "4 Otro"),
        ],
    )
    ingresos_boxes = choice_boxes(
        raw_val("f_ingresos"),
        [
            (lambda s: s == "1" or "menos de 500" in s or "<500" in s, "1 (<500 $/mes)"),
            (lambda s: s == "2" or "500-1" in s or "500 - 1" in s, "2 (500-1.000 $)"),
            (lambda s: s == "3" or "1001-1500" in s, "3 (1001-1500 $)"),
            (lambda s: s == "4" or "1501" in s, "4 (1501-2000 $)"),
            (lambda s: s == "5" or "2001" in s, "5 (2001-2500 $)"),
            (lambda s: s == "6" or "2501" in s, "6 (2501-3000 $)"),
            (lambda s: s == "7" or "3001" in s, "7 (3001-3500 $)"),
            (lambda s: s == "8" or "otra" in s, "8 (Otras)"),
        ],
    )

    rows_1_2 = [
        [
            Paragraph(f"<b>Provincia de nacimiento:</b> {line_val(val('f_provincia_nac'), 14)}", q_style),
            Paragraph(f"<b>1.- Lugar nac. Municipio / Cantón:</b> {line_val(val('f_municipio'), 14)}", q_style),
            Paragraph(f"<b>- País de nacimiento:</b> {line_val(val('f_pais_nac'), 12)}", q_style),
        ],
        [
            Paragraph(f"<b>2.- Fecha de nacimiento:</b> {line_val(val('f_fecha_nac'), 12)}", q_style),
            Paragraph(f"<b>3.- Edad:</b> {line_val(val('f_edad'), 5, 'años')}", q_style),
            Paragraph(f"<b>4.- Sexo:</b> &nbsp; {sexo_boxes}", q_style),
        ],
        [
            Paragraph(f"<b>5.- Raza:</b> &nbsp; {raza_boxes}", q_style),
            "",
            "",
        ],
        [
            Paragraph(f"<b>6.- Estado Civil:</b> &nbsp; {ec_boxes}", q_style),
            "",
            Paragraph(f"<b>7.- ¿Cuántos hijos tiene?:</b> {line_val(val('f_hijos'), 6)}", q_style),
        ],
        [
            Paragraph(f"<b>8.- ¿Con quién vive usted ahora?:</b> &nbsp; {convive_boxes}", q_style),
            "",
            Paragraph(f"<b>9.- Personas convivientes:</b> {line_val(val('f_convivientes'), 6)}", q_style),
        ],
        [
            Paragraph(f"<b>10.- Mayor nivel de estudios:</b> &nbsp; {estudios_boxes}", q_style),
            "",
            "",
        ],
        [
            Paragraph(f"<b>11.- Horario laboral:</b> &nbsp; {horario_boxes}", q_style),
            "",
            "",
        ],
        [
            Paragraph(f"<b>12.- Categoría profesión:</b> &nbsp; {profesion_boxes}", q_style),
            "",
            "",
        ],
        [
            Paragraph(f"<b>13.- Su vivienda es:</b> &nbsp; {vivienda_boxes}", q_style),
            "",
            "",
        ],
        [
            Paragraph(f"<b>14.- Ingresos totales familia (dólares/mes):</b> &nbsp; {ingresos_boxes}", q_style),
            "",
            "",
        ],
    ]
    t_1_2 = styled_grid_table(rows_1_2, [180, 182, 180])
    t_1_2.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 2), (2, 2)),
                ("SPAN", (0, 3), (1, 3)),
                ("SPAN", (0, 4), (1, 4)),
                ("SPAN", (0, 5), (2, 5)),
                ("SPAN", (0, 6), (2, 6)),
                ("SPAN", (0, 7), (2, 7)),
                ("SPAN", (0, 8), (2, 8)),
                ("SPAN", (0, 9), (2, 9)),
            ]
        )
    )
    add_section("1.2", "Cuestionario Sociodemográfico", t_1_2)

    # =========================================================================
    # MÓDULO 2: EXPLORACIÓN Y SIGNOS
    # =========================================================================
    add_module_header("MÓDULO 2", "Exploración y Signos")

    soplos_state = tri_bool("soplos", "soplos_cardiacos")
    soplo_grado_val = val("soplo_grado", "f_grado_soplo", suppress_if_no=(soplos_state is False))
    soplo_tipo_val = val("soplo_tipo", suppress_if_no=(soplos_state is False))

    rows_2_1 = [
        subhdr_row("Medidas Corporales y Constantes Vitales", 4),
        [
            Paragraph(f"<b>1.- Peso:</b> {line_val(val('f_peso', 'peso_kg'), 8, 'kg')}", q_style),
            Paragraph(f"<b>2.- Talla:</b> {line_val(val('f_talla', 'talla_cm'), 8, 'cm')}", q_style),
            Paragraph(f"<b>3.- IMC:</b> {line_val(val('f_imc', 'imc_kgm2'), 8, 'kg/m²')}", q_style),
            Paragraph(f"<b>4.- ASC:</b> {line_val(val('f_asc', 'asc_m2'), 8, 'm²')}", q_style),
        ],
        [
            Paragraph(f"<b>5.- Perímetro Abdominal:</b> {line_val(val('f_perimetro', 'perimetro_abdominal_cm'), 7, 'cm')}", q_style),
            Paragraph(f"<b>6.- Saturación O2:</b> {line_val(val('f_sat_o2', 'saturacion_o2'), 6, '%')}", q_style),
            Paragraph(f"<b>7.- TAS - Sistólica:</b> {line_val(val('f_tas', 'tas_ts'), 6, 'mm Hg')}", q_style),
            Paragraph(f"<b>7.- TSI - Diastólica:</b> {line_val(val('f_tsi', 'tas_mmhg', 'tad_mmhg'), 6, 'mm Hg')}", q_style),
        ],
        subhdr_row("Hallazgos Físicos", 4),
        [
            Paragraph(f"<b>8.- Soplos cardiacos:</b> &nbsp; {yn_pair(force_state=soplos_state)}", q_style),
            "",
            Paragraph(
                f"<b>9. Grado:</b> {line_val(soplo_grado_val, 8)} &nbsp;&nbsp;&nbsp; "
                f"<b>Tipo:</b> {line_val(soplo_tipo_val, 16)}",
                q_style,
            ),
            "",
        ],
        [
            Paragraph(f"<b>10.- Extra-tonos:</b> &nbsp; {yn_pair('extratonos', 'extratono_sino_tipo')}", q_style),
            "",
            Paragraph(f"<b>Cuál:</b> {line_val(val('extratonos_detalle', suppress_if_no=True), 26)}", q_style),
            "",
        ],
        [
            Paragraph(f"<b>11.- Pulsos pedios palpables:</b> &nbsp; {yn_pair('pulsos_palp', 'pulsospedios')}", q_style),
            "",
            Paragraph(f"<b>simétricos:</b> &nbsp; {yn_pair('pulsos_sim', 'f_pulsos_pedios')}", q_style),
            "",
        ],
        [
            Paragraph(f"<b>12.- Exploración respiratoria normal:</b> &nbsp; {yn_pair('resp_norm', 'exploracion_respiratoria')}", q_style),
            "",
            Paragraph(
                f"<b>Existe Estertores:</b> {yn_pair('estert')} &nbsp;&nbsp; "
                f"<b>sibilancias:</b> {yn_pair('sibil')}",
                q_style,
            ),
            "",
        ],
        [
            Paragraph(f"<b>13.- Exploración abdominal normal:</b> &nbsp; {yn_pair('abdom_norm', 'exploracion_abdominal')}", q_style),
            "",
            Paragraph(
                f"{chk(tri_bool('hepatomegalia') is True)}&nbsp;Tiene hepatomegalia &nbsp;&nbsp; "
                f"{chk(tri_bool('organomegalia') is True)}&nbsp;Tiene organomegalia<br/>"
                f"<b>Otras Cuáles:</b> {line_val(val('abd_alteracion_detalle', suppress_if_no=True), 22)}",
                q_style,
            ),
            "",
        ],
    ]
    t_2_1 = styled_grid_table(rows_2_1, [135, 136, 135, 136], subheader_rows={0, 3})
    for r_i in range(4, 9):
        t_2_1.setStyle(TableStyle([("SPAN", (0, r_i), (1, r_i)), ("SPAN", (2, r_i), (3, r_i))]))
    add_section("2.1", "Exploración Física", t_2_1)

    # =========================================================================
    # MÓDULO 3: RIESGO E HISTORIA CARDIOVASCULAR
    # =========================================================================
    add_module_header("MÓDULO 3", "Riesgo e Historia Cardio")

    # --- 3.1 Factores de Riesgo Modificables (Ítems 1 al 21 en orden exacto) ---
    hta_state = tri_bool("r_hta", "hipertension")
    hta_trat_state = None
    if hta_state is not False and not is_blank:
        hta_trat_state = tri_bool("r_hta_trat", "r_hta_farmacos", "hta_tto")
        if hta_trat_state is None:
            h_txt = _fold_text(raw_val("hipertension"))
            if "no tratada" in h_txt:
                hta_trat_state = False
            elif "tratada" in h_txt:
                hta_trat_state = True
    hta_trat_str = yn_pair(no_label="No tratada", yes_label="Sí tratada", force_state=hta_trat_state)

    mapa_state = tri_bool("r_mapa", "prueba_mapa", "mapa")
    mapa_res_boxes = choice_boxes(
        raw_val("mapa_resultado", "resultado_mapa", "mapa_alt"),
        [(lambda s: "normal" in s, "Normal"), (lambda s: "alterad" in s or s in {"si", "1"}, "Alterada")],
        disabled=(mapa_state is False),
    )

    dm_state = tri_bool("r_dm", "diabetes_mellitus")
    dislip_state = tri_bool("r_dislip", "dislipemia", "dislipidemia")
    dislip_trat_state = None if dislip_state is False else tri_bool("r_dislip_trat", "r_dislip_farmacos", "dlp_tto")
    dislip_trat_str = yn_pair(
        no_label="No tratada con fármacos",
        yes_label="Sí tratada con fármacos",
        force_state=dislip_trat_state,
    )

    # Obesidad y Sobrepeso (soportando peso_corporal de SPSS además de radios directos)
    peso_corp_fold = _fold_text(raw_val("peso_corporal"))
    obesidad_state = tri_bool("r_obesidad")
    if obesidad_state is None and peso_corp_fold:
        if "obesidad" in peso_corp_fold and "no " not in peso_corp_fold:
            obesidad_state = True
        elif "no tiene" in peso_corp_fold or "normopeso" in peso_corp_fold or "sobrepeso" in peso_corp_fold:
            obesidad_state = False
    obesidad_grado_str = val("obesidad_grado")
    if not obesidad_grado_str and obesidad_state is True and "obesidad" in peso_corp_fold:
        obesidad_grado_str = val("peso_corporal")

    sobrepeso_state = tri_bool("r_sobrepeso")
    if sobrepeso_state is None and not is_blank:
        sp_raw_fold = _fold_text(raw_val("r_sobrepeso", "peso_corporal"))
        if sp_raw_fold:
            if "no " in sp_raw_fold or "normopeso" in sp_raw_fold or ("obesidad" in sp_raw_fold and "sobrepeso" not in sp_raw_fold):
                sobrepeso_state = False
            elif "sobrepeso" in sp_raw_fold:
                sobrepeso_state = True

    arr_state = tri_bool("r_arritmias", "arritmias")
    sinc_state = tri_bool("r_sincopes", "sincopes")
    holter_state = tri_bool("r_holter", "prueba_holter", "holter")
    holter_res_boxes = choice_boxes(
        raw_val("holter_resultado", "resultado_holter"),
        [(lambda s: "normal" in s, "Normal"), (lambda s: "alterad" in s, "Alterada")],
        disabled=(holter_state is False),
    )

    irc_state = tri_bool("r_irc", "insuf_renal_cronica")
    irc_tipo_boxes = choice_boxes(
        raw_val("r_irc_tipo"),
        [(lambda s: "dialisis" in s, "Diálisis"), (lambda s: "trasplante" in s, "Trasplante renal")],
        disabled=(irc_state is False),
    )

    rows_3_1 = [
        [
            Paragraph(f"<b>&bull; 1.- Hipertensión:</b> &nbsp; {yn_pair(force_state=hta_state)}", q_style),
            Paragraph(
                f"{hta_trat_str}<br/><b>Cuáles medicamentos:</b> {line_val(val('hta_medicamentos', suppress_if_no=True), 22)}",
                q_style,
            ),
        ],
        [
            Paragraph(f"<b>2.- Prueba de MAPA:</b> &nbsp; {yn_pair(force_state=mapa_state)}", q_style),
            Paragraph(f"<b>Resultado:</b> &nbsp; {mapa_res_boxes}", q_style),
        ],
        [
            Paragraph(f"<b>3.- Diabetes mellitus:</b> &nbsp; {yn_pair(force_state=dm_state)}", q_style),
            Paragraph(
                f"<b>Clasificación:</b> {line_val(val('dm_clasificacion', suppress_if_no=(dm_state is False)), 20)} &nbsp;&nbsp; "
                f"<b>Fármacos:</b> {line_val(val('dm_farmacos', suppress_if_no=True), 14)}",
                q_style,
            ),
        ],
        [
            Paragraph(f"<b>4.- Dislipemia:</b> &nbsp; {yn_pair(force_state=dislip_state)}", q_style),
            Paragraph(
                f"{dislip_trat_str}<br/>"
                f"<b>Tipo:</b> {line_val(val('dislip_tipo', 'dislipemia_tipo', suppress_if_no=(dislip_state is False)), 12)} &nbsp;&nbsp; "
                f"<b>Cuáles:</b> {line_val(val('dislip_farmacos', 'dislipemia_farmacos_cual', suppress_if_no=True), 14)}",
                q_style,
            ),
        ],
        [
            Paragraph(f"<b>5.- Tabaquismo:</b> &nbsp; {yn_pair('r_tabaco', 'tabaquismo')}", q_style),
            Paragraph(
                f"<b>Frecuencia:</b> {line_val(val('tabaco_frecuencia', suppress_if_no=True), 14)} &nbsp;&nbsp; "
                f"<b>Cantidad:</b> {line_val(val('tabaco_cantidad'), 5)} &nbsp;&nbsp; "
                f"{chk(tri_bool('chk_exfumador') is True or 'exfumador' in _fold_text(raw_val('tabaquismo')))}&nbsp;Exfumador &gt; 1 año",
                q_style,
            ),
        ],
        [
            Paragraph(f"<b>6.- Alcohol:</b> &nbsp; {yn_pair('r_alcohol', 'alcohol')}", q_style),
            Paragraph(
                f"<b>Frecuencia:</b> {line_val(val('alcohol_frecuencia', suppress_if_no=True), 14)} &nbsp;&nbsp; "
                f"{chk(tri_bool('chk_ex_alcohol') is True)}&nbsp;Ex tomador &gt; 1 año &nbsp;&nbsp; "
                f"<b>Unidades:</b> {line_val(val('alcohol_unidades'), 5)}",
                q_style,
            ),
        ],
        [
            Paragraph(f"<b>7.- Drogas:</b> &nbsp; {yn_pair('r_drogas', 'drogas')}", q_style),
            Paragraph(
                f"<b>Cuáles:</b> {line_val(val('drogas_cuales', suppress_if_no=True), 12)} &nbsp;&nbsp; "
                f"<b>Frecuencia:</b> {line_val(val('drogas_frecuencia', suppress_if_no=True), 12)} &nbsp;&nbsp; "
                f"{chk(tri_bool('chk_ex_drogas') is True)}&nbsp;Ex consumidor &gt; 1 año<br/>"
                f"<b>Dosis diaria:</b> {line_val(val('drogas_dosis_diaria'), 7)} &nbsp; "
                f"<b>Dosis semanal:</b> {line_val(val('drogas_dosis_semanal'), 7)} &nbsp; "
                f"<b>Dosis ocasional:</b> {line_val(val('drogas_dosis_ocasional'), 7)}",
                q_style,
            ),
        ],
        [
            Paragraph(f"<b>8.- Obesidad:</b> &nbsp; {yn_pair(force_state=obesidad_state)}", q_style),
            Paragraph(f"<b>Grado según base:</b> {line_val(obesidad_grado_str, 22)}", q_style),
        ],
        [
            Paragraph(f"<b>9.- Sobrepeso:</b> &nbsp; {yn_pair(force_state=sobrepeso_state)}", q_style),
            Paragraph("", q_style),
        ],
        [
            Paragraph(f"<b>10.- Arritmias:</b> &nbsp; {yn_pair(force_state=arr_state)}", q_style),
            Paragraph(f"<b>Tipo de arritmia:</b> {line_val(val('arritmias_tipo', suppress_if_no=True), 22)}", q_style),
        ],
        [
            Paragraph(f"<b>11.- Síncopes:</b> &nbsp; {yn_pair(force_state=sinc_state)}", q_style),
            Paragraph(f"<b>Tipo de síncope:</b> {line_val(val('sincopes_tipo', suppress_if_no=True), 22)}", q_style),
        ],
        [
            Paragraph(
                f"<b>12.- Prueba de Holter</b> <font size='6.8' color='#64748b'>(Arritmias y/o síncope 24h)</font>:<br/>"
                f"{yn_pair(force_state=holter_state)}",
                q_style,
            ),
            Paragraph(f"<b>Resultado:</b> &nbsp; {holter_res_boxes}", q_style),
        ],
        [
            Paragraph(
                f"<b>13.- Vasculopatía periférica:</b> &nbsp; {yn_pair('r_vasc_perif')}<br/>"
                f"<b>14.- Vasculopatía carotídea:</b> &nbsp; {yn_pair('r_vasc_carot')}",
                q_style,
            ),
            Paragraph(f"<b>15.- Vasculopatía femoral:</b> &nbsp; {yn_pair('r_vasc_fem', 'r_vasc_femoral', 'vasculopatia_femoral')}", q_style),
        ],
        [
            Paragraph(f"<b>16.- Insuficiencia renal crónica:</b> &nbsp; {yn_pair(force_state=irc_state)}", q_style),
            Paragraph(f"{irc_tipo_boxes}", q_style),
        ],
        [
            Paragraph(f"<b>17.- Antecedentes ictus/AIT:</b> &nbsp; {yn_pair('r_ictus', 'antecedentrs_ictus')}", q_style),
            Paragraph(f"<b>18.- Disfunción eréctil:</b> &nbsp; {yn_pair('r_disfunc', 'disfuncion_erectil')}", q_style),
        ],
        [
            Paragraph(f"<b>19.- Hígado graso:</b> &nbsp; {yn_pair('r_higado', 'higado_graso')}", q_style),
            Paragraph(f"<b>20.- Apnea del sueño:</b> &nbsp; {yn_pair('r_apnea', 'apnea_sueno')}", q_style),
        ],
        [
            Paragraph(f"<b>21.- Otros:</b> &nbsp; {yn_pair('r_otros')}", q_style),
            Paragraph(f"<b>Cuáles:</b> {line_val(val('otros_factores_detalle', suppress_if_no=True), 26)}", q_style),
        ],
    ]
    t_3_1 = styled_grid_table(rows_3_1, [225, 317])
    add_section("3.1", "Factores de Riesgo Modificables", t_3_1)

    # --- 3.2 Factores Emergentes (Ítems 1 al 9 en orden exacto) ---
    sueno_opts = [
        (lambda s: "buen" in s, "Buena"),
        (lambda s: "regul" in s, "Regular"),
        (lambda s: "mal" in s, "Mala"),
    ]
    estrog_txt = _fold_text(raw_val("bajos_estrogenos", "em_estrogenos"))
    is_menopausia = (not is_blank) and (tri_bool("em_estrogenos_menopausia") is True or "menopausia" in estrog_txt)
    is_estrog_otras = (not is_blank) and (tri_bool("em_estrogenos_otras") is True or "otras causas" in estrog_txt)

    rows_3_2 = [
        [
            Paragraph(f"<b>1.- Cantidad de sueño:</b> &nbsp; {choice_boxes(raw_val('sueno_cantidad', 'cantidad_sueno'), sueno_opts)}", q_style),
            Paragraph(f"<b>2.- Calidad del sueño:</b> &nbsp; {choice_boxes(raw_val('sueno_calidad', 'calidad_sueno'), sueno_opts)}", q_style),
        ],
        [
            Paragraph(f"<b>3.- Trabaja con tóxicos:</b> &nbsp; {yn_pair('em_toxicos', 'trabaja_con_toxicos')}", q_style),
            Paragraph(f"<b>Cuáles:</b> {line_val(val('toxicos_cuales', 'trabaja_con_toxicos_cuales', suppress_if_no=True), 24)}", q_style),
        ],
        [
            Paragraph(f"<b>4.- Niveles bajos de estrógenos en la mujer:</b> &nbsp; {yn_pair('em_estrogenos', 'bajos_estrogenos')}", q_style),
            Paragraph(
                f"{chk(is_menopausia)}&nbsp;menopausia &nbsp;&nbsp;&nbsp; "
                f"{chk(is_estrog_otras)}&nbsp;Otras causas",
                q_style,
            ),
        ],
        [
            Paragraph(f"<b>5.- Usa anticonceptivo &gt;35 años:</b> &nbsp; {yn_pair('em_anticonceptivos', 'proteccion_anticonceptivo')}", q_style),
            Paragraph(f"<b>6.- Tiene estrés en el trabajo:</b> &nbsp; {yn_pair('em_estres_trab')}", q_style),
        ],
        [
            Paragraph(f"<b>7.- Tiene estrés en la vida familiar:</b> &nbsp; {yn_pair('em_estres_fam')}", q_style),
            Paragraph(f"<b>8.- Mal ambiente laboral:</b> &nbsp; {yn_pair('em_mal_amb', 'mal_ambiente_laboral')}", q_style),
        ],
        [
            Paragraph(f"<b>9.- Personalidad tipo A:</b> &nbsp; {yn_pair('em_pers_a', 'personalidad_tipo_a')}", q_style),
            Paragraph(
                f"<b>Características conductuales:</b><br/>"
                f"{chk(tri_bool('em_exigente', 'exigente') is True)}&nbsp;Exigente con uno mismo y con los demás &nbsp;&nbsp; "
                f"{chk(tri_bool('em_perfeccionista', 'perfeccionista') is True)}&nbsp;Perfeccionista<br/>"
                f"{chk(tri_bool('em_hiperactivo', 'hiperactivo') is True)}&nbsp;Hiperactivo en la consecución de logros &nbsp;&nbsp; "
                f"{chk(tri_bool('em_ambicioso', 'ambicioso') is True)}&nbsp;Ambicioso<br/>"
                f"{chk(tri_bool('em_hostilidad', 'hostilidad') is True)}&nbsp;Hostilidad (impaciente, opositor, impulsivo) &nbsp;&nbsp; "
                f"{chk(tri_bool('em_aislamiento', 'aislamiento_social') is True)}&nbsp;Aislamiento social",
                q_small,
            ),
        ],
    ]
    t_3_2 = styled_grid_table(rows_3_2, [255, 287])
    add_section("3.2", "Factores Emergentes", t_3_2)

    # --- 3.3 Otros Factores de Riesgo No Modificables (Ítems 1 y 2) ---
    rows_3_3 = [
        [
            Paragraph(
                "<b>1.- Antecedentes familiares de cardiopatía Isquémica</b> "
                "<font size='6.8' color='#64748b'>(Angina, infarto, muerte súbita)</font>:",
                q_style,
            ),
            Paragraph(yn_pair("nm_cardiopatia", "factores_tiesgo_cardiopatia"), ans_right),
        ],
        [
            Paragraph(
                "<b>2.- Algún familiar directo ha fallecido por cardiopatía Isquémica</b> "
                "<font size='6.8' color='#64748b'>(&lt;55v / &lt;65m)</font>:",
                q_style,
            ),
            Paragraph(yn_pair("nm_fallecido", "af_muerte_subita"), ans_right),
        ],
    ]
    t_3_3 = styled_grid_table(rows_3_3, [420, 122])
    add_section("3.3", "Otros Factores de Riesgo No Modificables", t_3_3, keep_together=True)

    # --- 3.4 Antecedentes Familiares (Ítems 1, 2 y 3) ---
    rows_3_4 = [
        [
            Paragraph(
                f"<b>1.- Padre con:</b> &nbsp;&nbsp; "
                f"{chk(tri_bool('ant_padre_hta', 'af_padre_hta', 'padre_hta') is True)}&nbsp;HTA &nbsp;&nbsp; "
                f"{chk(tri_bool('ant_padre_dm', 'af_padre_dm', 'padre_dm') is True)}&nbsp;Diabetes &nbsp;&nbsp; "
                f"{chk(tri_bool('ant_padre_dislip', 'af_padre_dlp', 'padre_dlp') is True)}&nbsp;Dislipemia",
                q_style,
            ),
            Paragraph(
                f"<b>2.- Madre con:</b> &nbsp;&nbsp; "
                f"{chk(tri_bool('ant_madre_hta', 'af_madre_hta', 'madre_hta') is True)}&nbsp;HTA &nbsp;&nbsp; "
                f"{chk(tri_bool('ant_madre_dm', 'af_madre_dm', 'madre_dm') is True)}&nbsp;Diabetes &nbsp;&nbsp; "
                f"{chk(tri_bool('ant_madre_dislip', 'af_madre_dlp', 'madre_dlp') is True)}&nbsp;Dislipemia",
                q_style,
            ),
        ],
        [
            Paragraph(f"<b>3.- Otras enfermedades:</b> &nbsp; {yn_pair('ant_otras_tog')}", q_style),
            Paragraph(f"<b>¿Cuáles enfermedades familiares?:</b> {line_val(val('ant_familiares_cuales', suppress_if_no=True), 20)}", q_style),
        ],
    ]
    t_3_4 = styled_grid_table(rows_3_4, [271, 271])
    add_section("3.4", "Antecedentes Familiares", t_3_4, keep_together=True)

    # --- 3.5 Historia Clínica Actual Cardiovascular (Ítems 1 al 6 en orden exacto) ---
    revasc_state = tri_bool("hc_revasc", "revascularizacion_coronaria")
    revasc_boxes = choice_boxes(
        raw_val("hc_revasc_tipo", "revascularizacion_tipo"),
        [
            (lambda s: "angioplastia" in s, "Con angioplastia"),
            (lambda s: "bypass" in s, "Con Bypass"),
            (lambda s: "ambas" in s, "Con ambas"),
        ],
        disabled=(revasc_state is False),
    )
    rows_3_5 = [
        [
            Paragraph(f"<b>1.- Historia de cualquier problema del corazón:</b> &nbsp; {yn_pair('hc_prob', 'problema_corazon')}", q_style),
            Paragraph(f"<b>Cuáles:</b> {line_val(val('prob_corazon_detalle', 'problema_corazon_detalle', suppress_if_no=True), 22)}", q_style),
        ],
        [
            Paragraph(f"<b>2.- Cardiopatía isquémica:</b> &nbsp; {yn_pair('hc_isquemica', 'cardiopatia_isquemica')}", q_style),
            Paragraph(
                f"{chk(tri_bool('hc_isquemica_angina') is True)}&nbsp;Angina &nbsp;&nbsp;&nbsp; "
                f"{chk(tri_bool('hc_isquemica_infarto') is True)}&nbsp;Infarto de miocardio",
                q_style,
            ),
        ],
        [
            Paragraph(f"<b>3.- Revascularización coronaria:</b> &nbsp; {yn_pair(force_state=revasc_state)}", q_style),
            Paragraph(revasc_boxes, q_style),
        ],
        [
            Paragraph(f"<b>4.- Historia de Insuficiencia cardiaca:</b> &nbsp; {yn_pair('hc_insuf_cardiaca', 'insuficiencia_cardiaca')}", q_style),
            Paragraph("", q_style),
        ],
        [
            Paragraph(f"<b>5.- Historia de valvulopatía:</b> &nbsp; {yn_pair('hc_valvulopatia', 'valvulopatia')}", q_style),
            Paragraph(
                f"<b>¿Cuáles?:</b> {line_val(val('hc_valvulopatia_cuales', 'valvulopatia_cuales', suppress_if_no=True), 14)}<br/>"
                f"<b>Operado por este motivo:</b> &nbsp; {yn_pair('hc_valvulopatia_operado', 'valvulopatia_operado')}",
                q_style,
            ),
        ],
        [
            Paragraph(
                f"<b>6.- Ha estado ingresado en el hospital por algún problema cardiaco:</b><br/>"
                f"{yn_pair('hc_ingresado', 'ingreso_hospitalario_cardiaco')}",
                q_style,
            ),
            Paragraph(f"<b>¿Cuál?:</b> {line_val(val('hc_ingresado_cual', 'ingreso_hospitalario_motivo', suppress_if_no=True), 22)}", q_style),
        ],
    ]
    t_3_5 = styled_grid_table(rows_3_5, [275, 267])
    add_section("3.5", "Historia Clínica Actual Cardiovascular", t_3_5)

    # =========================================================================
    # MÓDULO 4: NO CARDIO Y CUESTIONARIOS
    # =========================================================================
    add_module_header("MÓDULO 4", "No Cardio y Cuestionarios")

    # --- 4.1 Historia Clínica No Cardiovascular (Ítems 1 al 8 en orden exacto) ---
    rows_4_1 = [
        [
            Paragraph(f"<b>1.- Enfermedad reumatológica/inmunológica:</b> &nbsp; {yn_pair('nc_reuma', 'enfermedad_reumatologicas')}", q_style),
            Paragraph(f"<b>Cuáles:</b> {line_val(val('reuma_detalle', 'cual_enferm_reumatologica', suppress_if_no=True), 22)}", q_style),
        ],
        [
            Paragraph(f"<b>2.- Historia de cáncer:</b> &nbsp; {yn_pair('nc_cancer', 'historia_cancer')}", q_style),
            Paragraph(
                f"<b>Tipo de cáncer:</b> "
                f"{chk(tri_bool('cancer_pulmon') is True)}&nbsp;Pulmón &nbsp; "
                f"{chk(tri_bool('cancer_prostata') is True)}&nbsp;Próstata &nbsp; "
                f"{chk(tri_bool('cancer_colon') is True)}&nbsp;Colon &nbsp; "
                f"{chk(tri_bool('cancer_mama') is True)}&nbsp;Mama<br/>"
                f"{chk(tri_bool('cancer_vejiga') is True)}&nbsp;Vejiga &nbsp; "
                f"{chk(tri_bool('cancer_utero') is True)}&nbsp;Útero &nbsp; "
                f"{chk(tri_bool('cancer_ovario') is True)}&nbsp;Ovario &nbsp; "
                f"{chk(tri_bool('cancer_otro') is True)}&nbsp;Otro: {line_val(val('cancer_otro_detalle'), 10)}<br/>"
                f"<b>¿Recibió Qt?:</b> {yn_pair('cancer_qt', 'cancer_quimioterapia')} &nbsp;&nbsp;&nbsp; "
                f"<b>¿Recibió RT?:</b> {yn_pair('cancer_rt', 'cancer_radioterapia')}",
                q_small,
            ),
        ],
        [
            Paragraph(f"<b>3.- EPOC:</b> &nbsp; {yn_pair('nc_epoc')}", q_style),
            Paragraph(f"<b>4.- Asma:</b> &nbsp; {yn_pair('nc_asma')}", q_style),
        ],
        [
            Paragraph(f"<b>5.- Depresión:</b> &nbsp; {yn_pair('nc_depresion')}", q_style),
            Paragraph(f"<b>6.- Ansiedad:</b> &nbsp; {yn_pair('nc_ansiedad')}", q_style),
        ],
        [
            Paragraph(f"<b>7.- Alergia a medicamentos:</b> &nbsp; {yn_pair('nc_alergia', 'alergias')}", q_style),
            Paragraph(f"<b>¿Cuál?:</b> {line_val(val('alergia_medicamento', 'alergia_medicamentos_cual', suppress_if_no=True), 22)}", q_style),
        ],
        [
            Paragraph(f"<b>8.- Otras:</b> &nbsp; {yn_pair('nc_otras')}", q_style),
            Paragraph(f"<b>Cuáles:</b> {line_val(val('otras_enf_detalle', suppress_if_no=True), 22)}", q_style),
        ],
    ]
    t_4_1 = styled_grid_table(rows_4_1, [240, 302])
    add_section("4.1", "Historia Clínica No Cardiovascular", t_4_1)

    # --- 4.2 COVID-19 (Ítems 1 al 5) ---
    rows_4_2 = [
        [
            Paragraph(f"<b>1.- Ha pasado el COVID-19:</b> &nbsp; {yn_pair('covid_paso')}", q_style),
            Paragraph(f"<b>2.- ¿Estuvo ingresado en el hospital?:</b> &nbsp; {yn_pair('covid_ingreso')}", q_style),
        ],
        [
            Paragraph(
                f"<b>3.- Le detectaron alguna afectación cardiovascular debida al COVID-19:</b> &nbsp; {yn_pair('covid_cv')}",
                q_style,
            ),
            Paragraph(f"<b>¿Cuál?:</b> {line_val(val('covid_cv_detalle', suppress_if_no=True), 20)}", q_style),
        ],
        [
            Paragraph(
                f"<b>4.- Le detectaron alguna afectación pulmonar debida al COVID-19:</b> &nbsp; {yn_pair('covid_pulm')}",
                q_style,
            ),
            Paragraph(f"<b>¿Cuál?:</b> {line_val(val('covid_pulm_detalle', suppress_if_no=True), 20)}", q_style),
        ],
        [
            Paragraph(f"<b>5.- Otras:</b> &nbsp; {yn_pair('covid_otras')}", q_style),
            Paragraph(f"<b>Cuáles:</b> {line_val(val('covid_otras_detalle', suppress_if_no=True), 20)}", q_style),
        ],
    ]
    t_4_2 = styled_grid_table(rows_4_2, [330, 212])
    add_section("4.2", "COVID-19", t_4_2, keep_together=True)

    # --- 4.3 Long-COVID (Ítem 1) ---
    rows_4_3 = [
        [
            Paragraph(
                f"<b>1.- Ha presentado después del COVID, algún síntoma que antes no tenía:</b> &nbsp; {yn_pair('longcovid', 'long_covid')}",
                q_style,
            ),
            Paragraph(f"<b>Cuál/es:</b> {line_val(val('longcovid_sintomas', 'long_covid_sintomas', 'sintomas_covid', suppress_if_no=True), 20)}", q_style),
        ]
    ]
    t_4_3 = styled_grid_table(rows_4_3, [330, 212])
    add_section("4.3", "Long-COVID", t_4_3, keep_together=True)

    # --- 4.4 Cuestionario de Dolor de Pecho de G. Rose (Ítems 1 al 8 en orden exacto) ---
    zonas_grid_rows = []
    for row_start in (1, 4, 7):
        z_cells = []
        for z_num in range(row_start, row_start + 3):
            is_z = tri_bool(f"rose_zona_{z_num}") is True
            z_cells.append(Paragraph(f"{chk(is_z)}&nbsp;<b>Zona {z_num}</b>", q_style))
        zonas_grid_rows.append(z_cells)
    t_zonas = Table(zonas_grid_rows, colWidths=[110, 110, 110])
    t_zonas.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#e2e8f0")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ]
        )
    )
    rose_diagram_table = Table([[_build_rose_torso_drawing(), t_zonas]], colWidths=[165, 355])
    rose_diagram_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )

    rose5_boxes = choice_boxes(
        raw_val("rose_5"),
        [
            (lambda s: s == "se_para" or "se para" in s, "Se para"),
            (lambda s: s == "disminuye" or "disminuye" in s, "Disminuye la marcha"),
            (lambda s: s == "continua" or "continua" in s, "Continúa al mismo paso"),
        ],
    )
    rose7_boxes = choice_boxes(
        raw_val("rose_7"),
        [
            (lambda s: s == "10_o_menos" or "10 minutos o menos" in s or "menos" in s, "10 minutos o menos"),
            (lambda s: s == "mas_10" or "mas de 10" in s, "Más de 10 minutos"),
        ],
    )
    rose8_boxes = choice_boxes(
        raw_val("rose_8"),
        [
            (lambda s: "negativ" in s or s == "no", "Negativo"),
            (lambda s: "positiv" in s or s == "si", "Positivo"),
        ],
    )

    rows_4_4 = [
        [
            Paragraph("<b>1.- ¿A veces tiene algún dolor o molestia en el pecho?</b>", q_style),
            Paragraph(yn_pair("rose_1"), ans_right),
        ],
        [
            Paragraph(
                "<b>2.- ¿En qué lugar localiza este dolor o molestia?</b> "
                "<font size='6.8' color='#64748b'>(marque el o los cuadrantes)</font>",
                q_style,
            ),
            "",
        ],
        [rose_diagram_table, ""],
        [
            Paragraph("<b>3.- ¿Cuándo camina a paso habitual, esto le produce la molestia?</b>", q_style),
            Paragraph(yn_pair("rose_3"), ans_right),
        ],
        [
            Paragraph("<b>4.- ¿Cuándo camina cuesta arriba o apurado, esto le produce la molestia?</b>", q_style),
            Paragraph(yn_pair("rose_4"), ans_right),
        ],
        [
            Paragraph(f"<b>5.- ¿Cuándo tiene dolor caminando, qué hace?:</b> &nbsp; {rose5_boxes}", q_style),
            "",
        ],
        [
            Paragraph("<b>6.- ¿Desaparece el dolor o molestia en el pecho si se queda quieto?</b>", q_style),
            Paragraph(yn_pair("rose_6"), ans_right),
        ],
        [
            Paragraph(f"<b>7.- ¿En cuánto tiempo desaparece?:</b> &nbsp; {rose7_boxes}", q_style),
            "",
        ],
        [
            Paragraph("<b>8.- Cuestionario de dolor de pecho de G. Rose:</b>", q_style),
            Paragraph(rose8_boxes, ans_right),
        ],
    ]
    t_4_4 = styled_grid_table(rows_4_4, [382, 160], highlight_rows={8})
    t_4_4.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 1), (1, 1)),
                ("SPAN", (0, 2), (1, 2)),
                ("SPAN", (0, 5), (1, 5)),
                ("SPAN", (0, 7), (1, 7)),
            ]
        )
    )
    add_section("4.4", "Cuestionario de Dolor de Pecho de G. Rose", t_4_4)

    # --- 4.5 Clasificación Funcional NYHA ---
    nyha_boxes = choice_boxes(
        raw_val("nyha_clase"),
        [
            (lambda s: s in {"i", "1", "clase i"}, "Clase I"),
            (lambda s: s in {"ii", "2", "clase ii"}, "Clase II"),
            (lambda s: s in {"iii", "3", "clase iii"}, "Clase III"),
            (lambda s: s in {"iv", "4", "clase iv"}, "Clase IV"),
        ],
    )
    rows_4_5 = [
        [
            Paragraph("<b>Clasificación Funcional NYHA:</b>", q_style),
            Paragraph(nyha_boxes, ans_right),
        ]
    ]
    t_4_5 = styled_grid_table(rows_4_5, [210, 332])
    add_section("4.5", "Clasificación Funcional NYHA", t_4_5, keep_together=True)

    # =========================================================================
    # MÓDULO 5: LABORATORIO Y ECG
    # =========================================================================
    add_module_header("MÓDULO 5", "Laboratorio y ECG")

    # --- 5.1 Resultados del Electrocardiograma (Ítems 1 al 27 + ECG Normal + Comentario) ---
    ritmo_raw = raw_val("ecg_ritmo")
    ritmo_boxes = choice_boxes(
        ritmo_raw,
        [
            (lambda s: s == "rs" or "ritmo sinusal" in s, "RS (ritmo sinusal)"),
            (lambda s: s == "rl", "RL"),
            (lambda s: s in {"siunsal", "sinusal"}, "SINUSAL"),
            (lambda s: "acxfa" in s or "fibrilacion" in s or s == "fa", "ACXFA (Fibrilación auricular)"),
            (
                lambda s: s == "otro"
                or (
                    bool(s)
                    and s not in {"rs", "rl", "siunsal", "sinusal", "acxfa", "fa"}
                    and "sinusal" not in s
                    and "fibrilacion" not in s
                ),
                "Otro ritmo",
            ),
        ],
    )
    br_state = tri_bool("ecg_bloqueo_rama_sn")
    if br_state is None and not is_blank:
        br_txt = _fold_text(raw_val("ecg_bloqueo_rama", "bloqueo_de_rama_cual", "ecg_bloqueo"))
        if br_txt in {"ninguna", "ninguno", "no", "sin bloqueo"}:
            br_state = False
        elif br_txt:
            br_state = True

    rows_5_1 = [
        [
            Paragraph(f"<b>1.- ECG Ritmo:</b> &nbsp; {ritmo_boxes}", q_style),
            "",
            "",
        ],
        [
            Paragraph(f"<b>2.- Frecuencia cardíaca:</b> {line_val(val('ecg_fc', 'f_fc', 'frecuencia_cardiaca_ipm'), 7, 'lpm')}", q_style),
            Paragraph(f"<b>3.- Eje eléctrico A QRS:</b> {line_val(val('ecg_eje', 'eje_electrico_a'), 7, '°')}", q_style),
            Paragraph(f"<b>4.- Intervalo RR:</b> {line_val(val('ecg_rr', 'intervalo_rr_seg'), 7, 'seg')}", q_style),
        ],
        [
            Paragraph(f"<b>5.- Onda P:</b> {line_val(val('ecg_p_mm', 'anchura_onda_p_mm'), 7, 'mm')}", q_style),
            Paragraph(f"<b>6.- Intervalo PR:</b> {line_val(val('ecg_pr', 'intervalo_pr_seg'), 7, 'seg/ms')}", q_style),
            Paragraph(f"<b>7.- Complejo QRS:</b> {line_val(val('ecg_qrs', 'complejo_qr_sseg'), 7, 'seg/ms')}", q_style),
        ],
        [
            Paragraph(f"<b>8.- Intervalo QT:</b> {line_val(val('ecg_qt', 'intervalo_qt_seg'), 7, 'seg/ms')}", q_style),
            Paragraph(f"<b>9.- Intervalo corregido Bazett:</b> {line_val(val('ecg_qtc', 'intervalo_corregido_baset_mseg'), 7, 'mseg')}", q_style),
            Paragraph(f"<b>10.- Onda P mitral:</b> &nbsp; {yn_pair('ecg_p_mitral', 'onda_p_mitral')}", q_style),
        ],
        [
            Paragraph(f"<b>11.- Bloqueo A-V:</b> &nbsp; {yn_pair('ecg_bloqueo_av', 'bloqueo_av')}", q_style),
            Paragraph(f"<b>Grado:</b> {line_val(val('ecg_bloqueo_av_grado', suppress_if_no=True), 20)}", q_style),
            "",
        ],
        [
            Paragraph(f"<b>12.- Bloqueo sinoauricular:</b> &nbsp; {yn_pair('ecg_bloqueo_sa', 'bloqueo_sinoauricular_interaur', 'bloqueo_sinoauricular_interauricular')}", q_style),
            Paragraph(f"<b>13.- Bloqueo interauricular:</b> &nbsp; {yn_pair('ecg_bloqueo_ia', 'bloqueo_sinoauricular_interaur', 'bloqueo_sinoauricular_interauricular')}", q_style),
            "",
        ],
        [
            Paragraph(f"<b>14.- Hemibloqueos:</b> &nbsp; {yn_pair('ecg_hemibloqueo', 'hemibloqueos')}", q_style),
            Paragraph(f"<b>¿Cuál?:</b> {line_val(val('ecg_hemibloqueo_cual', 'hemibloqueos_cual', suppress_if_no=True), 22)}", q_style),
            "",
        ],
        [
            Paragraph(f"<b>15.- Bloqueo de Rama:</b> &nbsp; {yn_pair(force_state=br_state)}", q_style),
            Paragraph(f"<b>¿Cuál?:</b> {line_val(val('ecg_bloqueo_rama', 'bloqueo_de_rama_cual', suppress_if_no=(br_state is False)), 22)}", q_style),
            "",
        ],
        [
            Paragraph(f"<b>16.- Patrón Brugada:</b><br/>{yn_pair('ecg_brugada')}", q_style),
            Paragraph(f"<b>17.- Repolarización precoz:</b><br/>{yn_pair('ecg_repolarizacion_precoz')}", q_style),
            Paragraph(f"<b>18.- Criterios HVI:</b><br/>{yn_pair('ecg_hvi')}", q_style),
        ],
        [
            Paragraph(f"<b>19.- Sobrecarga Sistólica:</b> &nbsp; {yn_pair('ecg_sobrecarga_sistolica', 'sobrecarga_sistolica')}", q_style),
            Paragraph(f"<b>Complejos:</b> {line_val(val('ecg_sobrecarga_complejos', suppress_if_no=True), 22)}", q_style),
            "",
        ],
        [
            Paragraph(
                f"<b>20.- Deflexión intrinsicoide V5-V6:</b> {line_val(val('ecg_deflexion_intrinsicoide', 'deflexion_intrinsicoide_v5v6_s', 'deflexion_intrinsicoide_v5v6_seg'), 7, 'seg')}",
                q_style,
            ),
            "",
            Paragraph(f"<b>21.- Criterio de HVD:</b> &nbsp; {yn_pair('ecg_hvd')}", q_style),
        ],
        [
            Paragraph(f"<b>22.- Onda Delta:</b> &nbsp; {yn_pair('ecg_onda_delta', 'onda_delta')}", q_style),
            Paragraph(f"<b>23.- Cubeta digitálica:</b> &nbsp; {yn_pair('ecg_cubeta_digitalica', 'cubeta_digitalica')}", q_style),
            "",
        ],
        [
            Paragraph(f"<b>24.- Onda Q patológica:</b> &nbsp; {yn_pair('ecg_onda_q', 'onda_q_patologica')}", q_style),
            Paragraph(
                f"<b>Amplitud:</b> {line_val(val('ecg_onda_q_amplitud'), 7)} &nbsp; "
                f"<b>Voltaje:</b> {line_val(val('ecg_onda_q_voltaje'), 6, 'mV')} &nbsp; "
                f"<b>Complejos:</b> {line_val(val('ecg_onda_q_complejos'), 10)}",
                q_style,
            ),
            "",
        ],
        [
            Paragraph(f"<b>25.- T negativa:</b> &nbsp; {yn_pair('ecg_t_negativa', 't_negativa')}", q_style),
            Paragraph(
                f"<b>Complejos:</b> {line_val(val('ecg_t_negativa_complejos', 't_negativa_complejos'), 10)} &nbsp; "
                f"<b>Simétrica:</b> {yn_pair('ecg_t_simetrica')} &nbsp; "
                f"<b>Asimétrica:</b> {yn_pair('ecg_t_asimetrica')}",
                q_small,
            ),
            "",
        ],
        [
            Paragraph(f"<b>26.- Ascenso del ST patológico:</b><br/>{yn_pair('ecg_st_ascenso', 'ascenso_st_patologico')}", q_style),
            Paragraph(
                f"<b>Elevación:</b> {line_val(val('ecg_st_ascenso_mm'), 6, 'mm')} &nbsp;&nbsp; "
                f"<b>Complejos:</b> {line_val(val('ecg_st_ascenso_complejos'), 16)}",
                q_style,
            ),
            "",
        ],
        [
            Paragraph(f"<b>27.- Descenso ST:</b> &nbsp; {yn_pair('ecg_st_descenso', 'descenso_st_patologico')}", q_style),
            Paragraph(
                f"<b>Depresión:</b> {line_val(val('ecg_st_descenso_mm'), 6, 'mm')} &nbsp;&nbsp; "
                f"<b>Complejos:</b> {line_val(val('ecg_st_descenso_complejos'), 16)}",
                q_style,
            ),
            "",
        ],
        [
            Paragraph(f"<b>ECG Normal:</b> &nbsp; {yn_pair('ecg_normal')}", q_style),
            Paragraph(f"<b>Comentario del ECG:</b> {line_val(val('ecg_comentario', 'comentario_ecg'), 28)}", q_style),
            "",
        ],
    ]
    t_5_1 = styled_grid_table(rows_5_1, [180, 182, 180], highlight_rows={16})
    t_5_1.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (2, 0)),
                ("SPAN", (1, 4), (2, 4)),
                ("SPAN", (1, 5), (2, 5)),
                ("SPAN", (1, 6), (2, 6)),
                ("SPAN", (1, 7), (2, 7)),
                ("SPAN", (1, 9), (2, 9)),
                ("SPAN", (0, 10), (1, 10)),
                ("SPAN", (1, 11), (2, 11)),
                ("SPAN", (1, 12), (2, 12)),
                ("SPAN", (1, 13), (2, 13)),
                ("SPAN", (1, 14), (2, 14)),
                ("SPAN", (1, 15), (2, 15)),
                ("SPAN", (1, 16), (2, 16)),
            ]
        )
    )
    add_section("5.1", "Resultados del Electrocardiograma", t_5_1)

    # --- 5.2 Análisis Clínicos (TODOS los parámetros y sub-bloques en orden exacto) ---
    ac_state = tri_bool("ac_prueba")
    ac_res_boxes = choice_boxes(
        raw_val("ac_resultado"),
        [(lambda s: "normal" in s, "Normal"), (lambda s: "alterad" in s, "Alterada")],
        disabled=(ac_state is False),
    )
    rows_5_2 = [
        [
            Paragraph(f"<b>Prueba realizada:</b> &nbsp; {yn_pair('ac_prueba')}", q_style),
            "",
            Paragraph(f"<b>Resultado:</b> &nbsp; {ac_res_boxes}", q_style),
            "",
        ],
        subhdr_row("Hemograma", 4),
        [
            lab_cell("1.- Hematíes", "hemo_hematies", "hematies"),
            lab_cell("2.- Hemoglobina", "hemo_hemoglobina", "hemoglobina"),
            lab_cell("3.- Hematocrito", "hemo_hematocrito", "hematocrito"),
            lab_cell("4.- VCM", "hemo_vcm", "volumen_corpuscular_medio_vcm"),
        ],
        [
            lab_cell("5.- HCM", "hemo_hcm", "hemoglobina_corpuscular_medio_", "hemoglobina_corpuscular_medio_hcm"),
            lab_cell("6.- CHCM", "hemo_chcm", "concentracion_hemoglobina_corp", "concentracion_hemoglobina_corpuscular_media_chcm"),
            lab_cell("9.- Leucocitos", "hemo_leucocitos", "leucocitos"),
            lab_cell("10.- Neutrófilos", "hemo_neutrofilos", "neutrofilos"),
        ],
        [
            lab_cell("11.- Eosinófilos", "hemo_eosinofilos", "eosinofilos"),
            lab_cell("12.- Basófilos", "hemo_basofilos", "basofilos"),
            lab_cell("13.- Linfocitos", "hemo_linfocitos", "linfocitos"),
            lab_cell("14.- Monocitos", "hemo_monocitos", "monocitos"),
        ],
        [
            lab_cell("15.- Plaquetas", "hemo_plaquetas", "plaquetas"),
            lab_cell("16.- INR", "hemo_inr", "inr"),
            lab_cell("17.- T.P. Tromboplastina", "hemo_tpt", "tiempo_protombina"),
            lab_cell("18.- Fibrinógeno", "hemo_fibrinogeno", "fibrinogeno"),
        ],
        subhdr_row("Bioquímica General · Función Tiroidea", 4),
        [
            lab_cell("1.- TSH", "tiroidea_tsh", "tsh_funcion_tiroidea"),
            lab_cell("2.- Hormonas tiroideas T4", "tiroidea_t4", "hormonas_tiroideas_t4"),
            lab_cell("Hormonas tiroideas T3", "tiroidea_t3", "hormonas_tiroideas_t3"),
            Paragraph("", q_small),
        ],
        subhdr_row("Función Renal y Orina", 4),
        [
            lab_cell("1.- Urea", "renal_urea", "urea_funcion_renal"),
            lab_cell("2.- Creatinina", "renal_creatinina", "creatina_funcion_renal"),
            lab_cell("4.- Filtrado glomerular", "renal_filtrado", "filtracion_glomerular_tfg"),
            lab_cell("Orina · Microalbuminuria", "orina_microalbuminuria"),
        ],
        subhdr_row("Iones", 4),
        [
            lab_cell("1.- Potasio", "ion_potasio", "potasio_iones"),
            lab_cell("2.- Calcio", "ion_calcio", "calcio_iones"),
            lab_cell("3.- Magnesio", "ion_magnesio", "magnesio_iones"),
            lab_cell("4.- Sodio", "ion_sodio", "sodio_iones"),
        ],
        subhdr_row("Parámetros Diabéticos", 4),
        [
            lab_cell("1.- Glucosa en sangre", "diab_glucosa", "glucosa_sangre"),
            lab_cell("2.- Hb glicosilada", "diab_hba1c", "hemoglobina_glicosilada"),
            lab_cell("3.- HOMA IR", "diab_homair", "homa_ir"),
            lab_cell("4.- Insulina en Ayunas", "diab_insulina", "insulina_ayunas"),
        ],
        subhdr_row("Parámetros de Riesgo Cardiovascular", 4),
        [
            lab_cell("1.- Colesterol Total", "riesgo_colesterol", "colesterol_total_riesgo_cardio", "colesterol_total_riesgo_cardiovascular"),
            lab_cell("2.- HDL", "riesgo_hdl", "hdl_riesgo_cardiovascular"),
            lab_cell("3.- LDL", "riesgo_ldl", "ldl_riesgo_cardiovascular"),
            lab_cell("4.- VLDL", "riesgo_vldl", "vdl_riesgo_cardiovascular"),
        ],
        [
            lab_cell("5.- Triglicéridos", "riesgo_trigliceridos", "trigliceridos_riesgo_cardiovas", "trigliceridos_riesgo_cardiovascular"),
            lab_cell("6.- Lipoproteína a", "riesgo_lipoproteina_a", "lipoproteina_riesgo_cardiovasc", "lipoproteina_riesgo_cardiovascular"),
            lab_cell("Apolipoproteína B", "riesgo_apo_b", "apolipoproteina_b_riesgo_cardi", "apolipoproteina_b_riesgo_cardiovascular"),
            Paragraph("", q_small),
        ],
        subhdr_row("Factores Analíticos Emergentes", 4),
        [
            lab_cell("1.- Homocisteína", "emerg_homocisteina", "homocisteina"),
            lab_cell("2.- PCR ultrasensible", "emerg_pcr", "pcr_ultrasensible"),
            lab_cell("3.- Ácido Úrico", "emerg_acido_urico", "acido_urico"),
            Paragraph("", q_small),
        ],
        subhdr_row("Función Hepática", 4),
        [
            lab_cell("1.- GGT", "hepatica_ggt", "ggt_funcion_hepatica"),
            lab_cell("2.- GPT (ALT)", "hepatica_gpt", "gpt_alt_funcion_hepatica"),
            lab_cell("3.- GOT (AST)", "hepatica_got", "got_ast_funcion_hepatica"),
            lab_cell("4.- Fosfatasa alcalina", "hepatica_fosfatasa", "fosfatasa_alcalina"),
        ],
        [
            lab_cell("5.- Bilirrubina", "hepatica_bilirrubina", "bilirrubina"),
            Paragraph(
                f"<b>Comentario de los Análisis Clínicos:</b> {line_val(val('comentario_analisis'), 30)}",
                q_small,
            ),
            "",
            "",
        ],
    ]
    t_5_2 = styled_grid_table(
        rows_5_2,
        [135, 136, 135, 136],
        subheader_rows={1, 6, 8, 10, 12, 14, 17, 19},
        highlight_rows={0},
    )
    t_5_2.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (1, 0)),
                ("SPAN", (2, 0), (3, 0)),
                ("SPAN", (1, 21), (3, 21)),
            ]
        )
    )
    add_section("5.2", "Análisis Clínicos", t_5_2)

    # --- 5.3 Insuficiencia Pulmonar (Ítems 1 y 2) ---
    ip_grado_boxes = choice_boxes(
        raw_val("ip_grado", "insuficiencia_pulmonar"),
        [
            (lambda s: s == "no", "No"),
            (lambda s: "leve" in s, "Leve"),
            (lambda s: "moderad" in s, "Moderada"),
            (lambda s: "sever" in s, "Severa"),
        ],
    )
    rows_5_3 = [
        [
            Paragraph(
                f"<b>1.- Medida del chorro regurgitante (%):</b> {line_val(val('ip_medida_chorro', 'chorro_regurgitante'), 8, '%')}",
                q_style,
            ),
            Paragraph(f"<b>2.- Insuficiencia pulmonar:</b> &nbsp; {ip_grado_boxes}", q_style),
        ]
    ]
    t_5_3 = styled_grid_table(rows_5_3, [235, 307])
    add_section("5.3", "Insuficiencia Pulmonar", t_5_3, keep_together=True)

    # --- 5.4 Pericardio (Ítems 1 y 2) ---
    rows_5_4 = [
        [
            Paragraph(f"<b>1.- Derrame pericárdico:</b> &nbsp; {yn_pair('peri_derrame', 'derrame_pericardico', 'derrame_pericardio')}", q_style),
            Paragraph(
                f"<b>2.- Grosor derrame pericárdico</b> <font size='6.8' color='#64748b'>(&lt;1cm leve, &gt;1cm mod., &gt;2cm sev.)</font>: "
                f"{line_val(val('ip_ancho_chorro', 'derram_peric_cms'), 7, 'cm')}",
                q_style,
            ),
        ]
    ]
    t_5_4 = styled_grid_table(rows_5_4, [215, 327])
    add_section("5.4", "Pericardio", t_5_4, keep_together=True)

    # --- 5.5 Resultados (Ecocardiograma - Ítems 1 al 17 en orden exacto) ---
    norm_alt_opts = [(lambda s: "normal" in s, "Normal"), (lambda s: "alterad" in s, "Alterada")]
    norm_alt_pl_opts = [(lambda s: "normal" in s, "Normales"), (lambda s: "alterad" in s, "Alteradas")]

    row_10_11_12 = Table(
        [
            [
                Paragraph(f"<b>10.- Raíz Aórtica Dilatada:</b><br/>{yn_pair('res_raiz_aortica', 'aorta_dilatada')}", q_style),
                Paragraph(f"<b>11.- AI Dilatada:</b><br/>{yn_pair('res_ai_dilatada', 'dilatacion_ai')}", q_style),
                Paragraph(f"<b>12.- AD Dilatada:</b><br/>{yn_pair('res_ad_dilatada')}", q_style),
            ]
        ],
        colWidths=[180, 175, 175],
    )
    row_10_11_12.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    rows_5_5 = [
        [
            Paragraph(f"<b>1.- Ventrículo Izquierdo Dilatado:</b> &nbsp; {yn_pair('res_vi_dilatado', 'ventriculo_izquierdo_dilatado', 'dilatacion_vi')}", q_style),
            Paragraph(
                f"<b>2.- Ventrículo Izquierdo Hipertrófico:</b> &nbsp; {yn_pair('res_vi_hipertrofico', 'ventriculo_izquierdo_hipertrof')}<br/>"
                f"<b>Tipo:</b> {line_val(val('res_vi_hipertrofico_tipo', suppress_if_no=True), 18)}",
                q_style,
            ),
        ],
        [
            Paragraph(
                f"<b>3.- Función Sistólica del Ventrículo Izquierdo:</b><br/>{choice_boxes(raw_val('res_fsvi'), norm_alt_opts)}",
                q_style,
            ),
            Paragraph(
                f"<b>3.- Función Diastólica del Ventrículo Izquierdo:</b><br/>{choice_boxes(raw_val('res_fdvi'), norm_alt_opts)}",
                q_style,
            ),
        ],
        [
            Paragraph(
                f"<b>4.- Presiones de llenado del Ventrículo Izquierdo:</b><br/>{choice_boxes(raw_val('res_presiones_vi', 'presiones_llenado_ventriculo_i'), norm_alt_pl_opts)}",
                q_style,
            ),
            Paragraph(f"<b>5.- Alteraciones de la Contractilidad:</b> &nbsp; {yn_pair('res_contractilidad', 'alteraciones_contractilidad')}", q_style),
        ],
        [
            Paragraph(f"<b>6.- Ventrículo Derecho Dilatado:</b> &nbsp; {yn_pair('res_vd_dilatado', 'ventriculo_derecho_dilatado')}", q_style),
            Paragraph(f"<b>7.- Ventrículo Derecho Hipertrófico:</b> &nbsp; {yn_pair('res_vd_hipertrofico', 'ventriculo_derecho_hipertrofic')}", q_style),
        ],
        [
            Paragraph(
                f"<b>8.- Función Sistólica del Ventrículo Derecho:</b><br/>{choice_boxes(raw_val('res_fsvd'), norm_alt_opts)}",
                q_style,
            ),
            Paragraph(
                f"<b>9.- Función Diastólica del Ventrículo Derecho:</b><br/>{choice_boxes(raw_val('res_fdvd'), norm_alt_opts)}",
                q_style,
            ),
        ],
        [row_10_11_12, ""],
        [
            Paragraph(f"<b>13.- Valvulopatía:</b> &nbsp; {yn_pair('res_valvulopatia')}", q_style),
            Paragraph(f"<b>Tipo:</b> {line_val(val('valvulopatia_tipo_detalle', suppress_if_no=True), 24)}", q_style),
        ],
        [
            Paragraph(f"<b>14.- Derrame pericárdico:</b> &nbsp; {yn_pair('res_derrame')}", q_style),
            Paragraph(f"<b>Cuántos cms:</b> {line_val(val('derrame_grosor_cm'), 8, 'cm')}", q_style),
        ],
        [
            Paragraph(f"<b>15.- Ecocardiografía Normal:</b> &nbsp; {yn_pair('res_eco_normal')}", q_style),
            Paragraph(f"<b>Comentario:</b> {line_val(val('res_eco_comentario'), 24)}", q_style),
        ],
        [
            Paragraph(f"<b>16.- Ecografía Vascular Normal:</b> &nbsp; {yn_pair('res_eco_vascular')}", q_style),
            Paragraph(f"<b>Comentario:</b> {line_val(val('res_eco_vascular_comentario'), 24)}", q_style),
        ],
        [
            Paragraph(f"<b>17.- Ecografía Digestiva. Hígado Graso:</b> &nbsp; {yn_pair('res_higado_graso', 'higado_graso')}", q_style),
            Paragraph(f"<b>Comentario:</b> {line_val(val('res_higado_comentario'), 24)}", q_style),
        ],
    ]
    t_5_5 = styled_grid_table(rows_5_5, [271, 271])
    t_5_5.setStyle(TableStyle([("SPAN", (0, 5), (1, 5))]))
    add_section("5.5", "Resultados", t_5_5)

    # =========================================================================
    # MÓDULO 6: ESTILO DE VIDA
    # =========================================================================
    add_module_header("MÓDULO 6", "Estilo de Vida")

    # --- 6.1 Cuestionario PREDIMED (Ítems 1 al 19 en orden exacto + Puntuación / 16) ---
    # Prefer direct web-form keys (pred_q1..pred_q19); fall back to exact SPSS column codes
    # when a record was imported from SPSS and never resaved through the web form.
    has_direct_pred16 = any(datos.get(k) not in (None, "") for k in ("pred_q16", "pred_q17", "pred_q18", "pred_q19"))
    pred_item_keys = {
        "q1": ("pred_q1", "usa_usted_aceite_de_oliva"),
        "q2": ("pred_q2", "cuanto_aceite_de_oliva_consume"),
        "q3": ("pred_q3", "usted_consume_verduras"),
        "q4": ("pred_q4", "usted_consume_fruta"),
        "q5": ("pred_q5", "usted_consume_carne_roja_embut", "usted_consume_carne_roja_embutidos"),
        "q6": ("pred_q6", "usted_consume_mantequilla_marg", "usted_consume_mantequilla_margarina_nata"),
        "q7": ("pred_q7", "usted_consume_bebidas_carbonat", "usted_consume_bebidas_carbonatadas"),
        "q8": ("pred_q8",),
        "q9": ("pred_q9", "usted_consume_legumbres"),
        "q10": ("pred_q10", "usted_consume_pescado_mariscos"),
        "q11": ("pred_q11",) if has_direct_pred16 else ("usted_consume_pescado_azul", "pred_q11"),
        "q12": ("pred_q12",) if has_direct_pred16 else ("usted_consume_reposteria", "pred_q12"),
        "q16": ("pred_q16", "usted_consume_frutos_secos"),
        "q17": ("pred_q17", "usted_consume_cereales"),
        "q18": ("pred_q18", "usted_consume_pollo_pavo_o_con", "usted_consume_pollo_pavo_o_conejo_en_de_ternera"),
        "q19": ("pred_q19", "usted_consume_alimentos_con_so", "usted_consume_alimentos_con_sofrito"),
    }

    scored_states = [tri_bool(*ks) for ks in pred_item_keys.values()]
    any_pred_answered = (not is_blank) and any(st is not None for st in scored_states)
    saved_pred_total_raw = raw_val("pred_puntuacion_total")

    pred_score_int = None
    if not is_blank:
        if any_pred_answered:
            pred_score_int = sum(1 for st in scored_states if st is True)
        elif saved_pred_total_raw and saved_pred_total_raw not in {"0 / 16", "0/16"}:
            m_pt = re.search(r"\d+", saved_pred_total_raw)
            if m_pt:
                pred_score_int = int(m_pt.group(0))

    pred_score_str = f"{pred_score_int} / 16" if pred_score_int is not None else ""
    baja_adh = pred_score_int is not None and pred_score_int < 9
    buena_adh = pred_score_int is not None and pred_score_int >= 9

    def pred_row(text_str: str, item_id: str):
        return [
            Paragraph(f"<b>{xml_escape(text_str)}</b>", q_style),
            Paragraph(yn_pair(*pred_item_keys[item_id]), ans_right),
        ]

    rows_6_1 = [
        pred_row("1.- ¿Usa el aceite de oliva principalmente para cocinar?", "q1"),
        pred_row("2.- ¿Consume dos o más cucharadas de aceite de oliva al día?", "q2"),
        pred_row("3.- ¿Consume dos o más raciones de verduras u hortalizas al día?", "q3"),
        pred_row("4.- ¿Consume tres o más piezas de fruta al día?", "q4"),
        pred_row("5.- ¿Consume menos de una ración de carnes rojas/embutidos al día?", "q5"),
        pred_row("6.- ¿Consume menos de una ración de mantequilla/margarina/nata al día?", "q6"),
        pred_row("7.- ¿Consume menos de una bebida carbonatada/azucarada al día?", "q7"),
        [
            Paragraph(
                f"<b>8.- ¿Bebe vino tinto?:</b> &nbsp; {yn_pair('pred_q8_bebe')} &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp; "
                f"<b>Consume tres o más vasos por semana:</b>",
                q_style,
            ),
            Paragraph(yn_pair(*pred_item_keys["q8"]), ans_right),
        ],
        pred_row("9.- ¿Consume tres o más raciones de legumbres a la semana?", "q9"),
        pred_row("10.- ¿Consume tres o más raciones de pescado/mariscos a la semana?", "q10"),
        pred_row("11.- ¿Consume dos o más raciones de pescado azul a la semana?", "q11"),
        pred_row("12.- ¿Consume menos de tres veces por semana repostería comercial?", "q12"),
        subhdr_row("Lácteos (recolección informativa)", 2),
        [
            Paragraph(
                f"<b>13.- ¿Consume leche de vaca?:</b> &nbsp; {yn_pair('pred_q13_consume')}<br/>"
                f"<b>Vasos al día:</b> {line_val(val('pred_leche_vasos_dia'), 5)} &nbsp;&nbsp; "
                f"<b>a la semana:</b> {line_val(val('pred_leche_vasos_sem'), 5)} &nbsp;&nbsp; "
                f"<b>Tipo de leche:</b> {line_val(val('pred_leche_tipo'), 16)}",
                q_style,
            ),
            "",
        ],
        [
            Paragraph(
                f"<b>14.- ¿Consume queso?:</b> &nbsp; {yn_pair('pred_q14_consume')} &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp; "
                f"<b>Veces a la semana:</b> {line_val(val('pred_queso_veces_sem'), 5)} &nbsp;&nbsp; "
                f"<b>Gramos:</b> {line_val(val('pred_queso_gramos'), 6)}",
                q_style,
            ),
            "",
        ],
        [
            Paragraph(
                f"<b>15.- ¿Consume yogurt?:</b> &nbsp; {yn_pair('pred_q15_consume')} &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp; "
                f"<b>Cuántos a la semana:</b> {line_val(val('pred_yogurt_cant_sem'), 5)} &nbsp;&nbsp; "
                f"<b>De qué tipo:</b> {line_val(val('pred_yogurt_tipo'), 14)}",
                q_style,
            ),
            "",
        ],
        pred_row("16.- ¿Consume dos o más raciones de frutos secos a la semana?", "q16"),
        pred_row("17.- ¿Consume cereales integrales 3-4 veces por semana?", "q17"),
        pred_row("18.- ¿Consume preferentemente carne de pollo/pavo/conejo en vez de ternera/cerdo?", "q18"),
        pred_row("19.- ¿Consume sofrito dos o más veces por semana?", "q19"),
        [
            Paragraph(
                f"<b>Resultado final, puntuación total:</b> {line_val(xml_escape(pred_score_str), 8)} "
                f"&nbsp;&nbsp; {chk(baja_adh)}&nbsp;Baja adherencia (&lt; 9) &nbsp;&nbsp; "
                f"{chk(buena_adh)}&nbsp;Buena adherencia (&gt;= 9)",
                q_style,
            ),
            "",
        ],
    ]
    t_6_1 = styled_grid_table(rows_6_1, [420, 122], subheader_rows={12}, highlight_rows={20})
    t_6_1.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 13), (1, 13)),
                ("SPAN", (0, 14), (1, 14)),
                ("SPAN", (0, 15), (1, 15)),
                ("SPAN", (0, 20), (1, 20)),
            ]
        )
    )
    add_section(
        "6.1",
        "Cuestionario PREDIMED: Cuestionario de Adherencia a la Dieta Mediterránea",
        t_6_1,
    )

    # --- 6.2 Cuestionario de Actividad Física (Ítems 1 al 4 con claves reales + SPSS) ---
    af_act_raw = raw_val("af_actividad", "usted_realiza_actividad_fisica", "act_realiza", "af_realiza")
    af_act_boxes = choice_boxes(
        af_act_raw,
        [
            (lambda s: s.startswith("no") or "ninguna" in s or s == "0", "No realiza ninguna actividad"),
            (lambda s: s.startswith("si") or "realiza actividad" in s or s == "1", "Sí realiza actividad física"),
        ],
    )

    aero_cual_str = val("af_aero_cual", "act_aerob_cual", "cual_ejercicios_realiza", "af_aerobico_cual", suppress_if_no=True)
    aero_state = tri_bool("af_aerobicos", "act_aerob", "usted_realiza_ejercicios_aerob", "usted_realiza_ejercicios_aerobicos", "af_aerobico")
    if aero_state is None and aero_cual_str:
        aero_state = True

    anaero_cual_str = val("af_anaero_cual", "act_anaerob_cual", "cual_ejercicio_anaerobico_real", "af_anaerobico_cual", suppress_if_no=True)
    anaero_state = tri_bool("af_anaerobicos", "act_anaerob", "usted_realiza_ejercicios_anaer", "usted_realiza_ejercicios_anaerobicos", "af_anaerobico")
    if anaero_state is None and anaero_cual_str:
        anaero_state = True

    dep_tipo_str = val("af_dep_tipo", "act_deporte_tipo", "que_tipo_de_deporte", "af_deporte_tipo", suppress_if_no=True)
    dep_state = tri_bool("af_deporte", "act_deporte", "hace_deporte")
    if dep_state is None and dep_tipo_str:
        dep_state = True

    rows_6_2 = [
        [
            Paragraph(
                f"<b>1.- ¿Qué actividad física ha hecho durante su tiempo libre el último mes?:</b> &nbsp;&nbsp; {af_act_boxes}",
                q_style,
            ),
            "",
        ],
        [
            Paragraph(
                f"<b>2.- Realiza ejercicios aeróbicos</b> <font size='6.8' color='#64748b'>(caminar, correr, bicicleta, piscina, baile-terapia, etc.)</font>:<br/>"
                f"{yn_pair(force_state=aero_state)}",
                q_style,
            ),
            Paragraph(
                f"<b>Cuál:</b> {line_val(aero_cual_str, 14)}<br/>"
                f"<b>Veces/semana:</b> {line_val(val('af_aero_veces_sem', 'act_aerob_frec', 'cuantas_veces_por_semana', 'af_aerobico_veces'), 5)} &nbsp;&nbsp; "
                f"<b>Minutos/día:</b> {line_val(val('af_aero_minutos_dia', 'act_aerob_min', 'cuantos_minutos_al_dia', 'af_aerobico_min'), 5)}",
                q_style,
            ),
        ],
        [
            Paragraph(
                f"<b>3.- Realiza ejercicios físicos anaeróbicos de fuerza</b> <font size='6.8' color='#64748b'>(pesas, abdominales, etc.)</font>:<br/>"
                f"{yn_pair(force_state=anaero_state)}",
                q_style,
            ),
            Paragraph(
                f"<b>Cuál:</b> {line_val(anaero_cual_str, 14)}<br/>"
                f"<b>Veces/semana:</b> {line_val(val('af_anaero_veces_sem', 'act_anaerob_frec', 'cuantas_veces_por_semana_anaer', 'af_anaerobico_veces'), 5)} &nbsp;&nbsp; "
                f"<b>Minutos/día:</b> {line_val(val('af_anaero_minutos_dia', 'act_anaerob_min', 'cuantos_minutos_al_dia_anaerob', 'af_anaerobico_min'), 5)}",
                q_style,
            ),
        ],
        [
            Paragraph(f"<b>4.- ¿Hace deporte?:</b> &nbsp; {yn_pair(force_state=dep_state)}", q_style),
            Paragraph(
                f"<b>Qué tipo:</b> {line_val(dep_tipo_str, 14)}<br/>"
                f"<b>Veces/semana:</b> {line_val(val('af_dep_veces_sem', 'act_deporte_frec', 'cuantas_veces_por_semana_hace_', 'af_deporte_veces'), 5)} &nbsp;&nbsp; "
                f"<b>Minutos/día:</b> {line_val(val('af_dep_minutos_dia', 'act_deporte_min', 'cuantos_minutos_al_dia_hace_de', 'af_deporte_min'), 5)}",
                q_style,
            ),
        ],
    ]
    t_6_2 = styled_grid_table(rows_6_2, [285, 257])
    t_6_2.setStyle(TableStyle([("SPAN", (0, 0), (1, 0))]))
    add_section("6.2", "Cuestionario de Actividad Física", t_6_2, keep_together=True)

    # =========================================================================
    # MÓDULO 7: ESTUDIOS PRESCRITOS
    # =========================================================================
    add_module_header("MÓDULO 7", "Estudios Prescritos")

    rows_7_1 = [
        [
            Paragraph(
                f"<b>1.- Estudios de Análisis Clínicos:</b> &nbsp; {yn_pair('est_analisis_clinicos', 'estudios_clinicos', 'sol_analisis')}",
                q_style,
            ),
            Paragraph(
                f"<b>2.- Ergometría con SPECT:</b> &nbsp; {yn_pair('est_ergometria_spect', 'estudios_ergometria', 'sol_ergometria')}",
                q_style,
            ),
        ],
        [
            Paragraph(
                f"<b>3.- Estudios de TAC cardíaco:</b> &nbsp; {yn_pair('est_tac_cardiaco', 'estudios_tac', 'sol_tac')}",
                q_style,
            ),
            Paragraph(
                f"<b>4.- Estudios de RNM cardíaco:</b> &nbsp; {yn_pair('est_rnm_cardiaco', 'estudios_rnm', 'sol_rnm')}",
                q_style,
            ),
        ],
        [
            Paragraph(
                f"<b>5.- Estudios de Electrofisiología Cardíaca:</b> &nbsp; "
                f"{yn_pair('est_electrofisiologia', 'estudios_electrofisiologia', 'sol_electrofisiologia')}",
                q_style,
            ),
            Paragraph(
                f"<b>6.- Ecocardiografía:</b> &nbsp; "
                f"{yn_pair('est_ecocardiograma', 'estudios_ecocardiograma', 'est_eco', 'sol_eco')}",
                q_style,
            ),
        ],
        [
            Paragraph(
                f"<b>7.- Holter ECG:</b> &nbsp; "
                f"{yn_pair('est_holter', 'estudios_holter', 'estudios_holter_ecg', 'sol_holter')}",
                q_style,
            ),
            Paragraph(
                f"<b>8.- MAPA:</b> &nbsp; "
                f"{yn_pair('est_mapa', 'estudios_mapa', 'sol_mapa', 'usted_se_ha_realizado_estudios_de_mapa')}",
                q_style,
            ),
        ],
        [
            Paragraph(
                f"<b>Observaciones / Otros estudios indicados:</b><br/>"
                f"{line_val(val('est_otros_detalle', 'estudios_otros', 'estudios_observaciones', 'otros_estudios'), 58)}",
                q_style,
            ),
            "",
        ],
    ]
    t_7_1 = styled_grid_table(rows_7_1, [271, 271])
    t_7_1.setStyle(TableStyle([("SPAN", (0, 4), (1, 4))]))
    add_section("7.1", "Estudios que se le ha mandado al paciente", t_7_1, keep_together=True)

    doc.build(
        elements,
        canvasmaker=lambda *a, **kw: NumberedCanvas(
            *a,
            study_code=study_code_header,
            patient_info=patient_footer,
            is_blank=is_blank,
            **kw,
        ),
    )
    buffer.seek(0)
    return buffer.getvalue()
