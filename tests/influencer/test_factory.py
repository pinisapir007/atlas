import pytest

from atlas.assets.affiliate_department.models import AffiliateOpportunity
from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding, Task
from atlas.influencer.factory import (
    InfluencerDraft,
    create_influencer_from_proposal,
    draft_influencer_proposal,
    suggest_persona,
)
from atlas.influencer.registry import InfluencerRegistry


def _kb(tmp_path):
    return KnowledgeBase(tmp_path / "knowledge.json")


def _opportunity(marketing_niche="KetoDNA", recommended_market="US", category="affiliate", product_name="KetoDNA") -> AffiliateOpportunity:
    return AffiliateOpportunity(
        product_name=product_name, description="d", category=category, marketing_niche=marketing_niche, recommended_market=recommended_market
    )


def test_draft_cites_real_evidence_when_available(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(Finding(source="research", category="affiliate", description="a", evidence="https://x/1", subject="KetoDNA", market="US"))
    kb.save_finding(Finding(source="research", category="affiliate", description="b", evidence="https://x/2", subject="KetoDNA", market="US"))
    opportunity = _opportunity()

    draft = draft_influencer_proposal(opportunity, kb)

    assert draft.recommended_market == "US"
    assert draft.recommended_niche == "KetoDNA"
    assert draft.recommended_category == "affiliate"
    assert draft.source_opportunity_id == opportunity.id
    assert set(draft.evidence) == {"https://x/1", "https://x/2"}
    assert "US" in draft.rationale
    assert "2 independent source" in draft.rationale


def test_draft_looks_up_real_nationality_and_native_language_for_a_known_market(tmp_path):
    kb = _kb(tmp_path)
    opportunity = _opportunity(recommended_market="MX", marketing_niche="KetoDNA")

    draft = draft_influencer_proposal(opportunity, kb)

    assert draft.nationality == "Mexican"
    assert draft.native_language == "Spanish"


def test_draft_never_guesses_locale_for_an_unlisted_market(tmp_path):
    kb = _kb(tmp_path)
    opportunity = _opportunity(recommended_market="ZZ")  # not a real, listed market

    draft = draft_influencer_proposal(opportunity, kb)

    assert draft.nationality == ""
    assert draft.native_language == ""


def test_draft_has_no_locale_when_no_market_is_recommended(tmp_path):
    kb = _kb(tmp_path)
    opportunity = _opportunity(recommended_market="")

    draft = draft_influencer_proposal(opportunity, kb)

    assert draft.nationality == ""
    assert draft.native_language == ""


def test_draft_builds_an_honest_audience_description_from_real_fields(tmp_path):
    kb = _kb(tmp_path)
    opportunity = _opportunity(recommended_market="US", marketing_niche="KetoDNA")

    draft = draft_influencer_proposal(opportunity, kb)

    assert draft.recommended_audience == "US audience interested in KetoDNA"


def test_draft_audience_description_omits_market_when_none_is_recommended(tmp_path):
    kb = _kb(tmp_path)
    opportunity = _opportunity(recommended_market="", marketing_niche="KetoDNA")

    draft = draft_influencer_proposal(opportunity, kb)

    assert draft.recommended_audience == "Audience interested in KetoDNA"


# --- suggest_persona --------------------------------------------------


def _draft(nationality="American", niche="KetoDNA", opportunity_id="aopp-fixed-1") -> InfluencerDraft:
    return InfluencerDraft(
        recommended_market="US", recommended_niche=niche, recommended_category="affiliate",
        source_opportunity_id=opportunity_id, rationale="r", nationality=nationality,
    )


def test_suggest_persona_is_deterministic_for_the_same_opportunity():
    draft = _draft()

    first = suggest_persona(draft)
    second = suggest_persona(draft)

    assert first == second


def test_suggest_persona_can_differ_across_different_opportunities():
    a = suggest_persona(_draft(opportunity_id="aopp-1"))
    b = suggest_persona(_draft(opportunity_id="aopp-2"))
    c = suggest_persona(_draft(opportunity_id="aopp-3"))

    # Not a strict "must all differ" (pools are finite, collisions are
    # fine) -- just confirms this isn't hardcoded to one constant value.
    assert len({a.local_name, b.local_name, c.local_name}) > 1


def test_suggest_persona_picks_a_culturally_appropriate_name_pool():
    suggestion = suggest_persona(_draft(nationality="Mexican"))

    from atlas.influencer.factory import NAME_POOLS
    assert suggestion.local_name in NAME_POOLS["Mexican"]


def test_suggest_persona_falls_back_to_default_pool_for_an_unknown_nationality():
    suggestion = suggest_persona(_draft(nationality="Atlantean"))  # not a real, listed nationality

    from atlas.influencer.factory import _DEFAULT_NAME_POOL
    assert suggestion.local_name in _DEFAULT_NAME_POOL


def test_suggest_persona_every_field_is_non_empty():
    suggestion = suggest_persona(_draft())

    assert suggestion.local_name
    assert suggestion.personality
    assert suggestion.age_range
    assert suggestion.communication_style
    assert suggestion.visual_style
    assert suggestion.preferred_platforms


def test_suggest_persona_personality_references_the_real_niche():
    suggestion = suggest_persona(_draft(niche="KetoDNA"))

    assert "KetoDNA" in suggestion.personality


def test_draft_never_fabricates_evidence_when_none_is_tagged(tmp_path):
    kb = _kb(tmp_path)  # no findings at all
    opportunity = _opportunity(recommended_market="US")

    draft = draft_influencer_proposal(opportunity, kb)

    assert draft.evidence == []
    assert "no cited evidence" in draft.rationale


def test_draft_is_honest_about_no_market_recommendation(tmp_path):
    kb = _kb(tmp_path)
    opportunity = _opportunity(recommended_market="")

    draft = draft_influencer_proposal(opportunity, kb)

    assert draft.recommended_market == ""
    assert "No market-specific evidence" in draft.rationale


def test_draft_falls_back_to_product_name_when_no_marketing_niche_is_set(tmp_path):
    # Founder-manual intake (intake_real_product) never sets marketing_niche.
    kb = _kb(tmp_path)
    opportunity = _opportunity(marketing_niche="", product_name="KetoDNA", recommended_market="")

    draft = draft_influencer_proposal(opportunity, kb)

    assert draft.recommended_niche == "KetoDNA"


def test_draft_never_includes_any_fabricated_identity_fields():
    # Structural guarantee, not just a convention: InfluencerDraft's own
    # shape has no field to accidentally populate for anything without a
    # real evidence source -- name/personality/bio/voice/visual (never had
    # one) and age_range/communication_style/visual_style/preferred_platforms
    # (no real demographic/generation/per-platform-performance data exists
    # anywhere in this codebase either) -- the "no fabricated identity"
    # boundary is enforced by the dataclass definition itself, not by
    # convention.
    from dataclasses import fields
    from atlas.influencer.factory import InfluencerDraft

    field_names = {f.name for f in fields(InfluencerDraft)}
    assert field_names.isdisjoint(
        {"name", "personality", "bio", "voice", "visual", "age_range", "communication_style", "visual_style", "preferred_platforms"}
    )


# --- create_influencer_from_proposal ---------------------------------------


class _World:
    def __init__(self, tmp_path):
        self.memory = BrainMemory(tmp_path / "brain.json")
        self.knowledge = KnowledgeBase(tmp_path / "knowledge.json")
        self.affiliate_store = AffiliateStore(tmp_path / "affiliate_intelligence.json")
        self.influencers = InfluencerRegistry(tmp_path / "influencers.json")

    def approved_proposal_task(self, market="US", niche="KetoDNA", category="affiliate") -> Task:
        opportunity = AffiliateOpportunity(
            product_name=niche, description="d", category=category, marketing_niche=niche, recommended_market=market
        )
        self.affiliate_store.save_opportunity(opportunity)
        task = Task(goal_id="goal-a", description="Digital Influencer Factory: recommend creating a new influencer", category="create_asset", source_opportunity_id=opportunity.id)
        task.transition("done", "proposal applied")  # simulates a real brain approve()
        self.memory.save_task(task)
        return task


def test_creates_a_real_influencer_from_an_approved_proposal_with_explicit_overrides(tmp_path):
    world = _World(tmp_path)
    task = world.approved_proposal_task(market="US", niche="KetoDNA", category="affiliate")

    influencer = create_influencer_from_proposal(
        task.id, world.memory, world.affiliate_store, world.knowledge, world.influencers,
        name="Maya Health", personality="warm, first-person", bio="a real bio",
    )

    assert influencer.identity.name == "Maya Health"
    assert influencer.identity.nationality == "American"
    assert influencer.identity.market == "US"  # the real, machine-comparable match key -- distinct from the human-readable nationality
    assert influencer.identity.language == "English"
    assert influencer.identity.niche == "KetoDNA"
    assert influencer.identity.personality == "warm, first-person"
    assert influencer.identity.bio == "a real bio"
    assert influencer.categories == ["affiliate"]
    assert influencer.audience.description == "US audience interested in KetoDNA"
    assert world.influencers.get_influencer(influencer.id).identity.name == "Maya Health"


def test_creation_defaults_every_who_field_to_the_ai_suggestion_when_omitted(tmp_path):
    world = _World(tmp_path)
    task = world.approved_proposal_task(market="US", niche="KetoDNA", category="affiliate")
    opportunity = world.affiliate_store.get_opportunity(task.source_opportunity_id)
    draft = draft_influencer_proposal(opportunity, world.knowledge)
    expected = suggest_persona(draft)

    influencer = create_influencer_from_proposal(task.id, world.memory, world.affiliate_store, world.knowledge, world.influencers)

    assert influencer.identity.name == expected.local_name
    assert influencer.identity.personality == expected.personality
    assert influencer.identity.age_range == expected.age_range
    assert influencer.content_style.tone == expected.communication_style
    assert influencer.visual.description == expected.visual_style
    assert influencer.identity.bio == ""  # bio has no suggestion, always founder-only


def test_creation_lets_founder_override_a_single_field_and_keep_the_rest_suggested(tmp_path):
    world = _World(tmp_path)
    task = world.approved_proposal_task(market="US", niche="KetoDNA", category="affiliate")
    opportunity = world.affiliate_store.get_opportunity(task.source_opportunity_id)
    draft = draft_influencer_proposal(opportunity, world.knowledge)
    expected = suggest_persona(draft)

    influencer = create_influencer_from_proposal(task.id, world.memory, world.affiliate_store, world.knowledge, world.influencers, name="Custom Name")

    assert influencer.identity.name == "Custom Name"
    assert influencer.identity.personality == expected.personality  # untouched fields still suggested


def test_rejects_a_task_that_is_not_a_factory_proposal(tmp_path):
    world = _World(tmp_path)
    ordinary_task = Task(goal_id="goal-a", description="unrelated", category="affiliate_intelligence")
    ordinary_task.transition("done", "x")
    world.memory.save_task(ordinary_task)

    with pytest.raises(ValueError, match="not a Digital Influencer Factory proposal"):
        create_influencer_from_proposal(ordinary_task.id, world.memory, world.affiliate_store, world.knowledge, world.influencers, name="Maya")


def test_rejects_creation_before_approval(tmp_path):
    world = _World(tmp_path)
    opportunity = AffiliateOpportunity(product_name="KetoDNA", description="d", category="affiliate", recommended_market="US")
    world.affiliate_store.save_opportunity(opportunity)
    unapproved_task = Task(goal_id="goal-a", description="Digital Influencer Factory: recommend creating a new influencer", category="create_asset", source_opportunity_id=opportunity.id)
    world.memory.save_task(unapproved_task)  # still "proposed" -- never approved

    with pytest.raises(ValueError, match="has not been approved yet"):
        create_influencer_from_proposal(unapproved_task.id, world.memory, world.affiliate_store, world.knowledge, world.influencers, name="Maya")


def test_rejects_a_rejected_proposal(tmp_path):
    world = _World(tmp_path)
    task = world.approved_proposal_task()
    task.transition("failed", "rejected by owner")  # simulates CEOBrain.reject()
    world.memory.save_task(task)

    with pytest.raises(ValueError, match="has not been approved yet"):
        create_influencer_from_proposal(task.id, world.memory, world.affiliate_store, world.knowledge, world.influencers, name="Maya")
