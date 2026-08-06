import pytest

from atlas.brain.browser_allowlist import BrowserAllowlist
from atlas.brain.browser_plugin import BrowserPlugin, DomainNotApprovedError
from atlas.integrations.base import PageObservation


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


class _FakeObserver:
    name = "fake"

    def __init__(self, observation=None):
        self._observation = observation
        self.calls = []

    def observe(self, url, extract=None):
        self.calls.append((url, extract))
        return self._observation


def test_can_handle_recognizes_http_and_https_urls():
    plugin = BrowserPlugin(observer=_FakeObserver(), allowlist=BrowserAllowlist(store=_FakeStore()))
    assert plugin.can_handle("https://example.com") is True
    assert plugin.can_handle("http://example.com") is True


def test_can_handle_rejects_a_non_url_source():
    plugin = BrowserPlugin(observer=_FakeObserver(), allowlist=BrowserAllowlist(store=_FakeStore()))
    assert plugin.can_handle("C:/docs/notes.txt") is False


def test_observe_refuses_before_calling_the_observer_when_domain_not_approved():
    observer = _FakeObserver(observation=PageObservation(url="x", title="x", text_content="x"))
    plugin = BrowserPlugin(observer=observer, allowlist=BrowserAllowlist(store=_FakeStore()))

    with pytest.raises(DomainNotApprovedError):
        plugin.observe("https://reddit.com/r/keto")

    assert observer.calls == []


def test_observe_delegates_to_the_real_wrapped_observer_once_approved():
    allowlist = BrowserAllowlist(store=_FakeStore())
    allowlist.approve_domain("reddit.com")
    observation = PageObservation(url="https://reddit.com/x", title="t", text_content="real content")
    observer = _FakeObserver(observation=observation)
    plugin = BrowserPlugin(observer=observer, allowlist=allowlist)

    result = plugin.observe("https://reddit.com/x", extract={"heading": "the heading"})

    assert result is observation
    assert observer.calls == [("https://reddit.com/x", {"heading": "the heading"})]


def test_name_is_browser():
    assert BrowserPlugin(observer=_FakeObserver(), allowlist=BrowserAllowlist(store=_FakeStore())).name == "browser"
