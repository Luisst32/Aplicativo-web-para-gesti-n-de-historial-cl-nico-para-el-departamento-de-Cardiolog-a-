import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('clinical', '0012_sanitize_patient_birth_dates'),
    ]

    operations = [
        migrations.CreateModel(
            name='SourceDataset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_dataset_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('filename', models.CharField(blank=True, default='', max_length=255)),
                ('column_names', models.JSONField(default=list)),
                ('column_labels', models.JSONField(default=dict)),
                ('value_labels', models.JSONField(default=dict)),
                ('original_variable_types', models.JSONField(default=dict)),
                ('variable_display_width', models.JSONField(default=dict)),
                ('variable_measure', models.JSONField(default=dict)),
                ('missing_ranges', models.JSONField(default=dict)),
                ('file_label', models.TextField(blank=True, default='')),
                ('file_encoding', models.CharField(blank=True, default='', max_length=32)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'clinical"."source_dataset',
                'ordering': ['created_at', 'pk'],
            },
        ),
        migrations.AddField(
            model_name='visit',
            name='source_dataset',
            field=models.ForeignKey(blank=True, db_column='source_dataset_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='visits', to='clinical.sourcedataset'),
        ),
        migrations.AddField(
            model_name='visit',
            name='source_row_data',
            field=models.JSONField(blank=True, db_column='source_row_data', null=True),
        ),
        migrations.AddField(
            model_name='visit',
            name='source_row_index',
            field=models.PositiveIntegerField(blank=True, db_column='source_row_index', null=True),
        ),
        migrations.CreateModel(
            name='SourceDatasetRow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('row_index', models.PositiveIntegerField()),
                ('row_data', models.JSONField(default=dict)),
                ('source_dataset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rows', to='clinical.sourcedataset')),
                ('visit', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='source_rows', to='clinical.visit')),
            ],
            options={
                'db_table': 'clinical"."source_dataset_row',
                'ordering': ['row_index', 'pk'],
            },
        ),
        migrations.AddConstraint(
            model_name='sourcedatasetrow',
            constraint=models.UniqueConstraint(fields=('source_dataset', 'row_index'), name='uq_source_dataset_row_index'),
        ),
    ]
