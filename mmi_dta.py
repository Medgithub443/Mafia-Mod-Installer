# -*- coding: utf-8 -*-
"""Авто-распаковка .dta перед установкой модов.

Логика:
- DTA_MAP в исходниках dta_cli.cpp указывает, что лежит внутри каждого
  файла A*.dta (Missions, Models, Sounds, Animations, Textures, ...).
- Mafia: The City of Lost Heaven при загрузке предпочитает loose-файлы
  поверх содержимого .dta. Распаковка нужна именно поэтому: иначе мод,
  который кладёт `missions/A1mission/somefile.bin` рядом с A1.dta, может
  работать некорректно для ассетов, которых нет в моде.
- A8.dta («Patch Files») — патч-архив: обновлённые копии файлов из других
  архивов (таблицы carindex/carcyclopedia/load.def, MENU/*.mnu, ddsegment*,
  tree.klz, модели, карты). Движок отдаёт приоритет тому, что распаковано
  ПОСЛЕДНИМ, поэтому A8 обязан идти в конце очереди: иначе оригиналы затирают
  патчи (в меню свободной прогулки вместо имён машин — сырые идентификаторы,
  возможны вылеты). Порядок гарантирует dta_cli 1.1.0 (`extract-all`:
  алфавитная очередь, A8.dta последним).

Поэтому если у мода есть, например, папка `missions/`, мы распаковываем
ВСЕ .dta папки игры в саму папку игры (один вызов `extract-all`) до того,
как поверх кладём файлы мода. Повторная распаковка идемпотентна; факт
распаковки фиксируется маркером `.mmi_dta_unpacked`, чтобы последующие
установки не тратили на это время.
"""
from __future__ import annotations

import os
import subprocess
from typing import Iterable

from mmi_paths import res_path

# Folder name (lowercase, in mod root) -> list of game .dta filenames.
# Мод с такой папкой «требует» распаковки соответствующих архивов.
# "patch" приведена для полноты карты: патч-архив A8.dta dta_cli применяет
# сам и последним — отдельно указывать его в needed не нужно.
DTA_FOLDER_MAP = {
    "sounds":   ["A0.dta"],
    "missions": ["A1.dta"],
    "models":   ["A2.dta"],
    "anims":    ["A3.dta", "A4.dta", "AC.dta"],
    "maps":     ["A6.dta"],
    "records":  ["A7.dta"],
    "system":   ["A9.dta"],
    "tables":   ["AA.dta"],
    "music":    ["AB.dta"],
    "patch":    ["A8.dta"],
}

# Маркер в корне папки игры: все .dta распакованы extract-all (A8 последним).
# Хард-откат из clean_backup затирает его вместе с распакованными файлами.
UNPACKED_MARKER = ".mmi_dta_unpacked"

_version_cache = None


def cli_path() -> str:
    """Путь к dta_cli.exe (в bundled tools/)."""
    return res_path(os.path.join("tools", "dta_cli.exe"))


def is_available() -> bool:
    return os.path.isfile(cli_path())


def cli_version() -> str:
    """Версия dta_cli по выводу `dta_cli.exe version` ('' у старых сборок)."""
    global _version_cache
    if _version_cache is not None:
        return _version_cache
    _version_cache = ""
    if is_available():
        try:
            proc = subprocess.run(
                [cli_path(), "version"], capture_output=True, text=True,
                timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if proc.returncode == 0 and (proc.stdout or "").strip():
                _version_cache = (proc.stdout or "").strip().splitlines()[0]
        except Exception:
            pass
    return _version_cache


def _normalize_dirs(mod_paths: Iterable[str]) -> set:
    """Возвращает множество имён топ-уровневых директорий (lowercase)
    по всем модам из переданных распакованных каталогов."""
    out = set()
    for p in mod_paths:
        if not p or not os.path.isdir(p):
            continue
        for name in os.listdir(p):
            full = os.path.join(p, name)
            if os.path.isdir(full):
                out.add(name.lower())
    return out


def compute_dtas_for_dirs(mod_root_dirs: Iterable[str]) -> list:
    """По распакованным корням модов посчитать, какие .dta затрагивает
    установка. Возвращает упорядоченный список (например:
    ['A1.dta', 'A6.dta']). Пусто = распаковка не нужна."""
    folders = _normalize_dirs(mod_root_dirs)
    result = []
    for folder, dtas in DTA_FOLDER_MAP.items():
        if folder in folders:
            for d in dtas:
                if d not in result:
                    result.append(d)
    return result


def game_has_dtas(game_path: str) -> bool:
    """В папке игры вообще есть .dta (loose-версии игры могут быть без них)."""
    try:
        return any(f.lower().endswith(".dta")
                   for f in os.listdir(game_path))
    except OSError:
        return False


def is_fully_unpacked(game_path: str) -> bool:
    """Маркер полной распаковки на месте."""
    return os.path.isfile(os.path.join(game_path, UNPACKED_MARKER))


def extract_dtas(game_path: str, dta_names: Iterable[str],
                 log=lambda *_: None) -> dict:
    """Распаковать архивы игры в `game_path` перед установкой модов.

    dta_names — результат compute_dtas_for_dirs() (пусто → ничего не
    делаем). Фактически распаковываются ВСЕ *.dta папки игры одним вызовом
    `dta_cli extract-all` (A8.dta-патчи идут последними автоматически).
    После успеха в корне игры ставится маркер — повторные установки шаг
    пропускают.

    Возвращает {dta_name: status_str}: 'ok' | 'skipped' | 'no_dtas'
    | 'no_cli' | 'failed'.
    """
    dta_names = list(dta_names or [])
    if not dta_names:
        return {}
    if not is_available():
        log("dta_cli.exe не найден — авто-распаковка пропущена")
        return {d: "no_cli" for d in dta_names}
    if is_fully_unpacked(game_path):
        log("  .dta уже распакованы — пропуск")
        return {d: "skipped" for d in dta_names}
    if not game_has_dtas(game_path):
        # Loose-версия игры (архивы удалены) — распаковывать нечего.
        return {d: "no_dtas" for d in dta_names}

    ver = cli_version() or "dta_cli ?"
    log(f"  {ver}: распаковка всех .dta (A8.dta-патчи последними)…")
    results = {d: "failed" for d in dta_names}
    try:
        proc = subprocess.run(
            [cli_path(), "extract-all", game_path, "-o", game_path, "-q"],
            capture_output=True, text=True, timeout=1800,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if proc.returncode == 0:
            for d in results:
                results[d] = "ok"
            try:
                with open(os.path.join(game_path, UNPACKED_MARKER), "w",
                          encoding="utf-8") as f:
                    f.write(f"dta_cli {ver or ''}\n")
            except Exception:
                pass
            tail = [l for l in (proc.stderr or "").strip().splitlines() if l]
            if tail:
                log("  " + tail[-1])
        elif "no .dta files found" in (proc.stderr or "").lower():
            for d in results:
                results[d] = "no_dtas"
        else:
            err = (proc.stderr or proc.stdout or "").strip().splitlines()
            log("  ошибка extract-all: "
                + (err[-1] if err else f"rc={proc.returncode}"))
    except Exception as e:
        log(f"  ошибка: {e}")
    return results
