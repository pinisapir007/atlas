from pathlib import Path

from atlas.brain.resource_allowlist import ResourceAllowlist


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


def test_approved_folders_starts_empty():
    allowlist = ResourceAllowlist(store=_FakeStore())
    assert allowlist.approved_folders() == []


def test_approve_folder_records_the_real_resolved_path(tmp_path):
    allowlist = ResourceAllowlist(store=_FakeStore())
    allowlist.approve_folder(str(tmp_path))
    assert allowlist.approved_folders() == [str(tmp_path.resolve())]


def test_approve_folder_is_idempotent(tmp_path):
    allowlist = ResourceAllowlist(store=_FakeStore())
    allowlist.approve_folder(str(tmp_path))
    allowlist.approve_folder(str(tmp_path))
    assert allowlist.approved_folders() == [str(tmp_path.resolve())]


def test_revoke_folder_removes_it(tmp_path):
    allowlist = ResourceAllowlist(store=_FakeStore())
    allowlist.approve_folder(str(tmp_path))
    allowlist.revoke_folder(str(tmp_path))
    assert allowlist.approved_folders() == []


def test_revoke_folder_that_was_never_approved_is_a_safe_no_op(tmp_path):
    allowlist = ResourceAllowlist(store=_FakeStore())
    allowlist.revoke_folder(str(tmp_path))  # must not raise
    assert allowlist.approved_folders() == []


def test_is_approved_true_for_an_exact_approved_folder(tmp_path):
    allowlist = ResourceAllowlist(store=_FakeStore())
    allowlist.approve_folder(str(tmp_path))
    assert allowlist.is_approved(str(tmp_path)) is True


def test_is_approved_true_for_a_real_descendant_of_an_approved_folder(tmp_path):
    allowlist = ResourceAllowlist(store=_FakeStore())
    allowlist.approve_folder(str(tmp_path))
    child = tmp_path / "child" / "grandchild"
    assert allowlist.is_approved(str(child)) is True


def test_is_approved_false_for_an_unapproved_path(tmp_path):
    allowlist = ResourceAllowlist(store=_FakeStore())
    other = tmp_path / "unapproved"
    assert allowlist.is_approved(str(other)) is False


def test_is_approved_false_for_a_sibling_folder_with_a_similar_prefix(tmp_path):
    # e.g. approving /approved must never also approve /approved_2 --
    # a naive string .startswith() check (without the path-separator
    # boundary) would get this wrong.
    approved = tmp_path / "approved"
    approved.mkdir()
    sibling = Path(str(approved) + "_2")
    allowlist = ResourceAllowlist(store=_FakeStore())
    allowlist.approve_folder(str(approved))
    assert allowlist.is_approved(str(sibling)) is False
