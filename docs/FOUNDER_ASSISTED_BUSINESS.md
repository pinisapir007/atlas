# ATLAS Founder-Assisted Business Launch — Mission 004

Design only. No code changes this mission. Every mechanism below reuses something that already exists and ships — the one finding worth stating up front is that it *all* already fits, with zero new gating machinery required.

---

## The core finding: RiskPolicy already expresses every stop-condition

The six trigger conditions this mission lists — legal consent, account ownership, identity verification, payment information, tax information, clicking an external confirmation button — map onto `RiskPolicy`'s existing four axes with no gaps and no new mechanism:

| Trigger condition | Existing `Task` field |
|---|---|
| Legal consent | `involves_legal_agreement=True` |
| Account ownership | `involves_privileged_access=True` |
| Identity verification | `involves_privileged_access=True` |
| Payment information | `involves_privileged_access=True` |
| Tax information | `involves_privileged_access=True` |
| Clicking an external confirmation button | `reversible=False` |

Any Task carrying one or more of these flags is *already* routed straight to `pending_approval` by the existing, unmodified `RiskPolicy.evaluate()` — fail-closed, exactly as it already works for every other gated task in ATLAS. Nothing new needs to be built to make ATLAS "stop" — it already does. What's missing is the *explanation* a founder needs at that stop, which is the one real gap this mission closes.

## The one genuine gap: structured founder explanation

Today's founder-approval tasks (Mission 003) carry a plain `description: str` — enough for "approve this campaign," not enough for "here's which platform, why this is required, what information you need, which button to press, and what happens after." Recommended addition for the eventual implementation mission: an additive `founder_explanation: dict | None = None` field on `Task`, holding exactly those five named pieces. Additive and optional, same pattern as every other schema growth this session (`source_opportunity_id`, `founder_estimate`, `horizon`, `engine_id`) — nothing existing breaks, and it's what lets a future CLI/report render this consistently across every gate in every future business template, not just affiliate marketing.

---

## Integration Design

- **CEO Brain**: unchanged. This workflow is `Task`s under a `Goal`, dispatched through the existing `Delegator` — same `tick()` loop, no new orchestration cycle.
- **Strategist**: unchanged. Once real KPI data exists for a founder-assisted-business goal, `SimpleStrategist` blends and reallocates exactly as already proven for Recruitment and the Affiliate Department.
- **RiskPolicy**: unchanged — see above. This is the load-bearing reuse of the whole mission.
- **Founder Approval**: unchanged. Every gate below is a plain `Task` resolved via the existing `atlas brain approve`/`reject` — no bespoke approval method, same choice already made for the Mission 003 pipeline.
- **KPI Registry**: unchanged — new KPI names, same `KPIRegistry.record()`/`.latest()` API.
- **Review system**: unchanged — `CEOBrain.review()`/`Reporter.summarize()` produce the periodic report; no parallel reporting engine.

**Two layers, not one mechanism**: the workflow splits into a *platform/account* layer (new: Discovery → Platform Evaluation → Registration Preparation → Founder Approval → Account Ready) and an *opportunity/campaign* layer (**not new** — this is the exact Mission 003 `AffiliateDepartmentAgent` pipeline, renamed to fit this workflow's vocabulary: Product Discovery ≈ `discovered`, Campaign Planning ≈ `selected`, Content Planning ≈ `content_planned`). The second layer isn't rebuilt here; it's reused wholesale, now sitting downstream of a real, founder-approved account instead of running with no account context at all.

---

## Workflow Diagram

```
Discovery (of affiliate platforms — placeholder candidates, no external source)
   ↓
Platform Evaluation (score candidates: commission structure, approval difficulty, reputation)
   ↓
Registration Preparation (draft what the founder will need to submit — no real submission)
   ↓
Founder Approval  ◄── STOP: legal consent + account ownership + tax info, bundled into one gate
   ↓
Account Ready (asserted once the founder confirms they completed registration for real)
   ↓
Product Discovery ─┐
Campaign Planning   ├── reuses the Mission 003 AffiliateDepartmentAgent pipeline unchanged
Content Planning ──┘
   ↓
Founder Approval  ◄── STOP: publishing is not reversible, same gate Mission 003 already built
   ↓
Ready for Publishing (terminal for this mission — Publishing itself is not implemented)
```

---

## State Transitions

| From | To | Trigger | Founder gate? |
|---|---|---|---|
| *(none)* | Discovered | Placeholder platform candidates created | No |
| Discovered | Evaluated | Platform Evaluation scores all candidates | No |
| Evaluated | Registration Prepared | Best candidate selected; registration requirements drafted | No |
| Registration Prepared | *(waiting)* | Founder Approval task created | **Yes — Gate 1** |
| Registration Prepared | Account Ready | Founder approves | *(resolves Gate 1)* |
| Registration Prepared | Rejected | Founder rejects (e.g., platform terms unacceptable) | *(resolves Gate 1, terminal)* |
| Account Ready | Product Discovered | Mission 003 pipeline begins, now account-scoped | No |
| Product Discovered | Selected | Same Affiliate Manager evaluation as Mission 003 | No |
| Selected | Content Planned | Same Content Planner/MAYA Studio step as Mission 003 | No |
| Content Planned | *(waiting)* | Founder Approval task created | **Yes — Gate 2** |
| Content Planned | Ready for Publishing | Founder approves | *(resolves Gate 2, terminal — Publishing not implemented)* |
| Content Planned | Rejected | Founder rejects the campaign | *(resolves Gate 2, terminal)* |

`Evaluated` can also terminate at `Rejected` if no candidate platform clears a minimum bar — fail-closed, matching the "don't force a bad choice" principle already applied to Affiliate Manager's product evaluation.

---

## Required Founder Approvals

**Gate 1 — Registration Approval** (after Registration Preparation, before Account Ready)
- **Platform**: whichever candidate Platform Evaluation selected (a real, named platform — still an open decision; this document uses placeholder examples only, same open blocker already raised twice this session for Research's real discovery source).
- **Why required**: real affiliate registration requires legal consent to the platform's terms (legal consent), creating a real login (account ownership), and typically submitting a tax form — none of which ATLAS can or should do on the founder's behalf.
- **What information is needed**: business name/email for the account, tax ID for the required tax form, and the founder's own review/acceptance of the platform's terms.
- **Exactly what button to press**: the platform's own real "Sign Up"/"Apply" button, then "I Agree" on its terms, then submit the tax form.
- **What ATLAS does after approval**: marks this goal's platform as Account Ready and proceeds autonomously into Product Discovery, reusing the Mission 003 pipeline exactly.

**Gate 2 — Publishing Approval** (after Content Planning, before Ready for Publishing)
- Identical in spirit to Mission 003's existing gate: publishing is not reversible and is public-facing.
- **What ATLAS does after approval**: nothing further automated — Published/Tracking/Completed remain unimplemented, an explicit boundary carried over unchanged from Mission 003.

---

## Future Automation Opportunities

Split honestly into two categories, since conflating them would overstate what could ever be automated:

**Permanently human-only, by design, regardless of future integrations**: legal consent, account ownership, identity verification, payment information, tax information. These aren't "not automated yet" — they're not automatable in principle without ATLAS holding founder credentials/legal authority it should never hold.

**Temporarily human-only, until a future, explicitly-approved integration exists**: clicking a publish button, submitting a registration form. Once a real API integration is built for a *specific, named* platform (a separate, explicit future decision — same standing constraint as every "no external APIs yet" boundary this session), these steps could shrink to "founder pre-authorizes once, ATLAS executes within that authorization" — but that is a deliberate future mission, not implied by anything built here.
