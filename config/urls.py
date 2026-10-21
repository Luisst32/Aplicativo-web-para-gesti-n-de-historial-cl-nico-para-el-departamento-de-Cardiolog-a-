"""
URL configuration for config project.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('dashboard.urls')),
    path('security/', include('security.urls')),
    path('clinical/', include('clinical.urls')),
    path('chatbot/', include('chatbot.urls')),
]
