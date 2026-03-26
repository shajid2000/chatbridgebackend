from django.urls import path
from . import views

urlpatterns = [
    # Customer inbox
    path('customers/', views.CustomerListView.as_view(), name='customer-list'),
    path('customers/<uuid:pk>/', views.CustomerDetailView.as_view(), name='customer-detail'),

    # Message thread
    path('customers/<uuid:customer_id>/messages/', views.MessageListView.as_view(), name='message-list'),
    path('customers/<uuid:customer_id>/messages/send/', views.SendMessageView.as_view(), name='message-send'),

    # Actions
    path('customers/<uuid:customer_id>/assign/', views.AssignAgentView.as_view(), name='customer-assign'),
    path('customers/<uuid:customer_id>/status/', views.UpdateStatusView.as_view(), name='customer-status'),
    path('customers/<uuid:customer_id>/merge/', views.MergeCustomerView.as_view(), name='customer-merge'),
]
