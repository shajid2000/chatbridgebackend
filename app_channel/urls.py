from django.urls import path
from . import views

urlpatterns = [
    # Public — no auth required
    path('app/channel-info/', views.ChannelInfoView.as_view(), name='app-channel-info'),
    path('app/session/init/', views.SessionInitView.as_view(), name='app-session-init'),

    # App client — X-App-Token auth
    path('app/session/me/', views.SessionMeView.as_view(), name='app-session-me'),
    path('app/messages/', views.AppMessagesView.as_view(), name='app-messages'),
    path('app/messages/read/', views.AppMessageReadView.as_view(), name='app-messages-read'),
]
