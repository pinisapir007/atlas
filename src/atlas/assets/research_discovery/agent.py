"""ResearchDiscoveryAgent -- the real Asset that fulfills Executive
Discovery's Research Trigger (Milestone 1, docs/
EXECUTIVE_DISCOVERY_DESIGN_REVIEW.md, Mechanism 2).

Confirmed missing before this was built (verified directly against the
real code, not assumed): no open-topic "give me a topic, bring me real
sources" capability existed anywhere in this codebase --
GeminiProvider only operates on already-supplied content, and
MarketSignalProvider/OpportunityProvider are empty Protocols with zero
implementations. Built on the already-real, already-proven
BrowserUseObserver rather than a new credentialed integration --
navigates to a real public search-results page and asks the same real,
injectable AIProvider BrowserUseObserver already uses to extract real
result titles/URLs/snippets from the real fetched page text (never a
second, separate scraping mechanism).

Never fabricates a result: a real search/extraction failure is recorded
as an honest "failed" outcome, not a fabricated Finding; a real result
set with fewer than RESULT_COUNT entries is recorded exactly as found,
never padded -- the same loud-failure, never-fabricate discipline every
other real provider in this codebase already establishes.

Evidence Validation (2026-08-11, Qualification Framework Step 1, "Reuse
Before Build") -- the real, already-existing, already-tested
atlas.brain.evidence_validation.assess_observation_quality() now gates
the whole real search-results observation before any extraction/saving
happens at all, exactly the same call shape knowledge_source_research.
collect_evidence_from_source() already established (observe -> validate
-> only then save). Deliberately a page-level gate, not a per-result
one: assess_observation_quality() was built to judge one real
observation's raw text against one real task description, not to
re-judge each of RESULT_COUNT individually-extracted snippets -- doing
that would be building new behavior on top of the existing mechanism,
not reusing it. Honestly documented as a real limitation, not hidden:
this catches an irrelevant/empty/erroring search as a whole, not a
single bad result mixed into an otherwise-good page.

Autonomous Subject Discovery (2026-08-11, closing Root Cause A, docs/
DESIGN_GAP_A_SUBJECT_DISCOVERY.md) -- until now this agent never filled
Finding.subject, the real, root-caused reason Bridge 1 (Finding ->
Opportunity) could never fire autonomously (docs/
ROOT_CAUSE_ANALYSIS_RUN4.md). Real, live-tested fix, not assumed: the
search query changed from a definitional query ("{category} business
model revenue online") to a candidate-seeking one ("best {category}
products to sell 2026") -- proven insufficient alone (extraction was
never the problem; the definitional query rarely returns pages that
name a specific candidate at all). The real, decisive missing piece was
navigation depth: the SERP snippet itself never contains real candidate
names -- they live on the destination page. This agent now navigates
into the real, top real SERP result and extracts real candidates from
that page's own real content -- live-verified across 6 real, different
textual categories (digital_product, saas, shopify, seo,
email_marketing, ai_tools), zero complete failures.

Two real, evidence-backed filters reject a non-candidate before it ever
becomes a Finding: the candidate equals the category itself (a trivial,
useless echo -- live-observed for `youtube`, the AI reliably "extracts"
the category name back when the page has no real specific candidate),
and the candidate equals the source page's own site brand (live-
observed repeatedly -- a blog's own name, e.g. "Elementor"/"Merchize",
extracted as if it were a recommended product).

Known Limitation, named on purpose, not hidden (founder's own explicit
decision, 2026-08-11): a byline-shaped name (a real article's author,
e.g. "Itamar Haim") can still leak through as a false-positive
candidate. No real, evidence-backed mechanical rule to reject this
exists yet -- any naive heuristic (e.g. "two capitalized words") risks
rejecting real, legitimate two-word candidates too (e.g. "Notion
Templates", already proven real). Deliberately left unfiltered rather
than guessed at: this is a Qualification-measured question, not an RCA
question -- if live measurement shows meaningful leakage, a real,
evidence-backed RCA opens for it then, not before.

Explicitly out of scope, named in the locked Design doc, not silently
dropped: `Finding.market` stays unset (no experiment ever tested market
extraction); video content (e.g. real youtube.com pages) is real,
navigable, but yields no candidates here -- the observer reads page
text/metadata, not video transcripts, a different, unbuilt mechanism.
"""

from urllib.parse import quote, urlparse

from atlas.brain.discovery.research_request import category_from_research_task
from atlas.brain.evidence_role_classification import UNKNOWN as ROLE_UNKNOWN
from atlas.brain.evidence_role_classification import classify_evidence_role
from atlas.brain.evidence_validation import assess_observation_quality
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Finding
from atlas.integrations.base import AIProvider
from atlas.integrations.browser_use_observer import BrowserUseError, BrowserUseObserver

SEARCH_URL_TEMPLATE = "https://duckduckgo.com/html/?q={query}"
RESULT_COUNT = 5
SOURCE_NAME = "research_discovery"
# Real, live-tested candidate-seeking query shape (docs/
# ROOT_CAUSE_ANALYSIS_RUN4.md, H2 + navigation) -- deliberately the
# exact wording already validated across 6 real categories, not a new,
# untested rewording.
CANDIDATE_QUERY_TEMPLATE = "best {category} products to sell 2026"
MAX_CANDIDATES_PER_PAGE = 10


def _extract_fields() -> dict[str, str]:
    fields = {}
    for i in range(1, RESULT_COUNT + 1):
        fields[f"result_{i}_title"] = "the title of this real search result"
        fields[f"result_{i}_url"] = "the real URL of this search result"
        fields[f"result_{i}_snippet"] = "the real snippet/description text shown for this search result"
    return fields


def _candidate_extract_fields() -> dict[str, str]:
    fields = {}
    for i in range(1, MAX_CANDIDATES_PER_PAGE + 1):
        fields[f"candidate_{i}"] = (
            f"the name of the {i}-th specific real product, brand, tool, or creator this page actually "
            "recommends/lists/discusses as one of its real items -- not a generic term. Empty string if "
            "this page names fewer than that many specific real items."
        )
    return fields


def _normalize_url(raw_url: str) -> str:
    # Real, observed harness/AI-extraction gap (docs/
    # ROOT_CAUSE_ANALYSIS_RUN4.md): a real URL extracted from a SERP
    # sometimes comes back missing its scheme -- never navigable as-is.
    return raw_url if raw_url.startswith(("http://", "https://")) else f"https://{raw_url}"


def _source_site_brand(url: str) -> str:
    """A simple, mechanical, real fact about a URL -- its own domain's
    brand-like root (e.g. "https://elementor.com/blog/..." ->
    "elementor") -- never a judgment call. Used only to reject a
    candidate that's really just the source page's own site name."""
    host = urlparse(url).netloc.removeprefix("www.")
    return host.split(".")[0].replace("-", " ").replace("_", " ").strip().lower()


def _is_valid_candidate(candidate: str, category: str, source_url: str) -> bool:
    normalized = candidate.strip().lower()
    if not normalized:
        return False
    if normalized == category.replace("_", " ").strip().lower():
        return False  # trivial category echo, live-observed for youtube
    if normalized == _source_site_brand(source_url):
        return False  # site self-reference, live-observed repeatedly
    return True


class ResearchDiscoveryAgent:
    def __init__(
        self,
        knowledge: KnowledgeBase | None = None,
        observer: BrowserUseObserver | None = None,
        ai_provider: AIProvider | None = None,
    ):
        self._knowledge = knowledge if knowledge is not None else KnowledgeBase()
        self._observer = observer if observer is not None else BrowserUseObserver()
        self._ai_provider = ai_provider  # None -> assess_observation_quality()'s own real default

    def run(self, task=None, **kwargs) -> dict:
        # Delegator's unmatched-fallback path can hand this agent ANY
        # task, not just a real request_research one (the same real
        # risk atlas.hands.agent.HandsAgent already guards against for
        # its own "no real correlated request" case) -- an honest
        # "failed" result here, never an uncaught ValueError that would
        # crash the whole delegate()/tick() call for an unrelated task.
        try:
            category = category_from_research_task(task)
        except (ValueError, AttributeError) as exc:
            return {"status": "failed", "reason": f"not a real research-trigger task: {exc}"}

        query = CANDIDATE_QUERY_TEMPLATE.format(category=category.replace("_", " "))
        return self.execute_step(category, query)

    def execute_step(self, category: str, query: str, source: str = SOURCE_NAME) -> dict:
        """One real, bounded research step: search `query`, quality-gate
        the real SERP, save its real generic findings, then navigate into
        the top real result and save any real subject-bearing candidates.
        Extracted (2026-08-18, P0 Independence Mission) so a bounded,
        multi-step caller (atlas.assets.deep_research.agent.
        DeepResearchAgent) can run several real, differently-worded steps
        for the same category without duplicating this logic -- run()
        above is now just "one step with the original, proven query."
        `source` defaults to this agent's own SOURCE_NAME (zero behavior
        change to run() itself, re-verified against this file's own
        existing test suite) -- a caller running its own multi-step
        escalation passes its own source name instead, so every Finding
        stays honestly attributed to the real agent that produced it,
        never silently mislabeled as this one."""
        url = SEARCH_URL_TEMPLATE.format(query=quote(query))

        try:
            observation = self._observer.observe(url, extract=_extract_fields())
        except BrowserUseError as exc:
            return {"status": "failed", "category": category, "findings_created": 0, "reason": f"real search failed: {exc}"}

        # Judges the SERP page itself (titles/snippets of pages ABOUT
        # candidates) -- not whether it already names specific
        # candidates. Real candidates live one level deeper, on the
        # destination page _discover_subjects() navigates into below;
        # demanding them here caused a real, live, spurious failure
        # (the SERP is legitimately just a list of article titles).
        task_description = f"real, current pages about specific products/tools worth selling in the '{category}' category"
        quality = assess_observation_quality(observation, task_description, ai_provider=self._ai_provider)
        if not quality.passed:
            return {
                "status": "failed",
                "category": category,
                "findings_created": 0,
                "reason": f"real search results failed evidence quality: {quality.reason}",
            }

        findings_created = self._save_findings(category, observation.structured_data, source=source)
        findings_created += self._discover_subjects(category, observation.structured_data, source=source)
        return {"status": "done", "category": category, "findings_created": findings_created}

    def report(self) -> dict:
        # Aggregate, not task-specific -- Reportable.report() takes no
        # arguments, computed fresh from KnowledgeBase every call, not
        # cached in-memory state (an asset instance doesn't survive
        # across separate CLI/tick invocations; only real, durable
        # storage does), the same discipline every other asset's
        # report() already follows.
        findings = [f for f in self._knowledge.findings() if f.source == SOURCE_NAME]
        return {"status": "done", "total_findings": len(findings)}

    def _save_findings(self, category: str, structured: dict, source: str = SOURCE_NAME) -> int:
        created = 0
        for i in range(1, RESULT_COUNT + 1):
            title = structured.get(f"result_{i}_title", "")
            url = structured.get(f"result_{i}_url", "")
            snippet = structured.get(f"result_{i}_snippet", "")
            if not title or not url:
                continue  # a real, honest gap -- fewer than RESULT_COUNT real results found, never padded
            finding = Finding(
                source=source,
                category=category,
                description=f"{title} -- {snippet}".strip(" -"),
                evidence=url,
            )
            self._knowledge.save_finding(finding)
            created += 1
        return created

    def _discover_subjects(self, category: str, serp_data: dict, source: str = SOURCE_NAME) -> int:
        """Root Cause A closure (docs/DESIGN_GAP_A_SUBJECT_DISCOVERY.md):
        navigates into the real, top real SERP result and extracts real,
        specific candidates from that page's own real content -- the
        only step in this whole agent that ever fills Finding.subject.
        Additive to _save_findings() -- never replaces the existing
        generic, subject-less Findings, which still matter for
        category-level evidence (confidence_score()) independent of any
        specific candidate. A real navigation failure here degrades
        honestly to zero new Findings, never a fabricated one and never
        a crash of the whole run() call -- the base Findings from
        _save_findings() already happened by the time this runs."""
        title = serp_data.get("result_1_title", "")
        raw_url = serp_data.get("result_1_url", "")
        if not raw_url:
            return 0

        target_url = _normalize_url(raw_url)
        try:
            page = self._observer.observe(target_url, extract=_candidate_extract_fields())
        except BrowserUseError:
            return 0  # honest degradation -- known limitation, not a crash

        # Evidence Role Classification (2026-08-17, ONE BRAIN Web Evidence
        # Role Classification): the Brain, not this sensor, decides what
        # kind of relationship this page has to its real-world source.
        # Classified once for the whole page (every candidate Finding
        # below shares the same real observation/origin) -- reuses the
        # exact same classifier browser_research.py/knowledge_source_
        # research.py use, no local role logic. No subject-verification
        # step here (unlike those two): this function DISCOVERS candidate
        # subjects from the page rather than verifying a pre-known one --
        # a structurally different question, not skipped by omission.
        role = classify_evidence_role(page, ai_provider=self._ai_provider)
        evidence_role = "" if role == ROLE_UNKNOWN else role

        created = 0
        for i in range(1, MAX_CANDIDATES_PER_PAGE + 1):
            candidate = page.structured_data.get(f"candidate_{i}", "")
            if not _is_valid_candidate(candidate, category, target_url):
                continue
            finding = Finding(
                source=source,
                category=category,
                subject=candidate,
                description=f"{candidate} -- named as a real candidate on {title or target_url}".strip(" -"),
                evidence=target_url,
                evidence_role=evidence_role,
            )
            self._knowledge.save_finding(finding)
            created += 1
        return created
