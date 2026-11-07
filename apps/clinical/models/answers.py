from django.db import models


class VisitAnswer(models.Model):
    """
    Questionnaire Responses per Visit Encounter (VisitaRespuesta).
    Records an answer to a specific parametric survey question for a given clinical visit.
    Enforces exactly one response value (selected option, numeric, or free text).
    """
    answer_id = models.BigAutoField(primary_key=True, db_column='answer_id')
    visit = models.ForeignKey(
        'clinical.Visit',
        on_delete=models.CASCADE,
        db_column='visit_id',
        related_name='answers'
    )
    question = models.ForeignKey(
        'catalog.Question',
        on_delete=models.PROTECT,
        db_column='question_id',
        related_name='answers'
    )
    selected_option = models.ForeignKey(
        'catalog.AnswerOption',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        db_column='selected_option_id',
        related_name='answers'
    )
    numeric_value = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        blank=True,
        null=True,
        db_column='numeric_value'
    )
    text_value = models.CharField(
        max_length=250,
        blank=True,
        null=True,
        db_column='text_value'
    )

    class Meta:
        db_table = 'clinical"."visit_answer'
        constraints = [
            models.UniqueConstraint(
                fields=['visit', 'question'],
                name='uq_visit_answer_question'
            ),
            models.CheckConstraint(
                condition=(
                    (models.Q(selected_option__isnull=False) & models.Q(numeric_value__isnull=True) & models.Q(text_value__isnull=True)) |
                    (models.Q(selected_option__isnull=True) & models.Q(numeric_value__isnull=False) & models.Q(text_value__isnull=True)) |
                    (models.Q(selected_option__isnull=True) & models.Q(numeric_value__isnull=True) & models.Q(text_value__isnull=False))
                ),
                name='ck_visit_answer_single_value'
            )
        ]
        verbose_name = "Visit Answer"
        verbose_name_plural = "Visit Answers"

    def __str__(self):
        val = self.selected_option.label if self.selected_option else (self.numeric_value or self.text_value)
        return f"Answer #{self.answer_id} (Visit {self.visit.study_code}, Q: {self.question.code}) -> {val}"
