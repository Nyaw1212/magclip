from __future__ import annotations

import time

from magclip.engine.base import EngineContext, EngineResult, MagclipEngine


class MonthTyperEngine(MagclipEngine):
    """Month-entry engine with a default four-column pattern and custom actions.

    Default row:
    MONTH | YEAR | VALUE 1 | VALUE 2

    Default behavior:
    TYPE first 3 letters of MONTH -> TAB -> PASTE YEAR -> TAB ->
    PASTE VALUE 1 -> TAB -> PASTE VALUE 2 -> TAB

    Custom actions:
    TYPE, PASTE, TAB, ENTER, ESC

    TYPE and PASTE each consume the next magazine cell. TYPE converts that cell
    to the first three alphabetic characters in uppercase before sending real
    keystrokes. Keyboard-only actions do not consume a cell.
    """

    name = "month_typer"
    expected_columns = 4
    valid_actions = {"TYPE", "PASTE", "TAB", "ENTER", "ESC"}

    def __init__(self, delay_ms: int = 120) -> None:
        self.delay_ms = delay_ms

    def _wait(self) -> None:
        time.sleep(self.delay_ms / 1000)

    @staticmethod
    def _month_code(value: str) -> str:
        cleaned = "".join(ch for ch in value.strip() if ch.isalpha())
        return cleaned[:3].upper()

    def run_sequence(
        self,
        context: EngineContext,
        values: list[str],
        actions: list[str],
    ) -> tuple[EngineResult, int]:
        consumed = 0

        for action in actions:
            if context.should_abort():
                return EngineResult(completed=False, aborted=True), consumed
            if action not in self.valid_actions:
                return EngineResult(completed=False), consumed

            if action in {"TYPE", "PASTE"}:
                if consumed >= len(values):
                    return EngineResult(completed=False), consumed

                value = values[consumed]
                if action == "TYPE":
                    code = self._month_code(value)
                    if not code:
                        return EngineResult(completed=False), consumed
                    context.type_text(code, interval_ms=self.delay_ms)
                else:
                    context.paste_text(value)

                consumed += 1
                self._wait()
                continue

            if action == "TAB":
                context.press_tab()
            elif action == "ENTER":
                context.press_enter()
            elif action == "ESC":
                context.press_escape()

            self._wait()

        return EngineResult(completed=True), consumed

    def run_row(self, context: EngineContext, values: list[str]) -> EngineResult:
        if len(values) != self.expected_columns:
            return EngineResult(completed=False)

        actions = [
            "TYPE", "TAB",
            "PASTE", "TAB",
            "PASTE", "TAB",
            "PASTE", "TAB",
        ]
        result, consumed = self.run_sequence(context, values, actions)
        if result.completed and consumed != len(values):
            return EngineResult(completed=False)
        return result

    def run_rounds(self, context: EngineContext, values: list[str]) -> EngineResult:
        return self.run_row(context, values)

    def run_batch(self, context: EngineContext, values: list[str]) -> EngineResult:
        return self.run_row(context, values)
