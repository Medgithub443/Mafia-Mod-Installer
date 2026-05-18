"""Сервис: revert all/one, поиск дубликатов, troubleshooter."""

import datetime as _dt
import hashlib
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


# ---------------------------------------------------------
# Troubleshooter — текстовый отчёт
# ---------------------------------------------------------

def _file_sha256(path: str, limit_mb: int = 200) -> str:
    """SHA-256 файла. Для очень больших (>limit_mb) возвращает 'too-large'."""
    try:
        st = os.stat(path)
    except OSError:
        return "missing"
    if st.st_size > limit_mb * 1024 * 1024:
        return "too-large"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _tree_lines(root: str, max_files: int = 5000) -> list:
    """Список строк tree-like: relative_path, size, mtime."""
    out = []
    if not root or not os.path.isdir(root):
        out.append(f"  (нет директории: {root})")
        return out
    n = 0
    for dirpath, dirnames, files in os.walk(root):
        dirnames.sort()
        for fn in sorted(files):
            full = os.path.join(dirpath, fn)
            try:
                st = os.stat(full)
                size = st.st_size
                mtime = _dt.datetime.fromtimestamp(st.st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S")
            except OSError:
                size = -1
                mtime = "?"
            rel = os.path.relpath(full, root).replace("\\", "/")
            out.append(f"  {rel}  ({size} bytes, {mtime})")
            n += 1
            if n >= max_files:
                out.append(f"  ... (truncated at {max_files} files)")
                return out
    out.append(f"  (всего файлов: {n})")
    return out


def _mod_checksum(mod: dict) -> str:
    """Возвращает уже сохранённый checksum мода (если есть) или вычисляет
    sha256 по конкатенации rel+size всех файлов."""
    cs = (mod.get("checksum") or "").strip()
    if cs:
        return cs
    mdir = mod.get("dir")
    if not mdir or not os.path.isdir(mdir):
        return "unknown"
    h = hashlib.sha256()
    for rel in sorted(mod.get("files", [])):
        h.update(rel.encode("utf-8", "replace"))
        full = os.path.join(mdir, rel)
        try:
            h.update(str(os.stat(full).st_size).encode("ascii"))
        except OSError:
            h.update(b"missing")
    return h.hexdigest()


def _mod_block(mod: dict) -> list:
    lines = []
    name = mod.get("name") or mod["id"]
    lines.append(f"Мод: {name} (id={mod['id']})")
    lines.append(f"  priority: {mod.get('priority', '?')}")
    lines.append(f"  target_version: {mod.get('target_version') or '-'}")
    lines.append(f"  checksum: {_mod_checksum(mod)}")
    mdir = mod.get("dir") or ""
    lines.append(f"  dir: {mdir}")
    lines.append("  --- file tree ---")
    lines.extend(_tree_lines(mdir))
    return lines


def build_troubleshooter_report(scope: str, mod_id, instance) -> str:
    """Полный текстовый отчёт согласно prompt v0.15:
        1. Результаты проверок
        1.1. Версия игры и состояние rw_data.dll
        2. Tree файлов игры + SHA Game.exe и rw_data.dll
        3. Tree файлов мода (one_mod) или активных модов (active_in_game)
        4. Tree остальных модов (только для active_in_game)
    """
    reports = troubleshoot_scope(scope, mod_id, instance)
    mods_all = load_json(PATHS["mods_json"], [])
    by_id = {m["id"]: m for m in mods_all}
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []
    lines.append("=" * 70)
    lines.append("MAFIA MOD INSTALLER — отчёт средства устранения неполадок")
    lines.append(f"Сгенерировано: {now}")
    lines.append(f"Область проверки: {scope}")
    if instance:
        lines.append(f"Экземпляр игры: {instance.get('name', '?')}  "
                     f"({instance.get('path', '')})")
    lines.append("=" * 70)

    # 1 — результаты проверок
    lines.append("\n1. РЕЗУЛЬТАТЫ ПРОВЕРОК")
    lines.append("-" * 70)
    if not reports:
        lines.append("(нет данных — выбрана пустая область)")
    for r in reports:
        lines.append(f"\n• {r['name']}")
        for issue in r["issues"]:
            k = issue.get("kind")
            if k == "ok":
                lines.append("  ✓ проблем не найдено")
            elif k == "version_mismatch":
                lines.append(
                    f"  ✗ несоответствие версий: мод для "
                    f"{issue['mod_version']}, игра {issue['game_version']}")
            elif k == "rw_data_unpatched":
                lines.append("  ✗ rw_data.dll не запатчен (>4 ГБ адресации)")
            elif k == "standalone_installer":
                lines.append(
                    f"  ✗ автономный установщик: {', '.join(issue['files'])}")
            elif k == "no_resource_dirs":
                lines.append("  ✗ нет стандартных папок ресурсов")
        for rec in r.get("recommendations", []):
            lines.append(f"    → {rec}")

    # 1.1 — версия игры + rw_data
    lines.append("\n1.1. ВЕРСИЯ ИГРЫ И СОСТОЯНИЕ rw_data.dll")
    lines.append("-" * 70)
    if instance and instance.get("path"):
        info = detect_game_version(instance["path"])
        ver = info.get("version") or "не определена"
        build = info.get("build")
        dll_sz = info.get("dll_size", 0)
        lines.append(f"  Версия игры (по LS3DF.dll): {ver}"
                     + (f" (build {build})" if build else ""))
        lines.append(f"  LS3DF.dll size: {dll_sz} bytes")
        patched = is_rw_data_patched(instance["path"])
        rw_state = ("запатчен" if patched is True
                    else "ванильный" if patched is False
                    else "неизвестно")
        lines.append(f"  rw_data.dll: {rw_state}")
    else:
        lines.append("  (экземпляр игры не выбран)")

    # 2 — tree игры + SHA exe / dll
    lines.append("\n2. ФАЙЛЫ ЭКЗЕМПЛЯРА ИГРЫ")
    lines.append("-" * 70)
    if instance and instance.get("path"):
        gp = instance["path"]
        exe = os.path.join(gp, "Game.exe")
        rwd = os.path.join(gp, "rw_data.dll")
        lines.append(f"  SHA-256(Game.exe):    {_file_sha256(exe)}")
        lines.append(f"  SHA-256(rw_data.dll): {_file_sha256(rwd)}")
        lines.append("  --- file tree ---")
        lines.extend(_tree_lines(gp))
    else:
        lines.append("  (экземпляр игры не выбран)")

    # 3 / 4 — моды
    if scope == "one_mod" and mod_id and mod_id in by_id:
        lines.append("\n3. ФАЙЛЫ МОДА")
        lines.append("-" * 70)
        lines.extend(_mod_block(by_id[mod_id]))
    elif scope == "active_in_game" and instance:
        active_ids = [mid for mid in (instance.get("active_mods") or [])
                      if mid in by_id]
        if active_ids:
            lines.append("\n3. ФАЙЛЫ АКТИВНОГО МОДА")
            lines.append("-" * 70)
            lines.extend(_mod_block(by_id[active_ids[0]]))
            if len(active_ids) > 1:
                lines.append("\n4. ФАЙЛЫ ОСТАЛЬНЫХ АКТИВНЫХ МОДОВ")
                lines.append("-" * 70)
                for mid in active_ids[1:]:
                    lines.extend(_mod_block(by_id[mid]))
                    lines.append("")
        else:
            lines.append("\n3. ФАЙЛЫ МОДОВ")
            lines.append("-" * 70)
            lines.append("  (активных модов нет)")

    lines.append("\n" + "=" * 70)
    lines.append("Конец отчёта.")
    return "\n".join(lines)
