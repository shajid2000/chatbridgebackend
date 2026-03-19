import json
import logging
import uuid

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from accounts.permissions import IsBusinessAdmin, IsBusiness
from .models import Channel, ChannelType, SourceConnection
from .serializers import ChannelSerializer, ChannelTypeSerializer, SourceConnectionSerializer
from .services import ChannelService, WebhookVerifier, MessageNormalizer
from . import source_service as meta
from .connectors import ConnectorFactory

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
                # if not WebhookVerifier.verify_whatsapp(raw_body, signature, channel.webhook_secret):
                #     logger.warning('Invalid WhatsApp signature for channel %s', channel.id)
                #     continue
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


class RotateClientKeyView(APIView):
    """POST /api/channels/<uuid:pk>/rotate-key/ — regenerate client_key for an app channel."""
    permission_classes = [IsAuthenticated, IsBusinessAdmin]

    def post(self, request, pk):
        channel = get_object_or_404(Channel, pk=pk, business=request.user.business)
        channel.client_key = uuid.uuid4()
        channel.save(update_fields=['client_key', 'updated_at'])
        return Response({'client_key': str(channel.client_key)})


# ─────────────────────────────────────────
# Source Connection — OAuth connect flow
# ─────────────────────────────────────────

class SourceConnectionListView(generics.ListAPIView):
    """GET /api/sources/ — list all source connections for the business."""
    permission_classes = [IsAuthenticated, IsBusinessAdmin]
    serializer_class   = SourceConnectionSerializer

    def get_queryset(self):
        return SourceConnection.objects.filter(business=self.request.user.business)


class SourceConnectView(APIView):
    """
    POST /api/sources/connect/

    Phase A — no auth_code in body:
        Returns { login_url } for the frontend to open as a popup.

    Phase B — auth_code (full redirect URL) present:
        Exchanges code, discovers assets, persists SourceConnection + Channel.
        Returns serialized SourceConnection. May also include facebook_pages
        or phone_numbers for user selection.
    """
    permission_classes = [IsAuthenticated, IsBusinessAdmin]

    def post(self, request):
        source        = request.data.get('source', '')
        auth_code_url = request.data.get('auth_code', '')

        try:
            connector = ConnectorFactory.get(source)
        except KeyError:
            return Response(
                {'detail': f'Unsupported source "{source}". Supported: {ConnectorFactory.supported_sources()}'},
                status=400,
            )

        # Phase A — return consent URL
        if not auth_code_url:
            url = connector.get_login_url(state=str(request.user.business.id))
            return Response({'login_url': url})

        # Phase B — finalize
        return connector.finalize(request, auth_code_url)


class SourceAssignView(APIView):
    """
    PATCH /api/sources/connect/

    Assign a selected page / phone number to the business after a multi-choice
    response from Phase B. Body example:

    {
      "source": "facebook.com",
      "properties": [
        { "item": { "page_id": "...", "page_name": "...", "page_token": "..." } }
      ]
    }
    """
    permission_classes = [IsAuthenticated, IsBusinessAdmin]

    def patch(self, request):
        source     = request.data.get('source', '')
        properties = request.data.get('properties', [])
        business   = request.user.business

        if not source or not properties:
            return Response({'detail': '"source" and "properties" are required.'}, status=400)

        try:
            connector = ConnectorFactory.get(source)
        except KeyError:
            return Response({'detail': f'Unsupported source "{source}".'}, status=400)

        try:
            connection = SourceConnection.objects.get(business=business, source=source)
        except SourceConnection.DoesNotExist:
            return Response(
                {'detail': 'No existing source connection. Complete Phase B connect first.'},
                status=404,
            )

        results = []
        for prop in properties:
            resp = connector.assign(request, connection, item=prop.get('item', {}))
            results.append(resp.data)

        return Response(results)


class SourceDisconnectView(APIView):
    """
    DELETE /api/sources/connect/<uuid:pk>/

    Revokes tokens, deactivates Channel, deletes SourceConnection.
    """
    permission_classes = [IsAuthenticated, IsBusinessAdmin]

    def delete(self, request, pk):
        try:
            connection = SourceConnection.objects.get(pk=pk, business=request.user.business)
        except SourceConnection.DoesNotExist:
            return Response({'detail': 'Source connection not found.'}, status=404)

        try:
            connector = ConnectorFactory.get(connection.source)
        except KeyError:
            logger.warning('No connector for source %s during disconnect', connection.source)
            connection.delete()
            return Response({'detail': 'Disconnected (no connector found for cleanup).'})

        connector.disconnect(connection)
        return Response({'detail': 'Source disconnected successfully.'})
