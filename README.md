# PyScreen — Terminal Multiplexer for Windows

**PyScreen** brings GNU Screen-like functionality to the Windows command line.
It runs inside any terminal (CMD, PowerShell, Windows Terminal) and lets you create,
manage, and switch between multiple virtual shell windows within a single console session.

Unlike simple terminal emulators, PyScreen supports **session detach and reattach**:
start a session, detach from it, close your terminal, and later reconnect from any other
terminal — your programs keep running in the background.

- **Author:** Igor Brzezek
- **Version:** 0.0.1
- **GitHub:** https://github.com/IgorBrzezek
- **Python:** 3.13.4

---

## Features

| Feature | Description |
|:---|:---|
| Multiple windows | Create any number of shell windows inside one terminal |
| Detach / Reattach | Detach a session and reattach later from any terminal |
| Window management | Switch, rename, reorder, kill windows |
| Scrollback | Scroll up/down through each window's history |
| Status bar | Customizable status bar with clock, window list, colours |
| Config file | INI-based configuration with many options |
| Language support | Translation system via `.lng` files |
| Session listing | List all active sessions with `-ls` |
| Overlay UI | Help, window list, and info displayed as overlays |
| Transparent to child processes | Programs see a real Windows console (ConPTY) |

---

## Requirements

- **Windows 10** v1809 (build 17763) or later (ConPTY support required)
- **Python 3.13+**
- Libraries: `pywinpty >= 3.0`, `pyte >= 0.8`

---

## Installation

```cmd
pip install -r requirements.txt
```

Requirements file format:
```
pywinpty>=3.0
pyte>=0.8
```

---

## Usage

### Starting a new session

```cmd
python pyscreen.py
```
Starts a new PyScreen session with one window. The session is named automatically
as `PyScr_YYYYMMDD_HHMMSS`.

### Detaching and reattaching

```
Ctrl+A  d          		       Detach from the current session
python pyscreen.py -r <session_name>   Reattach to a detached session
python pyscreen.py -ls                 List all active sessions
```

When you detach, the server continues running in the background. All your windows
and running programs stay alive. You can close your terminal and reconnect later.

### Reattaching to a session

```cmd
python pyscreen.py -r PyScr_20260101_120000
```

If the session name is omitted, you will see an error. Use `-ls` to list available sessions.

### Command-line options

```
usage: pyscreen.py [-h] [-c FILE] [-e CMD] [-n NAME] [--encoding ENC]
                   [--linebuf N] [--lang FILE] [-S NAME] [-r NAME] [-ls]
                   [--version]

PyScreen 0.0.1 by Igor Brzezek (https://github.com/IgorBrzezek)
— Terminal Multiplexer for Windows (like GNU Screen)

optional arguments:
  -h, --help            Show this help message and exit
  -c FILE, --config FILE
                        Path to pyscreen.cfg config file
  -e CMD, --execute CMD
                        Command to run in the first window
  -n NAME, --name NAME  Name of the first window
  --encoding ENC        Terminal encoding (utf-8, cp1250, cp852, cp437, latin-1)
  --linebuf N           Scrollback buffer lines (default: 256)
  --lang FILE           Path to translation .lng file
  -S NAME, --session NAME
                        Session name (for detach)
  -r NAME, --reattach NAME
                        Reattach to existing session
  -ls, --list           List active sessions
  --version             Show version
```

---

## Key bindings

All commands use the **Ctrl+A** prefix. Press Ctrl+A, release it, then press the
command key.

### Window management

| Shortcut | Action |
|:---|:---|
| `Ctrl+A` `c` | **New window** — create a new shell window |
| `Ctrl+A` `n` | **Next window** — switch to the next window |
| `Ctrl+A` `p` | **Previous window** — switch to the previous window |
| `Ctrl+A` `0-9` | **Go to window N** — switch directly to window by number |
| `Ctrl+A` `Ctrl+A` | **Toggle** — switch to the last active window |
| `Ctrl+A` `A` | **Rename** — rename current window (Enter confirms, Esc cancels) |
| `Ctrl+A` `k` | **Kill window** — close the current window |
| `Ctrl+A` `w` | **Window list** — show an overlay with all windows |

### Session control

| Shortcut | Action |
|:---|:---|
| `Ctrl+A` `d` | **Detach** — detach from session (server stays in background) |
| `Ctrl+A` `i` | **Info** — show session info overlay |
| `Ctrl+A` `?` / `h` | **Help** — show keyboard shortcut overlay |
| `Ctrl+A` `l` / `r` | **Redraw** — force a full screen redraw |

### Scrolling

| Shortcut | Action |
|:---|:---|
| `Ctrl+A` `Up` | **Scroll up** — scroll the window buffer up |
| `Ctrl+A` `Down` | **Scroll down** — scroll the window buffer down |
| `Ctrl+A` `PageUp` | **Page up** — scroll up one page |
| `Ctrl+A` `PageDown` | **Page down** — scroll down one page |

---

## Session management

PyScreen uses a **two-process architecture**:
- A **server process** (headless, no console window) manages all virtual windows,
  runs programs via ConPTY, and listens on a TCP port for client connections.
- A **client process** (your terminal) connects to the server, sends keystrokes,
  and displays the rendered screen.

### Session files

Session information is stored in `%APPDATA%\PyScreen\sessions\` as JSON files.
Each file contains:

```json
{
  "name": "PyScr_20260622_120000",
  "app": "PyScreen",
  "version": "0.0.1",
  "pid": 12345,
  "port": 54321,
  "windows": 3,
  "created": 1234567890.0
}
```

### Listing sessions

```cmd
python pyscreen.py -ls
```

Example output:
```
Active PyScreen sessions:
  Name                 PID        Windows  App        Version
  -------------------- ---------- ------ ---------- ----------
  PyScr_20260622_...   12345      1       PyScreen   0.0.1
```

### Cleaning up

```cmd
python pyscreen.py --CLEAN_ALL_SESSIONS
```

Kills all server processes and removes all session files.

---

## Configuration

PyScreen reads `pyscreen.cfg` — an INI-format file. The search order is:

1. Current directory (`.\pyscreen.cfg`)
2. Program directory (same folder as `pyscreen.py`)
3. User home directory (`%USERPROFILE%\.pyscreen.cfg`)
4. AppData directory (`%APPDATA%\PyScreen\pyscreen.cfg`)

### Example config

```ini
[statusbar]
position = bottom
background_color = 4
foreground_color = 15
active_window_fg = 14
active_window_bg = 4
inactive_window_fg = 7
inactive_window_bg = 4
window_brackets = brackets
active_symbol = *
show_clock = yes
clock_format = HH:MM:SS
clock_position = right

[shell]
command = cmd.exe
default_name = shell
```

### Config reference

#### `[statusbar]` section

| Key | Values | Default | Description |
|:---|:---|:---|:---|
| `position` | `top`, `bottom` | `bottom` | Status bar position |
| `background_color` | `0-255` | `4` (blue) | Status bar background (ANSI 256) |
| `foreground_color` | `0-255` | `15` (white) | Status bar text colour |
| `active_window_fg` | `0-255` | `14` (cyan) | Active window name foreground |
| `active_window_bg` | `0-255` | `4` (blue) | Active window name background |
| `inactive_window_fg` | `0-255` | `7` (silver) | Inactive window name foreground |
| `inactive_window_bg` | `0-255` | `4` (blue) | Inactive window name background |
| `rename_fg` | `0-255` | `11` (yellow) | Rename mode text foreground |
| `rename_bg` | `0-255` | `4` (blue) | Rename mode text background |
| `window_brackets` | `parens`, `brackets`, `angles`, `braces` | `brackets` | Bracket style: `()`, `[]`, `<>`, `{}` |
| `active_symbol` | any char | `*` | Marker for the active window |
| `show_clock` | `yes`, `no` | `no` | Show clock in the status bar |
| `clock_format` | tokens + separators | `HH:MM:SS` | Clock format tokens: `HH`, `MM`, `SS`, `DD`, `MO`, `YY`, `YYYY` |
| `clock_position` | `left`, `right` | `right` | Clock placement on the status bar |

#### `[shell]` section

| Key | Values | Default | Description |
|:---|:---|:---|:---|
| `command` | string | `cmd.exe` | Shell command for new windows |
| `default_name` | string | `shell` | Default window name |

#### `[keybinds]` section

Custom key bindings. Override defaults by specifying action=key pairs:

```ini
[keybinds]
new_window = n
next_window = Tab
```

Supported actions: `new_window`, `next_window`, `prev_window`, `switch_window`,
`last_window`, `rename_start`, `kill_window`, `list_windows`, `detach`, `help`,
`redraw`, `scroll_up`, `scroll_down`, `info`.

---

## Architecture

PyScreen uses a **two-process architecture** (server + client) communicating over
TCP on localhost.

```
┌────────────────────────────────────────────────┐
│                  SERVER PROCESS                 │
│  (headless, no console, DETACHED_PROCESS)       │
│                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │ Window 1 │ │ Window 2 │ │ Window 3 │ ...    │
│  │ (ConPTY) │ │ (ConPTY) │ │ (ConPTY) │        │
│  │ pywinpty │ │ pywinpty │ │ pywinpty │        │
│  │ + pyte   │ │ + pyte   │ │ + pyte   │        │
│  └──────────┘ └──────────┘ └──────────┘        │
│                                                 │
│  WindowManager ── StatusBar ── TCP Listener     │
└──────────────────────┬──────────────────────────┘
                       │ TCP (localhost)
┌──────────────────────┴──────────────────────────┐
│                  CLIENT PROCESS                  │
│  (your terminal)                                 │
│                                                 │
│  Renderer ── InputHandler ── TCP Connection     │
│                                                 │
│  ┌──────────────────────────────────────────┐   │
│  │          Terminal Output (VT100)         │   │
│  └──────────────────────────────────────────┘   │
└────────────────────────────────────────────────┘
```

### Components

| File | Role |
|:---|:---|
| `pyscreen.py` | Entry point, server main loop, client main loop |
| `config.py` | Parses `pyscreen.cfg` using configparser |
| `manager.py` | Manages windows, tracks active/detach state |
| `vt_window.py` | ConPTY via pywinpty + VT100 emulation via pyte |
| `renderer.py` | Renders window buffers + status bar to ANSI/VT |
| `input_handler.py` | Keyboard hook (mouse, paste, Ctrl+A prefix) |
| `status_bar.py` | Builds the status bar string |
| `overlay.py` | Builds help, window list, and info overlays |
| `session.py` | TCP session management, detach/reattach protocol |
| `lang.py` | Translation system (key=value .lng files) |
| `colors.py` | ANSI colour test patterns |

### Protocol

Client and server communicate over a simple binary protocol on a random localhost TCP port:

| Byte 0-3 | Byte 4 | Byte 5+ |
|:---|:---|:---|
| Length (4 bytes, big-endian) | Command (1 byte) | Payload |

Commands:

| Code | Name | Direction | Description |
|:---|:---|:---|:---|
| `0x01` | `CMD_KBD` | Client → Server | Keystroke data |
| `0x02` | `CMD_SCR` | Server → Client | Rendered screen content |
| `0x03` | `CMD_RST` | Server → Client | Reset/resize notification |
| `0x04` | `CMD_DET` | Client → Server | Detach request |
| `0x05` | `CMD_QUIT` | Client → Server | Quit request |
| `0x06` | `CMD_PNG` | Both | Ping |
| `0x08` | `CMD_ACT` | Client → Server | Action (new window, switch, etc.) |

---

## Development

### Running from source

```cmd
python pyscreen.py
```

For testing with a specific command:
```cmd
python pyscreen.py -e powershell.exe
```

For testing detach/reattach:
```cmd
# Terminal 1
python pyscreen.py -S mytest
# Inside: Ctrl+A d to detach
# Terminal 2
python pyscreen.py -r mytest
```

---

## Troubleshooting

| Problem | Likely cause | Fix |
|:---|:---|:---|
| "Cannot start server" | Port conflict or missing dependencies | Check `pywinpty` is installed |
| Detached session not found | Server may have crashed | Use `-ls` to check, or clean sessions |
| Window shows no output | ConPTY not supported | Windows 10 v1809+ required |
| Encoding issues | Wrong encoding setting | Try `--encoding cp1250` or `--encoding utf-8` |

---

## License

GNU GPL 3.0 