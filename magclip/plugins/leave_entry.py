from __future__ import annotations

import time

from magclip.engine.base import EngineContext, EngineResult, MagclipEngine


class LeaveEntryEngine(MagclipEngine):
    """Engine for the Manage Leave form.

    Batch order:
    TYPE, START, END, STATUS, VL, SL, LWOP

    Normal firing can execute only part of a batch. Custom sequences can mix
    PASTE, TAB, ENTER, SPACE, and ESC actions. Each PASTE consumes one magazine
    round. LWOP keeps its special behavior: a truthy/non-zero value presses
    SPACE instead of pasting text.
    """

    name = "leave_entry"
    field_names = ("TYPE", "START", "END", "STATUS", "VL", "SL", "LWOP")
    valid_actions = {"PASTE", "TAB", "ENTER", "SPACE", "ESC"}

    def __init__(self, delay_ms: int = 120) -> None:
        self.delay_ms = delay_ms

    @staticmethod
    def _lwop_enabled(value: str) -> bool:
        normalized = value.strip().lower()
        return normalized not in {"", "0", "0.0", "false", "no", "n", "off"}

    def _wait(self) -> None:
        time.sleep(self.delay_ms / 1000)

    def run_rounds(
        self,
        context: EngineContext,
        values: list[str],
        start_round: int,
    ) -> EngineResult:
        for offset, value in enumerate(values):
            if context.should_abort():
                return EngineResult(completed=False, aborted=True)

            field_index = start_round + offset
            if field_index >= len(self.field_names):
                return EngineResult(completed=False)

            field_name = self.field_names[field_index]
            is_last_in_fire = offset == len(values) - 1

            if field_name == "LWOP":
                if self._lwop_enabled(value):
                    context.press_space()
                    self._wait()
                continue

            context.paste_text(value)
            self._wait()

            if not is_last_in_fire:
                context.press_tab()
                self._wait()

        return EngineResult(completed=True)

    def run_sequence(
        self,
        context: EngineContext,
        values: list[str],
        start_round: int,
        actions: list[str],
    ) -> tuple[EngineResult, int]:
        """Execute a custom action sequence.

        Returns (result, consumed_rounds). Only PASTE consumes a round.
        """
        consumed = 0

        for action in actions:
            if context.should_abort():
                return EngineResult(completed=False, aborted=True), consumed

            if action not in self.valid_actions:
                return EngineResult(completed=False), consumed

            if action == "PASTE":
                if consumed >= len(values):
                    return EngineResult(completed=False), consumed

                field_index = start_round + consumed
                if field_index >= len(self.field_names):
                    return EngineResult(completed=False), consumed

                value = values[consumed]
                field_name = self.field_names[field_index]

                if field_name == "LWOP":
                    if self._lwop_enabled(value):
                        context.press_space()
                else:
                    context.paste_text(value)

                consumed += 1
                self._wait()
                continue

            if action == "TAB":
                context.press_tab()
            elif action == "ENTER":
                context.press_enter()
            elif action == "SPACE":
                context.press_space()
            elif action == "ESC":
                context.press_escape()

            self._wait()

        return EngineResult(completed=True), consumed

    def run_batch(self, context: EngineContext, values: list[str]) -> EngineResult:
        if len(values) != len(self.field_names):
            return EngineResult(completed=False)
        return self.run_rounds(context, values, start_round=0)
