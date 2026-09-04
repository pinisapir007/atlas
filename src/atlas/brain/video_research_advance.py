"""Bounded Executive Discovery -> Video Research bridge.

This module owns only source discovery and Task creation. It never performs
Gemini video understanding itself.

When explicitly enabled it may make at most ONE YouTube search call and
create at most ONE video_research Task per invocation. The Task is then
handled later by the normal CEOBrain prioritization/delegation lifecycle.

The bridge is deliberately separate from ResearchDiscoveryAgent so adding
video as another real research source cannot alter the already-qualified
web-research execution path.
"""

from atlas.brain.discovery.decide import discovery_goal
from atlas.brain.discovery.research_request import categories_needing_research
from atlas.brain.discovery.video_research_request import (
    VIDEO_RESEARCH_TASK_CATEGORY,
    parse_video_research_task,
    video_research_task_description,
)
from atlas.brain.feature_flags import (
    executive_discovery_enabled,
    video_research_enabled,
)
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Task
from atlas.integrations.youtube_provider import YouTubeAPIError, YouTubeProvider

SOURCE_NAME = "video_research"

# Initial qualification bound. This is intentionally conservative and is
# editable later from evidence; it is not presented as a monetary budget.
MAX_VIDEO_RESEARCH_ATTEMPTS_PER_CATEGORY = 1
MAX_VIDEO_RESEARCH_TASKS_PER_TICK = 1

_ATTEMPT_PREFIX = "video_research_attempts_"


def _attempt_kpi_name(category: str) -> str:
    return f"{_ATTEMPT_PREFIX}{category}"


def video_research_attempts(category: str, kpis: KPIRegistry) -> int:
    return int(kpis.latest(_attempt_kpi_name(category)) or 0)


def _record_attempt(category: str, kpis: KPIRegistry) -> None:
    kpis.record(
        _attempt_kpi_name(category),
        video_research_attempts(category, kpis) + 1,
    )


def _task_payload(task: Task) -> tuple[str, str] | None:
    if task.category != VIDEO_RESEARCH_TASK_CATEGORY:
        return None
    try:
        return parse_video_research_task(task)
    except (ValueError, AttributeError):
        return None


def _open_video_categories(memory: BrainMemory) -> set[str]:
    result: set[str] = set()
    for task in memory.tasks():
        payload = _task_payload(task)
        if payload is None:
            continue
        category, _url = payload
        if task.status not in ("done", "failed", "blocked"):
            result.add(category)
    return result


def _known_video_urls(memory: BrainMemory, knowledge: KnowledgeBase) -> set[str]:
    urls: set[str] = set()

    # Every previously-created video Task counts, including terminal ones:
    # do not pay to rediscover/reanalyse the same source merely because an
    # earlier execution finished.
    for task in memory.tasks():
        payload = _task_payload(task)
        if payload is not None:
            _category, url = payload
            urls.add(url)

    # Also honor durable evidence created before this bridge existed.
    for finding in knowledge.findings():
        if finding.source != SOURCE_NAME or not finding.evidence:
            continue
        url = finding.evidence.split(" @ ", 1)[0].strip()
        if url.startswith("https://"):
            urls.add(url)

    return urls


def _category_already_has_video_evidence(
    category: str,
    knowledge: KnowledgeBase,
) -> bool:
    return any(
        finding.source == SOURCE_NAME
        and finding.category == category
        and bool(finding.evidence)
        for finding in knowledge.findings()
    )


def _video_id(item: dict) -> str:
    raw_id = item.get("id")
    if not isinstance(raw_id, dict):
        return ""
    value = raw_id.get("videoId")
    return value.strip() if isinstance(value, str) else ""


def advance_video_research(
    memory: BrainMemory,
    knowledge: KnowledgeBase,
    kpis: KPIRegistry,
    youtube_provider: YouTubeProvider | None = None,
) -> list[Task]:
    """Create at most one bounded video_research Task.

    No-op unless BOTH Executive Discovery and Video Research are explicitly
    enabled. A missing YouTube credential is also an honest no-op because
    YouTubeProvider.search() returns None when it cannot make a real call.
    """
    if not executive_discovery_enabled() or not video_research_enabled():
        return []

    categories = sorted(categories_needing_research(knowledge, kpis))
    if not categories:
        return []

    open_categories = _open_video_categories(memory)
    known_urls = _known_video_urls(memory, knowledge)
    provider = youtube_provider if youtube_provider is not None else YouTubeProvider()

    searches_made = 0
    created: list[Task] = []

    for category in categories:
        if len(created) >= MAX_VIDEO_RESEARCH_TASKS_PER_TICK:
            break
        if searches_made >= 1:
            break
        if category in open_categories:
            continue
        if _category_already_has_video_evidence(category, knowledge):
            continue
        if video_research_attempts(category, kpis) >= MAX_VIDEO_RESEARCH_ATTEMPTS_PER_CATEGORY:
            continue

        query = f"{category.replace('_', ' ')} business model explained"

        try:
            results = provider.search(query, max_results=5)
        except YouTubeAPIError as exc:
            searches_made += 1
            _record_attempt(category, kpis)
            memory.append_log(
                {
                    "event": "video_research_source_discovery_failed",
                    "category": category,
                    "reason": str(exc)[:500],
                }
            )
            return []

        # None means no configured credential, therefore no real search call
        # was made and no attempt is charged.
        if results is None:
            return []

        searches_made += 1
        _record_attempt(category, kpis)

        for item in results:
            if not isinstance(item, dict):
                continue

            video_id = _video_id(item)
            if not video_id:
                continue

            url = f"https://www.youtube.com/watch?v={video_id}"
            if url in known_urls:
                continue

            goal = discovery_goal(memory)
            task = Task(
                goal_id=goal.id,
                category=VIDEO_RESEARCH_TASK_CATEGORY,
                description=video_research_task_description(category, url),
                reversible=True,
            )
            memory.save_task(task)
            created.append(task)
            known_urls.add(url)
            break

        # Hard bound: one real YouTube search per invocation even if the
        # returned page contained no usable unseen video.
        break

    return created
