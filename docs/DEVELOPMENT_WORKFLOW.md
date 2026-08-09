# Development Workflow

**Owns:** how ATLAS itself works — as a software engineer and as a CEO — across every Mission, permanently. Established 2026-08-09 (founder directive), codifying the discipline that was already being followed in practice across every real mission this session (Vision V1, Hearing V1, Hands V1, Memory V1, Learning V1, the Maya Health missions) rather than inventing a new process from scratch. No Mission may be closed without passing every phase below.

## 1. When a Mission is considered started

A Mission starts only when the founder issues an explicit directive — a named Mission, or a clear, unambiguous instruction. ATLAS does not self-initiate Missions. Restating or re-scoping an existing instruction is not a new Mission start; it's a continuation.

## 2. When a Mission is considered ended

A Mission reaches **"ready for review"** only once every phase in Section 3 is complete for real, evidenced work — never asserted from memory of intent. It reaches **"closed"** only once the founder has reviewed and confirmed it, explicitly, in a later message. These are two different states, and the gap between them is deliberate: every Mission in this project's real history has ended with an explicit wait for founder approval before the next Mission began — "ready for review" is not permission to proceed to the next Mission.

## 3. The fixed phases of every Mission

1. **Understand the real ask.** Re-read the instruction precisely; note explicit constraints and boundaries stated (e.g. "no code," "no UI," "don't build until I approve").
2. **Check real system state first.** What already exists, what's missing — verified directly (`grep`, reading real files, querying real `.atlas/` data), never assumed. Building something that already exists is a real failure mode, not a neutral inefficiency (see `feedback_gap_closure_methodology.md`, `feedback_new_business_methodology.md`).
3. **Research, when real-world facts are needed.** Real tools only — `WebSearch`/`WebFetch`/direct API calls. Never fabricated, never inferred from training data alone when a live check is possible.
4. **Plan/design for anything non-trivial**, tracked via `TodoWrite` so partial progress is never silently lost.
5. **Build**, following the codebase's own established conventions: reuse existing capability before adding anything new, no new dependency without real justification, no speculative abstraction beyond what the Mission actually requires.
6. **Test.** Real, mocked unit tests for every new capability — no live external calls inside the automated suite.
7. **Run the full suite**, not just the new tests — `python -m pytest -q`. Regressions in unrelated code are still this Mission's problem if this Mission caused them.
8. **Live-validate for real**, with no mocks, whenever a Mission claims a capability actually works — this has been a hard, non-negotiable requirement throughout (screen capture, real API calls, real browser actions, real financial records). A capability that has only ever been exercised by a mock is not yet proven.
9. **Update documentation** — see Section 6.
10. **Update memory** — see Section 6.
11. **Commit**, scoped precisely — see Section 7.
12. **Report status to the founder honestly**, with real evidence, and explicitly wait for approval before starting the next Mission.

## 4. Self-review before completion

Before presenting a Mission as ready for review: re-read the actual diff, not a memory of what was intended. Re-run the full suite fresh, not just the tests written for this Mission. Re-verify claims against freshly re-checked real state, not against what was true when the Mission started (state can have changed mid-Mission — this project has caught real drift this way more than once). Apply the same counterfactual discipline `docs/NEW_BUSINESS_METHODOLOGY.md` established for business decisions to engineering decisions too: would this same conclusion/implementation hold up if re-derived independently, or does it depend on an assumption that was never actually checked?

## 5. How Review happens

The founder is the reviewer of record. Every Mission's status report presents real, evidenced work — what was built, what was tested, what was live-validated, with the actual evidence shown, not summarized as "done." For architecture/strategy Missions, the report is typically a durable, referenceable document (an artifact, or a `docs/` file) rather than only chat text, so the decision trail survives past the conversation. A `/code-review` pass is available as a real, separate tool for deeper scrutiny on complex or high-risk changes — not mandatory for every Mission, but available whenever the risk profile warrants it.

## 6. When documentation and memory updates are mandatory

**Documentation** (`CLAUDE.md`, `docs/*.md`) must be updated whenever a Mission changes a *real, durable architectural fact*: a new capability exists, a new standing principle is established, a new entity/department concept is introduced, or a real, previously-documented gap is closed. Not for internal implementation detail that doesn't change what a future reader needs to know.

**Memory** (the cross-session memory system) must be updated whenever a Mission produces a standing behavioral correction, a confirmed working preference, or an ongoing project-state fact the next session needs to know without re-deriving it. Project-state memories are expected to decay and get superseded; feedback-type memories (standing principles) are expected to persist indefinitely unless explicitly revised.

## 7. When commit is mandatory

Every Mission that produces real, working code ends in a real commit — scoped precisely to that Mission's own files, verified via `git status`/`git diff --stat` *before* staging, explicitly excluding any pre-existing unrelated uncommitted work found in the working tree. This has been followed exactly, every time, across every Mission in this project's real history. A commit only happens *after* the full suite passes and live validation (where applicable) succeeds — never before. A Mission that produces no code (pure research, planning, or architecture work with no real file changes) does not require a commit; a Mission that produces real `docs/` files does.

## 8. When push to GitHub is mandatory

**Never automatically.** A real remote exists (`origin` → `github.com/pinisapir007/atlas`), and as of this document, local `main` is 81 real commits ahead of `origin/main` — every Mission in this project's history has committed locally but none has pushed. This is the honest, current state, not a gap to silently close. Push is a shared, externally-visible action (matching this project's own general safety discipline for actions with real, outward blast radius) and requires the founder's explicit, direct request each time — the same standing rule that already governs force-push, `git reset --hard`, and every other action that touches shared or remote state. Local commit discipline (Section 7) is deliberately kept independent of the push decision, so real work is never blocked on a push authorization that hasn't been asked for yet.

## 9. How rollback works when a Mission fails

Because commit only happens after real validation succeeds (Section 7), a failed Mission is, by construction, almost always caught *before* it ever reaches a commit — the real fix is diagnose, correct, retry, not rollback. When a real regression is discovered later in *already-committed* work (a later Mission finds a bug an earlier one introduced), the fix is a new, corrective commit — never amending or rewriting history, matching this project's standing Git Safety Protocol exactly. For a genuinely severe, already-pushed error (not yet a real scenario, since nothing has been pushed — see Section 8), `git revert` is the safe tool of record, never `git reset --hard` on shared history, and never without the founder's explicit authorization first.

## 10. How ATLAS preserves development history over years

Several distinct, durable records, each serving a different purpose — not one mechanism trying to do all of it:

- **Git commit history** — the permanent, real engineering record of what changed, when, and why (every commit message in this project states the real reasoning, not just the diff).
- **`CLAUDE.md`** — the living architecture reference, explicitly maintained to be cross-checked against real code rather than trusted as permanently accurate.
- **`docs/*.md`** — deeper, topic-scoped permanent references (this file, `NEW_BUSINESS_METHODOLOGY.md`, `ATLAS_ARCHITECTURE_REFERENCE.md`, `ATLAS_BUSINESS_BLUEPRINT.md`) for material too detailed to keep in `CLAUDE.md` itself.
- **`HANDOFF.md`** — current build state, specifically for session-to-session continuation.
- **The cross-session memory system** — standing behavioral corrections and ongoing project state that must survive a session boundary without being re-derived from scratch.
- **`KnowledgeBase`/`DecisionLog`** (`.atlas/knowledge.json`, `.atlas/decisions.json`) — the durable *business* decision and evidence history (distinct from engineering history: this is what ATLAS itself learned and decided as a company, not what its own codebase changed).

These five are deliberately not merged into one mechanism — engineering history, architecture reference, session handoff, cross-session behavioral memory, and business decision history are different questions with different audiences and different staleness profiles, the same "don't collapse genuinely different concerns into one store" discipline already applied everywhere else in this codebase (e.g. `Ledger` staying separate from `KPIRegistry`, `DecisionLog` staying separate from `KnowledgeBase`).
