from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('auth/me/', views.MeView.as_view(), name='me'),
    path('team/invite/', views.InviteCreateView.as_view(), name='invite-create'),
    path('team/invite/accept/', views.InviteAcceptView.as_view(), name='invite-accept'),
    path('team/members/', views.TeamMembersView.as_view(), name='team-members'),
]
