import logging

from security.models import DEFAULT_GEMINI_MODEL, SystemSetting

logger = logging.getLogger(__name__)


def clinical_access(request):
    from security.access import clinical_capabilities, has_dashboard_access, has_pdf_access

    capabilities = getattr(request, 'clinical_capabilities', None)
    if capabilities is None:
        capabilities = clinical_capabilities(request.user)
    ui_access = dict(capabilities)
    ui_access['dashboard'] = has_dashboard_access(request.user)
    ui_access['pdf'] = has_pdf_access(request.user)
    return {'clinical_access': ui_access}


def global_system_settings(request):
    """
    Context processor para exponer el estado del chatbot y del Modo Rol en las plantillas.
    Falla cerrado (chatbot_enabled=False, role_mode_enabled=True) si ocurre un error al consultar BD.
    """
    try:
        cfg = SystemSetting.get_settings()
        return {
            'chatbot_enabled': cfg.chatbot_enabled,
            'role_mode_enabled': cfg.role_mode_enabled,
            'gemini_model': cfg.gemini_model,
        }
    except Exception:
        logger.exception("Error cargando SystemSetting en context_processor; fallando cerrado.")
        return {
            'chatbot_enabled': False,
            'role_mode_enabled': True,
            'gemini_model': DEFAULT_GEMINI_MODEL,
        }
