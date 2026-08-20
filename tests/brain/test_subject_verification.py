from atlas.brain.subject_verification import SubjectMatch, verify_subject_match
from atlas.integrations.base import PageObservation


class _FakeAIProvider:
    def __init__(self, verdict: str):
        self._verdict = verdict
        self.last_prompt = None
        self.last_fields = None

    def complete_structured(self, prompt, fields):
        self.last_prompt = prompt
        self.last_fields = fields
        return {"verdict": self._verdict, "reason": "fake"}


def _observation(title="Prostadine", text="Prostadine is a real supplement with 65% commission.") -> PageObservation:
    return PageObservation(url="https://example.com", title=title, text_content=text)


def test_same_verdict_returns_verified_same():
    result = verify_subject_match(_observation(), "Prostadine", ai_provider=_FakeAIProvider("same"))
    assert result == SubjectMatch.VERIFIED_SAME


def test_different_verdict_returns_verified_different():
    result = verify_subject_match(_observation(title="Glucotonic"), "Prostadine", ai_provider=_FakeAIProvider("different"))
    assert result == SubjectMatch.VERIFIED_DIFFERENT


def test_unknown_verdict_returns_unknown():
    result = verify_subject_match(_observation(), "Prostadine", ai_provider=_FakeAIProvider("unknown"))
    assert result == SubjectMatch.UNKNOWN


def test_a_malformed_or_unrecognized_answer_defaults_to_unknown_never_same():
    """Never guess toward VERIFIED_SAME just because nothing contradicts
    it -- an unparseable/empty answer must fail closed to UNKNOWN."""
    result = verify_subject_match(_observation(), "Prostadine", ai_provider=_FakeAIProvider(""))
    assert result == SubjectMatch.UNKNOWN


def test_requested_subject_and_real_observation_text_both_reach_the_prompt():
    provider = _FakeAIProvider("same")
    verify_subject_match(_observation(text="real detail about Prostadine"), "Prostadine", ai_provider=provider)
    assert "Prostadine" in provider.last_prompt
    assert "verdict" in provider.last_fields
