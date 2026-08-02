import json
from dataclasses import asdict
from pathlib import Path

from atlas.assets.recruitment_workforce.models import CandidateRecord, EmployerDemand, Opportunity, WorkforceSupplier

_DEFAULT_PATH = Path(".atlas/recruitment_workforce.json")
_EMPTY = {"demands": {}, "suppliers": {}, "candidates": {}, "opportunities": {}}


class WorkforceStore:
    """Local, file-backed persistence for the Recruitment Agent's own
    business data (employer demand, suppliers, candidates, opportunities)
    — separate from atlas.core's per-asset run-state store, the same
    separation of concerns BrainMemory uses for atlas.brain. No
    atlas.core/atlas.brain imports: this asset is self-contained.
    """

    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        self._path = Path(path)

    def _read(self) -> dict:
        if not self._path.exists():
            return json.loads(json.dumps(_EMPTY))
        return json.loads(self._path.read_text())

    def _write(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2))

    # Employer demand
    def save_demand(self, demand: EmployerDemand) -> None:
        data = self._read()
        data["demands"][demand.id] = asdict(demand)
        self._write(data)

    def demands(self) -> list[EmployerDemand]:
        return [EmployerDemand(**d) for d in self._read()["demands"].values()]

    def get_demand(self, demand_id: str) -> EmployerDemand:
        raw = self._read()["demands"].get(demand_id)
        if raw is None:
            raise KeyError(f"no such demand: {demand_id}")
        return EmployerDemand(**raw)

    # Workforce supplier
    def save_supplier(self, supplier: WorkforceSupplier) -> None:
        data = self._read()
        data["suppliers"][supplier.id] = asdict(supplier)
        self._write(data)

    def suppliers(self) -> list[WorkforceSupplier]:
        return [WorkforceSupplier(**s) for s in self._read()["suppliers"].values()]

    # Candidate / worker pool
    def save_candidate(self, candidate: CandidateRecord) -> None:
        data = self._read()
        data["candidates"][candidate.id] = asdict(candidate)
        self._write(data)

    def candidates(self) -> list[CandidateRecord]:
        return [CandidateRecord(**c) for c in self._read()["candidates"].values()]

    # Opportunities
    def save_opportunity(self, opportunity: Opportunity) -> None:
        data = self._read()
        data["opportunities"][opportunity.id] = asdict(opportunity)
        self._write(data)

    def opportunities(self) -> list[Opportunity]:
        return [Opportunity(**o) for o in self._read()["opportunities"].values()]

    def get_opportunity(self, opportunity_id: str) -> Opportunity:
        raw = self._read()["opportunities"].get(opportunity_id)
        if raw is None:
            raise KeyError(f"no such opportunity: {opportunity_id}")
        return Opportunity(**raw)
