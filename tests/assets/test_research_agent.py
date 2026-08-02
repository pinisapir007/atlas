from atlas.assets.research.agent import ResearchAgent


def test_classifies_default_signal_as_affiliate_opportunity():
    agent = ResearchAgent()

    result = agent.run()

    assert result["status"] == "done"
    assert result["opportunities"][0]["suggested_category"] == "revenue_affiliate"


def test_default_signals_include_a_recruitment_opportunity():
    agent = ResearchAgent()

    opportunities = agent.run()["opportunities"]

    assert any(o["suggested_category"] == "revenue_recruitment_leads" for o in opportunities)


def test_report_reflects_last_run():
    agent = ResearchAgent()
    run_result = agent.run()

    report = agent.report()

    assert report["opportunities"] == run_result["opportunities"]


def test_classifies_custom_signals_by_keyword():
    agent = ResearchAgent(
        signals=[
            "Sell an ebook about budgeting",
            "Recruit contract labor for a warehouse client",
            "Produce AI-generated marketing images",
            "A totally novel business idea with no obvious channel",
        ]
    )

    opportunities = agent.run()["opportunities"]

    assert [o["suggested_category"] for o in opportunities] == [
        "revenue_digital_product",
        "revenue_recruitment_leads",
        "revenue_content_assets",
        "create_asset",
    ]
