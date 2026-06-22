MAX_TRANS = 512


class Lang:
    def __init__(self):
        self._entries: dict[str, str] = {}
        self._loaded = False

    def load(self, filename: str | None) -> bool:
        if not filename:
            return False
        try:
            with open(filename, "r", encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    self._entries[key.strip()] = value.strip()
            self._loaded = True
            return True
        except (FileNotFoundError, OSError):
            return False

    def tr(self, key: str, fallback: str) -> str:
        if not self._loaded:
            return fallback
        return self._entries.get(key, fallback)


_lang = Lang()


def lang_load(filename: str | None):
    _lang.load(filename)


def tr(key: str, fallback: str) -> str:
    return _lang.tr(key, fallback)
