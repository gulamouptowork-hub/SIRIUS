from __future__ import annotations

from sirius.config import Settings
from sirius.llm.base import LLMProvider


def create_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "anthropic":
        from sirius.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(settings)
    if settings.llm_provider == "ollama":
        from sirius.llm.ollama_provider import OllamaProvider

        return OllamaProvider(settings)
    if settings.llm_provider == "nvidia":
        import json

        from sirius.llm.openai_compat import OpenAICompatProvider

        extra_body = json.loads(settings.nvidia_extra_body) if settings.nvidia_extra_body else {}
        return OpenAICompatProvider(
            settings.nvidia_base_url,
            settings.nvidia_api_key,
            settings.nvidia_model,
            settings.llm_max_tokens,
            timeout=settings.llm_timeout_seconds,
            extra_body=extra_body,
        )
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
