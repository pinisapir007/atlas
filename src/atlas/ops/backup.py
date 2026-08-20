"""ATLAS Memory Backup (P0 Stage 1B, 2026-08-19) -- the real, minimal
mechanism closing "no backup of any kind exists for .atlas/", the
first of the two named Stage 1 blockers (Body & World Access / Stage 1
audits). Read-only on the real source -- every file under `source_dir`
is only ever opened for reading; nothing here writes into `.atlas/`
itself, ever.

Atomic by the same convention atlas.core.store.write_json_atomic
already established: every real file is copied into a temporarily-
named folder first, and only renamed to its real, final timestamped
name (one atomic Path.replace()) once every file has been copied and
verified -- a backup folder under its real name either exists
complete, or doesn't exist at all. A crash mid-copy can never leave a
half-finished backup masquerading as a real one, and a real integrity
failure leaves the temp folder in place (never silently deleted) so a
human can inspect exactly what went wrong.

Integrity verification is real, not assumed: every real .json file
copied is re-parsed from the copy and every file's size and a real
sha256 are recorded and checked -- a backup that "exists" but was
never actually verified is not a real backup, the same "prove it,
don't assume it" discipline this codebase already applies everywhere
(e.g. the P0 planner fix, verified via git-stash isolation rather than
trusted).

Never logs file content -- only real, structural metadata (filename,
size, a content hash). No secret lives inside .atlas/*.json by this
codebase's own architecture (secrets are environment variables, never
written to disk here), but this module never assumes that and has no
code path that could print raw file bytes anywhere.
"""

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"


@dataclass
class FileRecord:
    relative_path: str
    size_bytes: int
    sha256: str
    valid_json: bool | None  # None if not a .json file -- the check doesn't apply


@dataclass
class BackupResult:
    success: bool
    backup_path: Path | None
    timestamp: str
    files_backed_up: int
    total_bytes: int
    integrity_errors: list[str] = field(default_factory=list)
    files: list[FileRecord] = field(default_factory=list)
    error: str = ""


@dataclass
class RestoreResult:
    success: bool
    restored_path: Path | None
    files_restored: int
    mismatches: list[str] = field(default_factory=list)
    error: str = ""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_json(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8") as f:
            json.load(f)
        return True
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False


def _is_backup_timestamp_name(name: str) -> bool:
    try:
        datetime.strptime(name, _TIMESTAMP_FORMAT)
        return True
    except ValueError:
        return False


def create_backup(
    source_dir: Path = Path(".atlas"),
    backup_root: Path = Path(".atlas_backups"),
    retention: int = 5,
    now: datetime | None = None,
) -> BackupResult:
    """Copies every real file under `source_dir` into a new, timestamped
    folder under `backup_root` -- read-only on `source_dir` throughout.
    Copies into a temporary name first, verifies every copied file
    (size match + a real JSON parse for every .json file), and only
    then atomically renames the temp folder to its real timestamped
    name. On any integrity failure, the temp folder is left in place
    and `success=False` -- never a silently-discarded, unverifiable
    failure.

    `retention`: after a successful backup, keeps only the `retention`
    most recent real backup folders under `backup_root` (matched
    strictly by this function's own timestamp naming pattern) and
    removes older ones -- never touches `source_dir`, never touches
    anything under `backup_root` that doesn't match the exact pattern
    this function itself produces.
    """
    source_dir = Path(source_dir)
    backup_root = Path(backup_root)
    timestamp = (now or datetime.now(timezone.utc)).strftime(_TIMESTAMP_FORMAT)

    if not source_dir.exists() or not source_dir.is_dir():
        return BackupResult(
            success=False, backup_path=None, timestamp=timestamp,
            files_backed_up=0, total_bytes=0,
            error=f"source directory does not exist: {source_dir}",
        )

    backup_root.mkdir(parents=True, exist_ok=True)
    tmp_path = backup_root / f".tmp_{timestamp}"
    final_path = backup_root / timestamp

    if tmp_path.exists():
        # A real leftover from a previous crashed run -- never a real,
        # completed backup under this name, safe to clear before retrying.
        shutil.rmtree(tmp_path)

    records: list[FileRecord] = []
    integrity_errors: list[str] = []
    total_bytes = 0

    try:
        for source_file in sorted(source_dir.rglob("*")):
            if not source_file.is_file():
                continue
            relative = source_file.relative_to(source_dir)
            dest_file = tmp_path / relative
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, dest_file)

            source_size = source_file.stat().st_size
            dest_size = dest_file.stat().st_size
            if source_size != dest_size:
                integrity_errors.append(f"{relative}: size mismatch (source {source_size}, backup {dest_size})")

            valid_json = None
            if dest_file.suffix == ".json":
                valid_json = _verify_json(dest_file)
                if not valid_json:
                    integrity_errors.append(f"{relative}: backup copy is not valid JSON")

            records.append(
                FileRecord(
                    relative_path=str(relative).replace("\\", "/"),
                    size_bytes=dest_size,
                    sha256=_sha256(dest_file),
                    valid_json=valid_json,
                )
            )
            total_bytes += dest_size
    except OSError as exc:
        return BackupResult(
            success=False, backup_path=tmp_path, timestamp=timestamp,
            files_backed_up=len(records), total_bytes=total_bytes,
            integrity_errors=integrity_errors, files=records,
            error=f"real failure while copying: {exc}",
        )

    if integrity_errors:
        _write_manifest(tmp_path, timestamp, source_dir, records, integrity_errors, success=False)
        _append_log(backup_root, timestamp, success=False, files=len(records), total_bytes=total_bytes)
        return BackupResult(
            success=False, backup_path=tmp_path, timestamp=timestamp,
            files_backed_up=len(records), total_bytes=total_bytes,
            integrity_errors=integrity_errors, files=records,
            error="integrity verification failed -- backup left under its temporary name for inspection",
        )

    _write_manifest(tmp_path, timestamp, source_dir, records, integrity_errors, success=True)
    tmp_path.replace(final_path)  # atomic -- final_path either fully exists now, or this line never ran

    _apply_retention(backup_root, retention)
    _append_log(backup_root, timestamp, success=True, files=len(records), total_bytes=total_bytes)

    return BackupResult(
        success=True, backup_path=final_path, timestamp=timestamp,
        files_backed_up=len(records), total_bytes=total_bytes,
        integrity_errors=[], files=records,
    )


def restore_backup(backup_path: Path, destination_dir: Path) -> RestoreResult:
    """Restores a real backup folder into `destination_dir` -- read-only
    on `backup_path` throughout, the mirror of create_backup(). Fails
    closed if `destination_dir` already exists: this function never
    overwrites existing state, including a real, live .atlas/ -- the
    caller is responsible for pointing this at a genuinely new/temporary
    location, per the Stage 1B restore-drill requirement (never drop a
    restore on top of live state)."""
    backup_path = Path(backup_path)
    destination_dir = Path(destination_dir)

    if not backup_path.exists() or not backup_path.is_dir():
        return RestoreResult(success=False, restored_path=None, files_restored=0, error=f"backup path does not exist: {backup_path}")
    if destination_dir.exists():
        return RestoreResult(
            success=False, restored_path=None, files_restored=0,
            error=f"refusing to restore onto an already-existing path: {destination_dir}",
        )

    manifest_path = backup_path / "_backup_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None

    destination_dir.mkdir(parents=True)
    restored = 0
    mismatches: list[str] = []
    for source_file in sorted(backup_path.rglob("*")):
        if not source_file.is_file() or source_file.name == "_backup_manifest.json":
            continue
        relative = source_file.relative_to(backup_path)
        dest_file = destination_dir / relative
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, dest_file)
        restored += 1

        if dest_file.suffix == ".json" and not _verify_json(dest_file):
            mismatches.append(f"{relative}: restored copy is not valid JSON")

    if manifest is not None:
        expected_count = manifest["file_count"]
        if restored != expected_count:
            mismatches.append(f"file count mismatch: manifest says {expected_count}, restored {restored}")
        for entry in manifest["files"]:
            dest_file = destination_dir / entry["path"]
            if not dest_file.exists():
                mismatches.append(f"{entry['path']}: missing from restore")
                continue
            if dest_file.stat().st_size != entry["size_bytes"]:
                mismatches.append(f"{entry['path']}: size mismatch after restore")
            if _sha256(dest_file) != entry["sha256"]:
                mismatches.append(f"{entry['path']}: hash mismatch after restore")

    return RestoreResult(
        success=not mismatches, restored_path=destination_dir, files_restored=restored, mismatches=mismatches,
    )


def _write_manifest(
    backup_path: Path,
    timestamp: str,
    source_dir: Path,
    records: list[FileRecord],
    integrity_errors: list[str],
    success: bool,
) -> None:
    manifest = {
        "timestamp": timestamp,
        "source_dir": str(source_dir),
        "success": success,
        "file_count": len(records),
        "total_bytes": sum(r.size_bytes for r in records),
        "integrity_errors": integrity_errors,
        "files": [
            {"path": r.relative_path, "size_bytes": r.size_bytes, "sha256": r.sha256, "valid_json": r.valid_json}
            for r in records
        ],
    }
    (backup_path / "_backup_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _append_log(backup_root: Path, timestamp: str, success: bool, files: int, total_bytes: int) -> None:
    status = "SUCCESS" if success else "FAILED"
    line = f"{timestamp} {status} files={files} bytes={total_bytes}\n"
    with (backup_root / "backup.log").open("a", encoding="utf-8") as f:
        f.write(line)


def _apply_retention(backup_root: Path, retention: int) -> None:
    """Deletes only real backup folders this function itself created --
    matched strictly against the exact timestamp pattern create_backup()
    uses, never a loose glob that could catch an unrelated folder a
    human happened to place under backup_root."""
    candidates = [p for p in backup_root.iterdir() if p.is_dir() and _is_backup_timestamp_name(p.name)]
    candidates.sort(key=lambda p: p.name, reverse=True)
    for stale in candidates[retention:]:
        shutil.rmtree(stale)
