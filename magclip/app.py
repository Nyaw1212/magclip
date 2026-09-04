from __future__ import annotations

import sys
import threading
import time

import keyboard
import pyperclip
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QGridLayout,
    QHBoxLayout, QInputDialog, QLabel, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
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
        pyperclip.copy(value); keyboard.send("ctrl+v")
    def type_text(self, value: str, interval_ms: int = 0) -> None:
        keyboard.write(value, delay=max(interval_ms, 0) / 1000)
    def press_tab(self) -> None: keyboard.send("tab")
    def press_enter(self) -> None: keyboard.send("enter")
    def press_space(self) -> None: keyboard.send("space")
    def press_escape(self) -> None: keyboard.send("esc")
    def should_abort(self) -> bool: return self.abort_event.is_set()


class RoundMonitor(QWidget):
    SEQUENCE_SLOTS = 20

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
        self.current_label = QLabel("CURRENT\n—"); self.current_label.setWordWrap(True)
        self.next_label = QLabel("NEXT\n—"); self.next_label.setWordWrap(True)
        self.load_button = QPushButton("Load Clipboard")
        self.data_table = QTableWidget()
        self.data_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.data_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.data_table.setAlternatingRowColors(True)
        self.data_table.verticalHeader().setVisible(True)
        self.data_table.setMinimumHeight(260)

        self.mode_label = QLabel("Mode:")
        self.mode_box = QComboBox(); self.mode_box.addItems(["LEAVE ENTRY", "MONTH TYPER"])
        mode_row = QHBoxLayout(); mode_row.addWidget(self.mode_label); mode_row.addWidget(self.mode_box)

        self.fire_mode_label = QLabel("Rounds per F1:")
        self.fire_mode = QComboBox(); self.fire_mode.addItems(["1", "2", "3", "ALL"]); self.fire_mode.setCurrentText("ALL")
        fire_row = QHBoxLayout(); fire_row.addWidget(self.fire_mode_label); fire_row.addWidget(self.fire_mode)

        self.delay_label = QLabel("Action delay:")
        self.delay_spin = QSpinBox(); self.delay_spin.setRange(25, 2000); self.delay_spin.setSingleStep(25); self.delay_spin.setSuffix(" ms"); self.delay_spin.setValue(self.controller.leave_engine.delay_ms)
        delay_row = QHBoxLayout(); delay_row.addWidget(self.delay_label); delay_row.addWidget(self.delay_spin)

        self.repeat_check = QCheckBox("Repeat sequence")
        self.repeat_delay_label = QLabel("Repeat delay:")
        self.repeat_delay_spin = QSpinBox(); self.repeat_delay_spin.setRange(100, 10000); self.repeat_delay_spin.setSingleStep(100); self.repeat_delay_spin.setSuffix(" ms"); self.repeat_delay_spin.setValue(700)
        repeat_row = QHBoxLayout(); repeat_row.addWidget(self.repeat_check); repeat_row.addStretch(1); repeat_row.addWidget(self.repeat_delay_label); repeat_row.addWidget(self.repeat_delay_spin)

        self.sequence_label = QLabel("Custom sequence (optional) — up to 20 actions.")
        self.sequence_boxes = []; self.sequence_labels = []; self.sequence_grid = QGridLayout()
        for index in range(self.SEQUENCE_SLOTS):
            label = QLabel(str(index + 1)); box = QComboBox(); box.addItems(self._sequence_actions_for_mode()); box.currentTextChanged.connect(self._sequence_changed)
            self.sequence_labels.append(label); self.sequence_boxes.append(box)
        self._reflow_sequence_grid(4)

        self.saved_label = QLabel("Saved sequence:")
        self.saved_box = QComboBox(); self.saved_box.addItem("— Select saved sequence —")
        self.save_sequence_button = QPushButton("Save Current"); self.delete_sequence_button = QPushButton("Delete Saved")
        saved_row = QHBoxLayout(); saved_row.addWidget(self.saved_label); saved_row.addWidget(self.saved_box, 1); saved_row.addWidget(self.save_sequence_button); saved_row.addWidget(self.delete_sequence_button)
        self.clear_sequence_button = QPushButton("Clear Custom Sequence")
        self.hotkeys_label = QLabel("F1 Fire / Start Repeat  •  F2 Stop Repeat  •  R Reload Last Round  •  F4 Reload Batch  •  F3 Abort")
        self.hotkeys_label.setWordWrap(True)

        layout = QVBoxLayout(self); layout.setContentsMargins(8,8,8,8); layout.setSpacing(5)
        for w in (self.status_label,self.progress_label,self.current_label,self.next_label,self.data_table): layout.addWidget(w)
        layout.addLayout(mode_row); layout.addLayout(fire_row); layout.addLayout(delay_row); layout.addLayout(repeat_row)
        layout.addWidget(self.sequence_label); layout.addLayout(self.sequence_grid); layout.addLayout(saved_row); layout.addWidget(self.clear_sequence_button); layout.addWidget(self.hotkeys_label); layout.addWidget(self.load_button)

        self.load_button.clicked.connect(self.load_clipboard)
        self.mode_box.currentTextChanged.connect(self._mode_changed)
        self.fire_mode.currentTextChanged.connect(self.controller.set_rounds_per_fire)
        self.delay_spin.valueChanged.connect(self.controller.set_delay_ms)
        self.repeat_check.toggled.connect(self.controller.set_repeat_enabled)
        self.repeat_delay_spin.valueChanged.connect(self.controller.set_repeat_delay_ms)
        self.clear_sequence_button.clicked.connect(self.clear_custom_sequence)
        self.save_sequence_button.clicked.connect(self.save_current_sequence)
        self.delete_sequence_button.clicked.connect(self.delete_saved_sequence)
        self.saved_box.currentTextChanged.connect(self.load_saved_sequence)
        self.bridge.refresh.connect(self.refresh_view); self.bridge.status.connect(self.status_label.setText)
        self.refresh_saved_sequences(); self.resize(700,760); self.refresh_view(); self.apply_mode_layout()

    def _sequence_actions_for_mode(self):
        return ["NONE","TYPE","TAB","PASTE","ENTER","ESC"] if self.controller.mode == "MONTH TYPER" else ["NONE","PASTE","TAB","ENTER","SPACE","ESC"]
    def _refresh_sequence_action_options(self):
        allowed=self._sequence_actions_for_mode()
        for box in self.sequence_boxes:
            cur=box.currentText(); box.blockSignals(True); box.clear(); box.addItems(allowed); box.setCurrentText(cur if cur in allowed else "NONE"); box.blockSignals(False)
        self._sequence_changed()
    def _reflow_sequence_grid(self, n):
        for l,b in zip(self.sequence_labels,self.sequence_boxes): self.sequence_grid.removeWidget(l); self.sequence_grid.removeWidget(b)
        for i,(l,b) in enumerate(zip(self.sequence_labels,self.sequence_boxes)):
            r=i//n; c=(i%n)*2; self.sequence_grid.addWidget(l,r,c); self.sequence_grid.addWidget(b,r,c+1)
    def _mode_changed(self,value):
        self.controller.set_mode(value); self._refresh_sequence_action_options(); self.populate_table(); self.refresh_view(); self.apply_mode_layout()
    def apply_mode_layout(self):
        month=self.controller.mode=="MONTH TYPER"; self.fire_mode_label.setVisible(not month); self.fire_mode.setVisible(not month)
        if month:
            self.sequence_label.setText("Month sequence — TYPE / TAB / PASTE / ENTER / ESC. TYPE and PASTE consume cells."); self._reflow_sequence_grid(2); self.data_table.setMinimumHeight(300); self.data_table.setMaximumHeight(430); self.setMinimumWidth(420); self.setMaximumWidth(580); self.resize(520,920)
        else:
            self.sequence_label.setText("Custom sequence (optional) — up to 20 actions."); self._reflow_sequence_grid(4); self.data_table.setMaximumHeight(16777215); self.setMaximumWidth(16777215); self.setMinimumWidth(700); self.resize(max(self.width(),700),800)
    def _sequence_changed(self): self.controller.set_custom_sequence([b.currentText() for b in self.sequence_boxes])
    def _set_sequence_boxes(self,actions):
        allowed=set(self._sequence_actions_for_mode()); padded=actions[:self.SEQUENCE_SLOTS]+["NONE"]*self.SEQUENCE_SLOTS
        for i,b in enumerate(self.sequence_boxes): b.blockSignals(True); b.setCurrentText(padded[i] if padded[i] in allowed else "NONE"); b.blockSignals(False)
    def clear_custom_sequence(self): self._set_sequence_boxes([]); self.controller.set_custom_sequence([])
    def refresh_saved_sequences(self,select_name=None):
        seq=self.sequence_store.load_all(); self.saved_box.blockSignals(True); self.saved_box.clear(); self.saved_box.addItem("— Select saved sequence —")
        for name in sorted(seq,key=str.lower): self.saved_box.addItem(name)
        if select_name:
            i=self.saved_box.findText(select_name)
            if i>=0:self.saved_box.setCurrentIndex(i)
        self.saved_box.blockSignals(False)
    def save_current_sequence(self):
        actions=[b.currentText() for b in self.sequence_boxes]; actions=[a for a in actions if a!="NONE"]
        if not actions: self.bridge.status.emit("SAVE ERROR — CUSTOM SEQUENCE IS EMPTY"); return
        name,ok=QInputDialog.getText(self,"Save Sequence","Sequence name:"); name=name.strip()
        if ok and name: self.sequence_store.save(name,actions); self.refresh_saved_sequences(name); self.bridge.status.emit(f"SAVED SEQUENCE: {name}")
    def load_saved_sequence(self,name):
        if not name or name.startswith("—"): return
        actions=self.sequence_store.load_all().get(name)
        if actions: self._set_sequence_boxes(actions); self.controller.set_custom_sequence([b.currentText() for b in self.sequence_boxes]); self.bridge.status.emit(f"LOADED SEQUENCE: {name}")
    def delete_saved_sequence(self):
        name=self.saved_box.currentText()
        if name and not name.startswith("—") and self.sequence_store.delete(name): self.refresh_saved_sequences(); self.bridge.status.emit(f"DELETED SEQUENCE: {name}")
    def load_clipboard(self):
        rows=parse_tabular_text(pyperclip.paste()); self.magazine.load(rows); self.populate_table(); self.bridge.status.emit("READY" if rows else "EMPTY"); self.refresh_view(); self.apply_mode_layout()
    def _headers_for_columns(self,count):
        if self.controller.mode=="MONTH TYPER" and count==4:return ["MONTH","YEAR","EARNED","CREDIT"]
        if self.controller.mode=="LEAVE ENTRY" and count==7:return ["TYPE","START","END","STATUS","VL","SL","LWOP"]
        return [f"COL {i+1}" for i in range(count)]
    def populate_table(self):
        batches=self.magazine.batches
        if not batches: self.data_table.clear(); self.data_table.setRowCount(0); self.data_table.setColumnCount(0); return
        cc=max(len(b.rounds) for b in batches); self.data_table.clear(); self.data_table.setRowCount(len(batches)); self.data_table.setColumnCount(cc); self.data_table.setHorizontalHeaderLabels(self._headers_for_columns(cc))
        for r,batch in enumerate(batches):
            for c in range(cc):
                item=QTableWidgetItem(batch.rounds[c].value if c<len(batch.rounds) else ""); item.setTextAlignment(Qt.AlignCenter); self.data_table.setItem(r,c,item)
        self.data_table.resizeColumnsToContents(); self.highlight_current_row()
    def highlight_current_row(self):
        active=self.magazine.batch_index; hi=QColor(255,235,59,204); normal=QColor(0,0,0,0)
        for r in range(self.data_table.rowCount()):
            for c in range(self.data_table.columnCount()):
                item=self.data_table.item(r,c)
                if item:item.setBackground(hi if r==active else normal)
        if 0<=active<self.data_table.rowCount():
            item=self.data_table.item(active,0)
            if item:self.data_table.scrollToItem(item,QAbstractItemView.PositionAtCenter)
    @staticmethod
    def _month_preview(value): return "".join(ch for ch in value.strip() if ch.isalpha())[:3].upper()
    def refresh_view(self):
        bn,tb,rn,tr=self.magazine.progress(); self.highlight_current_row()
        if tb==0:self.progress_label.setText("No magazine loaded"); self.current_label.setText("CURRENT\n—"); self.next_label.setText("NEXT\n—"); return
        self.progress_label.setText(f"Batch {bn}/{tb}  •  Round {rn}/{tr}")
        if self.controller.mode=="MONTH TYPER":
            batch=self.magazine.current_batch()
            if batch and batch.rounds:
                vals=[x.value for x in batch.rounds]; self.current_label.setText(f"CURRENT ROW\n{vals[0]} → TYPE {self._month_preview(vals[0])} | {' | '.join(vals[1:])}")
            self.next_label.setText(("CUSTOM: "+" → ".join(self.controller.custom_sequence)) if self.controller.custom_sequence else "DEFAULT: TYPE → TAB → PASTE → TAB → PASTE → TAB → PASTE → TAB")
        else:
            cur=self.magazine.current_round(); nxt=self.magazine.next_round_value(); self.current_label.setText(f"CURRENT\n{cur.value if cur else 'DONE'}"); self.next_label.setText(f"NEXT\n{nxt if nxt is not None else '—'}")


class MagclipApp:
    def __init__(self):
        self.magazine=Magazine(); self.abort_event=threading.Event(); self.repeat_stop_event=threading.Event(); self.bridge=Bridge()
        self.leave_engine=LeaveEntryEngine(delay_ms=120); self.month_engine=MonthTyperEngine(delay_ms=120); self.context=AppContext(self.abort_event)
        self.running=False; self.rounds_per_fire=None; self.custom_sequence=[]; self.mode="LEAVE ENTRY"; self.repeat_enabled=False; self.repeat_delay_ms=700; self.repeat_running=False
    def set_mode(self,value): self.mode=value; self.custom_sequence=[]; self.bridge.status.emit("MONTH TYPER — CUSTOM SEQUENCE AVAILABLE" if value=="MONTH TYPER" else "LEAVE ENTRY MODE"); self.bridge.refresh.emit()
    def set_rounds_per_fire(self,value): self.rounds_per_fire=None if value=="ALL" else int(value)
    def set_delay_ms(self,value): self.leave_engine.delay_ms=value; self.month_engine.delay_ms=value; self.bridge.status.emit(f"ACTION DELAY: {value} ms")
    def set_repeat_enabled(self,value): self.repeat_enabled=value; self.bridge.status.emit("REPEAT SEQUENCE ON" if value else "REPEAT SEQUENCE OFF")
    def set_repeat_delay_ms(self,value): self.repeat_delay_ms=value; self.bridge.status.emit(f"REPEAT DELAY: {value} ms")
    def set_custom_sequence(self,actions): self.custom_sequence=[a for a in actions if a!="NONE"]; self.bridge.refresh.emit()

    def _fire_once(self):
        batch=self.magazine.current_batch()
        if batch is None:return False
        start=self.magazine.round_index; remaining=batch.rounds[start:]
        if not remaining:return False
        if self.mode=="MONTH TYPER":
            if self.custom_sequence:
                count=sum(1 for a in self.custom_sequence if a in {"TYPE","PASTE"})
                if count==0 or count>len(remaining):return False
                vals=[r.value for r in remaining[:count]]; result,consumed=self.month_engine.run_sequence(self.context,vals,self.custom_sequence)
            else:
                if self.magazine.round_index!=0:return False
                vals=[r.value for r in batch.rounds]; result=self.month_engine.run_row(self.context,vals); consumed=len(vals)
        elif self.custom_sequence:
            count=self.custom_sequence.count("PASTE")
            if count==0 or count>len(remaining):return False
            vals=[r.value for r in remaining[:count]]; result,consumed=self.leave_engine.run_sequence(self.context,vals,start,self.custom_sequence)
        else:
            count=len(remaining) if self.rounds_per_fire is None else min(self.rounds_per_fire,len(remaining)); vals=[r.value for r in remaining[:count]]; result=self.leave_engine.run_rounds(self.context,vals,start); consumed=len(vals)
        if result.completed:
            for _ in range(consumed):self.magazine.advance_round()
            self.bridge.refresh.emit(); return True
        return False

    def fire_current_batch(self):
        if self.running or self.repeat_running:return
        self.abort_event.clear()
        if self.repeat_enabled:
            self.repeat_running=True; self.repeat_stop_event.clear(); self.bridge.status.emit(f"REPEATING — {self.repeat_delay_ms} ms BETWEEN SEQUENCES — F2 STOP")
            def repeat_worker():
                while not self.repeat_stop_event.is_set() and not self.abort_event.is_set():
                    if not self._fire_once():break
                    if self.magazine.current_batch() is None:break
                    if self.repeat_stop_event.wait(self.repeat_delay_ms/1000):break
                self.repeat_running=False; self.bridge.status.emit("REPEAT STOPPED" if self.repeat_stop_event.is_set() else "READY — REPEAT COMPLETE"); self.bridge.refresh.emit()
            threading.Thread(target=repeat_worker,daemon=True).start()
        else:
            self.running=True; self.bridge.status.emit("RUNNING — F3 ABORT")
            def worker():
                ok=self._fire_once(); self.running=False; self.bridge.status.emit("READY" if ok else "SEQUENCE ERROR"); self.bridge.refresh.emit()
            threading.Thread(target=worker,daemon=True).start()
    def stop_repeat(self): self.repeat_stop_event.set(); self.bridge.status.emit("STOPPING REPEAT…")
    def abort(self): self.abort_event.set(); self.repeat_stop_event.set()
    def reload_last_round(self):
        if not self.running and not self.repeat_running and self.magazine.reload_last_round(): self.bridge.status.emit("LAST ROUND RELOADED"); self.bridge.refresh.emit()
    def reload_last_batch(self):
        if not self.running and not self.repeat_running and self.magazine.reload_last_batch(): self.bridge.status.emit("LAST BATCH RELOADED"); self.bridge.refresh.emit()


def main():
    qt_app=QApplication(sys.argv); controller=MagclipApp(); monitor=RoundMonitor(controller); monitor.show()
    keyboard.add_hotkey("f1",controller.fire_current_batch,suppress=True)
    keyboard.add_hotkey("f2",controller.stop_repeat,suppress=True)
    keyboard.add_hotkey("r",controller.reload_last_round,suppress=True)
    keyboard.add_hotkey("f3",controller.abort,suppress=True)
    keyboard.add_hotkey("f4",controller.reload_last_batch,suppress=True)
    code=qt_app.exec(); keyboard.unhook_all_hotkeys(); return code

if __name__=="__main__": raise SystemExit(main())
