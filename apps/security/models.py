from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.conf import settings
import base64
import hashlib
from cryptography.fernet import Fernet


class Role(models.Model):
    """
    Role definition for security and access control (Mapped to security.role).
    """
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
        db_column='status'
    )

    class Meta:
        db_table = 'security"."role'
        verbose_name = "Role"
        verbose_name_plural = "Roles"

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    """
    Custom manager for institutional User model.
    """
    def create_user(self, username, email, password=None, **extra_fields):
        if not username:
            raise ValueError('The Username field is required.')
        if not email:
            raise ValueError('The Email field is required.')

        email = self.normalize_email(email)
        extra_fields.setdefault('status', 'ACTIVE')
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)

        user = self.model(
            username=username,
            email=email,
            **extra_fields
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('status', 'ACTIVE')
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(username, email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Institutional User model integrated with Django authentication system.
    Mapped to security.user table.
    """
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
        help_text="Institution the user belongs to (nullable for superadmin)"
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
        db_column='status'
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
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return f"{self.username} ({self.first_name} {self.last_name})"

    @property
    def full_name(self):
        last_names = f"{self.last_name} {self.second_last_name or ''}".strip()
        return f"{self.first_name} {last_names}"


class UserRole(models.Model):
    """
    Association table between User and Role (Mapped to security.user_role).
    """
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
        db_column='status'
    )

    class Meta:
        db_table = 'security"."user_role'
        constraints = [
            models.UniqueConstraint(fields=['user', 'role'], name='unique_user_role')
        ]
        verbose_name = "User Role"
        verbose_name_plural = "User Roles"

    def __str__(self):
        return f"{self.user.username} - {self.role.name}"


def _get_fernet_cipher():
    secret = getattr(settings, 'SECRET_KEY', 'default-insecure-key-cardiounemi')
    key_bytes = hashlib.sha256(secret.encode('utf-8')).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))


def encrypt_api_key(raw_key: str) -> str:
    if not raw_key or not raw_key.strip():
        return ""
    cipher = _get_fernet_cipher()
    return cipher.encrypt(raw_key.strip().encode('utf-8')).decode('utf-8')


def decrypt_api_key(enc_key: str) -> str:
    if not enc_key or not enc_key.strip():
        return ""
    cipher = _get_fernet_cipher()
    try:
        return cipher.decrypt(enc_key.strip().encode('utf-8')).decode('utf-8')
    except Exception:
        # Fallback si ya estuviera en texto plano o corrupted
        return enc_key.strip()


class SystemSetting(models.Model):
    """
    Tabla global de configuración del sistema (security.system_setting).
    Guarda ajustes globales institucionales, switch del chatbot y la API Key encriptada.
    """
    setting_id = models.AutoField(primary_key=True, db_column='setting_id')
    chatbot_enabled = models.BooleanField(
        default=True,
        db_column='chatbot_enabled',
        help_text="Interruptor global para activar o desactivar el Asistente Clínico con IA"
    )
    gemini_api_key_encrypted = models.TextField(
        blank=True,
        null=True,
        db_column='gemini_api_key_encrypted',
        help_text="Clave de API de Google Gemini encriptada con Fernet (AES-128-CBC + HMAC)"
    )
    gemini_model = models.CharField(
        max_length=60,
        default='gemini-3.5-flash-lite',
        db_column='gemini_model',
        help_text="Modelo por defecto de Gemini Flash"
    )
    updated_at_utc = models.DateTimeField(auto_now=True, db_column='updated_at_utc')
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='updated_by_id',
        related_name='updated_settings'
    )

    class Meta:
        app_label = 'security'
        db_table = 'security"."system_setting'
        verbose_name = "System Setting"
        verbose_name_plural = "System Settings"

    def __str__(self):
        status = "ACTIVO" if self.chatbot_enabled else "INACTIVO"
        return f"Configuración Global (Chatbot: {status})"

    @classmethod
    def get_settings(cls):
        obj = cls.objects.first()
        if not obj:
            # Sembrar inicialmente con .env si existe clave previa
            import os
            env_key = os.getenv('GEMINI_API_KEY', '').strip()
            enc_key = encrypt_api_key(env_key) if env_key else ""
            obj = cls.objects.create(
                chatbot_enabled=True,
                gemini_api_key_encrypted=enc_key,
                gemini_model=os.getenv('GEMINI_MODEL', 'gemini-3.5-flash-lite').strip()
            )
        return obj

    @classmethod
    def is_chatbot_enabled(cls) -> bool:
        try:
            return cls.get_settings().chatbot_enabled
        except Exception:
            return True

    @classmethod
    def get_gemini_api_key(cls) -> str:
        try:
            cfg = cls.get_settings()
            if cfg.gemini_api_key_encrypted:
                decrypted = decrypt_api_key(cfg.gemini_api_key_encrypted)
                if decrypted:
                    return decrypted
        except Exception:
            pass
        # Fallback a .env
        import os
        return os.getenv('GEMINI_API_KEY', '').strip()

    @classmethod
    def set_settings(cls, chatbot_enabled: bool, raw_api_key: str = None, model: str = None, user=None):
        cfg = cls.get_settings()
        cfg.chatbot_enabled = bool(chatbot_enabled)
        if raw_api_key is not None:
            raw_key_clean = raw_api_key.strip()
            if raw_key_clean:
                cfg.gemini_api_key_encrypted = encrypt_api_key(raw_key_clean)
            elif raw_api_key == "":
                cfg.gemini_api_key_encrypted = ""
        if model:
            cfg.gemini_model = model.strip()
        if user and getattr(user, 'is_authenticated', False):
            cfg.updated_by = user
        cfg.save()
        return cfg
