import os


def opportunity_discovery_v1_enabled() -> bool:
    """Whether Opportunity Discovery V1's real-evidence-driven behavior is
    live against production data — off by default (2026-08-03).

    The founder's explicit instruction: keep every new Opportunity
    Discovery capability disconnected from real production until it's
    explicitly approved, even while development continues. This is the one
    switch that separates the two: with ATLAS_OPPORTUNITY_DISCOVERY_V1
    unset, the real, currently-running production tick (the Windows
    Scheduled Task, see atlas-autonomy-policy) behaves exactly as it does
    today — this module's code existing in the working tree changes
    nothing on its own.

    A live os.environ check (not a cached module-level constant) so the
    flag can be flipped without a restart and tests can toggle it per case
    — the same env-var-gated-inertness pattern already established by
    DIGISTORE24_API_KEY (atlas.integrations.digistore24). Kept in its own
    module rather than inside confidence.py or opportunity_discovery_advance.py
    since both need to read it.
    """
    return bool(os.environ.get("ATLAS_OPPORTUNITY_DISCOVERY_V1"))


def executive_discovery_enabled() -> bool:
    """Whether Executive Discovery (Milestone 1, docs/
    EXECUTIVE_DISCOVERY_DESIGN_REVIEW.md) is live -- off by default, the
    identical env-var-gated-inertness pattern opportunity_discovery_v1_
    enabled() already established, for the identical reason: a real,
    evidence-based finding, not a guess -- running the full test suite
    against the unconditionally-wrapped decide() broke a large number of
    existing, locked, single-category tests (every one of them
    legitimately tests one category in isolation, which Exploration
    Before Commitment's breadth gate correctly refuses to commit to
    until real evidence exists across several categories), and let the
    new ResearchDiscoveryAgent's real browser/network calls run
    unmocked inside the general suite, extending it from its normal
    runtime to 43 minutes. With ATLAS_EXECUTIVE_DISCOVERY_ENABLED unset,
    atlas.brain.discovery.decide.decide_with_discovery() defers straight
    to the real, unmodified decision_engine.decide() and advance_
    executive_discovery() is a no-op -- today's production tick behaves
    exactly as it does now; this module's code existing in the working
    tree changes nothing on its own."""
    return bool(os.environ.get("ATLAS_EXECUTIVE_DISCOVERY_ENABLED"))


def video_research_enabled() -> bool:
    """Whether autonomous Video Research source discovery may create real
    video_research Tasks.

    Off by default. The VideoResearchAsset itself may exist and be directly
    dispatchable while this bridge remains completely inert. This separation
    is deliberate because discovering a YouTube source can consume YouTube
    API quota and executing the resulting Task can consume Gemini usage.
    """
    return bool(os.environ.get("ATLAS_VIDEO_RESEARCH_ENABLED"))



def sales_sync_enabled() -> bool:
    """Whether autonomous real financial synchronization may run in tick().

    Off by default. When enabled, ATLAS may make authenticated read-only
    Digistore24 financial API calls and persist only attributable,
    idempotent real financial events into KPI/Ledger.
    """
    return bool(os.environ.get("ATLAS_SALES_SYNC_ENABLED"))



def pattern_hypothesis_enabled() -> bool:
    """Whether Stage 7 / Layer 2 may autonomously scan newly-arrived
    durable Findings and form bounded hypothesis Claims.

    Off by default. When disabled, the production tick performs zero
    semantic-selection/reasoning AI calls for this capability.

    Enabling this does NOT grant execution authority: the Layer-2 bridge
    may persist Claim knowledge only. It cannot create/dispatch Tasks,
    Goals, Decisions, campaigns, spending, publishing, or other actions.
    """
    return bool(os.environ.get("ATLAS_PATTERN_HYPOTHESIS_ENABLED"))


def research_mission_enabled() -> bool:
    """Whether durable Research Mission orchestration may advance.

    Off by default.

    Research Mission is orchestration only: enabling this flag does not
    authorize publishing, spending, account changes, legal commitments,
    or any other external action. Source access remains independently
    constrained by the existing BrowserAllowlist/ResourceAllowlist and
    each KnowledgeSourcePlugin's own fail-closed safety checks.
    """
    return bool(os.environ.get("ATLAS_RESEARCH_MISSION_ENABLED"))
