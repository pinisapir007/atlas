import pytest

from atlas.integrations.video_research_provider import (
    GeminiVideoResearchProvider,
    VideoResearchError,
)


class FakeGemini:
    def understand_youtube_structured(self, youtube_url, prompt, fields):
        assert youtube_url == "https://www.youtube.com/watch?v=test123"
        assert "actual audio" in prompt
        assert "observation_1_timestamp" in fields

        return {
            "observation_1_timestamp": "02:18",
            "observation_1_spoken": "The speaker explains the framework.",
            "observation_1_visual": "The speaker draws circles on a board.",
            "observation_1_evidence_type": "BOTH",
            "observation_1_confidence": "HIGH",
            "observation_2_timestamp": "",
            "observation_2_spoken": "",
            "observation_2_visual": "",
            "observation_2_evidence_type": "",
            "observation_2_confidence": "",
        }


def test_real_shape_is_normalized_to_video_evidence():
    provider = GeminiVideoResearchProvider(gemini=FakeGemini())

    evidence = provider.analyze_youtube(
        "https://www.youtube.com/watch?v=test123",
        max_observations=2,
    )

    assert len(evidence) == 1
    assert evidence[0].timestamp == "02:18"
    assert evidence[0].evidence_type == "BOTH"
    assert evidence[0].confidence == "HIGH"
    assert "draws circles" in evidence[0].visual


def test_rejects_non_youtube_source():
    provider = GeminiVideoResearchProvider(gemini=FakeGemini())

    with pytest.raises(VideoResearchError):
        provider.analyze_youtube("https://example.com/video.mp4")
