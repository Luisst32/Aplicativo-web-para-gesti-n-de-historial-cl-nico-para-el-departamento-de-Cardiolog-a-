from django.db import models
from django.conf import settings


# ============================================================================
# NÚCLEO CLÍNICO: PACIENTE Y VISITA (Esquema clinico)
# ============================================================================

class Paciente(models.Model):
    """
    Datos biológicos y de filiación del participante/paciente.
    Mapeado a clinico.Paciente.
    """
    paciente_id = models.AutoField(primary_key=True, db_column='pacienteid')
    institucion = models.ForeignKey('catalogo.Institucion', on_delete=models.RESTRICT, db_column='institucionid')
    numero_cedula = models.CharField(max_length=13, unique=True, db_column='numerocedula')
    nombres = models.CharField(max_length=100, db_column='nombres')
    primer_apellido = models.CharField(max_length=50, db_column='primerapellido')
    segundo_apellido = models.CharField(max_length=50, blank=True, null=True, db_column='segundoapellido')
    fecha_nacimiento = models.DateField(db_column='fechanacimiento')
    sexo = models.ForeignKey('catalogo.Sexo', on_delete=models.RESTRICT, db_column='sexoid')
    etnia = models.ForeignKey('catalogo.Etnia', on_delete=models.RESTRICT, db_column='etniaid')
    canton_nacimiento = models.ForeignKey('catalogo.Canton', on_delete=models.RESTRICT, blank=True, null=True, db_column='cantonnacimientoid')
    pais_nacimiento = models.ForeignKey('catalogo.Pais', on_delete=models.RESTRICT, blank=True, null=True, db_column='paisnacimientoid')
    lugar_nacimiento_extranjero = models.CharField(max_length=80, blank=True, null=True, db_column='lugarnacimientoextranjero')
    correo_electronico = models.EmailField(max_length=100, blank=True, null=True, db_column='correoelectronico')
    numero_telefono = models.CharField(max_length=20, blank=True, null=True, db_column='numerotelefono')
    fecha_creacion_utc = models.DateTimeField(auto_now_add=True, db_column='fechacreacionutc')
    usuario_creacion = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, db_column='usuariocreacionid')

    class Meta:
        db_table = '"clinico"."paciente"'
        verbose_name = "Paciente"
        verbose_name_plural = "Pacientes"

    def __str__(self):
        apellidos = f"{self.primer_apellido} {self.segundo_apellido or ''}".strip()
        return f"{self.numero_cedula} - {self.nombres} {apellidos}"


class Visita(models.Model):
    """
    Evaluación médica o visita clínica (relación 1:1 con el Paciente en la cohorte).
    Mapeado a clinico.Visita.
    """
    visita_id = models.AutoField(primary_key=True, db_column='visitaid')
    paciente = models.OneToOneField(Paciente, on_delete=models.RESTRICT, db_column='pacienteid', related_name='visita')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, db_column='usuarioid')
    numero_visita = models.SmallIntegerField(default=1, db_column='numerovisita')
    codigo_estudio = models.CharField(max_length=30, unique=True, db_column='codigoestudio')
    fecha_visita = models.DateField(db_column='fechavisita')
    anio_estudio = models.IntegerField(editable=False, blank=True, null=True, db_column='anioestudio')
    categoria_personal = models.ForeignKey('catalogo.CategoriaPersonal', on_delete=models.RESTRICT, blank=True, null=True, db_column='categoriapersonalid')
    categoria_profesional = models.ForeignKey('catalogo.CategoriaProfesional', on_delete=models.RESTRICT, blank=True, null=True, db_column='categoriaprofesionalid')
    nivel_estudios = models.ForeignKey('catalogo.NivelEstudios', on_delete=models.RESTRICT, blank=True, null=True, db_column='nivelestudiosid')
    rango_ingresos = models.ForeignKey('catalogo.RangoIngresos', on_delete=models.RESTRICT, blank=True, null=True, db_column='rangoingresosid')
    estado_civil = models.ForeignKey('catalogo.EstadoCivil', on_delete=models.RESTRICT, blank=True, null=True, db_column='estadocivilid')
    situacion_convivencia = models.ForeignKey('catalogo.SituacionConvivencia', on_delete=models.RESTRICT, blank=True, null=True, db_column='situacionconvivenciaid')
    tipo_vivienda = models.ForeignKey('catalogo.TipoVivienda', on_delete=models.RESTRICT, blank=True, null=True, db_column='tipoviviendaid')
    horario_trabajo = models.ForeignKey('catalogo.HorarioTrabajo', on_delete=models.RESTRICT, blank=True, null=True, db_column='horariotrabajoid')
    canton_residencia = models.ForeignKey('catalogo.Canton', on_delete=models.RESTRICT, db_column='cantonresidenciaid')
    facultad = models.CharField(max_length=150, blank=True, null=True, db_column='facultad')
    numero_hijos = models.SmallIntegerField(blank=True, null=True, db_column='numerohijos')
    numero_convivientes = models.SmallIntegerField(blank=True, null=True, db_column='numeroconvivientes')
    fecha_creacion_utc = models.DateTimeField(auto_now_add=True, db_column='fechacreacionutc')

    class Meta:
        db_table = '"clinico"."visita"'
        verbose_name = "Visita Clínica"
        verbose_name_plural = "Visitas Clínicas"

    def __str__(self):
        return f"{self.codigo_estudio} - {self.paciente.numero_cedula} ({self.fecha_visita})"

    def save(self, *args, **kwargs):
        if self.fecha_visita:
            self.anio_estudio = self.fecha_visita.year
        super().save(*args, **kwargs)


# ============================================================================
# TABLAS SATÉLITES 1:1 DE LA VISITA MÉDICA (Esquema clinico)
# ============================================================================

class VisitaAntropometria(models.Model):
    """Medidas somatométricas y cálculos de composición corporal (Esquema clinico.VisitaAntropometria)."""
    visita = models.OneToOneField(Visita, primary_key=True, on_delete=models.CASCADE, db_column='visitaid', related_name='antropometria')
    peso_kg = models.DecimalField(max_digits=5, decimal_places=2, db_column='pesokg')
    talla_cm = models.DecimalField(max_digits=4, decimal_places=1, db_column='tallacm')
    perimetro_abdominal_cm = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True, db_column='perimetroabdominalcm')
    imc = models.DecimalField(max_digits=5, decimal_places=2, editable=False, blank=True, null=True, db_column='imc')
    superficie_corporal = models.DecimalField(max_digits=4, decimal_places=2, editable=False, blank=True, null=True, db_column='superficiecorporal')

    class Meta:
        db_table = '"clinico"."visitaantropometria"'
        verbose_name = "Antropometría de Visita"
        verbose_name_plural = "Antropometrías de Visitas"

    def __str__(self):
        return f"Antropometría {self.visita.codigo_estudio} (IMC: {self.imc})"


class VisitaSignosVitales(models.Model):
    """Constantes fisiológicas y examen físico basal (Esquema clinico.VisitaSignosVitales)."""
    visita = models.OneToOneField(Visita, primary_key=True, on_delete=models.CASCADE, db_column='visitaid', related_name='signos_vitales')
    tas_mm_hg = models.SmallIntegerField(db_column='tasmmhg')
    tad_mm_hg = models.SmallIntegerField(db_column='tadmmhg')
    saturacion_oxigeno = models.SmallIntegerField(blank=True, null=True, db_column='saturacionoxigeno')
    frecuencia_cardiaca = models.SmallIntegerField(blank=True, null=True, db_column='frecuenciacardiaca')
    soplo_sistolico = models.BooleanField(default=False, db_column='soplosistolico')
    soplo_diastolico = models.BooleanField(default=False, db_column='soplodiastolico')
    grado_soplo = models.SmallIntegerField(blank=True, null=True, db_column='gradosoplo')
    extratonos_presentes = models.BooleanField(default=False, db_column='extratonospresentes')
    pulsos_pedios_simetricos = models.BooleanField(default=True, db_column='pulsospediossimetricos')
    auscultacion_pulmonar_normal = models.BooleanField(default=True, db_column='auscultacionpulmonarnormal')
    auscultacion_abdominal_normal = models.BooleanField(default=True, db_column='auscultacionabdominalnormal')
    detalle_hallazgo_fisico = models.CharField(max_length=300, blank=True, null=True, db_column='detallehallazgofisico')

    class Meta:
        db_table = '"clinico"."visitasignosvitales"'
        verbose_name = "Signos Vitales de Visita"
        verbose_name_plural = "Signos Vitales de Visitas"

    def __str__(self):
        return f"Signos {self.visita.codigo_estudio} ({self.tas_mm_hg}/{self.tad_mm_hg} mmHg)"


class VisitaElectrocardiograma(models.Model):
    """Registro y trazado electrocardiográfico de 12 derivaciones (Esquema clinico.VisitaElectrocardiograma)."""
    visita = models.OneToOneField(Visita, primary_key=True, on_delete=models.CASCADE, db_column='visitaid', related_name='electrocardiograma')
    ritmo = models.ForeignKey('catalogo.RitmoElectrocardiograma', on_delete=models.RESTRICT, db_column='ritmoelectrocardiogramaid')
    frecuencia_cardiaca_ecg = models.SmallIntegerField(blank=True, null=True, db_column='frecuenciacardiacaecg')
    intervalo_pr_ms = models.SmallIntegerField(blank=True, null=True, db_column='intervaloprms')
    duracion_qrs_ms = models.SmallIntegerField(blank=True, null=True, db_column='duracionqrsms')
    intervalo_qt_ms = models.SmallIntegerField(blank=True, null=True, db_column='intervaloqtms')
    qtc_bazzett_ms = models.SmallIntegerField(blank=True, null=True, db_column='qtcbazzettms')
    eje_qrs_grados = models.SmallIntegerField(blank=True, null=True, db_column='ejeqrsgrados')
    hipertrofia_ventriculo_izquierdo = models.BooleanField(default=False, db_column='hipertrofiaventriculoizquierdo')
    bloqueo_rama = models.CharField(max_length=50, blank=True, null=True, db_column='bloqueorama')
    alteraciones_repolarizacion = models.BooleanField(default=False, db_column='alteracionesrepolarizacion')
    observaciones_ecg = models.CharField(max_length=300, blank=True, null=True, db_column='observacionesecg')

    class Meta:
        db_table = '"clinico"."visitaelectrocardiograma"'
        verbose_name = "Electrocardiograma de Visita"
        verbose_name_plural = "Electrocardiogramas de Visitas"

    def __str__(self):
        return f"ECG {self.visita.codigo_estudio} - {self.ritmo.nombre}"


class VisitaEcocardiograma(models.Model):
    """Estudio de ecocardiografía transtorácica (Esquema clinico.VisitaEcocardiograma)."""
    visita = models.OneToOneField(Visita, primary_key=True, on_delete=models.CASCADE, db_column='visitaid', related_name='ecocardiograma')
    dimension_vi_mm = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True, db_column='dimensionvimm')
    dimension_vd_mm = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True, db_column='dimensionvdmm')
    hipertrofia_ventricular = models.BooleanField(default=False, db_column='hipertrofiaventricular')
    fevi_porcentaje = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True, db_column='feviporcentaje')
    disfuncion_diastolica = models.BooleanField(default=False, db_column='disfunciondiastolica')
    calcio_anillo_aortico = models.BooleanField(default=False, db_column='calcioanilloaortico')
    gradiente_aortico_max_mm_hg = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True, db_column='gradienteaorticomaxmmhg')
    gradiente_aortico_medio_mm_hg = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True, db_column='gradienteaorticomediommhg')
    insuficiencia_valvular_detalle = models.CharField(max_length=200, blank=True, null=True, db_column='insuficienciavalvulardetalle')

    class Meta:
        db_table = '"clinico"."visitaecocardiograma"'
        verbose_name = "Ecocardiograma de Visita"
        verbose_name_plural = "Ecocardiogramas de Visitas"

    def __str__(self):
        return f"Eco {self.visita.codigo_estudio} (FEVI: {self.fevi_porcentaje}%)"


class VisitaLaboratorio(models.Model):
    """Perfil analítico sanguíneo y metabólico integral (Esquema clinico.VisitaLaboratorio)."""
    visita = models.OneToOneField(Visita, primary_key=True, on_delete=models.CASCADE, db_column='visitaid', related_name='laboratorio')
    hematies_millones = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True, db_column='hematiesmillones')
    hemoglobina_g_dl = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True, db_column='hemoglobinagdl')
    hematocrito_porcentaje = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True, db_column='hematocritoporcentaje')
    vcm_fl = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_column='vcmfl')
    leucocitos_miles = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True, db_column='leucocitosmiles')
    plaquetas_miles = models.DecimalField(max_digits=6, decimal_places=1, blank=True, null=True, db_column='plaquetasmiles')
    tiempo_protrombina_seg = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True, db_column='tiempoprotrombinaseg')
    glucosa_mg_dl = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_column='glucosamgdl')
    urea_mg_dl = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_column='ureamgdl')
    creatinina_mg_dl = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True, db_column='creatininamgdl')
    colesterol_total_mg_dl = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_column='colesteroltotalmgdl')
    hdl_mg_dl = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_column='hdlmgdl')
    ldl_mg_dl = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_column='ldlmgdl')
    trigliceridos_mg_dl = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True, db_column='trigliceridosmgdl')
    got_ast_u_l = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True, db_column='gotastul')
    gpt_alt_u_l = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True, db_column='gptaltul')
    ggt_u_l = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True, db_column='ggtul')
    tsh_micro_u_l_ml = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_column='tshmicroulml')

    class Meta:
        db_table = '"clinico"."visitalaboratorio"'
        verbose_name = "Laboratorio de Visita"
        verbose_name_plural = "Laboratorios de Visitas"

    def __str__(self):
        return f"Lab {self.visita.codigo_estudio}"


class VisitaRespuesta(models.Model):
    """
    Respuestas individuales a ítems de cuestionarios dinámicos (MEDAS/PREDIMED, actividad física, hábitos).
    Mapeado a clinico.VisitaRespuesta.
    """
    visita_respuesta_id = models.BigAutoField(primary_key=True, db_column='visitarespuestaid')
    visita = models.ForeignKey(Visita, on_delete=models.CASCADE, db_column='visitaid', related_name='respuestas')
    pregunta = models.ForeignKey('catalogo.Pregunta', on_delete=models.RESTRICT, db_column='preguntaid')
    opcion_respuesta = models.ForeignKey('catalogo.OpcionRespuesta', on_delete=models.RESTRICT, blank=True, null=True, db_column='opcionrespuestaid')
    valor_numerico = models.DecimalField(max_digits=12, decimal_places=3, blank=True, null=True, db_column='valornumerico')
    valor_texto = models.CharField(max_length=250, blank=True, null=True, db_column='valortexto')

    class Meta:
        db_table = '"clinico"."visitarespuesta"'
        unique_together = (('visita', 'pregunta'),)
        verbose_name = "Respuesta de Visita"
        verbose_name_plural = "Respuestas de Visitas"

    def __str__(self):
        return f"Respuesta {self.visita.codigo_estudio} - {self.pregunta.codigo}"
