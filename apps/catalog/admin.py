from django.contrib import admin
from .models import (
    Country,
    Province,
    Canton,
    Institution,
    Sex,
    Ethnicity,
    StaffCategory,
    ProfessionalCategory,
    EducationLevel,
    IncomeRange,
    MaritalStatus,
    LivingSituation,
    HousingType,
    WorkSchedule,
    EcgRhythm,
    QuestionnaireSection,
    Question,
    AnswerOption,
)


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ('country_id', 'iso_alpha3', 'name')
    search_fields = ('iso_alpha3', 'name')


@admin.register(Province)
class ProvinceAdmin(admin.ModelAdmin):
    list_display = ('province_id', 'country', 'iso_code', 'name')
    search_fields = ('iso_code', 'name')
    list_filter = ('country',)


@admin.register(Canton)
class CantonAdmin(admin.ModelAdmin):
    list_display = ('canton_id', 'province', 'dpa_code', 'name')
    search_fields = ('dpa_code', 'name')
    list_filter = ('province',)


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ('institution_id', 'acronym', 'name', 'is_active')
    search_fields = ('acronym', 'name')
    list_filter = ('is_active',)


@admin.register(Sex)
class SexAdmin(admin.ModelAdmin):
    list_display = ('sex_id', 'name', 'is_active')
    search_fields = ('name',)
    list_filter = ('is_active',)


@admin.register(Ethnicity)
class EthnicityAdmin(admin.ModelAdmin):
    list_display = ('ethnicity_id', 'name', 'is_active')
    search_fields = ('name',)
    list_filter = ('is_active',)


@admin.register(StaffCategory)
class StaffCategoryAdmin(admin.ModelAdmin):
    list_display = ('staff_category_id', 'name', 'is_active')
    search_fields = ('name',)
    list_filter = ('is_active',)


@admin.register(ProfessionalCategory)
class ProfessionalCategoryAdmin(admin.ModelAdmin):
    list_display = ('professional_category_id', 'name', 'is_active')
    search_fields = ('name',)
    list_filter = ('is_active',)


@admin.register(EducationLevel)
class EducationLevelAdmin(admin.ModelAdmin):
    list_display = ('education_level_id', 'name', 'is_active')
    search_fields = ('name',)
    list_filter = ('is_active',)


@admin.register(IncomeRange)
class IncomeRangeAdmin(admin.ModelAdmin):
    list_display = ('income_range_id', 'name', 'is_active')
    search_fields = ('name',)
    list_filter = ('is_active',)


@admin.register(MaritalStatus)
class MaritalStatusAdmin(admin.ModelAdmin):
    list_display = ('marital_status_id', 'name', 'is_active')
    search_fields = ('name',)
    list_filter = ('is_active',)


@admin.register(LivingSituation)
class LivingSituationAdmin(admin.ModelAdmin):
    list_display = ('living_situation_id', 'name', 'is_active')
    search_fields = ('name',)
    list_filter = ('is_active',)


@admin.register(HousingType)
class HousingTypeAdmin(admin.ModelAdmin):
    list_display = ('housing_type_id', 'name', 'is_active')
    search_fields = ('name',)
    list_filter = ('is_active',)


@admin.register(WorkSchedule)
class WorkScheduleAdmin(admin.ModelAdmin):
    list_display = ('work_schedule_id', 'name', 'is_active')
    search_fields = ('name',)
    list_filter = ('is_active',)


@admin.register(EcgRhythm)
class EcgRhythmAdmin(admin.ModelAdmin):
    list_display = ('ecg_rhythm_id', 'name', 'is_active')
    search_fields = ('name',)
    list_filter = ('is_active',)


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    fields = ('code', 'text', 'response_type', 'display_order', 'is_active')


@admin.register(QuestionnaireSection)
class QuestionnaireSectionAdmin(admin.ModelAdmin):
    list_display = ('section_id', 'code', 'name', 'display_order', 'is_active')
    search_fields = ('code', 'name')
    list_filter = ('is_active',)
    ordering = ('display_order',)
    inlines = [QuestionInline]


class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    extra = 2
    fields = ('label', 'display_order', 'scores_predimed', 'is_active')


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('question_id', 'section', 'code', 'text', 'response_type', 'display_order', 'is_active')
    search_fields = ('code', 'text')
    list_filter = ('is_active', 'section', 'response_type')
    ordering = ('section', 'display_order')
    inlines = [AnswerOptionInline]


@admin.register(AnswerOption)
class AnswerOptionAdmin(admin.ModelAdmin):
    list_display = ('option_id', 'question', 'label', 'display_order', 'scores_predimed', 'is_active')
    search_fields = ('label', 'question__code')
    list_filter = ('is_active', 'scores_predimed', 'question__section')
    ordering = ('question', 'display_order')
