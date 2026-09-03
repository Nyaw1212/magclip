from __future__ import annotations

import time

from magclip.engine.base import EngineContext, EngineResult, MagclipEngine


class MonthTyperEngine(MagclipEngine):
    """Process a four-column month row in one fire.

    Expected row:
    MONTH | YEAR | VALUE 1 | VALUE 2

    Behavior:
    TYPE first 3 letters of MONTH -> TAB -> PASTE YEAR -> TAB ->
    PASTE VALUE 1 -> TAB -> PASTE VALUE 2 -> TAB
    """

    name = "month_typer"
    expected_columns = 4

    def __init__(self, delay_ms: int = 120) -> None:
        self.delay_ms = delay_ms

    def _wait(self) -> None:
        time.sleep(self.delay_ms / 1000)

    @staticmethod
    def _month_code(value: str) -> str:
        cleaned = "".join(ch for ch in value.strip() if ch.isalpha())
        return cleaned[:3].upper()

    def run_row(self, context: EngineContext, values: list[str]) -> EngineResult:
        if len(values) != self.expected_columns:
            return EngineResult(completed=False)

        if context.should_abort():
            return EngineResult(completed=False, aborted=True)

        code = self._month_code(values[0])
        if not code:
            return EngineResult(completed=False)

        # Month: real keystrokes, first 3 letters only.
        context.type_text(code, interval_ms=self.delay_ms)
        self._wait()
        context.press_tab()
        self._wait()

        # Year + two values: normal clipboard paste, TAB after each one,
        # including the last value as requested.
        for value in values[1:]:
            if context.should_abort():
                return EngineResult(completed=False, aborted=True)
            context.paste_text(value)
            self._wait()
            context.press_tab()
            self._wait()

        return EngineResult(completed=True)

    def run_rounds(self, context: EngineContext, values: list[str]) -> EngineResult:
        return self.run_row(context, values)

    def run_batch(self, context: EngineContext, values: list[str]) -> EngineResult:
        return self.run_row(context, values)
