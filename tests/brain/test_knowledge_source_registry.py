import pytest

from atlas.brain.audio_plugin import AudioPlugin
from atlas.brain.browser_plugin import BrowserPlugin
from atlas.brain.document_plugin import DocumentPlugin
from atlas.brain.image_plugin import ImagePlugin
from atlas.brain.knowledge_source_registry import KNOWLEDGE_SOURCE_PLUGINS, select_plugin
from atlas.brain.video_plugin import VideoPlugin
from atlas.brain.youtube_plugin import YouTubePlugin
from atlas.integrations.base import KnowledgeSourcePlugin


def test_registry_has_six_real_implementations():
    assert len(KNOWLEDGE_SOURCE_PLUGINS) == 6
    for cls in (YouTubePlugin, BrowserPlugin, DocumentPlugin, ImagePlugin, AudioPlugin, VideoPlugin):
        assert any(isinstance(p, cls) for p in KNOWLEDGE_SOURCE_PLUGINS)


def test_every_real_plugin_satisfies_the_protocol_structurally():
    for plugin in KNOWLEDGE_SOURCE_PLUGINS:
        assert isinstance(plugin, KnowledgeSourcePlugin)


def test_select_plugin_dispatches_a_url_to_the_browser_plugin():
    plugin = select_plugin("https://example.com")
    assert isinstance(plugin, BrowserPlugin)


def test_select_plugin_dispatches_a_youtube_url_to_the_youtube_plugin_not_the_browser_plugin():
    # A YouTube URL structurally matches BrowserPlugin's generic http(s)
    # check too -- this is the real reason YouTubePlugin must be listed
    # first in the registry, proven here rather than just asserted.
    plugin = select_plugin("https://www.youtube.com/watch?v=jNQXAC9IVRw")
    assert isinstance(plugin, YouTubePlugin)

    plugin = select_plugin("https://youtu.be/jNQXAC9IVRw")
    assert isinstance(plugin, YouTubePlugin)


def test_select_plugin_dispatches_a_text_file_to_the_document_plugin():
    plugin = select_plugin("C:/scratch/notes.txt")
    assert isinstance(plugin, DocumentPlugin)


def test_select_plugin_dispatches_an_image_file_to_the_image_plugin():
    plugin = select_plugin("C:/scratch/photo.png")
    assert isinstance(plugin, ImagePlugin)


def test_select_plugin_dispatches_an_audio_file_to_the_audio_plugin():
    plugin = select_plugin("C:/scratch/clip.mp3")
    assert isinstance(plugin, AudioPlugin)


def test_select_plugin_dispatches_a_video_file_to_the_video_plugin():
    plugin = select_plugin("C:/scratch/clip.mp4")
    assert isinstance(plugin, VideoPlugin)


def test_select_plugin_raises_for_an_unrecognized_source():
    with pytest.raises(ValueError, match="no registered knowledge source plugin"):
        select_plugin("some-random-string-not-a-real-source")
