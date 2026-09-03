from __future__ import annotations

import time

from magclip.engine.base import EngineContext, EngineResult, MagclipEngine


class MonthTyperEngine(MagclipEngine):
    """Type the first three letters of each loaded round instead of pasting it.

    Example: JANUARY -> J A N (typed as real keystrokes).
    Each fired value consumes one magazine round.
    """

    name = "month_typer"

    def __init__(self, delay_ms: int = 120) -> None:
        self.delay_ms = delay_ms

    def _wait(self) -> None:
        time.sleep(self.delay_ms / 1000)

    @staticmethod
    def _month_code(value: str) -> str:
        cleaned = "".join(ch for ch in value.strip() if ch.isalpha())
        return cleaned[:3].upper()

    def run_rounds(
        self,
        context: EngineContext,
        values: list[str],
    ) -> EngineResult:
        for value in values:
            if context.should_abort():
                return EngineResult(completed=False, aborted=True)

            code = self._month_code(value)
            if not code:
                return EngineResult(completed=False)

            context.type_text(code, interval_ms=self.delay_ms)
            self._wait()

        return EngineResult(completed=True)

    def run_batch(self, context: EngineContext, values: list[str]) -> EngineResult:
        return self.run_rounds(context, values)
