from __future__ import annotations

import json
from pathlib import Path


class SequenceStore:
    """Persist named custom action sequences in the user's profile."""

    def __init__(self) -> None:
        self.path = Path.home() / ".magclip" / "sequences.json"

    def load_all(self) -> dict[str, list[str]]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

        if not isinstance(data, dict):
            return {}

        cleaned: dict[str, list[str]] = {}
        for name, actions in data.items():
            if isinstance(name, str) and isinstance(actions, list):
                cleaned[name] = [str(action) for action in actions]
        return cleaned

    def save(self, name: str, actions: list[str]) -> None:
        sequences = self.load_all()
        sequences[name] = actions
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(sequences, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def delete(self, name: str) -> bool:
        sequences = self.load_all()
        if name not in sequences:
            return False
        del sequences[name]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(sequences, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return True
