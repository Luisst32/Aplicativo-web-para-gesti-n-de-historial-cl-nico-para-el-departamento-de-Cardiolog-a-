from django.db import models


class Patient(models.Model):
    """
    Clinical Patient Demographic and Identification Record.
    Mapped to PostgreSQL schema: clinical.patient (clinico.Paciente).
    """
    class PatientStatus(models.TextChoices):
        ACTIVE = 'ACTIVO', 'Activo / En seguimiento'
        INACTIVE = 'INACTIVO', 'Inactivo / Sin seguimiento'
        DECEASED = 'FALLECIDO', 'Fallecido'
        TRANSFERRED = 'TRASLADADO', 'Trasladado a otro centro'
        DISCHARGED = 'ALTA', 'Alta médica definitiva'

    patient_id = models.AutoField(primary_key=True, db_column='patient_id')
    institution = models.ForeignKey(
        'catalog.Institution',
        on_delete=models.PROTECT,
        db_column='institution_id',
        related_name='patients',
        help_text="Affiliated academic or healthcare institution"
    )
    id_card = models.CharField(
        max_length=13,
        unique=True,
        db_column='id_card',
        help_text="National identification card number (cédula de identidad)"
    )
    first_names = models.CharField(max_length=100, db_column='first_names')
    last_name1 = models.CharField(max_length=50, db_column='last_name1')
    last_name2 = models.CharField(max_length=50, blank=True, null=True, db_column='last_name2')
    birth_date = models.DateField(db_column='birth_date')
    sex = models.ForeignKey(
        'catalog.Sex',
        on_delete=models.PROTECT,
        db_column='sex_id',
        related_name='patients'
    )
    ethnicity = models.ForeignKey(
        'catalog.Ethnicity',
        on_delete=models.PROTECT,
        db_column='ethnicity_id',
        related_name='patients'
    )
    birth_canton = models.ForeignKey(
        'catalog.Canton',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        db_column='birth_canton_id',
        related_name='born_patients',
        help_text="Canton of birth if born in Ecuador"
    )
    birth_country = models.ForeignKey(
        'catalog.Country',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        db_column='birth_country_id',
        related_name='born_patients',
        help_text="Country of birth if born abroad"
    )
    foreign_birth_place = models.CharField(
        max_length=80,
        blank=True,
        null=True,
        db_column='foreign_birth_place',
        help_text="Foreign city or state of birth"
    )
    email = models.EmailField(max_length=100, blank=True, null=True, db_column='email')
    phone = models.CharField(max_length=20, blank=True, null=True, db_column='phone')

    # Estado clínico del paciente en el programa de cardiología
    status = models.CharField(
        max_length=20,
        choices=PatientStatus.choices,
        default=PatientStatus.ACTIVE,
        db_column='status',
        help_text="Estado del paciente (Activo, Inactivo, Fallecido si ya no está en el programa, Trasladado o Alta)"
    )
    is_active = models.BooleanField(
        default=True,
        db_column='is_active',
        help_text="Indica si el paciente se encuentra activo en el seguimiento clínico"
    )
    status_date = models.DateField(
        blank=True,
        null=True,
        db_column='status_date',
        help_text="Fecha de registro del estado (ej. fecha de defunción, traslado o inactividad)"
    )
    status_reason = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_column='status_reason',
        help_text="Detalle o justificación del estado (ej. causa clínica de defunción, hospital receptor de traslado)"
    )

    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    created_by = models.ForeignKey(
        'security.User',
        on_delete=models.PROTECT,
        db_column='created_by_id',
        related_name='created_patients'
    )

    class Meta:
        db_table = 'clinical"."patient'
        constraints = [
            models.UniqueConstraint(fields=['id_card'], name='uq_patient_id_card'),
            models.CheckConstraint(
                condition=(
                    (models.Q(birth_canton__isnull=False) & models.Q(birth_country__isnull=True) & models.Q(foreign_birth_place__isnull=True)) |
                    (models.Q(birth_canton__isnull=True) & models.Q(birth_country__isnull=False))
                ),
                name='ck_patient_birth_hierarchy'
            )
        ]
        verbose_name = "Patient"
        verbose_name_plural = "Patients"

    def __str__(self):
        return f"{self.id_card} - {self.first_names} {self.last_name1}"

    @property
    def full_name(self):
        if self.last_name2:
            return f"{self.first_names} {self.last_name1} {self.last_name2}"
        return f"{self.first_names} {self.last_name1}"

    @property
    def is_deceased(self):
        """Retorna True si el paciente ha fallecido."""
        return self.status == self.PatientStatus.DECEASED

    def mark_as_deceased(self, date=None, reason=None):
        """Registra al paciente como fallecido (ya no asiste ni se encuentra en el programa)."""
        from django.utils import timezone
        self.status = self.PatientStatus.DECEASED
        self.is_active = False
        self.status_date = date or timezone.now().date()
        if reason:
            self.status_reason = reason
        self.save(update_fields=['status', 'is_active', 'status_date', 'status_reason'])

    def mark_as_transferred(self, destination=None, date=None):
        """Registra al paciente como trasladado o derivado a otra institución."""
        from django.utils import timezone
        self.status = self.PatientStatus.TRANSFERRED
        self.is_active = False
        self.status_date = date or timezone.now().date()
        if destination:
            self.status_reason = f"Derivado a: {destination}"
        self.save(update_fields=['status', 'is_active', 'status_date', 'status_reason'])
