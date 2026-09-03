from __future__ import annotations

import sys
import threading

import keyboard
import pyperclip
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from magclip.core.magazine import Magazine
from magclip.core.parser import parse_tabular_text
from magclip.core.sequence_store import SequenceStore
from magclip.plugins.leave_entry import LeaveEntryEngine
from magclip.plugins.month_typer import MonthTyperEngine


class Bridge(QObject):
    refresh = Signal()
    status = Signal(str)


class AppContext:
    def __init__(self, abort_event: threading.Event) -> None:
        self.abort_event = abort_event

    def paste_text(self, value: str) -> None:
        pyperclip.copy(value)
        keyboard.send("ctrl+v")

    def type_text(self, value: str, interval_ms: int = 0) -> None:
        keyboard.write(value, delay=max(interval_ms, 0) / 1000)

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
        self.sequence_store = SequenceStore()

        self.setWindowTitle("MAGCLIP")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.status_label = QLabel("READY")
        self.progress_label = QLabel("No magazine loaded")
        self.current_label = QLabel("CURRENT\n—")
        self.current_label.setWordWrap(True)
        self.next_label = QLabel("NEXT\n—")
        self.next_label.setWordWrap(True)
        self.load_button = QPushButton("Load Clipboard")

        self.data_table = QTableWidget()
        self.data_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.data_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.data_table.setAlternatingRowColors(True)
        self.data_table.verticalHeader().setVisible(True)
        self.data_table.setMinimumHeight(260)

        self.mode_label = QLabel("Mode:")
        self.mode_box = QComboBox()
        self.mode_box.addItems(["LEAVE ENTRY", "MONTH TYPER"])
        self.mode_box.setCurrentText("LEAVE ENTRY")
        mode_row = QHBoxLayout()
        mode_row.addWidget(self.mode_label)
        mode_row.addWidget(self.mode_box)

        self.fire_mode_label = QLabel("Rounds per F1:")
        self.fire_mode = QComboBox()
        self.fire_mode.addItems(["1", "2", "3", "ALL"])
        self.fire_mode.setCurrentText("ALL")
        fire_row = QHBoxLayout()
        fire_row.addWidget(self.fire_mode_label)
        fire_row.addWidget(self.fire_mode)

        self.delay_label = QLabel("Delay:")
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(25, 2000)
        self.delay_spin.setSingleStep(25)
        self.delay_spin.setSuffix(" ms")
        self.delay_spin.setValue(self.controller.leave_engine.delay_ms)
        delay_row = QHBoxLayout()
        delay_row.addWidget(self.delay_label)
        delay_row.addWidget(self.delay_spin)

        self.sequence_label = QLabel(
            "Custom sequence (optional) — up to 20 actions."
        )
        self.sequence_boxes: list[QComboBox] = []
        self.sequence_labels: list[QLabel] = []
        sequence_grid = QGridLayout()
        for index in range(self.SEQUENCE_SLOTS):
            label = QLabel(str(index + 1))
            box = QComboBox()
            box.addItems(["NONE", "PASTE", "TAB", "ENTER", "SPACE", "ESC"])
            box.currentTextChanged.connect(self._sequence_changed)
            self.sequence_labels.append(label)
            self.sequence_boxes.append(box)
            row = index // self.SEQUENCE_COLUMNS
            col = (index % self.SEQUENCE_COLUMNS) * 2
            sequence_grid.addWidget(label, row, col)
            sequence_grid.addWidget(box, row, col + 1)

        self.saved_label = QLabel("Saved sequence:")
        self.saved_box = QComboBox()
        self.saved_box.addItem("— Select saved sequence —")
        self.save_sequence_button = QPushButton("Save Current")
        self.delete_sequence_button = QPushButton("Delete Saved")
        saved_row = QHBoxLayout()
        saved_row.addWidget(self.saved_label)
        saved_row.addWidget(self.saved_box, 1)
        saved_row.addWidget(self.save_sequence_button)
        saved_row.addWidget(self.delete_sequence_button)

        self.clear_sequence_button = QPushButton("Clear Custom Sequence")
        self.hotkeys_label = QLabel(
            "F1 Fire  •  R Reload Last Round  •  F4 Reload Batch  •  F3 Abort"
        )
        self.hotkeys_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.current_label)
        layout.addWidget(self.next_label)
        layout.addWidget(self.data_table)
        layout.addLayout(mode_row)
        layout.addLayout(fire_row)
        layout.addLayout(delay_row)
        layout.addWidget(self.sequence_label)
        layout.addLayout(sequence_grid)
        layout.addLayout(saved_row)
        layout.addWidget(self.clear_sequence_button)
        layout.addWidget(self.hotkeys_label)
        layout.addWidget(self.load_button)

        self.load_button.clicked.connect(self.load_clipboard)
        self.mode_box.currentTextChanged.connect(self._mode_changed)
        self.fire_mode.currentTextChanged.connect(self.controller.set_rounds_per_fire)
        self.delay_spin.valueChanged.connect(self.controller.set_delay_ms)
        self.clear_sequence_button.clicked.connect(self.clear_custom_sequence)
        self.save_sequence_button.clicked.connect(self.save_current_sequence)
        self.delete_sequence_button.clicked.connect(self.delete_saved_sequence)
        self.saved_box.currentTextChanged.connect(self.load_saved_sequence)
        self.bridge.refresh.connect(self.refresh_view)
        self.bridge.status.connect(self.status_label.setText)

        self.refresh_saved_sequences()
        self.resize(700, 760)
        self.refresh_view()
        self.apply_mode_layout()

    def _mode_changed(self, value: str) -> None:
        self.controller.set_mode(value)
        self.populate_table()
        self.refresh_view()
        self.apply_mode_layout()

    def apply_mode_layout(self) -> None:
        month_mode = self.controller.mode == "MONTH TYPER"
        leave_widgets = [
            self.fire_mode_label,
            self.fire_mode,
            self.sequence_label,
            self.saved_label,
            self.saved_box,
            self.save_sequence_button,
            self.delete_sequence_button,
            self.clear_sequence_button,
        ]
        for widget in leave_widgets:
            widget.setVisible(not month_mode)
        for label, box in zip(self.sequence_labels, self.sequence_boxes):
            label.setVisible(not month_mode)
            box.setVisible(not month_mode)

        if month_mode:
            self.data_table.setMinimumHeight(360)
            self.data_table.setMaximumHeight(520)
            self.data_table.resizeColumnsToContents()
            table_width = (
                self.data_table.verticalHeader().width()
                + sum(self.data_table.columnWidth(i) for i in range(self.data_table.columnCount()))
                + self.data_table.verticalScrollBar().sizeHint().width()
                + self.data_table.frameWidth() * 2
                + 28
            )
            compact_width = max(360, min(table_width, 500))
            self.setMinimumWidth(0)
            self.setMaximumWidth(520)
            self.resize(compact_width, 720)
        else:
            self.data_table.setMaximumHeight(16777215)
            self.setMaximumWidth(16777215)
            self.setMinimumWidth(700)
            self.resize(max(self.width(), 700), 760)

    def _sequence_changed(self) -> None:
        actions = [box.currentText() for box in self.sequence_boxes]
        self.controller.set_custom_sequence(actions)

    def clear_custom_sequence(self) -> None:
        self._set_sequence_boxes([])
        self.controller.set_custom_sequence([])
        self.saved_box.blockSignals(True)
        self.saved_box.setCurrentIndex(0)
        self.saved_box.blockSignals(False)

    def _set_sequence_boxes(self, actions: list[str]) -> None:
        padded = actions[: self.SEQUENCE_SLOTS] + ["NONE"] * self.SEQUENCE_SLOTS
        for index, box in enumerate(self.sequence_boxes):
            box.blockSignals(True)
            box.setCurrentText(padded[index])
            box.blockSignals(False)

    def refresh_saved_sequences(self, select_name: str | None = None) -> None:
        sequences = self.sequence_store.load_all()
        self.saved_box.blockSignals(True)
        self.saved_box.clear()
        self.saved_box.addItem("— Select saved sequence —")
        for name in sorted(sequences, key=str.lower):
            self.saved_box.addItem(name)
        if select_name:
            index = self.saved_box.findText(select_name)
            if index >= 0:
                self.saved_box.setCurrentIndex(index)
        self.saved_box.blockSignals(False)

    def save_current_sequence(self) -> None:
        actions = [box.currentText() for box in self.sequence_boxes]
        actions = [action for action in actions if action != "NONE"]
        if not actions:
            self.bridge.status.emit("SAVE ERROR — CUSTOM SEQUENCE IS EMPTY")
            return

        name, ok = QInputDialog.getText(self, "Save Sequence", "Sequence name:")
        name = name.strip()
        if not ok or not name:
            return

        self.sequence_store.save(name, actions)
        self.refresh_saved_sequences(select_name=name)
        self.bridge.status.emit(f"SAVED SEQUENCE: {name}")

    def load_saved_sequence(self, name: str) -> None:
        if not name or name.startswith("—"):
            return
        actions = self.sequence_store.load_all().get(name)
        if not actions:
            return
        self._set_sequence_boxes(actions)
        self.controller.set_custom_sequence(actions)
        self.bridge.status.emit(f"LOADED SEQUENCE: {name}")

    def delete_saved_sequence(self) -> None:
        name = self.saved_box.currentText()
        if not name or name.startswith("—"):
            self.bridge.status.emit("SELECT A SAVED SEQUENCE FIRST")
            return
        if self.sequence_store.delete(name):
            self.refresh_saved_sequences()
            self.bridge.status.emit(f"DELETED SEQUENCE: {name}")

    def load_clipboard(self) -> None:
        rows = parse_tabular_text(pyperclip.paste())
        self.magazine.load(rows)
        self.populate_table()
        self.bridge.status.emit("READY" if rows else "EMPTY")
        self.refresh_view()
        self.apply_mode_layout()

    def _headers_for_columns(self, count: int) -> list[str]:
        if self.controller.mode == "MONTH TYPER" and count == 4:
            return ["MONTH", "YEAR", "EARNED", "CREDIT"]
        if self.controller.mode == "LEAVE ENTRY" and count == 7:
            return ["TYPE", "START", "END", "STATUS", "VL", "SL", "LWOP"]
        return [f"COL {index + 1}" for index in range(count)]

    def populate_table(self) -> None:
        batches = self.magazine.batches
        if not batches:
            self.data_table.clear()
            self.data_table.setRowCount(0)
            self.data_table.setColumnCount(0)
            return

        column_count = max(len(batch.rounds) for batch in batches)
        self.data_table.clear()
        self.data_table.setRowCount(len(batches))
        self.data_table.setColumnCount(column_count)
        self.data_table.setHorizontalHeaderLabels(self._headers_for_columns(column_count))

        for row_index, batch in enumerate(batches):
            for column_index in range(column_count):
                value = batch.rounds[column_index].value if column_index < len(batch.rounds) else ""
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                self.data_table.setItem(row_index, column_index, item)

        self.data_table.resizeColumnsToContents()
        self.highlight_current_row()

    def highlight_current_row(self) -> None:
        active_row = self.magazine.batch_index
        active_brush = QColor(255, 235, 59, 204)
        normal_brush = QColor(0, 0, 0, 0)
        for row in range(self.data_table.rowCount()):
            for column in range(self.data_table.columnCount()):
                item = self.data_table.item(row, column)
                if item:
                    item.setBackground(active_brush if row == active_row else normal_brush)
        if 0 <= active_row < self.data_table.rowCount():
            item = self.data_table.item(active_row, 0)
            if item:
                self.data_table.scrollToItem(item, QAbstractItemView.PositionAtCenter)

    @staticmethod
    def _month_preview(value: str) -> str:
        cleaned = "".join(ch for ch in value.strip() if ch.isalpha())
        return cleaned[:3].upper()

    def refresh_view(self) -> None:
        batch_no, total_batches, round_no, total_rounds = self.magazine.progress()
        self.highlight_current_row()
        if total_batches == 0:
            self.progress_label.setText("No magazine loaded")
            self.current_label.setText("CURRENT\n—")
            self.next_label.setText("NEXT\n—")
            return

        self.progress_label.setText(
            f"Batch {batch_no}/{total_batches}  •  Round {round_no}/{total_rounds}"
        )
        current = self.magazine.current_round()
        next_value = self.magazine.next_round_value()

        if self.controller.mode == "MONTH TYPER":
            batch = self.magazine.current_batch()
            if batch and batch.rounds:
                values = [round_.value for round_ in batch.rounds]
                month = values[0]
                rest = " | ".join(values[1:])
                self.current_label.setText(
                    f"CURRENT ROW\n{month} → TYPE {self._month_preview(month)} | {rest}"
                )
            else:
                self.current_label.setText("CURRENT\nDONE")
            self.next_label.setText(
                "F1: TYPE MONTH → TAB → PASTE → TAB → PASTE → TAB → PASTE → TAB"
            )
        else:
            self.current_label.setText(f"CURRENT\n{current.value if current else 'DONE'}")
            self.next_label.setText(f"NEXT\n{next_value if next_value is not None else '—'}")


class MagclipApp:
    def __init__(self) -> None:
        self.magazine = Magazine()
        self.abort_event = threading.Event()
        self.bridge = Bridge()
        self.leave_engine = LeaveEntryEngine(delay_ms=120)
        self.month_engine = MonthTyperEngine(delay_ms=120)
        self.context = AppContext(self.abort_event)
        self.running = False
        self.rounds_per_fire: int | None = None
        self.custom_sequence: list[str] = []
        self.mode = "LEAVE ENTRY"

    def set_mode(self, value: str) -> None:
        self.mode = value
        self.bridge.status.emit(
            "MONTH TYPER — F1 PROCESSES ONE FULL ROW"
            if value == "MONTH TYPER"
            else "LEAVE ENTRY MODE"
        )
        self.bridge.refresh.emit()

    def set_rounds_per_fire(self, value: str) -> None:
        self.rounds_per_fire = None if value == "ALL" else int(value)
        if not self.custom_sequence and self.mode == "LEAVE ENTRY":
            self.bridge.status.emit(
                f"FIRE MODE: {value} ROUND{'S' if value != '1' else ''}"
            )

    def set_delay_ms(self, value: int) -> None:
        self.leave_engine.delay_ms = value
        self.month_engine.delay_ms = value
        self.bridge.status.emit(f"DELAY: {value} ms")

    def set_custom_sequence(self, actions: list[str]) -> None:
        self.custom_sequence = [action for action in actions if action != "NONE"]
        if self.custom_sequence and self.mode == "LEAVE ENTRY":
            self.bridge.status.emit(
                f"CUSTOM ({len(self.custom_sequence)}): {' → '.join(self.custom_sequence)}"
            )
        elif not self.custom_sequence:
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
            if self.mode == "MONTH TYPER":
                if self.magazine.round_index != 0:
                    self.bridge.status.emit("MONTH TYPER ERROR — RELOAD BATCH WITH F4")
                    self.running = False
                    return
                values = [round_.value for round_ in batch.rounds]
                result = self.month_engine.run_row(self.context, values)
                if result.completed:
                    for _ in values:
                        self.magazine.advance_round()
                    self.bridge.status.emit("READY — ROW COMPLETE")
                elif result.aborted:
                    self.bridge.status.emit("ABORTED")
                else:
                    self.bridge.status.emit("MONTH TYPER ERROR — EXPECTED 4 COLUMNS")
            elif self.custom_sequence:
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
                result, consumed = self.leave_engine.run_sequence(
                    self.context, values, start_round, self.custom_sequence
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
                result = self.leave_engine.run_rounds(self.context, values, start_round)
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
