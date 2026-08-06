import pytest

from atlas.integrations.ai_provider_registry import AI_PROVIDERS, get_ai_provider
from atlas.integrations.claude_provider import ClaudeProvider
from atlas.integrations.gemini_provider import GeminiProvider


def test_registry_has_two_real_implementations():
    assert set(AI_PROVIDERS) == {"gemini", "claude"}
    assert isinstance(AI_PROVIDERS["gemini"], GeminiProvider)
    assert isinstance(AI_PROVIDERS["claude"], ClaudeProvider)


def test_get_ai_provider_returns_the_real_named_instance():
    assert get_ai_provider("gemini") is AI_PROVIDERS["gemini"]
    assert get_ai_provider("claude") is AI_PROVIDERS["claude"]


def test_get_ai_provider_with_no_name_returns_the_real_default():
    assert get_ai_provider() is AI_PROVIDERS["gemini"]


def test_get_unknown_provider_raises():
    with pytest.raises(ValueError, match="unsupported AI provider"):
        get_ai_provider("chatgpt")


def test_both_real_providers_satisfy_the_ai_provider_protocol_structurally():
    from atlas.integrations.base import AIProvider

    assert isinstance(AI_PROVIDERS["gemini"], AIProvider)
    assert isinstance(AI_PROVIDERS["claude"], AIProvider)
