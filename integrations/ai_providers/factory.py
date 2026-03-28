from .base import AbstractAIProvider


def get_ai_provider(ai_config) -> AbstractAIProvider:
    """
    Return the correct provider instance for the given AIConfig.
    Add a new elif here when adding a new provider — nothing else changes.
    """
    if ai_config.provider == 'gemini':
        from .gemini import GeminiProvider
        return GeminiProvider(
            api_key=ai_config.api_key,
            model_name=ai_config.model_name,
        )

    if ai_config.provider == 'openai':
        from .openai import OpenAIProvider
        return OpenAIProvider(
            api_key=ai_config.api_key,
            model_name=ai_config.model_name,
        )

    raise ValueError(f'Unknown AI provider: {ai_config.provider}')
