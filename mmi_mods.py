"""Глобальная библиотека модов: загрузка, удаление, переименование,
сборка и распаковка .mmi-пакетов."""

import json
import os
import shutil
import tempfile
import zipfile

try:
    import patoolib
    PATOOL_AVAILABLE = True
except ImportError:
    PATOOL_AVAILABLE = False

from mmi_paths import (PATHS, APP_VERSION, DEFAULT_PRIORITY, MMI_README_LIMIT)
from mmi_utils import (load_json, save_json, slugify, sha256_dir, now,
                       detect_root_folders, is_readme_path, find_readmes)
from mmi_version import guess_target_version_from_readmes


# ---------------------------------------------------------
# Распаковка
# ---------------------------------------------------------

def extract_archive(archive_path: str, extract_to: str) -> bool:
    ext = os.path.splitext(archive_path)[1].lower()
    if ext in (".zip", ".mmi"):
        with zipfile.ZipFile(archive_path) as z:
            z.extractall(extract_to)
        return True
    if PATOOL_AVAILABLE:
        try:
            patoolib.extract_archive(archive_path, outdir=extract_to,
                                     verbosity=-1)
            return True
        except Exception:
            return False
    return False


# ---------------------------------------------------------
# .mmi build / import
# ---------------------------------------------------------

def build_mmi(mods_to_pack, output_path: str, mmi_readme: str = "") -> None:
    """Собрать .mmi из выбранных модов. Без сжатия для скорости."""
    manifest = {"version": APP_VERSION,
                "mmi_readme": mmi_readme[:MMI_README_LIMIT],
                "mods": []}
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_STORED) as out:
        for mod in mods_to_pack:
            mod_dir = mod.get("dir")
            if not mod_dir or not os.path.isdir(mod_dir):
                continue
            inner_name = f"{mod['id']}.zip"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            tmp.close()
            try:
                with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_STORED) as zin:
                    for root, _, files in os.walk(mod_dir):
                        for f in files:
                            full = os.path.join(root, f)
                            rel = os.path.relpath(full, mod_dir)
                            zin.write(full, rel)
                out.write(tmp.name, inner_name)
                manifest["mods"].append({
                    "id": mod["id"],
                    "alias": mod.get("name", ""),
                    "name": mod.get("name", ""),
                    "priority": int(mod.get("priority", DEFAULT_PRIORITY)),
                    "target_version": mod.get("target_version", "") or "",
                    "checksum": mod.get("checksum", ""),
                    "archive": inner_name,
                })
            finally:
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass
        out.writestr("manifest.json",
                     json.dumps(manifest, indent=2, ensure_ascii=False))


# ---------------------------------------------------------
# Library CRUD
# ---------------------------------------------------------

def _new_mod_id(display_name: str) -> str:
    base = slugify(display_name)
    existing = {m["id"] for m in load_json(PATHS["mods_json"], [])}
    cand = base
    i = 2
    while cand in existing or os.path.exists(os.path.join(PATHS["mods_dir"], cand)):
        cand = f"{base}_{i}"
        i += 1
    return cand


def add_mod_to_library(source_path: str, name: str = None,
                       priority: int = DEFAULT_PRIORITY,
                       target_version: str = None,
                       autodetect_target_version: bool = False) -> tuple:
    """Загружает мод из архива/папки в библиотеку.

    Поведение:
    - .mmi с manifest — обрабатывает каждый внутренний zip отдельным модом,
      берёт priority/target_version из манифеста.
    - архив или папка с НЕСКОЛЬКИМИ корнями (mod/ver1/, mod/ver2/, …) —
      каждый корень становится отдельным модом, в название добавляется
      имя родительской папки.
    - один корень — обычная загрузка.

    Если target_version не передан, пытаемся вытащить его из README мода.

    Возвращает (added_ids: list, mmi_readme_text: str)."""
    if not os.path.exists(source_path):
        raise FileNotFoundError(source_path)

    base_label = os.path.basename(source_path).rsplit(".", 1)[0]

    # --- .mmi packaging ---
    if os.path.isfile(source_path) and source_path.lower().endswith(".mmi"):
        try:
            with zipfile.ZipFile(source_path) as z:
                names = z.namelist()
                if "manifest.json" in names:
                    manifest = json.loads(z.read("manifest.json").decode("utf-8"))
                    mmi_readme = manifest.get("mmi_readme", "") or ""
                    added = []
                    for entry in manifest.get("mods", []):
                        inner = entry.get("archive")
                        if not inner or inner not in names:
                            continue
                        with tempfile.TemporaryDirectory() as tmp:
                            tmp_zip = os.path.join(tmp, inner)
                            with open(tmp_zip, "wb") as fout:
                                fout.write(z.read(inner))
                            display = (entry.get("alias")
                                       or entry.get("name")
                                       or os.path.splitext(inner)[0])
                            mp = int(entry.get("priority", DEFAULT_PRIORITY)
                                     or DEFAULT_PRIORITY)
                            tv = entry.get("target_version") or None
                            sub_ids, _ = _ingest_source(
                                tmp_zip, display, priority=mp,
                                mmi_readme=mmi_readme,
                                target_version=tv,
                                autodetect_target_version=autodetect_target_version)
                            added.extend(sub_ids)
                    return added, mmi_readme
        except zipfile.BadZipFile:
            raise

    # --- обычный архив или папка ---
    base_priority = priority
    ids, _ = _ingest_source(source_path, name or base_label,
                            priority=base_priority, mmi_readme="",
                            target_version=target_version,
                            autodetect_target_version=autodetect_target_version)
    return ids, ""


def _ingest_source(source_path: str, display_name: str,
                   priority: int = DEFAULT_PRIORITY,
                   mmi_readme: str = "",
                   target_version: str = None,
                   autodetect_target_version: bool = False) -> tuple:
    """Распаковывает архив или копирует папку во временную директорию,
    ищет ВСЕ корни мода и для каждого создаёт отдельную запись в библиотеке.

    Возвращает (added_ids: list, source_target_version_used: str|None).
    """
    if os.path.isdir(source_path):
        return _ingest_from_unpacked(source_path, display_name, priority,
                                     mmi_readme, target_version,
                                     autodetect_target_version)

    with tempfile.TemporaryDirectory() as tmp:
        if not extract_archive(source_path, tmp):
            raise RuntimeError("Не удалось распаковать архив")
        return _ingest_from_unpacked(tmp, display_name, priority,
                                     mmi_readme, target_version,
                                     autodetect_target_version)


def _ingest_from_unpacked(unpacked_path: str, display_name: str,
                          priority: int, mmi_readme: str,
                          target_version: str = None,
                          autodetect_target_version: bool = False) -> tuple:
    roots = detect_root_folders(unpacked_path)
    if not roots:
        # нет ни одного game-like корня — копируем всю переданную папку,
        # пользователь сам разберётся (вероятно странный мод, troubleshooter
        # это потом подсветит)
        roots = [unpacked_path]

    added = []
    multi = len(roots) > 1
    for root in roots:
        if multi:
            # «mod/ver1» → "mod ver1"
            sub_label = os.path.basename(root.rstrip(os.sep))
            mod_name = f"{display_name} {sub_label}".strip()
        else:
            mod_name = display_name

        # Определяем target_version: явный аргумент → readme в этом корне
        # (если включена экспериментальная автодетекция).
        tv = target_version
        if not tv and autodetect_target_version:
            readmes = find_readmes(root)
            tv = guess_target_version_from_readmes(readmes)

        mid = _ingest_one_root(root, mod_name, priority, mmi_readme, tv)
        added.append(mid)
    return added, target_version


def _ingest_one_root(root_path: str, display_name: str,
                     priority: int, mmi_readme: str,
                     target_version: str = None) -> str:
    """Создаёт ОДНУ запись в библиотеке из уже определённого корня."""
    mods = load_json(PATHS["mods_json"], [])
    mod_id = _new_mod_id(display_name)
    target = os.path.join(PATHS["mods_dir"], mod_id)
    os.makedirs(target, exist_ok=True)
    shutil.copytree(root_path, target, dirs_exist_ok=True)

    files_list = []
    for root, _, files in os.walk(target):
        for f in files:
            files_list.append(
                os.path.relpath(os.path.join(root, f), target).replace("\\", "/"))

    pri = int(priority) if int(priority) >= 1 else DEFAULT_PRIORITY
    mods.append({
        "id": mod_id,
        "name": display_name,
        "priority": pri,
        "target_version": target_version or "",
        "checksum": sha256_dir(target),
        "date": now(),
        "files_count": len(files_list),
        "dir": target,
        "files": files_list,
        "mmi_readme": (mmi_readme or "")[:MMI_README_LIMIT],
    })
    save_json(PATHS["mods_json"], mods)
    return mod_id


# Совместимость: старое имя
def _ingest(source_path: str, display_name: str,
            priority: int = DEFAULT_PRIORITY,
            mmi_readme: str = "") -> str:
    ids, _ = _ingest_source(source_path, display_name, priority, mmi_readme)
    return ids[0] if ids else ""


def remove_mod_from_library(mod_id: str) -> None:
    mods = load_json(PATHS["mods_json"], [])
    new_mods, target_dir = [], None
    for m in mods:
        if m["id"] == mod_id:
            target_dir = m.get("dir")
        else:
            new_mods.append(m)
    save_json(PATHS["mods_json"], new_mods)
    if target_dir and os.path.isdir(target_dir):
        shutil.rmtree(target_dir, ignore_errors=True)
    instances = load_json(PATHS["instances_json"], [])
    for inst in instances:
        if mod_id in inst.get("active_mods", []):
            inst["active_mods"] = [x for x in inst["active_mods"] if x != mod_id]
    save_json(PATHS["instances_json"], instances)


def update_mod_field(mod_id: str, field: str, value) -> None:
    mods = load_json(PATHS["mods_json"], [])
    for m in mods:
        if m["id"] == mod_id:
            m[field] = value
    save_json(PATHS["mods_json"], mods)


def mod_has_saves(mod: dict) -> bool:
    for rel in mod.get("files", []):
        low = rel.lower().replace("\\", "/")
        if low.startswith(("savegame/", "saves/")):
            return True
    return False
