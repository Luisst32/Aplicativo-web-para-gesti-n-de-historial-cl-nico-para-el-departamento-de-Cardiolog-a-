from django.db import models


class QuestionnaireSection(models.Model):
    """
    Survey / Questionnaire Module or Section (catalogo.SeccionCuestionario).
    """
    section_id = models.AutoField(primary_key=True, db_column='section_id')
    code = models.CharField(max_length=30, db_column='code')
    name = models.CharField(max_length=100, db_column='name')
    display_order = models.SmallIntegerField(db_column='display_order')
    is_active = models.BooleanField(
        default=True,
        db_column='is_active',
        help_text="Indica si la sección del cuestionario está activa y visible en el formulario"
    )

    class Meta:
        db_table = 'catalog"."questionnaire_section'
        constraints = [
            models.UniqueConstraint(fields=['code'], name='uq_questionnaire_section_code')
        ]
        ordering = ['display_order']
        verbose_name = "Questionnaire Section"
        verbose_name_plural = "Questionnaire Sections"

    def __str__(self):
        return f"{self.code} - {self.name}"


class Question(models.Model):
    """
    Parametric Survey Question (catalogo.Pregunta).
    """
    class ResponseType(models.TextChoices):
        OPCION = 'OPCION', 'Opción / Opción múltiple'
        NUMERICO = 'NUMERICO', 'Numérico'
        TEXTO = 'TEXTO', 'Texto libre'
        BOOLEANO = 'BOOLEANO', 'Lógico / Booleano'

    question_id = models.AutoField(primary_key=True, db_column='question_id')
    section = models.ForeignKey(
        QuestionnaireSection,
        on_delete=models.PROTECT,
        db_column='section_id',
        related_name='questions'
    )
    code = models.CharField(max_length=30, db_column='code')
    text = models.CharField(max_length=300, db_column='text')
    response_type = models.CharField(
        max_length=20,
        choices=ResponseType.choices,
        db_column='response_type'
    )
    display_order = models.SmallIntegerField(db_column='display_order')
    is_active = models.BooleanField(
        default=True,
        db_column='is_active',
        help_text="Indica si la pregunta está activa y habilitada para evaluación clínica"
    )

    class Meta:
        db_table = 'catalog"."question'
        constraints = [
            models.UniqueConstraint(fields=['code'], name='uq_question_code'),
            models.CheckConstraint(
                condition=models.Q(response_type__in=['OPCION', 'NUMERICO', 'TEXTO', 'BOOLEANO']),
                name='ck_question_response_type'
            )
        ]
        ordering = ['section', 'display_order']
        verbose_name = "Question"
        verbose_name_plural = "Questions"

    def __str__(self):
        return f"[{self.code}] {self.text[:50]}"


class AnswerOption(models.Model):
    """
    Answer Option for Choice-based Questions (catalogo.OpcionRespuesta).
    """
    option_id = models.AutoField(primary_key=True, db_column='option_id')
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        db_column='question_id',
        related_name='options'
    )
    label = models.CharField(max_length=150, db_column='label')
    display_order = models.SmallIntegerField(db_column='display_order')
    scores_predimed = models.BooleanField(
        default=False,
        db_column='scores_predimed',
        help_text="Indicates whether this answer option contributes points to the PREDIMED Mediterranean diet adherence score"
    )
    is_active = models.BooleanField(
        default=True,
        db_column='is_active',
        help_text="Indica si la opción de respuesta está disponible para selección"
    )

    class Meta:
        db_table = 'catalog"."answer_option'
        constraints = [
            models.UniqueConstraint(fields=['question', 'display_order'], name='uq_answer_option_display_order')
        ]
        ordering = ['question', 'display_order']
        verbose_name = "Answer Option"
        verbose_name_plural = "Answer Options"

    def __str__(self):
        return f"{self.question.code} - {self.label}"
