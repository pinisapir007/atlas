# New Business Creation Methodology

**Owns:** the fixed, mandatory process ATLAS follows before creating any new business, brand, Digital Influencer, or company. Established 2026-08-09 (founder directive), after the Maya Health missions proved — and then were explicitly challenged and re-proven — that a niche/positioning decision can only be trusted once demand, supply, competitors, regulation, and objective comparison have all been checked directly, never assumed from a prior project.

## Why this exists

The first Maya Health niche decision was reached honestly but was anchored: research queries were already framed around "personalized nutrition / keto" because that was the category the pre-existing KetoDNA campaign happened to sit in. The conclusion turned out to hold up under real, independent scrutiny — but only after two rounds of explicit challenge forced a genuine comparison against alternatives, including a live scan of real affiliate marketplaces (Digistore24, ClickBank) and real demand-side research (search volume, consumer priority ranking, documented frustration with the status quo). See `.atlas/knowledge.json` findings tagged `niche comparison: *`, `affiliate marketplace scan: *`, and `demand: *` for the real evidence trail this method produced.

The lesson made structural: **a niche is never selected because a product already exists for it.** The product may be *evidence* once real research is underway, but never the starting point.

## The 13 steps

Every step must produce a real, cited finding (or an honest "no data found") before the next step begins. Skipping a step, or substituting assumption for research at any step, is not permitted.

1. **Demand research** — what real problems people are searching to solve, what questions are asked most, what's genuinely frustrating them about existing answers. Search volume/trend data, consumer surveys, forum/community signal, peer-reviewed evidence where it exists. Never inferred from supply.
2. **Supply research** — what real products/services already exist to serve that demand, at what quality.
3. **Competitor research** — who already occupies this space, how saturated it is, whether there's real room for a new, differentiated voice.
4. **Regulatory research** — what compliance/legal/medical-claims risk applies to this category, and whether it's compatible with what the asset can honestly claim to be (e.g., an AI-curated, non-medical account cannot safely operate in categories requiring licensed-professional authority).
5. **Affiliate market research** — a real, live scan of actual affiliate platforms and their real top offers in the category (not secondary "best programs" articles alone) — commission structure, AOV, refund-rate signals, and critically, whether real products actually embody the intended differentiation or are generic. Digistore24's own API `listMarketplaceEntries` is vendor-scoped and returns nothing useful for a pure-affiliate account — real category research goes through the public marketplace/blog listings instead; this is documented so the same dead end isn't rediscovered next time.
6. **Product research** — the specific real products a candidate niche could realistically be built around, evaluated for quality and fit against the asset's own non-negotiable values (e.g., no product requiring fabricated personal testimony).
7. **Niche comparison** — every real candidate niche assembled side by side against the same criteria, defined *before* any research results are seen (to prevent the criteria themselves from being retrofit to favor a preferred answer).
8. **Objective ranking** — score each niche honestly on the criteria from step 7, marking genuine gaps as "no data found" rather than inventing a number.
9. **Niche selection** — the niche is chosen, with the full reasoning trail (steps 1–8) visible and citable, not asserted.
10. **Brand building** — only now does brand foundation work begin (positioning, DNA, mission, vision, values, tone, visual identity) — see the Maya Health brand documents for the template this follows.
11. **Business model building** — revenue sources, staging, business targets per stage.
12. **Roadmap building** — the digital-asset build order and the phased execution plan, each item justified by real dependency logic and real system-state checks (what already exists in ATLAS vs. what requires a new build decision), not convenience.
13. **Only then, execution begins.**

## The standing counterfactual test

Before finalizing any niche selection reached with an existing product already in hand, ATLAS must explicitly answer: *would this same conclusion be reached if that product did not exist at all?* If the honest answer is no, the process restarts from step 1 for the category itself, not just the product.

## Where this is enforced today

This is a **methodology ATLAS's reasoning follows**, not (yet) a hard, code-level gate — no code in `atlas.brain` currently blocks creating a Campaign/Brand/Influencer until these 13 steps are provably complete. It is applied the same way the CEO Decision Protocol is: as a standing operating discipline for whoever is reasoning as ATLAS, verified in each case by the real, cited evidence trail it produces (durable `Finding`s in `KnowledgeBase`, referenceable later via `recall()`). Encoding it as an actual `RiskPolicy`-style structural gate is a real, separate, future decision — not assumed to be needed until a real case shows the discipline being skipped in practice.
