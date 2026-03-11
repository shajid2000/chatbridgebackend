from abc import ABC, abstractmethod
import logging
import requests

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = 'v19.0'
GRAPH_API_BASE = f'https://graph.facebook.com/{GRAPH_API_VERSION}'


class BaseChannelAdapter(ABC):
    """
    Abstract base for all channel adapters.
    Every adapter must implement send_message() and send_media().
    """

    @abstractmethod
    def send_message(self, customer, message, channel) -> dict:
        """
        Send a text message to the customer via this channel.
        Returns the platform API response dict.
        """

    @abstractmethod
    def send_media(self, customer, message, channel) -> dict:
        """
        Send a media message (image, video, audio, file) to the customer.
        Returns the platform API response dict.
        """

    def _post(self, url: str, payload: dict, token: str) -> dict:
        """Shared HTTP helper with error logging."""
        resp = requests.post(
            url,
            json=payload,
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
