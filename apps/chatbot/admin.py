from django.contrib import admin
from .models import BotQuery


@admin.register(BotQuery)
class BotQueryAdmin(admin.ModelAdmin):
    list_display = (
        'bot_query_id',
        'user',
        'user_question_snippet',
        'tokens_used',
        'execution_time_ms',
        'created_at',
    )
    list_filter = ('created_at', 'user')
    search_fields = ('user_question', 'bot_response', 'generated_sql', 'user__username')
    readonly_fields = (
        'bot_query_id',
        'user',
        'user_question',
        'generated_sql',
        'bot_response',
        'tokens_used',
        'execution_time_ms',
        'created_at',
    )

    def user_question_snippet(self, obj):
        return obj.user_question[:60] + '...' if len(obj.user_question) > 60 else obj.user_question
    user_question_snippet.short_description = "Pregunta del Usuario"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
