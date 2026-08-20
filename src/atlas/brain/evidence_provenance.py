"""Evidence Provenance (2026-08-17, ONE BRAIN Provenance Implementation)
-- the central, sense-agnostic mechanism that answers "how many
genuinely independent real-world sources does this evidence represent",
replacing every raw `len(findings)` count that previously treated
repeated/duplicate-origin evidence as if it were independently
corroborated.

Two axes, deliberately never collapsed into one ("claimant if present
else origin" was explicitly rejected during design -- a real
falsification finding: two Findings can share a claimant across two
different origins, or share an origin with no known claimant, and both
cases must be recognized as "the same real-world source" independently
of each other):

- CLAIMANT (`Finding.claimant`) -- who in the real world is asserting
  this. Never guessed; "" is honest UNKNOWN.
- ORIGIN (derived from `Finding.evidence` via `evidence_origin()`) --
  the real, normalized page/document this specific evidence instance
  was read from. Never `Finding.source` (an internal ATLAS sensor name,
  never a real-world origin) and never `Finding.provider` (a platform,
  one level coarser than a specific page).

Two Findings count as the SAME real-world source whenever they share
EITHER a known claimant OR a known origin (transitively -- see
`independent_source_count()`'s union-find below). A Finding with
NEITHER known contributes nothing toward the independent-source count
(UNKNOWN, fail-closed) -- but it is never discarded from KnowledgeBase;
it simply doesn't count as proof of independence, the same "preserve,
never delete, never let it pass as proof" discipline every other
UNKNOWN case in this codebase already follows.

Deliberately NOT attempted here (explicit scope lock): automatic
syndication/content-copy detection, claimant inference from domain or
free text, a crawler, a content-fingerprint engine. If dependence
between two Findings can't be proven from real, already-known claimant/
origin data, they are conservatively treated as independent from each
other UNLESS a real signal says otherwise -- "cannot prove they're the
same" is not the same claim as "cannot prove they're independent";
this module only refuses to count evidence it cannot place an origin/
claimant on AT ALL (fully UNKNOWN), it does not invent dependence
between two otherwise-unrelated, individually-known sources.
"""

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from atlas.brain.models import Finding

# Evidence Role Gate (2026-08-17, ONE BRAIN Evidence Role Gate) -- the
# roles whose origin is trustworthy enough to stand in for a real-world
# source ON ITS OWN, with no known claimant: a primary observation has no
# external claimant to begin with; a direct assertion's own origin IS its
# claimant's own platform; an aggregated report's origin is one real,
# singular observation event, and Finding-level granularity already caps
# its contribution at exactly one group no matter how much it internally
# aggregates (see docstring below). "relay_or_quote" and "" (UNKNOWN) are
# deliberately excluded -- an artifact merely relaying/quoting another
# real claimant can be hosted at any number of different real origins
# without representing more than that one real underlying source, and
# guessing "no evidence of relay" as "therefore direct" would be exactly
# the fabricated-confidence mistake this module's fail-closed discipline
# forbids elsewhere.
_ORIGIN_TRUSTED_ROLES = frozenset({"primary_observation", "direct_assertion", "aggregated_report"})

# A real, stated, editable list -- the same "documented, non-exhaustive
# assumption" class as HASHTAG_PLATFORMS/MARKET_LOCALE elsewhere in this
# codebase, not a claim of completeness. Stripped because they identify
# the VISITOR/CAMPAIGN, never the underlying page/document itself.
KNOWN_TRACKING_PARAMS = frozenset(
    {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "fbclid", "gclid", "msclkid", "mc_cid", "mc_eid", "ref", "referrer",
    }
)


def normalize_url(url: str) -> str:
    """Real, conservative URL-equivalence normalization -- lowercases
    the host, strips a trailing slash, drops the fragment (never part of
    what a server returns) and known tracking query parameters, and
    re-serializes deterministically (sorted query params) so two
    differently-ordered-but-equivalent URLs normalize identically.
    Deliberately narrow: no crawler, no content fingerprinting, no
    canonical-link-tag following -- only the specific, named class of
    trivial variance (redirects landing on the same real page, tracking
    params) this was built to close. Returns "" for anything that isn't
    a real, well-formed, scheme+host URL (e.g. a local file path, or an
    empty string) -- honestly not normalizable, never guessed."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
    except ValueError:
        return ""
    if not parsed.scheme or not parsed.netloc:
        return ""  # not a real URL -- e.g. a local file path or a bare marker string

    query_pairs = sorted(
        (key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key not in KNOWN_TRACKING_PARAMS
    )
    path = parsed.path.rstrip("/") or "/"
    normalized = parsed._replace(netloc=parsed.netloc.lower(), path=path, query=urlencode(query_pairs), fragment="")
    return urlunparse(normalized)


def evidence_origin(finding: Finding) -> str:
    """The real, normalized page/document this Finding's evidence was
    actually read from -- derived from `Finding.evidence` (a real
    observed URL, see knowledge_source_research.py/browser_research.py),
    NEVER from `Finding.source` (an internal ATLAS sensor name -- using
    it here would be exactly the "sensor counted as real-world
    provenance" mistake this module exists to prevent). Returns "" --
    honest UNKNOWN, never fabricated -- when `Finding.evidence` isn't a
    real, parseable URL."""
    return normalize_url(finding.evidence)


def _origin_eligible(finding: Finding) -> bool:
    """Whether this Finding's origin is trustworthy enough to contribute
    to independent-source counting ON ITS OWN (i.e. with no known
    claimant). A known claimant already establishes real-world
    provenance directly -- origin is always additionally safe to record
    once claimant is known, since it can never be the SOLE basis for a
    false-independence merge at that point (see
    `_known_identifiers()`). When claimant is unknown, origin is trusted
    only for the roles in `_ORIGIN_TRUSTED_ROLES` -- a
    "relay_or_quote" or fully UNKNOWN ("") role artifact is exactly the
    quote-relay overcount case (three different sites relaying the same
    one real vendor claim, each a different real origin) this gate exists
    to close: excluded here, never merged, never counted."""
    if finding.claimant:
        return True
    return finding.evidence_role in _ORIGIN_TRUSTED_ROLES


def _known_identifiers(finding: Finding) -> set[tuple[str, str]]:
    """Every real, known way of naming "who/where this evidence really
    comes from" for this one Finding -- 0, 1, or 2 identifiers. A
    Finding with zero known identifiers is fully UNKNOWN provenance.

    The union-find merge logic in `independent_source_count()` below is
    completely unchanged by the Evidence Role Gate -- this function is
    the only thing that changed: origin is only added as a real
    identifier when `_origin_eligible()` says the origin can be trusted
    on its own (see that function's own docstring). Claimant is never
    gated by role -- a known claimant always participates exactly as it
    always has."""
    identifiers: set[tuple[str, str]] = set()
    if finding.claimant:
        identifiers.add(("claimant", finding.claimant))
    origin = evidence_origin(finding)
    if origin and _origin_eligible(finding):
        identifiers.add(("origin", origin))
    return identifiers


def independent_source_count(findings: list[Finding]) -> int:
    """The one, canonical, sense-agnostic API every real-independence
    consumer in this codebase should use instead of `len(findings)`.

    Union-find over real, known claimant/origin identifiers: two
    Findings merge into the same real-world-source group the moment
    they share ANY known identifier (claimant OR origin) -- transitively,
    so A~B (shared claimant) and B~C (shared origin) correctly puts all
    three in one group even with no direct A~C link. A Finding with
    zero known identifiers (fully UNKNOWN provenance) is excluded
    entirely -- it never inflates the count, and it never gets treated
    as "the same as" or "different from" anything else. Returns the
    real count of distinct groups among Findings that have at least one
    known identifier -- never a count that includes UNKNOWN Findings."""
    known = [f for f in findings if _known_identifiers(f)]
    if not known:
        return 0

    parent: dict[str, str] = {f.id: f.id for f in known}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(a: str, b: str) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_a] = root_b

    identifier_to_finding_id: dict[tuple[str, str], str] = {}
    for finding in known:
        for identifier in _known_identifiers(finding):
            if identifier in identifier_to_finding_id:
                union(finding.id, identifier_to_finding_id[identifier])
            else:
                identifier_to_finding_id[identifier] = finding.id

    return len({find(f.id) for f in known})
