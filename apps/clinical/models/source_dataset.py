import uuid

from django.db import models


class SourceDataset(models.Model):
    """Immutable schema metadata for a dataset imported from SPSS/R/CSV."""

    source_dataset_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    filename = models.CharField(max_length=255, blank=True, default='')
    column_names = models.JSONField(default=list)
    column_labels = models.JSONField(default=dict)
    value_labels = models.JSONField(default=dict)
    original_variable_types = models.JSONField(default=dict)
    variable_display_width = models.JSONField(default=dict)
    variable_measure = models.JSONField(default=dict)
    missing_ranges = models.JSONField(default=dict)
    file_label = models.TextField(blank=True, default='')
    file_encoding = models.CharField(max_length=32, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'clinical"."source_dataset'
        ordering = ['created_at', 'pk']

    def __str__(self):
        return self.filename or str(self.source_dataset_id)


class SourceDatasetRow(models.Model):
    """Original imported row, retained even if clinical identity de-duplicates it."""

    source_dataset = models.ForeignKey(SourceDataset, on_delete=models.CASCADE, related_name='rows')
    visit = models.ForeignKey(
        'clinical.Visit',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='source_rows',
    )
    row_index = models.PositiveIntegerField()
    row_data = models.JSONField(default=dict)

    class Meta:
        db_table = 'clinical"."source_dataset_row'
        constraints = [
            models.UniqueConstraint(fields=['source_dataset', 'row_index'], name='uq_source_dataset_row_index'),
        ]
        ordering = ['row_index', 'pk']
