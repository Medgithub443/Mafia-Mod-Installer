"""Переводы (ru/en/cz и любые добавленные json в languages/).

Языковые пакеты ищем в двух местах:
  1. <app_dir>/languages/   — рядом с MafiaModInstaller.exe.
     Сюда пользователь может класть свои .json без пересборки.
  2. <bundle>/languages/    — bundled внутрь exe (PyInstaller _MEIPASS).

Файлы из app_dir перекрывают bundled (приоритет у пользователя)."""

import json
import locale
import os

from mmi_paths import res_path, app_dir

LANG = "en"
# ВАЖНО: эти dict-ы заменять нельзя — main.py делает `from mmi_lang import LANGS`
# и держит ссылку на этот объект. Иначе обновления не увидит.
LANGS: dict = {}
LANG_NAMES: dict = {}


def _scan_dir(lang_dir: str) -> None:
    if not os.path.isdir(lang_dir):
        return
    for fname in sorted(os.listdir(lang_dir)):
        if not fname.endswith(".json"):
            continue
        code = os.path.splitext(fname)[0]
        try:
            with open(os.path.join(lang_dir, fname), "r", encoding="utf-8") as f:
                data = json.load(f)
            LANGS[code] = data
            LANG_NAMES[code] = data.get("_lang_name", code)
        except Exception:
            continue


def load_languages() -> None:
    LANGS.clear()
    LANG_NAMES.clear()
    # Сначала bundled (из PyInstaller _MEIPASS) — будет дефолтом.
    _scan_dir(res_path("languages"))
    # Потом — папка рядом с .exe; перекрывает bundled теми же кодами.
    _scan_dir(os.path.join(app_dir(), "languages"))


def detect_lang() -> str:
    try:
        loc = (locale.getlocale()[0] or "en").lower()
        if "ru" in loc:
            return "ru"
        if "cs" in loc or "cz" in loc:
            return "cz"
        if "fr" in loc:
            return "fr"
    except Exception:
        pass
    return "en"


def set_lang(code: str) -> None:
    global LANG
    LANG = code


def tr(key: str) -> str:
    pack = LANGS.get(LANG) or LANGS.get("en") or {}
    return pack.get(key, key)
