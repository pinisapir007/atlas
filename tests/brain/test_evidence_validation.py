from atlas.brain.evidence_validation import assess_observation_quality
from atlas.integrations.base import PageObservation


class _FakeAIProvider:
    name = "fake"

    def __init__(self, relevant: bool, reason: str = "because"):
        self._relevant = relevant
        self._reason = reason
        self.calls = []

    def complete_structured(self, prompt, fields):
        self.calls.append((prompt, fields))
        return {"relevant": "yes" if self._relevant else "no", "reason": self._reason}


def _long_text(marker: str = "real content") -> str:
    return f"{marker} " * 20  # comfortably above MIN_TEXT_LENGTH


def test_an_observation_with_a_real_error_fails_before_any_ai_call():
    observation = PageObservation(url="u", title="t", text_content="", error="real navigation timeout")
    provider = _FakeAIProvider(relevant=True)

    result = assess_observation_quality(observation, "does keto content sell well?", ai_provider=provider)

    assert result.passed is False
    assert "real navigation timeout" in result.reason
    assert provider.calls == []


def test_text_below_the_minimum_length_fails_before_any_ai_call():
    observation = PageObservation(url="u", title="t", text_content="too short")
    provider = _FakeAIProvider(relevant=True)

    result = assess_observation_quality(observation, "a real task", ai_provider=provider)

    assert result.passed is False
    assert "below the" in result.reason
    assert provider.calls == []


def test_enough_real_text_but_ai_judges_it_off_task_fails():
    observation = PageObservation(url="u", title="t", text_content=_long_text("unrelated cooking recipe"))
    provider = _FakeAIProvider(relevant=False, reason="this is about recipes, not business demand")

    result = assess_observation_quality(observation, "is there demand for a keto supplement?", ai_provider=provider)

    assert result.passed is False
    assert result.ai_relevant is False
    assert "recipes" in result.reason
    assert len(provider.calls) == 1


def test_enough_real_text_and_ai_judges_it_relevant_passes():
    observation = PageObservation(url="u", title="t", text_content=_long_text("real keto demand discussion"))
    provider = _FakeAIProvider(relevant=True, reason="directly discusses real demand")

    result = assess_observation_quality(observation, "is there demand for a keto supplement?", ai_provider=provider)

    assert result.passed is True
    assert result.ai_relevant is True
    assert result.text_length == len(_long_text("real keto demand discussion").strip())


def test_objective_check_alone_never_passes_without_the_ai_relevance_call():
    # Structural: even with plenty of real text, passed=True is only
    # ever reached through the real AI judgment -- never a bypass.
    observation = PageObservation(url="u", title="t", text_content=_long_text())
    provider = _FakeAIProvider(relevant=False)

    result = assess_observation_quality(observation, "a real task", ai_provider=provider)

    assert result.passed is False
    assert len(provider.calls) == 1
