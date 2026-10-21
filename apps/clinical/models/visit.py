from django.db import models
from django.db.models.functions import ExtractYear


class Visit(models.Model):
    """
    Clinical Evaluation Visit (Ficha / Visita Médica).
    Mapped to PostgreSQL schema: clinical.visit (clinico.Visita).
    1:1 relationship with Patient per PostgreSQL schema (UQ_Visita_Paciente).
    """
    visit_id = models.AutoField(primary_key=True, db_column='visit_id')
    patient = models.OneToOneField(
        'clinical.Patient',
        on_delete=models.PROTECT,
        db_column='patient_id',
        related_name='visit',
        help_text="Patient evaluated during this clinical encounter"
    )
    evaluator = models.ForeignKey(
        'security.User',
        on_delete=models.PROTECT,
        db_column='evaluator_id',
        related_name='evaluated_visits',
        help_text="Clinician / Specialist who conducted the evaluation"
    )
    visit_number = models.PositiveSmallIntegerField(default=1, db_column='visit_number')
    study_code = models.CharField(
        max_length=30,
        unique=True,
        db_column='study_code',
        help_text="Unique cardiovascular study code (e.g., CUN-2024-001)"
    )
    visit_date = models.DateField(db_column='visit_date')
    study_year = models.GeneratedField(
        expression=ExtractYear('visit_date'),
        output_field=models.IntegerField(),
        db_persist=True
    )
    staff_category = models.ForeignKey(
        'catalog.StaffCategory',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        db_column='staff_category_id',
        related_name='visits'
    )
    professional_category = models.ForeignKey(
        'catalog.ProfessionalCategory',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        db_column='professional_category_id',
        related_name='visits'
    )
    education_level = models.ForeignKey(
        'catalog.EducationLevel',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        db_column='education_level_id',
        related_name='visits'
    )
    income_range = models.ForeignKey(
        'catalog.IncomeRange',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        db_column='income_range_id',
        related_name='visits'
    )
    marital_status = models.ForeignKey(
        'catalog.MaritalStatus',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        db_column='marital_status_id',
        related_name='visits'
    )
    living_situation = models.ForeignKey(
        'catalog.LivingSituation',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        db_column='living_situation_id',
        related_name='visits'
    )
    housing_type = models.ForeignKey(
        'catalog.HousingType',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        db_column='housing_type_id',
        related_name='visits'
    )
    work_schedule = models.ForeignKey(
        'catalog.WorkSchedule',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        db_column='work_schedule_id',
        related_name='visits'
    )
    residence_canton = models.ForeignKey(
        'catalog.Canton',
        on_delete=models.PROTECT,
        db_column='residence_canton_id',
        related_name='resident_visits'
    )
    faculty = models.CharField(max_length=150, blank=True, null=True, db_column='faculty')
    num_children = models.PositiveSmallIntegerField(blank=True, null=True, db_column='num_children')
    num_cohabitants = models.PositiveSmallIntegerField(blank=True, null=True, db_column='num_cohabitants')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')

    class Meta:
        db_table = 'clinical"."visit'
        constraints = [
            models.UniqueConstraint(fields=['patient'], name='uq_visit_patient'),
            models.UniqueConstraint(fields=['study_code'], name='uq_visit_study_code'),
            models.CheckConstraint(
                condition=models.Q(num_children__isnull=True) |
                          models.Q(num_children__gte=0, num_children__lte=30),
                name='ck_visit_num_children'
            ),
            models.CheckConstraint(
                condition=models.Q(num_cohabitants__isnull=True) |
                          models.Q(num_cohabitants__gte=0, num_cohabitants__lte=50),
                name='ck_visit_num_cohabitants'
            )
        ]
        verbose_name = "Visit"
        verbose_name_plural = "Visits"

    def __str__(self):
        return f"{self.study_code} - {self.patient.full_name} ({self.visit_date})"
