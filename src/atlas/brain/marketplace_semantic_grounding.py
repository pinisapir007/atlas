"""Marketplace Semantic Grounding (2026-08-16) -- wires Digital Body
Marketplace Perception to the already-existing Cognitive Foundation
(`Claim`/`KnowledgeBase`), closing a real, live-confirmed gap: a real,
source-provided semantic hint (a Digistore24 Angular `matTooltip`) was
being read live during diagnosis but never preserved anywhere, and
`MarketplaceProductRecord`'s numeric fields carried no link to what they
mean or what real evidence supports that meaning.

Deliberately NOT a new Semantic Engine, NOT a Truth Protocol, NOT a
taxonomy parallel to Claim/Finding: this module is pure glue over
already-existing, already-tested primitives. No LLM call anywhere here --
a real tooltip's own text IS the evidence, quoted verbatim; asserting
"the source itself states field X means Y" needs no inference step, so
every Claim this module creates is `claim_type="observation"`.

Grounding is schema-level (per source+field), never per-instance (per-
product): the meaning of "commission_pct" is identical across every
product Digistore24 shows it on. One real Claim, formed once, reused
forever -- never one Claim per product observed.

Generalization: only `extract_field_tooltips()` touches the real DOM and
is Digistore24-specific (a `mattooltip` attribute read off a known set of
icon tags, walking the full simplified DOM tree -- see that function's
own docstring for why `selector_map` was live-proven unreliable for this
and `dom_root` is used instead). `ground_marketplace_fields()`/
`field_grounding()` are fully generic -- they would work identically for
a future, unrelated source's own field-meaning tooltips, since they only
ever call `Finding`/`Claim`/`KnowledgeBase.claims()`, never anything
Marketplace- or Digistore24-specific themselves.

Production wiring (2026-08-16, Blocker 1): called from
`marketplace_discovery.run_discovery()` every cycle a real `dom_root` is
available (i.e. every cycle after the first -- the first, `observe()`-
based cycle has no DOM tree; see that module's own docstring), gated
behind an optional `knowledge: KnowledgeBase | None` parameter --
`None` (the default) preserves every existing caller's/test's exact
original behavior, grounding runs only when a real `KnowledgeBase` is
actually supplied.
"""

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.marketplace_extraction import NET_EARNINGS_LABEL
from atlas.brain.models import Claim, Finding

SOURCE_NAME = "digistore24_marketplace"

# Real, live-confirmed (2026-08-17) field -> verbatim visible-label text
# mapping -- deliberately a WEAKER evidence class than TOOLTIP_ICON_TO_
# FIELD: a label only confirms what the source CALLS the field, never
# what it means or how it's computed. `ground_labeled_fields()` below
# uses `predicate="labeled_as"`, never `"means"`, so the two evidence
# strengths can never be confused by a caller inspecting a Claim.
LABELED_FIELDS = {
    "net_earnings_per_sale": NET_EARNINGS_LABEL,
}

# Real, live-confirmed (2026-08-16) icon-tag -> MarketplaceProductRecord
# field-name mapping, ONLY for icons a real matTooltip was actually found
# on (direct DOM inspection, not guessed). price-tag/person/calender/
# bookmark icons carry no matTooltip -- deliberately absent here, never
# filled in with an invented meaning.
TOOLTIP_ICON_TO_FIELD = {
    "coin-hands-icon": "commission_pct",
    "ds-marketplace-shopping-cart-icon": "cart_conversion_pct",
    "ds-marketplace-cancel-icon": "secondary_rate_pct",
}


def extract_field_tooltips(root) -> dict[str, str]:
    """The one DOM-touching, Digistore24-specific function in this
    module. Reads the real `mattooltip` attribute off the PARENT of each
    known icon node -- the exact structure confirmed live (2026-08-16:
    coin-hands-icon's parent carries `mattooltip="Your share of the
    vendor's earnings"`, etc.). Pure read -- no navigation/click/scroll,
    the same read-only discipline every other DOM-facing function in this
    codebase already has; `root` is always supplied by the caller (never
    fetched here), the same "credential/DOM-touching code stays at the
    edge" boundary `href_map` already established for
    `extract_marketplace_products()`.

    Walks the full simplified DOM tree (`dom_state._root`, a SimplifiedNode
    -- e.g. a `DiscoveryScrollAdvancer` result's `dom_root`, captured with
    `include_dom=True`), deliberately NOT `selector_map` -- root-caused
    live (2026-08-16, Blocker 2): three consecutive identical reads, zero
    action between them, proved the real tooltip-bearing icon nodes are
    reliably present in `_root` every time (ruling out timing/lazy-
    render/virtualization), while `selector_map` omitted them every time
    -- `selector_map` is browser-use's interactive-element index, capped/
    filtered independently of tooltip presence, never a reliable source
    for a non-interactive attribute like this. No interaction (hover,
    click) is required or performed here -- the tooltip text is a static
    DOM attribute, present without any interaction, confirmed by this
    same live investigation.

    Returns {field_name: tooltip_text} ONLY for icons whose parent
    actually carries a real, non-empty tooltip this call -- never a
    guessed/default entry for a field with none found. Fail-closed on
    `root=None` (nothing to walk): returns `{}`, never fabricates."""
    found: dict[str, str] = {}

    def walk(node) -> None:
        original = getattr(node, "original_node", None)
        if original is not None:
            tag = getattr(original, "tag_name", "")
            field_name = TOOLTIP_ICON_TO_FIELD.get(tag)
            if field_name is not None and field_name not in found:
                parent = getattr(original, "parent_node", None)
                parent_attrs = (getattr(parent, "attributes", {}) or {}) if parent is not None else {}
                tooltip = (parent_attrs.get("mattooltip") or "").strip()
                if tooltip:
                    found[field_name] = tooltip
        for child in getattr(node, "children", None) or []:
            walk(child)

    if root is not None:
        walk(root)
    return found


def ground_marketplace_fields(
    field_tooltips: dict[str, str],
    knowledge: KnowledgeBase,
    source_name: str = SOURCE_NAME,
) -> dict[str, str]:
    """For each (field, tooltip) pair, ensures exactly one real,
    evidence-backed Claim exists grounding what that field means on
    `source_name` -- idempotent, checked via `knowledge.claims()`, never
    a duplicate Finding/Claim pair for the same field on repeated calls
    with the same real tooltip text. Never overwrites/revises an
    existing grounding Claim just because this ran again -- revising a
    field's known meaning is a deliberate, separate, human/reason()-
    mediated action (setting `superseded_by_id`), not a side effect of
    re-observing the same tooltip.

    Returns {field_name: status}, status one of "already_grounded" |
    "newly_grounded" -- an honest record of what this specific call did,
    never a bare None."""
    results: dict[str, str] = {}
    for field_name, tooltip_text in field_tooltips.items():
        if not tooltip_text:
            continue
        subject_id = f"{source_name}:field:{field_name}"
        existing = knowledge.claims(subject_id=subject_id, predicate="means")
        if existing:
            results[field_name] = "already_grounded"
            continue

        finding = Finding(
            source=source_name,
            category="marketplace_field_semantics",
            description=f"{source_name} states the real meaning of {field_name!r}: {tooltip_text!r}",
            evidence=tooltip_text,
            provider=source_name,
            # evidence_role (2026-08-17, ONE BRAIN Evidence Role Gate):
            # "direct_assertion" -- this tooltip text IS source_name's own
            # first-party statement about its own UI/schema; no vendor or
            # third party is involved in defining what a field means.
            # claimant population is deliberately out of scope for this
            # round (see the Evidence Role Gate implementation's own
            # locked scope) -- stays "" for now, unchanged.
            evidence_role="direct_assertion",
        )
        knowledge.save_finding(finding)

        claim = Claim(
            subject_id=subject_id,
            predicate="means",
            object_value=tooltip_text,
            evidence_finding_ids=[finding.id],
            claim_type="observation",
            source="manual",
        )
        knowledge.save_claim(claim)
        results[field_name] = "newly_grounded"
    return results


def ground_labeled_fields(
    text_content: str,
    knowledge: KnowledgeBase,
    source_name: str = SOURCE_NAME,
) -> dict[str, str]:
    """Text-based (not DOM-based) grounding for fields whose only real
    evidence is the source's own visible label text -- no icon, no
    tooltip involved (e.g. `net_earnings_per_sale`, labeled verbatim
    'Net earnings/sale' right next to its value). Deliberately
    `predicate="labeled_as"`, never `"means"` -- this asserts only the
    real, verbatim label the source displays, never a claim about what
    the field represents, how it's computed, or what it includes (no
    evidence exists for any of that, so none is asserted). Works directly
    off `text_content` -- no DOM/tooltip access needed, so this can run
    even on the very first, DOM-less cycle of `run_discovery()`.
    Idempotent, same discipline as `ground_marketplace_fields()`."""
    results: dict[str, str] = {}
    for field_name, label in LABELED_FIELDS.items():
        if label not in text_content:
            continue
        subject_id = f"{source_name}:field:{field_name}"
        existing = knowledge.claims(subject_id=subject_id, predicate="labeled_as")
        if existing:
            results[field_name] = "already_grounded"
            continue

        finding = Finding(
            source=source_name,
            category="marketplace_field_semantics",
            description=f"{source_name} labels the field {field_name!r} as {label!r}",
            evidence=label,
            provider=source_name,
            # evidence_role (2026-08-17, ONE BRAIN Evidence Role Gate):
            # "direct_assertion" -- same reasoning as ground_marketplace_
            # fields() above: this label text is source_name's own
            # first-party UI copy about its own field.
            evidence_role="direct_assertion",
        )
        knowledge.save_finding(finding)

        claim = Claim(
            subject_id=subject_id,
            predicate="labeled_as",
            object_value=label,
            evidence_finding_ids=[finding.id],
            claim_type="observation",
            source="manual",
        )
        knowledge.save_claim(claim)
        results[field_name] = "newly_grounded"
    return results


def field_grounding(field_name: str, knowledge: KnowledgeBase, source_name: str = SOURCE_NAME) -> Claim | None:
    """Read-only lookup: the real, current (non-superseded) grounding
    Claim for a field, if one exists -- `None` (never fabricated) when
    the field's meaning has never been grounded from real evidence. This
    is the honest UNKNOWN case (e.g. `observed_date_raw`, `price`,
    `vendor` -- no real tooltip was ever found for these icons).

    Matches ANY real grounding predicate (`"means"` from a tooltip, or
    `"labeled_as"` from a visible-label-only fact) -- the caller
    distinguishes which evidence strength it got by reading the returned
    Claim's own `.predicate`, never by guessing from context."""
    subject_id = f"{source_name}:field:{field_name}"
    matches = [c for c in knowledge.claims(subject_id=subject_id) if c.superseded_by_id is None]
    return matches[0] if matches else None
