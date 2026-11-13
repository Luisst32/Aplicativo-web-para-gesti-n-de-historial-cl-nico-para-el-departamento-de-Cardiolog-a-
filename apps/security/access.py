"""Clinical action permissions, shared by HTTP endpoints and the assistant.

An authorized clinician can access every institution in the cohort. Institution
membership is not an authorization grant. Role names (except Administrador) and
is_staff are not clinical permissions either.
"""
from functools import wraps

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse

from security.models import Role, User, UserRole


READ = frozenset({'clinical.view_patient', 'clinical.view_visit'})
ACTION_PERMISSIONS = {
    'read': READ,
    'create': READ | {'clinical.add_patient', 'clinical.add_visit'},
    'change': READ | {'clinical.change_patient', 'clinical.change_visit'},
    'delete': READ | {'clinical.delete_patient', 'clinical.delete_visit'},
    'export': READ | {'clinical.export_clinical_data'},
    'import': READ | {
        'clinical.add_patient', 'clinical.add_visit',
        'clinical.change_patient', 'clinical.change_visit',
        'clinical.import_clinical_data',
    },
    'share': READ | {'clinical.export_clinical_data', 'clinical.add_secureshare'},
}
DENIED_MESSAGE = 'No cuenta con los privilegios clínicos requeridos para esta operación.'


def is_active_user(user):
    return bool(
        user and user.is_authenticated and user.is_active
        and user.status == User.Status.ACTIVE
    )


def clinical_capabilities(user):
    """Read current grants, without Django's persistent per-user permission cache."""
    if not is_active_user(user):
        return dict.fromkeys(ACTION_PERMISSIONS, False)
    if user.is_administrator:
        return dict.fromkeys(ACTION_PERMISSIONS, True)

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


def has_clinical_access(user, action='read'):
    return clinical_capabilities(user)[action]


def require_clinical_access(user, action='read'):
    if not has_clinical_access(user, action):
        raise PermissionDenied(DENIED_MESSAGE)


def clinical_access_required(action='read', *, api=False):
    if action not in ACTION_PERMISSIONS:
        raise ValueError(f'Unknown clinical action: {action}')

    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            capabilities = clinical_capabilities(request.user)
            request.clinical_capabilities = capabilities
            if not capabilities[action]:
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
