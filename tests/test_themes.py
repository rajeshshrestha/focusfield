import json
import tempfile
import unittest
from pathlib import Path

from core import FocusEngine
from themes import COLOR_MODES, THEMES, get_palette


def contrast(first, second):
    def luminance(color):
        channels = [int(color[i:i+2], 16)/255 for i in (1, 3, 5)]
        channels = [c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4 for c in channels]
        return sum(c*w for c, w in zip(channels, (.2126, .7152, .0722)))
    values = sorted((luminance(first), luminance(second)))
    return (values[1]+.05)/(values[0]+.05)


class AppearanceTests(unittest.TestCase):
    def test_text_contrast_in_every_palette(self):
        for mode in COLOR_MODES:
            for theme in THEMES:
                palette = get_palette(mode, theme)
                pairs = [(fg, bg) for fg in ('TEXT', 'MUTED', 'DIM')
                         for bg in ('BG', 'PANEL', 'PANEL_INNER', 'SIDEBAR', 'QUOTE')]
                pairs += [('BUTTON_TEXT', bg) for bg in
                          ('ACCENT', 'ACCENT_HOVER', 'SECONDARY', 'SECONDARY_HOVER')]
                pairs += [(fg, 'PANEL_INNER') for fg in ('ACCENT', 'SECONDARY')]
                for fg, bg in pairs:
                    with self.subTest(mode=mode, theme=theme, fg=fg, bg=bg):
                        self.assertGreaterEqual(contrast(palette[fg], palette[bg]), 4.5)

    def test_old_saves_and_invalid_appearance_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'state.json'
            for settings in ({'focus_minutes': 45}, {'color_mode': {}, 'theme': []}):
                path.write_text(json.dumps({'settings': settings}))
                engine = FocusEngine(path)
                self.assertEqual(engine.settings['color_mode'], 'dark')
                self.assertEqual(engine.settings['theme'], 'coral')
            engine.apply_settings({'color_mode': 'light', 'theme': 'ocean'})
            engine.apply_settings({'color_mode': 'system', 'theme': None})
            restored = FocusEngine(path)
            self.assertEqual(restored.settings['color_mode'], 'light')
            self.assertEqual(restored.settings['theme'], 'ocean')

    def test_appearance_preserves_live_deadline_and_completed_session(self):
        with tempfile.TemporaryDirectory() as directory:
            now = [0.0]
            engine = FocusEngine(Path(directory)/'state.json', clock=lambda: now[0])
            task = engine.add_task('Finish chapter')
            engine.start()
            for elapsed in (123, 1499.75, 1500):
                now[0] = elapsed
                engine.apply_settings({'color_mode': 'light', 'theme': 'forest'})
                self.assertTrue(engine.running)
                self.assertEqual(engine.seconds_remaining(), 1500-elapsed)
                self.assertEqual(engine.selected_task_id, task)
            self.assertEqual(engine.check_finished(), 'focus')
            self.assertEqual(len(engine.sessions), 1)
            engine.apply_settings({'theme': 'lavender'})
            self.assertFalse(engine.running)
            self.assertEqual(engine.seconds_remaining(), 300)

