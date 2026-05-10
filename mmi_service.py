"""Сервис: revert all/one, поиск дубликатов, troubleshooter."""

import os

from mmi_paths import PATHS
from mmi_utils import load_json, save_json, GAME_DIRS
from mmi_instances import get_instance_paths, update_instance
from mmi_installer import hard_restore_from
from mmi_version import detect_game_version, is_rw_data_patched


# ---------------------------------------------------------
# Revert
# ---------------------------------------------------------

def revert_one_instance(instance: dict, logger) -> bool:
    """Восстанавливает одну инстанцию из её clean_backup. True/False."""
    clean = get_instance_paths(instance["id"])["clean"]
    if not os.path.isdir(clean) or not instance.get("path"):
        logger(f"Нет чистой копии для {instance['name']}")
        return False
    try:
        hard_restore_from(clean, instance["path"])
        instance["active_mods"] = []
        update_instance(instance)
        logger(f"  ✓ {instance['name']} ({instance['path']})")
        return True
    except Exception as e:
        logger(f"  ✗ {instance['name']}: {e}")
        return False


def revert_all_instances(logger) -> int:
    instances = load_json(PATHS["instances_json"], [])
    n = 0
    for inst in instances:
        if revert_one_instance(inst, logger):
            n += 1
    return n


# ---------------------------------------------------------
# Дубликаты
# ---------------------------------------------------------

def find_duplicate_mods() -> dict:
    mods = load_json(PATHS["mods_json"], [])
    by_csum = {}
    for m in mods:
        cs = m.get("checksum") or ""
        if not cs:
            continue
        by_csum.setdefault(cs, []).append(m)
    return {cs: lst for cs, lst in by_csum.items() if len(lst) > 1}


# ---------------------------------------------------------
# Troubleshooter
# ---------------------------------------------------------

SUSPICIOUS_EXTS = (".exe", ".msi", ".bat", ".cmd", ".ps1")


def _mod_root_dirs(mod: dict) -> set:
    out = set()
    for rel in mod.get("files", []):
        rel = rel.replace("\\", "/")
        head = rel.split("/", 1)[0] if "/" in rel else ""
        if head:
            out.add(head.lower())
    return out


def _mod_top_files(mod: dict) -> list:
    out = []
    for rel in mod.get("files", []):
        rel = rel.replace("\\", "/")
        if "/" not in rel:
            out.append(rel)
    return out


def analyze_mod(mod: dict, instance=None) -> dict:
    """Структурированный отчёт по моду.

    Поля issues[*]:
      'version_mismatch'      → mod_version, game_version
      'rw_data_unpatched'
      'standalone_installer'  → files
      'no_resource_dirs'
      'ok'                    → проблем не найдено
    """
    report = {"name": mod.get("name", mod["id"]), "issues": [],
              "recommendations": []}

    if instance:
        game_ver = detect_game_version(instance["path"])
        mver = (mod.get("target_version") or "").strip()
        if mver and game_ver.get("version") and mver != game_ver["version"]:
            report["issues"].append({
                "kind": "version_mismatch",
                "mod_version": mver,
                "game_version": game_ver["version"],
            })

        patched = is_rw_data_patched(instance["path"])
        if patched is False:
            report["issues"].append({"kind": "rw_data_unpatched"})

    top_files = _mod_top_files(mod)
    suspicious = [f for f in top_files
                  if f.lower().endswith(SUSPICIOUS_EXTS)]
    has_resource_dirs = any(d in GAME_DIRS for d in _mod_root_dirs(mod))

    if suspicious:
        report["issues"].append({
            "kind": "standalone_installer",
            "files": suspicious,
        })
        report["recommendations"].append(
            "Этот мод выглядит как автономный установщик. "
            "Сделайте бэкап игры и запустите установщик согласно readme.")
    elif not has_resource_dirs:
        report["issues"].append({"kind": "no_resource_dirs"})
        report["recommendations"].append(
            "В моде нет стандартных папок ресурсов (sounds, maps, models, "
            "tables и т.д.) и нет установщика. Скорее всего это не мод — "
            "удалите его из библиотеки.")

    if not report["issues"]:
        report["issues"].append({"kind": "ok"})
    return report


def troubleshoot_scope(scope: str, mod_id, instance) -> list:
    """scope='one_mod' или 'active_in_game'.
    Возвращает список отчётов analyze_mod."""
    mods = load_json(PATHS["mods_json"], [])
    by_id = {m["id"]: m for m in mods}

    if scope == "one_mod" and mod_id:
        m = by_id.get(mod_id)
        return [analyze_mod(m, instance)] if m else []

    if scope == "active_in_game" and instance:
        active = [by_id[mid] for mid in instance.get("active_mods", [])
                  if mid in by_id]
        return [analyze_mod(m, instance) for m in active]

    return []
