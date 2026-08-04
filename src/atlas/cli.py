import sys
import argparse
import json

from atlas.assets.affiliate_intelligence.agent import AffiliateIntelligenceAgent
from atlas.assets.creative_agent.agent import CreativeAgent
from atlas.assets.publishing_gateway.agent import PublishingGatewayAgent
from atlas.assets.publishing_gateway.store import PublishingQueueStore
from atlas.assets.recruitment_workforce.agent import RecruitmentAgent
from atlas.brain.ceo import CEOBrain
from atlas.brain.confidence import confidence_score, rank_by_confidence
from atlas.brain.explain import explain_opportunity
from atlas.brain.asset_value import success_law_lifetime_value
from atlas.brain.opportunity_ranking import explain_opportunity_subject, rank_opportunities
from atlas.brain.portfolio import portfolio_entries, rank_portfolio
from atlas.brain.console import build_console_view, format_console_view
from atlas.brain.kpi_intake import record_manual_cost, record_manual_refund, record_manual_revenue, record_manual_settlement
from atlas.brain.models import Finding, SuccessLaw, Task
from atlas.core.registry import Registry, UnsupportedVerb, VERBS
from atlas.app import run_app
from atlas.brand.factory import create_brand_from_proposal
from atlas.brand.registry import BrandRegistry, attach_brand_asset
from atlas.campaign.registry import CampaignRegistry, create_campaign, link_brand, link_destination_url, link_goal, refresh_confidence, set_status
from atlas.influencer.factory import create_influencer_from_proposal
from atlas.influencer.models import TEMPLATE_KINDS, DigitalInfluencer, IdentityProfile
from atlas.influencer.performance import record_metric
from atlas.influencer.production import add_template, assemble_publishing_package, generate_campaign_content, templates_of_kind
from atlas.influencer.ranking import rank_influencers
from atlas.influencer.registry import InfluencerRegistry, add_platform_target, attach_asset
from atlas.brain.digistore24_opportunity_discovery import discover_and_rank_digistore24_opportunities
from atlas.brain.opportunity_discovery_engine import discover_opportunities
from atlas.brain.resource_allowlist import ResourceAllowlist
from atlas.brain.resource_discovery_engine import scan_resources
from atlas.brain.resource_index import ResourceIndex
from atlas.brain.decision_engine_integration import WAIT, TaskExecutionRequirements, evaluate_task_readiness
from atlas.brain.business_execution_planning import build_execution_plan
from atlas.integrations.digistore24 import Digistore24Provider
from atlas.orchestrator.orchestrator import advance_execution, start_execution


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="atlas")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="list known assets")
    subparsers.add_parser("console", help="consolidated operator view: goals, approvals, departments, KPIs")

    info_parser = subparsers.add_parser("info", help="show asset metadata")
    info_parser.add_argument("asset")

    for verb in VERBS:
        verb_parser = subparsers.add_parser(verb, help=f"invoke '{verb}' on an asset")
        verb_parser.add_argument("asset")

    brain_parser = subparsers.add_parser("brain", help="CEO brain operations")
    brain_sub = brain_parser.add_subparsers(dest="brain_command", required=True)

    goal_parser = brain_sub.add_parser("goal", help="manage goals")
    goal_sub = goal_parser.add_subparsers(dest="goal_command", required=True)
    goal_add = goal_sub.add_parser("add", help="add a goal")
    goal_add.add_argument("description")
    goal_add.add_argument("--priority", type=int, default=3, help="1 = highest")
    goal_add.add_argument(
        "--horizon", choices=["short", "long"], default="short", help="short = cash-flow-now, long = strategic-value-later"
    )
    goal_add.add_argument("--expected-revenue", type=float, default=None, help="founder estimate: projected revenue")
    goal_add.add_argument("--required-investment", type=float, default=None, help="founder estimate: projected cost")
    goal_add.add_argument("--time-to-first-profit", type=float, default=None, help="founder estimate: days")
    goal_add.add_argument("--scalability", type=float, default=None, help="founder estimate: 0.0-1.0")
    goal_add.add_argument("--automation-potential", type=float, default=None, help="founder estimate: 0.0-1.0")
    goal_add.add_argument(
        "--strategic-value", type=float, default=None, dest="long_term_strategic_value", help="founder estimate: 0.0-1.0"
    )
    goal_sub.add_parser("list", help="list goals")

    task_parser = brain_sub.add_parser("task", help="manage tasks")
    task_sub = task_parser.add_subparsers(dest="task_command", required=True)
    task_add = task_sub.add_parser("add", help="add a task under a goal (manual breakdown)")
    task_add.add_argument("goal_id")
    task_add.add_argument("description")
    task_add.add_argument("--category", default="general")
    task_add.add_argument("--amount", type=float, default=0.0, help="estimated financial commitment")
    task_add.add_argument("--reversible", action="store_true", help="mark as safely undoable")
    task_add.add_argument("--privileged-access", action="store_true", dest="privileged_access")
    task_add.add_argument("--legal-agreement", action="store_true", dest="legal_agreement")

    brain_sub.add_parser("tick", help="run one plan/prioritize/delegate/monitor cycle")
    brain_sub.add_parser("status", help="show all tasks and their status")
    brain_sub.add_parser("approvals", help="list tasks awaiting owner approval")

    approve_parser = brain_sub.add_parser("approve", help="approve a pending task/proposal")
    approve_parser.add_argument("task_id")
    reject_parser = brain_sub.add_parser("reject", help="reject a pending task/proposal")
    reject_parser.add_argument("task_id")

    brain_sub.add_parser("proposals", help="list asset/agent/redesign proposals")

    kpi_parser = brain_sub.add_parser("kpi", help="manage KPIs")
    kpi_sub = kpi_parser.add_subparsers(dest="kpi_command", required=True)
    kpi_record = kpi_sub.add_parser("record", help="record a KPI reading")
    kpi_record.add_argument("name")
    kpi_record.add_argument("value", type=float)
    kpi_sub.add_parser("list", help="list KPIs and their latest value")

    report_parser = brain_sub.add_parser("report", help="run a strategic review and print the executive report")
    report_parser.add_argument("--period", choices=["daily", "weekly", "monthly"], default="daily")

    opportunities_parser = brain_sub.add_parser(
        "opportunities", help="rank every discovered category by evidence-weighted confidence (Intelligence layer)"
    )
    opportunities_parser.add_argument(
        "--explain", action="store_true", help="show full evidence/confidence/ROI/risk breakdown for every ranked category"
    )

    brain_sub.add_parser(
        "discover-opportunities",
        help="Multi-Source Opportunity Discovery Engine V1 -- runs every registered provider (Digistore24 real, Amazon Associates/AliExpress/CJ/Impact/ShareASale honest placeholders), keeps going if one returns zero or fails, ranks combined real results, records real Findings",
    )

    finding_parser = brain_sub.add_parser("finding", help="manage the Intelligence knowledge base")
    finding_sub = finding_parser.add_subparsers(dest="finding_command", required=True)
    finding_add = finding_sub.add_parser("add", help="record a real, sourced finding (never a fabricated one)")
    finding_add.add_argument("source", help="who/what produced this finding, e.g. 'research' or a founder's name")
    finding_add.add_argument("category", help="open string: affiliate, digital_product, youtube, ugc, ...")
    finding_add.add_argument("description")
    finding_add.add_argument("--evidence", default="", help="a real URL/citation — leave unset if there isn't one yet")
    finding_add.add_argument(
        "--provider", default="", help="a specific registered provider this finding is about, e.g. 'digistore24' — leave unset for a category-general finding"
    )
    finding_add.add_argument(
        "--subject", default="", help="the specific candidate product/topic this finding is evidence for, e.g. 'KetoDNA' — leave unset for a category-general finding"
    )
    finding_add.add_argument(
        "--market", default="", help="the country/language this finding applies to, e.g. 'US' — leave unset if not market-specific"
    )
    finding_sub.add_parser("list", help="list every recorded finding")

    law_parser = brain_sub.add_parser("law", help="Success Laws: generalized business intelligence extracted from real evidence -- never a blueprint to copy")
    law_sub = law_parser.add_subparsers(dest="law_command", required=True)
    law_add = law_sub.add_parser("add", help="record a real Success Law -- a transferable principle, not an implementation to copy")
    law_add.add_argument("principle", help="the generalized, transferable rule, e.g. 'first-person testimonial framing outperforms feature-listing for consumer health products'")
    law_add.add_argument("source_description", help="what was actually observed, e.g. 'analysis of a real testimonial-style video' -- never phrased as 'do what X did'")
    law_add.add_argument("--evidence-finding", action="append", default=[], dest="evidence_finding_ids", help="a real finding id (see 'atlas brain finding list') this principle is grounded in (repeatable)")
    law_add.add_argument("--model", action="append", default=[], dest="applicable_business_models", help="a business category this principle generalizes to, e.g. affiliate (repeatable)")
    law_sub.add_parser("list", help="list every recorded Success Law")

    decisions_parser = brain_sub.add_parser("decisions", help="Decision Engine verdict history — full traceability, read-only")
    decisions_sub = decisions_parser.add_subparsers(dest="decisions_command", required=True)
    decisions_sub.add_parser("list", help="every Decision on record, latest first")
    decisions_show = decisions_sub.add_parser("show", help="full provenance for one category's current decision")
    decisions_show.add_argument("category")

    recruitment_parser = subparsers.add_parser("recruitment", help="Recruitment/Workforce agent intake and approvals")
    recruitment_sub = recruitment_parser.add_subparsers(dest="recruitment_command", required=True)

    demand_parser = recruitment_sub.add_parser("demand", help="manage employer demand intake")
    demand_sub = demand_parser.add_subparsers(dest="demand_command", required=True)
    demand_add = demand_sub.add_parser("add", help="intake a new employer demand")
    demand_add.add_argument("--industry", required=True)
    demand_add.add_argument("--employer-name", required=True, dest="employer_name")
    demand_add.add_argument("--role", required=True)
    demand_add.add_argument("--headcount", type=int, required=True)
    demand_add.add_argument("--rate", type=float, required=True, dest="rate_expectation_per_hour", help="bill rate per worker/hour")
    demand_add.add_argument("--location", default="")

    supplier_parser = recruitment_sub.add_parser("supplier", help="manage workforce supplier intake")
    supplier_sub = supplier_parser.add_subparsers(dest="supplier_command", required=True)
    supplier_add = supplier_sub.add_parser("add", help="intake a new workforce supplier")
    supplier_add.add_argument("--name", required=True)
    supplier_add.add_argument("--industry", required=True)

    candidate_parser = recruitment_sub.add_parser("candidate", help="manage candidate/worker pool intake")
    candidate_sub = candidate_parser.add_subparsers(dest="candidate_command", required=True)
    candidate_add = candidate_sub.add_parser("add", help="intake a new candidate/worker")
    candidate_add.add_argument("--industry", required=True)
    candidate_add.add_argument("--description", required=True)
    candidate_add.add_argument("--pay-rate", type=float, required=True, dest="pay_rate_expectation_per_hour", help="pay rate expectation per hour")
    candidate_add.add_argument("--supplier-id", default=None, dest="supplier_id")
    candidate_add.add_argument("--unavailable", action="store_true", help="mark as not currently available")

    recruitment_sub.add_parser("opportunities", help="list workforce opportunities and their stage")

    approve_outreach_parser = recruitment_sub.add_parser(
        "approve-outreach", help="founder approval gate: allow external outreach (proposal_ready -> active)"
    )
    approve_outreach_parser.add_argument("opportunity_id")

    approve_commitment_parser = recruitment_sub.add_parser(
        "approve-commitment", help="founder approval gate: allow agreement/placement/commitment (active -> won)"
    )
    approve_commitment_parser.add_argument("opportunity_id")

    lost_parser = recruitment_sub.add_parser("lost", help="mark an opportunity as lost")
    lost_parser.add_argument("opportunity_id")
    lost_parser.add_argument("--reason", default="")

    publishing_parser = subparsers.add_parser("publishing", help="Publishing Gateway queue management")
    publishing_sub = publishing_parser.add_subparsers(dest="publishing_command", required=True)
    publishing_sub.add_parser("queue", help="list publish packages and their status")
    delete_parser = publishing_sub.add_parser("delete", help="delete a queue item (direct action, not founder-approval-gated)")
    delete_parser.add_argument("package_id")
    mark_published_parser = publishing_sub.add_parser(
        "mark-published", help="confirm a QUEUED package was actually posted by the founder (direct action)"
    )
    mark_published_parser.add_argument("package_id")

    affiliate_parser = subparsers.add_parser("affiliate", help="real affiliate product intake and revenue tracking")
    affiliate_sub = affiliate_parser.add_subparsers(dest="affiliate_command", required=True)

    product_parser = affiliate_sub.add_parser("product", help="manage real affiliate product intake")
    product_sub = product_parser.add_subparsers(dest="product_command", required=True)
    product_add = product_sub.add_parser(
        "add", help="intake a real, founder-signed-up affiliate product (bypasses placeholder discovery)"
    )
    product_add.add_argument("--goal-id", required=True, dest="goal_id")
    product_add.add_argument("--name", required=True, dest="product_name")
    product_add.add_argument("--description", required=True)
    product_add.add_argument("--category", required=True)
    product_add.add_argument("--commission", type=float, required=True, dest="commission_per_conversion")
    product_add.add_argument("--link", required=True, dest="real_affiliate_link", help="the real affiliate tracking link")
    product_add.add_argument("--provider", required=True, help="the real affiliate network, e.g. digistore24")
    product_add.add_argument("--provider-product-id", default="", dest="provider_product_id", help="the network's own product id")
    product_add.add_argument("--conversion-rate", type=float, default=0.0, dest="estimated_conversion")
    product_add.add_argument("--competition", type=float, default=0.0)
    product_add.add_argument("--difficulty", type=float, default=0.0, dest="content_difficulty")

    revenue_parser = affiliate_sub.add_parser("revenue", help="record real affiliate revenue")
    revenue_sub = revenue_parser.add_subparsers(dest="revenue_command", required=True)
    revenue_record = revenue_sub.add_parser(
        "record", help="record a real conversion amount reported by the affiliate network, against a publish package"
    )
    revenue_record.add_argument("package_id")
    revenue_record.add_argument("amount", type=float)
    revenue_record.add_argument("--cost", type=float, default=None)
    revenue_record.add_argument("--provider", default="", help="which platform this conversion came from, e.g. digistore24")
    revenue_record.add_argument("--evidence", default="", help="what proves this happened, e.g. a dashboard screenshot reference or URL")
    revenue_record.add_argument("--document", default="", dest="document_ref", help="a stored invoice/receipt reference, if one exists")

    cost_parser = affiliate_sub.add_parser("cost", help="record real spend against a goal")
    cost_sub = cost_parser.add_subparsers(dest="cost_command", required=True)
    cost_record = cost_sub.add_parser(
        "record", help="record a real, incurred cost not tied to a single conversion (ad spend, subscriptions, setup), against a publish package's goal"
    )
    cost_record.add_argument("package_id")
    cost_record.add_argument("amount", type=float)
    cost_record.add_argument("--category", default="", help="cost sub-classification, e.g. ad_spend, tool_subscription")
    cost_record.add_argument("--provider", default="")
    cost_record.add_argument("--evidence", default="")
    cost_record.add_argument("--document", default="", dest="document_ref")

    fee_parser = affiliate_sub.add_parser("fee", help="record a real platform/processor fee against a goal")
    fee_sub = fee_parser.add_subparsers(dest="fee_command", required=True)
    fee_record = fee_sub.add_parser("record", help="record a real fee deducted by a platform or payment processor, against a publish package's goal")
    fee_record.add_argument("package_id")
    fee_record.add_argument("amount", type=float)
    fee_record.add_argument("--category", default="", help="fee sub-classification, e.g. platform_fee, processor_fee")
    fee_record.add_argument("--provider", default="")
    fee_record.add_argument("--evidence", default="")
    fee_record.add_argument("--document", default="", dest="document_ref")

    settlement_parser = affiliate_sub.add_parser("settlement", help="record real cash verified received against a goal")
    settlement_sub = settlement_parser.add_subparsers(dest="settlement_command", required=True)
    settlement_record = settlement_sub.add_parser(
        "record", help="record a real, verified payout received (distinct from a claimed conversion), against a publish package's goal"
    )
    settlement_record.add_argument("package_id")
    settlement_record.add_argument("amount", type=float)
    settlement_record.add_argument("--provider", default="")
    settlement_record.add_argument("--evidence", default="", help="what proves the cash was actually received, e.g. a bank statement reference")
    settlement_record.add_argument("--document", default="", dest="document_ref")

    refund_parser = affiliate_sub.add_parser("refund", help="record a real reversal of previously claimed revenue against a goal")
    refund_sub = refund_parser.add_subparsers(dest="refund_command", required=True)
    refund_record = refund_sub.add_parser(
        "record", help="record a real refund or chargeback that reverses previously claimed revenue, against a publish package's goal"
    )
    refund_record.add_argument("package_id")
    refund_record.add_argument("amount", type=float)
    refund_record.add_argument("--provider", default="")
    refund_record.add_argument("--evidence", default="")
    refund_record.add_argument("--document", default="", dest="document_ref")

    ds24_parser = affiliate_sub.add_parser("digistore24", help="real, live Digistore24 API calls (needs DIGISTORE24_API_KEY)")
    ds24_sub = ds24_parser.add_subparsers(dest="digistore24_command", required=True)
    ds24_sub.add_parser("verify", help="one real, low-risk getUserInfo call to confirm the API key/auth header actually work")
    ds24_marketplace = ds24_sub.add_parser("marketplace", help="real, read-only listMarketplaceEntries probe -- prints the raw response to discover its real shape")
    ds24_marketplace.add_argument("--sort-by", default=None, dest="sort_by", help="the one documented optional sort parameter")
    ds24_marketplace_entry = ds24_sub.add_parser("marketplace-entry", help="real, read-only getMarketplaceEntry probe for one specific entry_id")
    ds24_marketplace_entry.add_argument("entry_id", help="the real Digistore24 marketplace entry id to look up")
    ds24_sub.add_parser(
        "discover-opportunities",
        help="ATLAS Opportunity Discovery Engine for Digistore24 -- lists real marketplace entries, enriches and scores each by real revenue-potential fields, records real Findings for the Decision Engine to rank",
    )
    ds24_sub.add_parser("sales", help="real listPurchases call — prints the API's raw response, unmapped, for inspection")

    creative_parser = subparsers.add_parser("creative", help="Creative Agent brief drafts and real asset attachment")
    creative_sub = creative_parser.add_subparsers(dest="creative_command", required=True)
    creative_attach = creative_sub.add_parser(
        "attach", help="record a real, founder-produced image/short-video asset for an opportunity"
    )
    creative_attach.add_argument("opportunity_id")
    creative_attach.add_argument("--type", required=True, dest="asset_type", choices=["image", "short_video"])
    creative_attach.add_argument("--reference", required=True, help="a real file path or URL to the produced asset")

    influencer_parser = subparsers.add_parser("influencer", help="Digital Influencer Studio: reusable AI-presenter personas")
    influencer_sub = influencer_parser.add_subparsers(dest="influencer_command", required=True)

    influencer_create = influencer_sub.add_parser("create", help="create a new digital influencer persona")
    influencer_create.add_argument("--name", required=True)
    influencer_create.add_argument("--language", default="")
    influencer_create.add_argument("--nationality", default="", help="human-readable, e.g. 'Mexican' -- display only, not used for matching")
    influencer_create.add_argument("--market", default="", help="the real market/country code, e.g. 'MX' -- matched against a campaign's recommended market when selecting an influencer")
    influencer_create.add_argument("--niche", default="")
    influencer_create.add_argument("--personality", default="")
    influencer_create.add_argument("--bio", default="")
    influencer_create.add_argument(
        "--category", action="append", default=[], dest="categories",
        help="a business category this influencer can be assigned to (repeatable), e.g. --category affiliate",
    )

    influencer_create_from_proposal = influencer_sub.add_parser(
        "create-from-proposal",
        help="materialize a real influencer from an approved Digital Influencer Factory proposal — market/nationality/niche/audience from real evidence, name/personality/age/style default to ATLAS's AI-suggested draft (see the proposal text), override any of them",
    )
    influencer_create_from_proposal.add_argument("task_id", help="the approved create_asset task id (see 'atlas brain proposals')")
    influencer_create_from_proposal.add_argument("--name", default=None, help="defaults to the AI-suggested name if omitted")
    influencer_create_from_proposal.add_argument("--personality", default=None, help="defaults to the AI-suggested personality if omitted")
    influencer_create_from_proposal.add_argument("--age-range", dest="age_range", default=None, help="defaults to the AI-suggested age range if omitted")
    influencer_create_from_proposal.add_argument("--communication-style", dest="communication_style", default=None, help="defaults to the AI-suggested communication style if omitted")
    influencer_create_from_proposal.add_argument("--visual-style", dest="visual_style", default=None, help="defaults to the AI-suggested visual style if omitted")
    influencer_create_from_proposal.add_argument("--bio", default="", help="no AI suggestion for bio -- founder-only")

    influencer_sub.add_parser("list", help="list every digital influencer")

    influencer_show = influencer_sub.add_parser("show", help="show one digital influencer's full profile")
    influencer_show.add_argument("influencer_id")

    influencer_asset_parser = influencer_sub.add_parser("asset", help="manage an influencer's real asset library")
    influencer_asset_sub = influencer_asset_parser.add_subparsers(dest="influencer_asset_command", required=True)
    influencer_asset_attach = influencer_asset_sub.add_parser("attach", help="record a real asset (script/image/video/audio) for an influencer")
    influencer_asset_attach.add_argument("influencer_id")
    influencer_asset_attach.add_argument("--type", required=True, dest="asset_type", choices=["script", "image", "video", "audio"])
    influencer_asset_attach.add_argument("--reference", required=True, help="a real file path or URL to the asset")

    influencer_platform_parser = influencer_sub.add_parser("platform", help="declare a platform this influencer targets")
    influencer_platform_sub = influencer_platform_parser.add_subparsers(dest="influencer_platform_command", required=True)
    influencer_platform_add = influencer_platform_sub.add_parser("add", help="declare a platform target — a structural fact, never a publish action")
    influencer_platform_add.add_argument("influencer_id")
    influencer_platform_add.add_argument("--platform", required=True, help="e.g. TikTok, YouTube, Instagram")
    influencer_platform_add.add_argument("--handle", default="")

    influencer_metric_parser = influencer_sub.add_parser("metric", help="record real performance data for an influencer")
    influencer_metric_sub = influencer_metric_parser.add_subparsers(dest="influencer_metric_command", required=True)
    influencer_metric_record = influencer_metric_sub.add_parser("record", help="record a real performance reading (followers, views, engagement_rate, or any platform-specific metric)")
    influencer_metric_record.add_argument("influencer_id")
    influencer_metric_record.add_argument("metric_name")
    influencer_metric_record.add_argument("value", type=float)

    influencer_rank = influencer_sub.add_parser("rank", help="rank influencers eligible for a business category by real performance evidence")
    influencer_rank.add_argument("category")

    influencer_template_parser = influencer_sub.add_parser("template", help="manage an influencer's reusable content template libraries")
    influencer_template_sub = influencer_template_parser.add_subparsers(dest="influencer_template_command", required=True)
    influencer_template_add = influencer_template_sub.add_parser("add", help="add a reusable, founder-authored content template to an influencer's library")
    influencer_template_add.add_argument("influencer_id")
    influencer_template_add.add_argument("--kind", required=True, choices=sorted(TEMPLATE_KINDS))
    influencer_template_add.add_argument("--name", required=True)
    influencer_template_add.add_argument("--content", required=True, help="the template text/prompt; use {product_name} where it should be substituted")
    influencer_template_add.add_argument("--tag", action="append", default=[], dest="tags", help="a matching tag (repeatable)")
    influencer_template_list = influencer_template_sub.add_parser("list", help="list an influencer's templates, optionally filtered by kind")
    influencer_template_list.add_argument("influencer_id")
    influencer_template_list.add_argument("--kind", default=None, choices=sorted(TEMPLATE_KINDS))

    brand_parser = subparsers.add_parser("brand", help="Brand Factory: the company/product identity a Campaign operates under")
    brand_sub = brand_parser.add_subparsers(dest="brand_command", required=True)

    brand_create_from_proposal = brand_sub.add_parser(
        "create-from-proposal",
        help="materialize a real brand from an approved Brand Factory proposal — niche/category/market from real evidence, name defaults to the real product name, tagline/visual_identity/voice default to ATLAS's AI-suggested draft, override any of them",
    )
    brand_create_from_proposal.add_argument("task_id", help="the approved create_asset task id (see 'atlas brain proposals')")
    brand_create_from_proposal.add_argument("--name", default=None, help="defaults to the real product name if omitted")
    brand_create_from_proposal.add_argument("--tagline", default=None, help="defaults to the AI-suggested tagline if omitted")
    brand_create_from_proposal.add_argument("--visual-identity", dest="visual_identity", default=None, help="defaults to the AI-suggested visual identity if omitted")
    brand_create_from_proposal.add_argument("--voice", default=None, help="defaults to the AI-suggested brand voice if omitted")

    brand_sub.add_parser("list", help="list every brand")

    brand_show = brand_sub.add_parser("show", help="show one brand's full profile")
    brand_show.add_argument("brand_id")

    brand_asset_parser = brand_sub.add_parser("asset", help="manage a brand's real asset library (logo, banner, ...)")
    brand_asset_sub = brand_asset_parser.add_subparsers(dest="brand_asset_command", required=True)
    brand_asset_attach = brand_asset_sub.add_parser("attach", help="record a real asset (logo/banner/...) for a brand")
    brand_asset_attach.add_argument("brand_id")
    brand_asset_attach.add_argument("--type", required=True, dest="asset_type", choices=["logo", "banner", "image", "video"])
    brand_asset_attach.add_argument("--reference", required=True, help="a real file path or URL to the asset")

    campaign_parser = subparsers.add_parser("campaign", help="Campaign Intelligence Layer: the real business unit ATLAS manages end-to-end")
    campaign_sub = campaign_parser.add_subparsers(dest="campaign_command", required=True)

    campaign_create = campaign_sub.add_parser("create", help="assemble a complete Campaign from real evidence")
    campaign_create.add_argument("--objective", required=True, dest="business_objective")
    campaign_create.add_argument("--category", required=True)
    campaign_create.add_argument("--product", required=True, dest="product_offer")
    campaign_create.add_argument("--influencer", action="append", required=True, default=[], dest="influencer_ids", help="a DigitalInfluencer id (repeatable)")
    campaign_create.add_argument("--revenue-goal", type=float, default=None, dest="revenue_goal")
    campaign_create.add_argument("--target-audience", default="")
    campaign_create.add_argument("--customer-problem", default="")
    campaign_create.add_argument("--platform-strategy", default="")
    campaign_create.add_argument("--content-strategy", default="")
    campaign_create.add_argument("--content-format", action="append", default=[], dest="content_formats", help="repeatable, e.g. --content-format 'short-form video'")
    campaign_create.add_argument("--landing-page-strategy", default="")
    campaign_create.add_argument("--cta-strategy", default="")
    campaign_create.add_argument("--budget", type=float, default=None)
    campaign_create.add_argument("--success-kpi", action="append", default=[], dest="success_kpis", help="a real KPI series name this campaign considers success (repeatable)")
    campaign_create.add_argument("--goal-id", default=None, dest="goal_id")
    campaign_create.add_argument("--destination-url", default="", dest="destination_url", help="the real, clickable link content drives traffic to")

    campaign_sub.add_parser("list", help="list every campaign")

    campaign_show = campaign_sub.add_parser("show", help="show one campaign's full profile")
    campaign_show.add_argument("campaign_id")

    campaign_refresh = campaign_sub.add_parser("refresh-confidence", help="recompute a campaign's confidence_score from current evidence")
    campaign_refresh.add_argument("campaign_id")

    campaign_produce = campaign_sub.add_parser(
        "produce", help="generate one content package per assigned influencer from the campaign's own template libraries (no real generation — deterministic assembly only)"
    )
    campaign_produce.add_argument("campaign_id")

    campaign_activate = campaign_sub.add_parser("activate", help="approve a campaign for execution — the required gate before the Execution Orchestrator will start a plan")
    campaign_activate.add_argument("campaign_id")

    campaign_link_goal = campaign_sub.add_parser("link-goal", help="attach a real Goal to a campaign created without one")
    campaign_link_goal.add_argument("campaign_id")
    campaign_link_goal.add_argument("goal_id")

    campaign_link_url = campaign_sub.add_parser("link-destination-url", help="attach a real destination URL to a campaign created without one")
    campaign_link_url.add_argument("campaign_id")
    campaign_link_url.add_argument("destination_url")

    # Campaign-scoped Measurement/Finance entry points (2026-08-03): the
    # `atlas affiliate revenue/cost/fee/settlement/refund record` commands
    # above all resolve a package_id -> goal_id via PublishingQueueStore —
    # the old affiliate_department/publishing_gateway chain, which Campaigns
    # never touch. Without these, there was no real way to record real
    # money against a Campaign's goal_id at all; the underlying
    # record_manual_*() functions already take goal_id directly (package_id
    # resolution was always just a CLI convenience for the old flow), so
    # this is the same functions, a second real entry point.
    campaign_revenue_parser = campaign_sub.add_parser("revenue", help="record real revenue against a campaign's linked goal")
    campaign_revenue_sub = campaign_revenue_parser.add_subparsers(dest="campaign_revenue_command", required=True)
    campaign_revenue_record = campaign_revenue_sub.add_parser("record", help="record a real conversion amount for this campaign")
    campaign_revenue_record.add_argument("campaign_id")
    campaign_revenue_record.add_argument("amount", type=float)
    campaign_revenue_record.add_argument("--cost", type=float, default=None)
    campaign_revenue_record.add_argument("--provider", default="")
    campaign_revenue_record.add_argument("--evidence", default="")
    campaign_revenue_record.add_argument("--document", default="", dest="document_ref")

    campaign_cost_parser = campaign_sub.add_parser("cost", help="record real spend against a campaign's linked goal")
    campaign_cost_sub = campaign_cost_parser.add_subparsers(dest="campaign_cost_command", required=True)
    campaign_cost_record = campaign_cost_sub.add_parser("record", help="record a real, incurred cost not tied to a single conversion for this campaign")
    campaign_cost_record.add_argument("campaign_id")
    campaign_cost_record.add_argument("amount", type=float)
    campaign_cost_record.add_argument("--category", default="")
    campaign_cost_record.add_argument("--provider", default="")
    campaign_cost_record.add_argument("--evidence", default="")
    campaign_cost_record.add_argument("--document", default="", dest="document_ref")

    campaign_fee_parser = campaign_sub.add_parser("fee", help="record a real platform/processor fee against a campaign's linked goal")
    campaign_fee_sub = campaign_fee_parser.add_subparsers(dest="campaign_fee_command", required=True)
    campaign_fee_record = campaign_fee_sub.add_parser("record", help="record a real fee deducted by a platform or payment processor for this campaign")
    campaign_fee_record.add_argument("campaign_id")
    campaign_fee_record.add_argument("amount", type=float)
    campaign_fee_record.add_argument("--category", default="")
    campaign_fee_record.add_argument("--provider", default="")
    campaign_fee_record.add_argument("--evidence", default="")
    campaign_fee_record.add_argument("--document", default="", dest="document_ref")

    campaign_settlement_parser = campaign_sub.add_parser("settlement", help="record real cash verified received against a campaign's linked goal")
    campaign_settlement_sub = campaign_settlement_parser.add_subparsers(dest="campaign_settlement_command", required=True)
    campaign_settlement_record = campaign_settlement_sub.add_parser("record", help="record a real, verified payout received for this campaign")
    campaign_settlement_record.add_argument("campaign_id")
    campaign_settlement_record.add_argument("amount", type=float)
    campaign_settlement_record.add_argument("--provider", default="")
    campaign_settlement_record.add_argument("--evidence", default="")
    campaign_settlement_record.add_argument("--document", default="", dest="document_ref")

    campaign_refund_parser = campaign_sub.add_parser("refund", help="record a real reversal of previously claimed revenue against a campaign's linked goal")
    campaign_refund_sub = campaign_refund_parser.add_subparsers(dest="campaign_refund_command", required=True)
    campaign_refund_record = campaign_refund_sub.add_parser("record", help="record a real refund or chargeback that reverses previously claimed revenue for this campaign")
    campaign_refund_record.add_argument("campaign_id")
    campaign_refund_record.add_argument("amount", type=float)
    campaign_refund_record.add_argument("--provider", default="")
    campaign_refund_record.add_argument("--evidence", default="")
    campaign_refund_record.add_argument("--document", default="", dest="document_ref")

    campaign_package = campaign_sub.add_parser(
        "package",
        help="assemble the real, complete publishing package for a campaign+influencer -- copy, real media, landing page, creative brief, tracking link, all in one artifact",
    )
    campaign_package.add_argument("campaign_id")
    campaign_package.add_argument("influencer_id")
    campaign_package.add_argument("--export-landing-page", default=None, dest="export_landing_page", help="write the real landing page HTML to this file path")

    execution_parser = campaign_sub.add_parser("execution", help="Execution Orchestrator: coordinate a campaign's real business execution")
    execution_sub = execution_parser.add_subparsers(dest="execution_command", required=True)

    execution_start = execution_sub.add_parser("start", help="build an execution plan for an active campaign (idempotent — returns the existing plan if one is already in progress)")
    execution_start.add_argument("campaign_id")

    execution_advance = execution_sub.add_parser("advance", help="advance one execution plan by id — normally automatic every CEOBrain.tick(), this forces an immediate re-evaluation")
    execution_advance.add_argument("plan_id")

    execution_show = execution_sub.add_parser("show", help="show one execution plan's full step-by-step state")
    execution_show.add_argument("plan_id")

    portfolio_parser = subparsers.add_parser("portfolio", help="Business Asset Portfolio: every real, reusable asset ATLAS has created, across all types, ranked by measured lifetime value")
    portfolio_sub = portfolio_parser.add_subparsers(dest="portfolio_command", required=True)
    portfolio_sub.add_parser("list", help="list every real asset across every type, ranked by lifetime value")

    resources_parser = subparsers.add_parser("resources", help="Resource Discovery Engine V1: real, founder-approved local folders (and future Drive/OneDrive/Dropbox/NAS/Gmail sources), metadata only, never scanned without explicit approval")
    resources_sub = resources_parser.add_subparsers(dest="resources_command", required=True)

    resources_approve = resources_sub.add_parser("approve-folder", help="explicitly approve a real local folder for scanning -- required before any scan will touch it")
    resources_approve.add_argument("path", help="the real folder path to approve")

    resources_revoke = resources_sub.add_parser("revoke-folder", help="revoke a previously approved folder -- the engine will refuse to scan it again")
    resources_revoke.add_argument("path", help="the real folder path to revoke")

    resources_sub.add_parser("list-approved", help="list every currently approved folder")

    resources_sub.add_parser("scan", help="run the Resource Discovery Engine across every registered provider (approved local folders + honest placeholders), report new/modified/deleted/duplicate resources")

    resources_index_parser = resources_sub.add_parser("index", help="query the already-persisted Resource Index -- never triggers a new scan, reads only what the last 'scan' already found")
    resources_index_parser.add_argument("--folder", default=None, help="only show resources under this real folder path")
    resources_index_parser.add_argument("--type", default=None, dest="resource_type", choices=["file", "folder", "symlink"], help="only show resources of this type")

    decide_parser = subparsers.add_parser("decide", help="Decision Engine Integration V1: deterministic EXECUTE/WAIT readiness for one real task, using Resource Discovery + Opportunity Discovery + Time Awareness")
    decide_sub = decide_parser.add_subparsers(dest="decide_command", required=True)
    decide_task = decide_sub.add_parser("task", help="evaluate one real task's readiness to execute")
    decide_task.add_argument("task_id", help="the real task id (see 'atlas brain goal list' / task ids in approvals)")
    decide_task.add_argument("--require-resource", action="append", default=[], dest="required_resource_paths", help="a real approved resource path required for this task (repeatable)")
    decide_task.add_argument("--opportunity-category", default=None, help="the real opportunity category this task needs evidence for, e.g. affiliate")
    decide_task.add_argument("--min-confidence", type=float, default=None, dest="min_opportunity_confidence", help="minimum real opportunity confidence score required")
    decide_task.add_argument("--deadline", default=None, dest="deadline_iso", help="a real ISO-8601 deadline this task must still have time before")
    decide_task.add_argument("--min-remaining-seconds", type=float, default=0.0, dest="minimum_remaining_seconds", help="minimum real seconds that must remain before --deadline")

    decide_plan = decide_sub.add_parser("plan", help="Business Execution Planning V1 -- a real, read-only plan for a category: selected opportunity, required resources, confidence, risks, success criteria. Never executes anything.")
    decide_plan.add_argument("category", help="the real category to plan for, e.g. affiliate")
    decide_plan.add_argument("--require-resource", action="append", default=[], dest="required_resource_paths", help="a real approved resource path this plan requires (repeatable)")
    decide_plan.add_argument("--estimated-duration-seconds", type=float, default=None, dest="estimated_duration_seconds", help="a real, founder-supplied duration estimate -- omit to leave estimated_execution_time honestly unset")

    return parser


def main(argv: list[str] | None = None) -> int:
    # Some Windows terminals report a legacy, non-UTF-8 codepage (e.g. cp1255)
    # to Python's stdio streams, which crashes on the box-drawing/dash
    # characters the dashboard prints. Fall back to replacing unencodable
    # characters instead of raising, so startup never depends on the host's
    # active codepage.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    effective_argv = sys.argv[1:] if argv is None else argv
    if not effective_argv:
        run_app()
        return 0

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "list":
            _cmd_list()
        elif args.command == "console":
            _cmd_console()
        elif args.command == "info":
            _cmd_info(args.asset)
        elif args.command == "brain":
            _cmd_brain(args)
        elif args.command == "recruitment":
            _cmd_recruitment(args)
        elif args.command == "publishing":
            _cmd_publishing(args)
        elif args.command == "affiliate":
            _cmd_affiliate(args)
        elif args.command == "creative":
            _cmd_creative(args)
        elif args.command == "influencer":
            _cmd_influencer(args)
        elif args.command == "brand":
            _cmd_brand(args)
        elif args.command == "campaign":
            _cmd_campaign(args)
        elif args.command == "portfolio":
            _cmd_portfolio(args)
        elif args.command == "resources":
            _cmd_resources(args)
        elif args.command == "decide":
            _cmd_decide(args)
        else:
            _cmd_verb(args.command, args.asset)
    except (KeyError, UnsupportedVerb, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0


def _cmd_list() -> None:
    registry = Registry()
    for record in registry.records():
        print(f"{record.id}\t{record.kind}\t{record.name}")


def _cmd_console() -> None:
    brain = CEOBrain()
    print(format_console_view(build_console_view(brain)))


def _cmd_info(asset_id: str) -> None:
    registry = Registry()
    record = registry.get_record(asset_id)
    print(f"id: {record.id}")
    print(f"name: {record.name}")
    print(f"kind: {record.kind}")
    print(f"description: {record.description}")
    print(f"owner: {record.owner}")
    print(f"tags: {', '.join(record.tags)}")
    print(f"entrypoint: {record.entrypoint or '(none)'}")


def _cmd_verb(verb: str, asset_id: str) -> None:
    registry = Registry()
    result = registry.dispatch(asset_id, verb)
    print(result if result is not None else "ok")


def _cmd_brain(args: argparse.Namespace) -> None:
    brain = CEOBrain()
    cmd = args.brain_command

    if cmd == "goal":
        if args.goal_command == "add":
            founder_estimate = {
                key: value
                for key, value in {
                    "expected_revenue": args.expected_revenue,
                    "required_investment": args.required_investment,
                    "time_to_first_profit": args.time_to_first_profit,
                    "scalability": args.scalability,
                    "automation_potential": args.automation_potential,
                    "long_term_strategic_value": args.long_term_strategic_value,
                }.items()
                if value is not None
            }
            goal = brain.add_goal(
                args.description, args.priority, horizon=args.horizon, founder_estimate=founder_estimate
            )
            print(f"{goal.id}\tpriority={goal.priority}\thorizon={goal.horizon}\t{goal.description}")
        else:
            for goal in brain.memory.goals():
                print(
                    f"{goal.id}\t{goal.status}\thorizon={goal.horizon}\tpriority={goal.priority}\t{goal.description}"
                )

    elif cmd == "task":
        if args.task_command == "add":
            goal = brain.memory.get_goal(args.goal_id)  # raises KeyError if unknown
            task = Task(
                goal_id=goal.id,
                description=args.description,
                category=args.category,
                estimated_amount=args.amount,
                reversible=args.reversible,
                involves_privileged_access=args.privileged_access,
                involves_legal_agreement=args.legal_agreement,
            )
            brain.memory.save_task(task)
            print(f"{task.id}\t{task.category}\t{task.description}")

    elif cmd == "tick":
        tasks = brain.tick()
        print(f"tick complete: {len(tasks)} tasks tracked")

    elif cmd == "status":
        for task in brain.memory.tasks():
            print(f"{task.id}\t{task.status}\t{task.category}\t{task.description}")

    elif cmd == "approvals":
        for task in brain.memory.tasks():
            if task.status != "pending_approval":
                continue
            reason = task.history[-1]["reason"] if task.history else ""
            print(f"{task.id}\t{task.category}\t{task.description}\t({reason})")

    elif cmd == "approve":
        task = brain.approve(args.task_id)
        print(f"{task.id} -> {task.status}")

    elif cmd == "reject":
        task = brain.reject(args.task_id)
        print(f"{task.id} -> {task.status}")

    elif cmd == "proposals":
        for proposal in brain.memory.proposals():
            print(f"{proposal.id}\t{proposal.kind}\t{proposal.status}\t{proposal.rationale}")

    elif cmd == "kpi":
        if args.kpi_command == "record":
            brain.kpis.record(args.name, args.value)
            print(f"recorded {args.name}={args.value}")
        else:
            for name in brain.kpis.names():
                print(f"{name}\t{brain.kpis.latest(name)}")

    elif cmd == "report":
        _print_report(brain.review(args.period))

    elif cmd == "opportunities":
        categories = sorted({f.category for f in brain.knowledge.findings()})
        unranked = [confidence_score(c, brain.knowledge, brain.memory, brain.kpis) for c in categories]
        ranked = rank_by_confidence(unranked)
        for i, result in enumerate(ranked, start=1):
            score = f"{result['score']:.3f}" if result["score"] is not None else "unscored (no evidence yet)"
            print(f"{result['category']}\tconfidence={score}\tfactors={result['factors_available']}/{result['factors_total']}")
            if args.explain:
                explanation = explain_opportunity(result["category"], brain.knowledge, brain.memory, brain.kpis, rank=i)
                print(f"  Evidence: {len(explanation['evidence'])} finding(s)")
                for e in explanation["evidence"]:
                    print(f"    - [{e['source']}] {e['description']} ({e['evidence'] or 'no evidence URL'})")
                roi_str = f"{explanation['expected_roi']:.3f}" if explanation["expected_roi"] is not None else "not yet measured"
                print(f"  Expected ROI: {roi_str}")
                prob_str = (
                    f"{explanation['probability_of_success']:.0%}"
                    if explanation["probability_of_success"] is not None
                    else "not estimable yet (no track record)"
                )
                print(f"  Probability of success: {prob_str}")
                print("  Risks:")
                for r in explanation["risks"]:
                    print(f"    - {r}")
                print(f"  Why ranked here: {explanation['rank_reason']}")

                opportunities = rank_opportunities(result["category"], brain.knowledge)
                if opportunities:
                    print("  Specific opportunities (Opportunity Discovery V1):")
                    for j, opp in enumerate(opportunities, start=1):
                        opp_score = f"{opp['score']:.3f}" if opp["score"] is not None else "unscored"
                        market = opp["recommended_market"] or "unspecified"
                        print(
                            f"    - {opp['subject']}: confidence={opp_score} "
                            f"sources={opp['independent_sources']} recommended_market={market}"
                        )
                        opp_explanation = explain_opportunity_subject(result["category"], opp["subject"], brain.knowledge, rank=j)
                        for e in opp_explanation["evidence"]:
                            print(f"        - [{e['source']}] {e['description']} ({e['evidence'] or 'no evidence URL'})")
                        for r in opp_explanation["risks"]:
                            print(f"        risk: {r}")
                        for law in opp_explanation["success_laws"]:
                            backed = "evidence-backed" if law.evidence_finding_ids else "hypothesis"
                            print(f"        success law ({backed}): {law.principle}")

    elif cmd == "discover-opportunities":
        engine_result = discover_opportunities(knowledge=brain.knowledge)
        print("Provider status:")
        for provider_name, status in engine_result["provider_status"].items():
            status_str = f"error: {status['error']}" if status["error"] else f"{status['count']} real opportunity/opportunities"
            print(f"  {provider_name}: {status_str}")
        opportunities = engine_result["opportunities"]
        if not opportunities:
            print("0 real opportunities discovered across every configured provider.")
        else:
            print(f"{len(opportunities)} real opportunity/opportunities, ranked by real score across all providers:")
            for o in opportunities:
                score_str = f"{o.score:.4f}" if o.score is not None else "unscored"
                print(f"  [{o.provider}] id={o.external_id}: score={score_str} — {o.title}")

    elif cmd == "finding":
        if args.finding_command == "add":
            finding = Finding(
                source=args.source,
                category=args.category,
                description=args.description,
                evidence=args.evidence,
                provider=args.provider,
                subject=args.subject,
                market=args.market,
            )
            brain.knowledge.save_finding(finding)
            print(f"{finding.id}\t{finding.category}\t{finding.provider or '(category-general)'}\t{finding.subject or '(no subject)'}\t{finding.description}")
        else:
            for finding in brain.knowledge.findings():
                print(
                    f"{finding.id}\t{finding.category}\t{finding.provider or '(category-general)'}\t"
                    f"{finding.subject or '(no subject)'}\t{finding.market or '(no market)'}\t"
                    f"{finding.source}\t{finding.description}\t{finding.evidence}"
                )

    elif cmd == "law":
        if args.law_command == "add":
            unknown = [fid for fid in args.evidence_finding_ids if fid not in {f.id for f in brain.knowledge.findings()}]
            if unknown:
                raise ValueError(f"unknown finding id(s): {unknown} — record them with 'atlas brain finding add' first")
            law = SuccessLaw(
                principle=args.principle,
                source_description=args.source_description,
                evidence_finding_ids=args.evidence_finding_ids,
                applicable_business_models=args.applicable_business_models,
            )
            brain.knowledge.save_success_law(law)
            status = "evidence-backed" if law.evidence_finding_ids else "hypothesis (no cited evidence yet)"
            print(f"{law.id}\t{status}\t{law.principle}")
        else:
            for law in brain.knowledge.success_laws():
                status = "evidence-backed" if law.evidence_finding_ids else "hypothesis"
                track_record = success_law_lifetime_value(law.id, brain.campaigns, brain.memory, brain.kpis)
                track_record_str = f"{track_record:.2f}" if track_record is not None else "no measured campaigns yet"
                print(
                    f"{law.id}\t{status}\tmodels={','.join(law.applicable_business_models) or '(unspecified)'}\t"
                    f"real_track_record={track_record_str}\t{law.principle}\tsource={law.source_description}"
                )

    elif cmd == "decisions":
        if args.decisions_command == "show":
            decision = brain.decisions.latest_for_category(args.category)
            if decision is None:
                print(f"no decision on record for '{args.category}'")
            else:
                _print_decision(decision)
        else:
            for decision in sorted(brain.decisions.decisions(), key=lambda d: d.created_at, reverse=True):
                confidence = f"{decision.confidence:.3f}" if decision.confidence is not None else "unscored"
                print(f"{decision.id}\t{decision.category}\t{decision.verdict}\tconfidence={confidence}\t{decision.created_at}")


def _print_decision(decision) -> None:
    confidence = f"{decision.confidence:.3f}" if decision.confidence is not None else "unscored"
    print(f"=== Decision {decision.id} — {decision.category} ===")
    print(f"Verdict: {decision.verdict}")
    print(f"Confidence: {confidence}")
    print(f"Chosen provider: {decision.chosen_provider or '(none)'}")
    print(f"Reasoning: {decision.reasoning}")
    print(f"Context: {decision.context}")
    print(f"Evidence cited ({len(decision.evidence_finding_ids)} finding(s)): {', '.join(decision.evidence_finding_ids) or '(none)'}")
    print("Risks:")
    for risk in decision.risks:
        print(f"  - {risk}")
    print(f"Goal created: {decision.goal_id or '(none)'}")
    print(f"Supersedes: {decision.superseded_id or '(none — first decision for this category)'}")
    print(f"Decided at: {decision.created_at}")


def _print_report(report: dict) -> None:
    print(f"=== {report['period']} executive report ===")
    print("Active goals:")
    for description in report["active_goals"]:
        print(f"  - {description}")
    print(f"Tasks by status: {report['tasks_by_status']}")
    print("Pending approvals:")
    for item in report["pending_approvals"]:
        print(f"  - [{item['category']}] {item['description']} ({item['id']})")
    print("Blocked / opportunities:")
    for item in report["blocked_opportunities"]:
        print(f"  - {item['description']} — {item['reason']} ({item['id']})")
    print("Open proposals:")
    for item in report["open_proposals"]:
        print(f"  - [{item['kind']}/{item['status']}] {item['rationale']} ({item['id']})")
    print(f"KPI deltas: {report['kpi_deltas']}")
    print("Cash flow:")
    for item in report["cash_flow"]:
        print(
            f"  - {item['description']}: revenue={item['revenue']} cost={item['cost']} "
            f"profit={item['profit']} roi={item['roi']} ({item['goal_id']})"
        )
    print("Reallocations:")
    for item in report["reallocations"]:
        print(
            f"  - {item['description']} ({item['horizon']}): "
            f"priority {item['old_priority']}->{item['new_priority']}, "
            f"status {item['old_status']}->{item['new_status']} — {item['reason']} ({item['goal_id']})"
        )
    opportunities = report["opportunities"]
    print(f"Opportunities: {opportunities['findings_this_period']} new finding(s) this period")
    for entry in opportunities["categories_ranked"]:
        confidence = f"{entry['confidence']:.3f}" if entry["confidence"] is not None else "unscored"
        print(f"  - {entry['category']}: confidence={confidence}", end="")
        if entry["top_subject"]:
            score = f"{entry['top_subject_score']:.3f}" if entry["top_subject_score"] is not None else "unscored"
            print(f" top opportunity: {entry['top_subject']} (score={score}, market={entry['recommended_market'] or 'unspecified'})")
        else:
            print(" (no specific opportunities ranked yet)")
    success_laws = report["success_laws"]
    print(f"Success Laws: {success_laws['total']} total, {success_laws['evidence_backed']} evidence-backed")
    for law in success_laws["ranked_by_track_record"]:
        backed = "evidence-backed" if law["evidence_backed"] else "hypothesis"
        track_record = f"{law['real_track_record']:.2f}" if law["real_track_record"] is not None else "no measured campaigns yet"
        print(f"  - [{backed}] {law['principle']} — real_track_record={track_record}")
    print("Asset Portfolio (top by real lifetime value):")
    for asset in report["asset_portfolio"]:
        value = f"{asset['lifetime_value']:.2f}" if asset["lifetime_value"] is not None else "not yet measured"
        print(f"  - [{asset['asset_type']}] {asset['name']} ({asset['market']}): lifetime_value={value}")
    readiness = report["publishing_readiness"]
    print(f"Publishing packages ready: {readiness['packages_ready']}")
    for blocked in readiness["steps_blocked"]:
        print(f"  - blocked: campaign {blocked['campaign_id']} / influencer {blocked['influencer_id']} — {blocked['reason']}")


def _cmd_recruitment(args: argparse.Namespace) -> None:
    agent = RecruitmentAgent()
    cmd = args.recruitment_command

    if cmd == "demand":
        if args.demand_command == "add":
            demand = agent.intake_demand(
                industry=args.industry,
                employer_name=args.employer_name,
                role=args.role,
                headcount=args.headcount,
                rate_expectation_per_hour=args.rate_expectation_per_hour,
                location=args.location,
            )
            print(
                f"{demand.id}\t{demand.industry}\t{demand.employer_name}\t"
                f"{demand.role} x{demand.headcount} @ ${demand.rate_expectation_per_hour}/hr"
            )

    elif cmd == "supplier":
        if args.supplier_command == "add":
            supplier = agent.intake_supplier(name=args.name, industry=args.industry)
            print(f"{supplier.id}\t{supplier.industry}\t{supplier.name}")

    elif cmd == "candidate":
        if args.candidate_command == "add":
            candidate = agent.intake_candidate(
                industry=args.industry,
                description=args.description,
                pay_rate_expectation_per_hour=args.pay_rate_expectation_per_hour,
                supplier_id=args.supplier_id,
                available=not args.unavailable,
            )
            print(
                f"{candidate.id}\t{candidate.industry}\t{candidate.description}\t"
                f"${candidate.pay_rate_expectation_per_hour}/hr\tavailable={candidate.available}"
            )

    elif cmd == "opportunities":
        for opp in agent.report()["opportunities"]:
            print(
                f"{opp['id']}\t{opp['stage']}\t{opp['industry']}\t"
                f"fee=${opp['fee_per_hour']}/hr\trecurring=${opp['recurring_monthly_revenue']}/mo\t"
                f"profit=${opp['estimated_gross_profit']}/mo"
            )

    elif cmd == "approve-outreach":
        opportunity = agent.approve_outreach(args.opportunity_id)
        print(f"{opportunity.id} -> {opportunity.stage}")

    elif cmd == "approve-commitment":
        opportunity = agent.approve_commitment(args.opportunity_id)
        print(f"{opportunity.id} -> {opportunity.stage}")

    elif cmd == "lost":
        opportunity = agent.mark_lost(args.opportunity_id, reason=args.reason)
        print(f"{opportunity.id} -> {opportunity.stage}")


def _cmd_publishing(args: argparse.Namespace) -> None:
    agent = PublishingGatewayAgent()
    cmd = args.publishing_command

    if cmd == "queue":
        for package in agent.report()["packages"]:
            print(
                f"{package['id']}\t{package['status']}\t{package['platform']}\t"
                f"{package['title']}\t(opportunity {package['opportunity_id']})"
            )

    elif cmd == "delete":
        agent.delete_queue_item(args.package_id)
        print(f"{args.package_id} deleted")

    elif cmd == "mark-published":
        package = agent.mark_published(args.package_id)
        print(f"{package.id} -> {package.status}")


def _cmd_affiliate(args: argparse.Namespace) -> None:
    cmd = args.affiliate_command

    if cmd == "product":
        if args.product_command == "add":
            agent = AffiliateIntelligenceAgent()
            opportunity = agent.intake_real_product(
                goal_id=args.goal_id,
                product_name=args.product_name,
                description=args.description,
                category=args.category,
                commission_per_conversion=args.commission_per_conversion,
                real_affiliate_link=args.real_affiliate_link,
                provider=args.provider,
                provider_product_id=args.provider_product_id,
                estimated_conversion=args.estimated_conversion,
                competition=args.competition,
                content_difficulty=args.content_difficulty,
            )
            print(f"{opportunity.id}\t{opportunity.stage}\t{opportunity.product_name}\t{opportunity.goal_id}")

    elif cmd == "revenue":
        if args.revenue_command == "record":
            goal_id = _resolve_package_goal_id(args.package_id, "revenue")
            brain = CEOBrain()
            record_manual_revenue(
                goal_id, args.amount, args.cost, brain.kpis, brain.ledger,
                provider=args.provider, evidence=args.evidence, document_ref=args.document_ref,
            )
            print(f"recorded revenue_{goal_id} += {args.amount}", end="")
            print(f", cost_{goal_id} += {args.cost}" if args.cost is not None else "")

    elif cmd == "cost":
        if args.cost_command == "record":
            goal_id = _resolve_package_goal_id(args.package_id, "cost")
            brain = CEOBrain()
            record_manual_cost(
                goal_id, args.amount, brain.kpis, brain.ledger,
                category=args.category, provider=args.provider, evidence=args.evidence, document_ref=args.document_ref,
            )
            print(f"recorded cost_{goal_id} += {args.amount}")

    elif cmd == "fee":
        if args.fee_command == "record":
            goal_id = _resolve_package_goal_id(args.package_id, "fee")
            brain = CEOBrain()
            record_manual_cost(
                goal_id, args.amount, brain.kpis, brain.ledger, kind="fee",
                category=args.category, provider=args.provider, evidence=args.evidence, document_ref=args.document_ref,
            )
            print(f"recorded cost_{goal_id} += {args.amount} (fee)")

    elif cmd == "settlement":
        if args.settlement_command == "record":
            goal_id = _resolve_package_goal_id(args.package_id, "settlement")
            brain = CEOBrain()
            record_manual_settlement(
                goal_id, args.amount, brain.kpis, brain.ledger,
                provider=args.provider, evidence=args.evidence, document_ref=args.document_ref,
            )
            print(f"recorded settled_{goal_id} += {args.amount}")

    elif cmd == "refund":
        if args.refund_command == "record":
            goal_id = _resolve_package_goal_id(args.package_id, "refund")
            brain = CEOBrain()
            record_manual_refund(
                goal_id, args.amount, brain.kpis, brain.ledger,
                provider=args.provider, evidence=args.evidence, document_ref=args.document_ref,
            )
            print(f"recorded revenue_{goal_id} -= {args.amount} (refund)")

    elif cmd == "digistore24":
        provider = Digistore24Provider()
        if args.digistore24_command == "verify":
            result = provider.verify_connection()
            if result is None:
                print("DIGISTORE24_API_KEY is not set — nothing to verify")
            else:
                print("Connection verified — real getUserInfo response:")
                print(json.dumps(result, indent=2))
        elif args.digistore24_command == "sales":
            sales = provider.fetch_recent_sales()
            if sales is None:
                print("DIGISTORE24_API_KEY is not set — nothing to fetch")
            else:
                print(f"{len(sales)} real record(s) from listPurchases (raw, unmapped):")
                print(json.dumps(sales, indent=2))
        elif args.digistore24_command == "marketplace":
            result = provider.list_marketplace_entries(sort_by=args.sort_by)
            if result is None:
                print("DIGISTORE24_API_KEY is not set — nothing to fetch")
            else:
                print("Real listMarketplaceEntries response (raw, unmapped -- inspect this to learn the real shape):")
                print(json.dumps(result, indent=2))
        elif args.digistore24_command == "marketplace-entry":
            result = provider.get_marketplace_entry(args.entry_id)
            if result is None:
                print("DIGISTORE24_API_KEY is not set — nothing to fetch")
            else:
                print("Real getMarketplaceEntry response (raw, unmapped -- inspect this to learn the real shape):")
                print(json.dumps(result, indent=2))
        elif args.digistore24_command == "discover-opportunities":
            brain = CEOBrain()
            results = discover_and_rank_digistore24_opportunities(provider, brain.knowledge)
            if not results:
                print(
                    "0 real opportunities discovered. If DIGISTORE24_API_KEY is set, this means "
                    "listMarketplaceEntries returned zero real entries -- expected for an affiliate-only "
                    "account per Digistore24's own API scoping (\"marketplace data for a vendor\"), not an error."
                )
            else:
                print(f"{len(results)} real candidate(s), ranked by real revenue-potential score:")
                for r in results:
                    if r["error"]:
                        print(f"  entry_id={r['entry_id']}: ERROR — {r['error']}")
                    else:
                        headline = r["data"].get("headline", "(no headline)")
                        score_str = f"{r['score']:.4f}" if r["score"] is not None else "unscored (no real profit fields present)"
                        print(f"  entry_id={r['entry_id']}: score={score_str} — {headline}")


def _resolve_package_goal_id(package_id: str, purpose: str) -> str:
    package = PublishingQueueStore().get_package(package_id)
    if not package.goal_id:
        raise ValueError(f"publish package {package_id} has no goal_id — cannot attribute {purpose}")
    return package.goal_id


def _resolve_campaign_goal_id(campaign_id: str, campaign_registry: CampaignRegistry, purpose: str) -> str:
    campaign = campaign_registry.get_campaign(campaign_id)
    if not campaign.goal_id:
        raise ValueError(f"campaign {campaign_id} has no goal_id — cannot attribute {purpose} (use 'atlas campaign link-goal' first)")
    return campaign.goal_id


def _cmd_creative(args: argparse.Namespace) -> None:
    cmd = args.creative_command

    if cmd == "attach":
        agent = CreativeAgent()
        opportunity = agent.attach_real_asset(args.opportunity_id, args.asset_type, args.reference)
        print(f"{opportunity.id}\t{opportunity.creative_assets['status']}\t{opportunity.creative_assets['reference']}")


def _cmd_influencer(args: argparse.Namespace) -> None:
    cmd = args.influencer_command
    registry = InfluencerRegistry()

    if cmd == "create":
        influencer = DigitalInfluencer(
            identity=IdentityProfile(
                name=args.name, language=args.language, nationality=args.nationality, market=args.market, niche=args.niche,
                personality=args.personality, bio=args.bio,
            ),
            categories=args.categories,
        )
        registry.save_influencer(influencer)
        print(f"{influencer.id}\t{influencer.identity.name}\t{influencer.identity.niche}\t{','.join(influencer.categories)}")

    elif cmd == "create-from-proposal":
        brain = CEOBrain()
        influencer = create_influencer_from_proposal(
            args.task_id, brain.memory, brain.affiliate_store, brain.knowledge, registry,
            name=args.name, personality=args.personality, age_range=args.age_range,
            communication_style=args.communication_style, visual_style=args.visual_style, bio=args.bio,
        )
        print(
            f"{influencer.id}\t{influencer.identity.name}\t{influencer.identity.nationality}\t{influencer.identity.market}\t"
            f"{influencer.identity.language}\t{influencer.identity.niche}\t{influencer.identity.age_range}\t{','.join(influencer.categories)}"
        )

    elif cmd == "list":
        for influencer in registry.influencers():
            print(f"{influencer.id}\t{influencer.identity.name}\t{influencer.status}\t{','.join(influencer.categories)}")

    elif cmd == "show":
        influencer = registry.get_influencer(args.influencer_id)
        print(f"{influencer.id}\t{influencer.identity.name}\t{influencer.status}")
        print(
            f"  Identity: nationality={influencer.identity.nationality} market={influencer.identity.market} language={influencer.identity.language} "
            f"niche={influencer.identity.niche} age_range={influencer.identity.age_range} personality={influencer.identity.personality}"
        )
        print(f"  Voice: {influencer.voice.description or '(not set)'} (provider={influencer.voice.provider or 'none'})")
        print(f"  Visual: {influencer.visual.description or '(not set)'} (provider={influencer.visual.provider or 'none'})")
        print(f"  Content style: tone={influencer.content_style.tone or '(not set)'} formats={influencer.content_style.format_preferences}")
        print(f"  Audience: {influencer.audience.description or '(not set)'} estimated_size={influencer.audience.estimated_size}")
        print(f"  Categories: {', '.join(influencer.categories) or '(none)'}")
        for target in influencer.platform_targets:
            print(f"  Platform: {target.platform}\t{target.handle or '(no handle)'}\t{target.status}")
        for asset in influencer.asset_library:
            print(f"  Asset: {asset.asset_type}\t{asset.reference}")
        for template in influencer.templates:
            print(f"  Template: {template.kind}\t{template.name}\t{template.id}")

    elif cmd == "asset":
        if args.influencer_asset_command == "attach":
            influencer = attach_asset(args.influencer_id, args.asset_type, args.reference, registry)
            print(f"{influencer.id}\tasset library now has {len(influencer.asset_library)} entrie(s)")

    elif cmd == "platform":
        if args.influencer_platform_command == "add":
            influencer = add_platform_target(args.influencer_id, args.platform, args.handle, registry)
            print(f"{influencer.id}\t{args.platform}\t{args.handle or '(no handle)'}\tplanned")

    elif cmd == "metric":
        if args.influencer_metric_command == "record":
            record_metric(args.influencer_id, args.metric_name, args.value, CEOBrain().kpis)
            print(f"recorded {args.metric_name}_{args.influencer_id} = {args.value}")

    elif cmd == "rank":
        ranked = rank_influencers(args.category, registry, CEOBrain().kpis)
        if not ranked:
            print(f"no influencer tagged for category '{args.category}'")
        for entry in ranked:
            print(f"{entry['influencer_id']}\t{entry['factors_available']}/{entry['factors_total']} evidence factors\t{entry['metrics']}")

    elif cmd == "template":
        if args.influencer_template_command == "add":
            influencer = add_template(args.influencer_id, args.kind, args.name, args.content, registry, tags=args.tags)
            print(f"{influencer.id}\t{args.kind}\t{args.name}\t{len(templates_of_kind(influencer, args.kind))} template(s) of this kind")
        elif args.influencer_template_command == "list":
            influencer = registry.get_influencer(args.influencer_id)
            templates = templates_of_kind(influencer, args.kind) if args.kind else influencer.templates
            for template in templates:
                print(f"{template.id}\t{template.kind}\t{template.name}\t{template.content}")


def _cmd_brand(args: argparse.Namespace) -> None:
    cmd = args.brand_command
    registry = BrandRegistry()

    if cmd == "create-from-proposal":
        brain = CEOBrain()
        campaigns = CampaignRegistry()
        brand = create_brand_from_proposal(
            args.task_id, brain.memory, brain.affiliate_store, brain.knowledge, registry,
            campaign_registry=campaigns, name=args.name, tagline=args.tagline,
            visual_identity=args.visual_identity, voice=args.voice,
        )
        print(f"{brand.id}\t{brand.name}\t{brand.niche}\t{brand.category}\t{brand.market}")

    elif cmd == "list":
        for brand in registry.brands():
            print(f"{brand.id}\t{brand.name}\t{brand.niche}\t{brand.market}")

    elif cmd == "show":
        brand = registry.get_brand(args.brand_id)
        print(f"{brand.id}\t{brand.name}")
        print(f"  Tagline: {brand.tagline or '(not set)'}")
        print(f"  Visual identity: {brand.visual_identity or '(not set)'}")
        print(f"  Voice: {brand.voice or '(not set)'}")
        print(f"  Niche: {brand.niche}\tCategory: {brand.category}\tMarket: {brand.market or '(unspecified)'}")
        print(f"  Source opportunity: {brand.source_opportunity_id or '(none)'}")
        for asset in brand.asset_library:
            print(f"  Asset: {asset.asset_type}\t{asset.reference}")

    elif cmd == "asset":
        if args.brand_asset_command == "attach":
            brand = attach_brand_asset(args.brand_id, args.asset_type, args.reference, registry)
            print(f"{brand.id}\tasset library now has {len(brand.asset_library)} entrie(s)")


def _cmd_portfolio(args: argparse.Namespace) -> None:
    cmd = args.portfolio_command
    brain = CEOBrain()

    if cmd == "list":
        ranked = rank_portfolio(portfolio_entries(brain.influencers, brain.brands, brain.campaigns, brain.memory, brain.kpis))
        for entry in ranked:
            ltv = f"{entry.lifetime_value:.2f}" if entry.lifetime_value is not None else "unmeasured"
            print(
                f"{entry.asset_id}\t{entry.asset_type}\t{entry.name}\tmarket={entry.market or '(unspecified)'}\t"
                f"business_models={','.join(entry.business_models) or '(none)'}\tlifetime_value={ltv}"
            )


def _cmd_resources(args: argparse.Namespace) -> None:
    cmd = args.resources_command
    allowlist = ResourceAllowlist()

    if cmd == "approve-folder":
        allowlist.approve_folder(args.path)
        print(f"approved: {args.path}")
    elif cmd == "revoke-folder":
        allowlist.revoke_folder(args.path)
        print(f"revoked: {args.path}")
    elif cmd == "list-approved":
        folders = allowlist.approved_folders()
        if not folders:
            print("0 approved folders -- 'atlas resources scan' will scan nothing until at least one is approved.")
        else:
            for folder in folders:
                print(folder)
    elif cmd == "scan":
        result = scan_resources(allowlist)
        print("Provider status:")
        for provider_name, status in result["provider_status"].items():
            status_str = f"error: {status['error']}" if status["error"] else f"{status['count']} real resource(s)"
            print(f"  {provider_name}: {status_str}")
        print(f"Total resources: {len(result['resources'])}")
        print(f"New: {len(result['new'])}\tModified: {len(result['modified'])}\tDeleted: {len(result['deleted'])}")
        for path in result["new"]:
            print(f"  + new: {path}")
        for path in result["modified"]:
            print(f"  ~ modified: {path}")
        for path in result["deleted"]:
            print(f"  - deleted: {path}")
        if result["duplicates"]:
            print(f"Duplicate groups: {len(result['duplicates'])}")
            for group in result["duplicates"]:
                print(f"  duplicate: {group}")
    elif cmd == "index":
        index = ResourceIndex()
        if args.folder:
            resources = index.resources_in_folder(args.folder)
        elif args.resource_type:
            resources = index.find_by_type(args.resource_type)
        else:
            resources = index.all_resources()
        if not resources:
            print("0 resources in the index -- run 'atlas resources scan' first (this command never scans itself).")
        else:
            for r in resources:
                size_str = f"{r.size_bytes}B" if r.size_bytes is not None else "-"
                print(f"[{r.resource_type}] {r.path}\tname={r.name}\tsize={size_str}\tmodified={r.modified_at or '-'}\thash={r.content_hash or '-'}")


def _cmd_decide(args: argparse.Namespace) -> None:
    cmd = args.decide_command
    brain = CEOBrain()

    if cmd == "task":
        task = brain.memory.get_task(args.task_id)
        requirements = TaskExecutionRequirements(
            required_resource_paths=args.required_resource_paths,
            opportunity_category=args.opportunity_category,
            min_opportunity_confidence=args.min_opportunity_confidence,
            deadline_iso=args.deadline_iso,
            minimum_remaining_seconds=args.minimum_remaining_seconds,
        )
        readiness = evaluate_task_readiness(task, requirements, knowledge=brain.knowledge)

        print(f"Task {readiness.task_id}: {readiness.decision}")
        for check_name, check in readiness.checks.items():
            status_str = "OK" if check["passed"] else f"BLOCKED -- {check['reason']}"
            print(f"  {check_name}: {status_str}")
        if readiness.decision == WAIT:
            print("Blocking reason(s):")
            for reason in readiness.reasons:
                print(f"  - {reason}")

    elif cmd == "plan":
        plan = build_execution_plan(
            args.category,
            brain.knowledge,
            brain.memory,
            brain.kpis,
            required_resource_paths=args.required_resource_paths,
            estimated_duration_seconds=args.estimated_duration_seconds,
        )
        print(f"Business Execution Plan for '{plan.category}' -- can_execute={plan.can_execute}")
        print(f"  Decision Engine verdict: {plan.verdict}")
        print(f"  Confidence score: {plan.confidence_score if plan.confidence_score is not None else 'unscored'}")
        if plan.selected_opportunity:
            opp = plan.selected_opportunity
            print(f"  Selected opportunity: {opp['subject']} (score={opp['score']}, market={opp['recommended_market'] or 'unspecified'})")
        else:
            print("  Selected opportunity: none ranked yet")
        print(f"  Required resources: {plan.required_resources}")
        print(f"  Estimated execution time: {plan.estimated_execution_time}")
        print(f"  Task dependency order: {' -> '.join(plan.task_dependency_order)}")
        print(f"  Expected outcome: {plan.expected_outcome}")
        print("  Risk assessment:")
        for risk in plan.risk_assessment:
            print(f"    - {risk}")
        print("  Success criteria:")
        for criterion in plan.success_criteria:
            print(f"    - {criterion}")
        if not plan.can_execute:
            print("  Blocking reason(s):")
            for reason in plan.blocking_reasons:
                print(f"    - {reason}")


def _cmd_campaign(args: argparse.Namespace) -> None:
    cmd = args.campaign_command
    registry = CampaignRegistry()
    brain = CEOBrain()

    if cmd == "create":
        campaign = create_campaign(
            args.business_objective, args.category, args.product_offer, args.influencer_ids,
            InfluencerRegistry(), brain.knowledge, brain.memory, brain.kpis, registry,
            revenue_goal=args.revenue_goal, target_audience=args.target_audience, customer_problem=args.customer_problem,
            platform_strategy=args.platform_strategy, content_strategy=args.content_strategy, content_formats=args.content_formats,
            landing_page_strategy=args.landing_page_strategy, cta_strategy=args.cta_strategy, budget=args.budget,
            success_kpis=args.success_kpis, goal_id=args.goal_id, destination_url=args.destination_url,
        )
        print(f"{campaign.id}\t{campaign.business_objective}\t{campaign.product_offer}\tconfidence={campaign.confidence_score}")

    elif cmd == "list":
        for campaign in registry.campaigns():
            print(f"{campaign.id}\t{campaign.status}\t{campaign.product_offer}\tconfidence={campaign.confidence_score}\tinfluencers={','.join(campaign.influencer_ids)}")

    elif cmd == "show":
        campaign = registry.get_campaign(args.campaign_id)
        print(f"{campaign.id}\t{campaign.status}\tconfidence={campaign.confidence_score}")
        print(f"  Business objective: {campaign.business_objective}")
        print(f"  Category: {campaign.category}")
        print(f"  Revenue goal: {campaign.revenue_goal}\tBudget: {campaign.budget}")
        print(f"  Target audience: {campaign.target_audience or '(not set)'}")
        print(f"  Customer problem: {campaign.customer_problem or '(not set)'}")
        print(f"  Product / Offer: {campaign.product_offer or '(not set)'}")
        print(f"  Destination URL: {campaign.destination_url or '(not set)'}")
        print(f"  Brand: {campaign.brand_id or '(not set)'}")
        print(f"  Success Laws in effect: {', '.join(campaign.success_law_ids) or '(none)'}")
        print(f"  Digital Influencer(s): {', '.join(campaign.influencer_ids) or '(none)'}")
        print(f"  Platform strategy: {campaign.platform_strategy or '(not set)'}")
        print(f"  Content strategy: {campaign.content_strategy or '(not set)'}\tFormats: {campaign.content_formats}")
        print(f"  Landing page strategy: {campaign.landing_page_strategy or '(not set)'}")
        print(f"  CTA strategy: {campaign.cta_strategy or '(not set)'}")
        print(f"  Timeline: {campaign.timeline or '(not set)'}")
        print(f"  Success KPIs: {campaign.success_kpis or '(none)'}")
        print(f"  Goal: {campaign.goal_id or '(none)'}")
        for entry in campaign.learning_history:
            print(f"  Learning history: {entry}")

    elif cmd == "refresh-confidence":
        campaign = refresh_confidence(args.campaign_id, brain.knowledge, brain.memory, brain.kpis, registry)
        print(f"{campaign.id}\tconfidence={campaign.confidence_score}")

    elif cmd == "produce":
        packages = generate_campaign_content(args.campaign_id, registry, InfluencerRegistry())
        for package in packages:
            print(f"--- influencer {package.influencer_id} ---")
            print(f"scripts: {package.scripts}")
            print(f"hooks: {package.hooks}")
            print(f"ctas: {package.ctas}")
            print(f"image_prompts: {package.image_prompts}")
            print(f"video_prompts: {package.video_prompts}")
            print(f"voice_prompts: {package.voice_prompts}")
            print(f"captions: {package.captions}")
            print(f"landing_page_messages: {package.landing_page_messages}")
            print(f"titles: {package.titles}")
            print(f"descriptions: {package.descriptions}")
            print(f"hashtags: {package.hashtags}")
            print(f"missing_kinds: {package.missing_kinds}")

    elif cmd == "activate":
        campaign = set_status(args.campaign_id, "active", registry)
        print(f"{campaign.id}\t{campaign.status}")

    elif cmd == "link-goal":
        campaign = link_goal(args.campaign_id, args.goal_id, registry)
        print(f"{campaign.id}\tgoal={campaign.goal_id}")

    elif cmd == "link-destination-url":
        campaign = link_destination_url(args.campaign_id, args.destination_url, registry)
        print(f"{campaign.id}\tdestination_url={campaign.destination_url}")

    elif cmd == "revenue":
        if args.campaign_revenue_command == "record":
            goal_id = _resolve_campaign_goal_id(args.campaign_id, registry, "revenue")
            record_manual_revenue(
                goal_id, args.amount, args.cost, brain.kpis, brain.ledger,
                provider=args.provider, evidence=args.evidence, document_ref=args.document_ref,
            )
            print(f"recorded revenue_{goal_id} += {args.amount}", end="")
            print(f", cost_{goal_id} += {args.cost}" if args.cost is not None else "")

    elif cmd == "cost":
        if args.campaign_cost_command == "record":
            goal_id = _resolve_campaign_goal_id(args.campaign_id, registry, "cost")
            record_manual_cost(
                goal_id, args.amount, brain.kpis, brain.ledger,
                category=args.category, provider=args.provider, evidence=args.evidence, document_ref=args.document_ref,
            )
            print(f"recorded cost_{goal_id} += {args.amount}")

    elif cmd == "fee":
        if args.campaign_fee_command == "record":
            goal_id = _resolve_campaign_goal_id(args.campaign_id, registry, "fee")
            record_manual_cost(
                goal_id, args.amount, brain.kpis, brain.ledger, kind="fee",
                category=args.category, provider=args.provider, evidence=args.evidence, document_ref=args.document_ref,
            )
            print(f"recorded cost_{goal_id} += {args.amount} (fee)")

    elif cmd == "settlement":
        if args.campaign_settlement_command == "record":
            goal_id = _resolve_campaign_goal_id(args.campaign_id, registry, "settlement")
            record_manual_settlement(
                goal_id, args.amount, brain.kpis, brain.ledger,
                provider=args.provider, evidence=args.evidence, document_ref=args.document_ref,
            )
            print(f"recorded settled_{goal_id} += {args.amount}")

    elif cmd == "refund":
        if args.campaign_refund_command == "record":
            goal_id = _resolve_campaign_goal_id(args.campaign_id, registry, "refund")
            record_manual_refund(
                goal_id, args.amount, brain.kpis, brain.ledger,
                provider=args.provider, evidence=args.evidence, document_ref=args.document_ref,
            )
            print(f"recorded revenue_{goal_id} -= {args.amount} (refund)")

    elif cmd == "package":
        bundle = assemble_publishing_package(args.campaign_id, args.influencer_id, registry, brain.influencers)
        print(f"Product/offer: {bundle['product_offer']}")
        print(f"Destination URL: {bundle['destination_url'] or '(not set)'}")
        print(f"Title: {bundle['title'] or '(not set)'}")
        print(f"Description: {bundle['description'] or '(not set)'}")
        print(f"Hook: {bundle['hook'] or '(not set)'}")
        print(f"CTA: {bundle['cta'] or '(not set)'}")
        print(f"Caption: {bundle['caption'] or '(not set)'}")
        print(f"Hashtags: {bundle['hashtags'] or '(not set)'}")
        print(f"Real media: {bundle['real_media'] or '(none attached)'}")
        print(f"Platforms: {', '.join(bundle['platforms']) or '(none declared)'}")
        print(f"Landing page: {'ready (' + str(len(bundle['landing_page_html'])) + ' chars)' if bundle['landing_page_html'] else 'not ready yet'}")
        print("Creative brief:")
        for shot in bundle["creative_brief"]["shots"]:
            print(f"  shot {shot['shot']} ({shot['duration_seconds']}s): {shot['direction']}")
        if args.export_landing_page:
            if not bundle["landing_page_html"]:
                raise ValueError("cannot export landing page — it isn't ready yet (see missing fields above)")
            with open(args.export_landing_page, "w", encoding="utf-8") as f:
                f.write(bundle["landing_page_html"])
            print(f"Landing page written to {args.export_landing_page}")

    elif cmd == "execution":
        _cmd_campaign_execution(args, registry, brain)


def _cmd_campaign_execution(args: argparse.Namespace, campaign_registry: CampaignRegistry, brain: CEOBrain) -> None:
    cmd = args.execution_command

    if cmd == "start":
        plan = start_execution(args.campaign_id, campaign_registry, brain.execution_plans)
        print(f"{plan.id}\t{plan.status}\t{len(plan.steps)} step(s)")

    elif cmd == "advance":
        plan = advance_execution(args.plan_id, brain.execution_plans, campaign_registry, brain.influencers, brain.memory, brain.kpis, brain.knowledge)
        print(f"{plan.id}\t{plan.status}")
        for step in plan.steps:
            print(f"  {step.kind}\t{step.status}\t{step.result}")

    elif cmd == "show":
        plan = brain.execution_plans.get_plan(args.plan_id)
        print(f"{plan.id}\tcampaign={plan.campaign_id}\t{plan.status}")
        for step in plan.steps:
            print(f"  Step: {step.kind}\t{step.status}\tdepends_on={step.depends_on}\ttask_id={step.task_id}")
            print(f"    result: {step.result}")
        for entry in plan.event_log:
            print(f"  Event: {entry}")


if __name__ == "__main__":
    sys.exit(main())
