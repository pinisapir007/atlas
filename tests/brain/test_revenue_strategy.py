from atlas.brain.confidence import BOOTSTRAP_TASK_CATEGORIES
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding, Goal, Opportunity, Task
from atlas.brain.opportunities import OpportunityStore
from atlas.brain.revenue_strategy import MAX_CONCURRENT_COMMITMENTS, commit_ready_opportunities


def _kb(tmp_path) -> KnowledgeBase:
    return KnowledgeBase(tmp_path / "knowledge.json")


def _store(tmp_path) -> OpportunityStore:
    return OpportunityStore(tmp_path / "opportunities.json")


def _memory(tmp_path) -> BrainMemory:
    return BrainMemory(tmp_path / "brain.json")


def _seed_findings(knowledge: KnowledgeBase, category: str, subject: str, count: int) -> list[str]:
    ids = []
    for i in range(count):
        f = Finding(source="research", category=category, subject=subject, description=f"s{i}", evidence=f"https://e/{subject}-{i}", evidence_role="direct_assertion")
        knowledge.save_finding(f)
        ids.append(f.id)
    return ids


def _ready_opp(category: str, subject: str, evidence_ids: list[str]) -> Opportunity:
    return Opportunity(subject=subject, description="d", category=category, evidence_finding_ids=evidence_ids)


def test_no_real_channel_is_never_committed(tmp_path):
    knowledge = _kb(tmp_path)
    memory = _memory(tmp_path)
    store = _store(tmp_path)
    ids = _seed_findings(knowledge, "youtube", "Some Channel", 2)  # no BOOTSTRAP_TASK_CATEGORIES entry
    store.save_opportunity(_ready_opp("youtube", "Some Channel", ids))

    results = commit_ready_opportunities("youtube", store, knowledge, memory)

    assert results[0]["status"] == "no_real_channel"
    assert results[0]["goal_id"] is None
    assert memory.goals() == []


def test_already_committed_opportunity_is_never_re_decided(tmp_path):
    knowledge = _kb(tmp_path)
    memory = _memory(tmp_path)
    store = _store(tmp_path)
    goal = Goal(description="existing")
    memory.save_goal(goal)
    ids = _seed_findings(knowledge, "digital_product", "Notion templates", 2)
    opp = _ready_opp("digital_product", "Notion templates", ids)
    opp.goal_id = goal.id
    store.save_opportunity(opp)

    results = commit_ready_opportunities("digital_product", store, knowledge, memory)

    assert results[0]["status"] == "already_committed"
    assert results[0]["goal_id"] == goal.id
    assert len(memory.goals()) == 1  # no second Goal created


def test_first_commitment_creates_a_new_subject_attributed_goal(tmp_path):
    knowledge = _kb(tmp_path)
    memory = _memory(tmp_path)
    store = _store(tmp_path)
    ids = _seed_findings(knowledge, "digital_product", "Notion templates", 2)
    opp = _ready_opp("digital_product", "Notion templates", ids)
    store.save_opportunity(opp)

    results = commit_ready_opportunities("digital_product", store, knowledge, memory)

    assert results[0]["status"] == "committed_new_goal"
    assert results[0]["revenue_model"] == BOOTSTRAP_TASK_CATEGORIES["digital_product"][0]
    goal_id = results[0]["goal_id"]
    assert goal_id is not None
    saved_opp = store.get_opportunity(opp.id)
    assert saved_opp.goal_id == goal_id
    assert saved_opp.task_id is not None
    goals = memory.goals()
    assert len(goals) == 1
    assert goals[0].id == goal_id
    tasks = memory.tasks()
    assert len(tasks) == 1
    assert tasks[0].category == BOOTSTRAP_TASK_CATEGORIES["digital_product"][0]
    assert tasks[0].goal_id == goal_id


# --- Design doc's own 4-part falsification test (docs/DESIGN_REVENUE_STRATEGY.md §7) ---


def test_falsification_part_a_joins_existing_category_goal_not_duplicate(tmp_path):
    knowledge = _kb(tmp_path)
    memory = _memory(tmp_path)
    store = _store(tmp_path)

    # Simulates the old categorical path (decision_apply.apply_decision()):
    # a real active Goal + a real Task whose category is one of
    # CATEGORY_TASK_CATEGORIES["digital_product"], with no Opportunity
    # ever having claimed it.
    old_goal = Goal(description="Pursue digital_product opportunities (Decision Engine)")
    memory.save_goal(old_goal)
    old_task = Task(goal_id=old_goal.id, description="Bootstrap digital_product pipeline", category="revenue_digital_product")
    memory.save_task(old_task)

    ids = _seed_findings(knowledge, "digital_product", "Notion templates", 2)
    opp = _ready_opp("digital_product", "Notion templates", ids)
    store.save_opportunity(opp)

    results = commit_ready_opportunities("digital_product", store, knowledge, memory)

    assert results[0]["status"] == "joined_existing_goal"
    assert results[0]["goal_id"] == old_goal.id
    assert len(memory.goals()) == 1  # no second Goal created


def test_falsification_part_b_separate_goals_for_two_ready_subjects_same_category(tmp_path):
    knowledge = _kb(tmp_path)
    memory = _memory(tmp_path)
    store = _store(tmp_path)

    a_ids = _seed_findings(knowledge, "digital_product", "A", 4)
    b_ids = _seed_findings(knowledge, "digital_product", "B", 2)
    opp_a = _ready_opp("digital_product", "A", a_ids)
    opp_b = _ready_opp("digital_product", "B", b_ids)
    store.save_opportunity(opp_a)
    store.save_opportunity(opp_b)

    results = commit_ready_opportunities("digital_product", store, knowledge, memory)

    statuses = {r["subject"]: r for r in results}
    assert statuses["A"]["status"] == "committed_new_goal"
    assert statuses["B"]["status"] == "committed_new_goal"
    assert statuses["A"]["goal_id"] != statuses["B"]["goal_id"]
    assert len(memory.goals()) == 2


def test_falsification_part_c_repeated_run_never_creates_a_second_goal(tmp_path):
    knowledge = _kb(tmp_path)
    memory = _memory(tmp_path)
    store = _store(tmp_path)
    ids = _seed_findings(knowledge, "digital_product", "Notion templates", 2)
    opp = _ready_opp("digital_product", "Notion templates", ids)
    store.save_opportunity(opp)

    first = commit_ready_opportunities("digital_product", store, knowledge, memory)
    first_goal_id = first[0]["goal_id"]

    second = commit_ready_opportunities("digital_product", store, knowledge, memory)

    assert second[0]["status"] == "already_committed"
    assert second[0]["goal_id"] == first_goal_id
    assert len(memory.goals()) == 1
    saved_opp = store.get_opportunity(opp.id)
    assert saved_opp.goal_id == first_goal_id


def test_falsification_part_d_resource_exhaustion_defers_then_resumes_when_freed(tmp_path):
    knowledge = _kb(tmp_path)
    memory = _memory(tmp_path)
    store = _store(tmp_path)

    # Exhaust the declared threshold with unrelated pre-existing active Goals.
    for i in range(MAX_CONCURRENT_COMMITMENTS):
        memory.save_goal(Goal(description=f"unrelated {i}"))

    ids = _seed_findings(knowledge, "digital_product", "Notion templates", 2)
    opp = _ready_opp("digital_product", "Notion templates", ids)
    store.save_opportunity(opp)

    results = commit_ready_opportunities("digital_product", store, knowledge, memory)
    assert results[0]["status"] == "deferred_resources"
    assert results[0]["goal_id"] is None
    saved_opp = store.get_opportunity(opp.id)
    assert saved_opp.goal_id is None  # not rejected, not silently dropped -- still uncommitted

    # Free up a slot -- pause one of the unrelated Goals.
    unrelated = [g for g in memory.goals() if g.description.startswith("unrelated")][0]
    unrelated.status = "paused"
    memory.save_goal(unrelated)

    resumed = commit_ready_opportunities("digital_product", store, knowledge, memory)
    assert resumed[0]["status"] in ("committed_new_goal", "joined_existing_goal")
    assert resumed[0]["goal_id"] is not None


def test_two_ready_subjects_one_slot_first_commits_second_defers(tmp_path):
    knowledge = _kb(tmp_path)
    memory = _memory(tmp_path)
    store = _store(tmp_path)
    for i in range(MAX_CONCURRENT_COMMITMENTS - 1):
        memory.save_goal(Goal(description=f"unrelated {i}"))

    a_ids = _seed_findings(knowledge, "digital_product", "A", 4)  # ranks first (more evidence)
    b_ids = _seed_findings(knowledge, "digital_product", "B", 2)
    store.save_opportunity(_ready_opp("digital_product", "A", a_ids))
    store.save_opportunity(_ready_opp("digital_product", "B", b_ids))

    results = commit_ready_opportunities("digital_product", store, knowledge, memory)

    by_subject = {r["subject"]: r for r in results}
    assert by_subject["A"]["status"] == "committed_new_goal"
    assert by_subject["B"]["status"] == "deferred_resources"
