"""Research Mission -> existing timestamped YouTube research lifecycle.

This module does not analyze video itself.

It creates/reuses the already-qualified `video_research` Task and later
reconciles the resulting durable Findings back to the exact
ResearchMissionSource.

Correlation is exact:
- durable Task id on ResearchMissionSource;
- exact requested category;
- exact requested YouTube URL;
- Finding.source == "video_research".

No fuzzy URL matching, no second video engine, no direct provider call.
"""

from atlas.brain.discovery.video_research_request import (
    VIDEO_RESEARCH_TASK_CATEGORY,
    parse_video_research_task,
    video_research_task_description,
)
from atlas.brain.feature_flags import (
    research_mission_enabled,
    video_research_enabled,
)
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.knowledge_source_registry import select_plugin
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding, Task, now
from atlas.brain.research_missions import (
    ResearchMissionSource,
    ResearchMissionStore,
)

SOURCE_NAME = "video_research"
MAX_SOURCES_PER_CALL = 1

# Task model semantics:
# - failed: terminal unsuccessful execution;
# - superseded: terminal obsolete work;
# - blocked: deliberately resumable, therefore NOT terminal here.
_TASK_RETRY_TERMINAL_STATUSES = {
    "failed",
    "superseded",
}


def _base_evidence_url(finding: Finding) -> str:
    if not finding.evidence:
        return ""

    # Timestamped atomic video evidence may be stored as:
    #   URL @ locator
    # The VideoResearchProvider itself is already required to return the
    # exact requested source URL before persistence.
    return finding.evidence.split(" @ ", 1)[0].strip()


def _matching_findings(
    knowledge: KnowledgeBase,
    source: ResearchMissionSource,
) -> list[Finding]:
    return [
        finding
        for finding in knowledge.findings()
        if finding.source == SOURCE_NAME
        and finding.category == source.category
        and _base_evidence_url(finding) == source.source_ref
    ]


def _matching_tasks(
    memory: BrainMemory,
    *,
    goal_id: str,
    category: str,
    youtube_url: str,
) -> list[Task]:
    result: list[Task] = []

    for task in memory.tasks():
        if task.goal_id != goal_id:
            continue

        if task.category != VIDEO_RESEARCH_TASK_CATEGORY:
            continue

        try:
            task_category, task_url = parse_video_research_task(task)
        except (ValueError, AttributeError):
            continue

        if task_category != category:
            continue

        if task_url != youtube_url:
            continue

        result.append(task)

    return sorted(
        result,
        key=lambda task: (
            task.created_at,
            task.id,
        ),
    )


def _mark_processed(
    store: ResearchMissionStore,
    source: ResearchMissionSource,
    findings: list[Finding],
) -> ResearchMissionSource:
    source.status = "processed"
    source.finding_ids = sorted(
        {
            finding.id
            for finding in findings
        }
    )
    source.last_error = ""
    source.updated_at = now()
    store.save_source(source)
    return store.get_source(source.id)


def _mark_rejected(
    store: ResearchMissionStore,
    source: ResearchMissionSource,
    reason: str,
) -> ResearchMissionSource:
    source.status = "rejected"
    source.last_error = reason[:1000]
    source.updated_at = now()
    store.save_source(source)
    return store.get_source(source.id)


def _handle_terminal_task_without_evidence(
    store: ResearchMissionStore,
    source: ResearchMissionSource,
    *,
    max_attempts: int,
    task: Task,
) -> ResearchMissionSource:
    source.last_error = (
        f"video_research task {task.id} ended with "
        f"status {task.status}"
    )[:1000]
    source.updated_at = now()

    if source.attempts >= max_attempts:
        source.status = "failed_exhausted"
    else:
        # Clear only the correlation so the next bounded invocation may
        # create one fresh retry Task.
        source.task_id = ""
        source.status = "pending"

    store.save_source(source)
    return store.get_source(source.id)


def advance_research_mission_youtube(
    store: ResearchMissionStore,
    memory: BrainMemory,
    knowledge: KnowledgeBase,
) -> list[ResearchMissionSource]:
    """Advance at most one YouTube ResearchMissionSource.

    Strict no-op unless BOTH Research Mission and Video Research are
    explicitly enabled.

    Existing durable Findings are always reused first.

    If no evidence exists:
      - an already-correlated Task is reconciled;
      - otherwise an existing matching open Task under the same Goal is
        adopted (crash/idempotency protection);
      - otherwise one new normal video_research Task is created.

    The actual video understanding occurs later through the normal
    CEOBrain -> Delegator -> Registry -> VideoResearchAgent -> Monitor
    lifecycle.
    """
    if (
        not research_mission_enabled()
        or not video_research_enabled()
    ):
        return []

    missions = sorted(
        store.active_missions(),
        key=lambda mission: (
            mission.created_at,
            mission.id,
        ),
    )

    for mission in missions:
        pending = sorted(
            store.pending_sources(mission.id),
            key=lambda source: (
                source.created_at,
                source.id,
            ),
        )

        for source in pending:
            try:
                plugin = select_plugin(source.source_ref)
            except ValueError:
                # Generic source bridge owns unsupported-source rejection.
                continue

            if plugin.name != "youtube":
                continue

            # Evidence is the durable source of truth. This also allows a
            # mission to reuse exact YouTube evidence created earlier.
            findings = _matching_findings(
                knowledge,
                source,
            )

            if findings:
                return [
                    _mark_processed(
                        store,
                        source,
                        findings,
                    )
                ]

            if source.task_id:
                try:
                    task = memory.get_task(source.task_id)
                except KeyError:
                    source.last_error = (
                        f"correlated video_research task "
                        f"{source.task_id!r} no longer exists"
                    )[:1000]
                    source.updated_at = now()

                    if source.attempts >= mission.max_attempts_per_source:
                        source.status = "failed_exhausted"
                    else:
                        source.task_id = ""
                        source.status = "pending"

                    store.save_source(source)

                    return [
                        store.get_source(source.id)
                    ]

                # A done Task with no exact durable Findings means the
                # qualified video run produced no usable atomic evidence.
                if task.status == "done":
                    return [
                        _mark_rejected(
                            store,
                            source,
                            "video_research task completed but produced "
                            "zero exact durable Findings",
                        )
                    ]

                if task.status in _TASK_RETRY_TERMINAL_STATUSES:
                    return [
                        _handle_terminal_task_without_evidence(
                            store,
                            source,
                            max_attempts=mission.max_attempts_per_source,
                            task=task,
                        )
                    ]

                # proposed/prioritized/delegated/in_progress and blocked:
                # still legitimately open/resumable. Do not duplicate the
                # exact Task and do not consume another attempt.
                return []

            existing = _matching_tasks(
                memory,
                goal_id=mission.goal_id,
                category=source.category,
                youtube_url=source.source_ref,
            )

            open_existing = [
                task
                for task in existing
                if task.status
                not in (
                    "done",
                    "failed",
                    "superseded",
                )
            ]

            if open_existing:
                # Crash-safe adoption: if Task persistence succeeded before
                # ResearchMissionSource.task_id persistence, reuse it rather
                # than create duplicate work. No new mission attempt is
                # charged because this invocation created nothing.
                source.task_id = open_existing[0].id
                source.last_error = ""
                source.updated_at = now()
                store.save_source(source)

                return [
                    store.get_source(source.id)
                ]

            done_existing = [
                task
                for task in existing
                if task.status == "done"
            ]

            if done_existing:
                # No Findings matched above, therefore an exact prior Task
                # completed without usable durable evidence.
                return [
                    _mark_rejected(
                        store,
                        source,
                        "existing exact video_research task completed "
                        "without exact durable Findings",
                    )
                ]

            if source.attempts >= mission.max_attempts_per_source:
                source.status = "failed_exhausted"
                source.last_error = (
                    "YouTube retry budget exhausted before a new "
                    "video_research Task could be created"
                )
                source.updated_at = now()
                store.save_source(source)

                return [
                    store.get_source(source.id)
                ]

            # Ensure the mission still points to a real Goal before creating
            # a Task under it. Never create an orphan Task.
            try:
                memory.get_goal(mission.goal_id)
            except KeyError:
                return [
                    _mark_rejected(
                        store,
                        source,
                        f"research mission goal {mission.goal_id!r} "
                        "does not exist",
                    )
                ]

            task = Task(
                goal_id=mission.goal_id,
                category=VIDEO_RESEARCH_TASK_CATEGORY,
                description=video_research_task_description(
                    source.category,
                    source.source_ref,
                ),
                reversible=True,
            )

            memory.save_task(task)

            source.attempts += 1
            source.task_id = task.id
            source.last_error = ""
            source.updated_at = now()
            store.save_source(source)

            return [
                store.get_source(source.id)
            ]

    return []
