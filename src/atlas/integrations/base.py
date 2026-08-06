from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

# Two genuinely different capability shapes, kept as separate, narrow
# Protocols rather than one "PlatformProvider" interface — the same
# discipline atlas.core.capabilities already uses (Runnable/Triggerable/
# Reportable are separate, not one "Asset" interface). A commerce platform
# (Digistore24, Amazon, AliExpress, Etsy, Shopify, Gumroad) has trackable
# links and sales data; a content platform (YouTube, TikTok, Instagram)
# publishes content — nothing about link-validation or sales data applies
# to the second family, and nothing about publishing applies to the first.
#
# ContentPublisher is defined here (the interface future content-platform
# work will implement) but deliberately has no implementation anywhere yet.
# publishing_gateway is "still, deliberately, a dead end" (CLAUDE.md) — no
# external API call exists anywhere in this codebase — and building a real
# YouTube/TikTok/Instagram publisher (real OAuth, real upload) is a much
# bigger, separately-scoped decision than this layer's job to make.


@runtime_checkable
class CommerceProvider(Protocol):
    """A real-world platform ATLAS can sell through or earn affiliate
    commission from. Every provider (Digistore24 today; Amazon, AliExpress,
    Etsy, Shopify, Gumroad in the future) implements this same shape —
    adding a platform means adding one class satisfying this Protocol and
    one entry in registry.PROVIDERS, never touching atlas.core/atlas.brain
    or any existing provider.
    """

    name: str
    # The Finding/Task category this provider serves (e.g. "affiliate") —
    # what makes it possible to ask "which registered providers are even
    # eligible for this category" without any credential or network call.
    # A structural fact about the provider, not a runtime decision.
    category: str

    def validate_link(self, url: str) -> bool:
        """Whether `url` is a real, correctly-formed tracking/product link
        for this provider. Pure pattern-matching — no network call, so this
        is always safe to call with no credentials configured."""
        ...

    def fetch_recent_sales(self) -> list[dict] | None:
        """Real, live conversion/commission data from this provider's own
        API, if a real credential is configured and the live call is
        actually implemented. None means "not available right now" —
        either no credential is configured, or (honestly, for a provider
        still being built out) the real API call itself doesn't exist yet.
        Never an empty list standing in for "checked, found nothing" when
        nothing was actually checked — that would be exactly the kind of
        fabricated-looking success this codebase's fail-closed rule exists
        to prevent.
        """
        ...


@runtime_checkable
class ContentPublisher(Protocol):
    """A platform ATLAS can publish content to — YouTube, TikTok,
    Instagram, and future content platforms. Reserved: no implementation
    exists yet anywhere in this codebase. Building one is a separate,
    explicitly-scoped decision (real OAuth app registration, real content
    upload, real credentials) — not something this layer's existence
    implies is ready to build."""

    name: str

    def publish(self, content: dict) -> dict: ...


@runtime_checkable
class MarketSignalProvider(Protocol):
    """A real source of external demand/market signal data — search
    trends, a marketplace's product catalog, social platform trending
    topics, and similar (2026-08-03, Opportunity Discovery V1). Reserved,
    the same way ContentPublisher is: no implementation exists yet
    anywhere in this codebase. Picking and integrating one is a separate,
    explicitly-scoped, credentialed decision — not something this
    Protocol's existence implies is ready to build. See
    atlas.integrations.signal_registry, which starts empty for exactly
    this reason.
    """

    name: str
    # The Finding/Task category this signal source is evidence for (e.g.
    # "affiliate") — the same structural, no-credential-required fact
    # CommerceProvider.category already establishes.
    category: str

    def fetch_signals(self) -> list[dict] | None:
        """Real, live demand-signal data from this source, if a real
        credential is configured and the live call is actually
        implemented. None means "not available right now" — no credential
        configured, or the real API call itself isn't built yet. Never an
        empty list standing in for "checked, found nothing" when nothing
        was actually checked — the same fail-closed rule
        CommerceProvider.fetch_recent_sales() already follows."""
        ...


@dataclass
class Opportunity:
    """A normalized, provider-agnostic revenue opportunity (2026-08-04,
    Multi-Source Opportunity Discovery Engine V1) — the one shared shape
    every OpportunityProvider returns, regardless of how different their
    real underlying data is (Digistore24 marketplace stats vs. a future
    provider's own real commission data). Mirrors Finding's "real
    evidence, honestly incomplete" discipline: `score` is None (never a
    fabricated 0.0) until a provider's own real data can compute one,
    and `raw` always carries the real, unmodified source data a
    provider's score was actually computed from, for traceability.
    """

    provider: str
    external_id: str
    title: str
    category: str = ""
    score: float | None = None
    url: str = ""
    raw: dict = field(default_factory=dict)
    error: str | None = None


@runtime_checkable
class OpportunityProvider(Protocol):
    """A real source of revenue opportunities for the Opportunity
    Discovery Engine (atlas.brain.opportunity_discovery_engine) —
    narrower and more specific than MarketSignalProvider above (which
    stays reserved for its original, broader scope: search trends,
    social trending topics, and other signals that aren't necessarily a
    scored "opportunity" at all). One real class per real affiliate
    network/marketplace, each normalizing its own real data into the
    same Opportunity shape. Digistore24SignalProvider (atlas.brain.
    digistore24_opportunity_discovery) is the first real implementation;
    the Amazon Associates/AliExpress/CJ/Impact/ShareASale placeholders
    (atlas.integrations.affiliate_provider_placeholders) are honest,
    structural placeholders — reserved, zero real API calls, the same
    "no fabrication" discipline ContentPublisher already established for
    an unbuilt integration."""

    name: str
    category: str

    def fetch_opportunities(self) -> list[Opportunity] | None:
        """Real opportunities from this provider, normalized. None means
        not available right now — no credential configured, or (for a
        placeholder) no real implementation exists yet. Never an empty
        list standing in for "checked, found nothing" when nothing was
        actually checked — the same fail-closed rule every other
        provider Protocol in this codebase already follows."""
        ...


@dataclass
class Resource:
    """A normalized, provider-agnostic discovered resource (2026-08-04,
    Resource Discovery Engine V1) — metadata only, never content.
    `content_hash` exists for change/duplicate detection, not retrieval:
    computing it may require transiently reading a file's real bytes,
    but nothing beyond the digest is ever kept. None for a folder
    (nothing meaningful to hash) or a file whose hash couldn't be
    computed (recorded via `error`, never silently dropped).

    `name` is the real base name (the last path component) — kept
    separate from `path` since a caller querying "what is this called"
    shouldn't have to re-parse a full path. `created_at` is real but
    honestly platform-dependent: on Windows it is a real creation time;
    on POSIX systems the underlying `st_ctime` is the last metadata-
    change time, not creation — never presented as more precise than
    what the real OS actually reports."""

    provider: str
    path: str
    resource_type: str  # "file" | "folder"
    name: str = ""
    size_bytes: int | None = None
    modified_at: str | None = None
    created_at: str | None = None
    content_hash: str | None = None
    raw: dict = field(default_factory=dict)
    error: str | None = None


@runtime_checkable
class ResourceProvider(Protocol):
    """A real source of discoverable resources for the Resource
    Discovery Engine (atlas.brain.resource_discovery_engine) — one real
    class per real storage location, each normalizing its own real
    listing into the same Resource shape. LocalFolderProvider
    (atlas.integrations.local_folder_provider) is the first real
    implementation, and the only one permitted to touch anything without
    an explicit, durable, founder-approved allow-list behind it — see
    that module's own docstring for the full safety discipline. The
    Google Drive/OneDrive/Dropbox/NAS/Gmail placeholders
    (atlas.integrations.resource_provider_placeholders) are honest,
    structural placeholders — reserved, zero real API/network calls, the
    same "no fabrication" discipline ContentPublisher/OpportunityProvider
    already established for an unbuilt integration.
    """

    name: str

    def fetch_resources(self) -> list[Resource] | None:
        """Real resources from this provider, normalized. None means not
        available right now — no approved location configured (for
        LocalFolderProvider: an empty allow-list, never a default/implied
        one), or (for a placeholder) no real implementation exists yet.
        Never an empty list standing in for "checked, found nothing" when
        nothing was actually checked — the same fail-closed rule every
        other provider Protocol in this codebase already follows."""
        ...


# Intelligence Engine V1 (2026-08-05): an explicit, documented, editable
# set of domains -- the same "open-but-bounded" discipline
# influencer.models.TEMPLATE_KINDS already established. A new domain is
# a new string added here, never a new field/dataclass. Human Behavior
# Intelligence exists ONLY to understand people -- never to manipulate
# them or to optimize deception. Every field on Intelligence below stays
# purely observational/descriptive for that domain (a real, cited pain
# point or motivation, never a "trigger" or "exploit" framing) — a
# structural, not just documented, boundary this whole engine respects.
INTELLIGENCE_DOMAINS = {"market", "human_behavior", "competitor", "product", "economic"}


@dataclass
class Intelligence:
    """A normalized, provider-and-domain-agnostic piece of intelligence
    (2026-08-05, ATLAS Intelligence Engine V1) — the one shared shape
    every IntelligenceProvider returns, regardless of domain (a real
    market Finding and a future real competitor-pricing signal look
    nothing alike underneath, same as Resource/Opportunity before it).
    Mirrors their exact "real evidence, honestly incomplete" discipline:
    `confidence` is None (never a fabricated number) unless a real
    computation actually produced one, and `raw` always carries the
    real, unmodified source data a provider's summary was built from.

    Collection only — this object is never generated, only ever
    normalized from something a provider actually observed. `subject`
    +`provider` together are this object's real identity (the same
    "no synthetic id" discipline Resource(path)/Opportunity(external_id)
    already established, keeping atlas.integrations dependency-free)."""

    provider: str
    domain: str
    subject: str
    summary: str
    source: str = ""
    evidence: str = ""
    market: str = ""
    confidence: float | None = None
    collected_at: str = ""
    raw: dict = field(default_factory=dict)
    error: str | None = None


@dataclass
class PageObservation:
    """Real, raw content read from one real page visit (2026-08-06,
    BrowserObserver V1) — never summarized or fabricated by this layer.
    Mirrors Resource/Opportunity/Intelligence's exact "real evidence,
    honestly incomplete" discipline: every field is either real data
    actually extracted from the page, or its honest empty/default value,
    never a guess. `structured_data` carries whatever specific fields a
    caller asked to extract (see BrowserObserver.observe's `extract`
    param); `text_content` is the real, raw page text, always present
    when a page was successfully reached. `screenshot_path`, when set,
    points to a real file on disk — never a fabricated reference."""

    url: str
    title: str
    text_content: str
    structured_data: dict = field(default_factory=dict)
    screenshot_path: str = ""
    fetched_at: str = ""
    error: str | None = None


@runtime_checkable
class BrowserObserver(Protocol):
    """A real, read-only browser capability (2026-08-06, BrowserObserver
    V1) — navigate to a real public URL and observe its real content.
    Deliberately narrower than a general browser-automation interface:
    this Protocol has no click/type/submit/login capability at all —
    only observation. Real, authenticated, or interactive browsing (the
    "act" side) is a structurally separate, higher-risk capability
    (a future BrowserActionAgent) that this Protocol does not, and is
    not meant to, provide — the same two-tier split CommerceProvider
    (read: fetch_recent_sales) and ContentPublisher (write: publish)
    already establish one layer up.

    One real implementation per real browser-automation backend — see
    atlas.integrations.browser_observer_registry (BROWSER_OBSERVERS,
    starts empty, mirrors signal_registry.SIGNAL_PROVIDERS exactly) for
    where a real implementation gets registered once one is chosen. No
    implementation exists anywhere in this codebase yet, the same
    "Protocol defined, real class lives in its own module, registry
    starts empty" pattern this codebase already establishes for every
    other unbuilt provider.
    """

    name: str

    def observe(self, url: str, extract: dict[str, str] | None = None) -> PageObservation:
        """Navigates to the real `url` and returns its real content.
        `extract` (optional) names specific fields to pull out, e.g.
        {"price": "the listed price"} — when omitted, only real raw
        title/text is returned. Raises on a real, unrecoverable failure
        (page unreachable, timeout) rather than returning a fabricated
        empty observation — the same fail-loud discipline
        Digistore24Provider's Digistore24APIError already establishes
        for a real, unexpected failure."""
        ...


@runtime_checkable
class AIProvider(Protocol):
    """A real AI backend ATLAS can route a task to (2026-08-06, AI
    Orchestrator V1). Before this Protocol existed, every caller that
    needed an AI call picked its own backend directly and hardcoded it
    (browser_use_observer.py instantiated ChatGoogle itself; the
    Claude executive connection was its own standalone, ungeneralized
    function -- explicitly documented at the time as "no Protocol, no
    provider registry... generalizing before a second [implementation]
    exists would be premature," per claude_provider.py). That second
    real implementation now exists (Claude, via the CLI), which is
    exactly the trigger that docstring named -- this Protocol is that
    generalization, not a premature one.

    Two real, general capabilities, not the full surface either real
    backend happens to expose: `complete` (a prompt in, real text out
    -- the one primitive every AI backend genuinely shares) and
    `complete_structured` (a prompt plus named fields in, a real dict
    of extracted values out -- what real, existing callers like
    BrowserObserver's evidence extraction actually need). Every
    provider implements both, the same "every provider implements the
    full Protocol shape, capability limits are expressed through
    behavior, never a missing method" discipline CommerceProvider.
    fetch_recent_sales() already established.

    One real class per real AI backend -- see
    atlas.integrations.ai_provider_registry (AI_PROVIDERS) for where a
    real implementation gets registered. Adding a backend means one
    new class satisfying this Protocol and one registry entry, never
    touching an existing provider or any caller -- the same extension
    discipline CommerceProvider/BrowserObserver/MarketSignalProvider
    already established three times over in this codebase.
    """

    name: str

    def complete(self, prompt: str) -> str:
        """Sends `prompt` to the real backend and returns its real,
        raw text response. Raises on a real, unrecoverable failure
        (missing credential, network/process failure, an error the
        backend itself reports) rather than returning a fabricated
        empty string -- the same fail-loud discipline every other
        provider Protocol in this codebase already establishes."""
        ...

    def complete_structured(self, prompt: str, fields: dict[str, str]) -> dict[str, str]:
        """Asks the real backend to extract/answer the named `fields`
        (field name -> what it means, e.g. {"price": "the listed
        price"}) from `prompt`, and returns the real values found --
        an empty string for a field genuinely absent from the real
        response, never an invented value. Raises on a real,
        unrecoverable failure, the same as `complete`."""
        ...


@runtime_checkable
class KnowledgeSourcePlugin(Protocol):
    """A real, pluggable knowledge source (2026-08-06, Knowledge
    Sources V1) — the general mechanism behind "ATLAS learns from any
    relevant business knowledge source: websites, documents, and in
    the future YouTube/TikTok/Instagram/Facebook/podcasts and other
    business sources," without the orchestrating code ever needing to
    know which kind of source it's talking to. Deliberately organized
    by real-world source, never by media type — a YouTube video is
    one source (video + audio + transcript + metadata together), not
    three separate plugins, because that's what it structurally is in
    the real world, not an artifact of how a computer decodes it.

    `can_handle(source_ref)` is pure, side-effect-free format
    recognition only (e.g. "is this an http(s) URL") — never a
    permission or credential check; real implementations (see
    atlas.brain.browser_plugin/document_plugin) each own their real
    policy check internally (a domain allowlist, a folder allowlist)
    inside `observe()`, the same fail-closed-by-default discipline
    every allowlist in this codebase already establishes, since
    different real source types genuinely need different allowlist
    mechanisms and the dispatch loop must never need to know which.

    One real class per real source type — see
    atlas.brain.knowledge_source_registry (KNOWLEDGE_SOURCE_PLUGINS)
    for where a real implementation gets registered. Adding a source
    (a document, and in the future a video/audio/social source) means
    one new class satisfying this Protocol and one registry entry,
    never touching this Protocol, the registry's dispatch logic, or
    any existing plugin — the same extension discipline
    CommerceProvider/BrowserObserver/AIProvider already establish.

    Real implementations live in atlas.brain, not atlas.integrations
    (the same split IntelligenceProvider/FindingsMarketIntelligence
    Provider already establish) — a real plugin here inherently
    carries brain-layer policy (an allowlist), not just a raw,
    policy-free platform connection.
    """

    name: str

    def can_handle(self, source_ref: str) -> bool:
        """Whether this plugin's real backend can observe `source_ref`
        at all, purely by its form (a URL, a file path, ...) — never a
        permission check, never a network/disk call."""
        ...

    def observe(self, source_ref: str, extract: dict[str, str] | None = None) -> PageObservation:
        """Reads `source_ref`'s real content and returns it. Raises on
        a real, unrecoverable failure — not approved by this plugin's
        own real allowlist, unreachable/not found, or any other real
        failure — never a fabricated empty observation, the same
        fail-loud discipline every other real observer in this
        codebase already establishes."""
        ...


@runtime_checkable
class IntelligenceProvider(Protocol):
    """A real source of intelligence for the Intelligence Engine
    (atlas.brain.intelligence_engine) — one real class per real
    intelligence source, each normalizing its own real observations into
    the same Intelligence shape. FindingsMarketIntelligenceProvider
    (atlas.brain.market_intelligence_provider) is the first real
    implementation — it wraps this codebase's own already-real,
    already-recorded Finding evidence rather than a new external API,
    which is honest and real without being a new fabricated data source.
    The Human Behavior/Competitor/Product/Economic placeholders
    (atlas.integrations.intelligence_provider_placeholders) are honest,
    structural placeholders — reserved, zero real API calls, the same
    "no fabrication" discipline every other unbuilt provider in this
    codebase already follows.
    """

    name: str
    domain: str

    def fetch_intelligence(self) -> list[Intelligence] | None:
        """Real intelligence from this provider, normalized. None means
        not available right now — no real data source configured, or
        (for a placeholder) no real implementation exists yet. An empty
        list is a real, successful check that found nothing (e.g. a real
        KnowledgeBase with zero Findings yet) — genuinely different from
        None, the same fail-closed distinction every other provider
        Protocol in this codebase already makes."""
        ...
