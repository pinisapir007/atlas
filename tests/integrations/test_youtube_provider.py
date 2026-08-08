import json
import urllib.error
from unittest.mock import patch

import pytest

from atlas.integrations.youtube_provider import YouTubeAPIError, YouTubeProvider


class _FakeResponse:
    def __init__(self, body: dict):
        self._body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return self._body


def test_name_is_youtube():
    assert YouTubeProvider().name == "youtube"


def test_search_returns_none_when_no_api_key_configured(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    assert YouTubeProvider().search("keto snacks") is None


def test_video_details_returns_none_when_no_api_key_configured(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    assert YouTubeProvider().video_details("abc123") is None


def test_search_sends_the_real_key_and_returns_real_items(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "real-test-key")
    real_items = [{"id": {"videoId": "abc123"}, "snippet": {"title": "Real keto video"}}]
    with patch("urllib.request.urlopen", return_value=_FakeResponse({"items": real_items})) as urlopen:
        results = YouTubeProvider().search("keto snacks", max_results=3)

    assert results == real_items
    sent_url = urlopen.call_args[0][0]
    assert "key=real-test-key" in sent_url
    assert "q=keto" in sent_url
    assert "maxResults=3" in sent_url


def test_video_details_returns_the_first_real_item(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "real-test-key")
    real_item = {"id": "abc123", "statistics": {"viewCount": "1000"}}
    with patch("urllib.request.urlopen", return_value=_FakeResponse({"items": [real_item]})):
        result = YouTubeProvider().video_details("abc123")

    assert result == real_item


def test_video_details_returns_none_for_a_real_but_empty_items_list(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "real-test-key")
    with patch("urllib.request.urlopen", return_value=_FakeResponse({"items": []})):
        result = YouTubeProvider().video_details("unknown-id")

    assert result is None


def test_raises_when_response_has_no_real_items_list(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "real-test-key")
    with patch("urllib.request.urlopen", return_value=_FakeResponse({"error": "something"})):
        with pytest.raises(YouTubeAPIError, match="no real 'items' list"):
            YouTubeProvider().search("keto snacks")


def test_raises_clearly_on_http_error(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "real-test-key")
    import io

    err = urllib.error.HTTPError(url="u", code=403, msg="Forbidden", hdrs=None, fp=io.BytesIO(b'{"error": "forbidden"}'))
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(YouTubeAPIError, match="HTTP 403"):
            YouTubeProvider().search("keto snacks")


def test_raises_on_malformed_json(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "real-test-key")

    class _BadResponse(_FakeResponse):
        def read(self) -> bytes:
            return b"not json{"

    with patch("urllib.request.urlopen", return_value=_BadResponse({})):
        with pytest.raises(YouTubeAPIError, match="non-JSON body"):
            YouTubeProvider().search("keto snacks")
