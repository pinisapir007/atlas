from atlas.brain.resource_index import ResourceIndex
from atlas.integrations.base import Resource


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


def test_all_resources_starts_empty():
    index = ResourceIndex(store=_FakeStore())
    assert index.all_resources() == []
    assert index.count() == 0


def test_replace_index_can_be_queried_without_rescanning():
    # The core requirement this class exists for: real query methods
    # that only ever read already-persisted data, no provider or
    # filesystem call anywhere in this test.
    index = ResourceIndex(store=_FakeStore())
    resources = [
        Resource(provider="local_folder", path="/approved/a.txt", resource_type="file", name="a.txt", content_hash="h1"),
        Resource(provider="local_folder", path="/approved/b.txt", resource_type="file", name="b.txt", content_hash="h2"),
    ]

    index.replace_index(resources)

    assert index.count() == 2
    all_resources = index.all_resources()
    assert {r.path for r in all_resources} == {"/approved/a.txt", "/approved/b.txt"}


def test_get_resource_returns_the_real_resource_by_path():
    index = ResourceIndex(store=_FakeStore())
    index.replace_index([Resource(provider="local_folder", path="/approved/a.txt", resource_type="file", name="a.txt")])

    resource = index.get_resource("/approved/a.txt")

    assert resource is not None
    assert resource.name == "a.txt"


def test_get_resource_returns_none_for_an_unknown_path():
    index = ResourceIndex(store=_FakeStore())
    assert index.get_resource("/never/indexed") is None


def test_resources_in_folder_returns_only_real_descendants(tmp_path):
    approved = tmp_path / "approved"
    sibling = tmp_path / "approved_2"
    index = ResourceIndex(store=_FakeStore())
    index.replace_index(
        [
            Resource(provider="local_folder", path=str(approved), resource_type="folder"),
            Resource(provider="local_folder", path=str(approved / "inside.txt"), resource_type="file"),
            Resource(provider="local_folder", path=str(sibling / "outside.txt"), resource_type="file"),
        ]
    )

    result = index.resources_in_folder(str(approved))

    paths = {r.path for r in result}
    assert str(approved / "inside.txt") in paths
    assert str(sibling / "outside.txt") not in paths


def test_find_by_type_filters_correctly():
    index = ResourceIndex(store=_FakeStore())
    index.replace_index(
        [
            Resource(provider="local_folder", path="/a", resource_type="file"),
            Resource(provider="local_folder", path="/b", resource_type="folder"),
        ]
    )

    assert [r.path for r in index.find_by_type("file")] == ["/a"]
    assert [r.path for r in index.find_by_type("folder")] == ["/b"]


def test_replace_index_is_a_full_replacement_not_an_incremental_merge():
    # A resource present in the first index but absent from a later
    # real scan (e.g. a deleted file) must not linger in the index.
    index = ResourceIndex(store=_FakeStore())
    index.replace_index([Resource(provider="local_folder", path="/a", resource_type="file")])
    assert index.count() == 1

    index.replace_index([Resource(provider="local_folder", path="/b", resource_type="file")])

    assert index.count() == 1
    assert index.get_resource("/a") is None
    assert index.get_resource("/b") is not None
