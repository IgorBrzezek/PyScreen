"""
PyScreen — renderer.py
Rendering active window and status bar to physical terminal
using ANSI/VT100 sequences.
"""

import sys
import os
import ctypes
from ctypes import wintypes

# --- Windows Console API constants ---
STD_OUTPUT_HANDLE = -11
STD_INPUT_HANDLE = -10
ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
ENABLE_PROCESSED_OUTPUT = 0x0001
ENABLE_WINDOW_INPUT = 0x0008
ENABLE_MOUSE_INPUT = 0x0010
ENABLE_PROCESSED_INPUT = 0x0001
ENABLE_LINE_INPUT = 0x0002
ENABLE_ECHO_INPUT = 0x0004

kernel32 = ctypes.windll.kernel32


class Renderer:
    """Renders PyScreen: window buffer + status bar."""

    # ANSI sequences
    ESC = "\x1b"
    CSI = "\x1b["

    def __init__(self, config):
        self.config = config
        self.cols = 80
        self.rows = 24
        self._prev_display = None
        self._prev_status = None
        self._original_out_mode = None
        self._original_in_mode = None

    def setup_terminal(self):
        """Configure terminal: VT processing, raw mode, alternate screen."""
        # Set UTF-8 encoding for console
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)

        # Configure stdout to UTF-8
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except AttributeError:
            import io
            if hasattr(sys.stdout, 'buffer'):
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

        # Save original console modes
        h_out = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        h_in = kernel32.GetStdHandle(STD_INPUT_HANDLE)
        out_mode = wintypes.DWORD()
        in_mode = wintypes.DWORD()
        kernel32.GetConsoleMode(h_out, ctypes.byref(out_mode))
        kernel32.GetConsoleMode(h_in, ctypes.byref(in_mode))
        self._original_out_mode = out_mode.value
        self._original_in_mode = in_mode.value

        # Enable VT processing on output
        new_out = out_mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING | ENABLE_PROCESSED_OUTPUT
        kernel32.SetConsoleMode(h_out, new_out)

        # Enable raw mode on input (disable PROCESSED, LINE, ECHO)
        new_in = ENABLE_WINDOW_INPUT  # Only window and key events
        kernel32.SetConsoleMode(h_in, new_in)

        # Get terminal size
        self._update_size()

        # Alternate screen buffer + hide cursor
        self._write(f"{self.CSI}?1049h")  # Alternate screen ON
        self._write(f"{self.CSI}?25l")     # Cursor OFF
        self._flush()

    def _write_vt(self, text: str):
        """Write VT sequences directly via WriteConsoleW."""
        h_out = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        written = wintypes.DWORD()
        kernel32.WriteConsoleW(h_out, text, len(text), ctypes.byref(written), None)

    def restore_terminal(self):
        """Restore terminal to state before startup."""
        # Force flush stdout buffer before writing VT
        sys.stdout.flush()

        # Write VT sequences directly via WriteConsoleW (bypasses encoding)
        self._write_vt(f"{self.CSI}?25h")     # Cursor ON
        self._write_vt(f"{self.CSI}1 q")      # Blinking block cursor
        self._write_vt(f"{self.CSI}?1049l")   # Alternate screen OFF
        self._write_vt(f"{self.CSI}0m")       # Reset attributes
        self._write_vt(f"{self.CSI}?25h")     # Cursor ON (double check)
        self._write_vt(f"{self.CSI}1 q")      # Blinking block cursor

        # Force flush before changing console mode
        sys.stdout.flush()

        # Restore original console modes
        h_out = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        h_in = kernel32.GetStdHandle(STD_INPUT_HANDLE)
        if self._original_out_mode is not None:
            kernel32.SetConsoleMode(h_out, self._original_out_mode)
        if self._original_in_mode is not None:
            kernel32.SetConsoleMode(h_in, self._original_in_mode)

    def get_terminal_size(self) -> tuple:
        """Return (cols, rows) of the terminal."""
        self._update_size()
        return (self.cols, self.rows)

    def get_usable_rows(self) -> int:
        """Return number of rows available for window (minus status bar)."""
        return self.rows - 1

    def render(self, window, status_line: str):
        """Render window and status bar (incremental)."""
        self._update_size()
        usable = self.get_usable_rows()
        sb_pos = self.config.statusbar_position

        buf = []

        # Determine row offset (if status on top, window starts at row 2)
        if sb_pos == "top":
            status_row = 0
            content_offset = 1
        else:
            status_row = self.rows - 1
            content_offset = 0

        # --- Render window content with colors ---
        colored_lines = []
        if window:
            buffer = window.get_buffer_with_attrs()
            for i in range(usable):
                row_data = buffer.get(i, {})
                colored_lines.append(self._render_buffer_line(row_data, self.cols))
        else:
            colored_lines = [" " * self.cols] * usable

        for i in range(usable):
            screen_row = content_offset + i
            line = colored_lines[i] if i < len(colored_lines) else " " * self.cols

            # Check if line changed
            need_draw = True
            if self._prev_display and i < len(self._prev_display):
                if self._prev_display[i] == line:
                    need_draw = False

            if need_draw:
                # Set cursor position (1-indexed)
                buf.append(f"{self.CSI}{screen_row + 1};1H")
                buf.append(line)

        # --- Render status bar ---
        if status_line != self._prev_status or self._prev_display is None:
            buf.append(f"{self.CSI}{status_row + 1};1H")
            buf.append(status_line)
            self._prev_status = status_line

        # --- Set cursor to pyte position ---
        if window:
            cx, cy = window.get_cursor()
            term_row = content_offset + cy + 1  # 1-indexed
            term_col = cx + 1
            if 1 <= term_row <= self.rows and 1 <= term_col <= self.cols:
                buf.append(f"{self.CSI}?25h")  # Show cursor
                buf.append(f"{self.CSI}1 q")   # Blinking block cursor
                buf.append(f"{self.CSI}{term_row};{term_col}H")
            else:
                buf.append(f"{self.CSI}?25l")  # Hide cursor
        else:
            buf.append(f"{self.CSI}?25l")

        # Reset attributes at end
        buf.append(f"{self.CSI}0m")

        if buf:
            self._write("".join(buf))
            self._flush()

        # Save current display for comparison
        self._prev_display = colored_lines[:]

        if window:
            window.mark_clean()

    def _render_buffer_line(self, row_data, cols):
        """Render a single buffer line with ANSI codes."""
        result = []
        prev_fg = 'default'
        prev_bg = 'default'
        prev_bold = False
        prev_italics = False
        prev_underscore = False
        prev_strikethrough = False
        prev_reverse = False

        for x in range(cols):
            ch = row_data.get(x)
            if ch is None:
                result.append(' ')
                continue

            if (ch.fg != prev_fg or ch.bg != prev_bg or
                ch.bold != prev_bold or ch.italics != prev_italics or
                ch.underscore != prev_underscore or
                ch.strikethrough != prev_strikethrough or
                ch.reverse != prev_reverse):
                result.append(self._ansi_attrs(ch))
                prev_fg = ch.fg
                prev_bg = ch.bg
                prev_bold = ch.bold
                prev_italics = ch.italics
                prev_underscore = ch.underscore
                prev_strikethrough = ch.strikethrough
                prev_reverse = ch.reverse

            result.append(ch.data)

        if any([prev_fg != 'default', prev_bg != 'default', prev_bold,
                prev_italics, prev_underscore, prev_strikethrough, prev_reverse]):
            result.append(f"{self.CSI}0m")

        return ''.join(result)

    def _ansi_attrs(self, ch):
        """Build ANSI SGR sequence from Char attributes."""
        parts = []
        if ch.bold:
            parts.append('1')
        if ch.italics:
            parts.append('3')
        if ch.underscore:
            parts.append('4')
        if ch.reverse:
            parts.append('7')
        if ch.strikethrough:
            parts.append('9')
        if isinstance(ch.fg, int):
            parts.append(f'38;5;{ch.fg}')
        elif ch.fg not in ('default',):
            r, g, b = self._parse_color(ch.fg)
            if r is not None:
                parts.append(f'38;2;{r};{g};{b}')
            else:
                parts.append(f'38;5;{self._named_color(ch.fg)}')
        if isinstance(ch.bg, int):
            parts.append(f'48;5;{ch.bg}')
        elif ch.bg not in ('default',):
            r, g, b = self._parse_color(ch.bg)
            if r is not None:
                parts.append(f'48;2;{r};{g};{b}')
            else:
                parts.append(f'48;5;{self._named_color(ch.bg)}')
        if not parts:
            return f"{self.CSI}0m"
        return f"{self.CSI}0;{';'.join(parts)}m"

    @staticmethod
    def _parse_color(color):
        """Parse color returned by pyte: hex string 'rrggbb' or name."""
        if isinstance(color, str) and len(color) == 6:
            try:
                r = int(color[0:2], 16)
                g = int(color[2:4], 16)
                b = int(color[4:6], 16)
                return r, g, b
            except ValueError:
                pass
        return None, None, None

    @staticmethod
    def _named_color(name):
        """Map pyte color name to ANSI 256 index."""
        mapping = {
            'black': 0, 'red': 1, 'green': 2, 'brown': 3,
            'blue': 4, 'magenta': 5, 'cyan': 6, 'white': 7,
            'lightblack': 8, 'lightred': 9, 'lightgreen': 10,
            'lightbrown': 11, 'lightblue': 12, 'lightmagenta': 13,
            'lightcyan': 14, 'lightwhite': 15,
            'brightblack': 8, 'brightred': 9, 'brightgreen': 10,
            'brightbrown': 11, 'brightblue': 12, 'brightmagenta': 13,
            'brightcyan': 14, 'brightwhite': 15,
        }
        return mapping.get(name, 7)

    def full_redraw(self, window, status_line: str):
        """Force full redraw of the screen."""
        self._prev_display = None
        self._prev_status = None
        # Clear screen
        self._write(f"{self.CSI}2J")
        self._flush()
        self.render(window, status_line)

    def show_message(self, message: str, row: int = -1):
        """Display a short message on screen (e.g. help, confirm)."""
        if row < 0:
            row = self.rows // 2
        padded = message[:self.cols].center(self.cols)
        buf = f"{self.CSI}{row + 1};1H{self.CSI}7m{padded}{self.CSI}0m"
        self._write(buf)
        self._flush()

    def _update_size(self):
        """Update terminal size from Windows API."""
        try:
            size = os.get_terminal_size()
            self.cols = size.columns
            self.rows = size.lines
        except OSError:
            pass

    def _write(self, text: str):
        """Write text to stdout."""
        sys.stdout.write(text)

    def _flush(self):
        """Flush stdout."""
        sys.stdout.flush()
