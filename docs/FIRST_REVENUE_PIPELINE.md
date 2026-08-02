# ATLAS First Revenue Pipeline — Mission 003

The first executable slice of the Affiliate Department (`AFFILIATE_DEPARTMENT.md`, `AFFILIATE_OPPORTUNITY_MODEL.md`) — placeholder data only, no external APIs, no publishing, no affiliate registration, no internet access. Stops safely at the founder-approval gate.

## What was built

| File | Purpose |
|---|---|
| `src/atlas/assets/affiliate_department/models.py` | `AffiliateOpportunity` — a deliberately reduced slice of the full Product/Opportunity/Campaign model: one entity, four stages (`discovered → selected → content_planned`, plus `lost`). Qualified+Selected are collapsed into one evaluation pass; Published/Tracking/Completed don't exist in code at all yet. |
| `src/atlas/assets/affiliate_department/scoring.py` | `score_opportunity()` — one deterministic, fully transparent formula: `estimated_conversion × commission × (1-competition) × (1-content_difficulty)`. |
| `src/atlas/assets/affiliate_department/store.py` | Self-contained JSON persistence (`.atlas/affiliate_department.json`), same pattern as `WorkforceStore`. |
| `src/atlas/assets/affiliate_department/agent.py` | `AffiliateDepartmentAgent` — exactly one internal stage advances per `run()` call, same invariant `RecruitmentAgent` documents. |
| `src/atlas/assets/affiliate_department/manifest.toml` | New asset id **`affiliate_department`** — deliberately distinct from the pre-existing `affiliate` id (a metadata-only `revenue_channel` entry owned by `revenue`, unrelated to this department). |
| `src/atlas/brain/affiliate_pipeline_advance.py` | Brain-side bridge, mirroring `pipeline_advance.py`'s shape for Recruitment — two responsibilities, described below. |
| `src/atlas/brain/ceo.py` | One new call in `tick()`, same integration point as the Recruitment bridge. |

## Why an asset id collision had to be avoided

`affiliate` was already registered (metadata-only, `kind="revenue_channel"`, `owner="revenue"`) — its real logic lives inside `revenue/channels/affiliate.py`, unrelated to this department. Reusing that id would have silently repurposed an existing org-chart entry. The new department is `affiliate_department`; its dispatch category is `affiliate_pipeline` — distinct from Revenue's existing `revenue_affiliate` category, so the two systems never collide at the `Delegator` category-matching layer.

## Pipeline stages, as implemented

| Stage | Who | What actually happens |
|---|---|---|
| **Discovered** | Market Intelligence | First `run()` call with no existing opportunities creates exactly 3 fixed placeholder candidates — no network access, no external source. |
| **Selected** (collapses Qualified+Selected) | Affiliate Manager | Second `run()` call scores all 3 via `score_opportunity()`, promotes the highest to `selected` with a recorded reason (`"highest score X among 3 evaluated candidates"`), transitions the other two to `lost` with their own recorded reasons. |
| **Content Planned** | Content Planner / MAYA Studio (planning only) | Third `run()` call drafts a content brief for the selected opportunity only: `audience`, `hook`, `headline`, `cta`, `platform`, `content_ideas`. Never invokes MAYA's real (stubbed) capability, never publishes anything. |
| **Founder Approval** | *(brain-mediated, not the asset itself)* | `affiliate_pipeline_advance.py` records four projected KPIs (below) and creates exactly one `reversible=False` Task. `RiskPolicy` routes it straight to `pending_approval` — it never reaches `Delegator` at all. **Pause. No automatic continuation.** |

## A real regression found and fixed along the way

Adding `affiliate_department` (which sorts alphabetically before `maya`) broke two pre-existing tests that relied on `Delegator`'s unmatched-category fallback picking `maya` by alphabetical accident. Two fixes, not one:

1. **Real correctness fix**: `AffiliateDepartmentAgent.run()` now no-ops (doesn't touch its own state) when dispatched a task whose category isn't `affiliate_pipeline` — an unrelated task landing here via fallback must never silently advance this department's pipeline as a side effect. This is a latent gap `RecruitmentAgent` already shared (never triggered, because its id happens to sort after `maya`), not something new introduced by this mission.
2. **Test correction**: the two affected tests asserted `assigned_asset_id == "maya"` specifically, when what they actually meant to verify was "an unmatched task still finds a capable fallback asset." Updated to assert that property instead of a specific asset id.

## Reuse discipline (per the explicit requirements)

- **Goal/Task architecture**: unchanged — this pipeline is entirely `Task`s under one `Goal`, dispatched through the existing `Delegator`.
- **RiskPolicy**: unchanged — the founder-approval gate is a plain `reversible=False` Task, not a new gating mechanism.
- **KPI Registry**: unchanged — projected KPIs use the existing `KPIRegistry.record()`/`.latest()` API.
- **Founder Approval**: unchanged — resolved via the existing `atlas brain approve`/`reject` CLI, no bespoke approval method (unlike Recruitment's `approve_outreach`/`approve_commitment`, which wasn't needed here since a plain Task already covers it).
- **Strategist reporting**: unchanged — `brain.review()` and `Reporter.summarize()` are called as-is; no parallel report engine was built.
- **No duplicate workflow engine**: the only new orchestration code is one small bridge function following the exact shape of the existing Recruitment one, plus one new call in `tick()` — not a new engine.
- **No duplicate state machine**: `discovered/selected/content_planned/lost` is an explicit, intentional reduction of the 8-stage model in `AFFILIATE_OPPORTUNITY_MODEL.md`, not a competing one.

## Projected KPIs (never real, never written to the real KPI series)

| KPI | Formula | Why this formula |
|---|---|---|
| `expected_ctr_<goal_id>` | fixed placeholder constant `0.03` | No real platform data exists to estimate this from yet — stated plainly as an assumption. |
| `expected_conversion_<goal_id>` | `= opportunity.estimated_conversion` | Direct passthrough of the founder/Market-Intelligence estimate. |
| `expected_revenue_<goal_id>` | `estimated_conversion × commission_per_conversion × 500` | `500` is a named, stated assumption (`ASSUMED_MONTHLY_LEADS`) — an illustrative monthly lead-volume figure, not derived from any real traffic data. |
| `risk_score_<goal_id>` | `(competition + content_difficulty) / 2` | A simple average of the two judgment-only inputs — deliberately unrelated to `RiskPolicy`'s own four-axis compliance gate, which is a separate concern. |

**Critical safeguard**: these are written to `expected_*_<goal_id>` and `risk_score_<goal_id>` — never to `revenue_<goal_id>`/`cost_<goal_id>`, which are reserved for real, `kpi_intake`-attributed measurements. Writing a projection into that series would let the Strategist's confidence-blending mechanism mistake an estimate for verified data — the same class of bug already found and fixed once this session (the founder-estimate-defaulting-to-zero issue).

## What happens after approval — explicitly out of scope

Calling `atlas brain approve` on the founder-approval task today has no further automated effect: nothing in this mission implements Published/Tracking/Completed. That's a deliberate boundary, not an oversight — "no publishing" was an explicit constraint. A future mission would need to define what "approved" transitions to once real publishing exists.
