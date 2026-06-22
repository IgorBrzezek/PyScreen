import socket
from datetime import datetime
from config import PyScreenConfig


class StatusBar:
    ESC = "\x1b"

    def __init__(self, config: PyScreenConfig):
        self.config = config
        self._last_clock = ""
        self._hostname = socket.gethostname()

    def render(self, windows: list, active_id: int, cols: int,
               input_state_label: str = "") -> str:
        cfg = self.config

        bar_bg = self._bg256(cfg.statusbar_bg)
        bar_fg_codes = self._fg256(cfg.statusbar_fg)
        reset = f"{self.ESC}[0m"

        left_parts = []

        if cfg.show_hostname:
            left_parts.append(
                f"{self._fg256(cfg.hostname_fg)} {self._hostname}"
                f"{self._fg256(cfg.separator_fg)} |"
            )

        clock_str = ""
        if cfg.show_clock:
            clock_str = self._format_clock()
            if cfg.clock_position == "left":
                left_parts.append(
                    f"{self._fg256(cfg.separator_fg)} | "
                    f"{self._fg256(cfg.clock_fg)}{clock_str} "
                )

        win_entries = []
        for wid, wname, is_alive in windows:
            entry = self._format_window_entry(wid, wname, wid == active_id)
            win_entries.append(entry)
        windows_str = " ".join(win_entries)
        if windows_str:
            left_parts.append(f"{bar_fg_codes} {windows_str}")

        if input_state_label:
            left_parts.append(
                f"{self._fg256(cfg.rename_fg)}{self._bg256(cfg.rename_bg)}"
                f" {input_state_label}"
                f"{bar_fg_codes}{bar_bg}"
            )

        left_part = "".join(left_parts)

        right_part = ""
        if cfg.show_clock and cfg.clock_position == "right":
            right_part = (
                f"{self._fg256(cfg.separator_fg)} | "
                f"{self._fg256(cfg.clock_fg)}{clock_str} "
            )

        left_visible = self._visible_len(left_part)
        right_visible = self._visible_len(right_part)
        padding_len = cols - left_visible - right_visible
        if padding_len < 1:
            padding_len = 1
        padding = " " * padding_len

        line = (
            f"{bar_bg}"
            f"{left_part}"
            f"{bar_bg}{bar_fg_codes}{padding}"
            f"{bar_bg}{right_part}"
            f"{reset}"
        )
        return line

    def _format_window_entry(self, wid: int, name: str, is_active: bool) -> str:
        cfg = self.config
        open_br, close_br = cfg.get_bracket_chars()
        symbol = cfg.active_symbol if is_active else " "

        if is_active:
            bracket_fg = self._fg256(cfg.active_bracket_fg)
            bracket_bg = self._bg256(cfg.active_bracket_bg)
            win_fg = self._fg256(cfg.active_window_fg)
            win_bg = self._bg256(cfg.active_window_bg)
        else:
            bracket_fg = self._fg256(cfg.inactive_bracket_fg)
            bracket_bg = self._bg256(cfg.inactive_bracket_bg)
            win_fg = self._fg256(cfg.inactive_window_fg)
            win_bg = self._bg256(cfg.inactive_window_bg)

        return (
            f"{bracket_fg}{bracket_bg}{open_br}"
            f"{win_fg}{win_bg}{wid}{symbol}{name}"
            f"{bracket_fg}{bracket_bg}{close_br}"
        )

    def _format_clock(self) -> str:
        now = datetime.now()
        return self.config.format_clock(now)

    def _fg256(self, color_id: int) -> str:
        return f"{self.ESC}[38;5;{color_id}m"

    def _bg256(self, color_id: int) -> str:
        return f"{self.ESC}[48;5;{color_id}m"

    @staticmethod
    def _visible_len(text: str) -> int:
        import re
        ansi_re = re.compile(r'\x1b\[[0-9;]*m')
        clean = ansi_re.sub('', text)
        return len(clean)
