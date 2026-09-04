import pytest

from atlas.brain.audio_plugin import AudioPlugin, AudioPluginError, PathNotApprovedError
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

    def understand_audio(self, audio_bytes, prompt, mime_type="audio/wav"):
        self.understand_calls.append((audio_bytes, prompt, mime_type))
        return self._description

    def understand_audio_structured(self, audio_bytes, prompt, fields, mime_type="audio/wav"):
        self.structured_calls.append((audio_bytes, prompt, fields, mime_type))
        return self._structured


def _allowlist():
    return ResourceAllowlist(store=_FakeStore())


def test_can_handle_recognizes_real_audio_extensions(tmp_path):
    plugin = AudioPlugin(allowlist=_allowlist())
    assert plugin.can_handle(str(tmp_path / "clip.wav")) is True
    assert plugin.can_handle(str(tmp_path / "clip.mp3")) is True
    assert plugin.can_handle(str(tmp_path / "clip.flac")) is True


def test_can_handle_rejects_non_audio_files(tmp_path):
    plugin = AudioPlugin(allowlist=_allowlist())
    assert plugin.can_handle(str(tmp_path / "notes.txt")) is False
    assert plugin.can_handle(str(tmp_path / "clip.mp4")) is False


def test_observe_refuses_a_path_outside_the_approved_folder(tmp_path):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"real-fake-wav-bytes")
    plugin = AudioPlugin(allowlist=_allowlist(), gemini_provider=_FakeGeminiProvider())

    with pytest.raises(PathNotApprovedError):
        plugin.observe(str(audio))


def test_observe_reads_and_understands_a_real_approved_audio_file(tmp_path):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"real-fake-wav-bytes")
    allowlist = _allowlist()
    allowlist.approve_folder(str(tmp_path))
    fake_provider = _FakeGeminiProvider(description="Atlas hearing test. The keto diet product costs $47.")
    plugin = AudioPlugin(allowlist=allowlist, gemini_provider=fake_provider)

    observation = plugin.observe(str(audio))

    assert observation.text_content == "Atlas hearing test. The keto diet product costs $47."
    assert observation.title == "clip.wav"
    assert len(fake_provider.understand_calls) == 1
    assert fake_provider.understand_calls[0][0] == b"real-fake-wav-bytes"
    assert fake_provider.understand_calls[0][2] == "audio/wav"


def test_observe_raises_on_a_real_missing_file(tmp_path):
    allowlist = _allowlist()
    allowlist.approve_folder(str(tmp_path))
    plugin = AudioPlugin(allowlist=allowlist, gemini_provider=_FakeGeminiProvider())

    with pytest.raises(AudioPluginError, match="not found"):
        plugin.observe(str(tmp_path / "missing.wav"))


def test_observe_with_extract_routes_through_structured_understanding(tmp_path):
    audio = tmp_path / "clip.mp3"
    audio.write_bytes(b"real-fake-mp3-bytes")
    allowlist = _allowlist()
    allowlist.approve_folder(str(tmp_path))
    fake_provider = _FakeGeminiProvider(structured={"price": "$47"})
    plugin = AudioPlugin(allowlist=allowlist, gemini_provider=fake_provider)

    observation = plugin.observe(str(audio), extract={"price": "the price mentioned"})

    assert observation.structured_data == {"price": "$47"}
    assert len(fake_provider.structured_calls) == 1


def test_a_real_provider_failure_is_wrapped_loudly(tmp_path):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"real-fake-wav-bytes")
    allowlist = _allowlist()
    allowlist.approve_folder(str(tmp_path))

    class _FailingProvider:
        name = "failing"

        def understand_audio(self, audio_bytes, prompt, mime_type="audio/wav"):
            from atlas.integrations.gemini_provider import GeminiProviderError

            raise GeminiProviderError("real audio outage")

    plugin = AudioPlugin(allowlist=allowlist, gemini_provider=_FailingProvider())

    with pytest.raises(AudioPluginError, match="real audio outage"):
        plugin.observe(str(audio))


def test_name_is_audio():
    assert AudioPlugin(allowlist=_allowlist()).name == "audio"


def test_observe_evidence_returns_canonical_audio_media_evidence(tmp_path):
    audio = tmp_path / "clip.wav"
    audio_bytes = b"real-fake-wav-bytes"
    audio.write_bytes(audio_bytes)

    allowlist = _allowlist()
    allowlist.approve_folder(str(tmp_path))

    fake_provider = _FakeGeminiProvider(
        structured={
            "audible": "One speaker is speaking clearly.",
            "transcribed_text": "Atlas audio qualification price forty seven dollars.",
            "confidence": "HIGH",
        }
    )

    plugin = AudioPlugin(
        allowlist=allowlist,
        gemini_provider=fake_provider,
    )

    evidence = plugin.observe_evidence(str(audio))

    assert len(evidence) == 1
    item = evidence[0]

    assert item.source_ref == str(audio.resolve())
    assert item.modality == "audio"
    assert item.locator == "audio:whole"
    assert item.audible == "One speaker is speaking clearly."
    assert item.transcribed_text == "Atlas audio qualification price forty seven dollars."
    assert item.confidence == "HIGH"
    assert item.observed_at
    assert len(item.content_hash) == 64
