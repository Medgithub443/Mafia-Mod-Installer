"""Instance Finder — поиск папок игры Mafia на компьютере.

Признак игры: `Game.exe` + валидная LS3DF.dll с детектируемой версией
(см. mmi_version.is_mafia_game_folder).

Режимы:
  AUTO      — сканируем C:\\Games, %USERPROFILE%\\Documents, Desktop, %ProgramFiles%
  FULL      — сканируем все локальные диски, кроме папки MMI
  SELECTIVE — пользователь выбирает один корень в проводнике

ВАЖНО: никогда не сканируем папку, где установлена сама MMI.
"""
from __future__ import annotations

import os
import string
import sys

from mmi_paths import app_dir
from mmi_version import is_mafia_game_folder


SCAN_MAX_DEPTH = 5
SKIP_DIR_NAMES = {
    "$recycle.bin", "system volume information", "windows", "winsxs",
    "drivers", "appdata", "node_modules", ".git", "__pycache__",
    "perflogs", "msocache", "recovery", "boot",
}


def _mmi_dir() -> str:
    """Папка, где установлена сама MMI (запрещено сканировать)."""
    return os.path.abspath(app_dir())


def _is_inside(path: str, parent: str) -> bool:
    try:
        path_n = os.path.abspath(path) + os.sep
        parent_n = os.path.abspath(parent) + os.sep
        return path_n.startswith(parent_n) or path_n.rstrip(os.sep) == parent_n.rstrip(os.sep)
    except Exception:
        return False


def _scan_root(root: str, results: list, on_log=lambda *_: None,
               max_depth: int = SCAN_MAX_DEPTH) -> None:
    if not root or not os.path.isdir(root):
        return
    mmi = _mmi_dir()
    base_depth = root.rstrip("/\\").count(os.sep)

    for dirpath, dirnames, _files in os.walk(root, followlinks=False):
        # depth-limit
        depth = dirpath.rstrip("/\\").count(os.sep) - base_depth
        if depth > max_depth:
            dirnames[:] = []
            continue

        # never go inside MMI
        if _is_inside(dirpath, mmi):
            dirnames[:] = []
            continue

        # фильтр служебных директорий
        dirnames[:] = [d for d in dirnames
                       if d.lower() not in SKIP_DIR_NAMES
                       and not d.startswith(".")]

        try:
            info = is_mafia_game_folder(dirpath)
        except Exception:
            info = None
        if info:
            # дубликаты по нормализованному пути
            norm = os.path.normcase(os.path.normpath(info["path"]))
            if not any(os.path.normcase(os.path.normpath(r["path"])) == norm
                       for r in results):
                results.append(info)
                on_log(f"Найдена игра: {info['path']} ({info['version']})")
            # не лезем глубже — мод-папки внутри игры
            dirnames[:] = []


def auto_scan_paths() -> list:
    """Каталоги для AUTO-режима (только существующие)."""
    candidates = []
    if sys.platform.startswith("win"):
        candidates.append("C:\\Games")
        candidates.append(os.environ.get("ProgramFiles", "C:\\Program Files"))
        candidates.append(os.environ.get("ProgramFiles(x86)",
                                         "C:\\Program Files (x86)"))
        candidates.append(os.path.join(os.path.expanduser("~"), "Documents"))
        candidates.append(os.path.join(os.path.expanduser("~"), "Desktop"))
    else:  # для разработки на других ОС
        candidates.append(os.path.expanduser("~/Games"))
        candidates.append(os.path.expanduser("~/Documents"))
        candidates.append(os.path.expanduser("~/Desktop"))
    seen = set()
    out = []
    for p in candidates:
        if p and os.path.isdir(p):
            n = os.path.normcase(os.path.normpath(p))
            if n not in seen:
                seen.add(n)
                out.append(p)
    return out


def full_scan_paths() -> list:
    """Каталоги для FULL: все буквы дисков (Windows) или /."""
    if sys.platform.startswith("win"):
        roots = []
        for letter in string.ascii_uppercase:
            p = f"{letter}:\\"
            if os.path.isdir(p):
                roots.append(p)
        return roots
    return ["/"]


def scan(mode: str, custom_path: str = "", on_log=lambda *_: None,
         abort_check=lambda: False) -> list:
    """mode: 'auto' | 'full' | 'selective'.
    Возвращает список найденных игр (dict {path, version, build, name}).
    """
    results = []
    mmi = _mmi_dir()

    if mode == "selective":
        if not custom_path:
            return results
        if _is_inside(custom_path, mmi):
            on_log("Папка установки MMI не сканируется")
            return results
        on_log(f"SELECTIVE: {custom_path}")
        _scan_root(custom_path, results, on_log)
        return results

    if mode == "auto":
        roots = auto_scan_paths()
    elif mode == "full":
        roots = full_scan_paths()
    else:
        return results

    for root in roots:
        if abort_check():
            on_log("Поиск прерван пользователем")
            break
        on_log(f"Сканирую {root}…")
        _scan_root(root, results, on_log)
    return results
