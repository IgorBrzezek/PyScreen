import os
import time
from typing import Optional
from vt_window import VtWindow
from config import PyScreenConfig


class WindowManager:
    MAX_WINDOWS = 10

    def __init__(self, config: PyScreenConfig):
        self.config = config
        self.windows: dict[int, VtWindow] = {}
        self.active_id: int = -1
        self.last_active_id: int = -1
        self.session_name: str = ""
        self.server_port: int = 0
        self.sb_dirty: bool = True
        self.state_label: str = ""
        self.start_time: float = time.time()
        self.detach_start: Optional[float] = None
        self.total_detach_seconds: float = 0.0

    @property
    def uptime_seconds(self) -> int:
        return int(time.time() - self.start_time)

    @property
    def detach_seconds(self) -> int:
        total = self.total_detach_seconds
        if self.detach_start is not None:
            total += time.time() - self.detach_start
        return int(total)

    def create_window(self, name: Optional[str] = None,
                      cols: int = 80, rows: int = 24) -> Optional[VtWindow]:
        if len(self.windows) >= self.MAX_WINDOWS:
            return None

        wid = self._find_free_id()
        if wid is None:
            return None

        if name is None:
            name = self.config.default_window_name

        window = VtWindow(
            window_id=wid,
            name=name,
            cols=cols,
            rows=rows,
            shell_cmd=self.config.shell_command,
            encoding=self.config.encoding,
            linebuf=self.config.linebuf,
        )
        self.windows[wid] = window

        self.last_active_id = self.active_id
        self.active_id = wid
        self.sb_dirty = True

        return window

    def close_window(self, wid: int) -> bool:
        if wid not in self.windows:
            return False

        window = self.windows[wid]
        window.close()
        del self.windows[wid]
        self.sb_dirty = True

        if self.active_id == wid:
            if self.last_active_id >= 0 and self.last_active_id in self.windows:
                self.active_id = self.last_active_id
            elif self.windows:
                ids = sorted(self.windows.keys())
                self.active_id = ids[0]
            else:
                self.active_id = -1

        if self.last_active_id == wid:
            self.last_active_id = -1

        return True

    def switch_to(self, wid: int) -> bool:
        if wid not in self.windows:
            return False
        if wid == self.active_id:
            return True
        self.last_active_id = self.active_id
        self.active_id = wid
        self.windows[wid].dirty = True
        self.sb_dirty = True
        return True

    def next_window(self) -> bool:
        if len(self.windows) <= 1:
            return False
        ids = sorted(self.windows.keys())
        try:
            idx = ids.index(self.active_id)
            next_idx = (idx + 1) % len(ids)
            return self.switch_to(ids[next_idx])
        except ValueError:
            return False

    def prev_window(self) -> bool:
        if len(self.windows) <= 1:
            return False
        ids = sorted(self.windows.keys())
        try:
            idx = ids.index(self.active_id)
            prev_idx = (idx - 1) % len(ids)
            return self.switch_to(ids[prev_idx])
        except ValueError:
            return False

    def switch_to_last(self) -> bool:
        if self.last_active_id >= 0 and self.last_active_id in self.windows:
            return self.switch_to(self.last_active_id)
        return False

    def rename_window(self, wid: int, name: str) -> bool:
        if wid not in self.windows:
            return False
        self.windows[wid].name = name
        self.sb_dirty = True
        return True

    def get_active(self) -> Optional[VtWindow]:
        return self.windows.get(self.active_id)

    def get_window_list(self) -> list:
        result = []
        for wid in sorted(self.windows.keys()):
            w = self.windows[wid]
            result.append((wid, w.name, w.is_alive()))
        return result

    def cleanup_dead(self) -> list:
        dead = [wid for wid, w in self.windows.items() if not w.is_alive()]
        for wid in dead:
            self.close_window(wid)
        return dead

    def resize_all(self, cols: int, rows: int):
        for w in self.windows.values():
            w.resize(cols, rows)

    def has_windows(self) -> bool:
        return len(self.windows) > 0

    def update_session_info(self):
        if not self.session_name:
            return
        try:
            import session as _session
            info = _session.load_session_info(self.session_name) or {}
            info["name"] = self.session_name
            info["app"] = "PyScreen"
            info["version"] = getattr(self, 'version', "")
            info["pid"] = os.getpid()
            info["port"] = self.server_port
            info["windows"] = len(self.windows)
            info["created"] = self.start_time
            _session.save_session_info(self.session_name, info)
        except Exception:
            pass

    def _find_free_id(self) -> Optional[int]:
        for i in range(self.MAX_WINDOWS):
            if i not in self.windows:
                return i
        return None


