import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone


class Business(models.Model):
    """Tenant root — every entity belongs to a business."""

    class Plan(models.TextChoices):
        FREE = 'free', 'Free'
        PRO = 'pro', 'Pro'
        ENTERPRISE = 'enterprise', 'Enterprise'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    plan = models.CharField(max_length=20, choices=Plan.choices, default=Plan.FREE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'businesses'

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required.')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.ADMIN)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user — belongs to a Business, has a role (admin or staff)."""

    class Role(models.TextChoices):
        SUPERADMIN = 'superadmin', 'Super Admin'
        ADMIN = 'admin', 'Admin'
        STAFF = 'staff', 'Staff'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name='users', null=True, blank=True
    )
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STAFF)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return f'{self.email} ({self.role})'

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip() or self.email


class InviteToken(models.Model):
    """Single-use, expiring invite for onboarding staff members."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='invites')
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=User.Role.choices, default=User.Role.STAFF)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='sent_invites'
    )
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_used(self):
        return self.used_at is not None

    @property
    def is_valid(self):
        return not self.is_expired and not self.is_used

    def __str__(self):
        return f'Invite to {self.email} ({self.business.name})'
