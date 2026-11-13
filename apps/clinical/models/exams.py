from django.db import models
from django.db.models.functions import Cast, Power, Round


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
            Cast(
                models.ExpressionWrapper(
                    models.F('weight_kg') / Power(models.F('height_cm') / 100.0, 2),
                    output_field=models.FloatField()
                ),
                models.DecimalField(max_digits=5, decimal_places=2)
            ),
            2
        ),
        output_field=models.DecimalField(max_digits=5, decimal_places=2),
        db_persist=True
    )
    body_surface_area = models.GeneratedField(
        expression=Round(
            Cast(
                models.ExpressionWrapper(
                    models.Value(0.007184) * Power(models.F('weight_kg'), 0.425) * Power(models.F('height_cm'), 0.725),
                    output_field=models.FloatField()
                ),
                models.DecimalField(max_digits=4, decimal_places=2)
            ),
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
    Refleja íntegramente los 27 ítems del Cuestionario UNEMI Definitivo 2026.
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
    qrs_axis_degrees = models.SmallIntegerField(blank=True, null=True, db_column='qrs_axis_degrees')
    rr_interval_sec = models.DecimalField(max_digits=5, decimal_places=3, blank=True, null=True, db_column='rr_interval_sec', help_text="4. Intervalo RR en segundos")
    p_wave_mm = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True, db_column='p_wave_mm', help_text="5. Onda P en mm")
    pr_interval_ms = models.SmallIntegerField(blank=True, null=True, db_column='pr_interval_ms')
    qrs_duration_ms = models.SmallIntegerField(blank=True, null=True, db_column='qrs_duration_ms')
    qt_interval_ms = models.SmallIntegerField(blank=True, null=True, db_column='qt_interval_ms')
    qtc_bazett_ms = models.SmallIntegerField(blank=True, null=True, db_column='qtc_bazett_ms')
    p_mitrale = models.BooleanField(default=False, db_column='p_mitrale', help_text="10. Onda P mitral (No/Sí)")
    av_block = models.BooleanField(default=False, db_column='av_block', help_text="11. Bloqueo A-V (No/Sí)")
    av_block_grade = models.CharField(max_length=50, blank=True, null=True, db_column='av_block_grade', help_text="11. Grado de bloqueo A-V")
    sa_block = models.BooleanField(default=False, db_column='sa_block', help_text="12. Bloqueo sinoauricular (No/Sí)")
    interatrial_block = models.BooleanField(default=False, db_column='interatrial_block', help_text="13. Bloqueo Interauricular (No/Sí)")
    hemiblock = models.BooleanField(default=False, db_column='hemiblock', help_text="14. Hemibloqueos (No/Sí)")
    hemiblock_detail = models.CharField(max_length=100, blank=True, null=True, db_column='hemiblock_detail', help_text="14. Detalle de hemibloqueo")
    bundle_branch_block = models.CharField(max_length=50, blank=True, null=True, db_column='bundle_branch_block')
    has_bundle_branch_block = models.BooleanField(default=False, db_column='has_bundle_branch_block', help_text="15. Bloqueo de rama (No/Sí)")
    brugada_pattern = models.BooleanField(default=False, db_column='brugada_pattern', help_text="16. Patrón Brugada (No/Sí)")
    early_repolarization = models.BooleanField(default=False, db_column='early_repolarization', help_text="17. Repolarización precoz (No/Sí)")
    left_ventricular_hypertrophy = models.BooleanField(default=False, db_column='left_ventricular_hypertrophy', help_text="18. Criterios de HVI (No/Sí)")
    systolic_overload = models.BooleanField(default=False, db_column='systolic_overload', help_text="19. Sobrecarga Sistólica (No/Sí)")
    systolic_overload_complexes = models.CharField(max_length=100, blank=True, null=True, db_column='systolic_overload_complexes', help_text="19. Complejos con sobrecarga sistólica")
    intrinsicoid_deflection_sec = models.DecimalField(max_digits=5, decimal_places=3, blank=True, null=True, db_column='intrinsicoid_deflection_sec', help_text="20. Deflexión intrinsicoide V5-V6 en seg")
    right_ventricular_hypertrophy = models.BooleanField(default=False, db_column='right_ventricular_hypertrophy', help_text="21. Criterio de HVD (No/Sí)")
    delta_wave = models.BooleanField(default=False, db_column='delta_wave', help_text="22. Onda Delta (No/Sí)")
    digitalis_effect = models.BooleanField(default=False, db_column='digitalis_effect', help_text="23. Cubeta digitálica (No/Sí)")
    pathological_q_wave = models.BooleanField(default=False, db_column='pathological_q_wave', help_text="24. Onda Q patológica (No/Sí)")
    q_wave_amplitude = models.CharField(max_length=50, blank=True, null=True, db_column='q_wave_amplitude', help_text="24. Amplitud onda Q")
    q_wave_voltage_mv = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_column='q_wave_voltage_mv', help_text="24. Voltaje onda Q en mV")
    q_wave_complexes = models.CharField(max_length=100, blank=True, null=True, db_column='q_wave_complexes', help_text="24. Complejos con onda Q patológica")
    negative_t_wave = models.BooleanField(default=False, db_column='negative_t_wave', help_text="25. T negativa (No/Sí)")
    negative_t_complexes = models.CharField(max_length=100, blank=True, null=True, db_column='negative_t_complexes', help_text="25. Complejos con T negativa")
    negative_t_symmetric = models.BooleanField(default=False, db_column='negative_t_symmetric', help_text="25. T negativa simétrica")
    negative_t_asymmetric = models.BooleanField(default=False, db_column='negative_t_asymmetric', help_text="25. T negativa asimétrica")
    st_elevation_pathological = models.BooleanField(default=False, db_column='st_elevation_pathological', help_text="26. Ascenso del ST patológico (No/Sí)")
    st_elevation_mm = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True, db_column='st_elevation_mm', help_text="26. Elevación ST en mm")
    st_elevation_complexes = models.CharField(max_length=100, blank=True, null=True, db_column='st_elevation_complexes', help_text="26. Complejos con elevación ST")
    st_depression = models.BooleanField(default=False, db_column='st_depression', help_text="27. Descenso ST (No/Sí)")
    st_depression_mm = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True, db_column='st_depression_mm', help_text="27. Descenso ST en mm")
    st_depression_complexes = models.CharField(max_length=100, blank=True, null=True, db_column='st_depression_complexes', help_text="27. Complejos con descenso ST")
    repolarization_abnormalities = models.BooleanField(default=False, db_column='repolarization_abnormalities')
    is_normal = models.BooleanField(default=True, db_column='is_normal', help_text="28. ECG Normal (No/Sí)")
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


class OrderedStudies(models.Model):
    """
    Estudios solicitados / mandados al paciente (VisitaEstudiosMandados).
    1:1 satellite table linked to clinical.Visit.
    Refleja la sección 'ESTUDIOS QUE SE LE HA MANDADO AL PACIENTE'
    del Cuestionario UNEMI Definitivo 2026 (Pág. 19).
    """
    visit = models.OneToOneField(
        'clinical.Visit',
        on_delete=models.CASCADE,
        primary_key=True,
        db_column='visit_id',
        related_name='ordered_studies'
    )
    clinical_analysis = models.BooleanField(
        default=False,
        db_column='clinical_analysis',
        help_text="1- Estudios de Análisis clínicos (No/Sí)"
    )
    ergometry_spect = models.BooleanField(
        default=False,
        db_column='ergometry_spect',
        help_text="2- Estudios de ergometría con Spectk (No/Sí)"
    )
    cardiac_ct = models.BooleanField(
        default=False,
        db_column='cardiac_ct',
        help_text="3- Estudios de TAC cardiaco (No/Sí)"
    )
    cardiac_mri = models.BooleanField(
        default=False,
        db_column='cardiac_mri',
        help_text="4- Estudios de RNM cardiaco (No/Sí)"
    )
    electrophysiology = models.BooleanField(
        default=False,
        db_column='electrophysiology',
        help_text="5- Estudios de Electrofisiología (No/Sí)"
    )

    class Meta:
        db_table = 'clinical"."ordered_studies'
        verbose_name = "Ordered Studies"
        verbose_name_plural = "Ordered Studies"

    def __str__(self):
        return f"Estudios Mandados - Visit #{self.visit.study_code}"

