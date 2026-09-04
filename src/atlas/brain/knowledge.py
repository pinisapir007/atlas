from dataclasses import asdict
from pathlib import Path

from atlas.brain.models import (
    FUTURE_ITEM_RESOLUTIONS,
    FUTURE_ITEM_STATUSES,
    FUTURE_ITEM_TYPES,
    Claim,
    Finding,
    FutureItem,
    SuccessLaw,
)
from atlas.brain.store import BrainStore, JSONFileStore, update_store

_EMPTY = {"findings": {}, "success_laws": {}, "future_items": {}, "claims": {}}


class KnowledgeBase:
    """Durable record of everything ATLAS's Intelligence layer has
    discovered, independent of whether any given finding ever became a Task
    or a Goal — that lifecycle lives in BrainMemory, a different concern,
    the same separation BrainMemory already draws against
    atlas.core.store.JSONStore.

    Storage is delegated to a BrainStore (default: JSONFileStore, atomic
    writes), reusing the exact abstraction BrainMemory uses rather than
    inventing a second one — a future live data connector's findings land
    here through the same save_finding() call a human-curated or
    AI-researched seed does today.

    Also holds `SuccessLaw`s (added 2026-08-03) — generalized business
    principles extracted from real evidence, the same Intelligence-layer
    concept as a Finding one level more synthesized, so it lives in the
    same store rather than a new, parallel one. `.get("success_laws", {})`
    reads tolerate an older knowledge.json saved before this field existed
    — no migration needed.

    Also holds `FutureItem`s (added 2026-08-15, Future Capability Recall +
    Gates Phase 1) — a durable, evidence-linked record of a deliberately
    deferred decision, one synthesis level above a SuccessLaw the same way
    a SuccessLaw is one level above a Finding. `.get("future_items", {})`
    reads tolerate an older knowledge.json saved before this field existed
    — no migration needed, same precedent as success_laws.

    Also holds `Claim`s (added 2026-08-15, Cognitive Foundation) — the
    general relationship/attribute/hypothesis record; see Claim's own
    docstring in models.py for the full design. `.get("claims", {})` reads
    tolerate an older knowledge.json saved before this field existed —
    same no-migration precedent as success_laws/future_items.
    """

    def __init__(self, path: Path = Path(".atlas/knowledge.json"), store: BrainStore | None = None):
        self._store = store if store is not None else JSONFileStore(path)

    def _read(self) -> dict:
        data = self._store.read()
        return data if data is not None else {"findings": {}, "success_laws": {}, "future_items": {}, "claims": {}}

    def _write(self, data: dict) -> None:
        self._store.write(data)

    def save_finding(self, finding: Finding) -> None:
        def mutate(data):
            data["findings"][finding.id] = asdict(finding)

        update_store(self._store, self._read(), mutate)

    def findings(
        self, category: str | None = None, provider: str | None = None, subject: str | None = None
    ) -> list[Finding]:
        """Filtered Knowledge Retrieval seam (2026-08-15, Foundation Design
        approved): optional, additive equality filters over the exact
        fields real call sites already filtered by, by hand, in at least
        five separate places (confidence.py, opportunity_ranking.py,
        decision_engine.py, discovery/exploration_gate.py, explain.py,
        intelligence_workflow.py) before this existed. `market` was
        deliberately NOT added -- a real grep across this codebase found
        `Finding.market` is only ever read/reported, never filtered on
        anywhere, so adding it here would be a speculative parameter, not
        one justified by real usage.

        No filter given (the default, `None`) means exactly the original,
        unfiltered behavior -- every existing caller with no args is
        completely unaffected. Multiple filters combine with AND. Result
        order is preserved (dict insertion order, unchanged from before).

        Deliberately does NOT do: ranking, relevance scoring, semantic
        search, a query-object abstraction, an explanation/audit layer, or
        anything storage-technology-specific -- see docs/
        BUSINESS_BRAIN_AGENTIC_OS_SPECIFICATION.md's Cognitive Growth
        Foundation section for why this seam is intentionally this
        narrow."""
        results = [Finding(**f) for f in self._read()["findings"].values()]
        if category is not None:
            results = [f for f in results if f.category == category]
        if provider is not None:
            results = [f for f in results if f.provider == provider]
        if subject is not None:
            results = [f for f in results if f.subject == subject]
        return results

    def get_finding(self, finding_id: str) -> Finding:
        raw = self._read()["findings"].get(finding_id)
        if raw is None:
            raise KeyError(f"no such finding: {finding_id}")
        return Finding(**raw)

    def save_success_law(self, law: SuccessLaw) -> None:
        def mutate(data):
            data.setdefault("success_laws", {})[law.id] = asdict(law)

        update_store(self._store, self._read(), mutate)

    def success_laws(self) -> list[SuccessLaw]:
        return [SuccessLaw(**law) for law in self._read().get("success_laws", {}).values()]

    def get_success_law(self, law_id: str) -> SuccessLaw:
        raw = self._read().get("success_laws", {}).get(law_id)
        if raw is None:
            raise KeyError(f"no such success law: {law_id}")
        return SuccessLaw(**raw)

    def save_future_item(self, item: FutureItem) -> None:
        """Fail-closed on the four fields that drive real lifecycle/
        enforcement logic (type, status, resolution, trigger_check) --
        deliberately stricter than save_success_law()'s validation-free
        save, per standing instruction (2026-08-15): a malformed
        FutureItem is exactly the kind of thing that could otherwise
        silently stop being surfaced. trigger_check validation is a
        lazy import of atlas.brain.future_items (not a module-level
        import here) specifically to avoid a circular import --
        future_items.py itself imports KnowledgeBase to call these same
        methods."""
        from atlas.brain.future_items import is_valid_trigger_check

        if item.type not in FUTURE_ITEM_TYPES:
            raise ValueError(f"unknown FutureItem type: {item.type!r} (must be one of {sorted(FUTURE_ITEM_TYPES)})")
        if item.status not in FUTURE_ITEM_STATUSES:
            raise ValueError(f"unknown FutureItem status: {item.status!r} (must be one of {sorted(FUTURE_ITEM_STATUSES)})")
        if item.resolution is not None and item.resolution not in FUTURE_ITEM_RESOLUTIONS:
            raise ValueError(f"unknown FutureItem resolution: {item.resolution!r} (must be one of {sorted(FUTURE_ITEM_RESOLUTIONS)})")
        if not is_valid_trigger_check(item.trigger_check):
            raise ValueError(
                f"unknown trigger_check: {item.trigger_check!r} — not registered in TRIGGER_CHECKS and not UNWIRED_TRIGGER_CHECK"
            )

        def mutate(data):
            data.setdefault("future_items", {})[item.id] = asdict(item)

        update_store(self._store, self._read(), mutate)

    def future_items(self) -> list[FutureItem]:
        return [FutureItem(**f) for f in self._read().get("future_items", {}).values()]

    def get_future_item(self, item_id: str) -> FutureItem:
        raw = self._read().get("future_items", {}).get(item_id)
        if raw is None:
            raise KeyError(f"no such future item: {item_id}")
        return FutureItem(**raw)

    def save_claim(self, claim: Claim) -> None:
        """Fail-closed validation, the same discipline save_future_item()
        already established: `predicate` must be non-empty (a claim must
        claim something), `object_id`/`object_value` can never both be set
        (ambiguous what this claim relates to), and — the structural self-
        contamination firewall — every id in `evidence_finding_ids`/
        `contradicted_by_finding_ids` must resolve to a real Finding
        (never a Claim id: an LLM-produced claim can never become
        evidence for itself or any other claim), while every id in
        `prior_claim_ids`/`superseded_by_id` must resolve to a real,
        already-saved Claim. Reused for both first save and later
        revision (e.g. setting `superseded_by_id` on an existing Claim) —
        the same upsert-by-id shape every save_*() method in this class
        already has."""
        if not claim.predicate.strip():
            raise ValueError("Claim.predicate must be non-empty — a claim must claim something")
        if claim.object_id is not None and claim.object_value is not None:
            raise ValueError(
                "Claim cannot set both object_id and object_value — ambiguous what this claim relates to"
            )
        for fid in claim.evidence_finding_ids:
            self.get_finding(fid)  # raises KeyError if not a real Finding — a Claim id can never appear here
        for fid in claim.contradicted_by_finding_ids:
            self.get_finding(fid)
        for cid in claim.prior_claim_ids:
            self.get_claim(cid)  # raises KeyError if not a real, already-saved Claim
        if claim.superseded_by_id is not None:
            self.get_claim(claim.superseded_by_id)

        def mutate(data):
            data.setdefault("claims", {})[claim.id] = asdict(claim)

        update_store(self._store, self._read(), mutate)

    def claims(self, subject_id: str | None = None, predicate: str | None = None) -> list[Claim]:
        """Same optional-equality-filter shape as findings() — subject_id
        and predicate are the two dimensions a real caller (reason(),
        retrieving prior_claim_ids for a subject) actually needs; no
        filter given returns everything, unchanged."""
        results = [Claim(**c) for c in self._read().get("claims", {}).values()]
        if subject_id is not None:
            results = [c for c in results if c.subject_id == subject_id]
        if predicate is not None:
            results = [c for c in results if c.predicate == predicate]
        return results

    def get_claim(self, claim_id: str) -> Claim:
        raw = self._read().get("claims", {}).get(claim_id)
        if raw is None:
            raise KeyError(f"no such claim: {claim_id}")
        return Claim(**raw)
