from django.urls import path
from . import views

app_name = 'clinical'

urlpatterns = [
    # Páginas HTML principales
    path('formulario/', views.form_view, name='form'),
    path('listado/', views.list_view, name='list'),

    # APIs JSON para Directorio de Pacientes y Expediente (HU-15, HU-16)
    path('api/pacientes/', views.patient_list_api, name='api_patient_list'),
    path('api/pacientes/crear/', views.patient_create_api, name='api_patient_create'),
    path('api/pacientes/<str:patient_id>/', views.patient_detail_api, name='api_patient_detail'),

    # APIs JSON para Ficha Clínica (HU-11, HU-12, HU-13)
    path('api/ficha/guardar/', views.form_save_api, name='api_form_save'),
    path('api/ficha/<str:patient_id>/', views.form_get_api, name='api_form_get'),

    # Exportación oficial a PDF (HU-17)
    path('ficha/<int:visit_id>/pdf/', views.export_pdf_view, name='export_pdf'),
    path('ficha/pdf/', views.export_pdf_view, name='export_pdf_query'),
]
