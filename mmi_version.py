"""Детекция версии игры по сигнатурам в LS3DF.dll.

Порт оригинального verDetect.cpp на Python — никаких внешних зависимостей,
просто читаем DLL целиком и ищем подстроку.

Сигнатуры:
    LS3D Engine V3.95.1  → 1.2  (g_DetectedVersion 3951)
    LS3D Engine V3.93.4  → 1.1  (3934)
    LS3D Engine V3.84.5  → 1.0  (3845)

Также детектим — пропатчен ли rw_data.dll: сравниваем sha256 файла в игре
с sha256 нашего bundled assets/rw_data.dll. Совпадает ⇒ пропатчен."""

import hashlib
import os

from mmi_paths import res_path


# (string-сигнатура, человекочитаемая версия, build-id)
_SIGS = (
    (b"LS3D Engine V3.95.1", "1.2", 3951),
    (b"LS3D Engine V3.93.4", "1.1", 3934),
    (b"LS3D Engine V3.84.5", "1.0", 3845),
)


def detect_game_version(game_path: str) -> dict:
    """Возвращает {'version': '1.2'|'1.1'|'1.0'|None, 'build': int|None,
                   'dll_present': bool, 'dll_size': int|None}.

    Если DLL нет / нечитаема — version=None, dll_present=False."""
    out = {"version": None, "build": None, "dll_present": False, "dll_size": None}
    dll = os.path.join(game_path, "LS3DF.dll")
    if not os.path.isfile(dll):
        return out
    out["dll_present"] = True
    try:
        size = os.path.getsize(dll)
        out["dll_size"] = size
        # верх 20 MB — больше не читаем (как в оригинале)
        if size <= 0 or size > 20 * 1024 * 1024:
            return out
        with open(dll, "rb") as f:
            data = f.read()
    except Exception:
        return out

    for sig, ver, build in _SIGS:
        if sig in data:
            out["version"] = ver
            out["build"] = build
            return out
    return out


def is_rw_data_patched(game_path: str) -> bool | None:
    """True  — rw_data.dll в игре совпадает (по sha256) с нашим bundled.
    False — отличается (значит ванильный, нужен патч).
    None  — не найден файл в игре или bundled."""
    bundled = res_path(os.path.join("assets", "rw_data.dll"))
    target = os.path.join(game_path, "rw_data.dll")
    if not os.path.isfile(bundled) or not os.path.isfile(target):
        return None
    try:
        return _sha256(bundled) == _sha256(target)
    except Exception:
        return None


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------
# Mafia.WidescreenFix — auto-detect
# ---------------------------------------------------------

def detect_widescreen_fix(game_path: str) -> dict:
    """Возвращает {'present': bool, 'dinput8': bool, 'asi': bool, 'ini': bool}.

    Mafia.WidescreenFix кладёт:
      • dinput8.dll в корень игры
      • scripts/Mafia.WidescreenFix.asi
      • scripts/Mafia.WidescreenFix.ini
    Достаточно одновременно (a) и (b). dinput8.dll проверяем грубо
    по размеру (>500 KB) чтобы не путать с другими обёртками.
    """
    out = {"present": False, "dinput8": False, "asi": False, "ini": False}
    if not game_path or not os.path.isdir(game_path):
        return out
    di8 = os.path.join(game_path, "dinput8.dll")
    asi = os.path.join(game_path, "scripts", "Mafia.WidescreenFix.asi")
    ini = os.path.join(game_path, "scripts", "Mafia.WidescreenFix.ini")
    if os.path.isfile(di8):
        try:
            if os.path.getsize(di8) > 500 * 1024:
                out["dinput8"] = True
        except OSError:
            pass
    if os.path.isfile(asi):
        out["asi"] = True
    if os.path.isfile(ini):
        out["ini"] = True
    out["present"] = out["dinput8"] and out["asi"]
    return out


# ---------------------------------------------------------
# Mafia game folder validation (used by Instance Finder)
# ---------------------------------------------------------

def is_mafia_game_folder(folder: str) -> dict | None:
    """Если в `folder` лежит Game.exe И валидная LS3DF.dll с детектируемой
    версией — возвращает {'path', 'version', 'build', 'name'}. Иначе None."""
    if not folder or not os.path.isdir(folder):
        return None
    game_exe = os.path.join(folder, "Game.exe")
    if not os.path.isfile(game_exe):
        # case-insensitive
        try:
            names = {n.lower() for n in os.listdir(folder)}
        except OSError:
            return None
        if "game.exe" not in names:
            return None
    info = detect_game_version(folder)
    if not info.get("version"):
        return None
    return {
        "path": folder,
        "version": info["version"],
        "build": info["build"],
        "name": os.path.basename(folder.rstrip("/\\")),
    }


# ---------------------------------------------------------
# Парсинг целевой версии мода из README
# ---------------------------------------------------------

import re

_VERSION_PATTERNS = [
    # "Mafia 1.2", "Version 1.2", "v1.2", "версия 1.2", "версии 1.0",
    # "verze 1.2"; учитываем русские падежи через корень "верс".
    re.compile(r"(?:mafia|version|version[a-z]*|верс\w*|verze|verzia|wersja)"
               r"\s*[:=]?\s*v?(1\.[012])\b",
               re.IGNORECASE | re.UNICODE),
    re.compile(r"\bv\s*(1\.[012])\b", re.IGNORECASE),
    re.compile(r"(1\.[012])\s*(?:patch|update|version|верс\w*|verze)",
               re.IGNORECASE | re.UNICODE),
]


def guess_target_version_from_text(text: str) -> str | None:
    """Пытаемся найти упоминание целевой версии игры в README. Возвращаем
    '1.0' / '1.1' / '1.2' либо None."""
    if not text:
        return None
    for pat in _VERSION_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(1)
    return None


def guess_target_version_from_readmes(readmes: list) -> str | None:
    """Принимает список путей к readme-файлам, читает каждый, ищет версию."""
    for path in readmes:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                txt = f.read(200_000)  # 200KB достаточно
            v = guess_target_version_from_text(txt)
            if v:
                return v
        except Exception:
            continue
    return None
