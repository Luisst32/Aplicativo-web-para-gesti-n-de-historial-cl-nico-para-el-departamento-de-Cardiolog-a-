import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import models

logger = logging.getLogger(__name__)

ADMIN_ROLE_NAME = 'Administrador'
SYSTEM_SETTING_CACHE_KEY = 'security:system_setting:admin'
DEFAULT_GEMINI_MODEL = 'gemini-2.5-flash'
DEFAULT_OPENAI_MODEL = 'gpt-4o-mini'
DEFAULT_CLAUDE_MODEL = 'claude-3-5-sonnet-20241022'


class Role(models.Model):
    """Definición de rol para control de acceso (tabla security.role)."""

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        INACTIVE = 'INACTIVE', 'Inactive'

    role_id = models.AutoField(primary_key=True, db_column='role_id')
    name = models.CharField(max_length=50, unique=True, db_column='name')
    description = models.CharField(max_length=200, blank=True, null=True, db_column='description')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_column='status',
    )

    class Meta:
        db_table = 'security"."role'
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete(SYSTEM_SETTING_CACHE_KEY)

    def delete(self, *args, **kwargs):
        res = super().delete(*args, **kwargs)
        cache.delete(SYSTEM_SETTING_CACHE_KEY)
        return res

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    """Manager personalizado para el modelo institucional de usuarios."""

    def create_user(self, username, email, password=None, **extra_fields):
        if not username:
            raise ValueError('El campo username es obligatorio.')
        if not email:
            raise ValueError('El campo email es obligatorio.')

        email = self.normalize_email(email)
        extra_fields.setdefault('status', User.Status.ACTIVE)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)

        user = self.model(
            username=username,
            email=email,
            **extra_fields,
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('status', User.Status.ACTIVE)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('El superusuario debe tener is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('El superusuario debe tener is_superuser=True.')

        return self.create_user(username, email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Modelo institucional de usuario mapeado a la tabla security.user."""

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        INACTIVE = 'INACTIVE', 'Inactive'
        SUSPENDED = 'SUSPENDED', 'Suspended'

    user_id = models.AutoField(primary_key=True, db_column='user_id')
    institution = models.ForeignKey(
        'catalog.Institution',
        on_delete=models.RESTRICT,
        db_column='institution_id',
        related_name='users',
        null=True,
        blank=True,
        help_text="Institution the user belongs to (nullable for superadmin)",
    )
    username = models.CharField(max_length=60, unique=True, db_column='username')
    email = models.EmailField(max_length=150, unique=True, db_column='email')
    first_name = models.CharField(max_length=100, db_column='first_name')
    last_name = models.CharField(max_length=60, db_column='last_name')
    second_last_name = models.CharField(max_length=60, blank=True, null=True, db_column='second_last_name')

    last_login = models.DateTimeField(blank=True, null=True, db_column='last_login_utc')
    created_at_utc = models.DateTimeField(auto_now_add=True, db_column='created_at_utc')

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_column='status',
    )
    is_active = models.BooleanField(default=True, db_column='is_active')
    is_staff = models.BooleanField(default=False, db_column='is_staff')

    roles = models.ManyToManyField(Role, through='UserRole', related_name='users')

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'first_name', 'last_name']
    EMAIL_FIELD = 'email'

    class Meta:
        db_table = 'security"."user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def save(self, *args, **kwargs):
        # Mantener sincronizados status e is_active para evitar inconsistencias al autenticar
        if self.status != self.Status.ACTIVE:
            self.is_active = False
        elif not self.is_active:
            self.status = self.Status.INACTIVE
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} ({self.first_name} {self.last_name})"

    @property
    def full_name(self):
        last_names = f"{self.last_name} {self.second_last_name or ''}".strip()
        return f"{self.first_name} {last_names}"

    @property
    def is_administrator(self) -> bool:
        """
        Determina si el usuario es administrador del sistema únicamente por
        superusuario o pertenencia activa al rol exacto 'Administrador'.
        """
        if getattr(self, 'is_superuser', False):
            return True
        return self.userrole_set.filter(
            role__name=ADMIN_ROLE_NAME,
            role__status=Role.Status.ACTIVE,
            status=UserRole.Status.ACTIVE,
        ).exists()


class UserRole(models.Model):
    """Tabla asociativa entre User y Role (mapeada a security.user_role)."""

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        INACTIVE = 'INACTIVE', 'Inactive'

    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    role = models.ForeignKey(Role, on_delete=models.RESTRICT, db_column='role_id')
    assigned_at_utc = models.DateTimeField(auto_now_add=True, db_column='assigned_at_utc')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_column='status',
    )

    class Meta:
        db_table = 'security"."user_role'
        constraints = [
            models.UniqueConstraint(fields=['user', 'role'], name='unique_user_role'),
        ]
        verbose_name = 'User Role'
        verbose_name_plural = 'User Roles'

    def __str__(self):
        return f"{self.user.username} - {self.role.name}"


def _derive_secret_key_fernet() -> bytes:
    """Deriva una clave Fernet válida desde settings.SECRET_KEY para compatibilidad de rotación."""
    key_bytes = hashlib.sha256(settings.SECRET_KEY.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(key_bytes)


def _get_fernet_cipher() -> MultiFernet:
    """
    Construye un MultiFernet usando las claves dedicadas de settings.FIELD_ENCRYPTION_KEYS
    (para cifrado y rotación) y la derivada de settings.SECRET_KEY como respaldo de descifrado.
    """
    ciphers = [
        Fernet(k.encode('utf-8') if isinstance(k, str) else k)
        for k in getattr(settings, 'FIELD_ENCRYPTION_KEYS', [])
        if k
    ]
    ciphers.append(Fernet(_derive_secret_key_fernet()))
    return MultiFernet(ciphers)


def encrypt_api_key(raw_key: str) -> str:
    """Cifra una clave API con MultiFernet; retorna cadena vacía si está en blanco."""
    if not raw_key or not raw_key.strip():
        return ''
    return _get_fernet_cipher().encrypt(raw_key.strip().encode('utf-8')).decode('utf-8')


def decrypt_api_key(enc_key: str) -> str:
    """
    Descifra una clave API almacenada con MultiFernet.
    Si el token es inválido o fue manipulado, registra el error y retorna cadena vacía.
    """
    if not enc_key or not enc_key.strip():
        return ''
    try:
        return _get_fernet_cipher().decrypt(enc_key.strip().encode('utf-8')).decode('utf-8')
    except InvalidToken:
        logger.error("No se pudo descifrar la API key de SystemSetting (InvalidToken).")
        return ''


class SystemSetting(models.Model):
    """
    Configuración relacional del sistema (security.system_setting) vinculada
    exclusivamente al rol Administrador (security.role).
    Almacena el interruptor del chatbot y la API Key cifrada sin depender de .env.
    """

    setting_id = models.AutoField(primary_key=True, db_column='setting_id')
    role = models.OneToOneField(
        Role,
        on_delete=models.RESTRICT,
        db_column='role_id',
        related_name='system_setting',
        help_text='Rol exclusivo autorizado para administrar y utilizar la API Key del sistema',
    )
    chatbot_enabled = models.BooleanField(
        default=True,
        db_column='chatbot_enabled',
        help_text='Interruptor global para activar o desactivar el Asistente Clínico con IA',
    )
    active_llm_provider = models.CharField(
        max_length=30,
        default='gemini',
        db_column='active_llm_provider',
        help_text='Proveedor LLM activo para el asistente clínico: gemini, openai, claude',
    )

    # 1. Google Gemini Generative AI
    gemini_api_key_encrypted = models.TextField(
        blank=True,
        null=True,
        db_column='gemini_api_key_encrypted',
        help_text="Clave de API de Google Gemini encriptada con Fernet (AES-128-CBC + HMAC)",
    )
    gemini_model = models.CharField(
        max_length=60,
        default=DEFAULT_GEMINI_MODEL,
        db_column='gemini_model',
        help_text="Modelo por defecto de Gemini Flash",
    )
    gemini_enabled = models.BooleanField(
        default=True,
        db_column='gemini_enabled',
        help_text="Interruptor de activación de Google Gemini",
    )

    # 2. OpenAI / ChatGPT
    openai_api_key_encrypted = models.TextField(
        blank=True,
        null=True,
        db_column='openai_api_key_encrypted',
        help_text="Clave de API de OpenAI (ChatGPT) encriptada con Fernet",
    )
    openai_model = models.CharField(
        max_length=60,
        default=DEFAULT_OPENAI_MODEL,
        db_column='openai_model',
        help_text="Modelo activo de OpenAI (ej. gpt-4o, gpt-4o-mini)",
    )
    openai_enabled = models.BooleanField(
        default=False,
        db_column='openai_enabled',
        help_text="Interruptor de activación de OpenAI",
    )

    # 3. Anthropic Claude
    claude_api_key_encrypted = models.TextField(
        blank=True,
        null=True,
        db_column='claude_api_key_encrypted',
        help_text="Clave de API de Anthropic Claude encriptada con Fernet",
    )
    claude_model = models.CharField(
        max_length=60,
        default=DEFAULT_CLAUDE_MODEL,
        db_column='claude_model',
        help_text="Modelo activo de Anthropic Claude (ej. claude-3-5-sonnet, claude-3-5-haiku)",
    )
    claude_enabled = models.BooleanField(
        default=False,
        db_column='claude_enabled',
        help_text="Interruptor de activación de Anthropic Claude",
    )

    # 4. Google Gmail REST API
    gmail_client_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_column='gmail_client_id',
        help_text="Google Cloud Platform OAuth2 Client ID",
    )
    gmail_client_secret_encrypted = models.TextField(
        blank=True,
        null=True,
        db_column='gmail_client_secret_encrypted',
        help_text="Google OAuth2 Client Secret encriptado con Fernet",
    )
    gmail_refresh_token_encrypted = models.TextField(
        blank=True,
        null=True,
        db_column='gmail_refresh_token_encrypted',
        help_text="Google OAuth2 Offline Refresh Token encriptado con Fernet",
    )
    gmail_sender_email = models.CharField(
        max_length=254,
        blank=True,
        null=True,
        db_column='gmail_sender_email',
        help_text="Correo remitente institucional autorizado para despachos",
    )
    gmail_api_enabled = models.BooleanField(
        default=False,
        db_column='gmail_api_enabled',
        help_text="Interruptor de integración de Gmail API",
    )
    gmail_redirect_uri = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        default='http://127.0.0.1:8000/security/oauth2/gmail/callback/',
        db_column='gmail_redirect_uri',
        help_text="OAuth2 Redirect URI callback",
    )
    last_token_refresh = models.DateTimeField(
        blank=True,
        null=True,
        db_column='last_token_refresh',
        help_text="Timestamp de la última renovación del token de acceso",
    )
    updated_at_utc = models.DateTimeField(auto_now=True, db_column='updated_at_utc')
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='updated_by_id',
        related_name='updated_settings',
    )

    class Meta:
        db_table = 'security"."system_setting'
        verbose_name = 'System Setting'
        verbose_name_plural = 'System Settings'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete(SYSTEM_SETTING_CACHE_KEY)

    def delete(self, *args, **kwargs):
        res = super().delete(*args, **kwargs)
        cache.delete(SYSTEM_SETTING_CACHE_KEY)
        return res

    def __str__(self):
        status = 'ACTIVO' if self.chatbot_enabled else 'INACTIVO'
        role_name = self.role.name if self.role_id else 'Sin rol'
        return f"Configuración ({role_name} · Chatbot: {status})"

    @classmethod
    def get_admin_role(cls) -> Role:
        """Obtiene o crea el rol exclusivo Administrador."""
        role, _ = Role.objects.get_or_create(
            name=ADMIN_ROLE_NAME,
            defaults={
                'description': 'Rol administrativo con acceso exclusivo a credenciales de API y configuración del sistema',
                'status': Role.Status.ACTIVE,
            },
        )
        return role

    def is_role_authorized(self, user) -> bool:
        """
        Valida que el usuario pertenezca de forma activa al rol vinculado
        a esta configuración (o sea superusuario).
        """
        if not user or not getattr(user, 'is_authenticated', False):
            return False
        if not self.role_id or self.role.status != Role.Status.ACTIVE:
            return False
        if getattr(user, 'is_superuser', False):
            return True
        return UserRole.objects.filter(
            user=user,
            role_id=self.role_id,
            status=UserRole.Status.ACTIVE,
        ).exists()

    @classmethod
    def get_settings(cls):
        """
        Retorna la configuración única vinculada al rol Administrador usando caché
        de Django con invalidación automática al guardar o eliminar.
        """
        cached = cache.get(SYSTEM_SETTING_CACHE_KEY)
        if cached is not None:
            return cached
        admin_role = cls.get_admin_role()
        obj, _ = cls.objects.select_related('role').get_or_create(
            role=admin_role,
            defaults={
                'chatbot_enabled': True,
                'active_llm_provider': 'gemini',
                'gemini_api_key_encrypted': '',
                'gemini_model': DEFAULT_GEMINI_MODEL,
                'gemini_enabled': True,
                'openai_api_key_encrypted': '',
                'openai_model': DEFAULT_OPENAI_MODEL,
                'openai_enabled': False,
                'claude_api_key_encrypted': '',
                'claude_model': DEFAULT_CLAUDE_MODEL,
                'claude_enabled': False,
                'gmail_client_id': '',
                'gmail_client_secret_encrypted': '',
                'gmail_refresh_token_encrypted': '',
                'gmail_sender_email': '',
                'gmail_api_enabled': False,
            },
        )
        cache.set(SYSTEM_SETTING_CACHE_KEY, obj, timeout=300)
        return obj

    @classmethod
    def is_chatbot_enabled(cls) -> bool:
        """
        Consulta si el chatbot está habilitado. Falla cerrado (False) ante errores
        de acceso a base de datos por seguridad clínica.
        """
        try:
            return cls.get_settings().chatbot_enabled
        except Exception:
            logger.exception("Error consultando estado del chatbot en SystemSetting; fallando cerrado.")
            return False

    @classmethod
    def get_gemini_api_key(cls, user=None, check_enabled=True) -> str:
        """
        Retorna la clave API descifrada de Google Gemini si está habilitada.
        """
        try:
            cfg = cls.get_settings()
            if check_enabled and not cfg.gemini_enabled:
                return ''
            if not cfg.role_id or cfg.role.status != Role.Status.ACTIVE:
                return ''
            if user is not None and not cfg.is_role_authorized(user):
                return ''
            if cfg.gemini_api_key_encrypted:
                return decrypt_api_key(cfg.gemini_api_key_encrypted)
        except Exception:
            logger.exception("Error obteniendo la Gemini API key desde SystemSetting.")
        return ''

    @classmethod
    def get_openai_api_key(cls, user=None, check_enabled=True) -> str:
        """
        Retorna la clave API descifrada de OpenAI (ChatGPT) si está habilitada.
        """
        try:
            cfg = cls.get_settings()
            if check_enabled and not cfg.openai_enabled:
                return ''
            if not cfg.role_id or cfg.role.status != Role.Status.ACTIVE:
                return ''
            if user is not None and not cfg.is_role_authorized(user):
                return ''
            if cfg.openai_api_key_encrypted:
                return decrypt_api_key(cfg.openai_api_key_encrypted)
        except Exception:
            logger.exception("Error obteniendo la OpenAI API key desde SystemSetting.")
        return ''

    @classmethod
    def get_claude_api_key(cls, user=None, check_enabled=True) -> str:
        """
        Retorna la clave API descifrada de Anthropic Claude si está habilitada.
        """
        try:
            cfg = cls.get_settings()
            if check_enabled and not cfg.claude_enabled:
                return ''
            if not cfg.role_id or cfg.role.status != Role.Status.ACTIVE:
                return ''
            if user is not None and not cfg.is_role_authorized(user):
                return ''
            if cfg.claude_api_key_encrypted:
                return decrypt_api_key(cfg.claude_api_key_encrypted)
        except Exception:
            logger.exception("Error obteniendo la Claude API key desde SystemSetting.")
        return ''

    @classmethod
    def get_gmail_client_secret(cls, user=None) -> str:
        """
        Retorna el client secret descifrado de Gmail OAuth2.
        """
        try:
            cfg = cls.get_settings()
            if not cfg.role_id or cfg.role.status != Role.Status.ACTIVE:
                return ''
            if user is not None and not cfg.is_role_authorized(user):
                return ''
            if cfg.gmail_client_secret_encrypted:
                return decrypt_api_key(cfg.gmail_client_secret_encrypted)
        except Exception:
            logger.exception("Error obteniendo Gmail client secret desde SystemSetting.")
        return ''

    @classmethod
    def get_gmail_refresh_token(cls, user=None) -> str:
        """
        Retorna el refresh token descifrado de Gmail OAuth2.
        """
        try:
            cfg = cls.get_settings()
            if not cfg.role_id or cfg.role.status != Role.Status.ACTIVE:
                return ''
            if user is not None and not cfg.is_role_authorized(user):
                return ''
            if cfg.gmail_refresh_token_encrypted:
                return decrypt_api_key(cfg.gmail_refresh_token_encrypted)
        except Exception:
            logger.exception("Error obteniendo Gmail refresh token desde SystemSetting.")
        return ''

    @classmethod
    def set_settings(
        cls,
        chatbot_enabled: bool = None,
        active_llm_provider: str = None,
        raw_api_key: str = None,
        model: str = None,
        gemini_enabled: bool = None,
        raw_openai_key: str = None,
        openai_model: str = None,
        openai_enabled: bool = None,
        raw_claude_key: str = None,
        claude_model: str = None,
        claude_enabled: bool = None,
        gmail_client_id: str = None,
        raw_gmail_secret: str = None,
        raw_gmail_refresh_token: str = None,
        gmail_sender_email: str = None,
        gmail_api_enabled: bool = None,
        gmail_redirect_uri: str = None,
        user=None
    ):
        """
        Actualiza la configuración del sistema validando autorización del rol Administrador.
        Lanza PermissionDenied si un usuario sin autorización intenta modificarla.
        """
        cfg = cls.get_settings()
        if user is not None and not cfg.is_role_authorized(user):
            raise PermissionDenied("Solo el rol Administrador puede modificar la configuración del sistema.")

        if chatbot_enabled is not None:
            cfg.chatbot_enabled = bool(chatbot_enabled)
        if active_llm_provider is not None:
            cfg.active_llm_provider = active_llm_provider.strip().lower()

        # Google Gemini
        if raw_api_key is not None:
            cfg.gemini_api_key_encrypted = encrypt_api_key(raw_api_key)
        if model:
            cfg.gemini_model = model.strip()
        if gemini_enabled is not None:
            cfg.gemini_enabled = bool(gemini_enabled)

        # OpenAI / ChatGPT
        if raw_openai_key is not None:
            cfg.openai_api_key_encrypted = encrypt_api_key(raw_openai_key)
        if openai_model:
            cfg.openai_model = openai_model.strip()
        if openai_enabled is not None:
            cfg.openai_enabled = bool(openai_enabled)

        # Anthropic Claude
        if raw_claude_key is not None:
            cfg.claude_api_key_encrypted = encrypt_api_key(raw_claude_key)
        if claude_model:
            cfg.claude_model = claude_model.strip()
        if claude_enabled is not None:
            cfg.claude_enabled = bool(claude_enabled)

        # Gmail REST API
        if gmail_client_id is not None:
            cfg.gmail_client_id = gmail_client_id.strip()
        if raw_gmail_secret is not None:
            cfg.gmail_client_secret_encrypted = encrypt_api_key(raw_gmail_secret)
        if raw_gmail_refresh_token is not None:
            cfg.gmail_refresh_token_encrypted = encrypt_api_key(raw_gmail_refresh_token)
        if gmail_sender_email is not None:
            cfg.gmail_sender_email = gmail_sender_email.strip()
        if gmail_api_enabled is not None:
            cfg.gmail_api_enabled = bool(gmail_api_enabled)
        if gmail_redirect_uri is not None:
            cfg.gmail_redirect_uri = gmail_redirect_uri.strip()

        if user and getattr(user, 'is_authenticated', False):
            cfg.updated_by = user

        cfg.save()
        return cfg
