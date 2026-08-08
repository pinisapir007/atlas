import pytest

from atlas.brain.image_plugin import ImagePlugin, ImagePluginError, PathNotApprovedError
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

    def understand_image(self, image_bytes, prompt, media_type="image/png"):
        self.understand_calls.append((image_bytes, prompt, media_type))
        return self._description

    def understand_image_structured(self, image_bytes, prompt, fields, media_type="image/png"):
        self.structured_calls.append((image_bytes, prompt, fields, media_type))
        return self._structured


def _allowlist():
    return ResourceAllowlist(store=_FakeStore())


def test_can_handle_recognizes_real_image_extensions(tmp_path):
    plugin = ImagePlugin(allowlist=_allowlist())
    assert plugin.can_handle(str(tmp_path / "photo.png")) is True
    assert plugin.can_handle(str(tmp_path / "photo.jpg")) is True
    assert plugin.can_handle(str(tmp_path / "photo.webp")) is True


def test_can_handle_rejects_non_image_files(tmp_path):
    plugin = ImagePlugin(allowlist=_allowlist())
    assert plugin.can_handle(str(tmp_path / "notes.txt")) is False
    assert plugin.can_handle("https://example.com") is False


def test_observe_refuses_a_path_outside_the_approved_folder(tmp_path):
    img = tmp_path / "photo.png"
    img.write_bytes(b"real-fake-png-bytes")
    plugin = ImagePlugin(allowlist=_allowlist(), gemini_provider=_FakeGeminiProvider())

    with pytest.raises(PathNotApprovedError):
        plugin.observe(str(img))


def test_observe_reads_and_understands_a_real_approved_image(tmp_path):
    img = tmp_path / "photo.png"
    img.write_bytes(b"real-fake-png-bytes")
    allowlist = _allowlist()
    allowlist.approve_folder(str(tmp_path))
    fake_provider = _FakeGeminiProvider(description="A real photo showing a keto meal.")
    plugin = ImagePlugin(allowlist=allowlist, gemini_provider=fake_provider)

    observation = plugin.observe(str(img))

    assert observation.text_content == "A real photo showing a keto meal."
    assert observation.title == "photo.png"
    assert len(fake_provider.understand_calls) == 1
    assert fake_provider.understand_calls[0][0] == b"real-fake-png-bytes"


def test_observe_raises_on_a_real_missing_file(tmp_path):
    allowlist = _allowlist()
    allowlist.approve_folder(str(tmp_path))
    plugin = ImagePlugin(allowlist=allowlist, gemini_provider=_FakeGeminiProvider())

    with pytest.raises(ImagePluginError, match="not found"):
        plugin.observe(str(tmp_path / "missing.png"))


def test_observe_with_extract_routes_through_structured_understanding(tmp_path):
    img = tmp_path / "photo.png"
    img.write_bytes(b"real-fake-png-bytes")
    allowlist = _allowlist()
    allowlist.approve_folder(str(tmp_path))
    fake_provider = _FakeGeminiProvider(structured={"product": "KetoDNA"})
    plugin = ImagePlugin(allowlist=allowlist, gemini_provider=fake_provider)

    observation = plugin.observe(str(img), extract={"product": "the product name shown"})

    assert observation.structured_data == {"product": "KetoDNA"}
    assert len(fake_provider.structured_calls) == 1


def test_a_real_provider_failure_is_wrapped_loudly(tmp_path):
    img = tmp_path / "photo.png"
    img.write_bytes(b"real-fake-png-bytes")
    allowlist = _allowlist()
    allowlist.approve_folder(str(tmp_path))

    class _FailingProvider:
        name = "failing"

        def understand_image(self, image_bytes, prompt, media_type="image/png"):
            from atlas.integrations.gemini_provider import GeminiProviderError

            raise GeminiProviderError("real vision outage")

    plugin = ImagePlugin(allowlist=allowlist, gemini_provider=_FailingProvider())

    with pytest.raises(ImagePluginError, match="real vision outage"):
        plugin.observe(str(img))


def test_name_is_image():
    assert ImagePlugin(allowlist=_allowlist()).name == "image"
