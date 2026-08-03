import pytest

from atlas.assets.publishing_gateway.models import PublishPackage
from atlas.assets.publishing_gateway.store import PublishingQueueStore
from atlas.brain.ledger import Ledger
from atlas.brain.memory import BrainMemory
from atlas.cli import main


def test_bare_invocation_launches_the_full_screen_app_not_an_argparse_error(monkeypatch):
    calls = []
    monkeypatch.setattr("atlas.cli.run_app", lambda: calls.append(True))

    exit_code = main([])

    assert calls == [True]
    assert exit_code == 0


def test_manual_task_breakdown_and_daily_cycle(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    main(["brain", "goal", "add", "Grow revenue", "--priority", "1"])
    goal_id = capsys.readouterr().out.strip().split("\t")[0]

    main(["brain", "task", "add", goal_id, "Identify prospects", "--category", "analyze_revenue", "--reversible"])
    main(
        [
            "brain",
            "task",
            "add",
            goal_id,
            "Launch a paid campaign",
            "--category",
            "launch_campaign",
            "--amount",
            "500",
        ]
    )
    capsys.readouterr()

    main(["brain", "tick"])
    tick_out = capsys.readouterr().out
    assert "tick complete" in tick_out

    main(["brain", "approvals"])
    approvals_out = capsys.readouterr().out
    assert "launch_campaign" in approvals_out

    main(["brain", "status"])
    status_out = capsys.readouterr().out
    assert "Identify prospects" in status_out
    assert "delegated" in status_out or "done" in status_out

    main(["brain", "kpi", "record", "revenue", "0"])
    capsys.readouterr()

    main(["brain", "report", "--period", "daily"])
    report_out = capsys.readouterr().out
    assert "executive report" in report_out


def test_task_add_rejects_unknown_goal(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    exit_code = main(["brain", "task", "add", "does-not-exist", "x"])
    assert exit_code == 1
    assert "no such goal" in capsys.readouterr().err


def test_console_shows_goals_approvals_departments_and_kpis(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    main(["brain", "goal", "add", "Grow affiliate revenue", "--priority", "1"])
    goal_id = capsys.readouterr().out.strip().split("\t")[0]
    main(["brain", "task", "add", goal_id, "Do something", "--category", "general", "--reversible"])
    capsys.readouterr()
    main(["brain", "tick"])
    capsys.readouterr()
    main(["brain", "kpi", "record", "revenue", "0"])
    capsys.readouterr()

    main(["console"])
    out = capsys.readouterr().out

    assert "=== ATLAS Console ===" in out
    assert "Grow affiliate revenue" in out
    assert "Departments:" in out
    assert "recruitment_workforce" in out
    assert "KPIs:" in out
    assert "revenue = 0.0" in out


def test_goal_add_stores_horizon_and_founder_estimate(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    main(
        [
            "brain",
            "goal",
            "add",
            "Long-term bet",
            "--horizon",
            "long",
            "--expected-revenue",
            "5000",
            "--scalability",
            "0.8",
        ]
    )
    out = capsys.readouterr().out
    assert "horizon=long" in out
    goal_id = out.strip().split("\t")[0]

    goal = BrainMemory().get_goal(goal_id)
    assert goal.horizon == "long"
    assert goal.founder_estimate == {"expected_revenue": 5000.0, "scalability": 0.8}


def test_goal_add_defaults_to_short_horizon_and_empty_estimate(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    main(["brain", "goal", "add", "Plain goal"])
    out = capsys.readouterr().out
    goal_id = out.strip().split("\t")[0]

    goal = BrainMemory().get_goal(goal_id)
    assert goal.horizon == "short"
    assert goal.founder_estimate == {}


def test_goal_list_shows_horizon(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["brain", "goal", "add", "Test goal", "--horizon", "long"])
    capsys.readouterr()

    main(["brain", "goal", "list"])
    out = capsys.readouterr().out
    assert "horizon=long" in out


def test_report_shows_reallocations_section(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["brain", "goal", "add", "strong", "--expected-revenue", "1000"])
    capsys.readouterr()
    main(["brain", "goal", "add", "weak", "--expected-revenue", "100"])
    capsys.readouterr()

    main(["brain", "report", "--period", "daily"])
    out = capsys.readouterr().out
    assert "Reallocations:" in out
    assert "priority 3->1" in out or "priority 3->2" in out


def test_opportunities_ranks_categories_by_confidence_descending(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    # affiliate: 3 real sourced findings (source_corroboration + recency both
    # available). ugc: 1 unsourced finding (source_corroboration stays None,
    # since there's no evidence) — fewer factors available, so it must rank
    # below affiliate even though a bare recency score alone could tie.
    for i in range(3):
        main(["brain", "finding", "add", "research", "affiliate", f"real affiliate signal {i}", "--evidence", f"https://example.com/{i}"])
        capsys.readouterr()
    main(["brain", "finding", "add", "research", "ugc", "an idea with no source yet"])
    capsys.readouterr()

    main(["brain", "opportunities"])
    out = capsys.readouterr().out
    lines = [line for line in out.strip().splitlines() if line]

    assert lines[0].startswith("affiliate\t")
    assert "factors=2/6" in lines[0]
    assert lines[1].startswith("ugc\t")
    assert "factors=1/6" in lines[1]


def test_decisions_list_is_empty_before_any_tick(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    main(["brain", "decisions", "list"])
    out = capsys.readouterr().out

    assert out.strip() == ""


def test_decisions_show_reports_no_decision_on_record(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    main(["brain", "decisions", "show", "affiliate"])
    out = capsys.readouterr().out

    assert "no decision on record for 'affiliate'" in out


def test_decisions_list_and_show_after_a_real_tick(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["brain", "finding", "add", "research", "digital_product", "signal 1", "--evidence", "https://example.com/1"])
    capsys.readouterr()
    main(["brain", "finding", "add", "research", "digital_product", "signal 2", "--evidence", "https://example.com/2"])
    capsys.readouterr()

    main(["brain", "tick"])
    capsys.readouterr()

    main(["brain", "decisions", "list"])
    list_out = capsys.readouterr().out
    assert "digital_product" in list_out
    assert "invest" in list_out

    main(["brain", "decisions", "show", "digital_product"])
    show_out = capsys.readouterr().out
    assert "Verdict: invest" in show_out
    assert "Evidence cited (2 finding(s))" in show_out
    assert "Reasoning:" in show_out
    assert "Risks:" in show_out
    assert "Goal created:" in show_out
    assert "(none — first decision for this category)" in show_out
    assert "Chosen provider: (none)" in show_out  # digital_product has a channel but no registered provider yet


def test_decisions_show_names_the_real_chosen_provider_for_affiliate(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["brain", "finding", "add", "research", "affiliate", "signal 1", "--evidence", "https://example.com/1"])
    capsys.readouterr()
    main(["brain", "finding", "add", "research", "affiliate", "signal 2", "--evidence", "https://example.com/2"])
    capsys.readouterr()

    main(["brain", "tick"])
    capsys.readouterr()

    main(["brain", "decisions", "show", "affiliate"])
    show_out = capsys.readouterr().out
    assert "Chosen provider: digistore24" in show_out


def test_opportunities_explain_shows_evidence_roi_risks_and_rank_reason(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["brain", "finding", "add", "research", "affiliate", "a real signal", "--evidence", "https://example.com"])
    capsys.readouterr()

    main(["brain", "opportunities", "--explain"])
    out = capsys.readouterr().out

    assert "Evidence: 1 finding(s)" in out
    assert "Expected ROI: not yet measured" in out
    assert "Probability of success: not estimable yet (no track record)" in out
    assert "Risks:" in out
    assert "Why ranked here: ranked #1" in out


def test_opportunities_with_no_findings_prints_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    main(["brain", "opportunities"])
    out = capsys.readouterr().out

    assert out.strip() == ""


def test_finding_add_and_list_round_trip(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(
        [
            "brain",
            "finding",
            "add",
            "research",
            "youtube",
            "Short-form cooking content has low competition in this niche",
            "--evidence",
            "https://example.com/real-source",
        ]
    )
    add_out = capsys.readouterr().out
    assert "youtube" in add_out

    main(["brain", "finding", "list"])
    list_out = capsys.readouterr().out
    assert "youtube" in list_out
    assert "research" in list_out
    assert "https://example.com/real-source" in list_out


def test_finding_add_defaults_evidence_to_empty(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["brain", "finding", "add", "founder", "digital_product", "An idea with no source yet"])
    capsys.readouterr()

    main(["brain", "finding", "list"])
    out = capsys.readouterr().out
    assert "An idea with no source yet" in out


def test_finding_add_accepts_a_provider_scoped_finding(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(
        [
            "brain", "finding", "add", "research", "affiliate", "Digistore24 has a real X% commission on this product",
            "--evidence", "https://example.com/real-source", "--provider", "digistore24",
        ]
    )
    add_out = capsys.readouterr().out
    assert "digistore24" in add_out

    main(["brain", "finding", "list"])
    list_out = capsys.readouterr().out
    assert "digistore24" in list_out


def test_finding_add_without_provider_is_category_general(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["brain", "finding", "add", "research", "affiliate", "AI-tool affiliate programs pay well generally"])
    capsys.readouterr()

    main(["brain", "finding", "list"])
    out = capsys.readouterr().out
    assert "(category-general)" in out


def test_affiliate_product_add_creates_a_real_discovered_opportunity(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["brain", "goal", "add", "First real affiliate income"])
    goal_id = capsys.readouterr().out.strip().split("\t")[0]

    exit_code = main(
        [
            "affiliate", "product", "add",
            "--goal-id", goal_id,
            "--name", "Real Program",
            "--description", "A real, signed-up affiliate program",
            "--category", "software",
            "--commission", "30",
            "--link", "https://www.digistore24.com/redir/123456/myaffid/",
            "--provider", "digistore24",
        ]
    )
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "ranked" in out
    assert "Real Program" in out
    assert goal_id in out


def test_publishing_mark_published_transitions_queued_to_published(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    store = PublishingQueueStore()
    package = PublishPackage(
        platform="TikTok", title="t", description="d", cta="c",
        status="QUEUED", goal_id="goal-a", tracking_link="https://real-network.example/track/abc123",
    )
    store.save_package(package)

    exit_code = main(["publishing", "mark-published", package.id])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "PUBLISHED" in out
    assert store.get_package(package.id).status == "PUBLISHED"


def test_affiliate_revenue_record_accumulates_against_the_packages_goal(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    store = PublishingQueueStore()
    package = PublishPackage(platform="TikTok", title="t", description="d", cta="c", status="PUBLISHED", goal_id="goal-a")
    store.save_package(package)

    main(["affiliate", "revenue", "record", package.id, "150", "--cost", "40"])
    capsys.readouterr()
    main(["affiliate", "revenue", "record", package.id, "50"])
    capsys.readouterr()

    main(["brain", "kpi", "list"])
    out = capsys.readouterr().out
    assert "revenue_goal-a\t200.0" in out
    assert "cost_goal-a\t40.0" in out


def test_affiliate_revenue_record_rejects_a_package_with_no_goal_id(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    store = PublishingQueueStore()
    package = PublishPackage(platform="TikTok", title="t", description="d", cta="c", status="PUBLISHED", goal_id=None)
    store.save_package(package)

    exit_code = main(["affiliate", "revenue", "record", package.id, "150"])

    assert exit_code == 1
    assert "no goal_id" in capsys.readouterr().err


def test_affiliate_cost_record_accumulates_against_the_packages_goal(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    store = PublishingQueueStore()
    package = PublishPackage(platform="TikTok", title="t", description="d", cta="c", status="PUBLISHED", goal_id="goal-a")
    store.save_package(package)

    main(["affiliate", "cost", "record", package.id, "40"])
    capsys.readouterr()
    main(["affiliate", "cost", "record", package.id, "10"])
    capsys.readouterr()

    main(["brain", "kpi", "list"])
    out = capsys.readouterr().out
    assert "cost_goal-a\t50.0" in out
    assert "revenue_goal-a" not in out


def test_affiliate_cost_record_rejects_a_package_with_no_goal_id(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    store = PublishingQueueStore()
    package = PublishPackage(platform="TikTok", title="t", description="d", cta="c", status="PUBLISHED", goal_id=None)
    store.save_package(package)

    exit_code = main(["affiliate", "cost", "record", package.id, "40"])

    assert exit_code == 1
    assert "no goal_id" in capsys.readouterr().err


def test_affiliate_fee_record_accumulates_onto_cost(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    store = PublishingQueueStore()
    package = PublishPackage(platform="TikTok", title="t", description="d", cta="c", status="PUBLISHED", goal_id="goal-a")
    store.save_package(package)

    main(["affiliate", "fee", "record", package.id, "12", "--category", "platform_fee"])
    capsys.readouterr()

    main(["brain", "kpi", "list"])
    out = capsys.readouterr().out
    assert "cost_goal-a\t12.0" in out


def test_affiliate_settlement_record_accumulates_a_separate_series(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    store = PublishingQueueStore()
    package = PublishPackage(platform="TikTok", title="t", description="d", cta="c", status="PUBLISHED", goal_id="goal-a")
    store.save_package(package)

    main(["affiliate", "revenue", "record", package.id, "150"])
    capsys.readouterr()
    main(["affiliate", "settlement", "record", package.id, "150", "--evidence", "bank statement"])
    capsys.readouterr()

    main(["brain", "kpi", "list"])
    out = capsys.readouterr().out
    assert "revenue_goal-a\t150.0" in out
    assert "settled_goal-a\t150.0" in out


def test_affiliate_refund_record_decrements_claimed_revenue(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    store = PublishingQueueStore()
    package = PublishPackage(platform="TikTok", title="t", description="d", cta="c", status="PUBLISHED", goal_id="goal-a")
    store.save_package(package)

    main(["affiliate", "revenue", "record", package.id, "150"])
    capsys.readouterr()
    main(["affiliate", "refund", "record", package.id, "50"])
    capsys.readouterr()

    main(["brain", "kpi", "list"])
    out = capsys.readouterr().out
    assert "revenue_goal-a\t100.0" in out


def test_affiliate_revenue_record_writes_a_ledger_entry(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    store = PublishingQueueStore()
    package = PublishPackage(platform="TikTok", title="t", description="d", cta="c", status="PUBLISHED", goal_id="goal-a")
    store.save_package(package)

    main(["affiliate", "revenue", "record", package.id, "150", "--provider", "digistore24"])
    capsys.readouterr()

    entries = Ledger().entries_for_goal("goal-a")
    assert len(entries) == 1
    assert entries[0].kind == "revenue_claimed"
    assert entries[0].provider == "digistore24"


def test_influencer_create_and_list(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        ["influencer", "create", "--name", "Mira", "--niche", "fitness", "--personality", "energetic",
         "--category", "affiliate", "--category", "digital_product"]
    )
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "Mira" in out
    assert "affiliate,digital_product" in out

    main(["influencer", "list"])
    list_out = capsys.readouterr().out
    assert "Mira" in list_out
    assert "active" in list_out


def test_influencer_show_reflects_asset_and_platform_attachments(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["influencer", "create", "--name", "Kai", "--niche", "personal_finance"])
    influencer_id = capsys.readouterr().out.strip().split("\t")[0]

    main(["influencer", "asset", "attach", influencer_id, "--type", "script", "--reference", "https://example.com/s1.txt"])
    capsys.readouterr()
    main(["influencer", "platform", "add", influencer_id, "--platform", "TikTok", "--handle", "@kai.money"])
    capsys.readouterr()

    main(["influencer", "show", influencer_id])
    out = capsys.readouterr().out

    assert "Kai" in out
    assert "https://example.com/s1.txt" in out
    assert "@kai.money" in out


def test_influencer_metric_record_and_rank(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["influencer", "create", "--name", "Mira", "--category", "affiliate"])
    influencer_id = capsys.readouterr().out.strip().split("\t")[0]

    main(["influencer", "metric", "record", influencer_id, "followers", "5000"])
    capsys.readouterr()

    exit_code = main(["influencer", "rank", "affiliate"])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert influencer_id in out
    assert "1/3 evidence factors" in out


def test_influencer_rank_reports_no_match_for_an_untagged_category(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["influencer", "create", "--name", "Mira", "--category", "affiliate"])
    capsys.readouterr()

    main(["influencer", "rank", "youtube"])
    out = capsys.readouterr().out

    assert "no influencer tagged" in out


def test_influencer_template_add_rejects_an_unknown_kind(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["influencer", "create", "--name", "Mira"])
    influencer_id = capsys.readouterr().out.strip().split("\t")[0]

    with pytest.raises(SystemExit):
        main(["influencer", "template", "add", influencer_id, "--kind", "meme", "--name", "n", "--content", "c"])


def test_influencer_template_add_and_list(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["influencer", "create", "--name", "Mira"])
    influencer_id = capsys.readouterr().out.strip().split("\t")[0]

    main(["influencer", "template", "add", influencer_id, "--kind", "hook", "--name", "curiosity", "--content", "Nobody tells you this about {product_name}...", "--tag", "fitness"])
    capsys.readouterr()

    main(["influencer", "template", "list", influencer_id, "--kind", "hook"])
    out = capsys.readouterr().out

    assert "curiosity" in out
    assert "{product_name}" in out


def test_campaign_create_and_produce_end_to_end(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["influencer", "create", "--name", "Mira", "--category", "affiliate"])
    influencer_id = capsys.readouterr().out.strip().split("\t")[0]

    main(["influencer", "template", "add", influencer_id, "--kind", "hook", "--name", "h1", "--content", "Nobody tells you this about {product_name}..."])
    capsys.readouterr()
    main(["influencer", "template", "add", influencer_id, "--kind", "cta", "--name", "c1", "--content", "Try {product_name} today."])
    capsys.readouterr()

    exit_code = main(
        ["campaign", "create", "--objective", "grow affiliate revenue", "--category", "affiliate", "--product", "KetoDNA",
         "--influencer", influencer_id, "--goal-id", "goal-a", "--revenue-goal", "5000", "--budget", "500"]
    )
    create_out = capsys.readouterr().out
    campaign_id = create_out.strip().split("\t")[0]

    assert exit_code == 0
    assert "KetoDNA" in create_out

    exit_code = main(["campaign", "produce", campaign_id])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "Nobody tells you this about KetoDNA" in out
    assert "Try KetoDNA today" in out
    assert "'script_template'" in out  # a real, honest gap surfaced in missing_kinds


def test_campaign_create_rejects_an_unknown_influencer(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        ["campaign", "create", "--objective", "grow affiliate revenue", "--category", "affiliate", "--product", "KetoDNA",
         "--influencer", "does-not-exist"]
    )

    assert exit_code == 1
    assert "unknown influencer" in capsys.readouterr().err


def test_campaign_show_and_refresh_confidence(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["influencer", "create", "--name", "Mira", "--category", "affiliate"])
    influencer_id = capsys.readouterr().out.strip().split("\t")[0]
    main(
        ["campaign", "create", "--objective", "grow affiliate revenue", "--category", "affiliate", "--product", "KetoDNA",
         "--influencer", influencer_id, "--target-audience", "keto beginners"]
    )
    campaign_id = capsys.readouterr().out.strip().split("\t")[0]

    main(["campaign", "show", campaign_id])
    show_out = capsys.readouterr().out
    assert "keto beginners" in show_out
    assert influencer_id in show_out

    main(["brain", "finding", "add", "research", "affiliate", "independent source"])
    capsys.readouterr()
    exit_code = main(["campaign", "refresh-confidence", campaign_id])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert campaign_id in out


def test_campaign_list_shows_every_campaign(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["influencer", "create", "--name", "Mira", "--category", "affiliate"])
    influencer_id = capsys.readouterr().out.strip().split("\t")[0]
    main(["campaign", "create", "--objective", "a", "--category", "affiliate", "--product", "KetoDNA", "--influencer", influencer_id])
    capsys.readouterr()
    main(["campaign", "create", "--objective", "b", "--category", "affiliate", "--product", "OtherOffer", "--influencer", influencer_id])
    capsys.readouterr()

    main(["campaign", "list"])
    out = capsys.readouterr().out

    assert "KetoDNA" in out
    assert "OtherOffer" in out


def test_campaign_execution_full_lifecycle_via_cli(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["brain", "goal", "add", "grow affiliate revenue"])
    goal_id = capsys.readouterr().out.strip().split("\t")[0]
    main(["influencer", "create", "--name", "Mira", "--category", "affiliate"])
    influencer_id = capsys.readouterr().out.strip().split("\t")[0]
    main(["influencer", "template", "add", influencer_id, "--kind", "hook", "--name", "h1", "--content", "Nobody tells you this about {product_name}..."])
    capsys.readouterr()
    main(["influencer", "template", "add", influencer_id, "--kind", "cta", "--name", "c1", "--content", "Try {product_name} today."])
    capsys.readouterr()
    main(
        ["campaign", "create", "--objective", "grow affiliate revenue", "--category", "affiliate", "--product", "KetoDNA",
         "--influencer", influencer_id, "--goal-id", goal_id]
    )
    campaign_id = capsys.readouterr().out.strip().split("\t")[0]

    exit_code = main(["campaign", "activate", campaign_id])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "active" in out

    exit_code = main(["campaign", "execution", "start", campaign_id])
    out = capsys.readouterr().out
    assert exit_code == 0
    plan_id = out.strip().split("\t")[0]
    assert "in_progress" in out

    exit_code = main(["campaign", "execution", "advance", plan_id])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "verify_readiness" in out
    assert "done" in out
    assert "request_founder_review" in out
    assert "dispatched" in out

    main(["campaign", "execution", "show", plan_id])
    show_out = capsys.readouterr().out
    assert "produce_content" in show_out
    assert "check_measurement" in show_out


def test_campaign_execution_start_rejects_a_non_active_campaign(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["influencer", "create", "--name", "Mira", "--category", "affiliate"])
    influencer_id = capsys.readouterr().out.strip().split("\t")[0]
    main(["campaign", "create", "--objective", "a", "--category", "affiliate", "--product", "KetoDNA", "--influencer", influencer_id])
    campaign_id = capsys.readouterr().out.strip().split("\t")[0]

    exit_code = main(["campaign", "execution", "start", campaign_id])

    assert exit_code == 1
    assert "not active" in capsys.readouterr().err


def test_campaign_link_goal(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["influencer", "create", "--name", "Mira", "--category", "affiliate"])
    influencer_id = capsys.readouterr().out.strip().split("\t")[0]
    main(["campaign", "create", "--objective", "a", "--category", "affiliate", "--product", "KetoDNA", "--influencer", influencer_id])
    campaign_id = capsys.readouterr().out.strip().split("\t")[0]

    exit_code = main(["campaign", "link-goal", campaign_id, "goal-a"])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "goal-a" in out


def _campaign_with_goal(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    main(["brain", "goal", "add", "grow affiliate revenue"])
    goal_id = capsys.readouterr().out.strip().split("\t")[0]
    main(["influencer", "create", "--name", "Mira", "--category", "affiliate"])
    influencer_id = capsys.readouterr().out.strip().split("\t")[0]
    main(
        ["campaign", "create", "--objective", "a", "--category", "affiliate", "--product", "KetoDNA",
         "--influencer", influencer_id, "--goal-id", goal_id]
    )
    campaign_id = capsys.readouterr().out.strip().split("\t")[0]
    return campaign_id, goal_id


def test_campaign_revenue_record_accumulates_against_the_linked_goal(tmp_path, monkeypatch, capsys):
    campaign_id, goal_id = _campaign_with_goal(monkeypatch, tmp_path, capsys)

    main(["campaign", "revenue", "record", campaign_id, "150", "--cost", "40", "--provider", "digistore24"])
    capsys.readouterr()
    main(["campaign", "revenue", "record", campaign_id, "50"])
    capsys.readouterr()

    main(["brain", "kpi", "list"])
    out = capsys.readouterr().out
    assert f"revenue_{goal_id}\t200.0" in out
    assert f"cost_{goal_id}\t40.0" in out

    entries = Ledger().entries_for_goal(goal_id)
    assert any(e.kind == "revenue_claimed" and e.provider == "digistore24" for e in entries)


def test_campaign_cost_fee_settlement_refund_record_all_target_the_linked_goal(tmp_path, monkeypatch, capsys):
    campaign_id, goal_id = _campaign_with_goal(monkeypatch, tmp_path, capsys)

    main(["campaign", "revenue", "record", campaign_id, "150"])
    capsys.readouterr()
    main(["campaign", "cost", "record", campaign_id, "10", "--category", "ad_spend"])
    capsys.readouterr()
    main(["campaign", "fee", "record", campaign_id, "5", "--category", "platform_fee"])
    capsys.readouterr()
    main(["campaign", "settlement", "record", campaign_id, "130"])
    capsys.readouterr()
    main(["campaign", "refund", "record", campaign_id, "20"])
    capsys.readouterr()

    main(["brain", "kpi", "list"])
    out = capsys.readouterr().out
    assert f"cost_{goal_id}\t15.0" in out  # 10 ad_spend + 5 fee
    assert f"revenue_{goal_id}\t130.0" in out  # 150 - 20 refund
    assert f"settled_{goal_id}\t130.0" in out

    kinds = {e.kind for e in Ledger().entries_for_goal(goal_id)}
    assert kinds == {"revenue_claimed", "cost", "fee", "cash_settled", "refund"}


def test_campaign_revenue_record_rejects_a_campaign_with_no_linked_goal(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["influencer", "create", "--name", "Mira", "--category", "affiliate"])
    influencer_id = capsys.readouterr().out.strip().split("\t")[0]
    main(["campaign", "create", "--objective", "a", "--category", "affiliate", "--product", "KetoDNA", "--influencer", influencer_id])
    campaign_id = capsys.readouterr().out.strip().split("\t")[0]

    exit_code = main(["campaign", "revenue", "record", campaign_id, "150"])

    assert exit_code == 1
    assert "no goal_id" in capsys.readouterr().err


def test_campaign_revenue_record_unblocks_check_measurement_end_to_end(tmp_path, monkeypatch, capsys):
    campaign_id, goal_id = _campaign_with_goal(monkeypatch, tmp_path, capsys)
    main(["influencer", "list"])
    influencer_id = capsys.readouterr().out.strip().split("\t")[0]
    main(["influencer", "template", "add", influencer_id, "--kind", "hook", "--name", "h1", "--content", "Nobody tells you this about {product_name}..."])
    capsys.readouterr()
    main(["influencer", "template", "add", influencer_id, "--kind", "cta", "--name", "c1", "--content", "Try {product_name} today."])
    capsys.readouterr()
    main(["campaign", "activate", campaign_id])
    capsys.readouterr()
    main(["campaign", "execution", "start", campaign_id])
    plan_id = capsys.readouterr().out.strip().split("\t")[0]
    main(["campaign", "execution", "advance", plan_id])  # cascades to request_founder_review, dispatched
    capsys.readouterr()

    main(["campaign", "execution", "show", plan_id])
    task_line = [line for line in capsys.readouterr().out.splitlines() if "request_founder_review" in line][0]
    task_id = task_line.split("task_id=")[1]

    main(["brain", "approve", task_id])
    capsys.readouterr()
    main(["brain", "tick"])  # Monitor.sync() is what actually flips a delegated Task to "done" — advance alone never mutates Task state
    capsys.readouterr()
    main(["campaign", "revenue", "record", campaign_id, "200", "--cost", "100"])
    capsys.readouterr()

    main(["campaign", "execution", "advance", plan_id])
    out = capsys.readouterr().out

    assert "check_measurement\tdone" in out
    assert "'profit': 100.0" in out
