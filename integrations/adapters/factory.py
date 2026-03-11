from .whatsapp import WhatsappAdapter
from .instagram import InstagramAdapter
from .messenger import MessengerAdapter
from .base import BaseChannelAdapter

_ADAPTER_MAP = {
    'whatsapp': WhatsappAdapter,
    'instagram': InstagramAdapter,
    'messenger': MessengerAdapter,
}


class AdapterFactory:
    """
    Returns the correct channel adapter for a given Channel instance.

    Usage:
        adapter = AdapterFactory.get(channel)
        adapter.send_message(customer, message, channel)
    """

    @staticmethod
    def get(channel) -> BaseChannelAdapter:
        key = channel.channel_type.key
        cls = _ADAPTER_MAP.get(key)
        if not cls:
            raise ValueError(
                f'No adapter registered for channel type "{key}". '
                f'Supported: {list(_ADAPTER_MAP.keys())}'
            )
        return cls()

    @staticmethod
    def supports(channel_type_key: str) -> bool:
        return channel_type_key in _ADAPTER_MAP
