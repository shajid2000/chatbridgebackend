from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Business, User, InviteToken


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ['name', 'plan', 'created_at']
    search_fields = ['name']
    list_filter = ['plan']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'full_name', 'business', 'role', 'is_active', 'date_joined']
    list_filter = ['role', 'is_active', 'business']
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['email']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name')}),
        ('Business', {'fields': ('business', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates', {'fields': ('date_joined', 'last_login')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'business', 'role'),
        }),
    )


@admin.register(InviteToken)
class InviteTokenAdmin(admin.ModelAdmin):
    list_display = ['email', 'business', 'role', 'is_valid', 'expires_at', 'created_at']
    list_filter = ['role', 'business']
    search_fields = ['email']
    readonly_fields = ['token', 'used_at', 'created_at']
