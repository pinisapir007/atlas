import pytest

from atlas.brain.video_plugin import VideoPlugin, VideoPluginError, PathNotApprovedError
from atlas.brain.resource_allowlist import ResourceAllowlist


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

    def understand_video(self, video_bytes, prompt, mime_type="video/mp4"):
        self.understand_calls.append((video_bytes, prompt, mime_type))
        return self._description

    def understand_video_structured(self, video_bytes, prompt, fields, mime_type="video/mp4"):
        self.structured_calls.append((video_bytes, prompt, fields, mime_type))
        return self._structured


def _allowlist():
    return ResourceAllowlist(store=_FakeStore())


def test_can_handle_recognizes_real_video_extensions(tmp_path):
    plugin = VideoPlugin(allowlist=_allowlist())
    assert plugin.can_handle(str(tmp_path / "clip.mp4")) is True
    assert plugin.can_handle(str(tmp_path / "clip.mov")) is True
    assert plugin.can_handle(str(tmp_path / "clip.webm")) is True


def test_can_handle_rejects_non_video_files(tmp_path):
    plugin = VideoPlugin(allowlist=_allowlist())
    assert plugin.can_handle(str(tmp_path / "notes.txt")) is False
    assert plugin.can_handle(str(tmp_path / "clip.mp3")) is False


def test_observe_refuses_a_path_outside_the_approved_folder(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"real-fake-mp4-bytes")
    plugin = VideoPlugin(allowlist=_allowlist(), gemini_provider=_FakeGeminiProvider())

    with pytest.raises(PathNotApprovedError):
        plugin.observe(str(video))


def test_observe_reads_and_understands_a_real_approved_video_file(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"real-fake-mp4-bytes")
    allowlist = _allowlist()
    allowlist.approve_folder(str(tmp_path))
    fake_provider = _FakeGeminiProvider(description="A real product demo video.")
    plugin = VideoPlugin(allowlist=allowlist, gemini_provider=fake_provider)

    observation = plugin.observe(str(video))

    assert observation.text_content == "A real product demo video."
    assert observation.title == "clip.mp4"
    assert len(fake_provider.understand_calls) == 1
    assert fake_provider.understand_calls[0][0] == b"real-fake-mp4-bytes"
    assert fake_provider.understand_calls[0][2] == "video/mp4"


def test_observe_raises_on_a_real_missing_file(tmp_path):
    allowlist = _allowlist()
    allowlist.approve_folder(str(tmp_path))
    plugin = VideoPlugin(allowlist=allowlist, gemini_provider=_FakeGeminiProvider())

    with pytest.raises(VideoPluginError, match="not found"):
        plugin.observe(str(tmp_path / "missing.mp4"))


def test_observe_with_extract_routes_through_structured_understanding(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"real-fake-mp4-bytes")
    allowlist = _allowlist()
    allowlist.approve_folder(str(tmp_path))
    fake_provider = _FakeGeminiProvider(structured={"product": "KetoDNA"})
    plugin = VideoPlugin(allowlist=allowlist, gemini_provider=fake_provider)

    observation = plugin.observe(str(video), extract={"product": "the product shown"})

    assert observation.structured_data == {"product": "KetoDNA"}
    assert len(fake_provider.structured_calls) == 1


def test_a_real_provider_failure_is_wrapped_loudly(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"real-fake-mp4-bytes")
    allowlist = _allowlist()
    allowlist.approve_folder(str(tmp_path))

    class _FailingProvider:
        name = "failing"

        def understand_video(self, video_bytes, prompt, mime_type="video/mp4"):
            from atlas.integrations.gemini_provider import GeminiProviderError

            raise GeminiProviderError("real video outage")

    plugin = VideoPlugin(allowlist=allowlist, gemini_provider=_FailingProvider())

    with pytest.raises(VideoPluginError, match="real video outage"):
        plugin.observe(str(video))


def test_name_is_video():
    assert VideoPlugin(allowlist=_allowlist()).name == "video"
