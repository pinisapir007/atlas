class ResearchAgent:
    """Discovers revenue opportunities and classifies which Revenue Agent
    channel each one belongs to (or flags it as a new-channel candidate).

    Discovery itself is a placeholder pending a real demand-signal source
    (market data, search trends, etc.) — replace _discover once one is
    chosen. Classification is real, deterministic keyword matching, the
    same approach SimplePlanner uses for its own category inference.
    """

    _CHANNEL_KEYWORDS = {
        "affiliate": "revenue_affiliate",
        "referral": "revenue_affiliate",
        "digital product": "revenue_digital_product",
        "ebook": "revenue_digital_product",
        "course": "revenue_digital_product",
        "recruit": "revenue_recruitment_leads",
        "staffing": "revenue_recruitment_leads",
        "hiring": "revenue_recruitment_leads",
        "content": "revenue_content_assets",
        "image": "revenue_content_assets",
        "design": "revenue_content_assets",
    }

    _DEFAULT_SIGNALS = [
        "Affiliate opportunity: promote a productivity SaaS tool with a recurring commission program",
        "Staffing opportunity: a regional employer needs warehouse workers and a supplier pool is available",
    ]

    def __init__(self, signals: list[str] | None = None) -> None:
        self._signals = signals if signals is not None else list(self._DEFAULT_SIGNALS)
        self._last_opportunities: list[dict] = []

    def run(self, task=None, **kwargs) -> dict:
        self._last_opportunities = [self._classify(signal) for signal in self._discover()]
        return {"status": "done", "opportunities": self._last_opportunities}

    def report(self) -> dict:
        return {"status": "done", "opportunities": self._last_opportunities}

    def _discover(self) -> list[str]:
        return self._signals

    @classmethod
    def _classify(cls, description: str) -> dict:
        lowered = description.lower()
        for keyword, category in cls._CHANNEL_KEYWORDS.items():
            if keyword in lowered:
                return {"description": description, "suggested_category": category}
        return {"description": description, "suggested_category": "create_asset"}
