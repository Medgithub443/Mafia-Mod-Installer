# -*- coding: utf-8 -*-
"""Sound-кэш для лицензионных версий Mafia.

Контекст: в Steam/GOG-релизах Mafia 1 у Take-Two истекли музыкальные
лицензии, и из дистрибутива вырезаны треки HiT-FM и часть звуков (это
не .dta-файлы — звуки изначально лежат loose в папке `sounds/`).
Поэтому распаковка `.dta` тут не поможет — таких файлов в .dta никогда
не было. Workaround: один раз сохранить `sounds/` из ЛЮБОЙ доступной
копии игры (диск, старая инсталляция, бэкап) во внутренний кэш MMI,
а потом одной кнопкой накатывать его в любой лицензионный экземпляр.

Структура:
  <DATA>/sound_cache/
    sounds/
      ...
    cache_info.json   (метаданные: дата, размер, источник)
"""
from __future__ import annotations

import json
import os
import shutil
from typing import Callable

from mmi_paths import DATA


CACHE_ROOT = os.path.join(DATA, "sound_cache")
SOUNDS_SUBDIR = "sounds"
INFO_FILE = "cache_info.json"


def _cache_sounds_dir() -> str:
    return os.path.join(CACHE_ROOT, SOUNDS_SUBDIR)


def _info_path() -> str:
    return os.path.join(CACHE_ROOT, INFO_FILE)


def is_cached() -> bool:
    """True если в кэше есть содержимое sounds/."""
    p = _cache_sounds_dir()
    if not os.path.isdir(p):
        return False
    for _root, _dirs, files in os.walk(p):
        if files:
            return True
    return False


def cache_status() -> dict:
    """Возвращает {'cached': bool, 'files': int, 'size': int,
                   'source': str, 'date': str}."""
    out = {"cached": False, "files": 0, "size": 0, "source": "", "date": ""}
    p = _cache_sounds_dir()
    if not os.path.isdir(p):
        return out
    files = 0
    size = 0
    for root, _dirs, fnames in os.walk(p):
        for fn in fnames:
            full = os.path.join(root, fn)
            try:
                size += os.path.getsize(full)
                files += 1
            except OSError:
                pass
    out["cached"] = files > 0
    out["files"] = files
    out["size"] = size
    info_p = _info_path()
    if os.path.isfile(info_p):
        try:
            with open(info_p, "r", encoding="utf-8") as f:
                meta = json.load(f)
            out["source"] = meta.get("source", "")
            out["date"] = meta.get("date", "")
        except Exception:
            pass
    return out


def _validate_source(folder: str) -> str | None:
    """Источник должен либо БЫТЬ папкой sounds (содержит файлы),
    либо СОДЕРЖАТЬ подпапку sounds/.

    Возвращает путь до sounds-папки или None.
    """
    if not folder or not os.path.isdir(folder):
        return None
    # case-insensitive lookup для sounds
    try:
        names = os.listdir(folder)
    except OSError:
        return None
    sounds_match = None
    for n in names:
        if n.lower() == "sounds":
            sounds_match = os.path.join(folder, n)
            break
    if sounds_match and os.path.isdir(sounds_match):
        return sounds_match
    # сам folder — это уже sounds?
    # эвристика: есть подпапки/файлы с типичными именами Mafia (HiT-FM, sfx)
    # или просто >5 файлов в корне с расширениями wav/ogg/mp3
    cnt = 0
    audio_exts = (".wav", ".ogg", ".mp3", ".flac")
    try:
        for fn in names:
            if fn.lower().endswith(audio_exts):
                cnt += 1
                if cnt >= 5:
                    return folder
    except OSError:
        pass
    return None


def cache_sounds_from_folder(
        source_folder: str,
        log: Callable[[str], None] = lambda *_: None) -> dict:
    """Скопировать содержимое sounds/ в кэш MMI.

    Возвращает {'ok': bool, 'files': int, 'size': int, 'error': str}.
    """
    result = {"ok": False, "files": 0, "size": 0, "error": ""}
    sounds_src = _validate_source(source_folder)
    if not sounds_src:
        result["error"] = ("В выбранной папке не найдена sounds/ "
                           "и сама папка не похожа на sounds/")
        log(result["error"])
        return result

    log(f"Источник: {sounds_src}")
    dst = _cache_sounds_dir()
    if os.path.isdir(dst):
        shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(dst, exist_ok=True)

    files = 0
    size = 0
    try:
        for root, _dirs, fnames in os.walk(sounds_src):
            rel_dir = os.path.relpath(root, sounds_src)
            target_dir = dst if rel_dir == "." else os.path.join(dst, rel_dir)
            os.makedirs(target_dir, exist_ok=True)
            for fn in fnames:
                src_full = os.path.join(root, fn)
                dst_full = os.path.join(target_dir, fn)
                shutil.copy2(src_full, dst_full)
                try:
                    size += os.path.getsize(dst_full)
                except OSError:
                    pass
                files += 1
                if files % 50 == 0:
                    log(f"  скопировано {files}…")
    except Exception as e:
        result["error"] = str(e)
        log(f"ОШИБКА: {e}")
        return result

    # метаданные
    import datetime as _dt
    info = {
        "source": source_folder,
        "date": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "files": files,
        "size": size,
    }
    try:
        with open(_info_path(), "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    result.update({"ok": True, "files": files, "size": size})
    log(f"Готово: {files} файл(а/ов), {size} байт")
    return result


def apply_sounds_cache(
        game_path: str,
        log: Callable[[str], None] = lambda *_: None,
        overwrite: bool = True) -> dict:
    """Скопировать содержимое кэша в <game_path>/sounds/.

    Возвращает {'ok': bool, 'files': int, 'error': str}.
    """
    result = {"ok": False, "files": 0, "error": ""}
    if not is_cached():
        result["error"] = "Кэш пуст — сначала закэшируйте sounds/"
        log(result["error"])
        return result
    if not game_path or not os.path.isdir(game_path):
        result["error"] = "Папка игры недоступна"
        log(result["error"])
        return result

    src = _cache_sounds_dir()
    # ищем папку sounds в игре (case-insensitive); если нет — создаём
    target = None
    for n in os.listdir(game_path):
        if n.lower() == "sounds":
            target = os.path.join(game_path, n)
            break
    if target is None:
        target = os.path.join(game_path, "sounds")
        os.makedirs(target, exist_ok=True)

    files = 0
    try:
        for root, _dirs, fnames in os.walk(src):
            rel = os.path.relpath(root, src)
            tdir = target if rel == "." else os.path.join(target, rel)
            os.makedirs(tdir, exist_ok=True)
            for fn in fnames:
                src_full = os.path.join(root, fn)
                dst_full = os.path.join(tdir, fn)
                if not overwrite and os.path.exists(dst_full):
                    continue
                shutil.copy2(src_full, dst_full)
                files += 1
                if files % 50 == 0:
                    log(f"  применено {files}…")
    except Exception as e:
        result["error"] = str(e)
        log(f"ОШИБКА: {e}")
        return result

    result.update({"ok": True, "files": files})
    log(f"Применено: {files} файл(а/ов) в {target}")
    return result


def clear_cache() -> bool:
    """Очистить кэш sounds полностью."""
    if not os.path.isdir(CACHE_ROOT):
        return False
    try:
        shutil.rmtree(CACHE_ROOT)
        return True
    except OSError:
        return False
