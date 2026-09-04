"""Bounded video-research capability for ATLAS.

This layer does not search YouTube and does not download videos.
It receives an already-discovered public YouTube URL and turns the real
audio/video content into timestamped research evidence.

The real understanding backend is GeminiProvider's already-existing
understand_youtube_structured() capability.  This module only provides
the source-specific evidence contract and normalization.
"""

from urllib.parse import urlparse

from atlas.integrations.base import VideoEvidence
from atlas.integrations.gemini_provider import GeminiProvider


class VideoResearchError(Exception):
    """A real video-research request could not be completed."""


def _is_public_youtube_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme != "https":
        return False

    host = (parsed.hostname or "").lower()
    return (
        host == "youtu.be"
        or host == "youtube.com"
        or host.endswith(".youtube.com")
    )


class GeminiVideoResearchProvider:
    """Real public-YouTube research via the existing GeminiProvider."""

    name = "gemini_youtube"

    def __init__(self, gemini: GeminiProvider | None = None):
        self._gemini = gemini if gemini is not None else GeminiProvider()

    def analyze_youtube(
        self,
        youtube_url: str,
        max_observations: int = 3,
    ) -> list[VideoEvidence]:
        if not _is_public_youtube_url(youtube_url):
            raise VideoResearchError(
                "video research accepts only public https YouTube URLs"
            )

        if not 1 <= max_observations <= 6:
            raise VideoResearchError(
                "max_observations must be between 1 and 6"
            )

        fields: dict[str, str] = {}
        for i in range(1, max_observations + 1):
            fields[f"observation_{i}_timestamp"] = (
                "the precise MM:SS timestamp for this evidence"
            )
            fields[f"observation_{i}_spoken"] = (
                "what is audibly being said at this timestamp; "
                "empty only if there is no relevant speech"
            )
            fields[f"observation_{i}_visual"] = (
                "what is visibly shown at this timestamp; "
                "empty only if there is no relevant visual evidence"
            )
            fields[f"observation_{i}_evidence_type"] = (
                "AUDIO, VISUAL, or BOTH"
            )
            fields[f"observation_{i}_confidence"] = (
                "HIGH, MEDIUM, or LOW confidence that this observation "
                "is directly supported by the real video"
            )

        prompt = (
            "Analyze this real public YouTube video as research evidence. "
            "Return only observations directly supported by the video's "
            "actual audio and/or visible frames. Use precise timestamps. "
            "Do not infer facts that are not present in the video. "
            "Prefer observations useful for business/research reasoning."
        )

        try:
            raw = self._gemini.understand_youtube_structured(
                youtube_url,
                prompt,
                fields,
            )
        except Exception as exc:
            raise VideoResearchError(
                f"real YouTube understanding failed: {exc}"
            ) from exc

        evidence: list[VideoEvidence] = []

        for i in range(1, max_observations + 1):
            timestamp = raw.get(
                f"observation_{i}_timestamp", ""
            ).strip()
            spoken = raw.get(
                f"observation_{i}_spoken", ""
            ).strip()
            visual = raw.get(
                f"observation_{i}_visual", ""
            ).strip()

            if not timestamp or not (spoken or visual):
                continue

            evidence_type = raw.get(
                f"observation_{i}_evidence_type", ""
            ).strip().upper()

            if evidence_type not in {"AUDIO", "VISUAL", "BOTH"}:
                if spoken and visual:
                    evidence_type = "BOTH"
                elif spoken:
                    evidence_type = "AUDIO"
                else:
                    evidence_type = "VISUAL"

            confidence = raw.get(
                f"observation_{i}_confidence", ""
            ).strip().upper()

            if confidence not in {"HIGH", "MEDIUM", "LOW"}:
                confidence = "UNKNOWN"

            evidence.append(
                VideoEvidence(
                    source_url=youtube_url,
                    timestamp=timestamp,
                    spoken=spoken,
                    visual=visual,
                    evidence_type=evidence_type,
                    confidence=confidence,
                )
            )

        return evidence
