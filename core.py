"""Timer and persistence engine for Focusfield. No third-party dependencies."""
from __future__ import annotations

import json
import os
import time
import uuid
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

APP_NAME = "Focusfield"
MODES = ("focus", "short_break", "long_break")
DEFAULT_SETTINGS = {
    "focus_minutes": 25,
    "short_break_minutes": 5,
    "long_break_minutes": 15,
    "long_break_every": 4,
    "daily_goal": 4,
    "auto_start_breaks": False,
    "auto_start_focus": False,
    "desktop_notifications": True,
    "sound": True,
    "always_on_top": False,
}
BOUNDS = {
    "focus_minutes": (1, 180),
    "short_break_minutes": (1, 60),
    "long_break_minutes": (1, 120),
    "long_break_every": (2, 12),
    "daily_goal": (1, 20),
}


def data_path() -> Path:
    home = Path.home()
    base = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    return base / "focusfield" / "state.json"


def safe_int(value: Any, default: int, lower: int, upper: int) -> int:
    try:
        val = int(value)
    except (TypeError, ValueError):
        val = default
    return max(lower, min(upper, val))


class FocusEngine:
    def __init__(self, path: Optional[Path] = None, clock=None):
        self.path = Path(path) if path is not None else data_path()
        self.clock = clock or time.monotonic
        self.settings = deepcopy(DEFAULT_SETTINGS)
        self.tasks: list[dict] = []
        self.sessions: list[dict] = []
        self.selected_task_id: Optional[str] = None
        self.mode = "focus"
        self.remaining = 25 * 60.0
        self.running = False
        self._end_time: Optional[float] = None
        self.cycle_count = 0
        self.load()

    def duration(self, mode: Optional[str] = None) -> int:
        mode = mode or self.mode
        key = {"focus": "focus_minutes", "short_break": "short_break_minutes", "long_break": "long_break_minutes"}[mode]
        return self.settings[key] * 60

    def seconds_remaining(self) -> float:
        if self.running and self._end_time is not None:
            return max(0.0, self._end_time - self.clock())
        return max(0.0, self.remaining)

    def snapshot(self) -> dict:
        return {
            "version": 1,
            "settings": deepcopy(self.settings),
            "tasks": deepcopy(self.tasks),
            "sessions": deepcopy(self.sessions[-15000:]),
            "selected_task_id": self.selected_task_id,
            "mode": self.mode,
            # On exit, the clock is frozen. The user resumes by pressing Play.
            "remaining": round(self.seconds_remaining(), 3),
            "cycle_count": self.cycle_count,
        }

    def load(self) -> None:
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return
            settings = data.get("settings", {})
            if isinstance(settings, dict):
                for name, original in DEFAULT_SETTINGS.items():
                    value = settings.get(name, original)
                    if name in BOUNDS:
                        self.settings[name] = safe_int(value, original, *BOUNDS[name])
                    else:
                        self.settings[name] = value if type(value) is bool else original
            tasks = data.get("tasks", [])
            if isinstance(tasks, list):
                for t in tasks[:1000]:
                    if isinstance(t, dict) and isinstance(t.get("title"), str) and t.get("id"):
                        self.tasks.append({
                            "id": str(t["id"]),
                            "title": t["title"][:180],
                            "done": bool(t.get("done", False)),
                            "created_at": str(t.get("created_at", "")),
                        })
            sessions = data.get("sessions", [])
            if isinstance(sessions, list):
                self.sessions = [s for s in sessions[-15000:] if isinstance(s, dict) and "date" in s]
            candidate = data.get("selected_task_id")
            if any(t["id"] == candidate and not t["done"] for t in self.tasks):
                self.selected_task_id = candidate
            self.cycle_count = safe_int(data.get("cycle_count", 0), 0, 0, 100000000)
            mode = data.get("mode", "focus")
            self.mode = mode if mode in MODES else "focus"
            self.remaining = max(0.0, min(float(data.get("remaining", self.duration())), self.duration()))
            # Old completed timer snapshots should never launch with 0 seconds.
            if self.remaining <= 0:
                self.remaining = float(self.duration())
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(self.snapshot(), f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError as exc:
            print(f"Focusfield: could not save state: {exc}")

    def start(self) -> None:
        if self.running:
            return
        if self.remaining <= 0:
            self.remaining = float(self.duration())
        self._end_time = self.clock() + self.remaining
        self.running = True

    def pause(self) -> None:
        if not self.running:
            return
        self.remaining = self.seconds_remaining()
        self.running = False
        self._end_time = None

    def toggle(self) -> None:
        if self.running:
            self.pause()
        else:
            self.start()

    def reset(self) -> None:
        self.running = False
        self._end_time = None
        self.remaining = float(self.duration())

    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError(f"Unknown mode: {mode}")
        self.mode = mode
        self.reset()

    def _move_to_next(self, completed: bool) -> str:
        prev_mode = self.mode
        if prev_mode == "focus":
            if completed:
                self.sessions.append({
                    "id": uuid.uuid4().hex,
                    "date": date.today().isoformat(),
                    "ended_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "minutes": self.settings["focus_minutes"],
                    "task_id": self.selected_task_id,
                    "task_title": self.active_task_title() or "Unassigned focus",
                })
                self.cycle_count += 1
            self.mode = "long_break" if self.cycle_count > 0 and self.cycle_count % self.settings["long_break_every"] == 0 else "short_break"
        else:
            self.mode = "focus"
        self.reset()
        autostart = self.settings["auto_start_focus"] if self.mode == "focus" else self.settings["auto_start_breaks"]
        if autostart:
            self.start()
        return prev_mode

    def check_finished(self) -> Optional[str]:
        """Return just-finished mode, or None. Only one transition per tick."""
        if not self.running or self.seconds_remaining() > 0:
            return None
        return self._move_to_next(completed=True)

    def skip(self) -> str:
        return self._move_to_next(completed=False)

    def apply_settings(self, changes: dict) -> None:
        old_duration = self.duration()
        old_remaining = self.seconds_remaining()
        was_running = self.running
        self.pause()
        for key, value in changes.items():
            if key not in DEFAULT_SETTINGS:
                continue
            if key in BOUNDS:
                self.settings[key] = safe_int(value, self.settings[key], *BOUNDS[key])
            elif type(value) is bool:
                self.settings[key] = value
        new_duration = self.duration()
        # Preserve elapsed time when durations are edited; never go negative.
        self.remaining = max(1.0, min(float(new_duration), float(new_duration) - (old_duration - old_remaining)))
        if was_running:
            self.start()
        self.save()

    def add_task(self, title: str) -> Optional[str]:
        title = title.strip()[:180]
        if not title:
            return None
        task_id = uuid.uuid4().hex
        self.tasks.insert(0, {"id": task_id, "title": title, "done": False, "created_at": datetime.now().isoformat()})
        self.selected_task_id = task_id
        self.save()
        return task_id

    def select_task(self, task_id: str) -> None:
        if any(t["id"] == task_id and not t["done"] for t in self.tasks):
            self.selected_task_id = task_id
            self.save()

    def toggle_task(self, task_id: str) -> None:
        for task in self.tasks:
            if task["id"] == task_id:
                task["done"] = not task["done"]
                if task["done"] and self.selected_task_id == task_id:
                    self.selected_task_id = next((t["id"] for t in self.tasks if not t["done"]), None)
                self.save()
                return

    def delete_task(self, task_id: str) -> None:
        self.tasks = [t for t in self.tasks if t["id"] != task_id]
        if self.selected_task_id == task_id:
            self.selected_task_id = next((t["id"] for t in self.tasks if not t["done"]), None)
        self.save()

    def active_task_title(self) -> Optional[str]:
        return next((t["title"] for t in self.tasks if t["id"] == self.selected_task_id and not t["done"]), None)

    def focus_stats(self, day: Optional[date] = None) -> dict:
        day = day or date.today()
        daily = [s for s in self.sessions if s.get("date") == day.isoformat()]
        return {"sessions": len(daily), "minutes": sum(safe_int(s.get("minutes"), 0, 0, 1000) for s in daily)}

    def week_stats(self, today: Optional[date] = None) -> list[dict]:
        today = today or date.today()
        # The most recent 7 days, including today.
        result = []
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            stats = self.focus_stats(day)
            result.append({"date": day.isoformat(), "label": day.strftime("%a")[0], **stats})
        return result
