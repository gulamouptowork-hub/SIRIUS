from __future__ import annotations

from sirius.config import Settings
from sirius.llm.base import LLMProvider


def _nvidia_provider(settings: Settings, model: str, extra_body: dict | None = None):
    from sirius.llm.openai_compat import OpenAICompatProvider

    return OpenAICompatProvider(
        settings.nvidia_base_url,
        settings.nvidia_api_key,
        model,
        settings.llm_max_tokens,
        timeout=settings.llm_timeout_seconds,
        extra_body=extra_body,
    )


def create_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "anthropic":
        from sirius.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(settings)
    if settings.llm_provider == "ollama":
        from sirius.llm.ollama_provider import OllamaProvider

        return OllamaProvider(settings)
    if settings.llm_provider == "nvidia":
        import json

        extra_body = json.loads(settings.nvidia_extra_body) if settings.nvidia_extra_body else {}
        return _nvidia_provider(settings, settings.nvidia_model, extra_body)
    if settings.llm_provider == "router":
        import json

        from sirius.llm.router import CHAT, CODE, RESEARCH, RouterProvider

        # Reasoning options (e.g. DeepSeek thinking) apply to the research
        # branch only — they would slow down or break the other models.
        extra_body = json.loads(settings.nvidia_extra_body) if settings.nvidia_extra_body else {}
        return RouterProvider(
            {
                CODE: _nvidia_provider(settings, settings.router_code_model),
                RESEARCH: _nvidia_provider(settings, settings.router_research_model, extra_body),
                CHAT: _nvidia_provider(settings, settings.router_chat_model),
            }
        )
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
