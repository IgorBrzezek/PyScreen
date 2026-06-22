import ctypes
import threading
import sys
from ctypes import wintypes
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32

STD_INPUT_HANDLE = -10
KEY_EVENT = 0x0001
WINDOW_BUFFER_SIZE_EVENT = 0x0004
FOCUS_EVENT = 0x0010

RIGHT_ALT_PRESSED = 0x0001
LEFT_ALT_PRESSED = 0x0002
RIGHT_CTRL_PRESSED = 0x0004
LEFT_CTRL_PRESSED = 0x0008
SHIFT_PRESSED = 0x0010

VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_BACK = 0x08
VK_TAB = 0x09
VK_UP = 0x26
VK_DOWN = 0x28
VK_LEFT = 0x25
VK_RIGHT = 0x27
VK_HOME = 0x24
VK_END = 0x23
VK_DELETE = 0x2E
VK_INSERT = 0x2D
VK_PRIOR = 0x21
VK_NEXT = 0x22
VK_F1 = 0x70
VK_F12 = 0x7B

WH_MOUSE_LL = 14
WM_MOUSEWHEEL = 0x020A
WM_RBUTTONDOWN = 0x0204

class KEY_EVENT_RECORD(ctypes.Structure):
    class _uChar(ctypes.Union):
        _fields_ = [
            ("UnicodeChar", ctypes.c_wchar),
            ("AsciiChar", ctypes.c_char),
        ]
    _fields_ = [
        ("bKeyDown", wintypes.BOOL),
        ("wRepeatCount", wintypes.WORD),
        ("wVirtualKeyCode", wintypes.WORD),
        ("wVirtualScanCode", wintypes.WORD),
        ("uChar", _uChar),
        ("dwControlKeyState", wintypes.DWORD),
    ]

class COORD(ctypes.Structure):
    _fields_ = [
        ("X", ctypes.c_short),
        ("Y", ctypes.c_short),
    ]

class WINDOW_BUFFER_SIZE_RECORD(ctypes.Structure):
    _fields_ = [
        ("dwSize", COORD),
    ]

class FOCUS_EVENT_RECORD(ctypes.Structure):
    _fields_ = [
        ("bSetFocus", wintypes.BOOL),
    ]

class INPUT_RECORD_Event(ctypes.Union):
    _fields_ = [
        ("KeyEvent", KEY_EVENT_RECORD),
        ("WindowBufferSizeEvent", WINDOW_BUFFER_SIZE_RECORD),
        ("FocusEvent", FOCUS_EVENT_RECORD),
    ]

class INPUT_RECORD(ctypes.Structure):
    _fields_ = [
        ("EventType", wintypes.WORD),
        ("Event", INPUT_RECORD_Event),
    ]

class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("ptX", ctypes.c_long),
        ("ptY", ctypes.c_long),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]

class ActionType(Enum):
    NONE = auto()
    PASSTHROUGH = auto()
    NEW_WINDOW = auto()
    NEXT_WINDOW = auto()
    PREV_WINDOW = auto()
    SWITCH_WINDOW = auto()
    LAST_WINDOW = auto()
    RENAME_START = auto()
    RENAME_CHAR = auto()
    RENAME_CONFIRM = auto()
    RENAME_CANCEL = auto()
    KILL_WINDOW = auto()
    LIST_WINDOWS = auto()
    SELECT_WINDOW = auto()
    DETACH = auto()
    HELP = auto()
    RESIZE = auto()
    REDRAW = auto()
    SCROLL_UP = auto()
    SCROLL_DOWN = auto()
    INFO = auto()
    MOUSE_SCROLL_UP = auto()
    MOUSE_SCROLL_DOWN = auto()

@dataclass
class Action:
    type: ActionType
    data: Optional[bytes] = None
    window_id: Optional[int] = None
    text: Optional[str] = None
    scroll_count: int = 1

class InputState(Enum):
    NORMAL = auto()
    PREFIX = auto()
    RENAME = auto()
    WINDOW_SELECT = auto()


class InputHandler:
    ACTION_NAME_MAP = {
        "new_window": ActionType.NEW_WINDOW,
        "next_window": ActionType.NEXT_WINDOW,
        "prev_window": ActionType.PREV_WINDOW,
        "last_window": ActionType.LAST_WINDOW,
        "rename": ActionType.RENAME_START,
        "kill_window": ActionType.KILL_WINDOW,
        "list_windows": ActionType.LIST_WINDOWS,
        "select_window": ActionType.SELECT_WINDOW,
        "detach": ActionType.DETACH,
        "help": ActionType.HELP,
        "redraw": ActionType.REDRAW,
        "scroll_up": ActionType.SCROLL_UP,
        "scroll_down": ActionType.SCROLL_DOWN,
        "passthrough": ActionType.PASSTHROUGH,
        "info": ActionType.INFO,
    }

    def __init__(self, keybinds: dict = None):
        self.state = InputState.NORMAL
        self.rename_buffer = ""
        self._h_stdin = kernel32.GetStdHandle(STD_INPUT_HANDLE)
        self.keybinds = keybinds if keybinds is not None else {}
        self._mouse_wheel = 0
        self._mouse_lock = threading.Lock()
        self._paste_queue = []
        self._paste_lock = threading.Lock()
        self._hook_thread = None
        self._hook_running = False
        self._mouse_proc_callback = None
        self._mouse_hook_handle = None
        self._start_mouse_hook()

    def _start_mouse_hook(self):
        self._hook_running = True
        HOOKPROC = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_int, ctypes.c_ulong, ctypes.c_void_p
        )
        self._mouse_proc_callback = HOOKPROC(self._low_level_mouse_proc)
        self._hook_thread = threading.Thread(target=self._mouse_hook_loop, daemon=True)
        self._hook_thread.start()

    def _low_level_mouse_proc(self, nCode, wParam, lParam):
        if nCode == 0:
            info = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            hwnd = user32.GetConsoleWindow()
            rect = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            pt = POINT(info.ptX, info.ptY)
            if (pt.x >= rect.left and pt.x <= rect.right and
                pt.y >= rect.top and pt.y <= rect.bottom):
                if wParam == WM_RBUTTONDOWN:
                    if user32.OpenClipboard(None):
                        handle = user32.GetClipboardData(13)
                        if handle:
                            ptr = ctypes.windll.kernel32.GlobalLock(handle)
                            if ptr:
                                text = ctypes.c_wchar_p(ptr).value
                                if text:
                                    with self._paste_lock:
                                        self._paste_queue.append(text)
                                ctypes.windll.kernel32.GlobalUnlock(ptr)
                        user32.CloseClipboard()
                    return 1
                elif wParam == WM_MOUSEWHEEL:
                    delta = ctypes.c_short(info.mouseData >> 16).value
                    with self._mouse_lock:
                        if delta > 0:
                            self._mouse_wheel += 1
                        else:
                            self._mouse_wheel -= 1
                    return 1
        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    def _mouse_hook_loop(self):
        self._mouse_hook_handle = user32.SetWindowsHookExW(
            WH_MOUSE_LL, self._mouse_proc_callback,
            ctypes.windll.kernel32.GetModuleHandleW(None), 0
        )
        msg = wintypes.MSG()
        while self._hook_running:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret <= 0:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        if self._mouse_hook_handle:
            user32.UnhookWindowsHookEx(self._mouse_hook_handle)
            self._mouse_hook_handle = None

    def _consume_mouse_wheel(self) -> int:
        with self._mouse_lock:
            val = self._mouse_wheel
            self._mouse_wheel = 0
        return val

    def read_input(self, timeout_ms: int = 50) -> Optional[Action]:
        with self._paste_lock:
            if self._paste_queue:
                text = self._paste_queue.pop(0)
                if text:
                    return Action(type=ActionType.PASSTHROUGH, data=text.encode("utf-8"))

        wheel = self._consume_mouse_wheel()
        if wheel != 0:
            if wheel > 0:
                return Action(type=ActionType.SCROLL_UP, scroll_count=wheel)
            else:
                return Action(type=ActionType.SCROLL_DOWN, scroll_count=-wheel)
            # Each mouse wheel notch produces one event

        result = kernel32.WaitForSingleObject(self._h_stdin, timeout_ms)
        if result != 0:
            return None

        ir = INPUT_RECORD()
        num_read = wintypes.DWORD()
        if not kernel32.ReadConsoleInputW(
            self._h_stdin, ctypes.byref(ir), 1, ctypes.byref(num_read)
        ):
            return None

        if num_read.value == 0:
            return None

        if ir.EventType == WINDOW_BUFFER_SIZE_EVENT:
            return Action(type=ActionType.RESIZE)

        if ir.EventType != KEY_EVENT:
            return None

        ke = ir.Event.KeyEvent
        if not ke.bKeyDown:
            return None

        vk = ke.wVirtualKeyCode
        ctrl_state = ke.dwControlKeyState
        char = ke.uChar.UnicodeChar
        ctrl_pressed = bool(ctrl_state & (LEFT_CTRL_PRESSED | RIGHT_CTRL_PRESSED))

        if self.state == InputState.NORMAL:
            return self._handle_normal(vk, char, ctrl_pressed, ctrl_state)
        elif self.state == InputState.PREFIX:
            return self._handle_prefix(vk, char, ctrl_pressed)
        elif self.state == InputState.RENAME:
            return self._handle_rename(vk, char)
        elif self.state == InputState.WINDOW_SELECT:
            return self._handle_window_select(vk, char)
        return None

    def _handle_normal(self, vk, char, ctrl_pressed, ctrl_state) -> Action:
        if ctrl_pressed and vk == 0x41:
            self.state = InputState.PREFIX
            return Action(type=ActionType.NONE)

        data = self._key_to_bytes(vk, char, ctrl_pressed, ctrl_state)
        if data:
            return Action(type=ActionType.PASSTHROUGH, data=data)
        return Action(type=ActionType.NONE)

    def _handle_prefix(self, vk, char, ctrl_pressed) -> Action:
        self.state = InputState.NORMAL

        if ctrl_pressed and vk == 0x41:
            return Action(type=ActionType.LAST_WINDOW)

        if vk == VK_UP:
            return Action(type=ActionType.SCROLL_UP)
        elif vk == VK_DOWN:
            return Action(type=ActionType.SCROLL_DOWN)
        elif vk == VK_PRIOR:
            return Action(type=ActionType.SCROLL_UP, scroll_count=-1)
        elif vk == VK_NEXT:
            return Action(type=ActionType.SCROLL_DOWN, scroll_count=-1)

        if char and char in self.keybinds:
            action_name = self.keybinds[char]
            action_type = self.ACTION_NAME_MAP.get(action_name, ActionType.NONE)
            return self._dispatch_prefix_action(action_type, char)

        if char and char.isdigit():
            return Action(type=ActionType.SWITCH_WINDOW, window_id=int(char))

        return Action(type=ActionType.NONE)

    def _dispatch_prefix_action(self, action_type: ActionType, char: str) -> Action:
        if action_type == ActionType.RENAME_START:
            self.state = InputState.RENAME
            self.rename_buffer = ""
            return Action(type=ActionType.RENAME_START)
        elif action_type == ActionType.SELECT_WINDOW:
            self.state = InputState.WINDOW_SELECT
            return Action(type=ActionType.SELECT_WINDOW)
        elif action_type == ActionType.SWITCH_WINDOW:
            if char and char.isdigit():
                return Action(type=ActionType.SWITCH_WINDOW, window_id=int(char))
            return Action(type=ActionType.NONE)
        elif action_type == ActionType.PASSTHROUGH:
            return Action(type=ActionType.NONE)
        elif action_type != ActionType.NONE:
            return Action(type=action_type)
        return Action(type=ActionType.NONE)

    def _handle_rename(self, vk, char) -> Action:
        if vk == VK_RETURN:
            self.state = InputState.NORMAL
            name = self.rename_buffer
            self.rename_buffer = ""
            return Action(type=ActionType.RENAME_CONFIRM, text=name)
        elif vk == VK_ESCAPE:
            self.state = InputState.NORMAL
            self.rename_buffer = ""
            return Action(type=ActionType.RENAME_CANCEL)
        elif vk == VK_BACK:
            if self.rename_buffer:
                self.rename_buffer = self.rename_buffer[:-1]
            return Action(type=ActionType.RENAME_CHAR, text=self.rename_buffer)
        elif char and char.isprintable():
            self.rename_buffer += char
            return Action(type=ActionType.RENAME_CHAR, text=self.rename_buffer)
        return Action(type=ActionType.NONE)

    def _handle_window_select(self, vk, char) -> Action:
        self.state = InputState.NORMAL
        if char.isdigit():
            return Action(type=ActionType.SWITCH_WINDOW, window_id=int(char))
        return Action(type=ActionType.NONE)

    def _key_to_bytes(self, vk, char, ctrl_pressed, ctrl_state) -> Optional[bytes]:
        VT_MAP = {
            0x26: b'\x1b[A',
            0x28: b'\x1b[B',
            0x27: b'\x1b[C',
            0x25: b'\x1b[D',
            0x24: b'\x1b[H',
            0x23: b'\x1b[F',
            0x2E: b'\x1b[3~',
            0x2D: b'\x1b[2~',
            0x21: b'\x1b[5~',
            0x22: b'\x1b[6~',
            0x70: b'\x1bOP',
            0x71: b'\x1bOQ',
            0x72: b'\x1bOR',
            0x73: b'\x1bOS',
            0x74: b'\x1b[15~',
            0x75: b'\x1b[17~',
            0x76: b'\x1b[18~',
            0x77: b'\x1b[19~',
            0x78: b'\x1b[20~',
            0x79: b'\x1b[21~',
            0x7A: b'\x1b[23~',
            0x7B: b'\x1b[24~',
        }

        if vk in VT_MAP:
            return VT_MAP[vk]

        if ctrl_pressed and 0x41 <= vk <= 0x5A:
            return bytes([vk - 0x40])

        if vk == VK_TAB:
            return b'\t'
        if vk == VK_RETURN:
            return b'\r'
        if vk == VK_BACK:
            return b'\x7f'
        if vk == VK_ESCAPE:
            return b'\x1b'

        if char and char.isprintable():
            return char.encode('utf-8')

        return None

    def get_state_label(self) -> str:
        labels = {
            InputState.NORMAL: "",
            InputState.PREFIX: "[Ctrl+A-]",
            InputState.RENAME: "[RENAME]",
            InputState.WINDOW_SELECT: "[SELECT]",
        }
        return labels.get(self.state, "")
