from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission


class AppTokenAuthentication(BaseAuthentication):
    """
    Authenticates app clients using the X-App-Token header.
    Sets request.user = AppToken instance (NOT a Django User).
    Use IsAppClient permission on views that require this auth.
    """

    def authenticate(self, request):
        token = request.headers.get('X-App-Token')
        if not token:
            return None

        from .models import AppToken
        try:
            app_token = AppToken.objects.select_related(
                'customer',
                'channel',
                'channel__channel_type',
                'channel__business',
            ).get(token=token)
        except (AppToken.DoesNotExist, ValueError):
            raise AuthenticationFailed('Invalid or expired app token.')

        AppToken.objects.filter(pk=app_token.pk).update(last_seen_at=timezone.now())
        return (app_token, app_token)

    def authenticate_header(self, request):
        return 'X-App-Token'


class IsAppClient(BasePermission):
    """Permission for app client endpoints — request.user must be an AppToken."""

    def has_permission(self, request, view):
        from .models import AppToken
        return isinstance(request.user, AppToken)
