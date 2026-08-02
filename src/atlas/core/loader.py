import os
import tomllib
from pathlib import Path

from atlas.core.models import AssetRecord

_DEFAULT_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def _extra_dirs_from_env() -> list[Path]:
    raw = os.environ.get("ATLAS_ASSETS_PATH", "")
    return [Path(p) for p in raw.split(os.pathsep) if p]


def discover_manifests(dirs: list[Path] | None = None) -> list[AssetRecord]:
    """Scan directories for */manifest.toml and parse them into AssetRecords.

    Never imports asset code, so one broken asset can't break discovery of
    the rest. Defaults to the built-in assets dir plus any extra directories
    listed in ATLAS_ASSETS_PATH.
    """
    search_dirs = dirs if dirs is not None else [_DEFAULT_ASSETS_DIR, *_extra_dirs_from_env()]
    records = []
    for base in search_dirs:
        base = Path(base)
        if not base.is_dir():
            continue
        for manifest_path in sorted(base.glob("*/manifest.toml")):
            records.append(_load_manifest(manifest_path))
    return records


def _load_manifest(path: Path) -> AssetRecord:
    with path.open("rb") as f:
        data = tomllib.load(f)
    return AssetRecord(
        id=data["id"],
        name=data.get("name", data["id"]),
        kind=data.get("kind", "tool"),
        description=data.get("description", ""),
        owner=data.get("owner", ""),
        tags=tuple(data.get("tags", ())),
        entrypoint=data.get("entrypoint"),
        config=data.get("config", {}),
    )
