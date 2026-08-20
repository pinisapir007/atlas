from pathlib import Path

from atlas.brain.claims import claim_status
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.marketplace_extraction import extract_marketplace_products
from atlas.brain.marketplace_semantic_grounding import (
    LABELED_FIELDS,
    SOURCE_NAME,
    extract_field_tooltips,
    field_grounding,
    ground_labeled_fields,
    ground_marketplace_fields,
)

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "browser_snapshots" / "digistore24_marketplace_sample.txt"


def _kb(tmp_path):
    return KnowledgeBase(tmp_path / "knowledge.json")


class _FakeOriginalNode:
    """Mirrors the real, relevant slice of browser_use's EnhancedDOMTreeNode
    -- tag_name + parent_node.attributes, the only two things
    extract_field_tooltips() ever reads."""

    def __init__(self, tag_name, parent_node=None):
        self.tag_name = tag_name
        self.parent_node = parent_node


class _FakeParentNode:
    def __init__(self, attributes):
        self.attributes = attributes


class _FakeSimplifiedNode:
    """Mirrors the real, relevant slice of browser_use's SimplifiedNode --
    original_node + children, the tree-walk shape extract_field_tooltips()
    now uses (2026-08-16, Blocker 2 root-cause fix -- walks the full DOM
    tree, not selector_map)."""

    def __init__(self, original_node=None, children=None):
        self.original_node = original_node
        self.children = children or []


def _tree(*leaf_nodes) -> _FakeSimplifiedNode:
    """A minimal root with the given leaf _FakeOriginalNode-wrapped nodes
    as direct children -- depth doesn't matter to the walk, only the
    original_node/children shape does."""
    return _FakeSimplifiedNode(children=[_FakeSimplifiedNode(original_node=n) for n in leaf_nodes])


# --- extract_field_tooltips() -- pure, DOM-facing, Digistore24-specific ----
# Walks the full DOM tree (dom_root), NOT selector_map -- root-caused live
# (2026-08-16): 3 consecutive identical reads proved selector_map omits
# real tooltip-bearing nodes every time while the full tree finds them
# every time. See extract_field_tooltips()'s own docstring.


def test_extract_field_tooltips_reads_real_mattooltip_off_the_parent():
    root = _tree(_FakeOriginalNode("coin-hands-icon", parent_node=_FakeParentNode({"mattooltip": "Your share of the vendor's earnings"})))

    result = extract_field_tooltips(root)

    assert result == {"commission_pct": "Your share of the vendor's earnings"}


def test_extract_field_tooltips_covers_all_three_live_confirmed_icons():
    root = _tree(
        _FakeOriginalNode("coin-hands-icon", parent_node=_FakeParentNode({"mattooltip": "Your share of the vendor's earnings"})),
        _FakeOriginalNode("ds-marketplace-shopping-cart-icon", parent_node=_FakeParentNode({"mattooltip": "Visitors who open the order form and then make a purchase"})),
        _FakeOriginalNode("ds-marketplace-cancel-icon", parent_node=_FakeParentNode({"mattooltip": "Share of returns and chargebacks"})),
    )

    result = extract_field_tooltips(root)

    assert result == {
        "commission_pct": "Your share of the vendor's earnings",
        "cart_conversion_pct": "Visitors who open the order form and then make a purchase",
        "secondary_rate_pct": "Share of returns and chargebacks",
    }


def test_extract_field_tooltips_never_fabricates_an_entry_for_an_icon_with_no_tooltip():
    """price-tag/person/calender/bookmark icons -- confirmed live to carry
    no matTooltip. Must never appear in the result, not even as None."""
    root = _tree(
        _FakeOriginalNode("ds-marketplace-price-tag-icon", parent_node=_FakeParentNode({})),
        _FakeOriginalNode("ds-marketplace-person-icon", parent_node=_FakeParentNode({"class": "ng-star-inserted"})),
        _FakeOriginalNode("ds-marketplace-calender-icon", parent_node=None),
    )

    result = extract_field_tooltips(root)

    assert result == {}


def test_extract_field_tooltips_ignores_unrelated_icons_entirely():
    root = _tree(_FakeOriginalNode("ds-marketplace-bookmark-icon", parent_node=_FakeParentNode({"mattooltip": "Add to favorites"})))

    result = extract_field_tooltips(root)

    assert result == {}  # bookmark icon isn't in TOOLTIP_ICON_TO_FIELD -- never guessed in


def test_extract_field_tooltips_walks_nested_children_not_just_direct_children():
    """The real tree is several levels deep (icon nested under ds-icon
    under ds-marketplace-icon under the card div) -- the walk must recurse,
    not just check the immediate root's children."""
    leaf = _FakeSimplifiedNode(original_node=_FakeOriginalNode("coin-hands-icon", parent_node=_FakeParentNode({"mattooltip": "Your share of the vendor's earnings"})))
    mid = _FakeSimplifiedNode(children=[leaf])
    root = _FakeSimplifiedNode(children=[mid])

    result = extract_field_tooltips(root)

    assert result == {"commission_pct": "Your share of the vendor's earnings"}


def test_extract_field_tooltips_handles_missing_root():
    assert extract_field_tooltips(None) == {}


# --- ground_marketplace_fields() -- generic Finding+Claim wiring -----------


def test_ground_marketplace_fields_creates_a_real_finding_and_claim(tmp_path):
    kb = _kb(tmp_path)

    result = ground_marketplace_fields({"commission_pct": "Your share of the vendor's earnings"}, kb)

    assert result == {"commission_pct": "newly_grounded"}
    claim = field_grounding("commission_pct", kb)
    assert claim is not None
    assert claim.predicate == "means"
    assert claim.object_value == "Your share of the vendor's earnings"
    assert claim.claim_type == "observation"
    assert claim_status(claim) == "supported"

    finding = kb.get_finding(claim.evidence_finding_ids[0])
    assert finding.evidence == "Your share of the vendor's earnings"
    assert finding.provider == SOURCE_NAME


def test_ground_marketplace_fields_evidence_role_is_direct_assertion(tmp_path):
    """ONE BRAIN Evidence Role Gate (2026-08-17): this tooltip text IS
    digistore24's own first-party statement about its own schema -- no
    vendor/third party involved. Safe to trust via origin alone even
    with claimant left unpopulated."""
    kb = _kb(tmp_path)
    ground_marketplace_fields({"commission_pct": "Your share of the vendor's earnings"}, kb)

    finding = kb.findings(category="marketplace_field_semantics")[0]
    assert finding.evidence_role == "direct_assertion"


def test_ground_marketplace_fields_is_idempotent_no_duplicate_on_second_call(tmp_path):
    kb = _kb(tmp_path)
    ground_marketplace_fields({"commission_pct": "Your share of the vendor's earnings"}, kb)

    result = ground_marketplace_fields({"commission_pct": "Your share of the vendor's earnings"}, kb)

    assert result == {"commission_pct": "already_grounded"}
    assert len(kb.claims(subject_id="digistore24_marketplace:field:commission_pct", predicate="means")) == 1
    assert len(kb._read()["findings"]) == 1


def test_ground_marketplace_fields_grounds_multiple_fields_independently(tmp_path):
    kb = _kb(tmp_path)

    result = ground_marketplace_fields(
        {
            "commission_pct": "Your share of the vendor's earnings",
            "cart_conversion_pct": "Visitors who open the order form and then make a purchase",
            "secondary_rate_pct": "Share of returns and chargebacks",
        },
        kb,
    )

    assert result == {
        "commission_pct": "newly_grounded",
        "cart_conversion_pct": "newly_grounded",
        "secondary_rate_pct": "newly_grounded",
    }
    assert field_grounding("commission_pct", kb) is not None
    assert field_grounding("cart_conversion_pct", kb) is not None
    assert field_grounding("secondary_rate_pct", kb) is not None


def test_ground_marketplace_fields_skips_empty_tooltip_text(tmp_path):
    kb = _kb(tmp_path)

    result = ground_marketplace_fields({"commission_pct": ""}, kb)

    assert result == {}
    assert field_grounding("commission_pct", kb) is None


# --- field_grounding() -- honest UNKNOWN, never fabricated -----------------


def test_field_grounding_returns_none_for_an_ungrounded_field(tmp_path):
    """observed_date_raw's real case: no tooltip was ever found for the
    calendar icon -- must stay honestly UNKNOWN, never a guessed Claim."""
    kb = _kb(tmp_path)

    assert field_grounding("observed_date_raw", kb) is None


def test_field_grounding_ignores_a_superseded_claim(tmp_path):
    kb = _kb(tmp_path)
    ground_marketplace_fields({"commission_pct": "old wording"}, kb)
    old = field_grounding("commission_pct", kb)

    from atlas.brain.models import Claim, Finding

    new_finding = Finding(source=SOURCE_NAME, category="marketplace_field_semantics", description="revised", evidence="revised wording")
    kb.save_finding(new_finding)
    new_claim = Claim(
        subject_id=old.subject_id, predicate="means", object_value="revised wording",
        evidence_finding_ids=[new_finding.id], claim_type="observation",
    )
    kb.save_claim(new_claim)
    old.superseded_by_id = new_claim.id
    kb.save_claim(old)

    assert field_grounding("commission_pct", kb).id == new_claim.id


# --- Generalization: the general Finding->Claim wiring is not Digistore24- -
# -owned; only extract_field_tooltips() is source-specific.


# --- ground_labeled_fields() -- weaker, label-only evidence (2026-08-17) ---
# Deliberately predicate="labeled_as", never "means" -- confirms only what
# the source CALLS a field, never what it represents or how it's computed.


def test_ground_labeled_fields_grounds_net_earnings_per_sale_from_the_real_label(tmp_path):
    kb = _kb(tmp_path)
    text = "...$114.50 Net earnings/sale ..."

    result = ground_labeled_fields(text, kb)

    assert result == {"net_earnings_per_sale": "newly_grounded"}
    claim = field_grounding("net_earnings_per_sale", kb)
    assert claim is not None
    assert claim.predicate == "labeled_as"
    assert claim.object_value == "Net earnings/sale"
    assert claim.claim_type == "observation"
    assert claim_status(claim) == "supported"


def test_ground_labeled_fields_never_asserts_means_only_labeled_as(tmp_path):
    """The exact epistemic distinction the founder required: a label
    confirms the NAME, never the MEANING -- must never be saved under the
    'means' predicate ground_marketplace_fields() uses."""
    kb = _kb(tmp_path)
    ground_labeled_fields("...$114.50 Net earnings/sale ...", kb)

    assert kb.claims(subject_id="digistore24_marketplace:field:net_earnings_per_sale", predicate="means") == []
    assert len(kb.claims(subject_id="digistore24_marketplace:field:net_earnings_per_sale", predicate="labeled_as")) == 1


def test_ground_labeled_fields_evidence_role_is_direct_assertion(tmp_path):
    kb = _kb(tmp_path)
    ground_labeled_fields("...$114.50 Net earnings/sale ...", kb)

    finding = kb.findings(category="marketplace_field_semantics")[0]
    assert finding.evidence_role == "direct_assertion"


def test_ground_labeled_fields_is_idempotent(tmp_path):
    kb = _kb(tmp_path)
    ground_labeled_fields("Net earnings/sale", kb)

    result = ground_labeled_fields("Net earnings/sale", kb)

    assert result == {"net_earnings_per_sale": "already_grounded"}
    assert len(kb.claims(subject_id="digistore24_marketplace:field:net_earnings_per_sale", predicate="labeled_as")) == 1


def test_ground_labeled_fields_grounds_nothing_when_label_absent(tmp_path):
    kb = _kb(tmp_path)

    result = ground_labeled_fields("no relevant label anywhere in this text", kb)

    assert result == {}
    assert field_grounding("net_earnings_per_sale", kb) is None


def test_field_grounding_finds_a_labeled_as_claim_same_as_a_means_claim(tmp_path):
    """field_grounding() must not silently miss a weaker (labeled_as)
    grounding just because it was built to look for 'means' originally."""
    kb = _kb(tmp_path)
    ground_labeled_fields("Net earnings/sale", kb)

    claim = field_grounding("net_earnings_per_sale", kb)

    assert claim is not None
    assert claim.predicate == "labeled_as"


def test_labeled_fields_mapping_contains_net_earnings_per_sale():
    assert LABELED_FIELDS.get("net_earnings_per_sale") == "Net earnings/sale"


# --- Acceptance Test A: full backward traceability on one real product -----


def test_full_traceability_from_a_real_products_value_back_to_raw_source_evidence(tmp_path):
    """value -> semantic meaning -> Claim -> evidence Finding -> raw
    source evidence, on one real product from a real, live-captured
    snapshot -- the exact chain the founder's acceptance test requires."""
    kb = _kb(tmp_path)
    records = extract_marketplace_products(FIXTURE_PATH.read_text(encoding="utf-8"), "https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all")
    real_product = records[0]  # Joseph's Well, real commission_pct=75.0

    # Real tooltip text, live-confirmed (2026-08-16) against the actual DOM.
    ground_marketplace_fields({"commission_pct": "Your share of the vendor's earnings"}, kb)

    # Step 1: the real value on the real product.
    assert real_product.commission_pct == 75.0

    # Step 2: what that FIELD means (schema-level, not per-product).
    claim = field_grounding("commission_pct", kb)
    assert claim is not None
    assert claim.object_value == "Your share of the vendor's earnings"

    # Step 3: the evidence backing that meaning.
    assert claim_status(claim) == "supported"
    finding = kb.get_finding(claim.evidence_finding_ids[0])

    # Step 4: the raw source evidence itself, verbatim.
    assert finding.evidence == "Your share of the vendor's earnings"
    assert finding.provider == SOURCE_NAME

    # And the inverse honesty check: a field with no grounding evidence
    # stays honestly unknown, even on this same real product.
    assert field_grounding("observed_date_raw", kb) is None
    assert real_product.observed_date_raw is not None  # the raw value IS captured...
    # ...but what it MEANS is correctly still UNKNOWN.


def test_ground_marketplace_fields_works_for_a_wholly_different_hypothetical_source(tmp_path):
    kb = _kb(tmp_path)

    result = ground_marketplace_fields(
        {"conversion_rate": "The percentage of clicks that resulted in a sale"},
        kb,
        source_name="example_mart",
    )

    assert result == {"conversion_rate": "newly_grounded"}
    claim = field_grounding("conversion_rate", kb, source_name="example_mart")
    assert claim.subject_id == "example_mart:field:conversion_rate"
