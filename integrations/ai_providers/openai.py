import logging
from .base import AbstractAIProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(AbstractAIProvider):
    """
    OpenAI provider using the openai SDK.
    Initialised once per AIConfig (api_key + model_name).
    """

    def __init__(self, api_key: str, model_name: str = 'gpt-4o-mini'):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key)
        self._model = model_name

    def complete(self, system_prompt: str, messages: list[dict]) -> str:
        """
        Send conversation history to OpenAI and return the reply text.

        messages = [{'role': 'user'|'model', 'content': '...'}]
        OpenAI expects 'assistant' instead of 'model' — mapped here.
        """
        openai_messages = []

        if system_prompt:
            openai_messages.append({'role': 'system', 'content': system_prompt})

        for msg in messages:
            if msg.get('content', '').strip():
                role = 'assistant' if msg['role'] == 'model' else 'user'
                openai_messages.append({'role': role, 'content': msg['content']})

        if not openai_messages:
            return ''

        response = self._client.chat.completions.create(
            model=self._model,
            messages=openai_messages,
        )

        return (response.choices[0].message.content or '').strip()
