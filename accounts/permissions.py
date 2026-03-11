from rest_framework.permissions import BasePermission
from .models import User


class IsBusinessAdmin(BasePermission):
    """Only admin users of a business can access this view."""
    message = 'Only business admins can perform this action.'

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.business_id is not None
            and request.user.role == User.Role.ADMIN
        )


class IsBusiness(BasePermission):
    """Any authenticated user who belongs to a business."""
    message = 'User must belong to a business.'

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.business_id is not None
        )
