import json
from dataclasses import asdict
from pathlib import Path

from atlas.assets.affiliate_department.models import AffiliateOpportunity

# Self-contained, file-backed persistence — same pattern and same reason as
# recruitment_workforce.store.WorkforceStore: Registry always does zero-arg
# instantiation, so an asset with its own state must persist to disk (keyed
# off cwd) rather than rely on in-memory state surviving across separate CLI
# invocations.
_DEFAULT_PATH = Path(".atlas/affiliate_department.json")
_EMPTY = {"opportunities": {}}


class AffiliateStore:
    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        self._path = Path(path)

    def _read(self) -> dict:
        if not self._path.exists():
            return json.loads(json.dumps(_EMPTY))
        return json.loads(self._path.read_text())

    def _write(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2))

    def save_opportunity(self, opportunity: AffiliateOpportunity) -> None:
        data = self._read()
        data["opportunities"][opportunity.id] = asdict(opportunity)
        self._write(data)

    def opportunities(self) -> list[AffiliateOpportunity]:
        return [AffiliateOpportunity(**o) for o in self._read()["opportunities"].values()]

    def get_opportunity(self, opportunity_id: str) -> AffiliateOpportunity:
        raw = self._read()["opportunities"].get(opportunity_id)
        if raw is None:
            raise KeyError(f"no such opportunity: {opportunity_id}")
        return AffiliateOpportunity(**raw)
