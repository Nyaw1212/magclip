from __future__ import annotations

import time

from magclip.engine.base import EngineContext, EngineResult, MagclipEngine


class LeaveEntryEngine(MagclipEngine):
    """Engine for the Manage Leave form.

    Batch order:
    TYPE, START, END, STATUS, VL, SL, LWOP

    A fire may execute only part of a batch. Normal fields are pasted and TAB
    is sent only when another round remains in the same fire. LWOP is special:
    a truthy/non-zero value presses SPACE and LWOP never sends TAB.
    """

    name = "leave_entry"
    field_names = ("TYPE", "START", "END", "STATUS", "VL", "SL", "LWOP")

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
                # LWOP is always terminal and never sends TAB.
                continue

            context.paste_text(value)
            self._wait()

            # Stop on the last requested round without moving focus. This gives
            # e.g. 3 rounds: paste -> tab -> paste -> tab -> paste -> stop.
            if not is_last_in_fire:
                context.press_tab()
                self._wait()

        return EngineResult(completed=True)

    def run_batch(self, context: EngineContext, values: list[str]) -> EngineResult:
        if len(values) != len(self.field_names):
            return EngineResult(completed=False)
        return self.run_rounds(context, values, start_round=0)
