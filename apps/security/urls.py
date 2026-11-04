from django.urls import path
from . import views

app_name = 'security'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('api/profile/', views.api_profile_view, name='api_profile'),
    path('api/change-password/', views.api_change_password_view, name='api_change_password'),
    path('api/settings/', views.api_settings_view, name='api_settings'),
]
