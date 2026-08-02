from typing import Protocol, runtime_checkable


@runtime_checkable
class Runnable(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def status(self) -> str: ...


@runtime_checkable
class Triggerable(Protocol):
    def run(self, **kwargs) -> None: ...


@runtime_checkable
class Reportable(Protocol):
    def report(self) -> dict: ...
