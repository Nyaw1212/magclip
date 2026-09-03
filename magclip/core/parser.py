from __future__ import annotations

import csv
import io
from typing import List


def parse_tabular_text(text: str) -> List[List[str]]:
    """Parse spreadsheet clipboard text into rows/batches and cells/rounds."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if not normalized:
        return []

    reader = csv.reader(io.StringIO(normalized), delimiter="\t")
    rows: List[List[str]] = []
    for row in reader:
        cleaned = [cell.strip() for cell in row]
        if any(cleaned):
            rows.append(cleaned)
    return rows
