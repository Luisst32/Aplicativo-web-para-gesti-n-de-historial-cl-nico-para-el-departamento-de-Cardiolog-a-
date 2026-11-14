"""
URL configuration for config project.
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from clinical import views as clinical_views
from dashboard import views as dashboard_views

urlpatterns = [
    path('favicon.ico', RedirectView.as_view(url='/static/assets/images/favicon.ico', permanent=True)),
    path('admin/', admin.site.urls),
    path('login/', RedirectView.as_view(pattern_name='security:login', permanent=False)),
    path('accounts/login/', RedirectView.as_view(pattern_name='security:login', permanent=False)),
    path('', clinical_views.list_view, name='home'),
    path('dashboard/', include('dashboard.urls')),
    path('api/data/', dashboard_views.api_dashboard_data, name='dashboard_api_data_legacy'),
    path('security/', include('security.urls')),
    path('clinical/', include('clinical.urls')),
    path('chatbot/', include('chatbot.urls')),
]
