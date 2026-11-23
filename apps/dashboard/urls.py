from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index_view, name="index"),
    path("api/data/", views.api_dashboard_data, name="api_data"),
    path("export/html-pdf/", views.export_dashboard_html_pdf, name="export_html_pdf"),
]
