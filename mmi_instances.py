"""Экземпляры игры: путь, exe, активные моды, бэкапы, история сохранений."""

import os
import shutil

from mmi_paths import PATHS
from mmi_utils import load_json, save_json, slugify


def _new_instance_id(path: str) -> str:
    base = slugify(os.path.basename(path.rstrip("/\\")) or "game")
    existing = {i["id"] for i in load_json(PATHS["instances_json"], [])}
    cand = base
    i = 2
    while cand in existing:
        cand = f"{base}_{i}"
        i += 1
    return cand


def get_instance_paths(inst_id: str) -> dict:
    root = os.path.join(PATHS["instances_dir"], inst_id)
    paths = {
        "root": root,
        "clean": os.path.join(root, "clean_backup"),
        "auto_backup": os.path.join(root, "auto_backup"),
        "user_backups": os.path.join(root, "user_backups"),
        "saves_history": os.path.join(root, "saves_history"),
    }
    for k in ("user_backups", "auto_backup", "saves_history"):
        os.makedirs(paths[k], exist_ok=True)
    return paths


def find_instance(instances, instance_id):
    for i in instances:
        if i["id"] == instance_id:
            return i
    return None


def upsert_instance(path: str, exe: str = "Game.exe") -> dict:
    instances = load_json(PATHS["instances_json"], [])
    for inst in instances:
        if inst.get("path") == path:
            return inst
    iid = _new_instance_id(path)
    inst = {
        "id": iid,
        "name": os.path.basename(path.rstrip("/\\")) or iid,
        "path": path,
        "exe": exe,
        "active_mods": [],
        "has_clean_backup": False,
        "saves": [],
    }
    instances.append(inst)
    save_json(PATHS["instances_json"], instances)
    return inst


def update_instance(inst: dict) -> None:
    instances = load_json(PATHS["instances_json"], [])
    for i, x in enumerate(instances):
        if x["id"] == inst["id"]:
            instances[i] = inst
            save_json(PATHS["instances_json"], instances)
            return
    instances.append(inst)
    save_json(PATHS["instances_json"], instances)


def estimate_clean_backup_size_bytes(game_path: str) -> int:
    """Грубая оценка размера clean-бэкапа: суммарный размер всех файлов
    в папке игры (бэкап — это полная копия)."""
    total = 0
    if not game_path or not os.path.isdir(game_path):
        return 0
    for dirpath, _dirs, files in os.walk(game_path):
        for f in files:
            full = os.path.join(dirpath, f)
            try:
                total += os.path.getsize(full)
            except OSError:
                pass
    return total


def forget_instance(inst_id: str) -> bool:
    """Удаляет инстанс из библиотеки + папку instances/<id>/ с метаданными.
    НЕ трогает папку самой игры."""
    instances = load_json(PATHS["instances_json"], [])
    new_list = [i for i in instances if i.get("id") != inst_id]
    if len(new_list) == len(instances):
        return False
    save_json(PATHS["instances_json"], new_list)
    root = os.path.join(PATHS["instances_dir"], inst_id)
    if os.path.isdir(root):
        try:
            shutil.rmtree(root)
        except OSError:
            pass
    return True
