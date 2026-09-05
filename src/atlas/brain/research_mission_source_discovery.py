"""Bounded real source discovery for durable Research Missions.

This module DISCOVERS source references only.

It does not:
- read discovered web-page content;
- run Gemini video understanding;
- create Findings, Claims, Opportunities, Decisions, or commercial actions;
- approve local files;
- change the global BrowserAllowlist.

Discovery providers qualified in this first version:
- Brave structured web search -> public HTTPS candidate URLs
- YouTube Data API search -> canonical YouTube watch URLs

Every category/provider unit has durable ResearchMissionDiscovery state,
so restart/tick repetition cannot silently forget attempts or repeat a
completed search forever.

Exactly one pending discovery unit may make one external search call per
invocation.
"""

from __future__ import annotations

from urllib.parse import urlparse

from atlas.brain.evidence_provenance import normalize_url
from atlas.brain.feature_flags import research_mission_enabled
from atlas.brain.models import now
from atlas.brain.research_mission_public_https import (
    ResearchMissionPublicHTTPSPolicy,
)
from atlas.brain.research_missions import (
    DISCOVERY_TERMINAL_STATUSES,
    ResearchMission,
    ResearchMissionDiscovery,
    ResearchMissionStore,
)
from atlas.integrations.search_providers import BraveSearchProvider
from atlas.integrations.youtube_provider import (
    YouTubeAPIError,
    YouTubeProvider,
)


MAX_DISCOVERY_CALLS_PER_INVOCATION = 1
MAX_RESULTS_PER_SEARCH = 5
MAX_SOURCES_PER_DISCOVERY_UNIT = 1

_DISCOVERY_PROVIDERS = (
    "brave",
    "youtube",
)

_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
}


def _query(category: str, provider: str) -> str:
    """Stable code-owned query for one category/provider pair.

    No calendar year is embedded: an unfinished durable discovery unit must
    not suffer query drift merely because a restart happens after New Year.
    """
    topic = category.replace("_", " ").strip()

    if provider == "brave":
        return (
            f"{topic} business model market demand trends "
            "monetization opportunities"
        )

    if provider == "youtube":
        return (
            f"{topic} business model explained market demand monetization"
        )

    raise ValueError(f"unsupported Research Mission discovery provider: {provider!r}")


def _video_id(item: dict) -> str:
    raw_id = item.get("id")

    if not isinstance(raw_id, dict):
        return ""

    value = raw_id.get("videoId")
    return value.strip() if isinstance(value, str) else ""


def _web_candidate_url(item: dict) -> str:
    if not isinstance(item, dict):
        return ""

    raw = item.get("url")
    if not isinstance(raw, str):
        return ""

    normalized = normalize_url(raw.strip())
    if not normalized.startswith("https://"):
        return ""

    try:
        host = (urlparse(normalized).hostname or "").lower()
    except ValueError:
        return ""

    # YouTube has its own source-discovery/provider lifecycle. Do not let a
    # Brave result accidentally create the same source through two provider
    # units with two different semantics.
    if host in _YOUTUBE_HOSTS or host.endswith(".youtube.com"):
        return ""

    return normalized


def _youtube_candidate_url(item: dict) -> str:
    if not isinstance(item, dict):
        return ""

    video_id = _video_id(item)
    if not video_id:
        return ""

    return f"https://www.youtube.com/watch?v={video_id}"


def _save_failure(
    store: ResearchMissionStore,
    mission: ResearchMission,
    discovery: ResearchMissionDiscovery,
    reason: str,
) -> ResearchMissionDiscovery:
    discovery.last_error = reason[:1000]
    discovery.updated_at = now()

    if discovery.attempts >= mission.max_discovery_attempts_per_provider:
        discovery.status = "failed_exhausted"
    else:
        discovery.status = "pending"

    store.save_discovery(discovery)
    return store.get_discovery(discovery.id)


def _all_required_discovery_terminal(
    store: ResearchMissionStore,
    mission: ResearchMission,
) -> bool:
    categories = sorted(
        {
            category.strip()
            for category in mission.categories
            if category.strip()
        }
    )

    if not categories:
        return True

    for category in categories:
        for provider in _DISCOVERY_PROVIDERS:
            progress = store.discovery_for(
                mission.id,
                category,
                provider,
            )

            if progress is None:
                return False

            if progress.status not in DISCOVERY_TERMINAL_STATUSES:
                return False

    return True


def _finish_discovery_if_ready(
    store: ResearchMissionStore,
    mission: ResearchMission,
) -> None:
    mission = store.get_mission(mission.id)

    if mission.status != "active":
        return

    if len(store.sources(mission.id)) >= mission.max_sources:
        mission.source_discovery_complete = True
        mission.updated_at = now()
        store.save_mission(mission)
        return

    if _all_required_discovery_terminal(store, mission):
        mission.source_discovery_complete = True
        mission.updated_at = now()
        store.save_mission(mission)


def advance_research_mission_source_discovery(
    store: ResearchMissionStore,
    *,
    brave_provider: BraveSearchProvider | None = None,
    youtube_provider: YouTubeProvider | None = None,
    public_https_policy: ResearchMissionPublicHTTPSPolicy | None = None,
) -> list[ResearchMissionDiscovery]:
    """Advance at most one real discovery unit.

    Feature flag off -> exact no-op.

    A discovery attempt is persisted BEFORE the external provider call.

    Provider success, including a real result page with zero usable unseen
    sources, completes that category/provider unit. Provider/backend failure
    retries only within the mission's explicit discovery-attempt budget.

    Mission.source_discovery_complete becomes true only when:
    - all required category/provider units are terminal; OR
    - the mission's explicit source budget has been reached.
    """
    if not research_mission_enabled():
        return []

    brave = (
        brave_provider
        if brave_provider is not None
        else BraveSearchProvider()
    )
    youtube = (
        youtube_provider
        if youtube_provider is not None
        else YouTubeProvider()
    )
    public_policy = (
        public_https_policy
        if public_https_policy is not None
        else ResearchMissionPublicHTTPSPolicy()
    )

    calls_made = 0

    missions = sorted(
        store.active_missions(),
        key=lambda mission: (
            mission.created_at,
            mission.id,
        ),
    )

    for mission in missions:
        if mission.source_discovery_complete:
            continue

        categories = sorted(
            {
                category.strip()
                for category in mission.categories
                if category.strip()
            }
        )

        # A deliberately empty category set has no discovery frontier.
        if not categories:
            mission.source_discovery_complete = True
            mission.updated_at = now()
            store.save_mission(mission)
            continue

        if len(store.sources(mission.id)) >= mission.max_sources:
            mission.source_discovery_complete = True
            mission.updated_at = now()
            store.save_mission(mission)
            continue

        for category in categories:
            for provider_name in _DISCOVERY_PROVIDERS:
                query = _query(category, provider_name)

                discovery = store.ensure_discovery(
                    mission.id,
                    category,
                    provider_name,
                    query,
                )

                if discovery.status in DISCOVERY_TERMINAL_STATUSES:
                    continue

                if (
                    discovery.attempts
                    >= mission.max_discovery_attempts_per_provider
                ):
                    discovery.status = "failed_exhausted"
                    discovery.last_error = (
                        "discovery attempt budget already exhausted"
                    )
                    discovery.updated_at = now()
                    store.save_discovery(discovery)
                    continue

                if calls_made >= MAX_DISCOVERY_CALLS_PER_INVOCATION:
                    return []

                # Persist the attempt before any external provider call.
                discovery.attempts += 1
                discovery.updated_at = now()
                store.save_discovery(discovery)

                try:
                    if provider_name == "brave":
                        results = brave.search(
                            query,
                            max_results=MAX_RESULTS_PER_SEARCH,
                        )
                    elif provider_name == "youtube":
                        results = youtube.search(
                            query,
                            max_results=MAX_RESULTS_PER_SEARCH,
                        )
                    else:
                        raise ValueError(
                            f"unsupported discovery provider: "
                            f"{provider_name!r}"
                        )

                    calls_made += 1

                    if results is None:
                        raise RuntimeError(
                            f"{provider_name} search is not configured"
                        )

                    if not isinstance(results, list):
                        raise RuntimeError(
                            f"{provider_name} search returned unexpected "
                            f"result shape: {type(results).__name__}"
                        )

                except (YouTubeAPIError, Exception) as exc:
                    # YouTubeAPIError is intentionally named here for
                    # readability; Exception preserves the bounded retry
                    # contract for real provider/network/backend failures.
                    restored = _save_failure(
                        store,
                        mission,
                        discovery,
                        f"{type(exc).__name__}: {exc}",
                    )
                    return [restored]

                source_ids = list(discovery.source_ids)

                for item in results:
                    if (
                        len(source_ids)
                        >= MAX_SOURCES_PER_DISCOVERY_UNIT
                    ):
                        break

                    if (
                        len(store.sources(mission.id))
                        >= mission.max_sources
                    ):
                        break

                    if provider_name == "brave":
                        source_ref = _web_candidate_url(item)

                        if not source_ref:
                            continue

                        # Discovery itself does not read the page. This is
                        # only a pre-queue safety filter using the same
                        # Research Mission public-HTTPS policy the eventual
                        # BrowserPlugin will enforce again before/after
                        # navigation.
                        if not public_policy.is_approved(source_ref):
                            continue

                        source_kind = "browser"

                    else:
                        source_ref = _youtube_candidate_url(item)

                        if not source_ref:
                            continue

                        source_kind = "youtube"

                    source = store.add_source(
                        mission.id,
                        source_ref,
                        category,
                        (
                            f"Research {category.replace('_', ' ')} "
                            f"for mission objective: {mission.objective}"
                        ),
                        source_kind=source_kind,
                    )

                    if source.id not in source_ids:
                        source_ids.append(source.id)

                discovery.source_ids = source_ids
                discovery.status = "completed"
                discovery.last_error = ""
                discovery.updated_at = now()
                store.save_discovery(discovery)

                _finish_discovery_if_ready(
                    store,
                    mission,
                )

                return [
                    store.get_discovery(discovery.id)
                ]

        # Every required unit was already terminal before this invocation.
        _finish_discovery_if_ready(
            store,
            mission,
        )

    return []
