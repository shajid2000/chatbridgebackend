from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import (
    BusinessRegistrationSerializer,
    LoginSerializer,
    UserSerializer,
    InviteCreateSerializer,
    InviteAcceptSerializer,
    InviteTokenSerializer,
)
from .permissions import IsBusinessAdmin, IsBusiness
from .services import AccountService


def get_tokens_for_user(user: User) -> dict:
    """Generate JWT tokens with custom claims (business_id, role)."""
    refresh = RefreshToken.for_user(user)
    refresh['business_id'] = str(user.business_id) if user.business_id else None
    refresh['role'] = user.role
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class RegisterView(APIView):
    """Register a new business and its admin user."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = BusinessRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {'user': UserSerializer(user).data, 'tokens': get_tokens_for_user(user)},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """Login and receive JWT tokens."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        return Response(
            {'user': UserSerializer(user).data, 'tokens': get_tokens_for_user(user)}
        )


class MeView(APIView):
    """Get or update the current authenticated user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class InviteCreateView(APIView):
    """Admin sends an invite to a new staff member."""
    permission_classes = [IsAuthenticated, IsBusinessAdmin]

    def post(self, request):
        serializer = InviteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invite = AccountService.create_invite(
            business=request.user.business,
            email=serializer.validated_data['email'],
            role=serializer.validated_data['role'],
            invited_by=request.user,
        )
        return Response(InviteTokenSerializer(invite).data, status=status.HTTP_201_CREATED)


class InviteAcceptView(APIView):
    """Accept an invite and create the new user account."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = InviteAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = AccountService.accept_invite(**serializer.validated_data)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {'user': UserSerializer(user).data, 'tokens': get_tokens_for_user(user)},
            status=status.HTTP_201_CREATED,
        )


class TeamMembersView(generics.ListAPIView):
    """List all users in the current business (admin only)."""
    permission_classes = [IsAuthenticated, IsBusinessAdmin]
    serializer_class = UserSerializer

    def get_queryset(self):
        return User.objects.filter(
            business=self.request.user.business
        ).select_related('business').order_by('date_joined')
