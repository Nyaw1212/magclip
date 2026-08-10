from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Round:
    value: str


@dataclass
class Batch:
    rounds: List[Round] = field(default_factory=list)


class Magazine:
    def __init__(self) -> None:
        self.batches: List[Batch] = []
        self.batch_index = 0
        self.round_index = 0
        self.last_fired_batch_index: Optional[int] = None

    @property
    def empty(self) -> bool:
        return not self.batches

    def load(self, rows: List[List[str]]) -> None:
        self.batches = [
            Batch([Round(value) for value in row if value != ""])
            for row in rows
            if any(value != "" for value in row)
        ]
        self.batch_index = 0
        self.round_index = 0
        self.last_fired_batch_index = None

    def current_batch(self) -> Optional[Batch]:
        if self.empty or self.batch_index >= len(self.batches):
            return None
        return self.batches[self.batch_index]

    def current_round(self) -> Optional[Round]:
        batch = self.current_batch()
        if batch is None or self.round_index >= len(batch.rounds):
            return None
        return batch.rounds[self.round_index]

    def next_round_value(self) -> Optional[str]:
        batch = self.current_batch()
        if batch is None:
            return None
        next_index = self.round_index + 1
        if next_index < len(batch.rounds):
            return batch.rounds[next_index].value
        next_batch_index = self.batch_index + 1
        if next_batch_index < len(self.batches) and self.batches[next_batch_index].rounds:
            return self.batches[next_batch_index].rounds[0].value
        return None

    def advance_round(self) -> None:
        batch = self.current_batch()
        if batch is None:
            return
        self.round_index += 1
        if self.round_index >= len(batch.rounds):
            self.last_fired_batch_index = self.batch_index
            self.batch_index += 1
            self.round_index = 0

    def reload_last_batch(self) -> bool:
        if self.last_fired_batch_index is None:
            return False
        self.batch_index = self.last_fired_batch_index
        self.round_index = 0
        return True

    def reset(self) -> None:
        self.batch_index = 0
        self.round_index = 0

    def progress(self) -> tuple[int, int, int, int]:
        total_batches = len(self.batches)
        batch_no = min(self.batch_index + 1, total_batches) if total_batches else 0
        batch = self.current_batch()
        total_rounds = len(batch.rounds) if batch else 0
        round_no = min(self.round_index + 1, total_rounds) if total_rounds else 0
        return batch_no, total_batches, round_no, total_rounds
