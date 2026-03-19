from django.urls import re_path
from conversations import consumers
from app_channel import consumers as app_consumers

websocket_urlpatterns = [
    # Chat window — subscribe to a single customer thread
    re_path(r'^ws/customers/(?P<customer_id>[0-9a-f-]+)/$', consumers.CustomerConsumer.as_asgi()),
    # Inbox sidebar — business-wide new message notifications
    re_path(r'^ws/inbox/$', consumers.InboxConsumer.as_asgi()),
    # App channel — end-user app client real-time connection
    re_path(r'^ws/app/(?P<token>[0-9a-f-]+)/$', app_consumers.AppConsumer.as_asgi()),
]
