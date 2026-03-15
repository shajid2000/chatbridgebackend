import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

django_asgi_app = get_asgi_application()

# These imports MUST come after get_asgi_application()
# Any crash here kills the worker silently
try:
    from conversations.middleware import JWTAuthMiddleware
    from main.routing import websocket_urlpatterns
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.security.websocket import AllowedHostsOriginValidator

    application = ProtocolTypeRouter({
        'http': django_asgi_app,
        'websocket': AllowedHostsOriginValidator(
            JWTAuthMiddleware(
                URLRouter(websocket_urlpatterns)
            )
        ),
    })
except Exception as e:
    print(f"ASGI STARTUP ERROR: {e}", flush=True)
    raise