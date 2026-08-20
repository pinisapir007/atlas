"""Deep Research Trigger (P0 Independence Mission, 2026-08-18) -- the
escalation path for a category the shallow Research Trigger
(research_request.py) already gave up on: research_exhausted() became
true (MAX_RESEARCH_ATTEMPTS identical, single-step attempts made) but
the category still hasn't cleared decide()'s evidence bar. Before this,
a stuck category simply stayed stuck forever with no further autonomous
step -- the real, verified gap this mission closes (see
deep_research_advance.py for the actual escalation logic).

Mirrors research_request.py's exact shape on purpose (same fixed-prefix
Task.description encoding, same category_from_*/*_task_description
pair) -- a second, near-identical trigger deliberately kept separate
from the first rather than overloading RESEARCH_TASK_CATEGORY, since
the two dispatch to genuinely different assets (ResearchDiscoveryAgent's
single-step run() vs. DeepResearchAgent's bounded multi-step run()) and
Delegator routes purely by Task.category.
"""

from atlas.brain.models import Task

DEEP_RESEARCH_TASK_CATEGORY = "deep_research"
DEEP_RESEARCH_TASK_PREFIX = "Deep-research business model category: "


def deep_research_task_description(category: str) -> str:
    return f"{DEEP_RESEARCH_TASK_PREFIX}{category}"


def category_from_deep_research_task(task: Task) -> str:
    """The inverse of deep_research_task_description() -- raises loudly
    if `task` isn't a real Deep Research Trigger task rather than
    silently guessing, the same fail-closed discipline
    research_request.category_from_research_task() already establishes."""
    if not task.description.startswith(DEEP_RESEARCH_TASK_PREFIX):
        raise ValueError(f"task {task.id!r} is not a real deep-research task: {task.description!r}")
    return task.description[len(DEEP_RESEARCH_TASK_PREFIX):]
