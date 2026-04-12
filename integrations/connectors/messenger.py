"""
MessengerConnector — Facebook Messenger via Meta OAuth + Graph API.

Connect flow:
  Phase A  →  get_login_url()           returns Meta login dialog URL
  Phase B  →  finalize(request, code)   exchanges code → token → pages
  PATCH    →  assign(request, conn, item)  subscribes selected page
  DELETE   →  disconnect(conn)          revokes permissions, deactivates channel
"""
import logging

from rest_framework.response import Response

from integrations import source_service as api
from integrations.models import SourceConnection
from integrations.serializers import SourceConnectionSerializer
from .base import BaseConnector

logger = logging.getLogger(__name__)


class MessengerConnector(BaseConnector):
    source_key = 'facebook.com'

    # ── Phase A ──────────────────────────────────────────────────────────────

    def get_login_url(self, state: str = '') -> str:
        return api.get_login_url('facebook.com', state=state)

    # ── Phase B ──────────────────────────────────────────────────────────────

    def finalize(self, request, auth_code_url: str):
        business = request.user.business

        try:
            code         = api.parse_code_from_url(auth_code_url)
            access_token = api.exchange_code_for_token(code)
        except (ValueError, api.MetaAPIError) as e:
            return Response({'detail': str(e)}, status=400 if isinstance(e, ValueError) else 401)

        try:
            pages = api.get_facebook_pages(access_token)
        except api.MetaAPIError as e:
            return Response({'detail': str(e)}, status=401)

        if not pages:
            return Response(
                {'detail': 'No Facebook Pages found. Create a Facebook Page first.'},
                status=406,
            )

        conn, _ = SourceConnection.objects.update_or_create(
            business=business,
            source=self.source_key,
            defaults={'user': request.user, 'access_token': access_token},
        )

        if len(pages) == 1:
            self._apply_page(conn, pages[0], access_token)
            return Response(SourceConnectionSerializer(conn).data, status=201)

        # Multiple pages — save draft, let frontend pick via PATCH
        conn.save()
        return Response(
            {**SourceConnectionSerializer(conn).data, 'facebook_pages': pages},
            status=201,
        )

    # ── PATCH ─────────────────────────────────────────────────────────────────

    def assign(self, request, connection, item: dict):
        connection.page_id = item.get('page_id') or item.get('id', '')
        connection.page_name = item.get('page_name') or item.get('name', '')
        connection.page_token = item.get('page_token') or item.get('access_token', '')
        self._apply_page(connection, item, connection.access_token)
        return Response(SourceConnectionSerializer(connection).data)

    # ── DELETE ────────────────────────────────────────────────────────────────

    def disconnect(self, connection):
        self._deactivate_channel(connection.business, 'messenger')
        if connection.access_token:
            try:
                api.revoke_facebook_permissions(connection.access_token)
            except Exception:
                logger.warning('Permission revocation failed for connection %s', connection.id)
        connection.delete()

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _apply_page(self, conn, page: dict, access_token: str):
        """Subscribe page to webhooks, fetch metadata, persist, sync Channel."""
        conn.page_id    = page.get('id',           conn.page_id)
        conn.page_name  = page.get('name',         conn.page_name)
        conn.page_token = page.get('access_token', conn.page_token)

        if conn.page_token:
            api.subscribe_messenger_page(conn.page_token)

        if conn.page_id:
            meta = api.get_page_metadata(conn.page_id, access_token)
            biz  = meta.get('business', {})
            conn.business_manager_id          = biz.get('id',                  '')
            conn.business_manager_name        = biz.get('name',                '')
            conn.business_verification_status = biz.get('verification_status', '')

        conn.save()

        self._sync_channel(
            conn,
            channel_type_key='messenger',
            name=conn.page_name or 'Messenger',
            access_token=conn.page_token,
            page_id=conn.page_id,
        )
