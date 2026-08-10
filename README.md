# MAGCLIP

MAGCLIP is a Windows clipboard magazine for sequential data entry.

## v0.1 goal

- Capture tabular clipboard data copied from Google Sheets / Excel.
- Treat each copied row as a batch and each cell as a round.
- Show a compact always-on-top round monitor with current / next values.
- F1 fires the current batch automatically as Paste -> TAB -> Paste -> TAB.
- F3 aborts a running batch.
- F4 reloads the last fired batch so it can be repeated without resetting the whole magazine.
- Keep execution logic behind an engine/plugin interface so new workflows can be added later.

## Planned stack

- Python 3.11+
- PySide6
- keyboard
- pyperclip

## Architecture

```text
magclip/
  core/        magazine, parser, clipboard state
  engine/      executor and action abstractions
  plugins/     execution plugins
  ui/          main window and round monitor
```
