from __future__ import annotations

import time

from magclip.engine.base import EngineContext, EngineResult, MagclipEngine


class SequentialTabEngine(MagclipEngine):
    name = "sequential_tab"

    def __init__(self, delay_ms: int = 120, tab_after_last: bool = False) -> None:
        self.delay_ms = delay_ms
        self.tab_after_last = tab_after_last

    def run_batch(self, context: EngineContext, values: list[str]) -> EngineResult:
        for index, value in enumerate(values):
            if context.should_abort():
                return EngineResult(completed=False, aborted=True)

            context.paste_text(value)
            time.sleep(self.delay_ms / 1000)

            is_last = index == len(values) - 1
            if not is_last or self.tab_after_last:
                context.press_tab()
                time.sleep(self.delay_ms / 1000)

        return EngineResult(completed=True)
