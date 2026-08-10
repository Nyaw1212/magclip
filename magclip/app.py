from __future__ import annotations

import sys
import threading

import keyboard
import pyperclip
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

from magclip.core.magazine import Magazine
from magclip.core.parser import parse_tabular_text
from magclip.plugins.sequential_tab import SequentialTabEngine


class Bridge(QObject):
    refresh = Signal()
    status = Signal(str)


class AppContext:
    def __init__(self, abort_event: threading.Event) -> None:
        self.abort_event = abort_event

    def paste_text(self, value: str) -> None:
        pyperclip.copy(value)
        keyboard.send("ctrl+v")

    def press_tab(self) -> None:
        keyboard.send("tab")

    def should_abort(self) -> bool:
        return self.abort_event.is_set()


class RoundMonitor(QWidget):
    def __init__(self, magazine: Magazine, bridge: Bridge) -> None:
        super().__init__()
        self.magazine = magazine
        self.bridge = bridge
        self.setWindowTitle("MAGCLIP")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(360)

        self.status_label = QLabel("READY")
        self.progress_label = QLabel("No magazine loaded")
        self.current_label = QLabel("CURRENT\n—")
        self.current_label.setWordWrap(True)
        self.next_label = QLabel("NEXT\n—")
        self.next_label.setWordWrap(True)
        self.load_button = QPushButton("Load Clipboard")

        layout = QVBoxLayout(self)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.current_label)
        layout.addWidget(self.next_label)
        layout.addWidget(self.load_button)

        self.load_button.clicked.connect(self.load_clipboard)
        bridge.refresh.connect(self.refresh_view)
        bridge.status.connect(self.status_label.setText)
        self.refresh_view()

    def load_clipboard(self) -> None:
        rows = parse_tabular_text(pyperclip.paste())
        self.magazine.load(rows)
        self.bridge.status.emit("READY" if rows else "EMPTY")
        self.refresh_view()

    def refresh_view(self) -> None:
        batch_no, total_batches, round_no, total_rounds = self.magazine.progress()
        if total_batches == 0:
            self.progress_label.setText("No magazine loaded")
            self.current_label.setText("CURRENT\n—")
            self.next_label.setText("NEXT\n—")
            return

        self.progress_label.setText(
            f"Batch {batch_no}/{total_batches}  •  Round {round_no}/{total_rounds}"
        )
        current = self.magazine.current_round()
        self.current_label.setText(f"CURRENT\n{current.value if current else 'DONE'}")
        self.next_label.setText(f"NEXT\n{self.magazine.next_round_value() or '—'}")


class MagclipApp:
    def __init__(self) -> None:
        self.magazine = Magazine()
        self.abort_event = threading.Event()
        self.bridge = Bridge()
        self.engine = SequentialTabEngine(delay_ms=120, tab_after_last=False)
        self.context = AppContext(self.abort_event)
        self.running = False

    def fire_current_batch(self) -> None:
        if self.running:
            return
        batch = self.magazine.current_batch()
        if batch is None:
            self.bridge.status.emit("EMPTY")
            return

        values = [round_.value for round_ in batch.rounds[self.magazine.round_index :]]
        if not values:
            return

        self.running = True
        self.abort_event.clear()
        self.bridge.status.emit("RUNNING — F3 ABORT")

        def worker() -> None:
            result = self.engine.run_batch(self.context, values)
            if result.completed:
                while self.magazine.current_batch() is batch:
                    self.magazine.advance_round()
                self.bridge.status.emit("READY")
            elif result.aborted:
                self.bridge.status.emit("ABORTED")
            self.running = False
            self.bridge.refresh.emit()

        threading.Thread(target=worker, daemon=True).start()

    def abort(self) -> None:
        self.abort_event.set()

    def reload_last_batch(self) -> None:
        if self.running:
            return
        if self.magazine.reload_last_batch():
            self.bridge.status.emit("LAST BATCH RELOADED")
            self.bridge.refresh.emit()
        else:
            self.bridge.status.emit("NO LAST BATCH")


def main() -> int:
    qt_app = QApplication(sys.argv)
    controller = MagclipApp()
    monitor = RoundMonitor(controller.magazine, controller.bridge)
    monitor.show()

    keyboard.add_hotkey("f1", controller.fire_current_batch, suppress=True)
    keyboard.add_hotkey("f3", controller.abort, suppress=True)
    keyboard.add_hotkey("f4", controller.reload_last_batch, suppress=True)

    exit_code = qt_app.exec()
    keyboard.unhook_all_hotkeys()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
