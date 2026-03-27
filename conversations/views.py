from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import CursorPagination, PageNumberPagination
from django.db.models import Q, F
from django.db import transaction

from accounts.models import User
from accounts.permissions import IsBusiness
from integrations.models import Channel

from .models import Customer, Message,CustomerChannel
from .serializers import (
    CustomerSerializer,
    MessageSerializer,
    SendMessageSerializer,
    AssignAgentSerializer,
)
from .services import ReplyService


class CustomerPagePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 50


class CustomerListView(generics.ListAPIView):
    """
    Inbox — all customers for the business, visible to every agent.
    Supports filtering by status, channel_type, and search (name/phone/email).
    """
    permission_classes = [IsAuthenticated, IsBusiness]
    serializer_class = CustomerSerializer
    pagination_class = CustomerPagePagination

    def get_queryset(self):
        qs = Customer.objects.filter(
            business=self.request.user.business
        ).select_related('last_channel__channel_type', 'assigned_agent').order_by(
            F('last_message_at').desc(nulls_last=True), '-created_at'
        )

        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        channel_type = self.request.query_params.get('channel_type')
        if channel_type:
            qs = qs.filter(channel_identities__channel_type=channel_type).distinct()

        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search) | Q(phone__icontains=search) | Q(email__icontains=search)
            )

        return qs


class CustomerDetailView(generics.RetrieveUpdateAPIView):
    """Get or update a customer profile."""
    permission_classes = [IsAuthenticated, IsBusiness]
    serializer_class = CustomerSerializer

    def get_queryset(self):
        return Customer.objects.filter(
            business=self.request.user.business
        ).select_related('last_channel__channel_type', 'assigned_agent').prefetch_related('channel_identities')


class MessageCursorPagination(CursorPagination):
    page_size = 10
    ordering = '-timestamp'  # newest first; frontend reverses for display


class MessageListView(generics.ListAPIView):
    """Full unified message thread for a customer across all channels."""
    permission_classes = [IsAuthenticated, IsBusiness]
    serializer_class = MessageSerializer
    pagination_class = MessageCursorPagination

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


class MergeCustomerView(APIView):
    """
    Merge one or more duplicate customers into a primary customer.
    All messages and channel identities from secondaries move to the primary.
    Secondaries are deleted after merge.
    """
    permission_classes = [IsAuthenticated, IsBusiness]

    @transaction.atomic
    def post(self, request, customer_id):
        primary = Customer.objects.filter(
            business=request.user.business, id=customer_id
        ).first()
        if not primary:
            return Response({'detail': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)

        merge_ids = request.data.get('merge_ids', [])
        if not merge_ids:
            return Response({'detail': 'merge_ids is required.'}, status=status.HTTP_400_BAD_REQUEST)

        secondaries = Customer.objects.filter(
            business=request.user.business,
            id__in=merge_ids,
        ).exclude(id=primary.id)

        if not secondaries.exists():
            return Response({'detail': 'No valid customers to merge.'}, status=status.HTTP_400_BAD_REQUEST)

        for secondary in secondaries:
            # Move channel identities — skip exact duplicates
            for cc in secondary.channel_identities.all():
                CustomerChannel.objects.get_or_create(
                    customer=primary,
                    channel_type=cc.channel_type,
                    external_id=cc.external_id,
                )

            # Move all messages
            secondary.messages.update(customer=primary)

            # Move AppTokens — must happen before delete to avoid CASCADE removal
            secondary.app_tokens.update(customer=primary)

            # Fill missing contact fields from secondary
            if not primary.name and secondary.name:
                primary.name = secondary.name
            if not primary.phone and secondary.phone:
                primary.phone = secondary.phone
            if not primary.email and secondary.email:
                primary.email = secondary.email

            secondary.delete()

        # Sync last_message_at to the latest message across merged thread
        latest = primary.messages.order_by('-timestamp').first()
        if latest:
            primary.last_message_at = latest.timestamp

        primary.save()

        # Broadcast to all agents in this business so their inboxes update live
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'inbox_{request.user.business_id}',
            {
                'type': 'inbox.merged',
                'primary_id': str(primary.id),
                'merged_ids': [str(mid) for mid in merge_ids],
            }
        )

        return Response(CustomerSerializer(primary).data)
