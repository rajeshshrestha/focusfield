"""Appearance palettes shared by the desktop UI and saved preferences."""

COLOR_MODES = ("dark", "light")
THEMES = {
    "coral": {"name": "Coral", "description": "Warm peach, a familiar focus space.",
              "dark": ("#FFAB85", "#FFC3A8", "#83D5C3", "#A6E4D8"),
              "light": ("#A84422", "#913719", "#146B59", "#105747")},
    "ocean": {"name": "Ocean", "description": "Clear blue with a sea-green break.",
              "dark": ("#82C8FF", "#ADDFFF", "#85DBCE", "#ACEADF"),
              "light": ("#175F99", "#104B7B", "#146B59", "#105747")},
    "forest": {"name": "Forest", "description": "Leaf green with a blue-sky break.",
               "dark": ("#9DD6A0", "#BFE8BD", "#90C9F3", "#B5DDF8"),
               "light": ("#326B37", "#24542A", "#175F99", "#104B7B")},
    "lavender": {"name": "Lavender", "description": "Soft violet with a mint-green break.",
                 "dark": ("#C4ADFF", "#DCCBFF", "#91D8C7", "#B5E9DD"),
                 "light": ("#6B46A8", "#55358A", "#146B59", "#105747")},
}
CHOICE_SETTINGS = {"color_mode": COLOR_MODES, "theme": tuple(THEMES)}


def _mix(first, second, weight):
    rgb = [round(int(first[i:i+2], 16) * (1-weight) + int(second[i:i+2], 16) * weight)
           for i in (1, 3, 5)]
    return "#" + "".join(f"{channel:02X}" for channel in rgb)


def get_palette(color_mode="dark", theme="coral"):
    """Return an independent, complete palette; invalid saved values use defaults."""
    color_mode = color_mode if color_mode in COLOR_MODES else "dark"
    theme = theme if isinstance(theme, str) and theme in THEMES else "coral"
    if color_mode == "dark":
        colors = dict(BG="#0E1622", SIDEBAR="#0B121D", SIDEBAR_ACTIVE="#1A2937",
                      PANEL="#192534", PANEL_DARK="#152130", PANEL_INNER="#223145",
                      BORDER="#3B5066", TEXT="#F5F4F0", MUTED="#ACBAC9",
                      DIM="#98AABD", BUTTON_TEXT="#14202C")
    else:
        colors = dict(BG="#F2F5F9", SIDEBAR="#E6ECF3", SIDEBAR_ACTIVE="#D5E0EC",
                      PANEL="#FFFFFF", PANEL_DARK="#EDF2F7", PANEL_INNER="#E3EAF2",
                      BORDER="#AAB9CB", TEXT="#182536", MUTED="#47586D",
                      DIM="#52647A", BUTTON_TEXT="#FFFFFF")
    accent, hover, secondary, secondary_hover = THEMES[theme][color_mode]
    colors.update(ACCENT=accent, ACCENT_HOVER=hover, SECONDARY=secondary,
                  SECONDARY_HOVER=secondary_hover)
    colors["FOCUS_SURFACE"] = _mix(colors["PANEL"], accent, .09)
    colors["BREAK_SURFACE"] = _mix(colors["PANEL"], secondary, .09)
    colors["QUOTE"] = _mix(colors["SIDEBAR"], accent, .05)
    return colors
