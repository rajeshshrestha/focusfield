"""Exercise actual Tk widgets; run under xvfb-run on headless machines."""
import os
import tempfile
import unittest
from unittest.mock import patch

try:
    import tkinter as tk
    from app import FocusfieldApp
except ImportError:
    tk = None

from themes import COLOR_MODES, THEMES, get_palette


@unittest.skipUnless(tk and os.environ.get('DISPLAY'), 'Tkinter and a display are required')
class AppearanceGuiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {'XDG_DATA_HOME': self.directory.name})
        self.environment.start()
        self.root = tk.Tk()
        self.errors = []
        self.root.report_callback_exception = lambda *error: self.errors.append(error)
        self.app = FocusfieldApp(self.root)
        self.root.update()

    def tearDown(self):
        self.app.close()
        self.environment.stop()
        self.directory.cleanup()
        self.assertEqual(self.errors, [])

    def test_modes_themes_pages_and_running_timer(self):
        self.app.engine.add_task('Keep this task')
        self.app.engine.start()
        deadline = self.app.engine._end_time
        for mode in COLOR_MODES:
            for theme in THEMES:
                self.app.change_page('appearance')
                self.app.appearance_mode_buttons[mode]._click()
                self.app.theme_buttons[theme]._click()
                for page in ('today', 'insights', 'settings', 'appearance'):
                    self.app.change_page(page)
                    self.root.update()
                    self.assertEqual(self.root.cget('bg'), get_palette(mode, theme)['BG'])
                self.assertTrue(self.app.engine.running)
                self.assertEqual(self.app.engine._end_time, deadline)
                self.assertEqual(self.app.engine.active_task_title(), 'Keep this task')
                self.assertEqual(len(self.root.tk.call('after', 'info')), 1)

    def test_drafts_survive_switch_and_preferences_save(self):
        self.app._entry_focus_in(None)
        self.app.task_entry.insert(0, 'Unfinished draft')
        self.app.mode_toggle._click()
        self.assertEqual(self.app.task_entry.get(), 'Unfinished draft')
        self.app.change_page('settings')
        self.app.setting_vars['focus_minutes'].set('')
        self.app.setting_vars['sound'].set(False)
        self.app.mode_toggle._click()
        self.assertEqual(self.app.setting_vars['focus_minutes'].get(), '')
        self.assertFalse(self.app.setting_vars['sound'].get())
        self.app.setting_vars['focus_minutes'].set('45')
        self.app.save_settings()
        self.assertEqual(self.app.engine.settings['focus_minutes'], 45)
        self.app.change_page('today')
        self.assertEqual(self.app.task_entry.get(), 'Unfinished draft')

    def test_appearance_buttons_fit_minimum_window(self):
        self.root.geometry('980x700')
        self.app.change_page('appearance')
        self.root.update()
        for button in self.app.theme_buttons.values():
            self.assertTrue(button.winfo_viewable())
            self.assertEqual(button.winfo_height(), 36)
            self.assertLessEqual(button.winfo_y()+button.winfo_height(), button.master.winfo_height())
            self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),
                                 self.root.winfo_rooty()+self.root.winfo_height())

    def test_keyboard_mode_switch_does_not_start_timer(self):
        self.app.mode_toggle.focus_force()
        self.root.update()
        self.app.mode_toggle.event_generate('<space>')
        self.root.update()
        self.assertEqual(self.app.engine.settings['color_mode'], 'light')
        self.assertFalse(self.app.engine.running)

