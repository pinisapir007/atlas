"""Durable Research Mission orchestration state.

A ResearchMission is NOT evidence, a Claim, an Opportunity, a Decision,
or permission to act. It is only durable coordination state for a broad
research objective.

ResearchMissionSource records which real sources still need processing
and their bounded terminal lifecycle. The actual evidence collection is
owned by the already-qualified Knowledge Source pipeline.

No source discovery, browser access, AI call, ingestion, Task creation,
Opportunity creation, Decision creation, publishing, or spending occurs
in this module.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from atlas.brain.models import new_id, now
from atlas.brain.store import BrainStore, JSONFileStore, update_store


MISSION_STATUSES = {
    "active",
    "completed",
    "exhausted",
    "cancelled",
}

MISSION_TERMINAL_STATUSES = {
    "completed",
    "exhausted",
    "cancelled",
}

SOURCE_STATUSES = {
    "pending",
    "processed",
    "rejected",
    "failed_exhausted",
}

SOURCE_TERMINAL_STATUSES = {
    "processed",
    "rejected",
    "failed_exhausted",
}


@dataclass
class ResearchMission:
    """One durable broad-research objective."""

    goal_id: str
    objective: str
    categories: list[str] = field(default_factory=list)

    # Explicit bounds. They are orchestration safety limits, not claims
    # about how much research is scientifically or commercially sufficient.
    max_sources: int = 24
    max_attempts_per_source: int = 2

    # False while the orchestrator may still discover/add further sources.
    source_discovery_complete: bool = False

    status: str = "active"

    id: str = field(
        default_factory=lambda: new_id("research-mission")
    )
    created_at: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)
    completed_at: str | None = None


@dataclass
class ResearchMissionSource:
    """One concrete real source assigned to a ResearchMission."""

    mission_id: str
    source_ref: str

    # Finding.category for evidence collected from this source.
    category: str

    # Why this source is being read. This becomes input to the existing
    # evidence relevance/grounding layer later; it is not evidence itself.
    task_description: str

    # Informational routing label only. The actual plugin is still selected
    # by knowledge_source_registry.select_plugin(source_ref), never trusted
    # from this label.
    source_kind: str = ""

    status: str = "pending"
    attempts: int = 0

    # Finding ids created by the existing evidence pipeline.
    finding_ids: list[str] = field(default_factory=list)

    # Optional durable correlation to an asynchronous Task. Generic
    # Browser/Document/PDF/Image/Audio/Video sources are processed
    # synchronously and leave this empty. YouTube uses the existing
    # video_research Task lifecycle and stores that exact Task id here.
    task_id: str = ""

    last_error: str = ""

    id: str = field(
        default_factory=lambda: new_id("research-source")
    )
    created_at: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)


class ResearchMissionStore:
    """Durable store for missions and their concrete source queue."""

    def __init__(
        self,
        path: Path = Path(".atlas/research_missions.json"),
        store: BrainStore | None = None,
    ):
        self._store = (
            store
            if store is not None
            else JSONFileStore(path)
        )

    def _read(self) -> dict:
        data = self._store.read()

        if data is None:
            return {
                "missions": {},
                "sources": {},
            }

        data.setdefault("missions", {})
        data.setdefault("sources", {})
        return data

    def save_mission(
        self,
        mission: ResearchMission,
    ) -> None:
        self._validate_mission(mission)

        def mutate(data):
            data.setdefault("missions", {})
            data.setdefault("sources", {})
            data["missions"][mission.id] = asdict(mission)

        update_store(
            self._store,
            self._read(),
            mutate,
        )

    def get_mission(
        self,
        mission_id: str,
    ) -> ResearchMission:
        raw = self._read()["missions"].get(mission_id)

        if raw is None:
            raise KeyError(
                f"no such research mission: {mission_id}"
            )

        return ResearchMission(**raw)

    def missions(self) -> list[ResearchMission]:
        return [
            ResearchMission(**raw)
            for raw in self._read()["missions"].values()
        ]

    def active_missions(self) -> list[ResearchMission]:
        return [
            mission
            for mission in self.missions()
            if mission.status == "active"
        ]

    def save_source(
        self,
        source: ResearchMissionSource,
    ) -> None:
        self._validate_source(source)

        # A source may never exist for a mission that does not exist.
        self.get_mission(source.mission_id)

        def mutate(data):
            data.setdefault("missions", {})
            data.setdefault("sources", {})
            data["sources"][source.id] = asdict(source)

        update_store(
            self._store,
            self._read(),
            mutate,
        )

    def get_source(
        self,
        source_id: str,
    ) -> ResearchMissionSource:
        raw = self._read()["sources"].get(source_id)

        if raw is None:
            raise KeyError(
                f"no such research mission source: {source_id}"
            )

        return ResearchMissionSource(**raw)

    def sources(
        self,
        mission_id: str | None = None,
    ) -> list[ResearchMissionSource]:
        result = [
            ResearchMissionSource(**raw)
            for raw in self._read()["sources"].values()
        ]

        if mission_id is None:
            return result

        return [
            source
            for source in result
            if source.mission_id == mission_id
        ]

    def pending_sources(
        self,
        mission_id: str,
    ) -> list[ResearchMissionSource]:
        return [
            source
            for source in self.sources(mission_id)
            if source.status == "pending"
        ]

    def add_source(
        self,
        mission_id: str,
        source_ref: str,
        category: str,
        task_description: str,
        source_kind: str = "",
    ) -> ResearchMissionSource:
        """Idempotently add one concrete source to a mission.

        Dedupe is exact by mission_id + source_ref. The same concrete source
        is never queued twice inside one mission.
        """
        mission = self.get_mission(mission_id)

        normalized_ref = source_ref.strip()
        normalized_category = category.strip()
        normalized_task = task_description.strip()

        if not normalized_ref:
            raise ValueError("source_ref must not be empty")

        if not normalized_category:
            raise ValueError("category must not be empty")

        if not normalized_task:
            raise ValueError(
                "task_description must not be empty"
            )

        for existing in self.sources(mission_id):
            if existing.source_ref == normalized_ref:
                return existing

        existing_count = len(self.sources(mission_id))

        if existing_count >= mission.max_sources:
            raise ValueError(
                f"research mission {mission_id!r} already reached "
                f"max_sources={mission.max_sources}"
            )

        source = ResearchMissionSource(
            mission_id=mission_id,
            source_ref=normalized_ref,
            category=normalized_category,
            task_description=normalized_task,
            source_kind=source_kind.strip(),
        )

        self.save_source(source)
        return source

    @staticmethod
    def _validate_mission(
        mission: ResearchMission,
    ) -> None:
        if not mission.goal_id.strip():
            raise ValueError(
                "ResearchMission.goal_id must not be empty"
            )

        if not mission.objective.strip():
            raise ValueError(
                "ResearchMission.objective must not be empty"
            )

        if mission.status not in MISSION_STATUSES:
            raise ValueError(
                f"invalid ResearchMission.status: "
                f"{mission.status!r}"
            )

        if mission.max_sources < 1:
            raise ValueError(
                "ResearchMission.max_sources must be >= 1"
            )

        if mission.max_attempts_per_source < 1:
            raise ValueError(
                "ResearchMission.max_attempts_per_source "
                "must be >= 1"
            )

    @staticmethod
    def _validate_source(
        source: ResearchMissionSource,
    ) -> None:
        if not source.mission_id.strip():
            raise ValueError(
                "ResearchMissionSource.mission_id "
                "must not be empty"
            )

        if not source.source_ref.strip():
            raise ValueError(
                "ResearchMissionSource.source_ref "
                "must not be empty"
            )

        if not source.category.strip():
            raise ValueError(
                "ResearchMissionSource.category "
                "must not be empty"
            )

        if not source.task_description.strip():
            raise ValueError(
                "ResearchMissionSource.task_description "
                "must not be empty"
            )

        if source.status not in SOURCE_STATUSES:
            raise ValueError(
                f"invalid ResearchMissionSource.status: "
                f"{source.status!r}"
            )

        if source.attempts < 0:
            raise ValueError(
                "ResearchMissionSource.attempts "
                "must be >= 0"
            )
