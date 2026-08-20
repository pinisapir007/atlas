"""Verify-the-verifier: actuators must never certify their own outcome
(2026-08-17, ONE BRAIN Root Implementation, Gate 3). Python dataclasses
have no real field-level access control -- no invariant in this
codebase is enforced by the language itself (not even "Bridge 1 is the
sole Opportunity writer"). The proven, existing mechanism for exactly
this class of un-enforceable-by-language rule is a structural test via
inspect.getsource(), the same technique already proven twice
(test_reasoning_claims.py's Delegator/Registry/RiskPolicy import
firewall; test_m1_marketplace_discovery_safety_wiring.py's BrowserHands
exclusion) -- reused here a third time, not invented."""

import inspect
from pathlib import Path

ASSET_AGENT_FILES = sorted(Path("src/atlas/assets").glob("*/agent.py"))


def test_every_real_asset_agent_file_exists_to_check():
    """Sanity: the glob itself must actually find real files, or the
    structural test below would silently pass on nothing."""
    assert len(ASSET_AGENT_FILES) >= 10


def test_no_asset_agent_writes_task_verification_status_directly():
    """Actuator self-report is never source-of-truth for outcome --
    checks the real, installed source of every registered asset's
    agent.py, not a mention in prose."""
    for path in ASSET_AGENT_FILES:
        source = path.read_text(encoding="utf-8")
        assert "verification_status" not in source, (
            f"{path} must never write Task.verification_status directly -- "
            "only an independent, action-specific verifier (never the actuator itself) may."
        )


def test_no_asset_agent_writes_verification_evidence_id_directly():
    for path in ASSET_AGENT_FILES:
        source = path.read_text(encoding="utf-8")
        assert "verification_evidence_id" not in source, (
            f"{path} must never write Task.verification_evidence_id directly."
        )


def test_no_asset_agent_module_imports_task_verification_required():
    """A real asset has no legitimate reason to catch/reference the
    guard exception itself -- that belongs to the shared Task.
    try_complete()/transition() machinery only."""
    import atlas.brain.models as models_module

    source = inspect.getsource(models_module)
    assert "class TaskVerificationRequired" in source  # sanity: the real guard exists where expected

    for path in ASSET_AGENT_FILES:
        agent_source = path.read_text(encoding="utf-8")
        assert "TaskVerificationRequired" not in agent_source
