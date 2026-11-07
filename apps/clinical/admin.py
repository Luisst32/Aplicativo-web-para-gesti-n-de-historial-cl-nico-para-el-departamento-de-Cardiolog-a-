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


from django import forms
from django.core.exceptions import ValidationError
from audit.services import register_audit_log
from .validators import validate_ecuadorian_id, validate_clinical_ranges


class PatientAdminForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = '__all__'

    def clean_id_card(self):
        id_card = self.cleaned_data.get('id_card')
        if id_card and not validate_ecuadorian_id(id_card):
            raise ValidationError("La cédula ingresada no es válida según el algoritmo oficial ecuatoriano.")
        return id_card


class AnthropometryAdminForm(forms.ModelForm):
    class Meta:
        model = Anthropometry
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        errores = validate_clinical_ranges({
            'weight_kg': cleaned_data.get('weight_kg'),
            'height_cm': cleaned_data.get('height_cm'),
            'waist_circumference_cm': cleaned_data.get('waist_circumference_cm'),
        })
        if errores:
            raise ValidationError(errores)
        return cleaned_data


class VitalSignsAdminForm(forms.ModelForm):
    class Meta:
        model = VitalSigns
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        errores = validate_clinical_ranges({
            'systolic_bp': cleaned_data.get('systolic_bp'),
            'diastolic_bp': cleaned_data.get('diastolic_bp'),
            'oxygen_saturation': cleaned_data.get('oxygen_saturation'),
            'heart_rate': cleaned_data.get('heart_rate'),
        })
        if errores:
            raise ValidationError(errores)
        return cleaned_data


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    form = PatientAdminForm
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

    def save_model(self, request, obj, form, change):
        action = 'UPDATE' if change else 'INSERT'
        super().save_model(request, obj, form, change)
        register_audit_log(
            user=request.user,
            table_name='patient',
            record_key=obj.patient_id,
            action=action,
            new_value={'id_card': obj.id_card, 'name': obj.full_name},
            machine_name=getattr(request, 'client_ip', '127.0.0.1')
        )


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
    form = AnthropometryAdminForm
    list_display = ('visit', 'weight_kg', 'height_cm', 'waist_circumference_cm', 'bmi', 'body_surface_area')
    search_fields = ('visit__study_code', 'visit__patient__id_card')


@admin.register(VitalSigns)
class VitalSignsAdmin(admin.ModelAdmin):
    form = VitalSignsAdminForm
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
