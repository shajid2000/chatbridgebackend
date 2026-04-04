import logging
from .base import AbstractAIProvider
from .bot_prompt import COMPILED_PROMPT

logger = logging.getLogger(__name__)


class GeminiProvider(AbstractAIProvider):
    """
    Google Gemini provider using the google-genai SDK.
    Initialised once per AIConfig (api_key + model_name).
    """

    def __init__(self, api_key: str, model_name: str = 'gemini-2.0-flash'):
        from google import genai
        self._client = genai.Client(api_key=api_key)
        self._model = model_name

    def complete(self, system_prompt: str, messages: list[dict]) -> str:
        if self._model.startswith('gemma'):
            return self._complete_gemma(system_prompt, messages)
        return self._complete_gemini(system_prompt, messages)


    def _complete_gemma(self, system_prompt: str, messages: list[dict]) -> str:
        """
        Gemma-specific completion using single compiled prompt strategy.

        - No system_instruction (unsupported)
        - AI-driven greeting + name collection
        - Includes short conversation history
        """

        from google.genai import types

        if not messages:
            return ''

        # --- EXTRACT LAST USER MESSAGE ---
        last_user_msg = next(
            (m['content'] for m in messages if m['role'] == 'user'),
            ''
        )

        # --- BUILD CONVERSATION HISTORY ---
        history_msgs = messages

        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in history_msgs if m.get('content')
        )

        # --- FINAL PROMPT ---
        final_prompt = COMPILED_PROMPT.format(
            SYSTEM_PROMPT=system_prompt,
            HISTORY=history_text,
            LAST_USER_MSG=last_user_msg,
        )

        contents = [
            types.Content(
                role='user',
                parts=[types.Part(text=final_prompt)]
            )
        ]

        # --- CALL GEMMA ---
        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
        )

        # --- SAFE OUTPUT ---
        text = (response.text or '').strip()

        if not text:
            return "Sorry, I couldn't process that. Could you please rephrase?"

        return text
    
    def _complete_gemini(self, system_prompt: str, messages: list[dict]) -> str:
        from google.genai import types

        contents = [
            types.Content(
                role=msg['role'],
                parts=[types.Part(text=msg['content'])],
            )
            for msg in messages
            if msg.get('content', '').strip()
        ]

        if not contents:
            return ''

        wrapped_instruction = system_prompt

        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=wrapped_instruction,
            ),
        )

        return (response.text or '').strip()
