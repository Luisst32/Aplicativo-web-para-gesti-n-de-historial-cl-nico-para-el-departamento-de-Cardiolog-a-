from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager


class Rol(models.Model):
    """Rol de acceso y privilegios en el sistema (Esquema seguridad.Rol)."""
    rol_id = models.AutoField(primary_key=True, db_column='rolid')
    nombre = models.CharField(max_length=50, unique=True, db_column='nombre')
    descripcion = models.CharField(max_length=200, blank=True, null=True, db_column='descripcion')

    class Meta:
        db_table = '"seguridad"."rol"'
        verbose_name = "Rol"
        verbose_name_plural = "Roles"

    def __str__(self):
        return self.nombre


class UsuarioManager(BaseUserManager):
    """Manager para el modelo Usuario personalizado."""
    def create_user(self, nombre_usuario, correo_electronico, password=None, **extra_fields):
        if not nombre_usuario:
            raise ValueError('El nombre de usuario es obligatorio.')
        if not correo_electronico:
            raise ValueError('El correo electrónico es obligatorio.')

        correo_electronico = self.normalize_email(correo_electronico)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)

        user = self.model(
            nombre_usuario=nombre_usuario,
            correo_electronico=correo_electronico,
            **extra_fields
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, nombre_usuario, correo_electronico, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('El superusuario debe tener is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('El superusuario debe tener is_superuser=True.')

        return self.create_user(nombre_usuario, correo_electronico, password, **extra_fields)


class Usuario(AbstractBaseUser, PermissionsMixin):
    """
    Modelo de Usuario institucional integrado con el sistema de autenticación de Django.
    Mapeado a la tabla seguridad.Usuario.
    """
    usuario_id = models.AutoField(primary_key=True, db_column='usuarioid')
    institucion_id = models.IntegerField(default=1, db_column='institucionid', help_text="ID de la Institución (catalogo.Institucion)")
    nombre_usuario = models.CharField(max_length=50, unique=True, db_column='nombreusuario')
    correo_electronico = models.EmailField(max_length=100, unique=True, db_column='correoelectronico')
    nombres = models.CharField(max_length=100, db_column='nombres')
    primer_apellido = models.CharField(max_length=50, db_column='primerapellido')
    segundo_apellido = models.CharField(max_length=50, blank=True, null=True, db_column='segundoapellido')
    
    # Campo heredado last_login mapeado a columna FechaUltimoAccesoUtc
    last_login = models.DateTimeField(blank=True, null=True, db_column='fechaultimoaccesoutc')
    fecha_creacion_utc = models.DateTimeField(auto_now_add=True, db_column='fechacreacionutc')

    # Banderas de control de Django Auth
    is_active = models.BooleanField(default=True, db_column='is_active')
    is_staff = models.BooleanField(default=False, db_column='is_staff')

    # Relación de roles a través de tabla puente UsuarioRol
    roles = models.ManyToManyField(Rol, through='UsuarioRol', related_name='usuarios')

    objects = UsuarioManager()

    USERNAME_FIELD = 'nombre_usuario'
    REQUIRED_FIELDS = ['correo_electronico', 'nombres', 'primer_apellido']
    EMAIL_FIELD = 'correo_electronico'

    class Meta:
        db_table = '"seguridad"."usuario"'
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        return f"{self.nombre_usuario} ({self.nombres} {self.primer_apellido})"

    @property
    def nombre_completo(self):
        apellidos = f"{self.primer_apellido} {self.segundo_apellido or ''}".strip()
        return f"{self.nombres} {apellidos}"


class UsuarioRol(models.Model):
    """Tabla asociativa para asignación de roles a usuarios (Esquema seguridad.UsuarioRol)."""
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, db_column='usuarioid')
    rol = models.ForeignKey(Rol, on_delete=models.RESTRICT, db_column='rolid')
    fecha_asignacion_utc = models.DateTimeField(auto_now_add=True, db_column='fechaasignacionutc')

    class Meta:
        db_table = '"seguridad"."usuariorol"'
        unique_together = (('usuario', 'rol'),)
        verbose_name = "Rol de Usuario"
        verbose_name_plural = "Roles de Usuarios"

    def __str__(self):
        return f"{self.usuario.nombre_usuario} - {self.rol.nombre}"
