"""Переводы (ru/en/cz и любые добавленные json в languages/).

Языковые пакеты ищем в ТРЁХ местах (в порядке применения):
  1. <bundle>/languages/    — bundled внутрь exe (PyInstaller _MEIPASS).
  2. <app_dir>/languages/   — рядом с MafiaModInstaller.exe.
  3. <data>/languages/      — user-writable, всегда доступная для записи
     (Program Files может требовать админа, а data/ создаётся под пользователя).

Файлы из (2) перекрывают (1), а из (3) — обоих. Пакеты, добавленные
через диалог «Добавить язык…», копируются именно в (3) — это исключает
проблему read-only Program Files и в проверенный путь."""

import json
import locale
import os
import shutil

from mmi_paths import res_path, app_dir, DATA

LANG = "en"
# ВАЖНО: эти dict-ы заменять нельзя — main.py делает `from mmi_lang import LANGS`
# и держит ссылку на этот объект. Иначе обновления не увидит.
LANGS: dict = {}
LANG_NAMES: dict = {}


def user_languages_dir() -> str:
    """Папка для пользовательских .json (user-writable)."""
    p = os.path.join(DATA, "languages")
    os.makedirs(p, exist_ok=True)
    return p


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
    # 1) bundled
    _scan_dir(res_path("languages"))
    # 2) рядом с .exe (для совместимости с предыдущими версиями)
    _scan_dir(os.path.join(app_dir(), "languages"))
    # 3) user-writable (data/languages/)
    _scan_dir(user_languages_dir())


def add_language_file(src_json_path: str) -> str:
    """Копирует пользовательский .json в data/languages/ и подгружает.

    Возвращает имя языка из ключа `_lang_name` (или '' если пакет некорректный).
    """
    try:
        with open(src_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise ValueError(f"Невалидный JSON: {e}")
    name = (data.get("_lang_name") or "").strip()
    if not name:
        return ""
    dst_dir = user_languages_dir()
    dst = os.path.join(dst_dir, os.path.basename(src_json_path))
    shutil.copyfile(src_json_path, dst)
    load_languages()
    return name


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
