from django.urls import path
from . import views

urlpatterns = [
    # Channel types (for connect UI dropdown)
    path('channel-types/', views.ChannelTypeListView.as_view(), name='channel-type-list'),

    # Channel management (manual / legacy)
    path('channels/', views.ChannelListCreateView.as_view(), name='channel-list-create'),
    path('channels/<uuid:pk>/', views.ChannelDetailView.as_view(), name='channel-detail'),

    # Webhooks
    path('webhooks/meta/', views.MetaWebhookView.as_view(), name='webhook-meta'),

    # ── Source connections (OAuth-based — WhatsApp & Messenger Embedded Signup) ──
    # GET   /api/sources/           → list all connections for the business
    # POST  /api/sources/connect/   → Phase A (get URL) or Phase B (finalize)
    # PATCH /api/sources/connect/   → assign a selected page / phone number
    # DELETE /api/sources/connect/<id>/ → disconnect & revoke
    path('sources/',                  views.SourceConnectionListView.as_view(), name='source-list'),
    path('sources/connect/',          views.SourceConnectView.as_view(),        name='source-connect'),
    path('sources/connect/<uuid:pk>/', views.SourceDisconnectView.as_view(),    name='source-disconnect'),
    path('sources/assign/',           views.SourceAssignView.as_view(),         name='source-assign'),
]
