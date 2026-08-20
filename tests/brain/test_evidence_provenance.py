from atlas.brain.evidence_provenance import evidence_origin, independent_source_count, normalize_url
from atlas.brain.models import Finding


def _finding(**overrides) -> Finding:
    defaults = dict(source="test", category="affiliate", description="d", evidence="", subject="prostadine")
    defaults.update(overrides)
    return Finding(**defaults)


# --- normalize_url() ---------------------------------------------------------


def test_normalize_url_strips_known_tracking_params():
    a = normalize_url("https://example.com/prostadine?utm_source=newsletter&id=1")
    b = normalize_url("https://example.com/prostadine?id=1")
    assert a == b


def test_normalize_url_strips_fragment():
    assert normalize_url("https://example.com/a#section") == normalize_url("https://example.com/a")


def test_normalize_url_lowercases_host():
    assert normalize_url("https://Example.COM/a") == normalize_url("https://example.com/a")


def test_normalize_url_strips_trailing_slash():
    assert normalize_url("https://example.com/a/") == normalize_url("https://example.com/a")


def test_normalize_url_returns_empty_for_non_url():
    assert normalize_url("local screen capture") == ""
    assert normalize_url("") == ""


def test_normalize_url_keeps_genuinely_different_pages_distinct():
    assert normalize_url("https://example.com/a") != normalize_url("https://example.com/b")


# --- evidence_origin() -------------------------------------------------------


def test_evidence_origin_derives_from_evidence_never_from_source():
    finding = _finding(source="marketplace_catalog", evidence="https://example.com/prostadine")
    assert evidence_origin(finding) == normalize_url("https://example.com/prostadine")


def test_evidence_origin_unknown_for_non_url_evidence():
    finding = _finding(source="screen_observation", evidence="local screen capture")
    assert evidence_origin(finding) == ""


# --- independent_source_count() ----------------------------------------------


def test_c_same_url_with_tracking_params_counts_once():
    a = _finding(evidence="https://example.com/prostadine?utm_source=x", evidence_role="direct_assertion")
    b = _finding(evidence="https://example.com/prostadine", evidence_role="direct_assertion")
    assert independent_source_count([a, b]) == 1


def test_d_two_sensors_same_real_world_origin_counts_once():
    a = _finding(source="marketplace_catalog", evidence="https://example.com/prostadine", evidence_role="direct_assertion")
    b = _finding(source="browser", evidence="https://example.com/prostadine", evidence_role="direct_assertion")
    assert independent_source_count([a, b]) == 1


def test_e_same_known_claimant_across_two_origins_not_blindly_independent():
    a = _finding(claimant="vendorX", evidence="https://vendorx.com/prostadine")
    b = _finding(claimant="vendorX", evidence="https://affiliate-network.com/prostadine-promo")
    assert independent_source_count([a, b]) == 1


def test_f_different_claimant_and_different_origin_reaches_two():
    a = _finding(claimant="vendorX", evidence="https://vendorx.com/prostadine")
    b = _finding(claimant="independent-reviewer", evidence="https://review-site.com/prostadine")
    assert independent_source_count([a, b]) == 2


def test_g_unknown_provenance_counts_zero_toward_independence():
    a = _finding(claimant="", evidence="")  # fully unknown -- no claimant, no parseable origin
    assert independent_source_count([a]) == 0


def test_transitive_grouping_across_three_findings():
    """A~B via shared claimant, B~C via shared origin -> all three in one
    real-world-source group, even with no direct A~C link."""
    a = _finding(claimant="vendorX", evidence="https://vendorx.com/a")
    b = _finding(claimant="vendorX", evidence="https://vendorx.com/b")  # shares claimant with A
    c = _finding(claimant="someone-else", evidence="https://vendorx.com/b")  # shares origin with B
    assert independent_source_count([a, b, c]) == 1


def test_mixed_known_and_unknown_findings():
    known = _finding(claimant="reviewer", evidence="https://review-site.com/a")
    unknown = _finding(claimant="", evidence="")
    assert independent_source_count([known, unknown]) == 1  # the unknown one simply doesn't count


def test_empty_list_returns_zero():
    assert independent_source_count([]) == 0


# --- H: legacy Finding without claimant loads normally -----------------------


def test_h_legacy_finding_without_claimant_loads_normally(tmp_path):
    from atlas.brain.knowledge import KnowledgeBase

    path = tmp_path / "knowledge.json"
    # simulate a real, pre-existing Finding record saved before `claimant`
    # existed -- the exact raw JSON shape a real, older knowledge.json
    # would contain, with no "claimant" key at all.
    import json

    path.write_text(json.dumps({
        "findings": {
            "finding-legacy-1": {
                "source": "research", "category": "affiliate", "description": "d",
                "evidence": "https://example.com/legacy", "provider": "", "subject": "LegacyProduct",
                "market": "", "id": "finding-legacy-1", "created_at": "2026-08-01T00:00:00+00:00",
            }
        }
    }))

    knowledge = KnowledgeBase(path)
    findings = knowledge.findings()

    assert len(findings) == 1
    assert findings[0].claimant == ""  # defaults correctly, does not raise
    assert findings[0].evidence_role == ""  # defaults correctly, does not raise
    # ONE BRAIN Evidence Role Gate (2026-08-17): a genuinely legacy record
    # (pre-claimant AND pre-role) is honestly fully UNKNOWN -- claimant=""
    # and evidence_role="" together mean origin alone must NOT count it,
    # the same fail-closed default every other undated pre-field record
    # gets. This superseded the original ONE BRAIN Provenance
    # Implementation-era assertion (== 1, "still counts via
    # evidence_origin()") -- that was correct at the time (before the
    # Evidence Role Gate existed), and is now the exact case the Gate was
    # built to close: legacy unknowns must fail closed, never be
    # blindly backfilled to "trusted."
    assert independent_source_count(findings) == 0


# --- M: restart preserves claimant/evidence and the same independent count ---


def test_m_restart_preserves_claimant_and_the_same_independent_count(tmp_path):
    from atlas.brain.knowledge import KnowledgeBase

    path = tmp_path / "knowledge.json"
    kb1 = KnowledgeBase(path)
    kb1.save_finding(_finding(claimant="vendorX", evidence="https://vendorx.com/a", subject="Prostadine"))
    kb1.save_finding(_finding(claimant="vendorX", evidence="https://affiliate.example.com/promo", subject="Prostadine"))  # same claimant, different origin
    before = independent_source_count(kb1.findings(subject="Prostadine"))
    del kb1

    kb2 = KnowledgeBase(path)
    after = independent_source_count(kb2.findings(subject="Prostadine"))

    assert before == after == 1
    reloaded = kb2.findings(subject="Prostadine")
    assert all(f.claimant == "vendorX" for f in reloaded)


# --- Evidence Role Gate (2026-08-17, ONE BRAIN Evidence Role Gate) -----------


def test_quote_relay_negative_three_relays_of_the_same_unknown_claimant_count_zero():
    """The core danger case this round closes: three different origins,
    all relay_or_quote, all claimant unknown -- must NOT satisfy
    MIN_INDEPENDENT_SOURCES. Sensor/URL diversity alone is not proof of
    independence."""
    findings = [
        _finding(evidence=f"https://site-{i}.example.com/prostadine", claimant="", evidence_role="relay_or_quote")
        for i in ("a", "b", "c")
    ]
    assert independent_source_count(findings) == 0


def test_unknown_negative_different_urls_different_sensors_unknown_role_count_zero():
    findings = [
        _finding(source="browser_research", evidence="https://a.example.com/x", claimant="", evidence_role=""),
        _finding(source="knowledge_source_research", evidence="https://b.example.com/y", claimant="", evidence_role=""),
        _finding(source="research_discovery", evidence="https://c.example.com/z", claimant="", evidence_role=""),
    ]
    assert independent_source_count(findings) == 0


def test_known_claimant_relay_findings_still_group_correctly_by_claimant():
    """Role gating must never destroy correct claimant-based grouping --
    only the origin-only FALLBACK is gated."""
    a = _finding(evidence="https://site-a.example.com/x", claimant="vendorX", evidence_role="relay_or_quote")
    b = _finding(evidence="https://site-b.example.com/y", claimant="vendorX", evidence_role="relay_or_quote")
    assert independent_source_count([a, b]) == 1


def test_known_different_claimants_still_reach_two_independent_groups():
    a = _finding(evidence="https://site-a.example.com/x", claimant="vendorX", evidence_role="relay_or_quote")
    b = _finding(evidence="https://site-b.example.com/y", claimant="independent-reviewer", evidence_role="direct_assertion")
    assert independent_source_count([a, b]) == 2


def test_primary_observation_counts_via_origin_with_no_external_claimant():
    """A structurally known primary observation must remain usable even
    without an external claimant -- claimant='' must not make it
    disappear when role proves there was never a claimant to begin
    with."""
    finding = _finding(evidence="https://example.com/observed-page", claimant="", evidence_role="primary_observation")
    assert independent_source_count([finding]) == 1


def test_direct_assertion_counts_via_origin_when_claimant_unknown():
    finding = _finding(evidence="https://digistore24.com/marketplace/field-semantics", claimant="", evidence_role="direct_assertion")
    assert independent_source_count([finding]) == 1


def test_aggregated_report_contributes_exactly_one_source_never_more():
    """A Marketplace-shaped mixed Finding -- claimant='', role=
    'aggregated_report', a real origin -- must contribute exactly one
    independent source, and multiple propositions bundled inside it must
    never inflate that beyond one (Finding-level granularity, not
    proposition-level, already caps this structurally)."""
    finding = _finding(
        source="marketplace_catalog",
        evidence="https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all/detail/12345",
        claimant="",
        evidence_role="aggregated_report",
    )
    assert independent_source_count([finding]) == 1
    # a second, distinct real aggregated_report artifact is a genuinely
    # different real observation event -- correctly reaches two.
    second = _finding(
        source="marketplace_catalog",
        evidence="https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all/detail/67890",
        claimant="",
        evidence_role="aggregated_report",
    )
    assert independent_source_count([finding, second]) == 2


# --- Adversarial battery (2026-08-17) ----------------------------------------


def test_adversarial_same_origin_relay_and_unknown_still_merge_via_origin_when_role_allows():
    """Same origin, one Finding tagged aggregated_report and one tagged
    "" (unknown) -- both share a known origin once one of them is
    eligible; union-find still merges them into one real group (the
    origin identifier is the same real page either way once eligible)."""
    a = _finding(evidence="https://vendor.example.com/prostadine", claimant="", evidence_role="aggregated_report")
    b = _finding(evidence="https://vendor.example.com/prostadine", claimant="", evidence_role="")
    # b alone (role="", claimant="") would be ineligible and ordinarily
    # contribute 0 -- but the SAME real origin is also carried by `a`,
    # which IS eligible, so the shared origin still merges them into one
    # real-world-source group, exactly as it should for the same real page.
    assert independent_source_count([a, b]) == 1


def test_adversarial_tracking_param_variant_of_a_relay_url_still_excluded():
    a = _finding(evidence="https://site-a.example.com/prostadine?utm_source=x", claimant="", evidence_role="relay_or_quote")
    b = _finding(evidence="https://site-a.example.com/prostadine", claimant="", evidence_role="relay_or_quote")
    assert independent_source_count([a, b]) == 0


def test_adversarial_relay_chain_a_to_b_to_c_all_excluded_without_claimant():
    """A relay chain (A quotes vendor, B quotes A, C syndicates B) -- all
    three artifacts are role=relay_or_quote with claimant unknown; none
    should count, regardless of how many hops or how many distinct real
    domains are involved."""
    chain = [
        _finding(evidence="https://a.example.com/prostadine", claimant="", evidence_role="relay_or_quote"),
        _finding(evidence="https://b.example.com/prostadine", claimant="", evidence_role="relay_or_quote"),
        _finding(evidence="https://c.example.com/prostadine", claimant="", evidence_role="relay_or_quote"),
    ]
    assert independent_source_count(chain) == 0


def test_adversarial_known_role_but_missing_origin_still_falls_back_honestly():
    """role=direct_assertion but evidence isn't a parseable URL (e.g. a
    local capture) -- no origin identifier exists to gate in the first
    place; with claimant also unknown this Finding is fully UNKNOWN,
    contributing zero, exactly like any other unparseable-evidence case."""
    finding = _finding(evidence="local screen capture", claimant="", evidence_role="direct_assertion")
    assert independent_source_count([finding]) == 0


def test_adversarial_old_finding_without_evidence_role_field_loads_and_behaves_as_unknown(tmp_path):
    import json

    from atlas.brain.knowledge import KnowledgeBase

    path = tmp_path / "knowledge.json"
    path.write_text(json.dumps({
        "findings": {
            "finding-legacy-2": {
                "source": "research", "category": "affiliate", "description": "d",
                "evidence": "https://example.com/legacy-relay", "provider": "", "subject": "LegacyProduct",
                "market": "", "claimant": "", "id": "finding-legacy-2", "created_at": "2026-08-01T00:00:00+00:00",
            }
        }
    }))

    knowledge = KnowledgeBase(path)
    findings = knowledge.findings()

    assert len(findings) == 1
    assert findings[0].evidence_role == ""  # defaults correctly, does not raise
    # a lone legacy Finding, evidence_role="", claimant="" -- honestly
    # UNKNOWN, contributes zero, the same conservative fail-closed default
    # every other undated pre-field record already gets elsewhere.
    assert independent_source_count(findings) == 0


# --- Restart / persistence ----------------------------------------------------


def test_restart_preserves_evidence_role_and_the_same_independent_count(tmp_path):
    from atlas.brain.knowledge import KnowledgeBase

    path = tmp_path / "knowledge.json"
    kb1 = KnowledgeBase(path)
    kb1.save_finding(_finding(claimant="", evidence="https://a.example.com/x", evidence_role="relay_or_quote", subject="Prostadine"))
    kb1.save_finding(_finding(claimant="", evidence="https://digistore24.com/listing/1", evidence_role="aggregated_report", subject="Prostadine"))
    kb1.save_finding(_finding(claimant="", evidence="https://reviewer.example.com/review", evidence_role="direct_assertion", subject="Prostadine"))
    before = independent_source_count(kb1.findings(subject="Prostadine"))
    del kb1

    kb2 = KnowledgeBase(path)
    reloaded = kb2.findings(subject="Prostadine")
    after = independent_source_count(reloaded)

    assert before == after == 2  # aggregated_report + direct_assertion count; relay_or_quote does not
    roles = {f.evidence_role for f in reloaded}
    assert roles == {"relay_or_quote", "aggregated_report", "direct_assertion"}


# --- Section 12 end-to-end proofs (2026-08-17, ONE BRAIN Web Evidence Role Classification) ---


def test_section12_1_three_relay_findings_unknown_claimant_count_zero():
    findings = [
        _finding(evidence=f"https://site-{i}.example.com/prostadine", claimant="", evidence_role="relay_or_quote")
        for i in ("a", "b", "c")
    ]
    assert independent_source_count(findings) == 0


def test_section12_2_one_direct_assertion_plus_one_relay_quoting_it_counts_one():
    vendor_direct = _finding(evidence="https://vendorx.com/prostadine", claimant="", evidence_role="direct_assertion")
    relay_quoting_vendor = _finding(evidence="https://affiliate-article.example.com/prostadine", claimant="", evidence_role="relay_or_quote")
    assert independent_source_count([vendor_direct, relay_quoting_vendor]) == 1


def test_section12_3_vendor_direct_plus_independent_reviewer_direct_counts_two():
    vendor_direct = _finding(evidence="https://vendorx.com/prostadine", claimant="", evidence_role="direct_assertion")
    reviewer_direct = _finding(evidence="https://independent-review.example.com/prostadine", claimant="", evidence_role="direct_assertion")
    assert independent_source_count([vendor_direct, reviewer_direct]) == 2


def test_section12_4_aggregated_plus_direct_plus_relay_plus_direct_counts_three():
    aggregated_marketplace = _finding(evidence="https://www.digistore24-app.com/marketplace/detail/1", claimant="", evidence_role="aggregated_report")
    vendor_direct = _finding(evidence="https://vendorx.com/prostadine", claimant="", evidence_role="direct_assertion")
    relay_article = _finding(evidence="https://affiliate-article.example.com/prostadine", claimant="", evidence_role="relay_or_quote")
    reviewer_direct = _finding(evidence="https://independent-review.example.com/prostadine", claimant="", evidence_role="direct_assertion")
    findings = [aggregated_marketplace, vendor_direct, relay_article, reviewer_direct]
    assert independent_source_count(findings) == 3
