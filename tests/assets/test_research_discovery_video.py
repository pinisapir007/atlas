from atlas.assets.research_discovery.agent import ResearchDiscoveryAgent
from atlas.integrations.base import VideoEvidence


class FakeKnowledge:
    def __init__(self):
        self.saved = []

    def save_finding(self, finding):
        self.saved.append(finding)

    def findings(self):
        return list(self.saved)


class FakeVideoProvider:
    name = "fake_video"

    def analyze_youtube(self, youtube_url, max_observations=3):
        assert youtube_url == "https://www.youtube.com/watch?v=test123"
        assert max_observations == 3

        return [
            VideoEvidence(
                source_url=youtube_url,
                timestamp="04:14",
                spoken="The speaker discusses starting with why.",
                visual="The speaker points to the center circle.",
                evidence_type="BOTH",
                confidence="HIGH",
            )
        ]


def test_youtube_result_becomes_timestamped_durable_finding():
    knowledge = FakeKnowledge()

    agent = ResearchDiscoveryAgent(
        knowledge=knowledge,
        search_providers=[],
        video_provider=FakeVideoProvider(),
    )

    created, status = agent._research_youtube_evidence(
        "leadership",
        {
            "result_1_url": "https://www.youtube.com/watch?v=test123",
        },
    )

    assert created == 1
    assert status["status"] == "done"
    assert status["provider"] == "fake_video"

    assert len(knowledge.saved) == 1
    finding = knowledge.saved[0]

    assert finding.category == "leadership"
    assert "04:14" in finding.description
    assert "starting with why" in finding.description
    assert "center circle" in finding.description
    assert finding.evidence == (
        "https://www.youtube.com/watch?v=test123 @ 04:14"
    )
