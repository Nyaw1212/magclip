from __future__ import annotations

import time

from magclip.engine.base import EngineContext, EngineResult, MagclipEngine


class LeaveEntryEngine(MagclipEngine):
    """Engine for the Manage Leave form.

    Expected batch order:
    TYPE, START, END, STATUS, VL, SL, LWOP

    TYPE through SL are pasted and followed by TAB.
    LWOP is the final command: if it contains a truthy/non-zero value,
    SPACE is pressed to toggle the checkbox. No TAB is sent after LWOP.
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

    def run_batch(self, context: EngineContext, values: list[str]) -> EngineResult:
        if len(values) != len(self.field_names):
            return EngineResult(completed=False)

        # TYPE, START, END, STATUS, VL, SL
        for value in values[:-1]:
            if context.should_abort():
                return EngineResult(completed=False, aborted=True)

            context.paste_text(value)
            self._wait()
            context.press_tab()
            self._wait()

        # LWOP is the final field. Toggle only when the sheet value is non-zero.
        if context.should_abort():
            return EngineResult(completed=False, aborted=True)

        lwop_value = values[-1]
        if self._lwop_enabled(lwop_value):
            context.press_space()
            self._wait()

        return EngineResult(completed=True)
