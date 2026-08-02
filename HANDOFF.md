# ATLAS — Session Handoff

**Last verified against actual code:** 2026-07-23 (test suite run, file timestamps checked)
**Test suite state:** 356/356 passing (`python -m pytest -q`)
**Git:** no repository exists in this project — nothing to commit; all work is saved directly to disk.

This document is the continuation point for the next Claude Code session. Read this before making changes. See also `CLAUDE.md` (architecture/code structure) and `docs/ATLAS_BUSINESS_BLUEPRINT.md` (business state) — all three can go stale independently; cross-check against the code before trusting a specific claim.

---

## 0. Why this document was rewritten

The previous version of this file was written mid-session at 11:30, and documented 134 passing tests. Work continued the *same day* through ~17:02 without this file being updated — by the time the next session picked it up, the actual codebase had grown to 319 passing tests and roughly two-thirds of `src/atlas/` (an entire affiliate/content/publishing pipeline, plus a full operator console/REPL/app layer) was undocumented here. That gap was caught and closed in this pass — see `CLAUDE.md`'s "Architecture: atlas.assets" and "Architecture: operator interface" sections for the full technical detail; this file focuses on build state and what's next.

**Lesson for future sessions**: update this file at the end of *every* work session that touches code, not just the one that felt like "the" session boundary — a single calendar day produced eight sequential missions here, and none of the later ones updated this file.

---

## 0-b. Session update — 2026-07-23: Digistore24, first real product, Creative Agent

Priority shifted this session, per explicit instruction: stop refining internal revenue estimation, get ATLAS's **first real affiliate dollar**. Summary, newest first:

- **Built `creative_agent`** (new asset) — drafts a deterministic creative brief (shot list) for any `approved_for_marketing` opportunity, and `attach_real_asset()` records a real founder-produced image/video (no generation happens in ATLAS; that's still a separate future decision). Wired as the seventh brain-side bridge (`creative_agent_advance.py`).
- **Publishing Gateway now fail-closed refuses to queue without a real creative asset** — a soft gate (never even attempts a build) plus a hard gate (`build_publish_package()` rejects if `creative_assets.status != "ready"`), matching its existing "re-verify independently" style for editorial verdict/stage/disclosure. `media_references` now carries the real attached reference instead of hardcoded placeholders.
- **A real, pre-existing bug found and fixed**: `editorial_review_advance._trigger_fix()`'s dedup logic counted fix-request tasks all-time instead of scoping to the current content generation — a founder-rejection regeneration (which resets `editorial_cycles` to 0) could get permanently stuck never receiving a fresh fix request. Fixed by scoping the count to tasks created after the opportunity's most recent `content_packaged` transition. Regression test added.
- **Root-cause fix**: generated marketing copy was using `category` (the provider's product-type classification, e.g. `"software"`) as the audience-facing niche in templates. Added `AffiliateOpportunity.marketing_niche` (separate field); `content_factory/generator.py` and `publishing_gateway/builder.py`'s hashtag logic both now prefer it, falling back to `category` when unset.
- **Digistore24 integration**: `AffiliateOpportunity` gained `provider`/`provider_product_id`. `validate_provider_link()` (`affiliate_department/models.py`) accepts two real link shapes for `digistore24` — the generic `digistore24.com/redir/...` domain, or a vendor's own custom sales-page domain carrying the affiliate id in a strict, parsed (not substring) non-empty `aff=` query/fragment parameter. `AffiliateIntelligenceAgent.intake_real_product()` (not `AffiliateDepartmentAgent` — see the dead-end note below) is the real intake path; CLI: `atlas affiliate product add`.
- **A real architecture bug caught by live testing, not by re-reading docs**: real-product intake was originally wired into `AffiliateDepartmentAgent` (`discovered → selected → content_planned`), whose founder-approval gate is a dead end — `content_factory` only ever picks up `stage == "selected_for_marketing"`, which *only* `AffiliateIntelligenceAgent` sets. The two are separate, parallel pipelines sharing one store. Corrected before it shipped.

**Live state as of this session's end** — first real campaign, sitting at the founder's discretion:
- Goal `goal-e3ec71a1b9f3` ("KetoDNA affiliate revenue (Digistore24)")
- Opportunity `aopp-f4afdf53555a` (KetoDNA, provider `digistore24`, real link, real niche "Keto Diet / Weight Loss", real attached image at `C:\Users\User\Downloads\1768961030344-gwgp6l.png`)
- Publish package `pub-309a51629d33` — status **`QUEUED`**, real image/hashtags/tracking link verified in it. **Not published.** `atlas publishing mark-published`/`atlas affiliate revenue record` are real, existing CLI commands (built in an earlier session, still unused for real) waiting on the founder's own real-world posting action.
- New CLI surface this session: `atlas affiliate product add` (+ `--provider`/`--provider-product-id`), `atlas creative attach`.

**Founder's stated next-session priorities (verbatim, not yet started)**:
1. Creative Marketing Agent (beyond today's brief-only `creative_agent` — likely richer creative strategy/variation generation)
2. Landing Page Intelligence
3. Better TikTok creatives and videos (today's Creative Agent has no real generation — still the deferred external-provider decision)
4. Better conversion flow

---

## 1. Current project state

Everything below is real, tested, and wired into `CEOBrain.tick()` unless stated otherwise.

### Core CEO substrate (stable, pre-dates this session's work)

`atlas.core` (manifest-driven asset registry), `atlas.brain`'s planner/prioritizer/delegator/risk/monitor/improvement/reporter/`CEOBrain`, and the Strategist (capital allocation: blends founder estimates against measured KPI data, reallocates `Goal.priority`/`status` in `review()`, never in `tick()`). Full detail in `CLAUDE.md`.

### Revenue-producing today

- **Recruitment** (`recruitment_workforce`) — the *only* engine producing real, non-placeholder revenue and cost. Full pipeline with founder-approval gates, real bill-rate/pay-rate arithmetic, precise `Opportunity.goal_id`/`task_id` attribution (set once, never rewritten).
- **Revenue channels** (`revenue` asset: affiliate/digital_product/content_assets) — real dispatch wiring, but every channel's `execute()` still returns `revenue_generated: 0.0` (an honest placeholder, not fabricated) and **no channel exposes a cost signal at all**. Still open — see §4.

### The affiliate/content pipeline (built this session, real and tested, produces zero external revenue by design)

Built across several same-day "missions" (numbered where the source docs number them):

1. **`affiliate_department`** (Mission 003) — 4-stage opportunity pipeline (`discovered → selected → content_planned`, `lost`), 3 fixed placeholder candidates, deterministic scoring, drafts a content brief, stops at founder approval. No publishing, no external APIs.
2. **`affiliate_intelligence`** — a separate ranking pipeline (`discovered → researched → ranked`) over the same shared opportunity store; every opportunity gets ranked, founder picks which to pursue.
3. **`content_factory`** — deterministic template-based content package generation (hooks/headlines/CTAs/platform suggestions/content ideas), handles editorial fix requests and founder "request changes" (2-strike abandonment).
4. **`editorial_review`** — 7 deterministic QA checks before any package reaches the founder; pass/revision/reject with a 2-cycle revision cap.
5. **`publishing_gateway`** — the single controlled boundary to the outside world; independently re-verifies, builds a `PublishPackage`, gates on one more founder approval, stops at `QUEUED`. No external platform call exists anywhere in this codebase.

Each stage has a matching brain-side "pipeline advance" bridge (`src/atlas/brain/*_advance.py`) that nudges internal stages forward and creates exactly one founder-approval task per gate — six now exist (Recruitment's original, plus one per stage above), all following the same shape, deliberately not unified into one engine.

**Design-only, never implemented**: Mission 004 (`docs/FOUNDER_ASSISTED_BUSINESS.md`) — a platform-registration workflow gated by `RiskPolicy`'s existing axes, plus a `founder_explanation: dict` field on `Task`. Explicitly scoped as "design only, no code changes this mission" and nothing after it picked the implementation back up. Confirmed absent from `src/` as of this rewrite.

### Operator interface (built this session, no preceding design doc — first code in the project to ship that way)

`src/atlas/repl.py` (line-based console), `src/atlas/app.py` (full-screen dashboard + natural-language command aliases — **this is what bare `atlas` launches**), `src/atlas/speech.py` (optional local Windows TTS/STT, best-effort, never raises), `src/atlas/brain/console.py` (shared read-only data/formatting layer all three of the above reuse). All wired through `cli.py`. Fully tested (`tests/test_app.py`, `tests/test_repl.py`, `tests/test_speech.py`, `tests/brain/test_console.py`), no TODOs or stubs found on inspection.

### Still registered metadata-only, explicitly on hold

`marketing`/`analytics`/`automation`/`cfo`/`coo` — unchanged, per the standing instruction not to build them before there's real activity to justify them.

---

## 2. Architecture decisions made across this session

Carried forward from the Strategist build (still true, unchanged):
1. The Strategist is not the `CEOBrain` orchestrator — it's the judgment layer plugged into `review()`, never `tick()`.
2. The Strategist writes only `Goal.priority`/`Goal.status`, never dispatches or creates anything.
3. Founder estimates are provisional; blended against measured KPI data with weight that grows from 0→1 as readings accumulate, never a hard cutover.
4. Short-term cash flow and long-term asset creation are scored and ranked in separate `horizon` cohorts.
5. Reallocation is auto-applied, always logged, never approval-gated (it's reversible/zero-cost/no-privileged-access by `RiskPolicy`'s own criteria).
6. Anti-thrash is structural: identical inputs across `review()` calls produce the same rank, so nothing new is ever logged.

New, established while building the affiliate/content/publishing chain:
7. **One small, asset-specific "pipeline advance" bridge per multi-stage asset, never a shared framework.** Six now exist; each is a deliberate, near-identical copy of the previous one's shape, not a generalized engine — copy-and-adapt was the explicit choice over premature abstraction.
8. **Shared opportunity storage across a whole pipeline chain, one file.** `affiliate_department`, `affiliate_intelligence`, `content_factory`, `editorial_review`, and `publishing_gateway` (for reads) all operate on the *same* `AffiliateStore`/`DEFAULT_STORE_PATH` records — deliberate, since they're stages of one lifecycle, not independent entities.
9. **Every founder-approval gate reuses the existing `RiskPolicy`/`Task(reversible=False)`/`approve()`/`reject()` mechanism, with zero bespoke gating code.** This includes multi-choice-feeling situations (which ranked opportunity to pursue) — expressed as one binary approve/reject task per candidate, not a new multi-choice primitive.
10. **`PublishingGatewayAgent` re-verifies independently rather than trusting upstream state** — it re-runs Editorial Review's own compliance check before building a package, on the principle that "the single controlled entry point to the outside world" must not just trust every upstream stage.
11. **Never write a projection into the real `revenue_<goal_id>`/`cost_<goal_id>` series.** Affiliate Department's projected KPIs (`expected_revenue_<goal_id>`, etc.) are deliberately namespaced apart from the real, `kpi_intake`-attributed series — the same class of bug (an estimate mistaken for verified data) already found and fixed once earlier this session.
12. **The operator console/REPL/app is presentation-only.** No business logic lives in `repl.py`/`app.py`/`console.py` — every command calls straight into already-existing `CEOBrain`/`Registry` methods.

---

## 3. Design rules that must not change (without explicit new user approval)

Everything from earlier sessions still holds, unchanged:
- `atlas.core` is not modified.
- MAYA is untouched and is not an agent in the orchestration sense (it's a Registry asset like any other).
- No direct agent-to-agent calls; cooperation is brain-mediated only (the one documented exception: Editorial Review dispatches a fix-request `Task` *categorized* for Content Factory — still mediated through the same `Task`/`Delegator` mechanism, not a direct call).
- Fail-closed `RiskPolicy` is unchanged.
- Recruitment's founder-approval gates are unchanged.
- **No external integrations exist anywhere in this codebase** — this now spans Research, Revenue, and the entire affiliate/content/publishing chain, not just the original scope. Publishing Gateway is the designated single future integration point when this changes.
- Manifest-driven extensibility is the only supported way to add an asset.
- The Strategist is not a Registry asset, never runs in `tick()`, and reallocation stays auto-applied/never approval-gated (all from the prior session, still true).
- `scalability`/`automation_potential`/`long_term_strategic_value` stay founder-judgment-only until a future session designs a measured proxy — do not fabricate one.

New from this session:
- **Never fabricate a KPI or a cost figure.** Restated as an explicit business rule in `docs/ATLAS_BUSINESS_BLUEPRINT.md` §10, but it governs every line of code touching `KPIRegistry` too — an unmeasured metric stays absent, never defaulted to a plausible-looking number.
- **Do not build Marketing or Analytics** until there's real activity to justify them (restated, still binding — this was the standing instruction that gated the Strategist build in the first place, and still gates these two).
- **New pipeline-advance bridges follow the existing six's shape** — do not invent a generalized "advance any asset" engine; the deliberate choice has been repeated six times now.

---

## 4. Outstanding tasks / open items (not started, flagged not solved)

Ranked by how close each is to "the obvious next step" as of this rewrite:

1. **Mission 004 (`docs/FOUNDER_ASSISTED_BUSINESS.md`)** — fully designed, explicitly deferred, never implemented, never referenced again by later work. The cleanest "designed but not built" candidate in the project.
2. **No CLI path to reactivate a paused `Goal`.** Flagged since the original Strategist handoff, still true — `atlas brain goal resume <id>` or similar.
3. **Revenue-channel cost signal.** `revenue/channels/*` still expose no cost data at all; `required_investment` for those goals stays founder-estimate-only. Small, isolated, real.
4. **MAYA's real content-generation capability.** `docs/ATLAS_BUSINESS_BLUEPRINT.md` §6 calls this the single blocker for the entire Asset Engine — large, undesigned, not a small next step.
5. **TikTok ownership** — open architectural decision, recommendation only (Option B: MAYA's distribution channel, not a Revenue channel) — see `docs/ATLAS_BUSINESS_BLUEPRINT.md` §7.
6. **No *automated* `AffiliateOpportunitySource`** — Market Intelligence (`docs/AFFILIATE_DEPARTMENT.md`) still has no automated discovery; **partially resolved this session** via manual real intake (`atlas affiliate product add`, Digistore24 only) — the founder still finds and vets each product by hand.
7. **`docs/ATLAS_BUSINESS_BLUEPRINT.md` itself needs a re-read against the code** — its §4 "Planned" list still describes Affiliate as "placeholder-only," written before the `affiliate_department`→`publishing_gateway` chain existed. The chain is real and tested but still produces zero external revenue, so neither "Operational Today" nor "Planned" cleanly describes it anymore — worth an explicit edit to that document, not done here since the user asked for `CLAUDE.md`/`HANDOFF.md` specifically.
8. **`engine_id` (multiple Goals representing one revenue engine)** — schema field only, not used by any scoring/allocation logic. Natural v2, not built.
9. **No mechanism for agents to autonomously create Goals** — still human/CLI-only.
10. **No scheduler/daemon** for `tick()`/`review()` cadence — still deferred.
11. **Pre-existing test isolation gap**: `tests/core/test_cli.py`'s asset-`Store` tests don't isolate to `tmp_path`, so running the full suite writes to the real project's `.atlas/state.json`. Harmless (gitignored), still worth fixing.

---

## 5. Assumptions and known limitations

- **`MATURITY_SAMPLE = 6`** (`valuation.py`) — placeholder constant, not tuned; revisit once real KPI cadence is known.
- **Equal-weighted scoring** (`scoring.py`) — a simple, explicitly swappable deterministic default, not a considered business judgment about which criterion matters most.
- **No real external integration exists anywhere** — every "opportunity," "product," "campaign," and "publish package" in the system is placeholder data. The entire affiliate/content/publishing chain built this session is real *code* producing zero real *revenue* until a specific, named, founder-approved integration is built for a specific platform (an explicit future decision, not implied by anything built so far).
- **No git repository** exists in this project. There is nothing to commit; all changes are already on disk.
- **This file, `CLAUDE.md`, and `docs/ATLAS_BUSINESS_BLUEPRINT.md` can each go stale independently of the others and of the code.** §0 above is a direct demonstration of how far that drift can get in a single day. Re-verify specifics (test count, which assets exist, which fields exist) against the actual code before relying on a claim here in a future session.

---

## 6. Recommended next priority — superseded by the founder's own stated agenda (2026-07-23)

No longer an open question — the founder named the next-session priorities directly (see §0-b): **Creative Marketing Agent, Landing Page Intelligence, better TikTok creatives/videos, better conversion flow.** All four sit downstream of this session's Creative Agent + Gate and the first real (still-`QUEUED`, unpublished) KetoDNA campaign — start by reading §0-b's "Live state" before touching anything, since there's a real campaign sitting mid-flight awaiting explicit founder approval to actually post.

Earlier candidates, now lower priority but still real and unaddressed: Mission 004 (designed, never implemented), the paused-goal CLI resume command, the Revenue-channel cost signal (see §4), MAYA's real content-generation capability (blocks the whole Asset Engine per the Business Blueprint, but is a large, undesigned mission on its own — likely the eventual dependency for "better TikTok creatives/videos" above, since real video generation needs *some* real model/API decision either way).
