"""
PyScreen — vt_window.py
Single virtual window: ConPTY (pywinpty) + VT100 emulation (pyte)
"""

import threading
import time
import pyte
from winpty import PTY


class VtWindow:
    """A single virtual terminal window = pseudo-console + VT100 emulator."""

    def __init__(self, window_id: int, name: str, cols: int, rows: int,
                 shell_cmd: str = "cmd.exe", encoding: str = "utf-8",
                 linebuf: int = 256):
        self.id = window_id
        self.name = name
        self.cols = cols
        self.rows = rows
        self.encoding = encoding
        self.shell_cmd = shell_cmd

        # Terminal emulation (pyte) with scrollback buffer
        self.screen = pyte.HistoryScreen(cols, rows, history=linebuf)
        self.screen.set_mode(pyte.modes.LNM)  # Line feed = new line
        self.stream = pyte.Stream(self.screen)

        # Pseudo-console (pywinpty ConPTY)
        self.pty = PTY(cols, rows)
        self.pty.spawn(shell_cmd if isinstance(shell_cmd, str) else shell_cmd.decode())

        # State
        self.alive = True
        self.dirty = True  # Flag: buffer changed, needs redraw
        self._lock = threading.Lock()
        self._prev_display = None


        # Thread reading output data from PTY
        self._reader_thread = threading.Thread(
            target=self._reader_loop, daemon=True, name=f"pty-reader-{window_id}"
        )
        self._reader_thread.start()

    def _reader_loop(self):
        """Thread reading output data from PTY and feeding pyte emulator."""
        while self.alive:
            try:
                data = self.pty.read()
                if data:
                    # pywinpty 3.x returns str — pyte.Stream needs str
                    if isinstance(data, bytes):
                        data = data.decode(self.encoding, errors="replace")
                    with self._lock:
                        self.stream.feed(data)
                        self.dirty = True
                else:
                    # No data — short delay
                    time.sleep(0.01)
            except (EOFError, OSError, RuntimeError):
                self.alive = False
                self.dirty = True
                break
            except Exception:
                time.sleep(0.05)

    def write(self, data):
        """Send data (pressed key) to PTY."""
        if not self.alive:
            return
        try:
            # pywinpty 3.x expects str
            if isinstance(data, bytes):
                data = data.decode(self.encoding, errors="replace")
            self.pty.write(data)
        except (OSError, RuntimeError):
            self.alive = False

    def resize(self, cols: int, rows: int):
        """Resize window (PTY + pyte buffer)."""
        self.cols = cols
        self.rows = rows
        try:
            self.pty.set_size(cols, rows)
        except (OSError, RuntimeError):
            pass
        with self._lock:
            self.screen.resize(rows, cols)
            self.dirty = True

    def get_display(self) -> list:
        """Return current screen content as a list of lines."""
        with self._lock:
            return list(self.screen.display)

    def get_cursor(self) -> tuple:
        """Return cursor position (column, row)."""
        with self._lock:
            return (self.screen.cursor.x, self.screen.cursor.y)

    def get_buffer_with_attrs(self):
        """Return buffer with attributes (colors, style) for advanced rendering."""
        with self._lock:
            buf = {}
            buffer = self.screen.buffer
            if isinstance(buffer, dict):
                items = buffer.items()
            else:
                items = enumerate(buffer)
            for y, row in items:
                if y >= self.rows:
                    break
                row_dict = {}
                items_row = row.items() if isinstance(row, dict) else enumerate(row)
                for x, ch in items_row:
                    row_dict[x] = ch
                buf[y] = row_dict
            return buf

    def is_dirty(self) -> bool:
        """Check if buffer changed since last render."""
        return self.dirty

    def mark_clean(self):
        """Mark buffer as rendered."""
        self.dirty = False

    def is_alive(self) -> bool:
        """Check if the shell process is alive."""
        if not self.alive:
            return False
        try:
            if not self.pty.isalive():
                self.alive = False
                return False
        except Exception:
            pass
        return self.alive

    def close(self):
        """Close the window — terminate PTY."""
        self.alive = False
        try:
            del self.pty
        except Exception:
            pass

    def __repr__(self):
        status = "alive" if self.alive else "dead"
        return f"VtWindow(id={self.id}, name='{self.name}', {self.cols}x{self.rows}, {status})"
