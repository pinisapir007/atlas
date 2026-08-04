# ATLAS Architecture Reference

**Maintenance note:** this document owns *the engine layer's architecture, engine responsibilities, execution flow, and current implementation status*. It is the fourth companion document alongside `CLAUDE.md` (owns *how the code is structured*), `docs/ATLAS_BUSINESS_BLUEPRINT.md` (owns *what the business does and why*), and `HANDOFF.md` (owns *current state of the build*, for session-to-session continuation). Update this file whenever a major engine is completed, changes status, or a new one is added — it deliberately does not re-explain what those three files already own; it references them instead. Like the other three, this file can go stale — cross-check against the code (`python -m pytest -q`, actual file contents) before trusting a specific claim.

*Last verified against the repository at commit `c0862b1` (1006/1006 tests passing).*

---

## 1. Scope of this document

ATLAS's foundational architecture (`atlas.core`, `atlas.brain`'s CEO loop, the original category-level Decision Engine, the affiliate/content/publishing pipeline, `atlas.campaign`/`atlas.influencer`/`atlas.brand`, the Execution Orchestrator, Finance, Success Laws, the operator interface) is documented exhaustively in `CLAUDE.md` — see its `## Architecture: atlas.core`, `## Architecture: atlas.brain`, and `## Architecture: atlas.assets` sections onward. This document does not restate any of that; it describes the **new engine layer** built on top of it (Resource Discovery, Multi-Source Opportunity Discovery, Time Awareness, Decision Engine Integration, Business Execution Planning), how the two layers connect, and the system's current implementation status at the architecture level.

For business rationale, see `docs/ATLAS_BUSINESS_BLUEPRINT.md`. For what to pick up in the next session, see `HANDOFF.md`.

---

## 2. The new engine layer

### 2.1 Resource Discovery Engine V1

**Responsible for:** discovering founder-approved local resources (files/folders) — metadata only, never anything unapproved.

| Piece | Module | Status |
|---|---|---|
| Normalized shape + provider contract | `atlas.integrations.base.Resource` / `ResourceProvider` | Production-ready |
| Real provider | `atlas.integrations.local_folder_provider.LocalFolderProvider` | Production-ready |
| Future-provider placeholders | `atlas.integrations.resource_provider_placeholders` (Google Drive, OneDrive, Dropbox, NAS, Gmail) | Placeholder — always return `None`, zero real API calls |
| Approval record | `atlas.brain.resource_allowlist.ResourceAllowlist` | Production-ready |
| Orchestration + diffing | `atlas.brain.resource_discovery_engine.scan_resources()`, `ResourceScanState` | Production-ready |
| Queryable index | `atlas.brain.resource_index.ResourceIndex` | Production-ready |

**Safety model:** default-deny, enforced independently at three layers (allow-list, provider, engine) — no single bug can defeat it. No method anywhere reads file content or writes/deletes/moves anything (structurally proven by test, not just documented).

**CLI:** `atlas resources approve-folder|revoke-folder|list-approved|scan|index`

### 2.2 Multi-Source Opportunity Discovery Engine V1

**Responsible for:** discovering, scoring, and ranking real revenue opportunities across multiple affiliate sources.

| Piece | Module | Status |
|---|---|---|
| Normalized shape + provider contract | `atlas.integrations.base.Opportunity` / `OpportunityProvider` | Production-ready |
| Real provider | `atlas.brain.digistore24_opportunity_discovery.Digistore24SignalProvider` | Production-ready, but *live-blocked* — see §4 |
| Future-provider placeholders | `atlas.integrations.affiliate_provider_placeholders` (Amazon Associates, AliExpress, CJ, Impact, ShareASale) | Placeholder — always `None` |
| Merge/dedupe/rank engine | `atlas.brain.opportunity_discovery_engine.discover_opportunities()` | Production-ready |
| Category/subject-level evidence ranking (older, foundational layer; see `CLAUDE.md`'s "Opportunity Discovery V1" section) | `atlas.brain.opportunity_ranking` | Production-ready, feature-flagged (`ATLAS_OPPORTUNITY_DISCOVERY_V1`) for its auto-bootstrapping path only |

**Deduplication:** exact `(provider, external_id)` match only — deliberately never fuzzy/cross-provider title matching, since no shared product-identity standard exists across real affiliate networks.

**CLI:** `atlas affiliate digistore24 marketplace|marketplace-entry|discover-opportunities`, `atlas brain discover-opportunities`

### 2.3 Time Awareness Engine V1

**Responsible for:** being the single source of real time (never a clock UI) for every other subsystem.

| Piece | Module | Status |
|---|---|---|
| Central time authority | `atlas.brain.time_service.TimeService` | Production-ready |
| Utilities (elapsed/remaining/deadline/timeout/age/scheduling-math) | Same module | Production-ready |
| Real dependency | `tzdata` (Windows-conditional) | Production-ready — verified necessary |
| Task timing | `Task.started_at`/`finished_at`/`duration`/`execution_time`, set automatically by `Task.transition()` | Production-ready |

**Explicitly deferred by design** (generic primitives are ready; nothing above builds them yet): reminders, campaign scheduling, business hours, recurring jobs, calendar integrations, holiday awareness.

### 2.4 Decision Engine Integration V1

**Responsible for:** a deterministic, explainable **EXECUTE/WAIT** verdict for one specific task, reading the three engines above.

| Piece | Module | Status |
|---|---|---|
| Requirements contract | `TaskExecutionRequirements` | Production-ready |
| Three independent checks | `check_resources_available`, `check_opportunity_available`, `check_time_remaining` | Production-ready |
| Combinator | `evaluate_task_readiness()` → `ExecutionReadiness` | Production-ready |

Not the same thing as `atlas.brain.decision_engine` — see §5.

**CLI:** `atlas decide task <task_id> [--require-resource]... [--opportunity-category] [--min-confidence] [--deadline] [--min-remaining-seconds]`

### 2.5 Business Execution Planning V1

**Responsible for:** connecting the *existing* category-level Decision Engine to all three completed engines to produce a complete, read-only plan **before any real action**.

| Piece | Module | Status |
|---|---|---|
| Plan object | `BusinessExecutionPlan` (deliberately not `ExecutionPlan` — see §5) | Production-ready |
| Builder | `atlas.brain.business_execution_planning.build_execution_plan()` | Production-ready |

Every field (selected opportunity, required resources, estimated execution time, task dependency order, expected outcome, confidence score, risk assessment, success criteria) is a direct read of an existing mechanism — no new scoring model. Never dispatches, writes, or publishes.

**CLI:** `atlas decide plan <category> [--require-resource]... [--estimated-duration-seconds]`

---

## 3. Information flow between engines

```
Founder approves a local folder
        |
        v
Resource Discovery      ResourceAllowlist -> scan_resources() -> ResourceIndex
        |
        | (queried, never re-scanned)
        v
Opportunity Discovery -----------> KnowledgeBase (Findings)
(Digistore24 + 5                          |
 placeholders)                            | (read, not re-fetched)
        |                                 v
        |                    atlas.brain.decision_engine.decide()  [EXISTING, unmodified]
        |                                 |
        |                    Decision(verdict, confidence, risks)
        v                                 v
Time Awareness  --------------->  Business Execution Planning
(TimeService)                      build_execution_plan()
                                           |
                                           v
                                  BusinessExecutionPlan
                              (future modules execute here —
                               not built in V1: dispatch,
                               Campaign creation, publishing)
```

**Separately**, Decision Engine Integration V1 (`evaluate_task_readiness()`) draws on the same three engines to answer a narrower, *task-scoped* EXECUTE/WAIT question — a sibling consumer, not a step in the chain above.

**Persistence boundary:** `ResourceIndex`/`ResourceScanState`/`ResourceAllowlist` are the only durable stores in this layer (`.atlas/resource_*.json`). `Opportunity`/`ExecutionReadiness`/`BusinessExecutionPlan` are all computed fresh on every call — nothing about them is cached or considered permanently true, the same discipline the original Decision Engine already established.

---

## 4. Naming collisions deliberately avoided

| Pair | Difference |
|---|---|
| `atlas.brain.decision_engine.decide()` vs. `atlas.brain.decision_engine_integration.evaluate_task_readiness()` | The first answers *"is this whole category worth investing in, given evidence"* (category scope). The second answers *"can this specific task execute right now, given what's really available"* (task scope; reads the first as one input). |
| `atlas.orchestrator.models.ExecutionPlan` vs. `atlas.brain.business_execution_planning.BusinessExecutionPlan` | The first is a **live, stateful, mutated-in-place** record of one Campaign's actual execution steps. The second is a **read-only planning artifact** produced before any Campaign exists — never instantiates real `ExecutionStep` objects. |

---

## 5. Current implementation status

### Completed (built, tested, real)
- Resource Discovery Engine V1
- Multi-Source Opportunity Discovery Engine V1 (Digistore24 real; 5 affiliate networks reserved)
- Time Awareness Engine V1
- Decision Engine Integration V1
- Business Execution Planning V1

*(For the pre-existing operational layer's completion status — asset registry, CEO loop, original Decision Engine, affiliate/content/publishing pipeline, Campaign/Influencer/Brand, Execution Orchestrator, Finance, Success Laws, operator interface — see `CLAUDE.md`, all production-ready as of this writing.)*

### In progress / real but incomplete
- **Digistore24 marketplace discovery** is connected and correctly handles errors, but the real account's `listMarketplaceEntries` call returns zero entries (Digistore24 scopes that endpoint to vendor accounts) — no real product data has flowed through this specific pipeline yet.
- **The new engine layer is not wired into `CEOBrain.tick()`.** `scan_resources()`, `discover_opportunities()`, `evaluate_task_readiness()`, and `build_execution_plan()` are all real and CLI/library-callable today, but none run automatically on the production tick the way the older `advance_opportunity_discovery()`/`advance_decision_driven_campaigns()` bridges do. This is the largest concrete gap between "built" and "autonomous" for this layer.

### Future roadmap (named, not started)
- Real implementations for the 5 affiliate placeholder providers and the 5 resource placeholder providers — each a separate, credentialed decision.
- Reminders, campaign scheduling, business hours, recurring jobs, calendar integrations, holiday awareness (Time Awareness's stated extension points).
- A module that actually *executes* a `BusinessExecutionPlan` — deliberately not built in V1.
- Wiring the new engine layer into `CEOBrain.tick()` for full autonomy.
- Everything already listed as deferred in `CLAUDE.md`'s own "Explicitly deferred" section (`ContentPublisher`, `MarketSignalProvider`, `marketing`/`analytics`/`automation`/`cfo`/`coo`, etc.) remains deferred, unchanged by this layer.
