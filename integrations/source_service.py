"""
SourceConnectionService — Meta OAuth connect/disconnect flow.

Supports:
  - Facebook Messenger (source = 'facebook.com')
  - WhatsApp Business (source = 'whatsapp')

Flow:
  Phase A  →  get_login_url(source)     →  returns Meta OAuth URL for frontend to open
  Phase B  →  finalize_*(business, ...)  →  exchange code, discover pages/WABA, persist
"""
import logging
from urllib.parse import urlparse, parse_qs

import requests
from decouple import config

logger = logging.getLogger(__name__)

GRAPH   = config('FACEBOOK_BASE_API_URI', default='https://graph.facebook.com/v19.0')
TIMEOUT = 10  # seconds for all Meta API calls

# Permissions we keep when revoking Messenger access
_KEEP_PERMISSIONS = {'whatsapp_business_management', 'whatsapp_business_messaging', 'public_profile'}


class MetaAPIError(Exception):
    """Raised when a Meta Graph API call returns an error."""


# ─────────────────────────────────────────────────────────────────────────────
# Login URL generation
# ─────────────────────────────────────────────────────────────────────────────

def get_login_url(source: str, state: str = '') -> str:
    """
    Return a Meta OAuth URL that opens the Embedded Signup / Login dialog.
    source = 'facebook.com' → uses FACEBOOK_CONFIG_ID
    source = 'whatsapp'     → uses WHATSAPP_FACEBOOK_CONFIG_ID
    """
    if source == 'facebook.com':
        config_id = config('FACEBOOK_CONFIG_ID', default='')
    elif source == 'whatsapp':
        config_id = config('WHATSAPP_FACEBOOK_CONFIG_ID', default='')
    else:
        raise ValueError(f"Unsupported source: {source}")

    params = {
        'client_id':     config('FACEBOOK_APP_ID', default=''),
        'config_id':     config_id,
        'redirect_uri':  config('FACEBOOK_REDIRECT_URI', default=''),
        'response_type': 'code',
        'state':         state,
    }
    qs = '&'.join(f"{k}={v}" for k, v in params.items() if v)
    return f"https://www.facebook.com/dialog/oauth?{qs}"


# ─────────────────────────────────────────────────────────────────────────────
# Token exchange (shared)
# ─────────────────────────────────────────────────────────────────────────────

def parse_code_from_url(auth_code_url: str) -> str:
    """auth_code is the full redirect URL; extract the `code` query param."""
    parsed = urlparse(auth_code_url)
    code_list = parse_qs(parsed.query).get('code', [])
    if not code_list:
        raise ValueError("No 'code' found in auth_code URL.")
    return code_list[0]


def exchange_code_for_token(code: str) -> str:
    """Exchange a short-lived code for a user access token."""
    resp = requests.get(
        f"{GRAPH}/oauth/access_token",
        params={
            'client_id':     config('FACEBOOK_APP_ID',     default=''),
            'redirect_uri':  config('FACEBOOK_REDIRECT_URI', default=''),
            'client_secret': config('FACEBOOK_APP_SECRET', default=''),
            'code':          code,
        },
        timeout=TIMEOUT,
    )
    data = resp.json()
    if 'error' in data:
        logger.error("Token exchange error: %s", data)
        raise MetaAPIError(data['error'].get('message', 'Token exchange failed'))
    return data['access_token']


# ─────────────────────────────────────────────────────────────────────────────
# Messenger helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_facebook_pages(access_token: str) -> list:
    """Return list of Facebook Pages the user manages."""
    resp = requests.get(
        f"{GRAPH}/me/accounts",
        params={'access_token': access_token},
        timeout=TIMEOUT,
    )
    data = resp.json()
    if 'error' in data:
        logger.error("get_facebook_pages error: %s", data)
        raise MetaAPIError(data['error'].get('message', 'Failed to fetch Facebook pages'))
    return data.get('data', [])


def subscribe_messenger_page(page_token: str):
    """Subscribe a page to the required webhook fields."""
    resp = requests.post(
        f"{GRAPH}/me/subscribed_apps",
        params={'access_token': page_token},
        data={'subscribed_fields': 'messages,message_reactions,message_reads,ratings'},
        timeout=TIMEOUT,
    )
    data = resp.json()
    if not data.get('success'):
        logger.warning("Messenger page subscription non-success: %s", data)


def get_page_metadata(page_id: str, access_token: str) -> dict:
    """Fetch business/verification metadata for a page."""
    resp = requests.get(
        f"{GRAPH}/{page_id}",
        headers={'Authorization': f"Bearer {access_token}"},
        params={'fields': 'business{id,name,verification_status},verification_status'},
        timeout=TIMEOUT,
    )
    data = resp.json()
    if 'error' in data:
        logger.error("get_page_metadata error: %s", data)
        return {}
    return data


# ─────────────────────────────────────────────────────────────────────────────
# WhatsApp helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_waba_id(access_token: str) -> str | None:
    """
    Use debug_token to inspect granular_scopes and find the WABA id
    granted under whatsapp_business_management.
    """
    admin_token = config('FACEBOOK_APP_ADMIN_TOKEN', default='')
    resp = requests.get(
        f"{GRAPH}/debug_token",
        params={'input_token': access_token},
        headers={'Authorization': f"Bearer {admin_token}"},
        timeout=TIMEOUT,
    )
    data = resp.json()
    if 'error' in data:
        logger.error("debug_token error: %s", data)
        raise MetaAPIError(data['error'].get('message', 'Failed to inspect access token'))

    granular_scopes = data.get('data', {}).get('granular_scopes', [])
    for scope_obj in granular_scopes:
        if scope_obj.get('scope') == 'whatsapp_business_management':
            target_ids = scope_obj.get('target_ids', [])
            if target_ids:
                return str(target_ids[0])
    return None


def subscribe_waba_to_app(waba_id: str):
    """Subscribe a WABA to the app's webhooks."""
    admin_token = config('FACEBOOK_ADMIN_TOKEN', default='')
    resp = requests.post(
        f"{GRAPH}/{waba_id}/subscribed_apps",
        headers={'Authorization': f"Bearer {admin_token}"},
        timeout=TIMEOUT,
    )
    data = resp.json()
    if not data.get('success'):
        logger.warning("WABA subscription non-success: %s", data)


def unsubscribe_waba_from_app(waba_id: str):
    """Unsubscribe the app from a WABA's webhooks (called on disconnect)."""
    admin_token = config('FACEBOOK_ADMIN_TOKEN', default='')
    resp = requests.delete(
        f"{GRAPH}/{waba_id}/subscribed_apps",
        headers={'Authorization': f"Bearer {admin_token}"},
        timeout=TIMEOUT,
    )
    data = resp.json()
    if not data.get('success'):
        logger.warning("WABA unsubscribe non-success for %s: %s", waba_id, data)


def get_waba_phone_numbers(waba_id: str, access_token: str) -> list:
    """Return phone numbers registered under the WABA."""
    resp = requests.get(
        f"{GRAPH}/{waba_id}/phone_numbers",
        headers={'Authorization': f"Bearer {access_token}"},
        timeout=TIMEOUT,
    )
    data = resp.json()
    if 'error' in data:
        logger.error("get_waba_phone_numbers error: %s", data)
        return []
    return data.get('data', [])


def get_waba_metadata(waba_id: str, access_token: str) -> dict:
    """Fetch WABA name, verification status, and business info."""
    resp = requests.get(
        f"{GRAPH}/{waba_id}",
        headers={'Authorization': f"Bearer {access_token}"},
        params={'fields': 'name,business_verification_status,on_behalf_of_business_info'},
        timeout=TIMEOUT,
    )
    data = resp.json()
    if 'error' in data:
        logger.error("get_waba_metadata error: %s", data)
        return {}
    return data


# ─────────────────────────────────────────────────────────────────────────────
# Permission revocation (used on Messenger disconnect)
# ─────────────────────────────────────────────────────────────────────────────

def revoke_facebook_permissions(access_token: str):
    """Revoke all granted permissions except those needed for WhatsApp."""
    resp = requests.get(
        f"{GRAPH}/me/permissions",
        params={'access_token': access_token},
        timeout=TIMEOUT,
    )
    for perm in resp.json().get('data', []):
        if perm.get('status') == 'granted' and perm['permission'] not in _KEEP_PERMISSIONS:
            requests.delete(
                f"{GRAPH}/me/permissions/{perm['permission']}",
                params={'access_token': access_token},
                timeout=TIMEOUT,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Channel sync helpers (keep Channel model in sync after connect)
# ─────────────────────────────────────────────────────────────────────────────

def sync_messenger_channel(connection):
    """Create or update the Channel record for a finalized Messenger connection."""
    from .models import Channel, ChannelType
    ch_type = ChannelType.objects.filter(key='messenger').first()
    if not ch_type or not connection.page_id:
        return
    Channel.objects.update_or_create(
        business=connection.business,
        channel_type=ch_type,
        page_id=connection.page_id,
        defaults={
            'name':         connection.page_name or 'Messenger',
            'access_token': connection.page_token,
            'status':       Channel.Status.ACTIVE,
        },
    )


def sync_whatsapp_channel(connection, phone_number_id: str, display_phone: str, access_token: str):
    """Create or update the Channel record for a finalized WhatsApp connection."""
    from .models import Channel, ChannelType
    ch_type = ChannelType.objects.filter(key='whatsapp').first()
    if not ch_type or not phone_number_id:
        return
    Channel.objects.update_or_create(
        business=connection.business,
        channel_type=ch_type,
        defaults={
            'name':            f"WhatsApp {display_phone}".strip(),
            'access_token':    access_token,
            'phone_number_id': phone_number_id,
            'status':          Channel.Status.ACTIVE,
        },
    )


def deactivate_channel(business, channel_type_key: str):
    """Mark the Channel as inactive on disconnect."""
    from .models import Channel, ChannelType
    ch_type = ChannelType.objects.filter(key=channel_type_key).first()
    if ch_type:
        Channel.objects.filter(business=business, channel_type=ch_type).update(
            status=Channel.Status.INACTIVE
        )
