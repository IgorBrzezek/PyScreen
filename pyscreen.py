import sys
import os
import socket
import argparse
import time
import subprocess

from config import PyScreenConfig
from manager import WindowManager
from renderer import Renderer
from input_handler import InputHandler, Action, ActionType
from status_bar import StatusBar
from overlay import build_help_overlay, build_window_list_overlay, build_info_overlay
import session
import lang


SCRIPT_AUTH = "Igor Brzezek"
VERSION = "0.0.1"
SCRIPT_GITHUB = "https://github.com/IgorBrzezek"

SESSIONS_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                            "PyScreen", "sessions")

SAVED_SCREENS = {}

HELP_TEXT = """
 PyScreen \u2014 Keyboard Shortcuts (prefix: Ctrl+A)

  c         New window              n / p     Next / Prev window
  0-9       Go to window N          A         Rename window
  k         Kill window             w         Window list
  d         Detach                  l / r     Redraw screen
  h / ?     Help                    i         Info
  \"         Select window           Ctrl+A    Last window
  \u2191 / \u2193       Scroll buffer           PgUp/Dn  Page up / down

                    [Press any key]
"""


# =========================================================================
# SERVER-SIDE: headless server process
# =========================================================================

def _server_render_to_string(manager, config, renderer, status_bar, state_label):
    """Render screen to string for sending to client."""
    active = manager.get_active()
    window_list = manager.get_window_list()
    cols = renderer.cols
    usable = renderer.get_usable_rows()

    lines = []
    if active:
        buffer = active.get_buffer_with_attrs()
        for i in range(usable):
            row_data = buffer.get(i, {})
            line = renderer._render_buffer_line(row_data, cols)
            lines.append(line)
    else:
        lines = [" " * cols] * usable

    status_line = status_bar.render(
        window_list, manager.active_id, cols, state_label
    )

    sb_pos = config.statusbar_position
    if sb_pos == "top":
        result = status_line + "\r\n" + "\r\n".join(lines)
    else:
        result = "\r\n".join(lines) + "\r\n" + status_line

    return result


def _handle_server_action(conn, data, manager, config, renderer, status_bar):
    """Handle action received from client. Returns True if overlay."""
    if not data or len(data) < 1:
        return False

    atype_val = data[0]

    if atype_val == ActionType.HELP.value:
        cols, rows = renderer.get_terminal_size()
        state_label = manager.state_label
        screen_text = _server_render_to_string(manager, config, renderer, status_bar, state_label)
        overlay_text = build_help_overlay(cols, rows)
        try:
            SAVED_SCREENS[id(conn)] = screen_text
            session.send_msg(conn, session.CMD_SCR, (screen_text + overlay_text).encode("utf-8"))
        except Exception:
            pass
        return True

    if atype_val == ActionType.LIST_WINDOWS.value:
        cols, rows = renderer.get_terminal_size()
        state_label = manager.state_label
        screen_text = _server_render_to_string(manager, config, renderer, status_bar, state_label)
        window_list = manager.get_window_list()
        overlay_text = build_window_list_overlay(window_list, manager.active_id, cols, rows)
        try:
            SAVED_SCREENS[id(conn)] = screen_text
            session.send_msg(conn, session.CMD_SCR, (screen_text + overlay_text).encode("utf-8"))
        except Exception:
            pass
        return True

    if atype_val == ActionType.INFO.value:
        cols, rows = renderer.get_terminal_size()
        state_label = manager.state_label
        screen_text = _server_render_to_string(manager, config, renderer, status_bar, state_label)
        overlay_text = build_info_overlay(manager, cols, rows,
                                          author=SCRIPT_AUTH,
                                          version=VERSION,
                                          github=SCRIPT_GITHUB)
        try:
            SAVED_SCREENS[id(conn)] = screen_text
            session.send_msg(conn, session.CMD_SCR, (screen_text + overlay_text).encode("utf-8"))
        except Exception:
            pass
        return True

    if atype_val == ActionType.RESIZE.value and len(data) >= 5:
        cols = (data[1] << 8) | data[2]
        rows = (data[3] << 8) | data[4]
        usable = rows - 1 if config.statusbar_position else rows
        renderer.cols = cols
        renderer.rows = rows
        manager.resize_all(cols, usable)
        return False

    try:
        atype = ActionType(atype_val)
    except ValueError:
        return False

    action = Action(type=atype)

    if atype == ActionType.SWITCH_WINDOW and len(data) > 1:
        action.window_id = data[1]
    elif atype == ActionType.RENAME_CONFIRM and len(data) > 1:
        action.text = data[1:].decode("utf-8", errors="replace")
    elif atype == ActionType.SCROLL_UP and len(data) > 1:
        action.scroll_count = data[1]
    elif atype == ActionType.SCROLL_DOWN and len(data) > 1:
        action.scroll_count = data[1]
    elif atype == ActionType.RENAME_CHAR and len(data) > 1:
        action.text = data[1:].decode("utf-8", errors="replace")

    _execute_action(action, manager, config, renderer)
    return False


def _handle_client_action(data, manager, config, renderer):
    """Handle action from client in overlay mode."""
    if not data:
        return
    atype_val = data[0]
    try:
        atype = ActionType(atype_val)
    except ValueError:
        return

    if atype == ActionType.RESIZE and len(data) >= 5:
        cols = (data[1] << 8) | data[2]
        rows = (data[3] << 8) | data[4]
        usable = rows - 1 if config.statusbar_position else rows
        renderer.cols = cols
        renderer.rows = rows
        manager.resize_all(cols, usable)
        return

    action = Action(type=atype)

    if atype == ActionType.SWITCH_WINDOW and len(data) > 1:
        action.window_id = data[1]
    elif atype == ActionType.RENAME_CONFIRM and len(data) > 1:
        action.text = data[1:].decode("utf-8", errors="replace")
    elif atype == ActionType.SCROLL_UP and len(data) > 1:
        action.scroll_count = data[1]
    elif atype == ActionType.SCROLL_DOWN and len(data) > 1:
        action.scroll_count = data[1]

    _execute_action(action, manager, config, renderer)


def _execute_action(action, manager, config, renderer):
    """Execute action on manager (shared between server and client)."""
    atype = action.type

    if atype == ActionType.NONE:
        return

    elif atype == ActionType.PASSTHROUGH:
        active = manager.get_active()
        if active:
            active.write(action.data)

    elif atype == ActionType.NEW_WINDOW:
        cols, _ = renderer.get_terminal_size()
        usable = renderer.get_usable_rows()
        window = manager.create_window(cols=cols, rows=usable)
        if window:
            manager.switch_to(window.id)

    elif atype == ActionType.NEXT_WINDOW:
        manager.next_window()

    elif atype == ActionType.PREV_WINDOW:
        manager.prev_window()

    elif atype == ActionType.SWITCH_WINDOW:
        if action.window_id is not None:
            manager.switch_to(action.window_id)

    elif atype == ActionType.LAST_WINDOW:
        manager.switch_to_last()

    elif atype == ActionType.RENAME_START:
        manager.state_label = lang.tr("rename_label_init", "Rename: _")

    elif atype == ActionType.RENAME_CHAR:
        manager.state_label = lang.tr("rename_label", "Rename: %s_") % action.text if action.text else ""

    elif atype == ActionType.RENAME_CONFIRM:
        if action.text:
            manager.rename_window(manager.active_id, action.text)
        manager.state_label = ""

    elif atype == ActionType.RENAME_CANCEL:
        manager.state_label = ""

    elif atype == ActionType.KILL_WINDOW:
        manager.close_window(manager.active_id)

    elif atype == ActionType.RESIZE:
        cols, rows = renderer.get_terminal_size()
        usable = renderer.get_usable_rows()
        manager.resize_all(cols, usable)

    elif atype == ActionType.REDRAW:
        pass

    elif atype == ActionType.SCROLL_UP:
        active = manager.get_active()
        if active:
            active.screen.prev_page()

    elif atype == ActionType.SCROLL_DOWN:
        active = manager.get_active()
        if active:
            active.screen.next_page()


def _server_handle_client(conn, manager, config, renderer, status_bar):
    """Client control loop on the server side."""
    conn.settimeout(0.05)
    clock_update = 0
    overlay_mode = False
    force_redraw = True

    while True:
        try:
            msg = session.recv_msg(conn)
            if msg:
                cmd, data = msg
                if cmd == session.CMD_KBD:
                    if overlay_mode:
                        overlay_mode = False
                        if len(data) == 1 and data[0] in b'0123456789':
                            act_data = bytes([ActionType.SWITCH_WINDOW.value, data[0] - 0x30])
                            _handle_client_action(act_data, manager, config, renderer)
                            force_redraw = True
                        else:
                            saved = SAVED_SCREENS.pop(id(conn), None)
                            if saved:
                                active_win = manager.get_active()
                                if active_win:
                                    cx, cy = active_win.get_cursor()
                                    content_offset = 0 if config.statusbar_position == "bottom" else 1
                                    term_row = content_offset + cy + 1
                                    term_col = cx + 1
                                    saved += f"\x1b[{term_row};{term_col}H\x1b[?25h\x1b[1 q"
                                try:
                                    session.send_msg(conn, session.CMD_SCR, saved.encode("utf-8"))
                                except Exception:
                                    pass
                                force_redraw = False
                            else:
                                force_redraw = True
                    else:
                        active = manager.get_active()
                        if active:
                            active.write(data)
                elif cmd == session.CMD_DET:
                    return
                elif cmd == session.CMD_QUIT:
                    return
                elif cmd == session.CMD_ACT:
                    was_overlay = _handle_server_action(conn, data, manager, config, renderer, status_bar)
                    if was_overlay:
                        overlay_mode = True
                    else:
                        force_redraw = True
        except socket.timeout:
            pass
        except (ConnectionResetError, BrokenPipeError, OSError):
            return

        dead = manager.cleanup_dead()
        if force_redraw and dead:
            pass

        if not manager.has_windows():
            return

        now = time.time()
        active = manager.get_active()
        needs_render = (
            force_redraw
            or manager.sb_dirty
            or (active and active.is_dirty())
            or (now - clock_update >= 1.0)
        )

        if needs_render and not overlay_mode:
            state_label = manager.state_label
            screen_text = _server_render_to_string(manager, config, renderer, status_bar, state_label)
            if active:
                cx, cy = active.get_cursor()
                content_offset = 0 if config.statusbar_position == "bottom" else 1
                term_row = content_offset + cy + 1
                term_col = cx + 1
                screen_text += f"\x1b[{term_row};{term_col}H\x1b[?25h\x1b[1 q"
            try:
                session.send_msg(conn, session.CMD_SCR,
                                 screen_text.encode("utf-8"))
            except (ConnectionResetError, BrokenPipeError, OSError):
                return
            clock_update = now
            force_redraw = False
            manager.sb_dirty = False
            if active:
                active.mark_clean()


def server_main(args):
    """Server: headless process, no terminal, creates windows, listens on TCP."""
    config = PyScreenConfig()
    config.encoding = args.encoding or "utf-8"
    config.linebuf = args.linebuf
    config.load(args.config)
    if args.execute:
        config.shell_command = args.execute

    session_name = args.server or args.session
    if not session_name:
        print("Server mode requires session name (--server <name> or -S <name>)", file=sys.stderr)
        sys.exit(1)

    lang.lang_load(args.lang)

    manager = WindowManager(config)
    manager.session_name = session_name
    manager.version = VERSION

    # Server renderer (not terminal, only renders to string)
    renderer = Renderer(config)
    renderer.cols = 80
    renderer.rows = 24
    status_bar = StatusBar(config)

    # Create first window
    name = args.name or config.default_window_name
    win = manager.create_window(name, 80, 23)
    if not win:
        return

    # Start TCP server
    listener = session.start_server(session_name, version=VERSION)
    if listener is None:
        return
    manager.server_port = listener.getsockname()[1]
    manager.update_session_info()

    try:
        while manager.has_windows():
            try:
                conn, addr = listener.accept()
            except socket.timeout:
                conn = None

            if conn:
                if manager.detach_start is not None:
                    manager.total_detach_seconds += time.time() - manager.detach_start
                manager.detach_start = None
                _server_handle_client(conn, manager, config, renderer, status_bar)
                try:
                    conn.close()
                except Exception:
                    pass
                manager.detach_start = time.time()

            manager.cleanup_dead()
    except KeyboardInterrupt:
        pass
    finally:
        for wid in list(manager.windows.keys()):
            manager.close_window(wid)
        session.remove_session_info(session_name)
        listener.close()


# =========================================================================
# CLIENT-SIDE: interactive terminal UI
# =========================================================================

def client_main(session_name, args):
    """Client: connects to server, displays terminal UI."""
    config = PyScreenConfig()
    config.encoding = args.encoding or "utf-8"
    config.linebuf = args.linebuf
    config.load(args.config)
    if args.execute:
        config.shell_command = args.execute
    lang.lang_load(args.lang)

    renderer = Renderer(config)
    input_handler = InputHandler(keybinds=config.keybinds)

    # Connect to server
    attempts = 0
    while attempts < 200:
        sock = session.connect_to_server(session_name)
        if sock is not None:
            break
        time.sleep(0.05)
        attempts += 1
    else:
        print(f"PyScreen: Cannot connect to session '{session_name}'.", file=sys.stderr)
        return

    renderer.setup_terminal()
    sock.settimeout(0.05)

    # Send initial terminal size
    new_cols, new_rows = renderer.get_terminal_size()
    resize_data = bytes([ActionType.RESIZE.value,
                         new_cols >> 8, new_cols & 0xFF,
                         new_rows >> 8, new_rows & 0xFF])
    try:
        session.send_msg(sock, session.CMD_ACT, resize_data)
    except Exception:
        pass

    running = True
    last_clock = 0

    try:
        while running:
            action = input_handler.read_input(timeout_ms=30)

            if action:
                atype = action.type

                if atype == ActionType.PASSTHROUGH:
                    if action.data:
                        try:
                            session.send_msg(sock, session.CMD_KBD, action.data)
                        except (ConnectionResetError, BrokenPipeError, OSError):
                            break

                elif atype == ActionType.DETACH:
                    try:
                        session.send_msg(sock, session.CMD_DET)
                    except Exception:
                        pass
                    break

                elif atype == ActionType.RESIZE:
                    new_cols, new_rows = renderer.get_terminal_size()
                    renderer.cols, renderer.rows = new_cols, new_rows
                    resize_data = bytes([ActionType.RESIZE.value,
                                         new_cols >> 8, new_cols & 0xFF,
                                         new_rows >> 8, new_rows & 0xFF])
                    try:
                        session.send_msg(sock, session.CMD_ACT, resize_data)
                    except Exception:
                        pass

                else:
                    act_data = bytes([atype.value])
                    if atype == ActionType.SWITCH_WINDOW and action.window_id is not None:
                        act_data += bytes([action.window_id])
                    elif atype == ActionType.RENAME_CONFIRM and action.text:
                        act_data += action.text.encode("utf-8")
                    elif atype == ActionType.SCROLL_UP and action.scroll_count > 1:
                        act_data += bytes([action.scroll_count])
                    elif atype == ActionType.SCROLL_DOWN and action.scroll_count > 1:
                        act_data += bytes([action.scroll_count])
                    elif atype == ActionType.RENAME_CHAR and action.text:
                        act_data += action.text.encode("utf-8")
                    elif atype == ActionType.RENAME_START:
                        pass
                    elif atype == ActionType.RENAME_CANCEL:
                        pass
                    try:
                        session.send_msg(sock, session.CMD_ACT, act_data)
                    except (ConnectionResetError, BrokenPipeError, OSError):
                        break

            try:
                msg = session.recv_msg(sock)
                if msg is None:
                    break
                cmd, data = msg
                if cmd == session.CMD_SCR:
                    text = data.decode("utf-8", errors="replace")
                    buf = [f"{renderer.CSI}2J", f"{renderer.CSI}0m",
                           f"{renderer.CSI}1;1H", text,
                           f"{renderer.CSI}0m", f"{renderer.CSI}?25h", f"{renderer.CSI}1 q"]
                    sys.stdout.write("".join(buf))
                    sys.stdout.flush()
                elif cmd == session.CMD_RST:
                    pass
            except socket.timeout:
                pass
            except (ConnectionResetError, BrokenPipeError, OSError):
                break

            now = time.time()
            if now - last_clock >= 1.0:
                last_clock = now

    except KeyboardInterrupt:
        pass
    finally:
        try:
            renderer.restore_terminal()
        except Exception:
            pass
        try:
            sock.close()
        except Exception:
            pass


# =========================================================================
# SPAWN SERVER
# =========================================================================

def _spawn_server(session_name, args):
    """Create a server process detached from the console."""
    python_exe = sys.executable
    script = __file__

    cmd = [python_exe, script, "--server", session_name]
    if args.config:
        cmd += ["-c", args.config]
    if args.execute:
        cmd += ["-e", args.execute]
    if args.name:
        cmd += ["-n", args.name]
    if args.encoding:
        cmd += ["--encoding", args.encoding]
    if args.linebuf is not None:
        cmd += ["--linebuf", str(args.linebuf)]
    if args.lang:
        cmd += ["--lang", args.lang]

    DETACHED_PROCESS = 0x00000008
    try:
        subprocess.Popen(
            cmd,
            creationflags=DETACHED_PROCESS,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
    except Exception as e:
        print(f"PyScreen: Cannot start server: {e}", file=sys.stderr)
        sys.exit(1)


def _wait_for_server(session_name, max_attempts=100, interval=0.1):
    """Wait until the server is ready. Returns True if ready."""
    for attempt in range(max_attempts):
        time.sleep(interval)
        info = session.load_session_info(session_name)
        if info and info.get("port", 0) > 0:
            sock = session.connect_to_server(session_name)
            if sock is not None:
                sock.close()
                return True
    return False


# =========================================================================
# CLI
# =========================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        prog="pyscreen",
        description=f"PyScreen {VERSION} by {SCRIPT_AUTH} ({SCRIPT_GITHUB}) \u2014 Terminal Multiplexer for Windows (like GNU Screen)",
        epilog="Prefix: Ctrl+A. Help: Ctrl+A h"
    )
    parser.add_argument("-c", "--config", metavar="FILE",
                        help="Path to pyscreen.cfg config file")
    parser.add_argument("-e", "--execute", metavar="CMD",
                        help="Command to run in the first window")
    parser.add_argument("-n", "--name", metavar="NAME",
                        help="Name of the first window")
    parser.add_argument("--encoding", metavar="ENC", default="utf-8",
                        choices=["utf-8", "cp1250", "cp852", "cp437", "latin-1"],
                        help="Terminal encoding (default: utf-8)")
    parser.add_argument("--linebuf", metavar="N", type=int, default=256,
                        help="Scrollback buffer lines (default: 256)")
    parser.add_argument("--lang", metavar="FILE",
                        help="Path to translation .lng file")
    parser.add_argument("-S", "--session", metavar="NAME",
                        help="Session name (for detach)")
    parser.add_argument("-r", "--reattach", metavar="NAME",
                        help="Reattach to existing session")
    parser.add_argument("-ls", "--list", action="store_true", dest="list_sessions",
                        help="List active sessions")
    parser.add_argument("--version", action="version",
                        version=f"PyScreen {VERSION}")
    parser.add_argument("--CLEAN_ALL_SESSIONS", action="store_true",
                        help="Remove all sessions and kill processes")
    parser.add_argument("--server", metavar="NAME",
                        help=argparse.SUPPRESS)
    return parser.parse_args()


def main():
    args = parse_args()

    if args.CLEAN_ALL_SESSIONS:
        session.clean_all_sessions()
        return

    if args.list_sessions:
        session.list_sessions()
        return

    # Server mode (internal, called by _spawn_server)
    if args.server:
        server_main(args)
        return

    # Reattach mode
    if args.reattach:
        client_main(args.reattach, args)
        return

    # Normal start: generate session name, start server, connect as client
    session_name = args.session or time.strftime("WinScr_%Y%m%d_%H%M%S")

    # Check if session already exists and is alive
    info = session.load_session_info(session_name)
    if info and info.get("port", 0) > 0:
        sock = session.connect_to_server(session_name)
        if sock is not None:
            sock.close()
            client_main(session_name, args)
            return
        # Dead session - remove
        session.remove_session_info(session_name)

    # Set session name in args
    args.session = session_name

    # Start server in background
    _spawn_server(session_name, args)

    # Wait for server
    if not _wait_for_server(session_name):
        print(f"PyScreen: Server did not respond for session '{session_name}'.",
              file=sys.stderr)
        sys.exit(1)

    # Connect as client
    client_main(session_name, args)


if __name__ == "__main__":
    main()
