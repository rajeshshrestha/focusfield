import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from core import FocusEngine


class Clock:
    t = 0.0
    def __call__(self):
        return self.t


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "test.json"
        self.clock = Clock()
        self.e = FocusEngine(self.path, clock=self.clock)

    def tearDown(self):
        self.tmp.cleanup()

    def test_start_pause_resume_elapsed_clock(self):
        self.e.start()
        self.clock.t += 14
        self.assertAlmostEqual(self.e.seconds_remaining(), 1486)
        self.e.pause()
        self.clock.t += 90
        self.assertAlmostEqual(self.e.seconds_remaining(), 1486)
        self.e.start()
        self.clock.t += 1486
        self.assertEqual(self.e.check_finished(), "focus")
        self.assertEqual(self.e.mode, "short_break")
        self.assertEqual(len(self.e.sessions), 1)

    def test_fourth_focus_triggers_long_break(self):
        for _ in range(4):
            self.e.set_mode("focus")
            self.e.start()
            self.clock.t += 1501
            self.assertEqual(self.e.check_finished(), "focus")
        self.assertEqual(self.e.mode, "long_break")
        self.assertEqual(self.e.cycle_count, 4)

    def test_skip_does_not_count(self):
        self.e.start()
        self.e.skip()
        self.assertEqual(self.e.mode, "short_break")
        self.assertFalse(self.e.running)
        self.assertEqual(self.e.focus_stats()["sessions"], 0)
        self.e.skip()
        self.assertEqual(self.e.mode, "focus")

    def test_task_save_and_restore(self):
        tid = self.e.add_task("Write proof")
        self.assertEqual(self.e.active_task_title(), "Write proof")
        self.e.start()
        self.clock.t += 1500
        self.e.check_finished()
        self.e.save()
        other = FocusEngine(self.path)
        self.assertEqual(other.active_task_title(), "Write proof")
        self.assertEqual(other.focus_stats(date.today())["sessions"], 1)
        self.assertFalse(other.running)
        other.toggle_task(tid)
        self.assertIsNone(other.active_task_title())
        other.delete_task(tid)
        self.assertEqual(len(other.tasks), 0)

    def test_settings_bounds_and_persist(self):
        self.e.apply_settings({"focus_minutes": 45, "short_break_minutes": -7, "daily_goal": 200})
        self.assertEqual(self.e.settings["short_break_minutes"], 1)
        self.assertEqual(self.e.settings["daily_goal"], 20)
        self.assertEqual(self.e.seconds_remaining(), 2700)
        self.assertEqual(FocusEngine(self.path).settings["focus_minutes"], 45)

    def test_malformed_save_ignored(self):
        self.path.write_text('{broken')
        self.assertEqual(FocusEngine(self.path).mode, "focus")

    def test_auto_start_options(self):
        self.e.apply_settings({"auto_start_breaks": True, "auto_start_focus": True})
        self.e.start()
        self.clock.t += 1500
        self.assertEqual(self.e.check_finished(), "focus")
        self.assertTrue(self.e.running)
        self.clock.t += 300
        self.assertEqual(self.e.check_finished(), "short_break")
        self.assertTrue(self.e.running)


if __name__ == "__main__":
    unittest.main()
