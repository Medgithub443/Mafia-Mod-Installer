"""Распознаватель мода: карта структуры игры + достраивание до 0-го уровня.

Карта игры (assets/game_map.json, строится tools/build_game_map.py по
распакованной Mafia) хранит:
  • level0 — имена элементов корня игры (game.exe, sounds, maps, …) в
    нижнем регистре — «нулевой уровень»;
  • parents — для каждого элемента глубже корня: имя (нижний регистр) →
    список относительных папок, где он встречается (00_build.wav →
    ["sounds"], freeride → ["missions"]).

Мод считался «корнем игры», только если его файлы лежат сразу в корне.
Моды вида drug_shipment_mod предлагают копировать FREERIDE внутрь
missions/ — такой сценарий раньше не поддерживался. Распознаватель
достраивает структуру мода до 0-го уровня: для каждого элемента верхнего
уровня, который НЕ является элементом корня игры, но встречается в карте
ровно в одной родительской папке, создаётся эта папка внутри мода
(FREERIDE → missions/FREERIDE). Неоднозначные и нераспознанные элементы
не трогаются — они попадают в предупреждение траблшутера.
"""

import json
import os
import shutil

from mmi_paths import res_path, DATA
from mmi_utils import is_readme_filename

# Документы и установщики никогда не переносим и не ругаемся на них:
# readme/инструкции лежат где угодно, .exe траблшутер помечает отдельно.
_DOC_EXTS = (".txt", ".pdf", ".md", ".rtf", ".doc", ".docx",
             ".html", ".htm", ".lnk")
_INSTALLER_EXTS = (".exe", ".msi", ".bat", ".cmd", ".ps1")

_cache = None


def load_game_map() -> dict:
    """Карта игры. {} если карта недоступна — распознавание пропускается."""
    global _cache
    if _cache is not None:
        return _cache
    _cache = {}
    for cand in (res_path(os.path.join("assets", "game_map.json")),
                 os.path.join(DATA, "game_map.json")):
        if os.path.isfile(cand):
            try:
                with open(cand, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("level0"):
                    _cache = data
                    break
            except Exception:
                continue
    return _cache


def reload_game_map() -> dict:
    """Сброс кэжа (после перегенерации карты)."""
    global _cache
    _cache = None
    return load_game_map()


def detect_roots_by_map(path: str) -> list:
    """Fallback-детект корня мода по карте игры, когда классический
    detect_root_folders ничего не нашёл (например, архив вида
    «drugshipment_mod_v20/DrugShipmentMod2alpha/FREERIDE/…» — FREERIDE
    не входит в GAME_DIRS и файлов игры нет, поэтому game-like-корня нет).

    Спускаемся сквозь обёртки (уровень без файлов и ровно с одной
    подпапкой) до папки, содержащей известные игровые элементы (уровень 0
    карты или имя, привязанное к папкам игры), и принимаем её за корень.
    """
    gmap = load_game_map()
    level0 = set(gmap.get("level0", []))
    parents = gmap.get("parents", {})
    if not level0:
        return []
    cur = path
    for _ in range(8):  # защита от бесконечного спуска
        try:
            entries = os.listdir(cur)
        except OSError:
            return []
        files = [e for e in entries
                 if os.path.isfile(os.path.join(cur, e))]
        known = [e for e in entries
                 if e.lower() in level0 or e.lower() in parents]
        if known or files:
            return [cur]
        dirs = [e for e in entries if os.path.isdir(os.path.join(cur, e))]
        if len(dirs) != 1:
            return []
        cur = os.path.join(cur, dirs[0])
    return []


def recognize_mod_root(root_dir: str) -> dict:
    """План достраивания мода. Возвращает:
      {"moves": {имя: родительская папка},
       "unknown": [имена не из игры],
       "ambiguous": [имена с несколькими родителями]}.
    """
    result = {"moves": {}, "unknown": [], "ambiguous": []}
    gmap = load_game_map()
    level0 = set(gmap.get("level0", []))
    parents = gmap.get("parents", {})
    if not level0 or not os.path.isdir(root_dir):
        return result
    for name in sorted(os.listdir(root_dir)):
        key = name.lower()
        if key in level0:
            continue
        if is_readme_filename(name) or key.endswith(_DOC_EXTS) \
                or key.endswith(_INSTALLER_EXTS):
            continue
        plist = parents.get(key)
        if not plist:
            result["unknown"].append(name)
        elif len(plist) > 1:
            result["ambiguous"].append(name)
        else:
            result["moves"][name] = plist[0]
    return result


def complete_mod_root(root_dir: str) -> dict:
    """Выполняет достраивание структуры мода до 0-го уровня.

    Возвращает {"moved": ["имя → папка/имя", …],
                "unknown": […], "ambiguous": […]} — для записи в
    карточку мода и отчёта траблшутера."""
    plan = recognize_mod_root(root_dir)
    moved = []
    ambiguous = list(plan["ambiguous"])
    for name, parent in plan["moves"].items():
        src = os.path.join(root_dir, name)
        dst = os.path.join(root_dir, parent, name)
        if os.path.exists(dst):
            # Конфликт: не перезаписываем существующее.
            ambiguous.append(name)
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        moved.append(f"{name} → {parent}/{name}")
    return {"moved": moved,
            "unknown": list(plan["unknown"]),
            "ambiguous": ambiguous}


def not_game_root_items(mod: dict) -> list:
    """Элементы верхнего уровня мода, не относящиеся к корню игры
    (неизвестные + неоднозначные). Для траблшутера: сначала смотрим
    запись, сделанную при загрузке мода, иначе считаем по живой папке."""
    stored = mod.get("map_warnings")
    if isinstance(stored, dict):
        return list(stored.get("unknown") or []) + \
               list(stored.get("ambiguous") or [])
    mdir = mod.get("dir")
    if not mdir or not os.path.isdir(mdir):
        return []
    plan = recognize_mod_root(mdir)
    return plan["unknown"] + plan["ambiguous"]
