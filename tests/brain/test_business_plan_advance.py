from atlas.assets.affiliate_department.models import AffiliateOpportunity
from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.brain.business_plan_advance import (
    COMMERCIAL_TERMS_TASK_CATEGORY,
    advance_business_plan_generation,
    create_affiliate_opportunity_from_terms,
)
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Goal, Task
from atlas.brain.opportunities import OpportunityStore
from atlas.brain.models import Opportunity

REAL_LINK = "https://www.digistore24.com/redir/123456/myaffid/"


def _memory(tmp_path) -> BrainMemory:
    return BrainMemory(tmp_path / "brain.json")


def _store(tmp_path) -> OpportunityStore:
    return OpportunityStore(tmp_path / "opportunities.json")


def _affiliate_store(tmp_path) -> AffiliateStore:
    return AffiliateStore(tmp_path / "affiliate_intelligence.json")


def _committed_opportunity(goal_id: str, subject: str = "Notion templates", category: str = "affiliate") -> Opportunity:
    return Opportunity(
        subject=subject,
        description="a real committed opportunity",
        category=category,
        marketing_niche="productivity",
        recommended_market="US",
        evidence_finding_ids=["f1", "f2"],
        score=0.8,
        goal_id=goal_id,
    )


# --- advance_business_plan_generation() ---


def test_committed_opportunity_gets_exactly_one_commercial_terms_task(tmp_path):
    memory = _memory(tmp_path)
    store = _store(tmp_path)
    affiliate_store = _affiliate_store(tmp_path)
    goal = Goal(description="Pursue 'Notion templates'", engine_id="intelligence_affiliate")
    memory.save_goal(goal)
    opportunity = _committed_opportunity(goal.id)
    store.save_opportunity(opportunity)

    tasks = advance_business_plan_generation(memory, store, affiliate_store)

    assert len(tasks) == 1
    task = tasks[0]
    assert task.category == COMMERCIAL_TERMS_TASK_CATEGORY
    assert task.goal_id == goal.id
    assert task.source_opportunity_id == opportunity.id
    assert task.reversible is False
    assert "Notion templates" in task.description


def test_uncommitted_opportunity_gets_no_task(tmp_path):
    memory = _memory(tmp_path)
    store = _store(tmp_path)
    affiliate_store = _affiliate_store(tmp_path)
    store.save_opportunity(Opportunity(subject="X", description="d", category="affiliate"))  # goal_id is None

    tasks = advance_business_plan_generation(memory, store, affiliate_store)

    assert tasks == []


def test_non_bridged_category_gets_no_task(tmp_path):
    memory = _memory(tmp_path)
    store = _store(tmp_path)
    affiliate_store = _affiliate_store(tmp_path)
    goal = Goal(description="Pursue digital_product", engine_id="intelligence_digital_product")
    memory.save_goal(goal)
    store.save_opportunity(_committed_opportunity(goal.id, category="digital_product"))

    tasks = advance_business_plan_generation(memory, store, affiliate_store)

    assert tasks == []


def test_goal_with_existing_affiliate_opportunity_gets_no_task(tmp_path):
    memory = _memory(tmp_path)
    store = _store(tmp_path)
    affiliate_store = _affiliate_store(tmp_path)
    goal = Goal(description="Pursue X", engine_id="intelligence_affiliate")
    memory.save_goal(goal)
    store.save_opportunity(_committed_opportunity(goal.id))
    affiliate_store.save_opportunity(AffiliateOpportunity(product_name="X", description="d", goal_id=goal.id))

    tasks = advance_business_plan_generation(memory, store, affiliate_store)

    assert tasks == []


def test_repeated_call_never_creates_a_second_task(tmp_path):
    memory = _memory(tmp_path)
    store = _store(tmp_path)
    affiliate_store = _affiliate_store(tmp_path)
    goal = Goal(description="Pursue X", engine_id="intelligence_affiliate")
    memory.save_goal(goal)
    opportunity = _committed_opportunity(goal.id)
    store.save_opportunity(opportunity)

    first = advance_business_plan_generation(memory, store, affiliate_store)
    for task in first:
        memory.save_task(task)

    second = advance_business_plan_generation(memory, store, affiliate_store)

    assert len(first) == 1
    assert second == []


# --- create_affiliate_opportunity_from_terms() ---


def _approved_task(memory: BrainMemory, opportunity: Opportunity) -> Task:
    task = Task(
        goal_id=opportunity.goal_id,
        description="commercial terms needed",
        category=COMMERCIAL_TERMS_TASK_CATEGORY,
        reversible=False,
        source_opportunity_id=opportunity.id,
        status="done",
    )
    memory.save_task(task)
    return task


def test_create_from_terms_succeeds_with_real_valid_terms(tmp_path):
    memory = _memory(tmp_path)
    store = _store(tmp_path)
    affiliate_store = _affiliate_store(tmp_path)
    goal = Goal(description="Pursue X", engine_id="intelligence_affiliate")
    memory.save_goal(goal)
    opportunity = _committed_opportunity(goal.id)
    store.save_opportunity(opportunity)
    task = _approved_task(memory, opportunity)

    result = create_affiliate_opportunity_from_terms(
        task.id, memory, store, affiliate_store,
        commission_per_conversion=25.0, real_affiliate_link=REAL_LINK, provider="digistore24",
    )

    assert result.stage == "selected_for_marketing"
    assert result.goal_id == goal.id
    assert result.product_name == "Notion templates"
    assert result.marketing_niche == "productivity"
    assert result.recommended_market == "US"
    assert result.commission_per_conversion == 25.0
    assert result.real_affiliate_link == REAL_LINK
    assert result.provider == "digistore24"
    saved = affiliate_store.opportunities()
    assert len(saved) == 1
    assert saved[0].id == result.id


def test_create_from_terms_rejects_unapproved_task(tmp_path):
    memory = _memory(tmp_path)
    store = _store(tmp_path)
    affiliate_store = _affiliate_store(tmp_path)
    goal = Goal(description="Pursue X", engine_id="intelligence_affiliate")
    memory.save_goal(goal)
    opportunity = _committed_opportunity(goal.id)
    store.save_opportunity(opportunity)
    task = Task(
        goal_id=goal.id, description="commercial terms needed", category=COMMERCIAL_TERMS_TASK_CATEGORY,
        reversible=False, source_opportunity_id=opportunity.id, status="pending_approval",
    )
    memory.save_task(task)

    try:
        create_affiliate_opportunity_from_terms(
            task.id, memory, store, affiliate_store,
            commission_per_conversion=25.0, real_affiliate_link=REAL_LINK, provider="digistore24",
        )
        assert False, "expected ValueError"
    except ValueError as e:
        assert "not been approved" in str(e)
    assert affiliate_store.opportunities() == []


def test_create_from_terms_rejects_zero_commission(tmp_path):
    memory = _memory(tmp_path)
    store = _store(tmp_path)
    affiliate_store = _affiliate_store(tmp_path)
    goal = Goal(description="Pursue X", engine_id="intelligence_affiliate")
    memory.save_goal(goal)
    opportunity = _committed_opportunity(goal.id)
    store.save_opportunity(opportunity)
    task = _approved_task(memory, opportunity)

    try:
        create_affiliate_opportunity_from_terms(
            task.id, memory, store, affiliate_store,
            commission_per_conversion=0.0, real_affiliate_link=REAL_LINK, provider="digistore24",
        )
        assert False, "expected ValueError"
    except ValueError as e:
        assert "commission_per_conversion" in str(e)
    assert affiliate_store.opportunities() == []


def test_create_from_terms_rejects_invalid_link(tmp_path):
    memory = _memory(tmp_path)
    store = _store(tmp_path)
    affiliate_store = _affiliate_store(tmp_path)
    goal = Goal(description="Pursue X", engine_id="intelligence_affiliate")
    memory.save_goal(goal)
    opportunity = _committed_opportunity(goal.id)
    store.save_opportunity(opportunity)
    task = _approved_task(memory, opportunity)

    try:
        create_affiliate_opportunity_from_terms(
            task.id, memory, store, affiliate_store,
            commission_per_conversion=25.0, real_affiliate_link="https://not-a-real-provider-link.example.com", provider="digistore24",
        )
        assert False, "expected ValueError"
    except ValueError:
        pass
    assert affiliate_store.opportunities() == []


def test_create_from_terms_rejects_wrong_task_category(tmp_path):
    memory = _memory(tmp_path)
    store = _store(tmp_path)
    affiliate_store = _affiliate_store(tmp_path)
    goal = Goal(description="Pursue X", engine_id="intelligence_affiliate")
    memory.save_goal(goal)
    task = Task(goal_id=goal.id, description="unrelated", category="create_asset", status="done")
    memory.save_task(task)

    try:
        create_affiliate_opportunity_from_terms(
            task.id, memory, store, affiliate_store,
            commission_per_conversion=25.0, real_affiliate_link=REAL_LINK, provider="digistore24",
        )
        assert False, "expected ValueError"
    except ValueError as e:
        assert "not a real affiliate commercial-terms request" in str(e)


def test_create_from_terms_rejects_duplicate_for_same_goal(tmp_path):
    memory = _memory(tmp_path)
    store = _store(tmp_path)
    affiliate_store = _affiliate_store(tmp_path)
    goal = Goal(description="Pursue X", engine_id="intelligence_affiliate")
    memory.save_goal(goal)
    opportunity = _committed_opportunity(goal.id)
    store.save_opportunity(opportunity)
    affiliate_store.save_opportunity(AffiliateOpportunity(product_name="X", description="d", goal_id=goal.id))
    task = _approved_task(memory, opportunity)

    try:
        create_affiliate_opportunity_from_terms(
            task.id, memory, store, affiliate_store,
            commission_per_conversion=25.0, real_affiliate_link=REAL_LINK, provider="digistore24",
        )
        assert False, "expected ValueError"
    except ValueError as e:
        assert "already exists" in str(e)
    assert len(affiliate_store.opportunities()) == 1
