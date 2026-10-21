from django.db import models


class Sex(models.Model):
    """
    Biological Sex catalog (catalogo.Sexo).
    Keys are assigned manually (0 to 9).
    """
    sex_id = models.SmallIntegerField(primary_key=True, db_column='sex_id')
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
    Self-identified Ethnicity catalog (catalogo.Etnia).
    """
    ethnicity_id = models.AutoField(primary_key=True, db_column='ethnicity_id')
    name = models.CharField(max_length=50, db_column='name')

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
    Institutional Staff Category: PDI, PAS, ESTUDIANTE, etc. (catalogo.CategoriaPersonal).
    """
    staff_category_id = models.AutoField(primary_key=True, db_column='staff_category_id')
    name = models.CharField(max_length=50, db_column='name')

    class Meta:
        db_table = 'catalog"."staff_category'
        constraints = [
            models.UniqueConstraint(fields=['name'], name='uq_staff_category_name')
        ]
        verbose_name = "Staff Category"
        verbose_name_plural = "Staff Categories"

    def __str__(self):
        return self.name


class ProfessionalCategory(models.Model):
    """
    Professional Rank or Academic Level (catalogo.CategoriaProfesional).
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
    Educational Attainment Level (catalogo.NivelEstudios).
    """
    education_level_id = models.AutoField(primary_key=True, db_column='education_level_id')
    name = models.CharField(max_length=80, db_column='name')

    class Meta:
        db_table = 'catalog"."education_level'
        constraints = [
            models.UniqueConstraint(fields=['name'], name='uq_education_level_name')
        ]
        verbose_name = "Education Level"
        verbose_name_plural = "Education Levels"

    def __str__(self):
        return self.name


class IncomeRange(models.Model):
    """
    Monthly Income Bracket (catalogo.RangoIngresos).
    """
    income_range_id = models.AutoField(primary_key=True, db_column='income_range_id')
    name = models.CharField(max_length=80, db_column='name')

    class Meta:
        db_table = 'catalog"."income_range'
        constraints = [
            models.UniqueConstraint(fields=['name'], name='uq_income_range_name')
        ]
        verbose_name = "Income Range"
        verbose_name_plural = "Income Ranges"

    def __str__(self):
        return self.name


class MaritalStatus(models.Model):
    """
    Marital Status catalog (catalogo.EstadoCivil).
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
    Living / Cohabitation arrangement (catalogo.SituacionConvivencia).
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
    Housing / Residence dwelling type (catalogo.TipoVivienda).
    """
    housing_type_id = models.AutoField(primary_key=True, db_column='housing_type_id')
    name = models.CharField(max_length=80, db_column='name')

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
    Work Shift and Schedule (catalogo.HorarioTrabajo).
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
    Electrocardiogram Baseline Rhythm pattern (catalogo.RitmoElectrocardiograma).
    """
    ecg_rhythm_id = models.AutoField(primary_key=True, db_column='ecg_rhythm_id')
    name = models.CharField(max_length=80, db_column='name')

    class Meta:
        db_table = 'catalog"."ecg_rhythm'
        constraints = [
            models.UniqueConstraint(fields=['name'], name='uq_ecg_rhythm_name')
        ]
        verbose_name = "ECG Rhythm"
        verbose_name_plural = "ECG Rhythms"

    def __str__(self):
        return self.name
