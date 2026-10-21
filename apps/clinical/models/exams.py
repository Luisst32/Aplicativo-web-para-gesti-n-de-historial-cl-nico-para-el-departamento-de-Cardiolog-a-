from django.db import models
from django.db.models.functions import Power, Round


class Anthropometry(models.Model):
    """
    Anthropometric Measurements and Body Composition (VisitaAntropometria).
    1:1 satellite table linked to clinical.Visit.
    Includes persistent generated fields for BMI and Body Surface Area (BSA).
    Fiel a bd_final (CK_Antropometria_Peso, CK_Antropometria_Talla, CK_Antropometria_Perimetro):
      - Peso: BETWEEN 20.00 AND 350.00
      - Talla: BETWEEN 50.0 AND 250.0
      - Perímetro abdominal: IS NULL OR BETWEEN 35.0 AND 220.0
    """
    visit = models.OneToOneField(
        'clinical.Visit',
        on_delete=models.CASCADE,
        primary_key=True,
        db_column='visit_id',
        related_name='anthropometry'
    )
    weight_kg = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        db_column='weight_kg',
        help_text="Body weight in kilograms (20.00 - 350.00 kg)"
    )
    height_cm = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        db_column='height_cm',
        help_text="Body height in centimeters (50.0 - 250.0 cm)"
    )
    waist_circumference_cm = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        blank=True,
        null=True,
        db_column='waist_circumference_cm',
        help_text="Waist / Abdominal circumference in centimeters (35.0 - 220.0 cm)"
    )
    bmi = models.GeneratedField(
        expression=Round(
            models.F('weight_kg') / Power(models.F('height_cm') / 100.0, 2),
            2
        ),
        output_field=models.DecimalField(max_digits=5, decimal_places=2),
        db_persist=True
    )
    body_surface_area = models.GeneratedField(
        expression=Round(
            models.Value(0.007184) * Power(models.F('weight_kg'), 0.425) * Power(models.F('height_cm'), 0.725),
            2
        ),
        output_field=models.DecimalField(max_digits=4, decimal_places=2),
        db_persist=True
    )

    class Meta:
        db_table = 'clinical"."anthropometry'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(weight_kg__gte=20.00, weight_kg__lte=350.00),
                name='ck_anthropometry_weight'
            ),
            models.CheckConstraint(
                condition=models.Q(height_cm__gte=50.0, height_cm__lte=250.0),
                name='ck_anthropometry_height'
            ),
            models.CheckConstraint(
                condition=models.Q(waist_circumference_cm__isnull=True) |
                          models.Q(waist_circumference_cm__gte=35.0, waist_circumference_cm__lte=220.0),
                name='ck_anthropometry_waist'
            )
        ]
        verbose_name = "Anthropometry"
        verbose_name_plural = "Anthropometries"

    def __str__(self):
        return f"Anthropometry - Visit #{self.visit.study_code} (BMI: {self.bmi})"


class VitalSigns(models.Model):
    """
    Vital Signs and Physical Examination Findings (VisitaSignosVitales).
    1:1 satellite table linked to clinical.Visit.
    Fiel a bd_final (CK_SignosVitales_Tas, CK_SignosVitales_Tad, CK_SignosVitales_SatO2, CK_SignosVitales_Fc, CK_SignosVitales_GradoSoplo):
      - TAS: BETWEEN 50 AND 300
      - TAD: BETWEEN 30 AND 200
      - SatO2: IS NULL OR BETWEEN 40 AND 100
      - FC: IS NULL OR BETWEEN 30 AND 250
      - GradoSoplo: IS NULL OR BETWEEN 1 AND 6
    """
    visit = models.OneToOneField(
        'clinical.Visit',
        on_delete=models.CASCADE,
        primary_key=True,
        db_column='visit_id',
        related_name='vital_signs'
    )
    systolic_bp = models.SmallIntegerField(
        db_column='systolic_bp',
        help_text="Systolic Blood Pressure in mmHg (50 - 300)"
    )
    diastolic_bp = models.SmallIntegerField(
        db_column='diastolic_bp',
        help_text="Diastolic Blood Pressure in mmHg (30 - 200)"
    )
    oxygen_saturation = models.SmallIntegerField(
        blank=True,
        null=True,
        db_column='oxygen_saturation',
        help_text="Blood Oxygen Saturation % (40 - 100)"
    )
    heart_rate = models.SmallIntegerField(
        blank=True,
        null=True,
        db_column='heart_rate',
        help_text="Resting Heart Rate in beats per minute (30 - 250)"
    )
    systolic_murmur = models.BooleanField(default=False, db_column='systolic_murmur')
    diastolic_murmur = models.BooleanField(default=False, db_column='diastolic_murmur')
    murmur_grade = models.SmallIntegerField(
        blank=True,
        null=True,
        db_column='murmur_grade',
        help_text="Levine murmur intensity grade (1 - 6)"
    )
    extra_heart_sounds = models.BooleanField(default=False, db_column='extra_heart_sounds')
    pedal_pulses_symmetric = models.BooleanField(default=True, db_column='pedal_pulses_symmetric')
    pulmonary_auscultation_normal = models.BooleanField(default=True, db_column='pulmonary_auscultation_normal')
    abdominal_auscultation_normal = models.BooleanField(default=True, db_column='abdominal_auscultation_normal')
    physical_findings_detail = models.CharField(
        max_length=300,
        blank=True,
        null=True,
        db_column='physical_findings_detail'
    )

    class Meta:
        db_table = 'clinical"."vital_signs'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(systolic_bp__gte=50, systolic_bp__lte=300),
                name='ck_vital_signs_systolic'
            ),
            models.CheckConstraint(
                condition=models.Q(diastolic_bp__gte=30, diastolic_bp__lte=200),
                name='ck_vital_signs_diastolic'
            ),
            models.CheckConstraint(
                condition=models.Q(oxygen_saturation__isnull=True) |
                          models.Q(oxygen_saturation__gte=40, oxygen_saturation__lte=100),
                name='ck_vital_signs_sat_o2'
            ),
            models.CheckConstraint(
                condition=models.Q(heart_rate__isnull=True) |
                          models.Q(heart_rate__gte=30, heart_rate__lte=250),
                name='ck_vital_signs_heart_rate'
            ),
            models.CheckConstraint(
                condition=models.Q(murmur_grade__isnull=True) |
                          models.Q(murmur_grade__gte=1, murmur_grade__lte=6),
                name='ck_vital_signs_murmur_grade'
            )
        ]
        verbose_name = "Vital Signs"
        verbose_name_plural = "Vital Signs"

    def __str__(self):
        return f"Vital Signs - Visit #{self.visit.study_code} ({self.systolic_bp}/{self.diastolic_bp} mmHg)"


class Electrocardiogram(models.Model):
    """
    Electrocardiogram (ECG / EKG) Interpretation (VisitaElectrocardiograma).
    1:1 satellite table linked to clinical.Visit.
    """
    visit = models.OneToOneField(
        'clinical.Visit',
        on_delete=models.CASCADE,
        primary_key=True,
        db_column='visit_id',
        related_name='electrocardiogram'
    )
    rhythm = models.ForeignKey(
        'catalog.EcgRhythm',
        on_delete=models.PROTECT,
        db_column='rhythm_id',
        related_name='electrocardiograms'
    )
    heart_rate = models.SmallIntegerField(blank=True, null=True, db_column='heart_rate')
    pr_interval_ms = models.SmallIntegerField(blank=True, null=True, db_column='pr_interval_ms')
    qrs_duration_ms = models.SmallIntegerField(blank=True, null=True, db_column='qrs_duration_ms')
    qt_interval_ms = models.SmallIntegerField(blank=True, null=True, db_column='qt_interval_ms')
    qtc_bazett_ms = models.SmallIntegerField(blank=True, null=True, db_column='qtc_bazett_ms')
    qrs_axis_degrees = models.SmallIntegerField(blank=True, null=True, db_column='qrs_axis_degrees')
    left_ventricular_hypertrophy = models.BooleanField(default=False, db_column='left_ventricular_hypertrophy')
    bundle_branch_block = models.CharField(max_length=50, blank=True, null=True, db_column='bundle_branch_block')
    repolarization_abnormalities = models.BooleanField(default=False, db_column='repolarization_abnormalities')
    ecg_comments = models.CharField(max_length=300, blank=True, null=True, db_column='ecg_comments')

    class Meta:
        db_table = 'clinical"."electrocardiogram'
        verbose_name = "Electrocardiogram"
        verbose_name_plural = "Electrocardiograms"

    def __str__(self):
        return f"ECG - Visit #{self.visit.study_code} ({self.rhythm.name})"


class Echocardiogram(models.Model):
    """
    Transthoracic Echocardiogram Measurements (VisitaEcocardiograma).
    1:1 satellite table linked to clinical.Visit.
    """
    visit = models.OneToOneField(
        'clinical.Visit',
        on_delete=models.CASCADE,
        primary_key=True,
        db_column='visit_id',
        related_name='echocardiogram'
    )
    lv_dimension_mm = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        blank=True,
        null=True,
        db_column='lv_dimension_mm',
        help_text="Left Ventricle end-diastolic internal diameter in mm"
    )
    rv_dimension_mm = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        blank=True,
        null=True,
        db_column='rv_dimension_mm',
        help_text="Right Ventricle dimension in mm"
    )
    ventricular_hypertrophy = models.BooleanField(default=False, db_column='ventricular_hypertrophy')
    lvef_percentage = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        blank=True,
        null=True,
        db_column='lvef_percentage',
        help_text="Left Ventricular Ejection Fraction % (10.0 - 90.0)"
    )
    diastolic_dysfunction = models.BooleanField(default=False, db_column='diastolic_dysfunction')
    aortic_valve_calcification = models.BooleanField(default=False, db_column='aortic_valve_calcification')
    aortic_gradient_max_mmhg = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        blank=True,
        null=True,
        db_column='aortic_gradient_max_mmhg',
        help_text="Maximum transaortic pressure gradient in mmHg"
    )
    aortic_gradient_mean_mmhg = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        blank=True,
        null=True,
        db_column='aortic_gradient_mean_mmhg',
        help_text="Mean transaortic pressure gradient in mmHg"
    )
    valvular_regurgitation_detail = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        db_column='valvular_regurgitation_detail'
    )

    class Meta:
        db_table = 'clinical"."echocardiogram'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(lvef_percentage__isnull=True) |
                          models.Q(lvef_percentage__gte=10.0, lvef_percentage__lte=90.0),
                name='ck_echocardiogram_lvef'
            )
        ]
        verbose_name = "Echocardiogram"
        verbose_name_plural = "Echocardiograms"

    def __str__(self):
        return f"Echo - Visit #{self.visit.study_code} (LVEF: {self.lvef_percentage}%)"


class Laboratory(models.Model):
    """
    Blood Chemistry and Hematology Laboratory Profile (VisitaLaboratorio).
    1:1 satellite table linked to clinical.Visit.
    """
    visit = models.OneToOneField(
        'clinical.Visit',
        on_delete=models.CASCADE,
        primary_key=True,
        db_column='visit_id',
        related_name='laboratory'
    )
    rbc_millions = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True, db_column='rbc_millions')
    hemoglobin_g_dl = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True, db_column='hemoglobin_g_dl')
    hematocrit_percentage = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True, db_column='hematocrit_percentage')
    mcv_fl = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_column='mcv_fl')
    wbc_thousands = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True, db_column='wbc_thousands')
    platelets_thousands = models.DecimalField(max_digits=6, decimal_places=1, blank=True, null=True, db_column='platelets_thousands')
    prothrombin_time_sec = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True, db_column='prothrombin_time_sec')
    glucose_mg_dl = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_column='glucose_mg_dl')
    urea_mg_dl = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_column='urea_mg_dl')
    creatinine_mg_dl = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True, db_column='creatinine_mg_dl')
    total_cholesterol_mg_dl = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_column='total_cholesterol_mg_dl')
    hdl_mg_dl = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_column='hdl_mg_dl')
    ldl_mg_dl = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_column='ldl_mg_dl')
    triglycerides_mg_dl = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True, db_column='triglycerides_mg_dl')
    ast_got_u_l = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True, db_column='ast_got_u_l')
    alt_gpt_u_l = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True, db_column='alt_gpt_u_l')
    ggt_u_l = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True, db_column='ggt_u_l')
    tsh_u_iu_ml = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_column='tsh_u_iu_ml')

    class Meta:
        db_table = 'clinical"."laboratory'
        verbose_name = "Laboratory"
        verbose_name_plural = "Laboratories"

    def __str__(self):
        return f"Lab - Visit #{self.visit.study_code} (Glucose: {self.glucose_mg_dl}, Total Chol: {self.total_cholesterol_mg_dl})"
