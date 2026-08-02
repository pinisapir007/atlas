from atlas.brain.decision_engine import decide, decide_all, has_materially_changed
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Decision, Finding, Goal, Task


def _kb(tmp_path):
    return KnowledgeBase(tmp_path / "knowledge.json")


def _memory(tmp_path):
    return BrainMemory(tmp_path / "brain.json")


def _sourced_finding(category: str, i: int) -> Finding:
    return Finding(source="research", category=category, description=f"signal {i}", evidence=f"https://example.com/{i}")


def test_insufficient_evidence_with_only_one_source(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("digital_product", 1))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    decision = decide("digital_product", kb, memory, kpis)

    assert decision.verdict == "insufficient_evidence"
    assert decision.context["independent_sources"] == 1
    assert decision.goal_id is None


def test_invest_verdict_for_channel_ready_unclaimed_category(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("digital_product", 1))
    kb.save_finding(_sourced_finding("digital_product", 2))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    decision = decide("digital_product", kb, memory, kpis)

    assert decision.verdict == "invest"
    assert decision.context["channel_ready"] is True
    assert decision.context["already_pursuing"] is False
    assert len(decision.evidence_finding_ids) == 2
    assert decision.confidence is not None


def test_invest_verdict_names_the_chosen_provider_when_one_is_registered(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("affiliate", 1))
    kb.save_finding(_sourced_finding("affiliate", 2))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    decision = decide("affiliate", kb, memory, kpis)

    assert decision.verdict == "invest"
    assert decision.chosen_provider == "digistore24"
    assert "digistore24" in decision.reasoning
    assert len(decision.context["provider_ranking"]) == 1
    assert decision.context["provider_ranking"][0]["provider"] == "digistore24"


def test_invest_verdict_has_no_chosen_provider_when_none_is_registered(tmp_path):
    # digital_product has a real dispatchable channel but no registered
    # CommerceProvider yet — a real, honest gap distinct from "category not
    # worth pursuing".
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("digital_product", 1))
    kb.save_finding(_sourced_finding("digital_product", 2))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    decision = decide("digital_product", kb, memory, kpis)

    assert decision.verdict == "invest"
    assert decision.chosen_provider is None
    assert decision.context["provider_ranking"] == []
    assert "no registered provider" in decision.reasoning


def test_non_invest_verdicts_never_set_chosen_provider(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("affiliate", 1))  # only 1 source -> insufficient_evidence
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    decision = decide("affiliate", kb, memory, kpis)

    assert decision.verdict == "insufficient_evidence"
    assert decision.chosen_provider is None
    assert "provider_ranking" not in decision.context


def test_already_invested_when_a_real_goal_already_pursues_the_category(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("affiliate", 1))
    kb.save_finding(_sourced_finding("affiliate", 2))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)
    existing = Goal(description="existing affiliate goal")
    memory.save_goal(existing)
    memory.save_task(Task(goal_id=existing.id, description="x", category="affiliate_pipeline"))

    decision = decide("affiliate", kb, memory, kpis)

    assert decision.verdict == "already_invested"
    assert decision.context["existing_goal_ids"] == [existing.id]


def test_a_paused_goal_does_not_block_reinvestment(tmp_path):
    # A paused goal was tried and capital already moved away from it —
    # treating that as "already invested" would be factually wrong and
    # would permanently block ATLAS from ever reconsidering a category it
    # once gave up on, no matter how much new evidence arrives later.
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("affiliate", 1))
    kb.save_finding(_sourced_finding("affiliate", 2))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)
    paused = Goal(description="an old affiliate attempt that didn't work out", status="paused")
    memory.save_goal(paused)
    memory.save_task(Task(goal_id=paused.id, description="x", category="affiliate_pipeline"))

    decision = decide("affiliate", kb, memory, kpis)

    assert decision.verdict == "invest"
    assert decision.context["existing_goal_ids"] == []
    assert decision.context["paused_goal_ids"] == [paused.id]
    assert paused.id in decision.reasoning
    assert "paused" in decision.reasoning


def test_a_paused_goal_alongside_an_active_one_still_blocks_reinvestment(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("affiliate", 1))
    kb.save_finding(_sourced_finding("affiliate", 2))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)
    active = Goal(description="currently active affiliate goal", status="active")
    memory.save_goal(active)
    memory.save_task(Task(goal_id=active.id, description="x", category="affiliate_pipeline"))
    paused = Goal(description="an old affiliate attempt", status="paused")
    memory.save_goal(paused)
    memory.save_task(Task(goal_id=paused.id, description="x", category="affiliate_pipeline"))

    decision = decide("affiliate", kb, memory, kpis)

    assert decision.verdict == "already_invested"
    assert decision.context["existing_goal_ids"] == [active.id]
    assert decision.context["paused_goal_ids"] == [paused.id]


def test_propose_capability_when_no_channel_exists(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("youtube", 1))
    kb.save_finding(_sourced_finding("youtube", 2))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    decision = decide("youtube", kb, memory, kpis)

    assert decision.verdict == "propose_capability"
    assert decision.context["channel_ready"] is False


def test_already_proposed_when_a_capability_gap_goal_already_exists(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("youtube", 1))
    kb.save_finding(_sourced_finding("youtube", 2))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)
    memory.save_goal(Goal(description="Capability gap: youtube", engine_id="intelligence_youtube"))

    decision = decide("youtube", kb, memory, kpis)

    assert decision.verdict == "already_proposed"


def test_decision_carries_full_citation_and_risks(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("digital_product", 1))
    kb.save_finding(_sourced_finding("digital_product", 2))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    decision = decide("digital_product", kb, memory, kpis)

    assert decision.evidence_finding_ids  # cites real Finding IDs, not just a count
    assert decision.factors  # the full confidence_score() breakdown, not just the number
    assert decision.risks  # reuses explain_opportunity()'s risk assessment
    assert decision.reasoning  # deterministic string, not empty
    assert "digital_product" in decision.reasoning


def test_decide_never_creates_a_goal_or_task(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("digital_product", 1))
    kb.save_finding(_sourced_finding("digital_product", 2))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    decide("digital_product", kb, memory, kpis)

    assert memory.goals() == []
    assert memory.tasks() == []


def test_decide_is_pure_and_recomputes_fresh_every_call(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("digital_product", 1))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    first = decide("digital_product", kb, memory, kpis)
    assert first.verdict == "insufficient_evidence"

    kb.save_finding(_sourced_finding("digital_product", 2))
    second = decide("digital_product", kb, memory, kpis)
    assert second.verdict == "invest"  # same call, same category, different answer — no caching


def _decision(verdict="invest", confidence=0.5):
    return Decision(category="affiliate", verdict=verdict, confidence=confidence, factors={})


def test_verdict_change_is_always_material():
    previous = _decision(verdict="insufficient_evidence", confidence=None)
    new = _decision(verdict="invest", confidence=0.5)

    assert has_materially_changed(previous, new) is True


def test_tiny_confidence_drift_is_not_material():
    previous = _decision(confidence=0.700)
    new = _decision(confidence=0.705)  # e.g. recency decay between ticks, not new evidence

    assert has_materially_changed(previous, new) is False


def test_large_confidence_shift_is_material():
    previous = _decision(confidence=0.700)
    new = _decision(confidence=0.500)  # e.g. a new contradicting finding arrived

    assert has_materially_changed(previous, new) is True


def test_both_none_confidence_is_not_material():
    previous = _decision(verdict="insufficient_evidence", confidence=None)
    new = _decision(verdict="insufficient_evidence", confidence=None)

    assert has_materially_changed(previous, new) is False


def test_confidence_becoming_measurable_is_material():
    previous = _decision(verdict="insufficient_evidence", confidence=None)
    new = _decision(verdict="insufficient_evidence", confidence=0.3)

    assert has_materially_changed(previous, new) is True


def test_decide_all_covers_every_sourced_category(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(_sourced_finding("affiliate", 1))
    kb.save_finding(_sourced_finding("youtube", 1))
    kb.save_finding(Finding(source="research", category="ugc", description="no evidence", evidence=""))
    memory = _memory(tmp_path)
    kpis = KPIRegistry(memory)

    decisions = decide_all(kb, memory, kpis)

    categories = {d.category for d in decisions}
    assert categories == {"affiliate", "youtube"}  # ugc excluded — its only finding has no evidence
