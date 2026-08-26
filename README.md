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
- Automatically receive newly saved leave magazines from the Python Leave Calendar.

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

## Leave Calendar integration

The Python Leave Calendar can send newly saved MAGCLIP rows directly to the
shared local inbox:

```text
%LOCALAPPDATA%\MAGCLIP\inbox
```

MAGCLIP checks this folder automatically. If a magazine is already active, the
new file remains queued and loads as soon as the current magazine is complete.
The clipboard-based **Load Clipboard** button remains available as a fallback.

## Build the Windows executable

From PowerShell in the repository folder:

```powershell
.\build_windows.ps1
```

The updated executable is created at `dist\MAGCLIP.exe`.
