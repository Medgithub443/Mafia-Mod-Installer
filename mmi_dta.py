# -*- coding: utf-8 -*-
"""Авто-распаковка .dta перед установкой модов.

Логика:
- DTA_MAP в исходниках dta_cli.cpp указывает, что лежит внутри каждого
  файла A*.dta (Missions, Models, Sounds, Animations, Textures, ...).
- Mafia: The City of Lost Heaven при загрузке предпочитает loose-файлы
  поверх содержимого .dta. Распаковка нужна именно поэтому: иначе мод,
  который кладёт `missions/A1mission/somefile.bin` рядом с A1.dta, может
  работать некорректно для ассетов, которых нет в моде.
- Поэтому если у мода есть, например, папка `missions/`, мы распаковываем
  A1.dta из папки игры в саму папку игры (через `-o <game_path>`) до того,
  как поверх кладём файлы мода.
"""
from __future__ import annotations

import os
import subprocess
from typing import Iterable

from mmi_paths import res_path

# Folder name (lowercase, in mod root) -> list of game .dta filenames
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
}


def cli_path() -> str:
    """Путь к dta_cli.exe (в bundled tools/)."""
    return res_path(os.path.join("tools", "dta_cli.exe"))


def is_available() -> bool:
    return os.path.isfile(cli_path())


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
    """По распакованным корням модов посчитать, какие .dta надо вынимать.
    Возвращает упорядоченный список (например: ['A1.dta', 'A2.dta'])."""
    folders = _normalize_dirs(mod_root_dirs)
    result = []
    for folder, dtas in DTA_FOLDER_MAP.items():
        if folder in folders:
            for d in dtas:
                if d not in result:
                    result.append(d)
    return result


def _dta_already_unpacked(game_path: str, folder: str) -> bool:
    """Эвристика: если в папке игры уже есть директория `folder/` и в ней
    >= 5 файлов, считаем, что распакованное содержимое уже на месте."""
    p = os.path.join(game_path, folder)
    if not os.path.isdir(p):
        return False
    count = 0
    for _root, _dirs, files in os.walk(p):
        count += len(files)
        if count >= 5:
            return True
    return False


def folders_for_dta(dta_name: str) -> list:
    """Обратная карта: какой папке мода соответствует .dta."""
    out = []
    for folder, dtas in DTA_FOLDER_MAP.items():
        if any(d.lower() == dta_name.lower() for d in dtas):
            out.append(folder)
    return out


def extract_dtas(game_path: str, dta_names: Iterable[str],
                 log=lambda *_: None, skip_if_unpacked: bool = True) -> dict:
    """Распаковать перечисленные .dta в `game_path` через dta_cli.exe.

    Возвращает {dta_name: status_str}. status: 'ok', 'missing', 'skipped',
    'failed', 'no_cli'.
    """
    results = {}
    if not is_available():
        log("dta_cli.exe не найден — авто-распаковка пропущена")
        return {d: "no_cli" for d in dta_names}

    for dta in dta_names:
        dta_full = os.path.join(game_path, dta)
        if not os.path.isfile(dta_full):
            # Регистр имени важен (a8 vs A8) — пробуем найти, игнорируя регистр
            found = None
            try:
                for fn in os.listdir(game_path):
                    if fn.lower() == dta.lower():
                        found = fn
                        break
            except OSError:
                pass
            if not found:
                results[dta] = "missing"
                log(f"  {dta}: нет в папке игры")
                continue
            dta_full = os.path.join(game_path, found)

        if skip_if_unpacked:
            folders = folders_for_dta(dta)
            if any(_dta_already_unpacked(game_path, f) for f in folders):
                results[dta] = "skipped"
                log(f"  {dta}: уже распакован")
                continue

        log(f"  {dta}: распаковка...")
        try:
            proc = subprocess.run(
                [cli_path(), "extract", dta_full, "-o", game_path, "-q"],
                capture_output=True, text=True, timeout=600,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if proc.returncode == 0:
                results[dta] = "ok"
                log(f"  {dta}: OK")
            else:
                results[dta] = "failed"
                err = (proc.stderr or proc.stdout or "").strip().splitlines()
                log(f"  {dta}: ошибка ({err[-1] if err else 'rc=' + str(proc.returncode)})")
        except Exception as e:
            results[dta] = "failed"
            log(f"  {dta}: ошибка ({e})")
    return results
