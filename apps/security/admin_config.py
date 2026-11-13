from django.contrib.admin.apps import AdminConfig


class ClinicalAdminConfig(AdminConfig):
    default_site = 'security.admin_site.ClinicalAdminSite'
