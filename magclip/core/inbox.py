from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA = "magclip.magazine/v1"


class InboxError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class InboxMagazine:
    rows: list[list[str]]
    workflow: str
    source: str
    employee_name: str

    @property
    def label(self) -> str:
        details = [self.source, self.employee_name]
        return " · ".join(value for value in details if value)


def default_inbox_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / ".magclip"
    path = root / "MAGCLIP" / "inbox" if base else root / "inbox"
    path.mkdir(parents=True, exist_ok=True)
    return path


class MagazineInbox:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_inbox_dir()
        self.path.mkdir(parents=True, exist_ok=True)

    def pending_count(self) -> int:
        return len(list(self.path.glob("*.json")))

    def receive_next(self) -> InboxMagazine | None:
        files = sorted(self.path.glob("*.json"), key=lambda item: item.name)
        if not files:
            return None

        selected = files[0]
        try:
            payload = json.loads(selected.read_text(encoding="utf-8"))
            magazine = _validate_payload(payload)
        except Exception as error:
            rejected = selected.with_suffix(".rejected")
            selected.replace(rejected)
            raise InboxError(f"Rejected invalid inbox file {selected.name}: {error}") from error

        selected.unlink()
        return magazine


def _validate_payload(payload: Any) -> InboxMagazine:
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    if payload.get("schema") != SCHEMA:
        raise ValueError(f"unsupported schema: {payload.get('schema')!r}")

    workflow = str(payload.get("workflow", "")).strip()
    if workflow != "leave_entry":
        raise ValueError(f"unsupported workflow: {workflow!r}")

    raw_rows = payload.get("rows")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise ValueError("rows must contain at least one batch")

    rows: list[list[str]] = []
    for row in raw_rows:
        if not isinstance(row, list) or len(row) != 7:
            raise ValueError("every leave_entry row must contain exactly 7 fields")
        rows.append([str(value) for value in row])

    employee = payload.get("employee") or {}
    return InboxMagazine(
        rows=rows,
        workflow=workflow,
        source=str(payload.get("source", "Leave Calendar")),
        employee_name=str(employee.get("name", "")) if isinstance(employee, dict) else "",
    )
