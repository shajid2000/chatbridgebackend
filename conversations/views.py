from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from accounts.models import User
from accounts.permissions import IsBusiness
from integrations.models import Channel

from .models import Customer, Message
from .serializers import (
    CustomerSerializer,
    MessageSerializer,
    SendMessageSerializer,
    AssignAgentSerializer,
)
from .services import ReplyService


class CustomerListView(generics.ListAPIView):
    """
    Inbox — all customers for the business, visible to every agent.
    Supports filtering by status and channel_type.
    """
    permission_classes = [IsAuthenticated, IsBusiness]
    serializer_class = CustomerSerializer

    def get_queryset(self):
        qs = Customer.objects.filter(
            business=self.request.user.business
        ).select_related('last_channel__channel_type', 'assigned_agent')

        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        channel_type = self.request.query_params.get('channel_type')
        if channel_type:
            qs = qs.filter(channel_identities__channel_type=channel_type).distinct()

        return qs


class CustomerDetailView(generics.RetrieveUpdateAPIView):
    """Get or update a customer profile."""
    permission_classes = [IsAuthenticated, IsBusiness]
    serializer_class = CustomerSerializer

    def get_queryset(self):
        return Customer.objects.filter(
            business=self.request.user.business
        ).select_related('last_channel__channel_type', 'assigned_agent').prefetch_related('channel_identities')


class MessageListView(generics.ListAPIView):
    """Full unified message thread for a customer across all channels."""
    permission_classes = [IsAuthenticated, IsBusiness]
    serializer_class = MessageSerializer

    def get_queryset(self):
        customer = Customer.objects.filter(
            business=self.request.user.business,
            id=self.kwargs['customer_id'],
        ).first()
        if not customer:
            return Message.objects.none()

        # Mark inbound messages as read when thread is opened
        Message.objects.filter(
            customer=customer,
            speaker=Message.Speaker.CUSTOMER,
            is_read=False,
        ).update(is_read=True)

        return Message.objects.filter(customer=customer).select_related('speaker_agent')


class SendMessageView(APIView):
    """
    Send a reply or outbound message to a customer.
    channel_id is optional — defaults to customer.last_channel.
    Used for both individual replies and triggered campaign messages.
    """
    permission_classes = [IsAuthenticated, IsBusiness]

    def post(self, request, customer_id):
        customer = Customer.objects.filter(
            business=request.user.business, id=customer_id
        ).first()
        if not customer:
            return Response({'detail': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        channel = None
        channel_id = serializer.validated_data.get('channel_id')
        if channel_id:
            channel = Channel.objects.filter(
                id=channel_id, business=request.user.business, status='active'
            ).first()
            if not channel:
                return Response({'detail': 'Channel not found or inactive.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            message = ReplyService.send(
                customer=customer,
                content=serializer.validated_data['content'],
                content_type=serializer.validated_data['content_type'],
                speaker=Message.Speaker.AGENT,
                channel=channel,
                agent=request.user,
            )
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)


class AssignAgentView(APIView):
    """Assign or unassign an agent to a customer thread."""
    permission_classes = [IsAuthenticated, IsBusiness]

    def post(self, request, customer_id):
        customer = Customer.objects.filter(
            business=request.user.business, id=customer_id
        ).first()
        if not customer:
            return Response({'detail': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AssignAgentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        agent_id = serializer.validated_data['agent_id']
        if agent_id:
            agent = User.objects.filter(id=agent_id, business=request.user.business).first()
            if not agent:
                return Response({'detail': 'Agent not found.'}, status=status.HTTP_404_NOT_FOUND)
            customer.assigned_agent = agent
        else:
            customer.assigned_agent = None

        customer.save(update_fields=['assigned_agent', 'updated_at'])
        return Response(CustomerSerializer(customer).data)


class UpdateStatusView(APIView):
    """Update customer thread status: open, resolved, pending."""
    permission_classes = [IsAuthenticated, IsBusiness]

    VALID_STATUSES = ['open', 'resolved', 'pending']

    def post(self, request, customer_id):
        customer = Customer.objects.filter(
            business=request.user.business, id=customer_id
        ).first()
        if not customer:
            return Response({'detail': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        if new_status not in self.VALID_STATUSES:
            return Response(
                {'detail': f'Invalid status. Choose from: {self.VALID_STATUSES}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer.status = new_status
        customer.save(update_fields=['status', 'updated_at'])
        return Response({'status': customer.status})
