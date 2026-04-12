"""
InstagramConnector - Instagram Messaging via Instagram Login for Business.
"""
from rest_framework.response import Response

from integrations import source_service as api
from integrations.models import SourceConnection
from integrations.serializers import SourceConnectionSerializer
from .base import BaseConnector


class InstagramConnector(BaseConnector):
    source_key = 'instagram'

    def get_login_url(self, state: str = '') -> str:
        return api.get_login_url('instagram', state=state)

    def finalize(self, request, auth_code_url: str):
        business = request.user.business

        try:
            code = api.parse_code_from_url(auth_code_url)
            short_lived = api.exchange_instagram_code_for_token(code)
            long_lived = api.exchange_instagram_for_long_lived_token(short_lived['access_token'])
            profile = api.get_instagram_user_profile(long_lived['access_token'])
        except (ValueError, api.MetaAPIError) as e:
            return Response({'detail': str(e)}, status=400 if isinstance(e, ValueError) else 401)

        instagram_user_id = str(profile.get('user_id') or profile.get('id') or short_lived.get('user_id') or '')
        if not instagram_user_id:
            return Response({'detail': 'Instagram profile ID was not returned by the login flow.'}, status=406)

        conn, _ = SourceConnection.objects.update_or_create(
            business=business,
            source=self.source_key,
            defaults={
                'user': request.user,
                'access_token': long_lived['access_token'],
            },
        )

        username = profile.get('username', '')
        name = profile.get('name', '')
        conn.page_id = instagram_user_id
        conn.page_name = username or name or conn.page_name
        conn.page_token = ''
        conn.business_manager_id = ''
        conn.business_manager_name = ''
        conn.business_approved_status = ''
        conn.business_verification_status = ''
        conn.save()

        display_name = username or name or 'instagram'
        self._sync_channel(
            conn,
            channel_type_key='instagram',
            name=f"Instagram @{display_name}".strip(),
            access_token=long_lived['access_token'],
            page_id=instagram_user_id,
        )

        return Response(
            {
                **SourceConnectionSerializer(conn).data,
                'instagram_user_id': instagram_user_id,
                'instagram_permissions': short_lived.get('permissions', ''),
                'access_token_expires_in': long_lived.get('expires_in'),
            },
            status=201,
        )

    def assign(self, request, connection, item: dict):
        return Response({'detail': 'Instagram Login connections are finalized during OAuth.'}, status=405)

    def disconnect(self, connection):
        self._deactivate_channel(connection.business, 'instagram')
        connection.delete()
