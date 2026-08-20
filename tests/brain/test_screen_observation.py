import pytest

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.screen_observation import observe_and_record_screen
from atlas.brain.screen_reader import ScreenReaderError


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


class _FakeScreenReader:
    def __init__(self, description="a real screen description", error=None):
        self._description = description
        self._error = error
        self.calls = []

    def read_screen(self, prompt=None):
        self.calls.append(prompt)
        if self._error:
            raise self._error
        from atlas.integrations.base import PageObservation

        return PageObservation(url="screen://local", title="t", text_content=self._description)


def test_observe_and_record_screen_saves_a_real_finding():
    knowledge = KnowledgeBase(store=_FakeStore())
    reader = _FakeScreenReader(description="Digistore24 category page showing Product X, 60% commission")

    finding = observe_and_record_screen("affiliate", subject="Product X", market="US", screen_reader=reader, knowledge=knowledge)

    saved = knowledge.findings()
    assert len(saved) == 1
    assert saved[0].id == finding.id
    assert saved[0].category == "affiliate"
    assert saved[0].subject == "Product X"
    assert saved[0].market == "US"
    assert saved[0].source == "screen_observation"
    assert "Product X" in saved[0].description


def test_observe_and_record_screen_evidence_role_is_primary_observation():
    """ONE BRAIN Evidence Role Gate (2026-08-17): ATLAS directly observing
    its own real, current screen -- no external claimant exists here at
    all, by construction."""
    knowledge = KnowledgeBase(store=_FakeStore())
    reader = _FakeScreenReader()

    finding = observe_and_record_screen("affiliate", screen_reader=reader, knowledge=knowledge)

    assert finding.evidence_role == "primary_observation"
    assert finding.claimant == ""


def test_observe_and_record_screen_passes_through_a_custom_prompt():
    knowledge = KnowledgeBase(store=_FakeStore())
    reader = _FakeScreenReader()

    observe_and_record_screen("affiliate", prompt="What commission rate is shown?", screen_reader=reader, knowledge=knowledge)

    assert reader.calls == ["What commission rate is shown?"]


def test_observe_and_record_screen_raises_loudly_on_a_real_capture_failure():
    knowledge = KnowledgeBase(store=_FakeStore())
    reader = _FakeScreenReader(error=ScreenReaderError("no display available"))

    with pytest.raises(ScreenReaderError, match="no display available"):
        observe_and_record_screen("affiliate", screen_reader=reader, knowledge=knowledge)

    assert knowledge.findings() == []


def test_later_recall_finds_the_recorded_screen_observation():
    from atlas.brain.recall import recall

    knowledge = KnowledgeBase(store=_FakeStore())
    reader = _FakeScreenReader(description="KetoDNA product page, personalized macro plan")

    observe_and_record_screen("affiliate", subject="KetoDNA", screen_reader=reader, knowledge=knowledge)
    hits = recall("KetoDNA", knowledge=knowledge)

    assert len(hits) == 1
    assert hits[0].store == "finding"
