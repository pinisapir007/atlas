# ATLAS Affiliate Department — Design Document

Documentation only. Nothing in this document has been implemented; no manifest, entrypoint, or code exists yet for any agent named here. Every design choice below reuses a pattern that already exists and ships in ATLAS today — none of this is a new architectural idiom.

---

## Department Mission

Generate sustainable affiliate-marketing revenue by pairing genuinely useful affiliate offers with AI-generated digital-influencer content (MAYA), on the same footing as every other Cash Engine in the Business Blueprint: real KPI data drives every decision, no fabricated numbers, founder approval gates every irreversible or public-facing step.

## Responsibilities

The department is responsible for the full lifecycle of one affiliate opportunity: discovering it, evaluating it, planning the content that would promote it, gating it behind founder approval, observing its real performance, and feeding that performance back into ATLAS's existing capital-allocation loop (the Strategist). It is **not** responsible for: calling any external affiliate network API, publishing any content anywhere, or running on any schedule beyond what `CEOBrain.tick()`/`review()` already provide. Those are explicitly out of scope for this document, per the mission's constraints.

---

## Agent Responsibilities

Five roles are defined below. Only one of them (Market Intelligence) maps onto something that already has a code home today; the rest are documented as future `operational_agent` assets, following the exact manifest + entrypoint pattern `research`/`revenue`/`recruitment_workforce` already use — no new asset *kind*, no new Registry mechanism.

### 1. Market Intelligence

**What it actually is**: not a new asset. This is the business name for the `"affiliate"` provider slot already reserved (but deliberately not built) in Research's `_PROVIDERS` dict, designed in the prior session turn. Building Market Intelligence *is* building `AffiliateOpportunitySource` under `atlas/assets/research/providers/` — reusing Research's existing discovery/classification role rather than inventing a parallel one.

- **Inputs**: an approved public source of affiliate program listings (not yet named/approved — same open blocker already raised for the Recruitment provider).
- **Outputs**: opportunity dicts in Research's existing schema — `{"description", "suggested_category": "revenue_affiliate", "source", "source_id"}` — no schema change, purely reuses what `absorb_opportunities` already reads.
- **KPIs**: opportunities discovered per period, tagged by source (reuses the `provider_status` field from the Research provider design).
- **State transitions**: opportunity enters the department lifecycle at `discovered` (see State Machine below).
- **Founder approval**: none required here — discovery alone is reversible, zero-cost, and non-public, matching how Research's existing `discover_opportunities` category is risk-gated today (auto-approved by `RiskPolicy`).

### 2. Affiliate Manager

**What it actually is**: the real evaluation/selection logic that eventually replaces `AffiliateChannel`'s current hardcoded `revenue_generated: 0.0` placeholder in `revenue/channels/affiliate.py` — the same class already registered under `revenue`'s manifest, not a new asset.

- **Inputs**: a `revenue_affiliate` task (created by `absorb_opportunities`, unchanged) describing a discovered affiliate program.
- **Outputs**: a decision — proceed (creates a content-planning task under the same goal) or reject (task marked `done` with a reason, no further action; matches Recruitment's `mark_lost` precedent for "drop this opportunity honestly rather than force it forward").
- **KPIs**: opportunities evaluated, proceed-vs-reject rate, evaluation criteria coverage (see "Missing pieces" below — the rubric itself isn't defined yet).
- **State transitions**: `discovered → evaluated` (proceed) or `discovered → lost` (reject).
- **Founder approval**: none — evaluation is an internal, reversible decision, no external or public action taken yet.

### 3. Content Planner (including MAYA Studio, planning only)

Two responsibilities under one workflow stage — the workflow diagram shows a single "Content Planner" box; MAYA Studio is its MAYA-specific sub-function, not a separate stage.

- **Content Planner**: given an evaluated affiliate opportunity, drafts a content angle/campaign plan (which value-ladder rung it serves, per `atlas-value-ladder` — most naturally L4, "affiliate recommendations," per that memory's own permanent ladder definition).
- **MAYA Studio (planning only)**: produces the MAYA-facing artifact specifically — a structured content brief/script direction formatted for MAYA to eventually execute. **Planning only** means: it never invokes MAYA's (currently stubbed) real content-generation capability, and it never publishes anything. Its output is a document, not an action.
- **Inputs**: an `evaluated` opportunity task.
- **Outputs**: a content-brief artifact (structured data — angle, offer, value-ladder rung, MAYA-facing brief) attached to the task/goal, and a new task requesting founder approval.
- **KPIs**: content plans produced per period, average time from `evaluated` to `content_planned`.
- **State transitions**: `evaluated → content_planned`.
- **Founder approval**: none at this stage — approval is the *next* stage, not this one. This stage only prepares what will be presented for approval.

### 4. Founder Approval

Not a new asset or a bespoke gate method (unlike Recruitment's `approve_outreach`/`approve_commitment`) — reuses the existing, already-built `RiskPolicy`/`Task` mechanism directly. The content-plan task this stage evaluates is marked `reversible=False` (going public is not reversible), which means `RiskPolicy.evaluate()` already routes it to `pending_approval` with zero new code — the same fail-closed path every other irreversible task in ATLAS already goes through. Resolution is the existing `atlas brain approve <task_id>` / `reject <task_id>` CLI, unchanged.

- **Inputs**: a `content_planned` task, `reversible=False`.
- **Outputs**: `approved` (task resolved via `approve()`) or `rejected` (via `reject()`, task → `failed`, matching existing semantics exactly).
- **KPIs**: `pending_approvals` (already-existing brain KPI), approval turnaround time.
- **State transitions**: `content_planned → approved` or `content_planned → lost`.
- **Founder approval**: **required, always** — this is the gate itself.

### 5. Analytics (department-scoped, not the org-wide Analytics department)

Important scoping note: the Business Blueprint's own execution order lists a full, cross-engine **Analytics** department as a later, separate build (step 5, after Affiliate). This section is **not** that. It's a narrow reuse of the existing `KPIRegistry`/`Reporter` machinery, scoped only to this department's own goals — reading `revenue_<goal_id>`/`cost_<goal_id>` (recorded automatically by the existing `kpi_intake` pipeline once real execution exists) and populating the "Affiliate conversions" line the Blueprint's own KPI table already lists as currently untracked. No new asset is required to do this narrow job; a full standalone Analytics department remains a separate, later decision.

- **Inputs**: `revenue_<goal_id>`/`cost_<goal_id>` KPI history for this department's goals.
- **Outputs**: a period-scoped performance summary (clicks/conversions/revenue/ROI per opportunity) — feeds the Strategist next.
- **KPIs**: the department-specific metrics defined below.
- **State transitions**: `approved → active` (being observed) → `won` (real, verified revenue realized) or `lost` (never converted).
- **Founder approval**: none — pure observation, no action taken.

### Strategist (already built — no new design needed)

Zero new work here. The moment real `revenue_<goal_id>`/`cost_<goal_id>` data exists for an Affiliate goal, the already-built, already-tested `SimpleStrategist` blends founder estimates against it and reallocates priority exactly as it already does for every other goal — this was proven end-to-end with Recruitment this session and needs no department-specific logic at all.

---

## Workflow

```
CEO Brain            — founder creates the Goal (horizon="short", a Cash Engine)
   ↓
Market Intelligence   — discovers an affiliate opportunity (future Research provider)
   ↓
Affiliate Manager     — evaluates it: proceed or reject
   ↓
Content Planner       — drafts the content plan + MAYA Studio brief
   ↓
Founder Approval      — reversible=False task, routed through existing RiskPolicy
   ↓
Analytics             — observes real performance once approved work executes
   ↓
Strategist            — reallocates priority using existing, already-built logic
```

Every arrow above is a `category`-tagged `Task` under the same `Goal`, dispatched through the existing `Delegator`/`Registry` mechanism — no new orchestration primitive, matching the standing constraint not to modify `atlas.core` or `CEOBrain`'s core loop.

---

## State Machine

**Superseded by `AFFILIATE_OPPORTUNITY_MODEL.md` (Mission 002)** — that document defines the authoritative, more detailed 8-stage lifecycle (`Discovered → Qualified → Selected → Content Planned → Approved → Published → Tracking → Completed`, plus `Lost` from any non-terminal stage) along with the full `Opportunity`/`Product`/`Campaign` data model. The simpler 6-stage sketch originally here is intentionally not repeated, to avoid the two documents quietly drifting apart.

---

## KPI Definitions

| KPI | Meaning | Source |
|---|---|---|
| `revenue_<goal_id>` / `cost_<goal_id>` | Already-existing convention; auto-recorded by `kpi_intake` once real execution produces a number | Existing mechanism, reused unchanged |
| Opportunities discovered | Count per period, by source | Market Intelligence |
| Evaluation proceed-rate | Opportunities evaluated → proceeded vs. rejected | Affiliate Manager |
| Content plans produced | Count per period | Content Planner / MAYA Studio |
| Approval turnaround | Time from `pending_founder_approval` to resolution | Founder Approval (reuses existing `pending_approvals` KPI) |
| Affiliate conversions | Real conversions once tracked — this is the exact line item the Business Blueprint's Section 9 already lists as untracked | Analytics (department-scoped) |
| Pipeline by stage | Count of opportunities at each state-machine stage | Analytics, mirroring Recruitment's existing `by_stage` summary |

---

## Future Expansion Roadmap

Not built now, per explicit instruction — listed only so the shape is visible:
- Real `AffiliateOpportunitySource` (needs an approved, named source — same open blocker as Recruitment's provider).
- Real evaluation rubric for Affiliate Manager (see Missing Pieces).
- Real content execution once MAYA's core capability is built (unblocks Content Planner's output actually being usable).
- The full, cross-engine Analytics department (separate from this department-scoped reuse).
- Real payment/conversion tracking (still no channel in ATLAS exposes real cost data except Recruitment — this department inherits that same limitation until a real integration exists).
