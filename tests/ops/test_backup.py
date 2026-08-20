import json
from datetime import datetime, timezone

from atlas.ops.backup import create_backup, restore_backup


def _make_source(tmp_path, files: dict[str, str]):
    source = tmp_path / "atlas_source"
    source.mkdir()
    for relative, content in files.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return source


def test_create_backup_copies_every_real_file_and_succeeds(tmp_path):
    source = _make_source(tmp_path, {
        "brain.json": json.dumps({"goals": {}}),
        "knowledge.json": json.dumps({"findings": {}}),
        "screenshots/shot1.png": "not really a png, just real bytes for this test",
    })
    backup_root = tmp_path / "backups"

    result = create_backup(source_dir=source, backup_root=backup_root)

    assert result.success is True
    assert result.files_backed_up == 3
    assert result.integrity_errors == []
    assert result.backup_path.exists()
    assert (result.backup_path / "brain.json").exists()
    assert (result.backup_path / "screenshots" / "shot1.png").exists()


def test_create_backup_never_modifies_the_real_source(tmp_path):
    source = _make_source(tmp_path, {"brain.json": json.dumps({"goals": {"g1": {}}})})
    original_content = (source / "brain.json").read_text(encoding="utf-8")
    original_mtime = (source / "brain.json").stat().st_mtime

    create_backup(source_dir=source, backup_root=tmp_path / "backups")

    assert (source / "brain.json").read_text(encoding="utf-8") == original_content
    assert (source / "brain.json").stat().st_mtime == original_mtime


def test_create_backup_is_atomic_final_name_only_appears_on_full_success(tmp_path):
    source = _make_source(tmp_path, {"brain.json": json.dumps({"goals": {}})})
    backup_root = tmp_path / "backups"
    now = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)

    result = create_backup(source_dir=source, backup_root=backup_root, now=now)

    assert result.success is True
    final_dirs = [p for p in backup_root.iterdir() if p.is_dir() and not p.name.startswith(".tmp_")]
    tmp_dirs = [p for p in backup_root.iterdir() if p.is_dir() and p.name.startswith(".tmp_")]
    assert len(final_dirs) == 1
    assert tmp_dirs == []  # the temp folder must be gone -- renamed, not copied-then-left-behind


def test_create_backup_flags_a_real_invalid_json_file_and_does_not_finalize(tmp_path):
    source = _make_source(tmp_path, {"broken.json": "{not valid json at all"})
    backup_root = tmp_path / "backups"
    now = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)

    result = create_backup(source_dir=source, backup_root=backup_root, now=now)

    assert result.success is False
    assert any("not valid JSON" in e for e in result.integrity_errors)
    # the real, final (non-tmp) name must never appear -- an unverified backup is not a real one
    final_dirs = [p for p in backup_root.iterdir() if p.is_dir() and not p.name.startswith(".tmp_")]
    assert final_dirs == []
    tmp_dirs = [p for p in backup_root.iterdir() if p.is_dir() and p.name.startswith(".tmp_")]
    assert len(tmp_dirs) == 1  # left in place for inspection, never silently deleted


def test_create_backup_writes_a_manifest_with_no_file_content(tmp_path):
    source = _make_source(tmp_path, {"brain.json": json.dumps({"secret_looking_field": "should never leak into the manifest as content"})})
    backup_root = tmp_path / "backups"

    result = create_backup(source_dir=source, backup_root=backup_root)

    manifest = json.loads((result.backup_path / "_backup_manifest.json").read_text(encoding="utf-8"))
    manifest_text = json.dumps(manifest)
    assert "should never leak" not in manifest_text  # only metadata (path/size/hash), never real content
    assert manifest["file_count"] == 1
    assert manifest["files"][0]["valid_json"] is True


def test_create_backup_appends_a_log_line_without_content(tmp_path):
    source = _make_source(tmp_path, {"brain.json": json.dumps({"a": "real content that must never appear in the log"})})
    backup_root = tmp_path / "backups"

    create_backup(source_dir=source, backup_root=backup_root)

    log_text = (backup_root / "backup.log").read_text(encoding="utf-8")
    assert "SUCCESS" in log_text
    assert "real content that must never appear" not in log_text


def test_retention_keeps_only_the_most_recent_n_and_never_touches_unrelated_folders(tmp_path):
    source = _make_source(tmp_path, {"brain.json": json.dumps({"goals": {}})})
    backup_root = tmp_path / "backups"
    (backup_root).mkdir()
    unrelated = backup_root / "not_a_backup_do_not_touch"
    unrelated.mkdir()
    (unrelated / "marker.txt").write_text("real, unrelated file", encoding="utf-8")

    for i in range(4):
        now = datetime(2026, 8, 19, 12, i, 0, tzinfo=timezone.utc)
        create_backup(source_dir=source, backup_root=backup_root, retention=2, now=now)

    real_backups = sorted(p.name for p in backup_root.iterdir() if p.is_dir() and p.name != "not_a_backup_do_not_touch")
    assert len(real_backups) == 2  # retention=2 enforced
    assert unrelated.exists()  # never touched -- doesn't match the timestamp-name pattern
    assert (unrelated / "marker.txt").exists()


def test_restore_into_a_fresh_directory_matches_the_backup_exactly(tmp_path):
    source = _make_source(tmp_path, {
        "brain.json": json.dumps({"goals": {"g1": {"id": "g1"}}}),
        "knowledge.json": json.dumps({"findings": {}}),
    })
    backup_result = create_backup(source_dir=source, backup_root=tmp_path / "backups")
    restore_target = tmp_path / "restore_drill"

    restore_result = restore_backup(backup_result.backup_path, restore_target)

    assert restore_result.success is True
    assert restore_result.mismatches == []
    assert restore_result.files_restored == 2
    restored_brain = json.loads((restore_target / "brain.json").read_text(encoding="utf-8"))
    original_brain = json.loads((source / "brain.json").read_text(encoding="utf-8"))
    assert restored_brain == original_brain


def test_restore_refuses_to_overwrite_an_existing_destination(tmp_path):
    source = _make_source(tmp_path, {"brain.json": json.dumps({"goals": {}})})
    backup_result = create_backup(source_dir=source, backup_root=tmp_path / "backups")
    already_there = tmp_path / "already_exists"
    already_there.mkdir()

    result = restore_backup(backup_result.backup_path, already_there)

    assert result.success is False
    assert "already-existing" in result.error


def test_restore_flags_a_corrupted_file_that_no_longer_matches_the_manifest(tmp_path):
    source = _make_source(tmp_path, {"brain.json": json.dumps({"goals": {}})})
    backup_result = create_backup(source_dir=source, backup_root=tmp_path / "backups")
    # Simulate real corruption of the backup copy itself (e.g. disk bit-rot)
    # -- must be caught by the manifest hash check on restore, not silently
    # passed through.
    (backup_result.backup_path / "brain.json").write_text('{"goals": {"tampered": true}}', encoding="utf-8")
    restore_target = tmp_path / "restore_drill"

    result = restore_backup(backup_result.backup_path, restore_target)

    assert result.success is False
    assert any("hash mismatch" in m for m in result.mismatches)
