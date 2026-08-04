from atlas.integrations.base import Resource
from atlas.integrations.local_folder_provider import LocalFolderProvider


def test_fetch_resources_returns_none_with_no_approved_folders():
    # The core safety invariant: an empty approved list means zero
    # scanning, never a fallback to any default location.
    assert LocalFolderProvider([]).fetch_resources() is None


def test_fetch_resources_returns_an_error_resource_for_a_nonexistent_approved_folder(tmp_path):
    missing = tmp_path / "does_not_exist"
    resources = LocalFolderProvider([str(missing)]).fetch_resources()
    assert len(resources) == 1
    assert resources[0].error is not None
    assert resources[0].path == str(missing)


def test_fetch_resources_discovers_a_real_file_with_real_metadata(tmp_path):
    real_file = tmp_path / "report.txt"
    real_file.write_text("real content")

    resources = LocalFolderProvider([str(tmp_path)]).fetch_resources()

    files = [r for r in resources if r.resource_type == "file"]
    assert len(files) == 1
    resource = files[0]
    assert isinstance(resource, Resource)
    assert resource.provider == "local_folder"
    assert resource.path == str(real_file)
    assert resource.size_bytes == len("real content")
    assert resource.modified_at is not None
    assert resource.content_hash is not None
    assert resource.error is None


def test_fetch_resources_recurses_into_real_subfolders(tmp_path):
    subfolder = tmp_path / "sub"
    subfolder.mkdir()
    (subfolder / "nested.txt").write_text("nested")

    resources = LocalFolderProvider([str(tmp_path)]).fetch_resources()

    paths = {r.path for r in resources}
    assert str(subfolder) in paths
    assert str(subfolder / "nested.txt") in paths


def test_folders_have_no_content_hash(tmp_path):
    (tmp_path / "sub").mkdir()
    resources = LocalFolderProvider([str(tmp_path)]).fetch_resources()
    folder_resources = [r for r in resources if r.resource_type == "folder"]
    assert len(folder_resources) == 1
    assert folder_resources[0].content_hash is None


def test_two_files_with_identical_real_content_get_the_same_real_hash(tmp_path):
    (tmp_path / "a.txt").write_text("identical content")
    (tmp_path / "b.txt").write_text("identical content")

    resources = LocalFolderProvider([str(tmp_path)]).fetch_resources()

    hashes = {r.content_hash for r in resources if r.resource_type == "file"}
    assert len(hashes) == 1  # both real files hash to the same real digest


def test_two_files_with_different_real_content_get_different_real_hashes(tmp_path):
    (tmp_path / "a.txt").write_text("content A")
    (tmp_path / "b.txt").write_text("content B")

    resources = LocalFolderProvider([str(tmp_path)]).fetch_resources()

    hashes = {r.content_hash for r in resources if r.resource_type == "file"}
    assert len(hashes) == 2


def test_multiple_approved_folders_are_all_scanned(tmp_path):
    folder_a = tmp_path / "a"
    folder_b = tmp_path / "b"
    folder_a.mkdir()
    folder_b.mkdir()
    (folder_a / "x.txt").write_text("x")
    (folder_b / "y.txt").write_text("y")

    resources = LocalFolderProvider([str(folder_a), str(folder_b)]).fetch_resources()

    paths = {r.path for r in resources if r.resource_type == "file"}
    assert str(folder_a / "x.txt") in paths
    assert str(folder_b / "y.txt") in paths


def test_only_scans_the_exact_approved_folders_never_their_parent(tmp_path):
    approved = tmp_path / "approved"
    approved.mkdir()
    (approved / "inside.txt").write_text("inside")
    (tmp_path / "sibling_outside.txt").write_text("outside the approved folder")

    resources = LocalFolderProvider([str(approved)]).fetch_resources()

    paths = {r.path for r in resources}
    assert str(approved / "inside.txt") in paths
    assert str(tmp_path / "sibling_outside.txt") not in paths
