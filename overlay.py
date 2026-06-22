import os

ESC = "\x1b"
CSI = f"{ESC}["

BOX_TL = "\u2554"
BOX_TR = "\u2557"
BOX_BL = "\u255A"
BOX_BR = "\u255D"
BOX_H  = "\u2550"
BOX_V  = "\u2551"
BOX_TITLE_L = "\u255E"
BOX_TITLE_R = "\u2561"

def _visible_len(text: str) -> int:
    import re
    ansi_re = re.compile(r'\x1b\[[0-9;]*m')
    clean = ansi_re.sub('', text)
    return len(clean)


def _fg256(color_id: int) -> str:
    return f"{CSI}38;5;{color_id}m"


def _bg256(color_id: int) -> str:
    return f"{CSI}48;5;{color_id}m"


def build_overlay_box(title: str, body_lines: list,
                      cols: int = 80, rows: int = 24,
                      footer: str = "  [Press any key]  ") -> str:
    if cols < 20:
        cols = 80
    if rows < 10:
        rows = 24

    flen = _visible_len(footer)
    tlen = _visible_len(title)

    max_w = flen
    if tlen + 4 > max_w:
        max_w = tlen + 4
    for line in body_lines:
        l = _visible_len(line)
        if l + 2 > max_w:
            max_w = l + 2

    inner = max_w + 2
    box_w = inner + 2
    if box_w > cols:
        box_w = cols
        inner = box_w - 2
    if box_w < 10:
        box_w = 10
        inner = 8

    box_h = len(body_lines) + 4
    if box_h > rows:
        box_h = rows

    sx = (cols - box_w) // 2 + 1
    sy = (rows - box_h) // 2 + 1

    buf = []

    grey_bg = _bg256(236)
    cyan_fg = _fg256(51)
    yellow_fg = _fg256(227)
    white_fg = _fg256(15)
    green_fg = _fg256(46)
    reset = f"{CSI}0m"

    title_padded = f" {title} " if title else ""

    # top: ╔══ title ══╗
    # visible width: ╔(1) + ══(2) + title_padded(tlen+2) + ══... + ╗(1) = inner+2 = box_w
    fill_count = inner - 2 - tlen - 2  # -2 for the two padding spaces around title
    if fill_count < 0:
        fill_count = 0
    ln = f"{grey_bg}{cyan_fg}"
    ln += BOX_TL + BOX_H + BOX_H
    ln += f"{yellow_fg}{title_padded}{cyan_fg}"
    for _ in range(fill_count):
        ln += BOX_H
    ln += BOX_TR
    ln += reset
    buf.append(f"{CSI}{sy};{sx}H{ln}")

    # blank separator: ║  ...  ║
    inner_spaces = " " * inner
    ln = f"{grey_bg}{cyan_fg}{BOX_V}{white_fg}{inner_spaces}{cyan_fg}{BOX_V}{reset}"
    buf.append(f"{CSI}{sy + 1};{sx}H{ln}")

    # body lines
    for b, body_line in enumerate(body_lines):
        blen = _visible_len(body_line)
        padding_right = inner - 1 - blen
        if padding_right < 0:
            padding_right = 0
        ln = f"{grey_bg}{cyan_fg}{BOX_V}{white_fg} {body_line}{' ' * padding_right}{cyan_fg}{BOX_V}{reset}"
        buf.append(f"{CSI}{sy + 2 + b};{sx}H{ln}")

    # footer
    pad_l = (inner - flen) // 2
    pad_r = inner - pad_l - flen
    if pad_r < 0:
        pad_r = 0
    ln = f"{grey_bg}{cyan_fg}{BOX_V}{green_fg}"
    ln += " " * pad_l
    ln += footer
    ln += " " * pad_r
    ln += f"{cyan_fg}{BOX_V}{reset}"
    buf.append(f"{CSI}{sy + 2 + len(body_lines)};{sx}H{ln}")

    # bottom: ╚══ ... ══╝
    ln = f"{grey_bg}{cyan_fg}"
    ln += BOX_BL
    for _ in range(inner):
        ln += BOX_H
    ln += BOX_BR
    ln += reset
    buf.append(f"{CSI}{sy + 2 + len(body_lines) + 1};{sx}H{ln}")

    return "".join(buf)


def build_help_overlay(cols: int = 80, rows: int = 24) -> str:
    help_lines = [
        "c           - new window",
        "n / p       - next / previous window",
        "k           - kill window",
        "h / ?       - this help",
        "i           - info",
        "w           - window list",
        "d           - detach",
        "a           - rename window",
        "l / r       - redraw screen",
        "0-9         - go to window N",
        "Ctrl+A      - last active window",
        "\u2191 / \u2193       - scroll buffer",
        "PgUp / PgDn - page up / page down",
    ]
    return build_overlay_box(" PyScreen - Keyboard Shortcuts ",
                            help_lines, cols, rows)


def build_window_list_overlay(windows: list, active_id: int,
                               cols: int = 80, rows: int = 24) -> str:
    body_lines = []
    for wid, wname, alive in windows:
        marker = "*" if wid == active_id else " "
        status = "" if alive else "  [dead]"
        body_lines.append(f" {wid}{marker}  {wname}{status}")
    body_lines.append("")
    return build_overlay_box(" PyScreen - Window List ",
                            body_lines, cols, rows)


def build_info_overlay(manager, cols: int = 80, rows: int = 24,
                       author: str = "", version: str = "",
                       github: str = "") -> str:
    labels = []
    values = []

    session_name = getattr(manager, 'session_name', None) or "(none)"
    labels.append("Session:")
    values.append(session_name)

    labels.append("PID:")
    values.append(str(os.getpid()))

    port = getattr(manager, 'server_port', 0)
    labels.append("Port:")
    values.append(str(port) if port else "-")

    labels.append("Windows:")
    values.append(str(len(manager.windows)))

    uptime_s = getattr(manager, 'uptime_seconds', 0)
    detach_s = getattr(manager, 'detach_seconds', 0)
    active_s = max(0, uptime_s - detach_s)

    labels.append("Active:")
    values.append(_format_duration(active_s))
    labels.append("Detached:")
    values.append(_format_duration(detach_s))
    labels.append("Total:")
    values.append(_format_duration(uptime_s))

    labels.append("Author:")
    values.append(author)
    labels.append("Version:")
    values.append(version)
    labels.append("GitHub:")
    values.append(github)

    max_label_w = max(_visible_len(l) for l in labels)
    data_col = max_label_w + 4

    body_lines = []
    for i in range(7):
        body_lines.append(f"{labels[i]:<{data_col}}{values[i]}")
    body_lines.append("")
    for i in range(7, len(labels)):
        body_lines.append(f"{labels[i]:<{data_col}}{values[i]}")
    body_lines.append("")

    return build_overlay_box(" PyScreen - Info ",
                            body_lines, cols, rows)


def _format_duration(total_seconds: int) -> str:
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
