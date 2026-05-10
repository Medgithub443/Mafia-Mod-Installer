"""Бэкап и восстановление папки savegame/ с историей.

Папка сохранений в Mafia называется savegame/ (в более ранней версии
программы я ошибочно использовал saves/). На случай старых установок
игр пробуем оба имени, при чтении предпочитаем savegame/.

В метаданные авто-бэкапа теперь записывается список активных модов
на момент бэкапа — потом видно, под какую конфигурацию был сейв."""

import os
import shutil

from mmi_paths import PATHS
from mmi_utils import now, now_compact, load_json
from mmi_instances import get_instance_paths, update_instance


# Имена папок сохранений в порядке предпочтения
SAVES_DIR_NAMES = ("savegame", "saves")


def saves_folder(instance: dict) -> str:
    """Возвращает путь к актуальной папке сохранений (в первую очередь
    savegame/). Если ничего не существует — путь к savegame/ (для записи)."""
    base = instance["path"]
    for name in SAVES_DIR_NAMES:
        cand = os.path.join(base, name)
        if os.path.isdir(cand):
            return cand
    return os.path.join(base, SAVES_DIR_NAMES[0])


def _active_mods_snapshot(instance: dict) -> list:
    """Список объектов {id, name, priority} активных модов экземпляра —
    встраивается в метаданные бэкапа."""
    active_ids = set(instance.get("active_mods", []))
    if not active_ids:
        return []
    all_mods = load_json(PATHS["mods_json"], [])
    out = []
    for m in all_mods:
        if m["id"] in active_ids:
            out.append({
                "id": m["id"],
                "name": m.get("name", m["id"]),
                "priority": m.get("priority", 2),
            })
    return out


def make_saves_backup(instance: dict, type_: str = "manual",
                      label: str = "") -> str:
    """Создаёт бэкап папки savegame/. Тихо возвращает '' если её нет."""
    inst_paths = get_instance_paths(instance["id"])
    src = saves_folder(instance)
    if not os.path.isdir(src):
        return ""
    sid = now_compact() + ("_auto" if type_ == "auto" else "_manual")
    dst_root = os.path.join(inst_paths["saves_history"], sid)
    if os.path.isdir(dst_root):
        shutil.rmtree(dst_root, ignore_errors=True)
    shutil.copytree(src, dst_root)
    instance.setdefault("saves", []).append({
        "id": sid,
        "date": now(),
        "type": type_,
        "label": label,
        "active_mods": _active_mods_snapshot(instance),
    })
    update_instance(instance)
    return sid


def restore_saves_backup(instance: dict, save_id: str) -> None:
    inst_paths = get_instance_paths(instance["id"])
    src = os.path.join(inst_paths["saves_history"], save_id)
    if not os.path.isdir(src):
        raise FileNotFoundError(src)
    dst = saves_folder(instance)
    # На всякий случай удалим старую savegame/ если она есть
    if os.path.isdir(dst):
        shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(instance["path"], exist_ok=True)
    shutil.copytree(src, dst)


def delete_saves_backup(instance: dict, save_id: str) -> None:
    inst_paths = get_instance_paths(instance["id"])
    src = os.path.join(inst_paths["saves_history"], save_id)
    if os.path.isdir(src):
        shutil.rmtree(src, ignore_errors=True)
    instance["saves"] = [s for s in instance.get("saves", [])
                         if s.get("id") != save_id]
    update_instance(instance)


def delete_saves_backups(instance: dict, save_ids: list) -> None:
    """Удаляет несколько бэкапов разом (для multi-select в UI)."""
    inst_paths = get_instance_paths(instance["id"])
    for sid in save_ids:
        src = os.path.join(inst_paths["saves_history"], sid)
        if os.path.isdir(src):
            shutil.rmtree(src, ignore_errors=True)
    sset = set(save_ids)
    instance["saves"] = [s for s in instance.get("saves", [])
                         if s.get("id") not in sset]
    update_instance(instance)
