from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index_view, name="index"),
    path("dashboard/", views.index_view, name="index_alias"),
    path("api/data/", views.api_dashboard_data, name="api_data"),
    path("dashboard/api/data/", views.api_dashboard_data, name="api_data_alias"),
]
