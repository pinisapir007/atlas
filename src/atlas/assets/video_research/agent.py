"""VideoResearchAgent -- bounded, read-only YouTube evidence collection.

This asset does not decide what ATLAS should research and does not search
for videos. It executes an already-created video_research Task against one
already-known public YouTube URL.

The actual audio/video understanding remains the responsibility of the
platform-level VideoResearchProvider. This agent only validates the Task,
invokes that capability, and persists the resulting real timestamped
evidence into the shared KnowledgeBase.
"""

from datetime import datetime, timezone

from atlas.brain.atomic_evidence import (
    atomic_from_video_evidence,
    persist_atomic_evidence,
)
from atlas.brain.discovery.video_research_request import (
    parse_video_research_task,
)
from atlas.brain.knowledge import KnowledgeBase
from atlas.integrations.base import VideoResearchProvider
from atlas.integrations.video_research_provider import (
    GeminiVideoResearchProvider,
)

SOURCE_NAME = "video_research"
MAX_OBSERVATIONS = 3


class VideoResearchAgent:
    def __init__(
        self,
        knowledge: KnowledgeBase | None = None,
        video_provider: VideoResearchProvider | None = None,
    ):
        self._knowledge = (
            knowledge if knowledge is not None else KnowledgeBase()
        )
        self._video_provider = (
            video_provider
            if video_provider is not None
            else GeminiVideoResearchProvider()
        )

    def run(self, task=None, **kwargs) -> dict:
        try:
            category, youtube_url = parse_video_research_task(task)
        except (ValueError, AttributeError) as exc:
            return {
                "status": "failed",
                "reason": f"not a real video-research task: {exc}",
            }

        try:
            observations = self._video_provider.analyze_youtube(
                youtube_url,
                max_observations=MAX_OBSERVATIONS,
            )
        except Exception as exc:
            return {
                "status": "failed",
                "category": category,
                "url": youtube_url,
                "provider": self._video_provider.name,
                "reason": str(exc)[:500],
            }

        # Fail closed if a provider returns evidence for a different
        # source than the exact public video ATLAS was asked to inspect.
        if any(
            observation.source_url.strip() != youtube_url
            for observation in observations
        ):
            return {
                "status": "failed",
                "category": category,
                "url": youtube_url,
                "provider": self._video_provider.name,
                "reason": "video evidence source URL does not match requested URL",
            }

        atomics = atomic_from_video_evidence(observations)

        created = persist_atomic_evidence(
            atomics,
            evidence=youtube_url,
            source=SOURCE_NAME,
            category=category,
            knowledge=self._knowledge,
            provider=self._video_provider.name,
            default_observed_at=datetime.now(timezone.utc).isoformat(),
        )

        return {
            "status": "done",
            "category": category,
            "url": youtube_url,
            "provider": self._video_provider.name,
            "findings_created": len(created),
        }

    def report(self) -> dict:
        findings = [
            f
            for f in self._knowledge.findings()
            if f.source == SOURCE_NAME
        ]
        return {
            "status": "done",
            "total_findings": len(findings),
        }
