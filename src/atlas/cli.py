import sys
import argparse

from atlas.assets.affiliate_intelligence.agent import AffiliateIntelligenceAgent
from atlas.assets.creative_agent.agent import CreativeAgent
from atlas.assets.publishing_gateway.agent import PublishingGatewayAgent
from atlas.assets.publishing_gateway.store import PublishingQueueStore
from atlas.assets.recruitment_workforce.agent import RecruitmentAgent
from atlas.brain.ceo import CEOBrain
from atlas.brain.confidence import confidence_score, rank_by_confidence
from atlas.brain.explain import explain_opportunity
from atlas.brain.console import build_console_view, format_console_view
from atlas.brain.kpi_intake import record_manual_cost, record_manual_refund, record_manual_revenue, record_manual_settlement
from atlas.brain.models import Finding, Task
from atlas.core.registry import Registry, UnsupportedVerb, VERBS
from atlas.app import run_app


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
    finding_sub.add_parser("list", help="list every recorded finding")

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

    creative_parser = subparsers.add_parser("creative", help="Creative Agent brief drafts and real asset attachment")
    creative_sub = creative_parser.add_subparsers(dest="creative_command", required=True)
    creative_attach = creative_sub.add_parser(
        "attach", help="record a real, founder-produced image/short-video asset for an opportunity"
    )
    creative_attach.add_argument("opportunity_id")
    creative_attach.add_argument("--type", required=True, dest="asset_type", choices=["image", "short_video"])
    creative_attach.add_argument("--reference", required=True, help="a real file path or URL to the produced asset")

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

    elif cmd == "finding":
        if args.finding_command == "add":
            finding = Finding(
                source=args.source,
                category=args.category,
                description=args.description,
                evidence=args.evidence,
                provider=args.provider,
            )
            brain.knowledge.save_finding(finding)
            print(f"{finding.id}\t{finding.category}\t{finding.provider or '(category-general)'}\t{finding.description}")
        else:
            for finding in brain.knowledge.findings():
                print(
                    f"{finding.id}\t{finding.category}\t{finding.provider or '(category-general)'}\t"
                    f"{finding.source}\t{finding.description}\t{finding.evidence}"
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


def _resolve_package_goal_id(package_id: str, purpose: str) -> str:
    package = PublishingQueueStore().get_package(package_id)
    if not package.goal_id:
        raise ValueError(f"publish package {package_id} has no goal_id — cannot attribute {purpose}")
    return package.goal_id


def _cmd_creative(args: argparse.Namespace) -> None:
    cmd = args.creative_command

    if cmd == "attach":
        agent = CreativeAgent()
        opportunity = agent.attach_real_asset(args.opportunity_id, args.asset_type, args.reference)
        print(f"{opportunity.id}\t{opportunity.creative_assets['status']}\t{opportunity.creative_assets['reference']}")


if __name__ == "__main__":
    sys.exit(main())
