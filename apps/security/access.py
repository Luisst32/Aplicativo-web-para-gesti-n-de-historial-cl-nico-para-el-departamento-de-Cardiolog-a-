"""Clinical and dashboard action permissions, shared by HTTP endpoints and the assistant.

Supports two institutional operating modes controlled exclusively by Administrador
in SystemSetting.role_mode_enabled ("Modo Rol"):
- Modo Rol ACTIVO (True):
  * Administrador: full clinical, dashboard, and system settings access.
  * Cardiólogo: read, create, change, delete, share (NO import, NO export, NO dashboard).
  * Departamento de Estadística: read, import, export, share, dashboard (NO create, NO change, NO delete).
  * Custom roles / explicit Django permissions: evaluated strictly from granted permissions.
- Modo Rol DESACTIVADO (False):
  * All active authenticated users have free access to clinical and dashboard actions,
    while Administrator settings remain strictly exclusive to Administrador.
"""
from functools import wraps

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse

from security.models import (
    CARDIOLOGO_ROLE_NAME,
    ESTADISTICA_ROLE_NAME,
    Role,
    SystemSetting,
    User,
    UserRole,
)


READ = frozenset({'clinical.view_patient', 'clinical.view_visit'})
ACTION_PERMISSIONS = {
    'read': READ,
    'create': READ | {'clinical.add_patient', 'clinical.add_visit'},
    'change': READ | {'clinical.change_patient', 'clinical.change_visit'},
    'delete': READ | {'clinical.delete_patient', 'clinical.delete_visit'},
    'export': READ | {'clinical.export_clinical_data'},
    'import': READ | {'clinical.import_clinical_data'},
    'share': READ | {'clinical.add_secureshare'},
}
DENIED_MESSAGE = 'No cuenta con los privilegios clínicos requeridos para esta operación.'

CARDIOLOGO_ALIASES = frozenset({
    CARDIOLOGO_ROLE_NAME.lower(),
    'cardiologo',
})
ESTADISTICA_ALIASES = frozenset({
    ESTADISTICA_ROLE_NAME.lower(),
    'departamento de estadistica',
    'estadística',
    'estadistica',
})

ROLE_CAPABILITY_PROFILES = {
    'cardiologo': {
        'read': True,
        'create': True,
        'change': True,
        'delete': True,
        'export': False,
        'import': False,
        'share': True,
    },
    'estadistica': {
        'read': True,
        'create': False,
        'change': False,
        'delete': False,
        'export': True,
        'import': True,
        'share': True,
    },
}


def is_active_user(user):
    return bool(
        user and user.is_authenticated and user.is_active
        and user.status == User.Status.ACTIVE
    )


def _active_role_names_lower(user) -> set:
    return {
        name.strip().lower()
        for name in Role.objects.filter(
            userrole__user=user,
            userrole__status=UserRole.Status.ACTIVE,
            status=Role.Status.ACTIVE,
        ).values_list('name', flat=True)
        if name
    }


def clinical_capabilities(user):
    """Read current grants, without Django's persistent per-user permission cache."""
    if not is_active_user(user):
        return dict.fromkeys(ACTION_PERMISSIONS, False)
    if user.is_administrator:
        return dict.fromkeys(ACTION_PERMISSIONS, True)
    if not SystemSetting.is_role_mode_enabled():
        return dict.fromkeys(ACTION_PERMISSIONS, True)

    role_names = _active_role_names_lower(user)
    matched_profiles = []
    if role_names & CARDIOLOGO_ALIASES:
        matched_profiles.append(ROLE_CAPABILITY_PROFILES['cardiologo'])
    if role_names & ESTADISTICA_ALIASES:
        matched_profiles.append(ROLE_CAPABILITY_PROFILES['estadistica'])

    if matched_profiles:
        return {
            action: any(profile.get(action, False) for profile in matched_profiles)
            for action in ACTION_PERMISSIONS
        }

    permissions = Permission.objects.filter(
        Q(user=user) | Q(group__user=user) | Q(
            clinical_roles__userrole__user=user,
            clinical_roles__userrole__status=UserRole.Status.ACTIVE,
            clinical_roles__status=Role.Status.ACTIVE,
        ),
        content_type__app_label='clinical',
    ).values_list('content_type__app_label', 'codename').distinct()
    grants = {f'{app}.{codename}' for app, codename in permissions}
    return {action: required <= grants for action, required in ACTION_PERMISSIONS.items()}


def has_dashboard_access(user) -> bool:
    """Determine whether the user can see and enter the epidemiological Dashboard."""
    if not is_active_user(user):
        return False
    if user.is_administrator:
        return True
    if not SystemSetting.is_role_mode_enabled():
        return True

    role_names = _active_role_names_lower(user)
    if role_names & ESTADISTICA_ALIASES:
        return True
    if role_names & CARDIOLOGO_ALIASES:
        return False

    return clinical_capabilities(user)['read']


def has_pdf_access(user) -> bool:
    """Determine whether the user can view and download clinical sheet PDFs."""
    if not is_active_user(user):
        return False
    if user.is_administrator:
        return True
    if not SystemSetting.is_role_mode_enabled():
        return True

    role_names = _active_role_names_lower(user)
    if role_names & (CARDIOLOGO_ALIASES | ESTADISTICA_ALIASES):
        return True

    return clinical_capabilities(user)['export']


def has_clinical_access(user, action='read'):
    if action == 'dashboard':
        return has_dashboard_access(user)
    if action == 'pdf':
        return has_pdf_access(user)
    return clinical_capabilities(user)[action]


def require_clinical_access(user, action='read'):
    if not has_clinical_access(user, action):
        raise PermissionDenied(DENIED_MESSAGE)


def clinical_access_required(action='read', *, api=False):
    if action not in ('dashboard', 'pdf') and action not in ACTION_PERMISSIONS:
        raise ValueError(f'Unknown clinical action: {action}')

    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            capabilities = clinical_capabilities(request.user)
            request.clinical_capabilities = capabilities
            if action == 'dashboard':
                allowed = has_dashboard_access(request.user)
            elif action == 'pdf':
                allowed = has_pdf_access(request.user)
            else:
                allowed = capabilities[action]
            if not allowed:
                if api:
                    authenticated = bool(request.user and request.user.is_authenticated)
                    return JsonResponse({
                        'success': False,
                        'status': 'forbidden' if authenticated else 'unauthorized',
                        'message': DENIED_MESSAGE,
                        'error': DENIED_MESSAGE,
                        'response': DENIED_MESSAGE,
                    }, status=403 if authenticated else 401)
                raise PermissionDenied(DENIED_MESSAGE)
            return view(request, *args, **kwargs)
        return wrapped
    return decorate


def dashboard_access_required(*, api=False):
    return clinical_access_required('dashboard', api=api)
