from django.db import models


# ============================================================================
# 1. GEOGRAFÍA Y CATÁLOGOS SOCIODEMOGRÁFICOS (Esquema catalogo)
# ============================================================================

class Pais(models.Model):
    """Catálogo de Países (Esquema catalogo.Pais)."""
    pais_id = models.AutoField(primary_key=True, db_column='paisid')
    codigo_iso3166_alfa3 = models.CharField(max_length=3, unique=True, db_column='codigoiso3166alfa3')
    nombre = models.CharField(max_length=100, unique=True, db_column='nombre')

    class Meta:
        db_table = '"catalogo"."pais"'
        verbose_name = "País"
        verbose_name_plural = "Países"

    def __str__(self):
        return f"{self.nombre} ({self.codigo_iso3166_alfa3})"


class Provincia(models.Model):
    """Catálogo de Provincias o Estados (Esquema catalogo.Provincia)."""
    provincia_id = models.AutoField(primary_key=True, db_column='provinciaid')
    pais = models.ForeignKey(Pais, on_delete=models.RESTRICT, db_column='paisid')
    codigo_iso3166 = models.CharField(max_length=6, db_column='codigoiso3166')
    nombre = models.CharField(max_length=100, db_column='nombre')

    class Meta:
        db_table = '"catalogo"."provincia"'
        unique_together = (('pais', 'codigo_iso3166'),)
        verbose_name = "Provincia"
        verbose_name_plural = "Provincias"

    def __str__(self):
        return f"{self.nombre} - {self.pais.nombre}"


class Canton(models.Model):
    """Catálogo de Cantones o Municipios (Esquema catalogo.Canton)."""
    canton_id = models.AutoField(primary_key=True, db_column='cantonid')
    provincia = models.ForeignKey(Provincia, on_delete=models.RESTRICT, db_column='provinciaid')
    codigo_dpa = models.CharField(max_length=4, db_column='codigodpa')
    nombre = models.CharField(max_length=100, db_column='nombre')

    class Meta:
        db_table = '"catalogo"."canton"'
        unique_together = (('provincia', 'codigo_dpa'),)
        verbose_name = "Cantón"
        verbose_name_plural = "Cantones"

    def __str__(self):
        return f"{self.nombre} ({self.provincia.nombre})"


class Institucion(models.Model):
    """Catálogo de Instituciones Académicas o de Salud (Esquema catalogo.Institucion)."""
    institucion_id = models.AutoField(primary_key=True, db_column='institucionid')
    siglas = models.CharField(max_length=20, unique=True, db_column='siglas')
    nombre = models.CharField(max_length=150, unique=True, db_column='nombre')

    class Meta:
        db_table = '"catalogo"."institucion"'
        verbose_name = "Institución"
        verbose_name_plural = "Instituciones"

    def __str__(self):
        return f"{self.siglas} - {self.nombre}"


class Sexo(models.Model):
    """Catálogo de Sexo Biológico (Esquema catalogo.Sexo)."""
    sexo_id = models.SmallIntegerField(primary_key=True, db_column='sexoid')
    nombre = models.CharField(max_length=20, unique=True, db_column='nombre')

    class Meta:
        db_table = '"catalogo"."sexo"'
        verbose_name = "Sexo"
        verbose_name_plural = "Sexos"

    def __str__(self):
        return self.nombre


class Etnia(models.Model):
    """Catálogo de Etnias (Esquema catalogo.Etnia)."""
    etnia_id = models.AutoField(primary_key=True, db_column='etniaid')
    nombre = models.CharField(max_length=50, unique=True, db_column='nombre')

    class Meta:
        db_table = '"catalogo"."etnia"'
        verbose_name = "Etnia"
        verbose_name_plural = "Etnias"

    def __str__(self):
        return self.nombre


class CategoriaPersonal(models.Model):
    """Estamento o Categoría de Personal: PDI, PAS, Servicios (Esquema catalogo.CategoriaPersonal)."""
    categoria_personal_id = models.AutoField(primary_key=True, db_column='categoriapersonalid')
    nombre = models.CharField(max_length=50, unique=True, db_column='nombre')

    class Meta:
        db_table = '"catalogo"."categoriapersonal"'
        verbose_name = "Categoría de Personal"
        verbose_name_plural = "Categorías de Personal"

    def __str__(self):
        return self.nombre


class CategoriaProfesional(models.Model):
    """Cargo o Rango Profesional (Esquema catalogo.CategoriaProfesional)."""
    categoria_profesional_id = models.AutoField(primary_key=True, db_column='categoriaprofesionalid')
    nombre = models.CharField(max_length=80, unique=True, db_column='nombre')

    class Meta:
        db_table = '"catalogo"."categoriaprofesional"'
        verbose_name = "Categoría Profesional"
        verbose_name_plural = "Categorías Profesionales"

    def __str__(self):
        return self.nombre


class NivelEstudios(models.Model):
    """Nivel de Instrucción Académica (Esquema catalogo.NivelEstudios)."""
    nivel_estudios_id = models.AutoField(primary_key=True, db_column='nivelestudiosid')
    nombre = models.CharField(max_length=80, unique=True, db_column='nombre')

    class Meta:
        db_table = '"catalogo"."nivelestudios"'
        verbose_name = "Nivel de Estudios"
        verbose_name_plural = "Niveles de Estudios"

    def __str__(self):
        return self.nombre


class RangoIngresos(models.Model):
    """Rangos de Ingreso Económico Mensual (Esquema catalogo.RangoIngresos)."""
    rango_ingresos_id = models.AutoField(primary_key=True, db_column='rangoingresosid')
    nombre = models.CharField(max_length=80, unique=True, db_column='nombre')

    class Meta:
        db_table = '"catalogo"."rangoingresos"'
        verbose_name = "Rango de Ingresos"
        verbose_name_plural = "Rangos de Ingresos"

    def __str__(self):
        return self.nombre


class EstadoCivil(models.Model):
    """Catálogo de Estado Civil (Esquema catalogo.EstadoCivil)."""
    estado_civil_id = models.AutoField(primary_key=True, db_column='estadocivilid')
    nombre = models.CharField(max_length=40, unique=True, db_column='nombre')

    class Meta:
        db_table = '"catalogo"."estadocivil"'
        verbose_name = "Estado Civil"
        verbose_name_plural = "Estados Civiles"

    def __str__(self):
        return self.nombre


class SituacionConvivencia(models.Model):
    """Modalidad de Convivencia Habitacional (Esquema catalogo.SituacionConvivencia)."""
    situacion_convivencia_id = models.AutoField(primary_key=True, db_column='situacionconvivenciaid')
    nombre = models.CharField(max_length=80, unique=True, db_column='nombre')

    class Meta:
        db_table = '"catalogo"."situacionconvivencia"'
        verbose_name = "Situación de Convivencia"
        verbose_name_plural = "Situaciones de Convivencia"

    def __str__(self):
        return self.nombre


class TipoVivienda(models.Model):
    """Régimen o Tipo de Vivienda (Esquema catalogo.TipoVivienda)."""
    tipo_vivienda_id = models.AutoField(primary_key=True, db_column='tipoviviendaid')
    nombre = models.CharField(max_length=80, unique=True, db_column='nombre')

    class Meta:
        db_table = '"catalogo"."tipovivienda"'
        verbose_name = "Tipo de Vivienda"
        verbose_name_plural = "Tipos de Vivienda"

    def __str__(self):
        return self.nombre


class HorarioTrabajo(models.Model):
    """Jornada u Horario Laboral (Esquema catalogo.HorarioTrabajo)."""
    horario_trabajo_id = models.AutoField(primary_key=True, db_column='horariotrabajoid')
    nombre = models.CharField(max_length=60, unique=True, db_column='nombre')

    class Meta:
        db_table = '"catalogo"."horariotrabajo"'
        verbose_name = "Horario de Trabajo"
        verbose_name_plural = "Horarios de Trabajo"

    def __str__(self):
        return self.nombre


class RitmoElectrocardiograma(models.Model):
    """Patrón o Ritmo del ECG: Sinusal, Fibrilación, etc. (Esquema catalogo.RitmoElectrocardiograma)."""
    ritmo_electrocardiograma_id = models.AutoField(primary_key=True, db_column='ritmoelectrocardiogramaid')
    nombre = models.CharField(max_length=80, unique=True, db_column='nombre')

    class Meta:
        db_table = '"catalogo"."ritmoelectrocardiograma"'
        verbose_name = "Ritmo ECG"
        verbose_name_plural = "Ritmos ECG"

    def __str__(self):
        return self.nombre


# ============================================================================
# 2. MOTOR DE CUESTIONARIOS: SECCIONES, PREGUNTAS Y OPCIONES (Esquema catalogo)
# ============================================================================

class SeccionCuestionario(models.Model):
    """Sección o Módulo de Cuestionario Clínico / Dieta / Hábitos (Esquema catalogo.SeccionCuestionario)."""
    seccion_cuestionario_id = models.AutoField(primary_key=True, db_column='seccioncuestionarioid')
    codigo = models.CharField(max_length=30, unique=True, db_column='codigo')
    nombre = models.CharField(max_length=100, db_column='nombre')
    orden = models.SmallIntegerField(db_column='orden')

    class Meta:
        db_table = '"catalogo"."seccioncuestionario"'
        verbose_name = "Sección de Cuestionario"
        verbose_name_plural = "Secciones de Cuestionarios"

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class Pregunta(models.Model):
    """Pregunta Parametrizada del Cuestionario (Esquema catalogo.Pregunta)."""
    TIPO_RESPUESTA_CHOICES = [
        ('OPCION', 'Opción Múltiple / Única'),
        ('NUMERICO', 'Numérico'),
        ('TEXTO', 'Texto Libre'),
        ('BOOLEANO', 'Booleano (Sí/No)'),
    ]

    pregunta_id = models.AutoField(primary_key=True, db_column='preguntaid')
    seccion = models.ForeignKey(SeccionCuestionario, on_delete=models.RESTRICT, db_column='seccioncuestionarioid')
    codigo = models.CharField(max_length=30, unique=True, db_column='codigo')
    enunciado = models.CharField(max_length=300, db_column='enunciado')
    tipo_respuesta = models.CharField(max_length=20, choices=TIPO_RESPUESTA_CHOICES, db_column='tiporespuesta')
    numero_orden = models.SmallIntegerField(db_column='numeroorden')

    class Meta:
        db_table = '"catalogo"."pregunta"'
        verbose_name = "Pregunta de Cuestionario"
        verbose_name_plural = "Preguntas de Cuestionarios"

    def __str__(self):
        return f"[{self.codigo}] {self.enunciado[:50]}"


class OpcionRespuesta(models.Model):
    """Alternativa de Respuesta para Preguntas de Selección (Esquema catalogo.OpcionRespuesta)."""
    opcion_respuesta_id = models.AutoField(primary_key=True, db_column='opcionrespuestaid')
    pregunta = models.ForeignKey(Pregunta, on_delete=models.CASCADE, db_column='preguntaid')
    etiqueta = models.CharField(max_length=150, db_column='etiqueta')
    numero_orden = models.SmallIntegerField(db_column='numeroorden')
    puntua_predimed = models.BooleanField(default=False, db_column='puntuapredimed')

    class Meta:
        db_table = '"catalogo"."opcionrespuesta"'
        unique_together = (('pregunta', 'numero_orden'),)
        verbose_name = "Opción de Respuesta"
        verbose_name_plural = "Opciones de Respuestas"

    def __str__(self):
        return f"{self.pregunta.codigo} - {self.etiqueta}"
