from django.urls import path
from . import views

app_name = 'clinical'

urlpatterns = [
    path('formulario/', views.form_view, name='form'),
    path('listado/', views.list_view, name='list'),
]
