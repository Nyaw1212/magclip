from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol


class EngineContext(Protocol):
    def paste_text(self, value: str) -> None: ...
    def press_tab(self) -> None: ...
    def press_enter(self) -> None: ...
    def press_space(self) -> None: ...
    def should_abort(self) -> bool: ...


@dataclass
class EngineResult:
    completed: bool
    aborted: bool = False


class MagclipEngine(ABC):
    name = "base"

    @abstractmethod
    def run_batch(self, context: EngineContext, values: list[str]) -> EngineResult:
        raise NotImplementedError
