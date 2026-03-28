from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from accounts.models import User
from accounts.permissions import IsBusinessAdmin
from .models import AIConfig
from .serializers import AIConfigSerializer

# Fields only a superadmin may write
_SUPERADMIN_FIELDS = {'provider', 'api_key', 'model_name', 'system_prompt', 'context_messages'}


class AIConfigView(generics.RetrieveUpdateAPIView):
    """
    GET   /api/ai/config/  — any admin/superadmin can read
    PATCH /api/ai/config/  — field-level permission:
        • 'enabled' only  → admin or superadmin
        • any other field → superadmin only
    """
    permission_classes = [IsAuthenticated, IsBusinessAdmin]
    serializer_class = AIConfigSerializer
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_object(self):
        config, _ = AIConfig.objects.get_or_create(business=self.request.user.business)
        return config

    def partial_update(self, request, *args, **kwargs):
        sensitive = _SUPERADMIN_FIELDS & set(request.data.keys())
        if sensitive and request.user.role != User.Role.SUPERADMIN:
            return Response(
                {'detail': f'Only super admins can update: {", ".join(sorted(sensitive))}.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().partial_update(request, *args, partial=True, **kwargs)
