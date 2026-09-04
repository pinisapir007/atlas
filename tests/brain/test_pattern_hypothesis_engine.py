from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Finding
from atlas.brain.pattern_hypothesis_engine import (
    candidate_pattern_groups,
    discover_pattern_hypotheses,
    form_pattern_hypothesis,
    select_semantic_pattern_candidate,
)


class _PatternProvider:
    name = "fake_pattern_provider"

    def __init__(self, coherent=True):
        self.coherent = coherent
        self.calls = []

    def complete_structured(self, prompt, fields):
        self.calls.append((prompt, fields))

        if "pattern_candidate_possible" in fields:
            if not self.coherent:
                return {
                    "pattern_candidate_possible": "no",
                    "member_numbers": "",
                    "candidate_theme": "",
                    "reason": "observations are unrelated",
                }
            return {
                "pattern_candidate_possible": "yes",
                "member_numbers": "1,2",
                "candidate_theme": "recurring delivery friction",
                "reason": "both observations concern repeated delivery problems",
            }

        if not self.coherent:
            return {
                "coherent_claim_possible": "no",
                "predicate": "",
                "object": "",
                "supporting_points": "",
                "counter_considerations": "observations are unrelated",
            }

        return {
            "coherent_claim_possible": "yes",
            "predicate": "recurring_customer_friction",
            "object": "delivery delay appears repeatedly associated with complaints",
            "supporting_points": "multiple observations mention the same friction",
            "counter_considerations": "the observations may reflect a temporary event",
        }


def _kb(tmp_path):
    return KnowledgeBase(tmp_path / "knowledge.json")


def _finding(
    kb,
    *,
    description,
    evidence,
    source="research",
    category="company_research",
    subject="",
    market="",
    claimant="",
    evidence_role="",
    content_hash="",
    locator="",
):
    finding = Finding(
        source=source,
        category=category,
        description=description,
        evidence=evidence,
        subject=subject,
        market=market,
        claimant=claimant,
        evidence_role=evidence_role,
        content_hash=content_hash,
        evidence_locator=locator,
    )
    kb.save_finding(finding)
    return finding


def test_repeated_identical_legacy_observation_does_not_create_pattern_candidate(
    tmp_path,
):
    kb = _kb(tmp_path)

    kwargs = dict(
        description="Customers complain about slow delivery.",
        evidence="https://example.com/report",
        content_hash="a" * 64,
    )
    _finding(kb, **kwargs)
    _finding(kb, **kwargs)

    assert candidate_pattern_groups(kb) == []


def test_unknown_provenance_media_can_form_candidate_without_fake_independence(
    tmp_path,
):
    """Hypothesis generation is broader than independent validation.

    YouTube/media evidence can be real and atomic while claimant/role are
    honestly UNKNOWN. Layer 2 must not discard those observations, but it
    must also never pretend they are independently sourced.
    """
    kb = _kb(tmp_path)

    _finding(
        kb,
        source="video_research",
        description="Spoken: customers mention delayed shipping",
        evidence="https://youtube.com/watch?v=a",
        locator="timestamp:00:30",
        content_hash="a" * 64,
    )
    _finding(
        kb,
        source="video_research",
        description="Visual: comments show repeated delivery complaints",
        evidence="https://youtube.com/watch?v=b",
        locator="timestamp:02:10",
        content_hash="b" * 64,
    )

    groups = candidate_pattern_groups(kb)

    assert len(groups) == 1
    assert len(groups[0].finding_ids) == 2
    assert groups[0].independent_sources == 0


def test_proven_independent_sources_are_preserved_as_strength_metadata(
    tmp_path,
):
    kb = _kb(tmp_path)

    _finding(
        kb,
        description="Customer review reports slow delivery.",
        evidence="https://source-a.example/report",
        evidence_role="direct_assertion",
    )
    _finding(
        kb,
        description="Separate report identifies delivery delays.",
        evidence="https://source-b.example/report",
        evidence_role="direct_assertion",
    )

    groups = candidate_pattern_groups(kb)

    assert len(groups) == 1
    assert groups[0].independent_sources == 2


def test_pattern_hypothesis_is_evidence_linked_and_explicitly_a_hypothesis(
    tmp_path,
):
    kb = _kb(tmp_path)

    first = _finding(
        kb,
        description="Customers repeatedly complain about slow delivery.",
        evidence="https://source-a.example/report",
        subject="CompanyA",
        market="US",
        evidence_role="direct_assertion",
    )
    second = _finding(
        kb,
        description="Delivery delays are a recurring customer complaint.",
        evidence="https://source-b.example/report",
        subject="CompanyB",
        market="US",
        evidence_role="direct_assertion",
    )

    group = candidate_pattern_groups(kb)[0]
    provider = _PatternProvider()

    claim = form_pattern_hypothesis(
        group,
        kb,
        ai_provider=provider,
    )

    assert claim is not None
    assert claim.claim_type == "hypothesis"
    assert claim.source == "reason_llm"
    assert claim.subject_id == "pattern_scope::company_research"
    assert claim.evidence_finding_ids == [first.id, second.id]

    prompt, _fields = provider.calls[0]
    assert "Independent real-world source count currently proven: 2" in prompt
    assert "subject=CompanyA" in prompt
    assert "subject=CompanyB" in prompt
    assert "market=US" in prompt


def test_unrelated_observations_can_fail_closed_without_creating_claim(
    tmp_path,
):
    kb = _kb(tmp_path)

    _finding(
        kb,
        description="Observation one.",
        evidence="https://source-a.example/x",
        evidence_role="direct_assertion",
    )
    _finding(
        kb,
        description="Observation two.",
        evidence="https://source-b.example/y",
        evidence_role="direct_assertion",
    )

    provider = _PatternProvider(coherent=False)
    group = candidate_pattern_groups(kb)[0]

    result = form_pattern_hypothesis(
        group,
        kb,
        ai_provider=provider,
    )

    assert result is None
    assert kb.claims() == []


def test_same_evidence_set_is_idempotent_and_spends_no_second_llm_call(
    tmp_path,
):
    kb = _kb(tmp_path)

    _finding(
        kb,
        description="Customers mention delivery delays.",
        evidence="https://source-a.example/x",
        evidence_role="direct_assertion",
    )
    _finding(
        kb,
        description="Delivery delays recur in customer feedback.",
        evidence="https://source-b.example/y",
        evidence_role="direct_assertion",
    )

    provider = _PatternProvider()

    first = discover_pattern_hypotheses(
        kb,
        ai_provider=provider,
    )
    second = discover_pattern_hypotheses(
        kb,
        ai_provider=provider,
    )

    assert len(first) == 1
    assert len(second) == 1
    assert first[0].id == second[0].id
    # First run: one semantic-selection call + one reasoning call.\n    # Second identical run: zero additional AI calls.\n    assert len(provider.calls) == 2\n    assert len(kb.claims()) == 1


def test_layer2_is_sensor_agnostic(tmp_path):
    kb = _kb(tmp_path)

    _finding(
        kb,
        source="browser_research",
        description="Browser evidence reports recurring price sensitivity.",
        evidence="https://example.com/article",
        evidence_role="direct_assertion",
    )
    _finding(
        kb,
        source="video_research",
        description="Video observation also shows price sensitivity.",
        evidence="https://youtube.com/watch?v=price",
        locator="timestamp:01:15",
        content_hash="c" * 64,
    )

    groups = candidate_pattern_groups(kb)

    assert len(groups) == 1
    assert len(groups[0].finding_ids) == 2



def test_semantic_selector_can_choose_related_subset_from_broad_category(
    tmp_path,
):
    kb = _kb(tmp_path)

    first = _finding(
        kb,
        description="Customers repeatedly complain about delivery delays.",
        evidence="https://a.example/report",
        subject="CompanyA",
        evidence_role="direct_assertion",
    )
    unrelated = _finding(
        kb,
        description="The company launched a new logo.",
        evidence="https://b.example/brand",
        subject="CompanyB",
        evidence_role="direct_assertion",
    )
    third = _finding(
        kb,
        description="Late shipping is a repeated source of customer complaints.",
        evidence="https://c.example/reviews",
        subject="CompanyC",
        evidence_role="direct_assertion",
    )

    class _SubsetProvider:
        name = "subset"

        def complete_structured(self, prompt, fields):
            return {
                "pattern_candidate_possible": "yes",
                "member_numbers": "1,3",
                "candidate_theme": "recurring delivery friction",
                "reason": "observations 1 and 3 describe the same recurring friction",
            }

    broad = candidate_pattern_groups(kb)[0]
    selected = select_semantic_pattern_candidate(
        broad,
        kb,
        ai_provider=_SubsetProvider(),
    )

    assert selected is not None
    assert selected.finding_ids == (first.id, third.id)
    assert unrelated.id not in selected.finding_ids


def test_semantic_selector_rejects_hallucinated_member_number(
    tmp_path,
):
    kb = _kb(tmp_path)

    _finding(
        kb,
        description="Observation A.",
        evidence="https://a.example/x",
        evidence_role="direct_assertion",
    )
    _finding(
        kb,
        description="Observation B.",
        evidence="https://b.example/y",
        evidence_role="direct_assertion",
    )

    class _HallucinatingSelector:
        name = "bad"

        def complete_structured(self, prompt, fields):
            return {
                "pattern_candidate_possible": "yes",
                "member_numbers": "1,99",
                "candidate_theme": "invented grouping",
                "reason": "bad selection",
            }

    broad = candidate_pattern_groups(kb)[0]

    assert (
        select_semantic_pattern_candidate(
            broad,
            kb,
            ai_provider=_HallucinatingSelector(),
        )
        is None
    )


def test_semantic_selector_can_fail_closed_when_category_has_no_real_cluster(
    tmp_path,
):
    kb = _kb(tmp_path)

    _finding(
        kb,
        description="A product costs $29.",
        evidence="https://a.example/x",
        evidence_role="direct_assertion",
    )
    _finding(
        kb,
        description="A company changed its logo.",
        evidence="https://b.example/y",
        evidence_role="direct_assertion",
    )

    provider = _PatternProvider(coherent=False)
    broad = candidate_pattern_groups(kb)[0]

    assert (
        select_semantic_pattern_candidate(
            broad,
            kb,
            ai_provider=provider,
        )
        is None
    )
