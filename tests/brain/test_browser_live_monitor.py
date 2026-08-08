from atlas.brain.browser_live_monitor import observe_and_compare
from atlas.integrations.base import PageObservation


class _FakeObserver:
    name = "fake"

    def __init__(self, observations):
        self._observations = list(observations)
        self.calls = []

    def observe(self, url, extract=None):
        self.calls.append(url)
        return self._observations.pop(0)


def test_first_real_check_with_no_previous_reports_changed():
    observer = _FakeObserver([PageObservation(url="u", title="Real Title", text_content="real content")])

    current, result = observe_and_compare(observer, "https://example.com", previous=None)

    assert result.changed is True
    assert result.title_changed is True
    assert result.text_changed is True
    assert current.title == "Real Title"


def test_no_real_change_between_two_identical_observations():
    obs = PageObservation(url="u", title="Real Title", text_content="real content")
    observer = _FakeObserver([obs, obs])

    first, _ = observe_and_compare(observer, "https://example.com", previous=None)
    second, result = observe_and_compare(observer, "https://example.com", previous=first)

    assert result.changed is False
    assert result.title_changed is False
    assert result.text_changed is False


def test_detects_a_real_title_change():
    first_obs = PageObservation(url="u", title="Old Title", text_content="same content")
    second_obs = PageObservation(url="u", title="New Title", text_content="same content")
    observer = _FakeObserver([first_obs, second_obs])

    first, _ = observe_and_compare(observer, "https://example.com", previous=None)
    second, result = observe_and_compare(observer, "https://example.com", previous=first)

    assert result.changed is True
    assert result.title_changed is True
    assert result.text_changed is False
    assert result.previous_title == "Old Title"
    assert result.current_title == "New Title"


def test_detects_a_real_text_change():
    first_obs = PageObservation(url="u", title="Same Title", text_content="old real content")
    second_obs = PageObservation(url="u", title="Same Title", text_content="new real content, longer")
    observer = _FakeObserver([first_obs, second_obs])

    first, _ = observe_and_compare(observer, "https://example.com", previous=None)
    second, result = observe_and_compare(observer, "https://example.com", previous=first)

    assert result.changed is True
    assert result.title_changed is False
    assert result.text_changed is True
    assert result.previous_text_length == len("old real content")
    assert result.current_text_length == len("new real content, longer")
