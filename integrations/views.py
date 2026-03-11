import json
import logging

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from accounts.permissions import IsBusinessAdmin, IsBusiness
from .models import Channel, ChannelType
from .serializers import ChannelSerializer, ChannelTypeSerializer
from .services import ChannelService, WebhookVerifier, MessageNormalizer

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────
# Channel Type Views
# ─────────────────────────────────────────

class ChannelTypeListView(generics.ListAPIView):
    """List all active channel types (for the connect UI)."""
    permission_classes = [IsAuthenticated, IsBusiness]
    serializer_class = ChannelTypeSerializer
    queryset = ChannelType.objects.filter(is_active=True)


# ─────────────────────────────────────────
# Channel CRUD
# ─────────────────────────────────────────

class ChannelListCreateView(generics.ListCreateAPIView):
    """List all channels for the business / connect a new channel."""
    permission_classes = [IsAuthenticated, IsBusinessAdmin]
    serializer_class = ChannelSerializer

    def get_queryset(self):
        return Channel.objects.filter(
            business=self.request.user.business
        ).select_related('channel_type')

    def perform_create(self, serializer):
        ChannelService.connect(
            business=self.request.user.business,
            validated_data=serializer.validated_data,
        )
        # Re-save via serializer to keep DRF response consistent
        serializer.save(business=self.request.user.business, status=Channel.Status.ACTIVE)


class ChannelDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update or disconnect a channel."""
    permission_classes = [IsAuthenticated, IsBusinessAdmin]
    serializer_class = ChannelSerializer

    def get_queryset(self):
        return Channel.objects.filter(business=self.request.user.business)

    def destroy(self, request, *args, **kwargs):
        channel = self.get_object()
        ChannelService.disconnect(channel)
        return Response({'detail': 'Channel disconnected.'}, status=status.HTTP_200_OK)


# ─────────────────────────────────────────
# Webhooks
# ─────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class MetaWebhookView(APIView):
    """
    Handles webhooks from Meta platforms:
    WhatsApp Cloud API, Instagram, Facebook Messenger.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        """Meta webhook verification handshake."""
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        channel = Channel.objects.filter(webhook_secret=token).first()
        if mode == 'subscribe' and channel:
            logger.info('Meta webhook verified for channel %s', channel.id)
            return HttpResponse(challenge, content_type='text/plain')

        return HttpResponse('Forbidden', status=403)

    def post(self, request):
        """Receive and process incoming Meta webhook events."""
        raw_body = request.body
        signature = request.headers.get('X-Hub-Signature-256', '')

        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            return Response({'detail': 'Invalid JSON.'}, status=400)

        object_type = payload.get('object')

        if object_type == 'whatsapp_business_account':
            self._handle_whatsapp(raw_body, signature, payload)
        elif object_type == 'instagram':
            self._handle_instagram(raw_body, signature, payload)
        elif object_type == 'page':
            self._handle_messenger(raw_body, signature, payload)
        else:
            logger.warning('Unknown Meta webhook object type: %s', object_type)

        # Always return 200 to Meta immediately
        return Response({'status': 'received'})

    def _get_channel(self, phone_number_id=None, page_id=None):
        if phone_number_id:
            return Channel.objects.filter(phone_number_id=phone_number_id, status='active').first()
        if page_id:
            return Channel.objects.filter(page_id=page_id, status='active').first()
        return None

    def _handle_whatsapp(self, raw_body, signature, payload):
        for entry in payload.get('entry', []):
            for change in entry.get('changes', []):
                phone_number_id = change.get('value', {}).get('metadata', {}).get('phone_number_id')
                channel = self._get_channel(phone_number_id=phone_number_id)
                if not channel:
                    continue
                if not WebhookVerifier.verify_whatsapp(raw_body, signature, channel.webhook_secret):
                    logger.warning('Invalid WhatsApp signature for channel %s', channel.id)
                    continue
                messages = MessageNormalizer.from_whatsapp(payload)
                self._dispatch(messages, channel)

    def _handle_instagram(self, raw_body, signature, payload):
        for entry in payload.get('entry', []):
            page_id = entry.get('id')
            channel = self._get_channel(page_id=page_id)
            if not channel:
                continue
            if not WebhookVerifier.verify_meta(raw_body, signature, channel.webhook_secret):
                logger.warning('Invalid Instagram signature for channel %s', channel.id)
                continue
            messages = MessageNormalizer.from_instagram(payload)
            self._dispatch(messages, channel)

    def _handle_messenger(self, raw_body, signature, payload):
        for entry in payload.get('entry', []):
            page_id = entry.get('id')
            channel = self._get_channel(page_id=page_id)
            if not channel:
                continue
            if not WebhookVerifier.verify_meta(raw_body, signature, channel.webhook_secret):
                logger.warning('Invalid Messenger signature for channel %s', channel.id)
                continue
            messages = MessageNormalizer.from_messenger(payload)
            self._dispatch(messages, channel)

    def _dispatch(self, messages: list, channel: Channel):
        """Hand off normalized messages to the message processor."""
        from conversations.services import MessageProcessor
        for message in messages:
            message['business_id'] = str(channel.business_id)
            message['channel_id'] = str(channel.id)
            try:
                MessageProcessor.process(message)
            except Exception as e:
                logger.exception('Failed to process message %s: %s', message.get('external_id'), e)
