import socket
from dataclasses import dataclass

import pytest

from atlas.brain.browser_plugin import (
    BrowserPlugin,
    DomainNotApprovedError,
)
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Finding
from atlas.brain.research_mission_public_https import (
    ResearchMissionPublicHTTPSPolicy,
)
from atlas.brain.research_mission_source_advance import (
    advance_research_mission_sources,
)
from atlas.brain.research_missions import (
    ResearchMission,
    ResearchMissionStore,
)
from atlas.integrations.base import PageObservation


def _resolver(*addresses):
    def resolve(host, port, type=0):
        rows = []

        for address in addresses:
            if ":" in address:
                rows.append(
                    (
                        socket.AF_INET6,
                        socket.SOCK_STREAM,
                        6,
                        "",
                        (address, port, 0, 0),
                    )
                )
            else:
                rows.append(
                    (
                        socket.AF_INET,
                        socket.SOCK_STREAM,
                        6,
                        "",
                        (address, port),
                    )
                )

        return rows

    return resolve


def test_public_https_policy_accepts_public_https():
    policy = ResearchMissionPublicHTTPSPolicy(
        resolver=_resolver("93.184.216.34")
    )

    assert policy.is_approved(
        "https://public.example/research?q=atlas"
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://public.example/report",
        "ftp://public.example/report",
        "https://user:secret@public.example/report",
        "https://public.example:8443/report",
        "https://localhost/report",
        "https://service.local/report",
        "https://service.internal/report",
        "https://metadata.google.internal/computeMetadata/v1/",
        "https://127.0.0.1/report",
        "https://10.0.0.8/report",
        "https://172.16.1.5/report",
        "https://192.168.1.9/report",
        "https://169.254.169.254/latest/meta-data/",
        "https://[::1]/report",
        "https://[fe80::1]/report",
    ],
)
def test_public_https_policy_rejects_nonpublic_targets(url):
    policy = ResearchMissionPublicHTTPSPolicy(
        resolver=_resolver("93.184.216.34")
    )

    assert policy.is_approved(url) is False


def test_public_https_policy_rejects_private_dns_resolution():
    policy = ResearchMissionPublicHTTPSPolicy(
        resolver=_resolver("10.0.0.9")
    )

    assert policy.is_approved(
        "https://public-looking.example/report"
    ) is False


def test_public_https_policy_rejects_mixed_public_private_dns_resolution():
    policy = ResearchMissionPublicHTTPSPolicy(
        resolver=_resolver(
            "93.184.216.34",
            "192.168.1.10",
        )
    )

    assert policy.is_approved(
        "https://mixed.example/report"
    ) is False


def test_public_https_policy_rejects_unresolved_dns():
    def failing_resolver(host, port, type=0):
        raise socket.gaierror("not found")

    policy = ResearchMissionPublicHTTPSPolicy(
        resolver=failing_resolver
    )

    assert policy.is_approved(
        "https://missing.example/report"
    ) is False


class _FakeObserver:
    name = "fake"

    def __init__(self, observation):
        self.observation = observation
        self.calls = []

    def observe(
        self,
        url,
        extract=None,
        verify_target=None,
    ):
        self.calls.append(
            (
                url,
                extract,
                verify_target,
            )
        )
        return self.observation


def test_browser_plugin_with_public_policy_refuses_private_target_before_observer():
    observer = _FakeObserver(
        PageObservation(
            url="https://127.0.0.1/private",
            title="private",
            text_content="private",
        )
    )

    plugin = BrowserPlugin(
        observer=observer,
        allowlist=ResearchMissionPublicHTTPSPolicy(
            resolver=_resolver("93.184.216.34")
        ),
    )

    with pytest.raises(DomainNotApprovedError):
        plugin.observe(
            "https://127.0.0.1/private"
        )

    assert observer.calls == []


def test_browser_plugin_public_policy_rejects_private_redirect_destination():
    observer = _FakeObserver(
        PageObservation(
            url="https://127.0.0.1/private",
            title="private",
            text_content="must not be trusted",
        )
    )

    plugin = BrowserPlugin(
        observer=observer,
        allowlist=ResearchMissionPublicHTTPSPolicy(
            resolver=_resolver("93.184.216.34")
        ),
    )

    with pytest.raises(
        DomainNotApprovedError,
        match="127.0.0.1",
    ):
        plugin.observe(
            "https://public.example/start"
        )


@dataclass
class _GroundedPlugin:
    name: str = "browser"
    raw_text_grounded: bool = True


def test_atomic_collector_plugin_override_prevents_registry_reselection(
    tmp_path,
    monkeypatch,
):
    import atlas.brain.knowledge_source_research as mod

    knowledge = KnowledgeBase(
        tmp_path / "knowledge.json"
    )
    plugin = _GroundedPlugin()
    captured = {}

    def forbidden_select(source_ref):
        raise AssertionError(
            "registry must not reselect when plugin_override is supplied"
        )

    def fake_observe_validated(
        source_ref,
        task_description,
        subject="",
        extract=None,
        ai_provider=None,
        *,
        require_grounded_text=False,
        plugin_override=None,
    ):
        captured["plugin"] = plugin_override

        return (
            plugin_override,
            PageObservation(
                url="https://public.example/report",
                title="report",
                text_content="real grounded source text",
            ),
            "",
        )

    monkeypatch.setattr(
        mod,
        "select_plugin",
        forbidden_select,
    )
    monkeypatch.setattr(
        mod,
        "_observe_validated_source",
        fake_observe_validated,
    )
    monkeypatch.setattr(
        mod,
        "extract_atomic_evidence_from_text",
        lambda *args, **kwargs: [],
    )

    result = mod.collect_atomic_evidence_from_source(
        source_ref="https://public.example/report",
        category="ugc",
        source="research_mission",
        task_description="Research UGC demand",
        knowledge=knowledge,
        ai_provider=object(),
        plugin_override=plugin,
        provider="browser",
    )

    assert result == []
    assert captured["plugin"] is plugin


@dataclass
class _RoutingPlugin:
    name: str


def test_research_mission_browser_source_injects_public_https_browser_policy(
    tmp_path,
    monkeypatch,
):
    import atlas.brain.research_mission_source_advance as mod

    monkeypatch.setenv(
        "ATLAS_RESEARCH_MISSION_ENABLED",
        "1",
    )

    store = ResearchMissionStore(
        tmp_path / "research_missions.json"
    )
    knowledge = KnowledgeBase(
        tmp_path / "knowledge.json"
    )

    mission = ResearchMission(
        goal_id="goal-ed",
        objective="Broad digital research",
    )
    store.save_mission(mission)

    source = store.add_source(
        mission.id,
        "https://public.example/report",
        "ugc",
        "Research UGC demand",
    )

    routing_plugin = _RoutingPlugin("browser")
    injected_plugin = object()
    policy = object()
    captured = {}

    monkeypatch.setattr(
        mod,
        "select_plugin",
        lambda ref: routing_plugin,
    )
    monkeypatch.setattr(
        mod,
        "ResearchMissionPublicHTTPSPolicy",
        lambda: policy,
    )

    def fake_browser_plugin(*, allowlist):
        assert allowlist is policy
        return injected_plugin

    monkeypatch.setattr(
        mod,
        "BrowserPlugin",
        fake_browser_plugin,
    )

    def fake_collect(**kwargs):
        captured.update(kwargs)

        return [
            Finding(
                id="finding-public-web",
                source="research_mission",
                category="ugc",
                description="real evidence",
                evidence="https://public.example/report",
            )
        ]

    monkeypatch.setattr(
        mod,
        "collect_atomic_evidence_from_source",
        fake_collect,
    )

    changed = advance_research_mission_sources(
        store,
        knowledge,
    )

    assert len(changed) == 1
    assert captured["plugin_override"] is injected_plugin
    assert captured["provider"] == "browser"

    restored = store.get_source(source.id)
    assert restored.status == "processed"
    assert restored.finding_ids == [
        "finding-public-web"
    ]
