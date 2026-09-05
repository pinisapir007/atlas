"""Bounded lifecycle bridge for durable Research Missions.

Foundation phase only.

This bridge performs no source discovery and no evidence collection.
A mission may close only after source discovery has explicitly declared
itself complete and every attached source is terminal.
"""

from atlas.brain.feature_flags import research_mission_enabled
from atlas.brain.models import now
from atlas.brain.research_missions import (
    SOURCE_TERMINAL_STATUSES,
    ResearchMission,
    ResearchMissionStore,
)


def advance_research_missions(
    store: ResearchMissionStore,
) -> list[ResearchMission]:
    if not research_mission_enabled():
        return []

    changed: list[ResearchMission] = []

    for mission in store.active_missions():
        if not mission.source_discovery_complete:
            continue

        sources = store.sources(mission.id)

        if sources and any(
            source.status not in SOURCE_TERMINAL_STATUSES
            for source in sources
        ):
            continue

        if sources and any(
            source.status == "processed"
            for source in sources
        ):
            mission.status = "completed"
        else:
            mission.status = "exhausted"

        mission.updated_at = now()
        mission.completed_at = mission.updated_at
        store.save_mission(mission)
        changed.append(mission)

    return changed
