from rest_framework.permissions import BasePermission
from .models import User


def _is_superadmin(user):
    """Superadmin bypasses all permission checks."""
    return (
        user.is_authenticated
        # and user.business_id is not None
        and user.role == User.Role.SUPERADMIN
    )


class IsBusinessAdmin(BasePermission):
    """Admin or superadmin users of a business."""
    message = 'Only business admins can perform this action.'

    def has_permission(self, request, view):
        if _is_superadmin(request.user):
            return True
        return (
            request.user.is_authenticated
            and request.user.business_id is not None
            and request.user.role == User.Role.ADMIN
        )


class IsSuperAdmin(BasePermission):
    """Only superadmin users can access this view."""
    message = 'Only super admins can perform this action.'

    def has_permission(self, request, view):
        return _is_superadmin(request.user)


class IsAdminOrSuperAdmin(BasePermission):
    """Admin or superadmin users only."""
    message = 'Only admins and super admins can perform this action.'

    def has_permission(self, request, view):
        if _is_superadmin(request.user):
            return True
        return (
            request.user.is_authenticated
            and request.user.business_id is not None
            and request.user.role == User.Role.ADMIN
        )


class IsBusiness(BasePermission):
    """Any authenticated user who belongs to a business. Superadmin always passes."""
    message = 'User must belong to a business.'

    def has_permission(self, request, view):
        if _is_superadmin(request.user):
            return True
        return (
            request.user.is_authenticated
            and request.user.business_id is not None
        )
