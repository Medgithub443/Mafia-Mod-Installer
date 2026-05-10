"""Установка модов в игру, откат, очистка ресурсов, патч rw_data.dll."""

import os
import shutil

from mmi_paths import PATHS, DEFAULT_PRIORITY, res_path
from mmi_utils import load_json, safe_copy, is_readme_path
from mmi_instances import get_instance_paths, update_instance
from mmi_lang import tr


DTA_MAP = {
    "a0.dta": "sounds", "a1.dta": "missions", "a2.dta": "models",
    "a3.dta": "animations", "a4.dta": "anims", "a5.dta": "maps",
    "a6.dta": "textures", "a7.dta": "records", "a8.dta": "patch",
    "a9.dta": "system", "aa.dta": "tables", "ab.dta": "music",
    "ac.dta": "animations3",
}
CLEANUP_FOLDERS = ["anims", "animations", "maps", "models", "sounds",
                   "tables", "missions", "music", "textures", "records"]


def cleanup_resources(game_path: str, logger) -> None:
    removed = []
    for dta, folder in DTA_MAP.items():
        if os.path.exists(os.path.join(game_path, dta)):
            folder_path = os.path.join(game_path, folder)
            if os.path.isdir(folder_path):
                try:
                    shutil.rmtree(folder_path)
                    removed.append(folder)
                except Exception as e:
                    logger(f"Ошибка при удалении {folder}: {e}")
    for folder in CLEANUP_FOLDERS:
        folder_path = os.path.join(game_path, folder)
        if os.path.isdir(folder_path) and folder not in removed:
            try:
                shutil.rmtree(folder_path)
                removed.append(folder)
            except Exception as e:
                logger(f"Ошибка при удалении {folder}: {e}")
    logger(f"Удалены папки: {', '.join(removed) if removed else '—'}")


def hard_restore_from(backup_path: str, game_path: str) -> None:
    if not os.path.isdir(backup_path):
        raise FileNotFoundError(backup_path)
    for item in os.listdir(game_path):
        full = os.path.join(game_path, item)
        try:
            if os.path.isfile(full) or os.path.islink(full):
                os.unlink(full)
            elif os.path.isdir(full):
                shutil.rmtree(full, ignore_errors=True)
        except Exception:
            pass
    shutil.copytree(backup_path, game_path, dirs_exist_ok=True)


def _save_to_auto_backup(rel: str, clean_dir: str, auto_dir: str) -> None:
    auto_path = os.path.join(auto_dir, rel)
    if os.path.exists(auto_path):
        return
    clean_src = os.path.join(clean_dir, rel)
    if os.path.exists(clean_src):
        safe_copy(clean_src, auto_path)


def _revert_file(rel: str, game_path: str, clean_dir: str, auto_dir: str) -> None:
    target = os.path.join(game_path, rel)
    auto_src = os.path.join(auto_dir, rel)
    clean_src = os.path.join(clean_dir, rel)
    try:
        if os.path.exists(auto_src):
            safe_copy(auto_src, target)
        elif os.path.exists(clean_src):
            safe_copy(clean_src, target)
        elif os.path.exists(target):
            os.remove(target)
    except Exception:
        pass


def detect_conflicts(active_mods, logger) -> int:
    """Пишет в лог конфликты (один файл — несколько модов). Возвращает их число."""
    file_to_mods = {}
    for m in active_mods:
        for rel in m.get("files", []):
            if is_readme_path(rel):
                continue
            file_to_mods.setdefault(rel, []).append(
                m.get("name") or m["id"])
    n = 0
    for rel, owners in file_to_mods.items():
        if len(owners) > 1:
            logger(tr("mod_conflict_log").format(rel, ", ".join(owners)))
            n += 1
    return n


def install_mods_into_game(selected_mods, instance, settings, logger) -> int:
    """Откатываем файлы убираемых модов из auto_backup/clean_backup,
    потом применяем выбранные в порядке приоритета (меньше = раньше).

    README пропускаются. saves/ пропускаются если включена immutable_saves."""
    inst_paths = get_instance_paths(instance["id"])
    clean_dir = inst_paths["clean"]
    auto_dir = inst_paths["auto_backup"]
    if not os.path.isdir(clean_dir):
        raise RuntimeError("Не настроена чистая резервная копия")

    all_mods = load_json(PATHS["mods_json"], [])
    by_id = {m["id"]: m for m in all_mods}
    prev_active = set(instance.get("active_mods", []))
    new_active = {m["id"] for m in selected_mods}

    immutable = settings.get("immutable_saves", True)

    def filtered_files(mod):
        for rel in mod.get("files", []):
            rel = rel.replace("\\", "/")
            if is_readme_path(rel):
                continue
            if immutable and rel.lower().startswith(("savegame/", "saves/")):
                continue
            yield rel

    prev_files = set()
    for mid in prev_active:
        m = by_id.get(mid)
        if m:
            prev_files.update(filtered_files(m))
    new_files = set()
    for m in selected_mods:
        new_files.update(filtered_files(m))

    revert_set = prev_files - new_files
    if revert_set:
        logger("Откат изменений предыдущих модов...")
    for rel in sorted(revert_set):
        _revert_file(rel, instance["path"], clean_dir, auto_dir)

    # Кэшируем ванильные копии файлов новых модов
    for m in selected_mods:
        for rel in filtered_files(m):
            _save_to_auto_backup(rel, clean_dir, auto_dir)

    # Применяем моды в порядке приоритета (меньше = раньше)
    sorted_mods = sorted(selected_mods,
                         key=lambda m: int(m.get("priority", DEFAULT_PRIORITY)))

    additive_only = prev_active.issubset(new_active)
    written = 0
    for mod in sorted_mods:
        cur_prio = int(mod.get("priority", DEFAULT_PRIORITY))
        is_kept = additive_only and mod["id"] in prev_active
        for rel in filtered_files(mod):
            if is_kept:
                # Файл уже на диске. Перезаписываем только если другой мод
                # с большим/равным приоритетом тоже на него претендует.
                claimed_later = False
                for other in sorted_mods:
                    if other["id"] == mod["id"]:
                        continue
                    op = int(other.get("priority", DEFAULT_PRIORITY))
                    if op >= cur_prio:
                        other_rels = {r.replace("\\", "/")
                                      for r in other.get("files", [])}
                        if rel in other_rels:
                            claimed_later = True
                            break
                if not claimed_later:
                    continue
            src = os.path.join(mod["dir"], rel)
            if os.path.exists(src):
                safe_copy(src, os.path.join(instance["path"], rel))
                written += 1

    instance["active_mods"] = list(new_active)
    update_instance(instance)

    if settings.get("conflict_check"):
        detect_conflicts(selected_mods, logger)

    return written


def patch_rw_data_dll(game_path: str, logger) -> None:
    src = res_path(os.path.join("assets", "rw_data.dll"))
    if not os.path.exists(src):
        raise FileNotFoundError(src)
    dst = os.path.join(game_path, "rw_data.dll")
    safe_copy(src, dst)
    logger(f"rw_data.dll -> {dst}")
