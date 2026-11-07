from security.models import SystemSetting


def global_system_settings(request):
    """
    Context processor para exponer el estado del chatbot y la configuración
    global en todas las plantillas del aplicativo.
    """
    try:
        cfg = SystemSetting.get_settings()
        return {
            'chatbot_enabled': cfg.chatbot_enabled,
            'gemini_model': cfg.gemini_model
        }
    except Exception:
        return {
            'chatbot_enabled': True,
            'gemini_model': 'gemini-3.5-flash-lite'
        }

