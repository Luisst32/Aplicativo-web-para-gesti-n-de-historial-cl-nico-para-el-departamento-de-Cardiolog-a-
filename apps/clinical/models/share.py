from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.hashers import check_password


class SecureShare(models.Model):
    """
    Registro individual de entrega de ficha clínica mediante enlace seguro
    temporal con caducidad, código de verificación de 6 dígitos y límite de descargas.
    Solo almacena los hashes criptográficos (SHA-256 del token y make_password del código).
    """
    share_id = models.AutoField(primary_key=True)
    visit = models.ForeignKey(
        'clinical.Visit',
        on_delete=models.CASCADE,
        related_name='secure_shares',
        verbose_name="Visita Médica"
    )
    recipient_email = models.EmailField(
        max_length=254,
        verbose_name="Correo Destinatario"
    )

    # Token del enlace: Solo se guarda su hash SHA-256 (64 hex chars)
    token_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name="Hash SHA-256 del Token"
    )

    # Código de acceso (6 dígitos): Solo se guarda su hash mediante make_password
    code_hash = models.CharField(
        max_length=128,
        verbose_name="Hash del Código de Acceso"
    )

    # Fechas y Caducidad
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación"
    )
    expires_at = models.DateTimeField(
        db_index=True,
        verbose_name="Fecha de Caducidad"
    )

    # Control de intentos de código
    attempts = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Intentos Fallidos"
    )
    max_attempts = models.PositiveSmallIntegerField(
        default=5,
        verbose_name="Máximo de Intentos Permitidos"
    )

    # Control de descargas
    download_count = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Descargas Realizadas"
    )
    max_downloads = models.PositiveSmallIntegerField(
        default=3,
        verbose_name="Máximo de Descargas Permitidas"
    )

    # Estado y Revocación
    is_revoked = models.BooleanField(
        default=False,
        verbose_name="Revocado"
    )
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de Revocación"
    )

    # Trazabilidad / Auditoría del emisor
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_shares',
        verbose_name="Creado por"
    )
    note = models.CharField(
        max_length=300,
        blank=True,
        default='',
        verbose_name="Observaciones Generales"
    )

    class Meta:
        db_table = 'clinical_secure_share'
        ordering = ['-created_at']
        verbose_name = "Envío Seguro de Ficha"
        verbose_name_plural = "Envíos Seguros de Fichas"

    def __str__(self):
        return f"Share #{self.share_id} ({self.recipient_email}) - V{self.visit_id}"

    def is_valid(self) -> bool:
        """
        Determina si el enlace se encuentra vigente, no revocado y dentro de los límites
        de caducidad, intentos fallidos y cupo de descargas.
        """
        if self.is_revoked:
            return False
        if timezone.now() > self.expires_at:
            return False
        if self.attempts >= self.max_attempts:
            return False
        if self.download_count >= self.max_downloads:
            return False
        return True

    def verify_code(self, raw_code: str) -> bool:
        """
        Verifica el código ingresado por el destinatario contra el hash almacenado.
        """
        if not self.is_valid():
            return False
        return check_password(str(raw_code).strip(), self.code_hash)

