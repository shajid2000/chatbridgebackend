from django.urls import path
from . import views

urlpatterns = [
    path('ai/config/', views.AIConfigView.as_view(), name='ai-config'),
]
