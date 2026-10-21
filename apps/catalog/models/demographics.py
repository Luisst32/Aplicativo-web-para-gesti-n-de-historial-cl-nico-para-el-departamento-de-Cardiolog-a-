from django.db import models


class Sex(models.Model):
    """
    Biological Sex catalog based on ISO 5218 (Mapped to catalog.sex).
    Keys are assigned manually: 0 Unknown, 1 Male, 2 Female, 9 Not Applicable.
    """
    sex_id = models.SmallIntegerField(primary_key=True, db_column='sex_id')
    iso_code = models.CharField(max_length=1, db_column='iso_code')
    name = models.CharField(max_length=20, db_column='name')

    class Meta:
        db_table = 'catalog"."sex'
        constraints = [
            models.UniqueConstraint(fields=['name'], name='uq_sex_name'),
            models.CheckConstraint(
                condition=models.Q(sex_id__gte=0, sex_id__lte=9),
                name='ck_sex_range'
            )
        ]
        verbose_name = "Sex"
        verbose_name_plural = "Sexes"

    def __str__(self):
        return f"{self.name} ({self.sex_id})"


class Ethnicity(models.Model):
    """
    Self-identified Ethnicity catalog (Mapped to catalog.ethnicity).
    """
    ethnicity_id = models.AutoField(primary_key=True, db_column='ethnicity_id')
    name = models.CharField(max_length=40, db_column='name')

    class Meta:
        db_table = 'catalog"."ethnicity'
        constraints = [
            models.UniqueConstraint(fields=['name'], name='uq_ethnicity_name')
        ]
        verbose_name = "Ethnicity"
        verbose_name_plural = "Ethnicities"

    def __str__(self):
        return self.name


class StaffCategory(models.Model):
    """
    Institutional Staff Category: PDI (Faculty), PAS (Admin), etc. (Mapped to catalog.staff_category).
    """
    staff_category_id = models.AutoField(primary_key=True, db_column='staff_category_id')
    code = models.CharField(max_length=10, db_column='code')
    name = models.CharField(max_length=60, db_column='name')

    class Meta:
        db_table = 'catalog"."staff_category'
        constraints = [
            models.UniqueConstraint(fields=['code'], name='uq_staff_category_code'),
            models.UniqueConstraint(fields=['name'], name='uq_staff_category_name')
        ]
        verbose_name = "Staff Category"
        verbose_name_plural = "Staff Categories"

    def __str__(self):
        return f"{self.code} - {self.name}"


class ProfessionalCategory(models.Model):
    """
    Professional Rank or Academic Level (Mapped to catalog.professional_category).
    """
    professional_category_id = models.AutoField(primary_key=True, db_column='professional_category_id')
    name = models.CharField(max_length=80, db_column='name')

    class Meta:
        db_table = 'catalog"."professional_category'
        constraints = [
            models.UniqueConstraint(fields=['name'], name='uq_professional_category_name')
        ]
        verbose_name = "Professional Category"
        verbose_name_plural = "Professional Categories"

    def __str__(self):
        return self.name


class EducationLevel(models.Model):
    """
    Educational Attainment Level (Mapped to catalog.education_level).
    """
    education_level_id = models.AutoField(primary_key=True, db_column='education_level_id')
    name = models.CharField(max_length=60, db_column='name')
    display_order = models.PositiveSmallIntegerField(db_column='display_order')

    class Meta:
        db_table = 'catalog"."education_level'
        constraints = [
            models.UniqueConstraint(fields=['name'], name='uq_education_level_name')
        ]
        ordering = ['display_order']
        verbose_name = "Education Level"
        verbose_name_plural = "Education Levels"

    def __str__(self):
        return self.name


class IncomeRange(models.Model):
    """
    Monthly Income Bracket in USD (Mapped to catalog.income_range).
    """
    income_range_id = models.AutoField(primary_key=True, db_column='income_range_id')
    name = models.CharField(max_length=60, db_column='name')
    lower_limit_usd = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, db_column='lower_limit_usd')
    upper_limit_usd = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, db_column='upper_limit_usd')
    display_order = models.PositiveSmallIntegerField(db_column='display_order')

    class Meta:
        db_table = 'catalog"."income_range'
        constraints = [
            models.UniqueConstraint(fields=['name'], name='uq_income_range_name'),
            models.CheckConstraint(
                condition=models.Q(lower_limit_usd__isnull=True) |
                          models.Q(upper_limit_usd__isnull=True) |
                          models.Q(lower_limit_usd__lte=models.F('upper_limit_usd')),
                name='ck_income_range_limits'
            )
        ]
        ordering = ['display_order']
        verbose_name = "Income Range"
        verbose_name_plural = "Income Ranges"

    def __str__(self):
        return self.name


class MaritalStatus(models.Model):
    """
    Marital Status catalog (Mapped to catalog.marital_status).
    """
    marital_status_id = models.AutoField(primary_key=True, db_column='marital_status_id')
    name = models.CharField(max_length=40, db_column='name')

    class Meta:
        db_table = 'catalog"."marital_status'
        constraints = [
            models.UniqueConstraint(fields=['name'], name='uq_marital_status_name')
        ]
        verbose_name = "Marital Status"
        verbose_name_plural = "Marital Statuses"

    def __str__(self):
        return self.name


class LivingSituation(models.Model):
    """
    Living / Cohabitation arrangement (Mapped to catalog.living_situation).
    """
    living_situation_id = models.AutoField(primary_key=True, db_column='living_situation_id')
    name = models.CharField(max_length=80, db_column='name')

    class Meta:
        db_table = 'catalog"."living_situation'
        constraints = [
            models.UniqueConstraint(fields=['name'], name='uq_living_situation_name')
        ]
        verbose_name = "Living Situation"
        verbose_name_plural = "Living Situations"

    def __str__(self):
        return self.name


class HousingType(models.Model):
    """
    Housing / Residence dwelling type (Mapped to catalog.housing_type).
    """
    housing_type_id = models.AutoField(primary_key=True, db_column='housing_type_id')
    name = models.CharField(max_length=40, db_column='name')

    class Meta:
        db_table = 'catalog"."housing_type'
        constraints = [
            models.UniqueConstraint(fields=['name'], name='uq_housing_type_name')
        ]
        verbose_name = "Housing Type"
        verbose_name_plural = "Housing Types"

    def __str__(self):
        return self.name


class WorkSchedule(models.Model):
    """
    Work Shift and Schedule (Mapped to catalog.work_schedule).
    """
    work_schedule_id = models.AutoField(primary_key=True, db_column='work_schedule_id')
    name = models.CharField(max_length=60, db_column='name')

    class Meta:
        db_table = 'catalog"."work_schedule'
        constraints = [
            models.UniqueConstraint(fields=['name'], name='uq_work_schedule_name')
        ]
        verbose_name = "Work Schedule"
        verbose_name_plural = "Work Schedules"

    def __str__(self):
        return self.name


class EcgRhythm(models.Model):
    """
    Electrocardiogram Baseline Rhythm pattern (Mapped to catalog.ecg_rhythm).
    """
    ecg_rhythm_id = models.AutoField(primary_key=True, db_column='ecg_rhythm_id')
    code = models.CharField(max_length=15, db_column='code', help_text="Short rhythm code (e.g., RS, RL, ACXFA)")
    name = models.CharField(max_length=80, db_column='name')

    class Meta:
        db_table = 'catalog"."ecg_rhythm'
        constraints = [
            models.UniqueConstraint(fields=['code'], name='uq_ecg_rhythm_code')
        ]
        verbose_name = "ECG Rhythm"
        verbose_name_plural = "ECG Rhythms"

    def __str__(self):
        return f"{self.code} - {self.name}"
