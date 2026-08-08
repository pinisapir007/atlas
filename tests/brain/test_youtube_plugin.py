import pytest

from atlas.brain.browser_allowlist import BrowserAllowlist
from atlas.brain.youtube_plugin import YouTubePlugin, YouTubePluginError, DomainNotApprovedError


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


class _FakeGeminiProvider:
    name = "fake"

    def __init__(self, description="a real description", structured=None):
        self._description = description
        self._structured = structured or {}
        self.understand_calls = []
        self.structured_calls = []

    def understand_youtube(self, youtube_url, prompt):
        self.understand_calls.append((youtube_url, prompt))
        return self._description

    def understand_youtube_structured(self, youtube_url, prompt, fields):
        self.structured_calls.append((youtube_url, prompt, fields))
        return self._structured


def _allowlist():
    return BrowserAllowlist(store=_FakeStore())


def test_can_handle_recognizes_real_youtube_urls():
    plugin = YouTubePlugin(allowlist=_allowlist())
    assert plugin.can_handle("https://www.youtube.com/watch?v=jNQXAC9IVRw") is True
    assert plugin.can_handle("https://youtu.be/jNQXAC9IVRw") is True


def test_can_handle_rejects_non_youtube_urls():
    plugin = YouTubePlugin(allowlist=_allowlist())
    assert plugin.can_handle("https://example.com") is False
    assert plugin.can_handle("C:/docs/notes.txt") is False


def test_observe_refuses_before_calling_gemini_when_domain_not_approved():
    fake_provider = _FakeGeminiProvider()
    plugin = YouTubePlugin(allowlist=_allowlist(), gemini_provider=fake_provider)

    with pytest.raises(DomainNotApprovedError):
        plugin.observe("https://www.youtube.com/watch?v=jNQXAC9IVRw")

    assert fake_provider.understand_calls == []


def test_observe_understands_a_real_approved_youtube_video():
    allowlist = _allowlist()
    allowlist.approve_domain("youtube.com")
    fake_provider = _FakeGeminiProvider(description="Jawed Karim at the San Diego Zoo elephant enclosure.")
    plugin = YouTubePlugin(allowlist=allowlist, gemini_provider=fake_provider)

    observation = plugin.observe("https://www.youtube.com/watch?v=jNQXAC9IVRw")

    assert observation.text_content == "Jawed Karim at the San Diego Zoo elephant enclosure."
    assert len(fake_provider.understand_calls) == 1
    assert fake_provider.understand_calls[0][0] == "https://www.youtube.com/watch?v=jNQXAC9IVRw"


def test_observe_with_extract_routes_through_structured_understanding():
    allowlist = _allowlist()
    allowlist.approve_domain("youtube.com")
    fake_provider = _FakeGeminiProvider(structured={"topic": "elephants"})
    plugin = YouTubePlugin(allowlist=allowlist, gemini_provider=fake_provider)

    observation = plugin.observe("https://www.youtube.com/watch?v=jNQXAC9IVRw", extract={"topic": "the main topic"})

    assert observation.structured_data == {"topic": "elephants"}
    assert len(fake_provider.structured_calls) == 1


def test_a_real_provider_failure_is_wrapped_loudly():
    allowlist = _allowlist()
    allowlist.approve_domain("youtube.com")

    class _FailingProvider:
        name = "failing"

        def understand_youtube(self, youtube_url, prompt):
            from atlas.integrations.gemini_provider import GeminiProviderError

            raise GeminiProviderError("real youtube outage")

    plugin = YouTubePlugin(allowlist=allowlist, gemini_provider=_FailingProvider())

    with pytest.raises(YouTubePluginError, match="real youtube outage"):
        plugin.observe("https://www.youtube.com/watch?v=jNQXAC9IVRw")


def test_name_is_youtube():
    assert YouTubePlugin(allowlist=_allowlist()).name == "youtube"
