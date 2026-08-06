from atlas.brain.browser_allowlist import BrowserAllowlist


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


def _allowlist():
    return BrowserAllowlist(store=_FakeStore())


def test_default_deny_nothing_approved_yet():
    allowlist = _allowlist()
    assert allowlist.is_approved("https://reddit.com/r/keto") is False
    assert allowlist.approved_domains() == []


def test_approve_then_is_approved_for_the_same_real_domain():
    allowlist = _allowlist()
    allowlist.approve_domain("reddit.com")
    assert allowlist.is_approved("https://reddit.com/r/keto") is True
    assert allowlist.is_approved("http://www.reddit.com/r/other") is True


def test_approve_is_idempotent_no_duplicate_entries():
    allowlist = _allowlist()
    allowlist.approve_domain("reddit.com")
    allowlist.approve_domain("reddit.com")
    assert allowlist.approved_domains() == ["reddit.com"]


def test_subdomain_of_an_approved_domain_is_approved():
    allowlist = _allowlist()
    allowlist.approve_domain("digistore24.com")
    assert allowlist.is_approved("https://news.digistore24.com/en/top-offers") is True


def test_unrelated_domain_is_not_approved():
    allowlist = _allowlist()
    allowlist.approve_domain("reddit.com")
    assert allowlist.is_approved("https://evil-reddit.com/phishing") is False


def test_revoke_removes_approval():
    allowlist = _allowlist()
    allowlist.approve_domain("reddit.com")
    allowlist.revoke_domain("reddit.com")
    assert allowlist.is_approved("https://reddit.com/r/keto") is False


def test_revoke_unapproved_domain_is_a_safe_no_op():
    allowlist = _allowlist()
    allowlist.revoke_domain("never-approved.com")
    assert allowlist.approved_domains() == []


def test_normalization_is_case_and_scheme_insensitive():
    allowlist = _allowlist()
    allowlist.approve_domain("HTTPS://Reddit.com/")
    assert allowlist.approved_domains() == ["reddit.com"]
