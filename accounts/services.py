from datetime import timedelta
from django.utils import timezone
from .models import Business, User, InviteToken


class AccountService:

    @staticmethod
    def register_business(
        business_name: str,
        admin_email: str,
        admin_password: str,
        first_name: str = '',
        last_name: str = '',
    ) -> tuple[Business, User]:
        """Create a new business and its first admin user."""
        business = Business.objects.create(name=business_name)
        admin = User.objects.create_user(
            email=admin_email,
            password=admin_password,
            business=business,
            role=User.Role.ADMIN,
            first_name=first_name,
            last_name=last_name,
        )
        return business, admin

    @staticmethod
    def create_invite(
        business: Business,
        email: str,
        role: str,
        invited_by: User,
        expires_hours: int = 48,
    ) -> InviteToken:
        """Create an invite token. Invalidates any pending invite for the same email."""
        # Expire previous pending invites for this email in this business
        InviteToken.objects.filter(
            business=business,
            email=email,
            used_at__isnull=True,
        ).update(expires_at=timezone.now())

        return InviteToken.objects.create(
            business=business,
            email=email,
            role=role,
            created_by=invited_by,
            expires_at=timezone.now() + timedelta(hours=expires_hours),
        )

    @staticmethod
    def accept_invite(
        token: str,
        password: str,
        first_name: str = '',
        last_name: str = '',
    ) -> User:
        """Accept an invite and create the new user."""
        try:
            invite = InviteToken.objects.select_related('business').get(token=token)
        except InviteToken.DoesNotExist:
            raise ValueError('Invalid invite token.')

        if not invite.is_valid:
            raise ValueError('This invite has expired or has already been used.')

        if User.objects.filter(email=invite.email).exists():
            raise ValueError('A user with this email already exists.')

        user = User.objects.create_user(
            email=invite.email,
            password=password,
            business=invite.business,
            role=invite.role,
            first_name=first_name,
            last_name=last_name,
        )

        invite.used_at = timezone.now()
        invite.save(update_fields=['used_at'])

        return user
