from django.db import models


class BotQuery(models.Model):
    """
    AI Clinical Assistant Queries and Interactions Log (ia.ConsultaBot).
    Records user clinical questions, optional generated SQL analytical queries,
    assistant responses, token consumption, and response latency.
    """
    bot_query_id = models.BigAutoField(primary_key=True, db_column='bot_query_id')
    user = models.ForeignKey(
        'security.User',
        on_delete=models.RESTRICT,
        db_column='user_id',
        related_name='bot_queries',
        help_text="User who submitted the clinical question"
    )
    user_question = models.TextField(
        db_column='user_question',
        help_text="Natural language question submitted by the user"
    )
    generated_sql = models.TextField(
        blank=True,
        null=True,
        db_column='generated_sql',
        help_text="Analytical SQL query generated to inspect clinical data (if applicable)"
    )
    bot_response = models.TextField(
        db_column='bot_response',
        help_text="Formatted response produced by the AI assistant"
    )
    tokens_used = models.IntegerField(
        blank=True,
        null=True,
        db_column='tokens_used',
        help_text="Total tokens consumed in the LLM completion"
    )
    execution_time_ms = models.IntegerField(
        blank=True,
        null=True,
        db_column='execution_time_ms',
        help_text="Response generation latency in milliseconds"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_column='created_at_utc',
        help_text="Timestamp when query was processed"
    )

    class Meta:
        db_table = 'ai"."bot_query'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at'], name='ix_bot_query_user_created'),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(tokens_used__isnull=True) | models.Q(tokens_used__gte=0),
                name='ck_bot_query_tokens'
            ),
            models.CheckConstraint(
                condition=models.Q(execution_time_ms__isnull=True) | models.Q(execution_time_ms__gte=0),
                name='ck_bot_query_time'
            )
        ]
        verbose_name = "Bot Query"
        verbose_name_plural = "Bot Queries"

    def __str__(self):
        snippet = self.user_question[:40] + '...' if len(self.user_question) > 40 else self.user_question
        return f"[{self.bot_query_id}] {self.user.username}: {snippet}"
