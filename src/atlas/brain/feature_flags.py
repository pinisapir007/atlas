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
