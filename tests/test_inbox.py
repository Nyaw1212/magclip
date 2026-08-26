import json
import tempfile
import unittest
from pathlib import Path

from magclip.core.inbox import InboxError, MagazineInbox


class MagazineInboxTests(unittest.TestCase):
    def test_receives_leave_calendar_magazine(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            payload = {
                "schema": "magclip.magazine/v1",
                "workflow": "leave_entry",
                "source": "Leave Calendar",
                "employee": {"id": "EMP-1", "name": "Juan Dela Cruz"},
                "rows": [["Vacation Leave", "08/10/2026", "08/11/2026", "A", "2.000", "0.000", "0.000"]],
            }
            (path / "001.json").write_text(json.dumps(payload), encoding="utf-8")

            item = MagazineInbox(path).receive_next()

            self.assertIsNotNone(item)
            self.assertEqual(item.employee_name, "Juan Dela Cruz")
            self.assertEqual(item.rows[0][0], "Vacation Leave")
            self.assertFalse((path / "001.json").exists())

    def test_rejects_invalid_magazine(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "001.json").write_text('{"schema":"wrong"}', encoding="utf-8")

            with self.assertRaises(InboxError):
                MagazineInbox(path).receive_next()

            self.assertTrue((path / "001.rejected").exists())


if __name__ == "__main__":
    unittest.main()
