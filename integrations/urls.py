from django.urls import path
from . import views

urlpatterns = [
    # Channel types (for connect UI dropdown)
    path('channel-types/', views.ChannelTypeListView.as_view(), name='channel-type-list'),

    # Channel management
    path('channels/', views.ChannelListCreateView.as_view(), name='channel-list-create'),
    path('channels/<uuid:pk>/', views.ChannelDetailView.as_view(), name='channel-detail'),

    # Webhooks
    path('webhooks/meta/', views.MetaWebhookView.as_view(), name='webhook-meta'),
]
