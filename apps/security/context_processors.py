import logging

from security.models import DEFAULT_GEMINI_MODEL, SystemSetting

logger = logging.getLogger(__name__)


def clinical_access(request):
    from security.access import clinical_capabilities

    capabilities = getattr(request, 'clinical_capabilities', None)
    if capabilities is None:
        capabilities = clinical_capabilities(request.user)
    return {'clinical_access': capabilities}


def global_system_settings(request):
    """
    Context processor para exponer el estado del chatbot en las plantillas.
    Falla cerrado (chatbot_enabled=False) si ocurre un error al consultar BD.
    """
    try:
        cfg = SystemSetting.get_settings()
        return {
            'chatbot_enabled': cfg.chatbot_enabled,
            'gemini_model': cfg.gemini_model,
        }
    except Exception:
        logger.exception("Error cargando SystemSetting en context_processor; fallando cerrado.")
        return {
            'chatbot_enabled': False,
            'gemini_model': DEFAULT_GEMINI_MODEL,
        }
