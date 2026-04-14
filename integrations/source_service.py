"""
Source connection helpers for OAuth-based integrations.

Supports:
  - Facebook Messenger via Facebook Login
  - Instagram Messaging via Instagram Login for Business
  - WhatsApp Business via Meta Embedded Signup
"""
import logging
from urllib.parse import parse_qs, urlparse

import requests
from decouple import config

logger = logging.getLogger(__name__)

GRAPH = config('FACEBOOK_BASE_API_URI', default='https://graph.facebook.com/v19.0')
INSTAGRAM_GRAPH = config('INSTAGRAM_GRAPH_API_URI', default='https://graph.instagram.com')
INSTAGRAM_AUTH_BASE = config('INSTAGRAM_AUTH_BASE_URI', default='https://www.instagram.com/oauth/authorize')
INSTAGRAM_OAUTH_BASE = config('INSTAGRAM_OAUTH_BASE_URI', default='https://api.instagram.com/oauth')
TIMEOUT = 10

# Permissions we keep when revoking Messenger access
_KEEP_PERMISSIONS = {'whatsapp_business_management', 'whatsapp_business_messaging', 'public_profile'}


class MetaAPIError(Exception):
    """Raised when a remote OAuth/Graph request returns an error."""


def get_login_url(source: str, state: str = '') -> str:
    """
    Return the login URL for the selected source.
    """
    if source == 'facebook.com':
        params = {
            'client_id': config('FACEBOOK_APP_ID', default=''),
            'config_id': config('FACEBOOK_CONFIG_ID', default=''),
            'redirect_uri': config('FACEBOOK_REDIRECT_URI', default=''),
            'response_type': 'code',
            'state': state,
        }
        qs = '&'.join(f"{k}={v}" for k, v in params.items() if v)
        return f"https://www.facebook.com/dialog/oauth?{qs}"

    if source == 'whatsapp':
        params = {
            'client_id': config('FACEBOOK_APP_ID', default=''),
            'config_id': config('WHATSAPP_FACEBOOK_CONFIG_ID', default=''),
            'redirect_uri': config('FACEBOOK_REDIRECT_URI', default=''),
            'response_type': 'code',
            'state': state,
        }
        qs = '&'.join(f"{k}={v}" for k, v in params.items() if v)
        return f"https://www.facebook.com/dialog/oauth?{qs}"

    if source == 'instagram':
        params = {
            'client_id': config('INSTAGRAM_APP_ID', default=config('FACEBOOK_APP_ID', default='')),
            'redirect_uri': config('INSTAGRAM_REDIRECT_URI', default=config('FACEBOOK_REDIRECT_URI', default='')),
            'response_type': 'code',
            'scope': config(
                'INSTAGRAM_LOGIN_SCOPES',
                default='instagram_business_basic,instagram_business_manage_messages',
            ),
            'state': state,
            'enable_fb_login': config('INSTAGRAM_ENABLE_FB_LOGIN', default='0'),
        }
        qs = '&'.join(f"{k}={v}" for k, v in params.items() if v != '')
        return f"{INSTAGRAM_AUTH_BASE}?{qs}"

    raise ValueError(f"Unsupported source: {source}")


def parse_code_from_url(auth_code_url: str) -> str:
    """Extract the authorization code from the full callback URL."""
    parsed = urlparse(auth_code_url)
    code_list = parse_qs(parsed.query).get('code', [])
    if not code_list:
        raise ValueError("No 'code' found in auth_code URL.")
    return code_list[0].replace('#_', '')


def exchange_code_for_token(code: str) -> str:
    """Exchange a Facebook/Meta code for a user access token."""
    resp = requests.get(
        f"{GRAPH}/oauth/access_token",
        params={
            'client_id': config('FACEBOOK_APP_ID', default=''),
            'redirect_uri': config('FACEBOOK_REDIRECT_URI', default=''),
            'client_secret': config('FACEBOOK_APP_SECRET', default=''),
            'code': code,
        },
        timeout=TIMEOUT,
    )
    data = resp.json()
    if 'error' in data:
        logger.error("Token exchange error: %s", data)
        raise MetaAPIError(data['error'].get('message', 'Token exchange failed'))
    return data['access_token']


def exchange_instagram_code_for_token(code: str) -> dict:
    """Exchange an Instagram authorization code for a short-lived token."""
    resp = requests.post(
        f"{INSTAGRAM_OAUTH_BASE}/access_token",
        data={
            'client_id': config('INSTAGRAM_APP_ID', default=config('FACEBOOK_APP_ID', default='')),
            'client_secret': config('INSTAGRAM_APP_SECRET', default=config('FACEBOOK_APP_SECRET', default='')),
            'grant_type': 'authorization_code',
            'redirect_uri': config('INSTAGRAM_REDIRECT_URI', default=config('FACEBOOK_REDIRECT_URI', default='')),
            'code': code,
        },
        timeout=TIMEOUT,
    )
    data = resp.json()
    if 'error' in data or 'error_message' in data or 'error_type' in data:
        logger.error("Instagram token exchange error: %s", data)
        raise MetaAPIError(
            data.get('error_message')
            or data.get('error', {}).get('message')
            or 'Instagram token exchange failed'
        )

    payload = data.get('data', [{}])[0] if isinstance(data.get('data'), list) else data
    if not payload.get('access_token'):
        logger.error("Instagram token exchange missing access token: %s", data)
        raise MetaAPIError('Instagram token exchange failed')
    return payload


def exchange_instagram_for_long_lived_token(short_lived_token: str) -> dict:
    """Exchange a short-lived Instagram token for a long-lived token."""
    resp = requests.get(
        f"{INSTAGRAM_GRAPH}/access_token",
        params={
            'grant_type': 'ig_exchange_token',
            'client_secret': config(
                'INSTAGRAM_APP_SECRET',
                default=config('FACEBOOK_APP_SECRET', default=''),
            ),
            'access_token': short_lived_token,
        },
        timeout=TIMEOUT,
    )
    data = resp.json()
    if 'error' in data:
        logger.error("Instagram long-lived token exchange error: %s", data)
        raise MetaAPIError(data['error'].get('message', 'Failed to get long-lived Instagram token'))
    if not data.get('access_token'):
        logger.error("Instagram long-lived token response missing access token: %s", data)
        raise MetaAPIError('Failed to get long-lived Instagram token')
    return data


def get_instagram_user_profile(access_token: str) -> dict:
    """
    Fetch the logged-in Instagram professional account profile.

    We keep the field set intentionally small because Instagram Login returns an
    Instagram-scoped user identity directly rather than a Facebook Page.
    """
    resp = requests.get(
        f"{INSTAGRAM_GRAPH}/me",
        params={
            'fields': 'user_id,username,name,profile_picture_url',
            'access_token': access_token,
        },
        timeout=TIMEOUT,
    )
    data = resp.json()
    if 'error' in data:
        logger.error("get_instagram_user_profile error: %s", data)
        raise MetaAPIError(data['error'].get('message', 'Failed to fetch Instagram profile'))
    return data

def subscribe_instagram_page(page_token: str):
    """Subscribe a page to Instagram webhook fields."""
    resp = requests.post(
        f"{INSTAGRAM_GRAPH}/me/subscribed_apps",
        params={'access_token': page_token},
        data={},
        timeout=TIMEOUT,
    )
    data = resp.json()
    if not data.get('success'):
        logger.warning("Instagram page subscription non-success: %s", data)


def unsubscribe_instagram_page(page_token: str):
    """Unsubscribe a page from Instagram webhook fields."""
    resp = requests.delete(
        f"{INSTAGRAM_GRAPH}/me/subscribed_apps",
        params={'access_token': page_token},
        data={},
        timeout=TIMEOUT,
    )
    data = resp.json()
    if not data.get('success'):
        logger.warning("Instagram page subscription non-success: %s", data)


def get_facebook_pages(access_token: str) -> list:
    """Return the Facebook Pages the user manages."""
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
    """Subscribe a page to Messenger webhook fields."""
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


def get_waba_id(access_token: str) -> str | None:
    """
    Inspect granular scopes and find the WABA id granted under
    whatsapp_business_management.
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

    for scope_obj in data.get('data', {}).get('granular_scopes', []):
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
    """Unsubscribe the app from a WABA's webhooks."""
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


def revoke_facebook_permissions(access_token: str):
    """Revoke all granted Facebook permissions except those needed for WhatsApp."""
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
