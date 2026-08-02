from atlas.integrations.base import CommerceProvider
from atlas.integrations.digistore24 import Digistore24Provider

# Adding a future platform (Amazon, AliExpress, Etsy, Shopify, Gumroad, ...)
# means adding one class satisfying CommerceProvider in its own module plus
# one entry here — never touching any existing provider, the Protocol
# definitions, or any code that calls get_provider().
PROVIDERS: dict[str, CommerceProvider] = {
    "digistore24": Digistore24Provider(),
}


def get_provider(name: str) -> CommerceProvider:
    if name not in PROVIDERS:
        raise ValueError(f"unsupported provider: {name!r} (supported: {sorted(PROVIDERS)})")
    return PROVIDERS[name]
