# ATLAS Affiliate Opportunity Model — Mission 002

Design only — no production code. This refines and supersedes the simpler placeholder state machine sketched in `AFFILIATE_DEPARTMENT.md`'s "State Machine" section; that document should be read as pointing here for the authoritative lifecycle.

Every design choice reuses a pattern that already ships: `Opportunity.goal_id`/`task_id` precise attribution (built for Recruitment this session), the founder-estimate/measured-data blending philosophy (built for `Goal`), and `RiskPolicy`'s existing four-axis fail-closed gate (not a new risk system).

---

## Three Entities

### Product

The durable, reusable catalog record — mirrors the role `EmployerDemand` plays for Recruitment. Many Opportunities can reference the same Product over time (re-evaluated later, or re-run after a successful first campaign).

| Field | Type | Notes |
|---|---|---|
| `id` | str | |
| `name` | str | |
| `vendor` | str | who runs the affiliate program |
| `category` | str | business taxonomy (e.g. `software`, `digital_course`, `physical_good`) — distinct from `Task.category`, which is a dispatch mechanism, not a business classification |
| `commission_structure` | dict | `{"type": "percentage"\|"flat"\|"recurring", "rate": float, "cookie_window_days": int}` |
| `audience_fit_notes` | str | founder's judgment on whether this is genuinely useful for MAYA's audience — directly enforces the standing `atlas-value-ladder` principle: L4 affiliate recommendations must be "genuinely useful only, disclosed, zero inventory," never interchangeable inventory |
| `source` / `source_id` | str, nullable | which Market Intelligence provider surfaced it, reusing Research's existing provider-tagging convention |
| `created_at` | str | |

### Opportunity

The pipeline object — this is what moves through the 8-stage lifecycle. Structurally, this is Recruitment's `Opportunity` pattern applied to affiliate discovery: same precise-attribution discipline, same `history` list, same terminal-`lost`-from-anywhere rule.

| Field | Type | Notes |
|---|---|---|
| `id` | str | |
| `goal_id` | str, nullable | **set once at creation, never rewritten** — identical rule to Recruitment's `Opportunity.goal_id`, for the identical reason: precise KPI attribution with no fallback |
| `task_id` | str, nullable | same rule as above |
| `product_id` | str | FK to Product |
| `source` | str | denormalized from Product/discovery event |
| `category` | str | denormalized from Product at discovery time — Product remains the source of truth if it ever changes later |
| `commission` | dict | **a snapshot** of the Product's commission terms *at discovery time* — deliberately not a live dereference, so a decision already made isn't silently invalidated if the real program's terms change later |
| `estimated_conversion` | float, nullable | founder/Market-Intelligence estimate, explicitly provisional — same "provisional, not fact" status as `Goal.founder_estimate`, and the same natural candidate for confidence-blending against real tracked conversions once this opportunity reaches `Tracking`/`Completed` |
| `competition` | str/float | judgment-only, no measured counterpart exists — same category as `Goal`'s `scalability`/`automation_potential`/`long_term_strategic_value`, which stay founder-judgment forever by design |
| `content_difficulty` | str/float | judgment-only, same category as above |
| `priority` | int | opportunity-level ranking; **not** wired to a scoring algorithm in this design — see Integration section for the natural future extension |
| `risk_notes` | str | a **summary/notes field only** — the actual risk *gate* is not reinvented here (see Approved stage); this exists for founder-facing context, not a parallel gating mechanism |
| `founder_approval_status` | str | `not_yet_submitted` \| `pending_approval` \| `approved` \| `rejected` — **derived from the linked Task's own status at the Approved stage**, never independently mutated, to avoid two sources of truth for the same fact |
| `stage` | str | the 8-stage lifecycle value, or `lost` |
| `history` | list[dict] | `{at, stage, reason}`, identical shape to Recruitment's |
| `created_at` / `updated_at` | str | |

### Campaign

Created once an Opportunity reaches **Content Planned** (not later) — the execution/tracking artifact, distinct from the Opportunity's decision pipeline. **Has no independent status field** — its lifecycle position is always read from its parent Opportunity's `stage`; keeping two overlapping state machines would be a real correctness risk, not a stylistic preference.

| Field | Type | Notes |
|---|---|---|
| `id` | str | |
| `opportunity_id` | str | FK, 1:1 for this design; nothing structurally forbids a future re-run spawning a second Campaign against the same Opportunity |
| `product_id` | str | denormalized for convenience |
| `content_brief` | dict/str | the MAYA Studio planning artifact from `AFFILIATE_DEPARTMENT.md` — the connective tissue between Content Planner's output and execution |
| `published_at` | str, nullable | **stays unset** until a future mission builds real publishing — the field exists in the model now so nothing needs to change shape later, exactly like `revenue_generated` sat honestly at `0.0` in Revenue's channels before this session wired real attribution around it |
| `tracking_link` / `tracking_id` | str, nullable | placeholder — real conversion attribution needs a real affiliate-network integration, explicitly out of scope here |
| `results` | dict, nullable | clicks/conversions/revenue once real tracking exists — never fabricated in the interim |
| `created_at` | str | |

---

## Lifecycle

```
Discovered → Qualified → Selected → Content Planned → Approved → Published → Tracking → Completed
     ↓            ↓           ↓              ↓             ↓           ↓          ↓
                                            Lost (reachable from any non-terminal stage)
```

| Stage | What happens | Who | Entity created/touched | KPIs |
|---|---|---|---|---|
| **Discovered** | Market Intelligence (Research's affiliate provider) surfaces a Product; Opportunity created | Market Intelligence | Product (created or reused, deduplicated by the same source/source_id mechanism built for Research's providers), Opportunity created | Opportunities discovered per period, by source, by product category |
| **Qualified** | Coarse pass/fail filter — commission terms exist and are nonzero, no conflicting existing promotion, passes the "genuinely useful" audience-fit bar | Affiliate Manager | Opportunity stage updated | Qualification pass-rate; disqualification reasons (via `history`) |
| **Selected** | Chosen among Qualified candidates using `estimated_conversion`/`competition`/`content_difficulty`/`commission`; `priority` set | Affiliate Manager | Opportunity `priority` set | Opportunities selected per period; average priority score; selection-to-qualification ratio |
| **Content Planned** | Content brief drafted | Content Planner / MAYA Studio (planning only) | **Campaign created**, holding `content_brief` | Content plans produced; average Qualified→Content Planned turnaround |
| **Approved** | Founder approval gate — reuses `RiskPolicy` directly: the underlying Task is `reversible=False`, routed to `pending_approval` automatically, resolved via the existing `atlas brain approve`/`reject` | Founder Approval | `founder_approval_status` derived from the Task's resolution | Approval turnaround time; approval rate |
| **Published** | A **human, founder-executed action** — posting the content — same category as Recruitment's founder-executed outreach/placement: tracked by the software, never performed by it, since no publishing automation exists | Founder (tracked, not automated) | `Campaign.published_at` set | Opportunities published per period; Content Planned→Published turnaround |
| **Tracking** | Real performance observed — for now, via manual `atlas brain kpi record` entry, exactly matching the honest current state of the rest of the system (no automatic real tracking exists anywhere yet) | Analytics (department-scoped) | `Campaign.results` populated as real data arrives | Clicks/conversions tracked; `revenue_<goal_id>`/`cost_<goal_id>` if/when a Campaign-aware `kpi_intake` extension exists (not built here) |
| **Completed** | Terminal — tracking window elapsed or founder marks done | Analytics | Final `Campaign.results` | Final revenue/cost/ROI for this opportunity; completed-vs-lost ratio |
| **Lost** | Terminal, reachable from any non-terminal stage above, with a reason recorded — identical to Recruitment's `mark_lost` | Any stage's owner | `history` entry | Lost-rate by stage (diagnoses *where* opportunities die, not just how many) |

---

## Integration with CEO Brain and Strategist

**Attribution**: `Opportunity.goal_id`/`task_id` follow the exact precise-attribution rule proven for Recruitment this session — set once, never rewritten, no fallback. This is what would let a future `kpi_intake` extension attribute a Campaign's real revenue/cost to the correct Goal with the same zero-cross-contamination guarantee already tested for Recruitment's two-goal case.

**Brain-mediated auto-advance**: `Discovered → Qualified → Selected → Content Planned` are all internal, non-founder-gated transitions — the natural candidate for a `revenue_affiliate`-category continuation mechanism structurally identical to `pipeline_advance.py`'s `advance_recruitment_pipeline`, built this session for Recruitment. `Approved` stops auto-advance completely, same as Recruitment's `proposal_ready`/`active` gates. `Published`/`Tracking`/`Completed` are human/external-action-driven and were never candidates for brain-mediated auto-advance in the first place, since they require real-world action the software doesn't perform.

**Strategist**: no new logic required at all. Once real `revenue_<goal_id>`/`cost_<goal_id>` data exists — aggregated across every `Completed` Opportunity under a goal, the same summation pattern already used for Recruitment's multiple-won-opportunities case — the existing, already-tested `SimpleStrategist` blends founder estimates against it and reallocates priority exactly as already proven end-to-end.

**Risk**: deliberately not reinvented. `Opportunity.risk_notes` is a founder-facing summary field only; the actual gating decision at `Approved` runs through `RiskPolicy`'s existing four-axis evaluation on the underlying Task, the same mechanism every other irreversible action in ATLAS already goes through.

**Future extension noted, not built**: `Opportunity.priority` and `estimated_conversion` are natural candidates for the same founder-estimate/measured-data confidence-blending mechanism already built for `Goal` — scoring individual opportunities within a goal, not just goals against each other. Not designed further here; flagging it as the shape a future mission could take.
