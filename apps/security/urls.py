from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'security'

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='security:login', permanent=False), name='root'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('password-reset/', views.password_reset_request_view, name='password_reset_request'),
    path('reset/<uidb64>/<token>/', views.password_reset_confirm_view, name='password_reset_confirm'),
    path('api/profile/', views.api_profile_view, name='api_profile'),
    path('api/change-password/', views.api_change_password_view, name='api_change_password'),
    path('api/settings/', views.api_settings_view, name='api_settings'),
]
