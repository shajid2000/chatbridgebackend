"""
ConnectorFactory — maps source keys to connector instances.

To add a new platform:
  1. Create integrations/connectors/telegram.py (subclass BaseConnector)
  2. Import it here and add to REGISTRY
  3. Done — views and URLs need no changes.
"""
from .messenger import MessengerConnector
from .whatsapp  import WhatsAppConnector


class ConnectorFactory:
    REGISTRY = {
        connector.source_key: connector
        for connector in [
            MessengerConnector(),
            WhatsAppConnector(),
            # TelegramConnector(),   ← future: just uncomment
            # LineConnector(),
        ]
    }

    @classmethod
    def get(cls, source_key: str):
        """
        Return the connector for the given source key.
        Raises KeyError if the source is not registered.
        """
        connector = cls.REGISTRY.get(source_key)
        if connector is None:
            raise KeyError(
                f"No connector registered for source '{source_key}'. "
                f"Available: {list(cls.REGISTRY.keys())}"
            )
        return connector

    @classmethod
    def supported_sources(cls) -> list[str]:
        """Return all registered source keys."""
        return list(cls.REGISTRY.keys())
