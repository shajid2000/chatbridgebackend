"""
BaseConnector — abstract contract every source connector must implement.

To add a new platform (e.g. Telegram, Line):
  1. Create  integrations/connectors/telegram.py
  2. Subclass BaseConnector and implement all abstract methods
  3. Register it in ConnectorFactory.REGISTRY

Views never call Meta / platform APIs directly — they go through connectors.
"""
from abc import ABC, abstractmethod


class BaseConnector(ABC):
    """
    A connector handles the full lifecycle of connecting a third-party
    messaging source to a business account:

      get_login_url  → Phase A: generate OAuth consent URL
      finalize       → Phase B: exchange code, discover assets, persist
      assign         → PATCH: assign a selected page/number after multi-choice
      disconnect     → DELETE: revoke tokens, deactivate channel
    """

    # Unique string key matching SourceConnection.source — e.g. 'facebook.com'
    source_key: str = ''

    # ── Phase A ──────────────────────────────────────────────────────────────

    @abstractmethod
    def get_login_url(self, state: str = '') -> str:
        """Return the OAuth consent URL to open in the frontend popup."""

    # ── Phase B ──────────────────────────────────────────────────────────────

    @abstractmethod
    def finalize(self, request, auth_code_url: str):
        """
        Exchange auth_code_url → access token, discover assets, persist
        SourceConnection + sync Channel.
        Returns a DRF Response.
        """

    # ── PATCH ────────────────────────────────────────────────────────────────

    @abstractmethod
    def assign(self, request, connection, item: dict):
        """
        Assign a specific page / number / asset chosen by the user.
        Called once per property entry in PATCH body.
        Returns a DRF Response.
        """

    # ── DELETE ───────────────────────────────────────────────────────────────

    @abstractmethod
    def disconnect(self, connection):
        """
        Revoke tokens, deactivate Channel, delete SourceConnection.
        No return value needed — view handles the final Response.
        """

    # ── Shared helpers ───────────────────────────────────────────────────────

    def _sync_channel(self, connection, *, channel_type_key: str, name: str,
                      access_token: str, phone_number_id: str = '', page_id: str = ''):
        """Upsert the Channel record so webhook routing stays in sync."""
        from integrations.models import Channel, ChannelType
        ch_type = ChannelType.objects.filter(key=channel_type_key).first()
        if not ch_type:
            return
        lookup = {'business': connection.business, 'channel_type': ch_type}
        if phone_number_id:
            lookup['phone_number_id'] = phone_number_id
        elif page_id:
            lookup['page_id'] = page_id
        Channel.objects.update_or_create(
            **lookup,
            defaults={'name': name, 'access_token': access_token, 'status': Channel.Status.ACTIVE},
        )

    def _deactivate_channel(self, business, channel_type_key: str):
        """Mark all channels for this type as inactive on disconnect."""
        from integrations.models import Channel, ChannelType
        ch_type = ChannelType.objects.filter(key=channel_type_key).first()
        if ch_type:
            Channel.objects.filter(business=business, channel_type=ch_type).update(
                status=Channel.Status.INACTIVE
            )
