# ATLAS Business Blueprint

This is the business operating manual for ATLAS — the CEO operating system for a real company, not a demo. It governs *what the business does and why*; `CLAUDE.md` governs *how the code is structured*. Where this document references a system component, the reference is accurate as of this session (134/134 tests passing) and should be re-verified against the code if this document is read much later — this document can go stale exactly like any other record of system state, and should be treated with the same skepticism.

---

## 1. Mission

Generate sustainable real-world revenue while simultaneously building long-term digital assets.

These are not sequential goals and not in tension by accident — the operating philosophy and principles below exist specifically to run both at once without either starving the other.

---

## 2. Business Philosophy

- **Cash Engine finances the Asset Engine.** Near-term revenue-generating activities (Section 5) fund the time/capital cost of building long-term assets (Section 6) — the Asset Engine is not expected to self-fund its own construction.
- **Asset Engine increases future cash generation.** The point of building MAYA is not brand-building for its own sake — it exists to expand the set of Cash Engines available later (an audience that trusts MAYA becomes a distribution channel for every future offer, including future Cash Engines not yet invented).
- **Every decision must be based on measurable ROI and real KPI data.** Not projected ROI, not narrative conviction — the same evidence-gating discipline already built into `atlas.brain.improvement` and `atlas.brain.strategist` at the code level. Section 10 restates that principle as a business rule so it governs founder decisions too, not just the software's.

---

## 3. Business Principles

- **Build only what creates measurable value or measurable learning.** If a build task produces neither a real KPI improvement nor a real answer to an open question, it isn't ready to build yet.
- **Real data always overrides assumptions.** A founder estimate is a starting point, not a conclusion — the moment real measured data exists, it takes precedence (this is the exact mechanism `atlas.brain.valuation.blended()` already implements in code: founder estimates smoothly lose influence as real KPI readings accumulate).
- **Missing data is preferable to fabricated data.** An unmeasured metric should stay visibly blank, never filled in with a plausible-looking placeholder. A gap is honest; a fabricated number is a silent lie that gets trusted later.
- **Protect long-term assets without starving short-term cash flow.** Neither engine is allowed to cannibalize the other — this is the operational meaning of "Cash Engine finances the Asset Engine, Asset Engine increases future cash generation."
- **Every department must justify its existence with measurable business outcomes.** No department is built because it seems like what a "real company" should have — Section 4's Operational/Planned split and Section 11's execution order both exist to enforce this.

---

## 4. Current Architecture Status

### Operational Today

- **Recruitment** (real) — complete pipeline, real revenue arithmetic, founder-approval gates, real KPI attribution. The only engine capable of producing a real, non-placeholder dollar right now.
- **Strategist** — the capital-allocation layer: ranks goals by cash-flow/strategic-value score, reallocates priority, blends founder estimates against measured data over time.
- **KPI Registry** — persistent, named business/operational metric time series backing everything measurable in this document.
- **KPI Intake** — the automatic pipeline that attributes real revenue/cost from Recruitment (and, where present, Revenue-channel executions) to the correct goal, fail-closed on anything unrecognized.
- **CEO Brain** — the orchestration substrate: plan → prioritize → risk-gate → delegate → monitor (`tick()`), plus the strategic review cycle (`review()`) that runs the Strategist, evaluates past structural bets, and produces the executive report.

### Planned

- **Affiliate** — channel exists in code as a placeholder only; no real affiliate program connected.
- **Stock Images** — maps to the `content_assets` channel, also placeholder-only; no real generation or licensing pipeline.
- **TikTok** — no corresponding component exists yet in any form; ownership is an open architectural decision (Section 7).
- **MAYA** — registered as Digital Asset #1, but real technical capability (LLM/content generation) is a stub. Nothing in Section 6's responsibilities can happen for real until this is built.
- **Analytics** — not started; explicitly on hold until there's enough real activity to analyze.
- **CFO** — not started; would own real cost-tracking beyond what Recruitment already provides.
- **Marketing** — not started; explicitly on hold until MAYA has something real to promote.

This split is the single most important fact in this document to keep current: everything in "Operational Today" can be trusted to produce real data; everything in "Planned" cannot, and any KPI associated with a Planned item is a target, not a measurement, until it moves up.

---

## 5. Initial Cash Engines

| Priority | Engine | Mechanism | Track | Status |
|---|---|---|---|---|
| **1** | **Recruitment** | Placement commissions | **Business development only** — no code needed | Ready to execute today |
| **2** | **Affiliate Marketing** | Referral commissions | **Build required** — the channel is a code placeholder; BD effort here has nothing real to sell yet | Not ready |
| **3** | **Stock Image Sales** | Licensing AI-generated image assets | **Build required** — same placeholder status as Affiliate | Not ready |
| **4** | **TikTok / Short-form content monetization** | Creator monetization, brand deals, traffic to other offers | **Build required, and ownership undecided** — see Section 7 | Not started |

The "Track" column exists so priority order is never mistaken for a single kind of work: item 1 is a business-development task waiting on a human; items 2–4 are engineering tasks waiting on a build decision. Scheduling BD effort against 2–4 before they're built would produce nothing to sell.

---

## 6. Asset Engine — MAYA

**Purpose:** Become the public face of ATLAS.

**Responsibilities:**
- Create educational content
- Build audience trust
- Publish videos
- Collect feedback
- Build community
- Promote ATLAS products naturally

**Current status:** MAYA is registered as Digital Asset #1, but her real technical capability is a stub — `MayaAgent.run()` acknowledges delegated work without performing it. This is the single blocker standing between the Asset Engine and any of the six responsibilities above actually happening. It does not block Section 5's Cash Engines, which is precisely why they're sequenced ahead of her in Section 11.

### MAYA Success Metrics

Responsibilities describe what MAYA is for; these metrics define how her progress against them will actually be measured. No targets are set here — these are the metrics to instrument, not yet the bars to clear:

- **Published videos** — count of videos published across MAYA's channels within a period.
- **Audience growth** — net change in follower/subscriber count across MAYA's owned channels over a period.
- **Engagement rate** — (likes + comments + shares) relative to views, per video or per period.
- **Qualified inbound leads** — count of inbound contacts or signups attributable to MAYA's content that meet a qualification bar (the bar itself is a future decision, not defined here).
- **Conversions influenced** — count and/or dollar value of Cash Engine conversions (affiliate sales, product sales, recruitment inquiries) traceable back to MAYA's content or audience as the originating touchpoint.
- **Audience retention** — rate at which MAYA's audience returns or remains engaged over a rolling window (returning-viewer rate, community member retention).

None of these are live KPIs today — they're defined now so they can be wired into `KPIRegistry` the moment MAYA's real capability exists, consistent with Section 3's "never fabricate KPIs" and Section 4's Operational/Planned distinction.

---

## 7. TikTok Ownership (Open Architectural Decision)

This remains undecided in code and should stay flagged as such until explicitly resolved.

**Option A — TikTok as a Revenue channel.** Modeled like `affiliate`/`digital_product`/`content_assets`: a discrete, dispatchable execution unit with its own attributable revenue. Consistent with the existing channel-plugin pattern, but creates a real attribution problem — if a TikTok video drives an affiliate sale, it's ambiguous whether that revenue belongs to "TikTok" or to "Affiliate."

**Option B — TikTok as MAYA's primary distribution channel.** Modeled as an extension of MAYA's existing "publish videos" responsibility (Section 6) — an ongoing content operation, not a one-shot monetizable execution. Direct TikTok monetization (Creator Fund payouts, brand deals) would be tracked as its own KPI/goal under MAYA, while conversions TikTok *drives* are attributed to whichever Cash Engine actually captures the sale (Affiliate, a digital product, a recruitment inquiry).

**Recommendation: Option B.** TikTok content is top-of-funnel distribution, not a self-contained monetization mechanism — this matches the value-ladder principle that free, persona-driven content is the foundation everything else is built on, and it avoids Option A's double-attribution problem entirely by not trying to make TikTok itself a revenue-attribution unit. Direct platform payouts (Creator Fund, brand deals) are the one piece of real, directly-attributable TikTok revenue and should still get their own KPI — but as a line item under MAYA's operation, not a Revenue-channel plugin.

---

## 8. First Revenue Milestones

| Milestone | Criterion |
|---|---|
| **1** | First verified $1 revenue |
| **2** | First verified $100 cumulative revenue |
| **3** | First verified $1,000 cumulative revenue |
| **4** | Three consecutive months with positive net profit |
| **5** | Legal business entity established and all revenue flows migrated |

**"Verified" is defined precisely**: observed via a real `revenue_<goal_id>` KPI reading recorded through the actual `kpi_intake` pipeline (Section 4), never a founder estimate, a manual assertion, or a projection. Milestones 1–3 are cumulative dollar thresholds crossed in `KPIRegistry` history; Milestone 4 requires `revenue_<goal_id>` minus `cost_<goal_id>` to stay positive across three consecutive monthly reporting periods (`atlas brain report --period monthly`).

**Milestone 5 is categorically different from 1–4.** It's a one-time human/legal action, not a KPI threshold — it is not reachable through any `atlas brain` command and will never show up automatically in a report. It should be tracked explicitly as a standing human-only item so it doesn't silently stall the way any human-only gate can if left implicit.

---

## 9. Business KPI

Track: Revenue, Profit, Investment, ROI, Lead generation, Placements, Affiliate conversions, Image sales, TikTok growth, Community growth.

Grouped by what kind of thing each one measures, since Analytics (Section 4, Planned) will eventually need this distinction to design around:

**Portfolio-level financial KPIs** — Revenue, Profit, Investment, ROI
**Per-engine operational KPIs** — Lead generation, Placements, Affiliate conversions, Image sales
**Audience/distribution KPIs** — TikTok growth, Community growth

**Current instrumentation status** (per Section 3's "never fabricate KPIs" — this table exists so nobody assumes a KPI is live when it isn't):

| KPI | Status today |
|---|---|
| Revenue | **Live** for Recruitment- and Revenue-driven goals (`revenue_<goal_id>`, auto-recorded via KPI Intake) |
| Investment (cost) | **Live for Recruitment only** (`cost_<goal_id>`, derived from real bill-rate/pay-rate spread). No other engine exposes real cost data yet, and none should be fabricated to fill the gap |
| Profit | **Not separately tracked** — computable as revenue minus cost wherever both are live (Recruitment only, today) |
| ROI | **Not yet computed as a named KPI** — the Strategist derives ranking scores internally, but a plain "ROI" figure isn't recorded on its own yet |
| Lead generation | **Not tracked** — no `leads_<engine>` KPI exists yet for any engine |
| Placements | **Computed but not KPI-recorded** — Recruitment's own stage summary already produces this count internally; it isn't fed into `KPIRegistry` as a named series yet |
| Affiliate conversions | **Not tracked** — the affiliate channel has no conversion-tracking of any kind, placeholder or real |
| Image sales | **Not tracked** — same as above, for Stock Images |
| TikTok growth | **Not tracked** — no TikTok integration exists |
| Community growth | **Not tracked** — no community platform integration exists |

Reading this table honestly: today, ATLAS can *measure* real business performance for exactly one engine (Recruitment). Everything else on this list is aspirational until the corresponding engine is built for real.

---

## 10. Strategic Rules

- **Never fabricate KPIs.**
- **Never fabricate costs.**
- **Fail closed.** When a measurement is missing, absent, or unrecognized, treat it as *unknown*, never as zero or as a default guess — the same rule already enforced in `RiskPolicy`, the Strategist's value blending, and KPI Intake's shape-dispatch.
- **Measure everything.** Every engine should have a defined KPI path *before* it's declared operational — Section 9's table is the tracker for this.
- **Optimize according to evidence.** Reallocate effort/priority based on real, measured KPI deltas — not narrative conviction, not sunk cost, not which engine "feels" more promising.
- **Cash funds assets.** Capital and time spent building the Asset Engine should be justified by Cash Engine performance already realized, not borrowed against a hoped-for future.
- **Assets create future cash.** The Asset Engine's payoff is measured in *future* Cash Engine expansion, not in isolation.

---

## 11. Recommended Execution Order

1. Recruitment — business development only, no build required
2. Affiliate — build required
3. Stock Images — build required
4. MAYA — build required; unlocks Section 6's responsibilities and resolves the TikTok ownership question in practice
5. Analytics — build required; deferred until items 1–4 produce enough real data to analyze
6. CFO — build required; deferred until there's real financial activity across more than one engine to track
7. Marketing — build required; deferred until MAYA (step 4) has something real to promote

This order runs Cash Engines before the Asset Engine, and defers Analytics, CFO, and Marketing until there's real activity worth measuring, financing, and promoting — consistent with Section 3's principle that every department must justify its existence with measurable business outcomes, and the standing instruction not to start Marketing or Analytics before that condition is met.

---

## 12. Roadmap

**Phase A — First real revenue.** Exit criterion: Milestone 1 (Section 8).

**Phase B — Validate repeatability.** Prove Recruitment (and any built-out Cash Engine) can produce revenue more than once, not as a single lucky event. Exit criterion: Milestone 2, and at least two independent revenue events contributing to it.

**Phase C — Scale successful engines.** Invest further only in engines with real, measured ROI — per Section 10, never on projection. Exit criterion: Milestone 3.

**Phase D — Build MAYA into a recognizable digital brand.** Begins once Cash Engines are self-sustaining enough to fund it (Section 2's "Cash Engine finances the Asset Engine"). Exit criterion: Section 6's MAYA Success Metrics showing real, sustained activity — not targets set here, but the metrics themselves must be live and moving.

**Phase E — Expand into additional business units.** Only after Milestone 4 (three consecutive profitable months) and the Asset Engine is producing measurable audience/distribution value — mirrors the standing portfolio principle that no new asset gets recommended before the current pilot has validated the operating system with real revenue.

---

## Document Maintenance

This document owns "current state of the business," the same way `HANDOFF.md` owns "current state of the build" and `CLAUDE.md` owns "current state of the architecture." Revisit it at each `atlas brain report --period monthly`, and any time an item moves between Section 4's Operational Today and Planned lists — that migration is the single most important edit this document will ever need.
