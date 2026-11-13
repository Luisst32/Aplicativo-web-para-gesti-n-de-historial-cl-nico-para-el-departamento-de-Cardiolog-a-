from django.contrib.admin import AdminSite

from security.access import is_active_user


class ClinicalAdminSite(AdminSite):
    """Back-office access is restricted to active system administrators."""

    def has_permission(self, request):
        user = request.user
        return bool(is_active_user(user) and user.is_staff and user.is_administrator)
