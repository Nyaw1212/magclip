from __future__ import annotations

import sys
import threading

import keyboard
import pyperclip
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from magclip.core.magazine import Magazine
from magclip.core.parser import parse_tabular_text
from magclip.plugins.leave_entry import LeaveEntryEngine


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

    def press_enter(self) -> None:
        keyboard.send("enter")

    def press_space(self) -> None:
        keyboard.send("space")

    def press_escape(self) -> None:
        keyboard.send("esc")

    def should_abort(self) -> bool:
        return self.abort_event.is_set()


class RoundMonitor(QWidget):
    SEQUENCE_SLOTS = 20
    SEQUENCE_COLUMNS = 4

    def __init__(self, controller: "MagclipApp") -> None:
        super().__init__()
        self.controller = controller
        self.magazine = controller.magazine
        self.bridge = controller.bridge
        self.setWindowTitle("MAGCLIP")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(560)

        self.status_label = QLabel("READY")
        self.progress_label = QLabel("No magazine loaded")
        self.current_label = QLabel("CURRENT\n—")
        self.current_label.setWordWrap(True)
        self.next_label = QLabel("NEXT\n—")
        self.next_label.setWordWrap(True)
        self.load_button = QPushButton("Load Clipboard")

        self.fire_mode_label = QLabel("Rounds per F1:")
        self.fire_mode = QComboBox()
        self.fire_mode.addItems(["1", "2", "3", "ALL"])
        self.fire_mode.setCurrentText("ALL")

        mode_layout = QHBoxLayout()
        mode_layout.addWidget(self.fire_mode_label)
        mode_layout.addWidget(self.fire_mode)

        self.delay_label = QLabel("Delay:")
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(25, 2000)
        self.delay_spin.setSingleStep(25)
        self.delay_spin.setSuffix(" ms")
        self.delay_spin.setValue(self.controller.engine.delay_ms)

        delay_layout = QHBoxLayout()
        delay_layout.addWidget(self.delay_label)
        delay_layout.addWidget(self.delay_spin)

        self.sequence_label = QLabel(
            "Custom sequence (optional) — up to 20 actions. Selected actions override Rounds per F1."
        )
        self.sequence_boxes: list[QComboBox] = []
        sequence_layout = QGridLayout()
        for index in range(self.SEQUENCE_SLOTS):
            label = QLabel(str(index + 1))
            box = QComboBox()
            box.addItems(["NONE", "PASTE", "TAB", "ENTER", "SPACE", "ESC"])
            box.currentTextChanged.connect(self._sequence_changed)
            self.sequence_boxes.append(box)
            row = index // self.SEQUENCE_COLUMNS
            col = (index % self.SEQUENCE_COLUMNS) * 2
            sequence_layout.addWidget(label, row, col)
            sequence_layout.addWidget(box, row, col + 1)

        self.clear_sequence_button = QPushButton("Clear Custom Sequence")
        self.clear_sequence_button.clicked.connect(self.clear_custom_sequence)

        self.hotkeys_label = QLabel(
            "F1 Fire  •  R Reload Last Round  •  F4 Reload Batch  •  F3 Abort"
        )
        self.hotkeys_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.current_label)
        layout.addWidget(self.next_label)
        layout.addLayout(mode_layout)
        layout.addLayout(delay_layout)
        layout.addWidget(self.sequence_label)
        layout.addLayout(sequence_layout)
        layout.addWidget(self.clear_sequence_button)
        layout.addWidget(self.hotkeys_label)
        layout.addWidget(self.load_button)

        self.load_button.clicked.connect(self.load_clipboard)
        self.fire_mode.currentTextChanged.connect(self.controller.set_rounds_per_fire)
        self.delay_spin.valueChanged.connect(self.controller.set_delay_ms)
        self.bridge.refresh.connect(self.refresh_view)
        self.bridge.status.connect(self.status_label.setText)
        self.refresh_view()

    def _sequence_changed(self) -> None:
        actions = [box.currentText() for box in self.sequence_boxes]
        self.controller.set_custom_sequence(actions)

    def clear_custom_sequence(self) -> None:
        for box in self.sequence_boxes:
            box.blockSignals(True)
            box.setCurrentText("NONE")
            box.blockSignals(False)
        self.controller.set_custom_sequence([])

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
        next_value = self.magazine.next_round_value()
        self.next_label.setText(f"NEXT\n{next_value if next_value is not None else '—'}")


class MagclipApp:
    def __init__(self) -> None:
        self.magazine = Magazine()
        self.abort_event = threading.Event()
        self.bridge = Bridge()
        self.engine = LeaveEntryEngine(delay_ms=120)
        self.context = AppContext(self.abort_event)
        self.running = False
        self.rounds_per_fire: int | None = None
        self.custom_sequence: list[str] = []

    def set_rounds_per_fire(self, value: str) -> None:
        self.rounds_per_fire = None if value == "ALL" else int(value)
        if not self.custom_sequence:
            self.bridge.status.emit(
                f"FIRE MODE: {value} ROUND{'S' if value != '1' else ''}"
            )

    def set_delay_ms(self, value: int) -> None:
        self.engine.delay_ms = value
        self.bridge.status.emit(f"DELAY: {value} ms")

    def set_custom_sequence(self, actions: list[str]) -> None:
        self.custom_sequence = [action for action in actions if action != "NONE"]
        if self.custom_sequence:
            preview = " → ".join(self.custom_sequence)
            self.bridge.status.emit(f"CUSTOM ({len(self.custom_sequence)}): {preview}")
        else:
            self.bridge.status.emit("CUSTOM SEQUENCE OFF")

    def fire_current_batch(self) -> None:
        if self.running:
            return

        batch = self.magazine.current_batch()
        if batch is None:
            self.bridge.status.emit("EMPTY")
            return

        start_round = self.magazine.round_index
        remaining = batch.rounds[start_round:]
        if not remaining:
            return

        self.running = True
        self.abort_event.clear()
        self.bridge.status.emit("RUNNING — F3 ABORT")

        def worker() -> None:
            if self.custom_sequence:
                paste_count = self.custom_sequence.count("PASTE")
                if paste_count == 0:
                    self.bridge.status.emit("CUSTOM ERROR — ADD AT LEAST ONE PASTE")
                    self.running = False
                    return
                if paste_count > len(remaining):
                    self.bridge.status.emit("CUSTOM ERROR — NOT ENOUGH ROUNDS")
                    self.running = False
                    return

                values = [round_.value for round_ in remaining[:paste_count]]
                result, consumed = self.engine.run_sequence(
                    self.context,
                    values,
                    start_round,
                    self.custom_sequence,
                )
                if result.completed:
                    for _ in range(consumed):
                        self.magazine.advance_round()
                    self.bridge.status.emit("READY")
                elif result.aborted:
                    self.bridge.status.emit("ABORTED")
                else:
                    self.bridge.status.emit("SEQUENCE ERROR")
            else:
                fire_count = len(remaining) if self.rounds_per_fire is None else min(
                    self.rounds_per_fire, len(remaining)
                )
                values = [round_.value for round_ in remaining[:fire_count]]
                result = self.engine.run_rounds(self.context, values, start_round)
                if result.completed:
                    for _ in values:
                        self.magazine.advance_round()
                    self.bridge.status.emit("READY")
                elif result.aborted:
                    self.bridge.status.emit("ABORTED")
                else:
                    self.bridge.status.emit("BATCH ERROR")

            self.running = False
            self.bridge.refresh.emit()

        threading.Thread(target=worker, daemon=True).start()

    def abort(self) -> None:
        self.abort_event.set()

    def reload_last_round(self) -> None:
        if self.running:
            return
        if self.magazine.reload_last_round():
            self.bridge.status.emit("LAST ROUND RELOADED")
            self.bridge.refresh.emit()
        else:
            self.bridge.status.emit("NO LAST ROUND")

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
    monitor = RoundMonitor(controller)
    monitor.show()

    keyboard.add_hotkey("f1", controller.fire_current_batch, suppress=True)
    keyboard.add_hotkey("r", controller.reload_last_round, suppress=True)
    keyboard.add_hotkey("f3", controller.abort, suppress=True)
    keyboard.add_hotkey("f4", controller.reload_last_batch, suppress=True)

    exit_code = qt_app.exec()
    keyboard.unhook_all_hotkeys()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
