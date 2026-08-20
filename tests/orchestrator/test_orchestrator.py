from pathlib import Path

import pytest

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Goal
from atlas.campaign.registry import CampaignRegistry, create_campaign, link_goal, set_status
from atlas.influencer.models import DigitalInfluencer, IdentityProfile
from atlas.influencer.production import add_template
from atlas.influencer.registry import InfluencerRegistry, add_platform_target, attach_asset
from atlas.orchestrator.orchestrator import advance_all_campaign_executions, advance_execution, start_execution
from atlas.orchestrator.registry import ExecutionPlanRegistry

# Every template kind PUBLISH_ESSENTIAL_TEMPLATE_KINDS requires, for a
# platform not in HASHTAG_PLATFORMS (so hashtags stay optional in these
# fixtures unless a test explicitly cares about that conditionality).
_PUBLISH_READY_KINDS = ("title", "description", "hook", "cta", "caption_template")


class _World:
    """One isolated, tmp_path-scoped set of every store the orchestrator
    needs — mirrors the shape CEOBrain wires together, without touching
    CEOBrain itself (these tests exercise the orchestration functions
    directly, the same way test_decision_engine.py exercises decide()
    without going through CEOBrain.tick())."""

    def __init__(self, tmp_path):
        self.memory = BrainMemory(tmp_path / "brain.json")
        self.kpis = KPIRegistry(self.memory)
        self.knowledge = KnowledgeBase(tmp_path / "knowledge.json")
        self.influencers = InfluencerRegistry(tmp_path / "influencers.json")
        self.campaigns = CampaignRegistry(tmp_path / "campaigns.json")
        self.plans = ExecutionPlanRegistry(tmp_path / "execution_plans.json")
        self.landing_page_dir = tmp_path / "landing_pages"

    def new_influencer(self, name="Mira") -> DigitalInfluencer:
        influencer = DigitalInfluencer(identity=IdentityProfile(name=name), categories=["affiliate"])
        self.influencers.save_influencer(influencer)
        return influencer

    def new_ready_campaign(self, influencer_ids, goal_id="goal-a", product_offer="KetoDNA", destination_url="https://example.com/track/real"):
        if goal_id is not None and goal_id not in {g.id for g in self.memory.goals()}:
            self.memory.save_goal(Goal(description="real campaign goal", id=goal_id))
        campaign = create_campaign(
            business_objective="grow affiliate revenue", category="affiliate", product_offer=product_offer,
            influencer_ids=influencer_ids, influencer_registry=self.influencers, knowledge=self.knowledge,
            memory=self.memory, kpis=self.kpis, registry=self.campaigns, goal_id=goal_id,
            destination_url=destination_url,
        )
        return set_status(campaign.id, "active", self.campaigns)

    def make_publish_ready(self, influencer_id, kinds=_PUBLISH_READY_KINDS):
        """Adds every template kind requested, one real attached asset, and
        one declared platform target — everything _produce_content()
        requires for "done" beyond the campaign's own fields."""
        for kind in kinds:
            # Includes real AI-disclosure and affiliate-disclosure phrasing so
            # these fixtures clear the mandatory Compliance & Trust Review
            # gate (compliance_review.py) the same way real content must.
            add_template(
                influencer_id, kind, f"{kind}-1",
                f"real {kind} about {{product_name}} -- AI-curated content. (affiliate link)",
                self.influencers,
            )
        attach_asset(influencer_id, "image", "https://example.com/real-asset.jpg", self.influencers)
        add_platform_target(influencer_id, "YouTube", "@handle", self.influencers)

    def advance(self, plan_id):
        return advance_execution(
            plan_id, self.plans, self.campaigns, self.influencers, self.memory, self.kpis, self.knowledge, self.landing_page_dir
        )


@pytest.fixture
def world(tmp_path):
    return _World(tmp_path)


# --- start_execution() -------------------------------------------------


def test_start_execution_requires_an_active_campaign(world):
    influencer = world.new_influencer()
    campaign = create_campaign(
        business_objective="a", category="affiliate", product_offer="KetoDNA", influencer_ids=[influencer.id],
        influencer_registry=world.influencers, knowledge=world.knowledge, memory=world.memory, kpis=world.kpis,
        registry=world.campaigns,
    )  # still "proposed" — never activated

    with pytest.raises(ValueError):
        start_execution(campaign.id, world.campaigns, world.plans)


def test_start_execution_builds_the_expected_dependency_graph(world):
    mira = world.new_influencer("Mira")
    kai = world.new_influencer("Kai")
    campaign = world.new_ready_campaign([mira.id, kai.id])

    plan = start_execution(campaign.id, world.campaigns, world.plans)

    kinds = [s.kind for s in plan.steps]
    assert kinds.count("verify_readiness") == 1
    assert kinds.count("produce_content") == 2
    assert kinds.count("request_founder_review") == 1
    assert kinds.count("check_measurement") == 1

    verify = next(s for s in plan.steps if s.kind == "verify_readiness")
    produce_steps = [s for s in plan.steps if s.kind == "produce_content"]
    review = next(s for s in plan.steps if s.kind == "request_founder_review")
    measure = next(s for s in plan.steps if s.kind == "check_measurement")

    assert all(s.depends_on == [verify.id] for s in produce_steps)
    assert set(review.depends_on) == {s.id for s in produce_steps}
    assert measure.depends_on == [review.id]
    assert {s.influencer_id for s in produce_steps} == {mira.id, kai.id}


def test_start_execution_is_idempotent_for_an_in_progress_plan(world):
    influencer = world.new_influencer()
    campaign = world.new_ready_campaign([influencer.id])

    first = start_execution(campaign.id, world.campaigns, world.plans)
    second = start_execution(campaign.id, world.campaigns, world.plans)

    assert first.id == second.id
    assert len(world.plans.plans_for_campaign(campaign.id)) == 1


# --- verify_readiness ----------------------------------------------------


def test_verify_readiness_blocks_when_no_goal_is_linked(world):
    influencer = world.new_influencer()
    campaign = world.new_ready_campaign([influencer.id], goal_id=None)
    plan = start_execution(campaign.id, world.campaigns, world.plans)

    advanced = world.advance(plan.id)

    verify = next(s for s in advanced.steps if s.kind == "verify_readiness")
    assert verify.status == "blocked"
    assert "no Goal linked" in verify.result["reason"]


def test_verify_readiness_resumes_automatically_once_a_goal_is_linked(world):
    influencer = world.new_influencer()
    campaign = world.new_ready_campaign([influencer.id], goal_id=None)
    plan = start_execution(campaign.id, world.campaigns, world.plans)
    world.advance(plan.id)  # blocked — no goal yet

    world.memory.save_goal(Goal(description="real campaign goal", id="goal-a"))
    link_goal(campaign.id, "goal-a", world.campaigns)
    advanced = world.advance(plan.id)  # same call, no special retry — re-evaluated fresh

    verify = next(s for s in advanced.steps if s.kind == "verify_readiness")
    assert verify.status == "done"


def test_verify_readiness_blocks_on_an_unknown_influencer_id(tmp_path):
    world = _World(tmp_path)
    campaign = create_campaign(
        business_objective="a", category="affiliate", product_offer="KetoDNA", influencer_ids=[],
        influencer_registry=world.influencers, knowledge=world.knowledge, memory=world.memory, kpis=world.kpis,
        registry=world.campaigns, goal_id="goal-a",
    )
    set_status(campaign.id, "active", world.campaigns)
    # bypass create_campaign's own validation by mutating the persisted campaign directly,
    # simulating an influencer that existed at campaign-creation time and was later removed
    stored = world.campaigns.get_campaign(campaign.id)
    stored.influencer_ids = ["influencer-that-no-longer-exists"]
    world.campaigns.save_campaign(stored)
    plan = start_execution(campaign.id, world.campaigns, world.plans)

    advanced = world.advance(plan.id)

    verify = next(s for s in advanced.steps if s.kind == "verify_readiness")
    assert verify.status == "blocked"
    assert "unknown influencer" in verify.result["reason"]


# --- produce_content -------------------------------------------------------


def test_produce_content_blocks_without_essential_templates(world):
    influencer = world.new_influencer()
    campaign = world.new_ready_campaign([influencer.id])
    plan = start_execution(campaign.id, world.campaigns, world.plans)

    # A single advance_execution() call cascades: verify_readiness becomes
    # "done" and produce_content's only dependency is verify_readiness, so
    # both are evaluated within this same pass — no incremental "one step
    # per call" model here, matching decide_all()'s same fresh-recompute
    # shape.
    advanced = world.advance(plan.id)

    produce = next(s for s in advanced.steps if s.kind == "produce_content")
    assert produce.status == "blocked"
    assert "hook" in produce.result["reason"] or "cta" in produce.result["reason"]


def test_produce_content_succeeds_once_publish_ready(world):
    influencer = world.new_influencer()
    world.make_publish_ready(influencer.id)
    campaign = world.new_ready_campaign([influencer.id])
    plan = start_execution(campaign.id, world.campaigns, world.plans)

    advanced = world.advance(plan.id)  # cascades: verify_readiness -> produce_content in one call

    produce = next(s for s in advanced.steps if s.kind == "produce_content")
    assert produce.status == "done"
    assert produce.result["hooks"] == 1
    assert produce.result["ctas"] == 1
    assert produce.result["titles"] == 1
    assert produce.result["descriptions"] == 1
    assert produce.result["real_assets"] == 1

    # "Prepare complete campaign packages" (founder's daily operational
    # workflow, step 6, 2026-08-03) is now automatic: reaching "done" here
    # means a real landing page file and creative brief were produced,
    # not just counted.
    assert produce.result["creative_brief_shots"] == 4
    landing_page_path = Path(produce.result["landing_page_path"])
    assert landing_page_path.is_relative_to(world.landing_page_dir)
    html = landing_page_path.read_text(encoding="utf-8")
    assert "<html" in html
    assert "https://example.com/track/real" in html


def test_produce_content_blocks_on_missing_destination_url_even_with_full_templates(world):
    influencer = world.new_influencer()
    world.make_publish_ready(influencer.id)
    campaign = world.new_ready_campaign([influencer.id], destination_url="")
    plan = start_execution(campaign.id, world.campaigns, world.plans)

    advanced = world.advance(plan.id)

    produce = next(s for s in advanced.steps if s.kind == "produce_content")
    assert produce.status == "blocked"
    assert "destination_url" in produce.result["reason"]


def test_produce_content_blocks_without_real_media_even_with_full_templates(world):
    influencer = world.new_influencer()
    world.make_publish_ready(influencer.id, kinds=_PUBLISH_READY_KINDS)
    # undo the real asset attach_asset() already did, to isolate this one requirement
    stored = world.influencers.get_influencer(influencer.id)
    stored.asset_library = []
    world.influencers.save_influencer(stored)
    campaign = world.new_ready_campaign([influencer.id])
    plan = start_execution(campaign.id, world.campaigns, world.plans)

    advanced = world.advance(plan.id)

    produce = next(s for s in advanced.steps if s.kind == "produce_content")
    assert produce.status == "blocked"
    assert "real media" in produce.result["reason"]


def test_produce_content_requires_hashtags_only_when_the_platform_conventionally_uses_them(world):
    influencer = world.new_influencer()
    world.make_publish_ready(influencer.id)  # platform target is "YouTube" -- not in HASHTAG_PLATFORMS
    campaign = world.new_ready_campaign([influencer.id])
    plan = start_execution(campaign.id, world.campaigns, world.plans)
    world.advance(plan.id)
    produce = next(s for s in world.plans.get_plan(plan.id).steps if s.kind == "produce_content")
    assert produce.status == "done"  # no hashtags added, but none required for YouTube

    influencer2 = world.new_influencer("Kai")
    world.make_publish_ready(influencer2.id)
    add_platform_target(influencer2.id, "TikTok", "@kai", world.influencers)  # IS in HASHTAG_PLATFORMS
    campaign2 = world.new_ready_campaign([influencer2.id], goal_id="goal-b")
    plan2 = start_execution(campaign2.id, world.campaigns, world.plans)
    world.advance(plan2.id)
    produce2 = next(s for s in world.plans.get_plan(plan2.id).steps if s.kind == "produce_content")
    assert produce2.status == "blocked"
    assert "hashtags" in produce2.result["reason"]

    add_template(influencer2.id, "hashtags", "h1", "#keto #diet", world.influencers)
    world.advance(plan2.id)
    produce2 = next(s for s in world.plans.get_plan(plan2.id).steps if s.kind == "produce_content")
    assert produce2.status == "done"


# --- request_founder_review + check_measurement -----------------------------


def _fully_produced_campaign(world):
    influencer = world.new_influencer()
    world.make_publish_ready(influencer.id)
    campaign = world.new_ready_campaign([influencer.id])
    plan = start_execution(campaign.id, world.campaigns, world.plans)
    world.advance(plan.id)  # cascades verify_readiness -> produce_content
    return campaign, plan


def test_request_founder_review_dispatches_a_real_reversible_false_task(world):
    campaign, plan = _fully_produced_campaign(world)

    advanced = world.advance(plan.id)  # request_founder_review becomes ready

    review = next(s for s in advanced.steps if s.kind == "request_founder_review")
    assert review.status == "dispatched"
    assert review.task_id is not None
    task = world.memory.get_task(review.task_id)
    assert task.reversible is False
    assert task.category == "campaign_execution"
    assert task.goal_id == "goal-a"


def test_review_step_completes_once_the_real_task_is_marked_done(world):
    campaign, plan = _fully_produced_campaign(world)
    world.advance(plan.id)  # dispatches the review task

    review = next(s for s in world.plans.get_plan(plan.id).steps if s.kind == "request_founder_review")
    task = world.memory.get_task(review.task_id)
    task.transition("done", "founder approved")
    world.memory.save_task(task)

    advanced = world.advance(plan.id)

    review = next(s for s in advanced.steps if s.kind == "request_founder_review")
    assert review.status == "done"


def test_review_step_fails_if_the_real_task_fails(world):
    campaign, plan = _fully_produced_campaign(world)
    world.advance(plan.id)

    review = next(s for s in world.plans.get_plan(plan.id).steps if s.kind == "request_founder_review")
    task = world.memory.get_task(review.task_id)
    task.transition("failed", "founder rejected")
    world.memory.save_task(task)

    advanced = world.advance(plan.id)

    review = next(s for s in advanced.steps if s.kind == "request_founder_review")
    assert review.status == "failed"


def test_check_measurement_blocks_until_profit_is_measurable_then_refreshes_confidence(world):
    campaign, plan = _fully_produced_campaign(world)
    world.advance(plan.id)  # dispatch review
    review = next(s for s in world.plans.get_plan(plan.id).steps if s.kind == "request_founder_review")
    task = world.memory.get_task(review.task_id)
    task.transition("done", "approved")
    world.memory.save_task(task)

    advanced = world.advance(plan.id)  # review -> done, check_measurement becomes ready but unmeasured
    measure = next(s for s in advanced.steps if s.kind == "check_measurement")
    assert measure.status == "blocked"

    world.kpis.record("revenue_goal-a", 200.0)
    world.kpis.record("cost_goal-a", 100.0)
    before_confidence = world.campaigns.get_campaign(campaign.id).confidence_score

    advanced = world.advance(plan.id)

    measure = next(s for s in advanced.steps if s.kind == "check_measurement")
    assert measure.status == "done"
    assert measure.result["profit"] == 100.0
    after = world.campaigns.get_campaign(campaign.id)
    assert len(after.learning_history) >= 2  # created + at least one confidence refresh


# --- full lifecycle: plan completion closes the campaign -------------------


def test_full_lifecycle_completes_the_plan_and_closes_the_campaign(world):
    campaign, plan = _fully_produced_campaign(world)
    world.advance(plan.id)  # dispatch review
    review = next(s for s in world.plans.get_plan(plan.id).steps if s.kind == "request_founder_review")
    task = world.memory.get_task(review.task_id)
    task.transition("done", "approved")
    world.memory.save_task(task)
    world.kpis.record("revenue_goal-a", 200.0)
    world.kpis.record("cost_goal-a", 100.0)

    advanced = world.advance(plan.id)  # review -> done, check_measurement -> done, plan completes

    assert advanced.status == "completed"
    assert all(s.status == "done" for s in advanced.steps)
    assert world.campaigns.get_campaign(campaign.id).status == "completed"


def test_advance_execution_on_a_completed_plan_is_a_pure_no_op(world):
    campaign, plan = _fully_produced_campaign(world)
    world.advance(plan.id)
    review = next(s for s in world.plans.get_plan(plan.id).steps if s.kind == "request_founder_review")
    task = world.memory.get_task(review.task_id)
    task.transition("done", "approved")
    world.memory.save_task(task)
    world.kpis.record("revenue_goal-a", 200.0)
    world.kpis.record("cost_goal-a", 100.0)
    world.advance(plan.id)
    completed = world.plans.get_plan(plan.id)
    assert completed.status == "completed"

    result = world.advance(plan.id)

    assert result.updated_at == completed.updated_at  # untouched — nothing to advance


# --- advance_all_campaign_executions() (the CEOBrain.tick() bridge) --------


def test_advance_all_campaign_executions_advances_every_in_progress_plan(world):
    influencer = world.new_influencer()
    campaign_a = world.new_ready_campaign([influencer.id], goal_id="goal-a")
    campaign_b = world.new_ready_campaign([influencer.id], goal_id="goal-b")
    plan_a = start_execution(campaign_a.id, world.campaigns, world.plans)
    plan_b = start_execution(campaign_b.id, world.campaigns, world.plans)

    advance_all_campaign_executions(
        world.plans, world.campaigns, world.influencers, world.memory, world.kpis, world.knowledge, world.landing_page_dir
    )

    for plan_id in (plan_a.id, plan_b.id):
        steps = world.plans.get_plan(plan_id).steps
        verify = next(s for s in steps if s.kind == "verify_readiness")
        produce = next(s for s in steps if s.kind == "produce_content")
        assert verify.status == "done"  # cascades within one advance call, since produce_content's only dependency is verify_readiness
        assert produce.status == "blocked"  # no essential templates exist yet for this influencer
