"""
PyScreen — session.py
Session management: detach/reattach via TCP on localhost.
"""

import json
import os
import socket
import struct
import time

SESSIONS_DIR = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "PyScreen", "sessions",
)

# Protocol commands (sent as 1 byte before data)
CMD_KBD = 0x01   # Keyboard: client->server, data = pressed key (bytes)
CMD_SCR = 0x02   # Screen: server->client, data = rendered lines (str)
CMD_RST = 0x03   # Reset/resize: server->client, data = "COLSxROWS"
CMD_DET = 0x04   # Detach: client->server, no data
CMD_QUIT = 0x05  # Quit: client->server, no data
CMD_PNG = 0x06   # Ping: both sides
CMD_ACT = 0x08   # Action (e.g. new window): client->server, data = [action_type_byte] + param


def _session_path(name):
    return os.path.join(SESSIONS_DIR, f"{name}.json")


def save_session_info(name, info):
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    path = _session_path(name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False)


def load_session_info(name):
    path = _session_path(name)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def remove_session_info(name):
    path = _session_path(name)
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


def send_msg(sock, cmd: int, data: bytes = b""):
    """Send a message: 4 bytes length + 1 byte command + data."""
    header = struct.pack("!I", 1 + len(data))  # total length (cmd + data)
    sock.sendall(header + bytes([cmd]) + data)


def recv_msg(sock):
    """Receive a message: returns (cmd, data) or None on close."""
    raw_len = b""
    while len(raw_len) < 4:
        chunk = sock.recv(4 - len(raw_len))
        if not chunk:
            return None
        raw_len += chunk
    msg_len = struct.unpack("!I", raw_len)[0]
    buf = b""
    while len(buf) < msg_len:
        chunk = sock.recv(msg_len - len(buf))
        if not chunk:
            return None
        buf += chunk
    cmd = buf[0]
    data = buf[1:]
    return cmd, data


def start_server(name: str, version: str = ""):
    """Create a listening socket. Returns socket."""
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    sock.settimeout(0.5)
    port = sock.getsockname()[1]

    # Preserve existing fields (e.g. windows, encoding) if file already exists
    info = load_session_info(name) or {}
    info.update({
        "name": name,
        "app": "PyScreen",
        "version": version,
        "pid": os.getpid(),
        "port": port,
        "created": time.time(),
    })
    save_session_info(name, info)
    return sock


def connect_to_server(name: str):
    """Connect to the server. Returns socket or None."""
    info = load_session_info(name)
    if info is None:
        return None
    port = info.get("port")
    if not port:
        return None
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5.0)
    try:
        sock.connect(("127.0.0.1", port))
    except (ConnectionRefusedError, OSError):
        return None
    sock.settimeout(None)
    return sock


def list_sessions():
    """Display list of active sessions."""
    if not os.path.exists(SESSIONS_DIR):
        print("No active PyScreen sessions.")
        return

    sessions_found = False
    for fname in sorted(os.listdir(SESSIONS_DIR)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(SESSIONS_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                info = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        if not sessions_found:
            print("Active PyScreen sessions:")
            print(f"  {'Name':<20} {'PID':<10} {'Windows':<6} {'App':<10} {'Version':<10}")
            print(f"  {'-'*20} {'-'*10} {'-'*6} {'-'*10} {'-'*10}")
            sessions_found = True

        name = info.get("name", fname.replace(".json", ""))
        pid = info.get("pid", "?")
        windows = info.get("windows", "?")
        app = info.get("app", "")
        version = info.get("version", "")
        print(f"  {name:<20} {str(pid):<10} {str(windows):<6} {app:<10} {version:<10}")

    if not sessions_found:
        print("No active PyScreen sessions.")


def clean_all_sessions():
    """Remove all session files and try to kill server processes."""
    if not os.path.exists(SESSIONS_DIR):
        return

    for fname in os.listdir(SESSIONS_DIR):
        if fname.endswith(".json"):
            try:
                path = os.path.join(SESSIONS_DIR, fname)
                info = None
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        info = json.load(f)
                except Exception:
                    pass
                os.remove(path)
                if info and "pid" in info:
                    try:
                        import signal
                        os.kill(info["pid"], signal.SIGTERM)
                    except (OSError, ImportError):
                        pass
            except OSError:
                pass

    try:
        os.rmdir(SESSIONS_DIR)
    except OSError:
        pass

    import subprocess
    try:
        subprocess.run(["taskkill", "/f", "/im", "pyscreen.exe"],
                       capture_output=True, timeout=5)
    except Exception:
        pass
