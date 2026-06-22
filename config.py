"""
PyScreen — config.py
Parser and validator for pyscreen.cfg config file
"""

import configparser
import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional


# Bracket name to character pair mapping
BRACKET_MAP = {
    "parens": ("(", ")"),
    "brackets": ("[", "]"),
    "angles": ("<", ">"),
    "braces": ("{", "}"),
}

# List of allowed action names for keybinds
VALID_KEYBIND_ACTIONS = {
    "new_window", "next_window", "prev_window", "last_window",
    "rename", "kill_window", "list_windows", "select_window",
    "detach", "help", "redraw", "scroll_up", "scroll_down",
    "passthrough", "info",
}

# Default keybinds (can be overridden in [keybinds] section)
DEFAULT_KEYBINDS = {
    "c": "new_window",
    "n": "next_window",
    "p": "prev_window",
    "A": "rename",
    "a": "rename",
    "k": "kill_window",
    "w": "list_windows",
    '"': "select_window",
    "d": "detach",
    "h": "help",
    "?": "help",
    "l": "redraw",
    "r": "redraw",
    "i": "info",
}

# Clock format tokens
CLOCK_TOKENS = {
    "YYYY": lambda dt: f"{dt.year:04d}",
    "YY": lambda dt: f"{dt.year % 100:02d}",
    "MO": lambda dt: f"{dt.month:02d}",
    "DD": lambda dt: f"{dt.day:02d}",
    "HH": lambda dt: f"{dt.hour:02d}",
    "MM": lambda dt: f"{dt.minute:02d}",
    "SS": lambda dt: f"{dt.second:02d}",
}


@dataclass
class PyScreenConfig:
    """PyScreen configuration loaded from pyscreen.cfg"""

    # --- statusbar ---
    statusbar_position: str = "bottom"
    statusbar_bg: int = 236
    statusbar_fg: int = 15
    active_window_fg: int = 15
    active_window_bg: int = 236
    inactive_window_fg: int = 244
    inactive_window_bg: int = 236
    window_brackets: str = "brackets"
    active_symbol: str = "*"
    active_bracket_fg: int = 11
    active_bracket_bg: int = 236
    inactive_bracket_fg: int = 15
    inactive_bracket_bg: int = 236
    show_clock: bool = False
    clock_format: str = "HH:MM"
    clock_position: str = "right"
    show_hostname: bool = False
    hostname_fg: int = 11
    clock_fg: int = 14
    separator_fg: int = 240
    rename_fg: int = 15
    rename_bg: int = 236

    # --- shell ---
    shell_command: str = "cmd.exe"
    default_window_name: str = "shell"

    # --- keybindings ---
    prefix_key: str = "Ctrl+A"

    # --- display ---
    main_background: str = "default"

    # --- linebuf ---
    linebuf: int = 256

    # --- keybinds (loaded from [keybinds], override DEFAULT_KEYBINDS) ---
    keybinds: dict = field(default_factory=lambda: dict(DEFAULT_KEYBINDS))

    # --- runtime (not from cfg file) ---
    encoding: str = "utf-8"
    session_name: Optional[str] = None

    def load(self, path: Optional[str] = None) -> bool:
        """Load config from file. Returns True if file was found."""
        cfg_path = self._find_config(path)
        if cfg_path is None:
            return False

        parser = configparser.ConfigParser()
        parser.optionxform = lambda x: x  # Preserve original key case
        parser.read(cfg_path, encoding="utf-8-sig")

        # --- [statusbar] ---
        if parser.has_section("statusbar"):
            sb = parser["statusbar"]
            self.statusbar_position = self._val_choice(
                sb.get("position", fallback=self.statusbar_position),
                ["top", "bottom"],
                self.statusbar_position,
            )
            self.statusbar_bg = self._val_color(
                sb.get("background_color"), self.statusbar_bg
            )
            self.statusbar_fg = self._val_color(
                sb.get("foreground_color"), self.statusbar_fg
            )
            self.active_window_fg = self._val_color(
                sb.get("active_window_fg"), self.active_window_fg
            )
            self.active_window_bg = self._val_color(
                sb.get("active_window_bg"), self.active_window_bg
            )
            self.inactive_window_fg = self._val_color(
                sb.get("inactive_window_fg"), self.inactive_window_fg
            )
            self.inactive_window_bg = self._val_color(
                sb.get("inactive_window_bg"), self.inactive_window_bg
            )
            self.window_brackets = self._val_choice(
                sb.get("window_brackets", fallback=self.window_brackets),
                list(BRACKET_MAP.keys()),
                self.window_brackets,
            )
            sym = sb.get("active_symbol", fallback=self.active_symbol)
            if len(sym) <= 2:
                self.active_symbol = sym
            self.active_bracket_fg = self._val_color(
                sb.get("active_bracket_fg"), self.active_bracket_fg
            )
            self.active_bracket_bg = self._val_color(
                sb.get("active_bracket_bg"), self.active_bracket_bg
            )
            self.inactive_bracket_fg = self._val_color(
                sb.get("inactive_bracket_fg"), self.inactive_bracket_fg
            )
            self.inactive_bracket_bg = self._val_color(
                sb.get("inactive_bracket_bg"), self.inactive_bracket_bg
            )
            self.show_clock = sb.getboolean("show_clock", fallback=self.show_clock)
            self.clock_format = sb.get("clock_format", fallback=self.clock_format)
            self.clock_position = self._val_choice(
                sb.get("clock_position", fallback=self.clock_position),
                ["left", "right"],
                self.clock_position,
            )
            self.show_hostname = sb.getboolean(
                "hostname", fallback=self.show_hostname
            )
            if not self.show_hostname:
                self.show_hostname = sb.get(
                    "show_hostname", fallback="no"
                ).lower() in ("yes", "true", "1", "on")
            self.hostname_fg = self._val_color(
                sb.get("hostname_fg"), self.hostname_fg
            )
            self.clock_fg = self._val_color(
                sb.get("clock_fg"), self.clock_fg
            )
            self.separator_fg = self._val_color(
                sb.get("separator_fg"), self.separator_fg
            )
            self.rename_fg = self._val_color(
                sb.get("rename_fg"), self.rename_fg
            )
            self.rename_bg = self._val_color(
                sb.get("rename_bg"), self.rename_bg
            )

        # --- [shell] ---
        if parser.has_section("shell"):
            sh = parser["shell"]
            self.shell_command = sh.get("command", fallback=self.shell_command)
            self.default_window_name = sh.get(
                "default_name", fallback=self.default_window_name
            )

        # --- [keybindings] ---
        if parser.has_section("keybindings"):
            kb = parser["keybindings"]
            self.prefix_key = kb.get("prefix", fallback=self.prefix_key)

        # --- [keybinds] (override default shortcuts) ---
        if parser.has_section("keybinds"):
            for key, action_name in parser["keybinds"].items():
                action_name = action_name.strip().lower()
                if action_name in VALID_KEYBIND_ACTIONS:
                    self.keybinds[key] = action_name
                # ignore unknown actions — don't break config

        # --- [display] ---
        if parser.has_section("display"):
            disp = parser["display"]
            self.main_background = disp.get(
                "main_background", fallback=self.main_background
            )

        return True

    def get_bracket_chars(self) -> tuple:
        """Return bracket character pair (opening, closing)."""
        return BRACKET_MAP.get(self.window_brackets, ("[", "]"))

    def format_clock(self, now: Optional[datetime] = None) -> str:
        """Format clock according to clock_format."""
        if now is None:
            now = datetime.now()
        result = self.clock_format
        # Replace tokens from longest (YYYY before YY)
        for token in sorted(CLOCK_TOKENS.keys(), key=len, reverse=True):
            if token in result:
                result = result.replace(token, CLOCK_TOKENS[token](now))
        return result

    def _find_config(self, explicit_path: Optional[str] = None) -> Optional[str]:
        """Search for config file in standard locations."""
        candidates = []
        if explicit_path:
            candidates.append(explicit_path)
        candidates.extend([
            os.path.join(os.getcwd(), "pyscreen.cfg"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "pyscreen.cfg"),
            os.path.join(os.path.expanduser("~"), ".pyscreen.cfg"),
            os.path.join(
                os.environ.get("APPDATA", ""), "PyScreen", "pyscreen.cfg"
            ),
        ])
        for path in candidates:
            if path and os.path.isfile(path):
                return path
        return None

    @staticmethod
    def _val_color(value, default: int) -> int:
        """Validate color value (0-255)."""
        if value is None:
            return default
        try:
            v = int(value)
            return v if 0 <= v <= 255 else default
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _val_choice(value: str, choices: list, default: str) -> str:
        """Validate value against allowed list."""
        v = value.strip().lower()
        return v if v in choices else default
