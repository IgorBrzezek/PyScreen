import random as _r
import sys as _s
import ctypes as _c

_k = _c.windll.kernel32
_h = _k.GetStdHandle(-11)
_mode = 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
_m = _c.c_uint32()
_k.GetConsoleMode(_h, _c.byref(_m))
_k.SetConsoleMode(_h, _m.value | _mode)
_s.stdout.reconfigure(encoding='utf-8')

_sentences = [
    "Cherry sunset paints the sky in violet and orange hues.",
    "Blue lagoon whispers calmly under the moonlight tonight.",
    "Green hills of Crimea hide secrets from thousands of years.",
    "Ruby lips whisper words that no one can hear.",
    "Sapphire ocean crashes against golden cliffs at dawn.",
    "Emerald eyes gaze into the pitch-black sky above.",
    "Amber lantern light reflects on the wet cobblestone.",
    "Amethyst clouds drift over a purple meadow.",
    "Turquoise water hides a coral reef full of life and color.",
    "Golden leaves dance in the autumn afternoon wind.",
]

def _demo_lines():
    for _ in range(_r.randint(3, 4)):
        t = _r.choice(_sentences)
        fg = _r.randint(16, 231)
        bg = _r.randint(16, 231)
        fmt = f"\x1b[38;5;{fg}m\x1b[48;5;{bg}m{t}\x1b[0m"
        _s.stdout.write(fmt + "\n")
    _s.stdout.write("\n")

def _show_256_fg():
    _s.stdout.write("\x1b[1m=== 256 Foreground Colors ===\x1b[0m\n")
    for i in range(256):
        _s.stdout.write(f"\x1b[38;5;{i}m{i:>3}\x1b[0m ")
        if (i + 1) % 16 == 0:
            _s.stdout.write("\n")
    _s.stdout.write("\n")

def _show_256_bg():
    _s.stdout.write("\x1b[1m=== 256 Background Colors ===\x1b[0m\n")
    for i in range(256):
        _s.stdout.write(f"\x1b[48;5;{i}m{i:>3}\x1b[0m ")
        if (i + 1) % 16 == 0:
            _s.stdout.write("\n")
    _s.stdout.write("\n")

if __name__ == "__main__":
    _demo_lines()
    _show_256_fg()
    _show_256_bg()
