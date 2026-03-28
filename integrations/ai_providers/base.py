from abc import ABC, abstractmethod


class AbstractAIProvider(ABC):
    """
    Provider-agnostic interface for AI reply generation.
    Swap providers by implementing this class — no other code changes needed.

    messages format (normalized, provider-independent):
        [
            {'role': 'user',  'content': 'Hello'},
            {'role': 'model', 'content': 'Hi! How can I help?'},
            ...
        ]
    'model' role = any non-customer speaker (agent or bot previous reply).
    """

    @abstractmethod
    def complete(self, system_prompt: str, messages: list[dict]) -> str:
        """
        Generate a reply given a system prompt and conversation history.
        Returns the reply text.
        Raises on unrecoverable error (caller handles logging).
        """
