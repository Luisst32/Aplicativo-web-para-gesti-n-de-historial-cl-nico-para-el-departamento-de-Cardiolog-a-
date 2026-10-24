from django.contrib import admin
from .models import (
    Patient,
    Visit,
    Anthropometry,
    VitalSigns,
    Electrocardiogram,
    Echocardiogram,
    Laboratory,
    VisitAnswer,
)


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = (
        'patient_id',
        'id_card',
        'first_names',
        'last_name1',
        'last_name2',
        'status',
        'sex',
        'birth_date',
        'institution',
        'created_at',
    )
    search_fields = (
        'id_card',
        'first_names',
        'last_name1',
        'last_name2',
        'email',
        'phone',
    )
    list_filter = ('status', 'institution', 'sex', 'ethnicity')
    ordering = ('last_name1', 'first_names')


class AnthropometryInline(admin.StackedInline):
    model = Anthropometry
    can_delete = False
    extra = 0


class VitalSignsInline(admin.StackedInline):
    model = VitalSigns
    can_delete = False
    extra = 0


class ElectrocardiogramInline(admin.StackedInline):
    model = Electrocardiogram
    can_delete = False
    extra = 0


class EchocardiogramInline(admin.StackedInline):
    model = Echocardiogram
    can_delete = False
    extra = 0


class LaboratoryInline(admin.StackedInline):
    model = Laboratory
    can_delete = False
    extra = 0


class VisitAnswerInline(admin.TabularInline):
    model = VisitAnswer
    extra = 0
    fields = ('question', 'selected_option', 'numeric_value', 'text_value')


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = (
        'visit_id',
        'study_code',
        'patient',
        'evaluator',
        'visit_date',
        'status',
        'study_year',
        'visit_number',
    )
    search_fields = (
        'study_code',
        'patient__id_card',
        'patient__first_names',
        'patient__last_name1',
    )
    list_filter = ('status', 'visit_date', 'study_year', 'staff_category')
    ordering = ('-visit_date', 'study_code')
    inlines = [
        AnthropometryInline,
        VitalSignsInline,
        ElectrocardiogramInline,
        EchocardiogramInline,
        LaboratoryInline,
        VisitAnswerInline,
    ]


@admin.register(Anthropometry)
class AnthropometryAdmin(admin.ModelAdmin):
    list_display = ('visit', 'weight_kg', 'height_cm', 'waist_circumference_cm', 'bmi', 'body_surface_area')
    search_fields = ('visit__study_code', 'visit__patient__id_card')


@admin.register(VitalSigns)
class VitalSignsAdmin(admin.ModelAdmin):
    list_display = ('visit', 'systolic_bp', 'diastolic_bp', 'heart_rate', 'oxygen_saturation')
    search_fields = ('visit__study_code', 'visit__patient__id_card')


@admin.register(Electrocardiogram)
class ElectrocardiogramAdmin(admin.ModelAdmin):
    list_display = ('visit', 'rhythm', 'heart_rate', 'left_ventricular_hypertrophy')
    search_fields = ('visit__study_code', 'visit__patient__id_card')
    list_filter = ('rhythm', 'left_ventricular_hypertrophy')


@admin.register(Echocardiogram)
class EchocardiogramAdmin(admin.ModelAdmin):
    list_display = ('visit', 'lvef_percentage', 'ventricular_hypertrophy', 'diastolic_dysfunction')
    search_fields = ('visit__study_code', 'visit__patient__id_card')


@admin.register(Laboratory)
class LaboratoryAdmin(admin.ModelAdmin):
    list_display = ('visit', 'glucose_mg_dl', 'total_cholesterol_mg_dl', 'hdl_mg_dl', 'ldl_mg_dl', 'triglycerides_mg_dl')
    search_fields = ('visit__study_code', 'visit__patient__id_card')


@admin.register(VisitAnswer)
class VisitAnswerAdmin(admin.ModelAdmin):
    list_display = ('answer_id', 'visit', 'question', 'selected_option', 'numeric_value', 'text_value')
    search_fields = ('visit__study_code', 'question__code', 'text_value')
    list_filter = ('question__section',)
