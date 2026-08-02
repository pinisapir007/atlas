from dataclasses import dataclass, field


@dataclass(frozen=True)
class AssetRecord:
    """Metadata for one digital asset, parsed from its manifest.toml."""

    id: str
    name: str
    kind: str
    description: str = ""
    owner: str = ""
    tags: tuple[str, ...] = ()
    entrypoint: str | None = None
    config: dict = field(default_factory=dict)
