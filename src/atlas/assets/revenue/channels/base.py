from typing import Protocol, runtime_checkable


@runtime_checkable
class RevenueChannel(Protocol):
    """One revenue stream the Revenue Agent can execute. Adding a new
    channel means adding one class implementing this shape and one entry
    in RevenueAgent's registry — never touching atlas.core/atlas.brain."""

    name: str

    def execute(self, task) -> dict: ...
    def status(self) -> dict: ...
