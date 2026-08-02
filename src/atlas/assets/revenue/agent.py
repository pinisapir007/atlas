from atlas.assets.revenue.channels.affiliate import AffiliateChannel
from atlas.assets.revenue.channels.content_assets import ContentAssetChannel
from atlas.assets.revenue.channels.digital_products import DigitalProductChannel


class RevenueAgent:
    """Evaluates, selects, launches, and tracks revenue channels.

    Channels are registered by task category, using the same category
    names Research's classifier assigns. Adding a new channel means
    adding one class and one registry entry here — never touching
    atlas.core or atlas.brain.

    Recruitment/workforce leads are not a channel here: that grew into
    its own standalone operational agent (atlas.assets.recruitment_workforce)
    once its mission expanded beyond a single execute() call — see its
    manifest, which now owns the "revenue_recruitment_leads" category.
    """

    def __init__(self) -> None:
        self._channels = {
            "revenue_affiliate": AffiliateChannel(),
            "revenue_digital_product": DigitalProductChannel(),
            "revenue_content_assets": ContentAssetChannel(),
        }
        self._last_result: dict | None = None

    def run(self, task=None, **kwargs) -> dict:
        category = getattr(task, "category", None)
        channel = self._channels.get(category)
        if channel is None:
            self._last_result = {
                "status": "failed",
                "reason": f"no revenue channel registered for category '{category}'",
            }
        else:
            self._last_result = channel.execute(task)
        return self._last_result

    def report(self) -> dict:
        return {
            "status": (self._last_result or {}).get("status", "idle"),
            "last_result": self._last_result,
            "channels": {name: channel.status() for name, channel in self._channels.items()},
        }
