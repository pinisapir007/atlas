from atlas.brain.resource_allowlist import ResourceAllowlist
from atlas.brain.resource_discovery_engine import ResourceScanState, scan_resources
from atlas.brain.resource_index import ResourceIndex
from atlas.integrations.base import Resource, ResourceProvider
from atlas.integrations.local_folder_provider import LocalFolderProvider


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


class _FakeResourceProvider:
    """A minimal, duck-typed ResourceProvider stand-in -- name,
    fetch_resources() -- used to test the engine's aggregation and
    fault-isolation without touching any real filesystem."""

    def __init__(self, name, resources=None, raises=None):
        self.name = name
        self._resources = resources
        self._raises = raises

    def fetch_resources(self):
        if self._raises is not None:
            raise self._raises
        return self._resources


def _allowlist():
    return ResourceAllowlist(store=_FakeStore())


def _scan_state():
    return ResourceScanState(store=_FakeStore())


def _resource_index():
    return ResourceIndex(store=_FakeStore())


def test_default_providers_never_scan_anything_with_an_empty_allowlist():
    # The core safety invariant, proven at the engine level with the
    # REAL default provider list (real LocalFolderProvider included) --
    # not just the provider's own unit test.
    result = scan_resources(allowlist=_allowlist(), scan_state=_scan_state(), resource_index=_resource_index())

    assert result["resources"] == []
    assert result["provider_status"]["local_folder"]["count"] == 0


def test_scanning_a_real_approved_tmp_folder_discovers_a_real_file(tmp_path):
    (tmp_path / "real_file.txt").write_text("real content")
    allowlist = _allowlist()
    allowlist.approve_folder(str(tmp_path))

    result = scan_resources(allowlist=allowlist, scan_state=_scan_state(), resource_index=_resource_index())

    file_resources = [r for r in result["resources"] if r.resource_type == "file"]
    assert len(file_resources) == 1
    assert file_resources[0].path == str(tmp_path / "real_file.txt")


def test_a_provider_with_no_data_does_not_stop_other_providers():
    empty = _FakeResourceProvider("empty_provider", resources=None)
    working = _FakeResourceProvider("working_provider", resources=[Resource(provider="working_provider", path="/a", resource_type="file", content_hash="abc")])

    result = scan_resources(providers=[empty, working], allowlist=_allowlist(), scan_state=_scan_state(), resource_index=_resource_index())

    assert result["provider_status"]["empty_provider"]["count"] == 0
    assert result["provider_status"]["working_provider"]["count"] == 1
    assert len(result["resources"]) == 1


def test_a_provider_that_raises_does_not_stop_other_providers():
    class _RealFailure(Exception):
        pass

    broken = _FakeResourceProvider("crashing_provider", raises=_RealFailure("real disk error"))
    working = _FakeResourceProvider("working_provider", resources=[Resource(provider="working_provider", path="/a", resource_type="file")])

    result = scan_resources(providers=[broken, working], allowlist=_allowlist(), scan_state=_scan_state(), resource_index=_resource_index())

    assert result["provider_status"]["crashing_provider"] == {"count": 0, "error": "real disk error"}
    assert result["provider_status"]["working_provider"]["count"] == 1


def test_default_providers_include_all_five_placeholders_plus_local_folder():
    result = scan_resources(allowlist=_allowlist(), scan_state=_scan_state(), resource_index=_resource_index())
    assert set(result["provider_status"]) == {"local_folder", "google_drive", "onedrive", "dropbox", "nas", "gmail"}


def test_duplicate_files_are_detected_by_real_matching_hash():
    provider = _FakeResourceProvider(
        "provider_x",
        resources=[
            Resource(provider="provider_x", path="/a.txt", resource_type="file", content_hash="same_hash"),
            Resource(provider="provider_x", path="/b.txt", resource_type="file", content_hash="same_hash"),
            Resource(provider="provider_x", path="/c.txt", resource_type="file", content_hash="different_hash"),
        ],
    )

    result = scan_resources(providers=[provider], allowlist=_allowlist(), scan_state=_scan_state(), resource_index=_resource_index())

    assert result["duplicates"] == [["/a.txt", "/b.txt"]]


def test_folders_are_never_counted_as_duplicates_even_with_no_hash():
    provider = _FakeResourceProvider(
        "provider_x",
        resources=[
            Resource(provider="provider_x", path="/folder1", resource_type="folder", content_hash=None),
            Resource(provider="provider_x", path="/folder2", resource_type="folder", content_hash=None),
        ],
    )

    result = scan_resources(providers=[provider], allowlist=_allowlist(), scan_state=_scan_state(), resource_index=_resource_index())

    assert result["duplicates"] == []


def test_new_files_are_detected_on_the_first_scan():
    provider = _FakeResourceProvider("provider_x", resources=[Resource(provider="provider_x", path="/a.txt", resource_type="file", content_hash="h1")])
    result = scan_resources(providers=[provider], allowlist=_allowlist(), scan_state=_scan_state(), resource_index=_resource_index())
    assert result["new"] == ["/a.txt"]
    assert result["modified"] == []
    assert result["deleted"] == []


def test_unchanged_files_are_not_reported_new_modified_or_deleted_on_the_second_scan():
    scan_state = _scan_state()
    resource_index = _resource_index()
    resource = Resource(provider="provider_x", path="/a.txt", resource_type="file", content_hash="h1", size_bytes=10)
    provider = _FakeResourceProvider("provider_x", resources=[resource])

    scan_resources(providers=[provider], allowlist=_allowlist(), scan_state=scan_state, resource_index=resource_index)
    second_result = scan_resources(providers=[provider], allowlist=_allowlist(), scan_state=scan_state, resource_index=resource_index)

    assert second_result["new"] == []
    assert second_result["modified"] == []
    assert second_result["deleted"] == []


def test_a_changed_hash_is_reported_modified_on_the_next_scan():
    scan_state = _scan_state()
    resource_index = _resource_index()
    first_provider = _FakeResourceProvider("provider_x", resources=[Resource(provider="provider_x", path="/a.txt", resource_type="file", content_hash="h1", size_bytes=10)])
    scan_resources(providers=[first_provider], allowlist=_allowlist(), scan_state=scan_state, resource_index=resource_index)

    second_provider = _FakeResourceProvider("provider_x", resources=[Resource(provider="provider_x", path="/a.txt", resource_type="file", content_hash="h2", size_bytes=20)])
    result = scan_resources(providers=[second_provider], allowlist=_allowlist(), scan_state=scan_state, resource_index=resource_index)

    assert result["modified"] == ["/a.txt"]
    assert result["new"] == []


def test_a_file_missing_from_the_next_scan_is_reported_deleted():
    scan_state = _scan_state()
    resource_index = _resource_index()
    first_provider = _FakeResourceProvider("provider_x", resources=[Resource(provider="provider_x", path="/a.txt", resource_type="file", content_hash="h1")])
    scan_resources(providers=[first_provider], allowlist=_allowlist(), scan_state=scan_state, resource_index=resource_index)

    second_provider = _FakeResourceProvider("provider_x", resources=[])
    result = scan_resources(providers=[second_provider], allowlist=_allowlist(), scan_state=scan_state, resource_index=resource_index)

    assert result["deleted"] == ["/a.txt"]


def test_a_resource_with_a_real_error_is_excluded_from_new_modified_deleted_comparison():
    provider = _FakeResourceProvider("provider_x", resources=[Resource(provider="provider_x", path="/broken", resource_type="file", error="permission denied")])
    result = scan_resources(providers=[provider], allowlist=_allowlist(), scan_state=_scan_state(), resource_index=_resource_index())
    assert result["new"] == []


def test_full_real_pipeline_local_folder_provider_through_the_engine_end_to_end(tmp_path):
    # No fakes anywhere in this one -- real ResourceAllowlist, real
    # LocalFolderProvider, real tmp_path files, real scan-state diffing
    # across two real calls.
    (tmp_path / "one.txt").write_text("first")
    allowlist = _allowlist()
    allowlist.approve_folder(str(tmp_path))
    scan_state = _scan_state()
    resource_index = _resource_index()

    first = scan_resources(allowlist=allowlist, scan_state=scan_state, resource_index=resource_index)
    assert str(tmp_path / "one.txt") in first["new"]

    (tmp_path / "two.txt").write_text("second")
    second = scan_resources(allowlist=allowlist, scan_state=scan_state, resource_index=resource_index)
    assert str(tmp_path / "two.txt") in second["new"]
    assert str(tmp_path / "one.txt") not in second["new"]  # already known from the first scan


def test_scan_resources_populates_the_resource_index_queryable_without_rescanning():
    provider = _FakeResourceProvider("provider_x", resources=[Resource(provider="provider_x", path="/a.txt", resource_type="file", name="a.txt", content_hash="h1")])
    resource_index = _resource_index()

    scan_resources(providers=[provider], allowlist=_allowlist(), scan_state=_scan_state(), resource_index=resource_index)

    # No provider, no scan -- purely reading what the scan above already
    # persisted. This is "the Decision Engine can query without rescanning."
    indexed = resource_index.all_resources()
    assert len(indexed) == 1
    assert indexed[0].path == "/a.txt"
    assert resource_index.get_resource("/a.txt").name == "a.txt"


def test_resource_index_reflects_a_deleted_file_after_the_next_scan():
    resource_index = _resource_index()
    scan_state = _scan_state()
    first_provider = _FakeResourceProvider("provider_x", resources=[Resource(provider="provider_x", path="/a.txt", resource_type="file")])
    scan_resources(providers=[first_provider], allowlist=_allowlist(), scan_state=scan_state, resource_index=resource_index)
    assert resource_index.count() == 1

    second_provider = _FakeResourceProvider("provider_x", resources=[])
    scan_resources(providers=[second_provider], allowlist=_allowlist(), scan_state=scan_state, resource_index=resource_index)

    assert resource_index.count() == 0  # the index reflects the current real state, never a stale entry


def test_resource_provider_protocol_declares_no_write_delete_or_move_capability():
    # Structural, not just documentary: nothing implementing
    # ResourceProvider is asked to expose more than reading.
    forbidden_substrings = ("write", "delete", "remove", "move", "modify", "rename", "update", "create")
    public_members = [m for m in dir(ResourceProvider) if not m.startswith("_")]
    for member in public_members:
        assert not any(word in member.lower() for word in forbidden_substrings)
