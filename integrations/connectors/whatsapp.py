"""
WhatsAppConnector — WhatsApp Business via Meta Embedded Signup / OAuth.

Connect flow:
  Phase A  →  get_login_url()           returns Meta login dialog URL
  Phase B  →  finalize(request, code)   exchanges code → token → WABA discovery
  PATCH    →  assign(...)               not typically needed (WABA-based, not page-based)
  DELETE   →  disconnect(conn)          deactivates channel, clears stored credentials
"""
import logging

from rest_framework.response import Response

from integrations import source_service as api
from integrations.models import SourceConnection
from integrations.serializers import SourceConnectionSerializer
from .base import BaseConnector

logger = logging.getLogger(__name__)


class WhatsAppConnector(BaseConnector):
    source_key = 'whatsapp'

    # ── Phase A ──────────────────────────────────────────────────────────────

    def get_login_url(self, state: str = '') -> str:
        return api.get_login_url('whatsapp', state=state)

    # ── Phase B ──────────────────────────────────────────────────────────────

    def finalize(self, request, auth_code_url: str):
        business = request.user.business

        try:
            code         = api.parse_code_from_url(auth_code_url)
            access_token = api.exchange_code_for_token(code)
        except (ValueError, api.MetaAPIError) as e:
            return Response({'detail': str(e)}, status=400 if isinstance(e, ValueError) else 401)

        try:
            waba_id = api.get_waba_id(access_token)
        except api.MetaAPIError as e:
            return Response({'detail': str(e)}, status=401)

        if not waba_id:
            return Response(
                {'detail': 'No WhatsApp Business Account found. '
                           'Ensure whatsapp_business_management permission was granted.'},
                status=406,
            )

        conn, _ = SourceConnection.objects.update_or_create(
            business=business,
            source=self.source_key,
            defaults={'user': request.user, 'access_token': access_token, 'waba_id': waba_id},
        )

        # Subscribe WABA to app webhooks
        api.subscribe_waba_to_app(waba_id)

        # Enrich with phone numbers + WABA metadata
        phones    = api.get_waba_phone_numbers(waba_id, access_token)
        waba_meta = api.get_waba_metadata(waba_id, access_token)
        self._persist_waba_metadata(conn, waba_meta)

        if phones:
            phone = phones[0]
            self._sync_channel(
                conn,
                channel_type_key='whatsapp',
                name=f"WhatsApp {phone.get('display_phone_number', '')}".strip(),
                access_token=access_token,
                phone_number_id=phone.get('id', ''),
            )

        return Response(
            {**SourceConnectionSerializer(conn).data, 'waba_id': waba_id, 'phone_numbers': phones},
            status=201,
        )

    # ── PATCH ─────────────────────────────────────────────────────────────────

    def assign(self, request, connection, item: dict):
        """
        WhatsApp is WABA-based — page-level assignment is not applicable.
        This can be used in future to let users pick a specific phone number.
        """
        phone_id      = item.get('phone_number_id', '')
        display_phone = item.get('display_phone_number', '')

        if phone_id:
            self._sync_channel(
                connection,
                channel_type_key='whatsapp',
                name=f"WhatsApp {display_phone}".strip(),
                access_token=connection.access_token,
                phone_number_id=phone_id,
            )

        return Response(SourceConnectionSerializer(connection).data)

    # ── DELETE ────────────────────────────────────────────────────────────────

    def disconnect(self, connection):
        # Unsubscribe app from WABA webhooks before deleting
        if connection.waba_id:
            try:
                api.unsubscribe_waba_from_app(connection.waba_id)
            except Exception:
                logger.warning(
                    'WABA webhook unsubscribe failed for connection %s (waba_id=%s)',
                    connection.id, connection.waba_id,
                )
        self._deactivate_channel(connection.business, 'whatsapp')
        connection.delete()

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _persist_waba_metadata(self, conn, waba_meta: dict):
        biz_info = waba_meta.get('on_behalf_of_business_info', {})
        conn.waba_name                    = waba_meta.get('name', '')
        conn.business_manager_id          = biz_info.get('id',     '')
        conn.business_manager_name        = biz_info.get('name',   '')
        conn.business_verification_status = waba_meta.get('business_verification_status', '')
        conn.business_approved_status     = str(biz_info.get('status', '')).lower()
        conn.save()
