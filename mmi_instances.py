"""Экземпляры игры: путь, exe, активные моды, бэкапы, история сохранений."""

import os

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
