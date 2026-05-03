# =========================================================
# Mafia Mod Installer v0.11
# main.py — точка входа GUI
#
# Структура данных (всё рядом с .exe, в подпапке data/):
#   <app_dir>/
#       MafiaModInstaller.exe
#       logoMaker.exe
#       assets/   languages/
#       data/
#           config.json        — глобальная конфигурация (язык, settings)
#           mods.json          — глобальная библиотека модов
#           instances.json     — список экземпляров игры
#           mods/<mod_id>/...  — распакованные файлы модов
#           instances/<inst_id>/clean_backup
#           instances/<inst_id>/user_backups
#           logos/<hash>.avi   — кэш сгенерированных logo1.avi
#           logs.txt
# =========================================================

import os
import re
import sys
import shutil
import zipfile
import json
import datetime
import tempfile
import subprocess
import locale
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

try:
    import patoolib
    PATOOL_AVAILABLE = True
except ImportError:
    PATOOL_AVAILABLE = False

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False
    TkinterDnD = tk

APP_NAME = "Mafia Mod Installer"
APP_VERSION = "0.11"


# =========================================================
# Расположение программы и данных
# =========================================================

def app_dir() -> str:
    """Папка, где лежит .exe (или main.py в dev-режиме)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def res_path(rel: str) -> str:
    """Путь к ресурсам (assets/, languages/) — учитывает PyInstaller _MEIPASS."""
    base = getattr(sys, "_MEIPASS", app_dir())
    return os.path.join(base, rel)


DATA = os.path.join(app_dir(), "data")
os.makedirs(DATA, exist_ok=True)

PATHS = {
    "config": os.path.join(DATA, "config.json"),
    "mods_json": os.path.join(DATA, "mods.json"),
    "instances_json": os.path.join(DATA, "instances.json"),
    "mods_dir": os.path.join(DATA, "mods"),
    "instances_dir": os.path.join(DATA, "instances"),
    "logos_dir": os.path.join(DATA, "logos"),
    "log_file": os.path.join(DATA, "logs.txt"),
}
for k in ("mods_dir", "instances_dir", "logos_dir"):
    os.makedirs(PATHS[k], exist_ok=True)


# =========================================================
# DTA / папки ресурсов
# =========================================================

DTA_MAP = {
    "a0.dta": "sounds", "a1.dta": "missions", "a2.dta": "models",
    "a3.dta": "animations", "a4.dta": "anims", "a5.dta": "maps",
    "a6.dta": "textures", "a7.dta": "records", "a8.dta": "patch",
    "a9.dta": "system", "aa.dta": "tables", "ab.dta": "music",
    "ac.dta": "animations3",
}
CLEANUP_FOLDERS = ["anims", "animations", "maps", "models", "sounds",
                   "tables", "missions", "music", "textures", "records"]


# =========================================================
# Языки
# =========================================================

LANG = "en"
LANGS: dict = {}
LANG_NAMES: dict = {}


def load_languages() -> None:
    global LANGS, LANG_NAMES
    LANGS, LANG_NAMES = {}, {}
    lang_dir = res_path("languages")
    if not os.path.isdir(lang_dir):
        return
    for fname in os.listdir(lang_dir):
        if not fname.endswith(".json"):
            continue
        code = os.path.splitext(fname)[0]
        try:
            with open(os.path.join(lang_dir, fname), "r", encoding="utf-8") as f:
                data = json.load(f)
            LANGS[code] = data
            LANG_NAMES[code] = data.get("_lang_name", code)
        except Exception:
            continue


def detect_lang() -> str:
    try:
        loc = (locale.getlocale()[0] or "en").lower()
        if "ru" in loc:
            return "ru"
        if "cs" in loc or "cz" in loc:
            return "cz"
    except Exception:
        pass
    return "en"


def tr(key: str) -> str:
    pack = LANGS.get(LANG) or LANGS.get("en") or {}
    return pack.get(key, key)


# =========================================================
# JSON / FS утилиты
# =========================================================

def now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def now_compact() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json(path, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def safe_copy(src, dst) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


def append_log(text: str) -> None:
    try:
        with open(PATHS["log_file"], "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception:
        pass


def open_path(path: str) -> None:
    if not path or not os.path.exists(path):
        return
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


def slugify(name: str, max_len: int = 40) -> str:
    """Безопасное человекочитаемое имя для папки."""
    name = name.strip().lower()
    name = re.sub(r"[^\w\s\-\.]+", "", name, flags=re.UNICODE)
    name = re.sub(r"[\s\-_\.]+", "_", name).strip("_")
    return (name or "item")[:max_len]


def detect_steam_path() -> str:
    for p in (r"C:\Program Files (x86)\Steam\steamapps\common\Mafia\Mafia",
              r"C:\Program Files\Steam\steamapps\common\Mafia\Mafia"):
        if os.path.exists(p):
            return p
    return ""


# =========================================================
# README + определение корня мода
# =========================================================

GAME_DIRS = {"maps", "missions", "models", "sounds", "tables", "textures",
             "records", "animations", "anims", "music"}
GAME_EXTS = (".dta", ".exe", ".dll", ".cfg")

README_KEYWORDS = [
    "readme", "read me", "readthis", "instruction", "instructions", "guide",
    "manual", "setup", "install", "notes",
    "прочитай", "читай", "инструкция", "руководство", "установка",
    "заметки", "прочти",
    "navod", "pokyny", "prirucka", "instalace", "návod", "příručka",
    "przeczytaj", "instrukcja", "instalacja", "czytaj",
    "liesmich", "anleitung", "handbuch", "installation", "hinweise",
    "інструкція", "керівництво",
    "leggimi", "istruzioni", "manuale", "installazione",
    "olvassel", "utasitas", "kezikonyv", "telepites",
    "citeste", "instructiuni", "instalare",
    "procitaj", "uputstvo", "instalacija",
    "oku", "talimat", "kilavuz", "kurulum",
]
README_EXTS = (".txt", ".pdf", ".md", ".rtf", ".doc", ".docx", ".html", ".htm")


def is_game_like_folder(path: str) -> bool:
    try:
        entries = os.listdir(path)
        for e in entries:
            full = os.path.join(path, e)
            if os.path.isdir(full) and e.lower() in GAME_DIRS:
                return True
        for e in entries:
            full = os.path.join(path, e)
            if os.path.isfile(full) and e.lower().endswith(GAME_EXTS):
                return True
    except Exception:
        pass
    return False


def detect_root_folder(path: str) -> str:
    if is_game_like_folder(path):
        return path
    for root, dirs, _ in os.walk(path):
        depth = root.replace(path, "").count(os.sep)
        if depth > 3:
            continue
        for d in dirs:
            candidate = os.path.join(root, d)
            if is_game_like_folder(candidate):
                return candidate
    return path


def is_readme_file(file_name: str, dir_path: str) -> bool:
    lower = file_name.lower()
    if any(kw in lower for kw in README_KEYWORDS) and lower.endswith(README_EXTS):
        return True
    try:
        files = [f for f in os.listdir(dir_path)
                 if os.path.isfile(os.path.join(dir_path, f))]
        text_files = [f for f in files if f.lower().endswith(README_EXTS)]
        if len(text_files) == 1 and text_files[0] == file_name:
            return True
    except Exception:
        pass
    return False


def find_readmes(mod_dir: str):
    out = []
    if not mod_dir or not os.path.isdir(mod_dir):
        return out
    for root, _, files in os.walk(mod_dir):
        for f in files:
            if is_readme_file(f, root):
                out.append(os.path.join(root, f))
    return out


# =========================================================
# Архивы
# =========================================================

def extract_archive(archive_path: str, extract_to: str) -> bool:
    ext = os.path.splitext(archive_path)[1].lower()
    if ext in (".zip", ".mmi"):
        with zipfile.ZipFile(archive_path) as z:
            z.extractall(extract_to)
        return True
    if PATOOL_AVAILABLE:
        try:
            patoolib.extract_archive(archive_path, outdir=extract_to, verbosity=-1)
            return True
        except Exception:
            return False
    return False


def build_mmi(mods_to_pack, output_path: str) -> None:
    """Собрать .mmi (zip) из выбранных модов: каждый — внутренний zip + manifest.json."""
    manifest = {"version": APP_VERSION, "mods": []}
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as out:
        for mod in mods_to_pack:
            mod_dir = mod.get("dir")
            if not mod_dir or not os.path.isdir(mod_dir):
                continue
            inner_name = f"{mod['id']}.zip"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            tmp.close()
            try:
                with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zin:
                    for root, _, files in os.walk(mod_dir):
                        for f in files:
                            full = os.path.join(root, f)
                            rel = os.path.relpath(full, mod_dir)
                            zin.write(full, rel)
                out.write(tmp.name, inner_name)
                # alias = отображаемое название, выбранное создателем .mmi
                # (то, как мод показан в его программе). Дублируем в name
                # для обратной совместимости с v0.10 манифестом.
                manifest["mods"].append({
                    "id": mod["id"],
                    "alias": mod.get("name", ""),
                    "name": mod.get("name", ""),
                    "archive": inner_name,
                })
            finally:
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass
        out.writestr("manifest.json",
                     json.dumps(manifest, indent=2, ensure_ascii=False))


# =========================================================
# Глобальная библиотека модов
# =========================================================

def _new_mod_id(display_name: str) -> str:
    base = slugify(display_name)
    existing = {m["id"] for m in load_json(PATHS["mods_json"], [])}
    cand = base
    i = 2
    while cand in existing or os.path.exists(os.path.join(PATHS["mods_dir"], cand)):
        cand = f"{base}_{i}"
        i += 1
    return cand


def add_mod_to_library(source_path: str, name: str = None) -> list:
    """Распаковать архив или скопировать папку в data/mods/<id>/.
    Если это .mmi с manifest — обработать каждый внутренний zip отдельным модом.
    Возвращает список добавленных id."""
    if not os.path.exists(source_path):
        raise FileNotFoundError(source_path)

    base_label = os.path.basename(source_path).rsplit(".", 1)[0]

    if os.path.isfile(source_path) and source_path.lower().endswith(".mmi"):
        try:
            with zipfile.ZipFile(source_path) as z:
                names = z.namelist()
                if "manifest.json" in names:
                    manifest = json.loads(z.read("manifest.json").decode("utf-8"))
                    added = []
                    for entry in manifest.get("mods", []):
                        inner = entry.get("archive")
                        if not inner or inner not in names:
                            continue
                        with tempfile.TemporaryDirectory() as tmp:
                            tmp_zip = os.path.join(tmp, inner)
                            with open(tmp_zip, "wb") as fout:
                                fout.write(z.read(inner))
                            # При импорте используем alias (отображаемое
                            # имя, заданное автором .mmi). Падаем на name
                            # для совместимости со старыми пакетами и на
                            # имя архива в самом крайнем случае.
                            display = (entry.get("alias")
                                       or entry.get("name")
                                       or os.path.splitext(inner)[0])
                            added.append(_ingest(tmp_zip, display))
                    return added
        except zipfile.BadZipFile:
            raise

    return [_ingest(source_path, name or base_label)]


def _ingest(source_path: str, display_name: str) -> str:
    mods = load_json(PATHS["mods_json"], [])
    mod_id = _new_mod_id(display_name)
    target = os.path.join(PATHS["mods_dir"], mod_id)
    os.makedirs(target, exist_ok=True)

    if os.path.isdir(source_path):
        root = detect_root_folder(source_path)
        shutil.copytree(root, target, dirs_exist_ok=True)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            if not extract_archive(source_path, tmp):
                shutil.rmtree(target, ignore_errors=True)
                raise RuntimeError("Не удалось распаковать архив")
            root = detect_root_folder(tmp)
            shutil.copytree(root, target, dirs_exist_ok=True)

    files_list = []
    for root, _, files in os.walk(target):
        for f in files:
            files_list.append(os.path.relpath(os.path.join(root, f), target))

    mods.append({
        "id": mod_id,
        "name": display_name,
        "date": now(),
        "files_count": len(files_list),
        "dir": target,
        "files": files_list,
    })
    save_json(PATHS["mods_json"], mods)
    return mod_id


def remove_mod_from_library(mod_id: str) -> None:
    mods = load_json(PATHS["mods_json"], [])
    new_mods = []
    target_dir = None
    for m in mods:
        if m["id"] == mod_id:
            target_dir = m.get("dir")
        else:
            new_mods.append(m)
    save_json(PATHS["mods_json"], new_mods)
    if target_dir and os.path.isdir(target_dir):
        shutil.rmtree(target_dir, ignore_errors=True)
    # Снять с активных модов всех экземпляров
    instances = load_json(PATHS["instances_json"], [])
    for inst in instances:
        if mod_id in inst.get("active_mods", []):
            inst["active_mods"] = [x for x in inst["active_mods"] if x != mod_id]
    save_json(PATHS["instances_json"], instances)


def rename_mod(mod_id: str, new_name: str) -> None:
    mods = load_json(PATHS["mods_json"], [])
    for m in mods:
        if m["id"] == mod_id:
            m["name"] = new_name
    save_json(PATHS["mods_json"], mods)


# =========================================================
# Экземпляры игры
# =========================================================

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
        "user_backups": os.path.join(root, "user_backups"),
    }
    os.makedirs(paths["user_backups"], exist_ok=True)
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


# =========================================================
# Установка / восстановление
# =========================================================

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


def install_mods_into_game(selected_mods, instance, logger) -> None:
    """Точечное переключение конфигурации модов:
       1) Откатываем только те файлы, которых касались ранее активные моды
          (восстанавливаем из clean_backup, либо удаляем если файла там не было).
       2) Поверх копируем файлы новых выбранных модов.
       Никакого hard-restore — Steam-housekeeping и любые посторонние файлы
       в папке игры остаются нетронутыми. Это и фиксит регрессию со Steam-версией."""
    inst_paths = get_instance_paths(instance["id"])
    clean_dir = inst_paths["clean"]
    if not os.path.isdir(clean_dir):
        raise RuntimeError("Не настроена чистая резервная копия")

    all_mods = load_json(PATHS["mods_json"], [])
    by_id = {m["id"]: m for m in all_mods}

    prev_files = set()
    for mid in instance.get("active_mods", []):
        m = by_id.get(mid)
        if m:
            prev_files.update(m.get("files", []))

    new_files = set()
    for m in selected_mods:
        new_files.update(m.get("files", []))

    # Откатываем только то, что было модифицировано ранее
    if prev_files:
        logger("Возврат изменений предыдущих модов...")
    for rel in sorted(prev_files):
        target = os.path.join(instance["path"], rel)
        clean_src = os.path.join(clean_dir, rel)
        try:
            if os.path.exists(clean_src):
                safe_copy(clean_src, target)
            elif os.path.exists(target):
                os.remove(target)
        except Exception as e:
            logger(f"Не удалось откатить {rel}: {e}")

    # Применяем выбранные моды
    total = 0
    for mod in selected_mods:
        logger(f"Копирую: {mod.get('name', mod['id'])}")
        mod_dir = mod["dir"]
        for rel in mod.get("files", []):
            src = os.path.join(mod_dir, rel)
            if os.path.exists(src):
                safe_copy(src, os.path.join(instance["path"], rel))
                total += 1
    logger(tr("installed_files").format(total))

    instance["active_mods"] = [m["id"] for m in selected_mods]
    update_instance(instance)


def patch_rw_data_dll(game_path: str, logger) -> None:
    """Копирует bundled rw_data.dll поверх файла в папке игры."""
    src = res_path(os.path.join("assets", "rw_data.dll"))
    if not os.path.exists(src):
        raise FileNotFoundError(src)
    dst = os.path.join(game_path, "rw_data.dll")
    safe_copy(src, dst)
    logger(f"rw_data.dll -> {dst}")


# =========================================================
# Логомейкер
# =========================================================

def _logo_text(selected_mods) -> str:
    lines = ["INSTALLED MODS:"]
    if not selected_mods:
        lines.append(" (none)")
    else:
        for i, m in enumerate(selected_mods, 1):
            lines.append(f" {i}. {m.get('name') or m['id']}")
    return "\n".join(lines)


def _logo_cache_key(selected_mods) -> str:
    import hashlib
    payload = "|".join(sorted(m["id"] for m in selected_mods))
    return hashlib.md5(payload.encode("utf-8")).hexdigest()[:12]


def update_logo_in_game(selected_mods, game_path, logger) -> None:
    cache_key = _logo_cache_key(selected_mods)
    cached = os.path.join(PATHS["logos_dir"], f"{cache_key}.avi")
    template = res_path(os.path.join("assets", "logo1.avi"))
    font = res_path(os.path.join("assets", "aurorabdcnbtrusbyme_bold.otf"))

    if not os.path.exists(template):
        raise FileNotFoundError(template)

    if not os.path.exists(cached):
        text = _logo_text(selected_mods)
        # Сначала пробуем внешний logoMaker.exe (рядом с программой)
        used_exe = False
        for exe_name in ("logoMaker.exe", "logoMaker"):
            exe = os.path.join(app_dir(), exe_name)
            if os.path.exists(exe):
                subprocess.run(
                    [exe, template, cached, font, text, "87", "361", "36"],
                    check=True)
                used_exe = True
                break
        if not used_exe:
            from logo_maker import render
            render(template, cached, font, text, 87, 361, 36)

    shutil.copy2(cached, os.path.join(game_path, "logo1.avi"))


# =========================================================
# GUI helpers
# =========================================================

ICON_PATH = res_path(os.path.join("assets", "mmi.ico"))


def apply_icon(window) -> None:
    """Установить mmi.ico для окна (тихо игнорирует ошибки на не-Windows)."""
    if os.path.exists(ICON_PATH):
        try:
            window.iconbitmap(ICON_PATH)
        except Exception:
            pass


def info_box(parent, title, text):
    apply_icon(parent)
    messagebox.showinfo(title, text, parent=parent)


def error_box(parent, title, text):
    apply_icon(parent)
    messagebox.showerror(title, text, parent=parent)


def yesno(parent, title, text):
    apply_icon(parent)
    return messagebox.askyesno(title, text, parent=parent)


def yesnocancel(parent, title, text):
    apply_icon(parent)
    return messagebox.askyesnocancel(title, text, parent=parent)


# =========================================================
# Основное окно
# =========================================================

class App(TkinterDnD.Tk if DND_AVAILABLE else tk.Tk):

    def __init__(self):
        super().__init__()
        load_languages()

        self.cfg = load_json(PATHS["config"], {})
        global LANG
        LANG = self.cfg.get("lang", detect_lang())
        if LANG not in LANGS:
            LANG = "en" if "en" in LANGS else next(iter(LANGS), "en")

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1100x700")
        self.minsize(960, 620)
        apply_icon(self)

        self.lang_var = tk.StringVar(value=LANG)
        self.settings = self.cfg.get("settings", {"insert_logo": True, "save_space": False})

        self.upload_path = tk.StringVar()
        self.upload_name = tk.StringVar()

        self.instances = load_json(PATHS["instances_json"], [])
        if not self.instances:
            steam = detect_steam_path()
            if steam:
                upsert_instance(steam)
                self.instances = load_json(PATHS["instances_json"], [])

        # Текущий выбранный экземпляр
        cur_id = self.cfg.get("current_instance")
        if cur_id and find_instance(self.instances, cur_id):
            self.current_instance_id = cur_id
        elif self.instances:
            self.current_instance_id = self.instances[0]["id"]
        else:
            self.current_instance_id = None

        self._first_launch_check()
        self.create_menu()
        self.create_ui()

        if DND_AVAILABLE:
            try:
                self.drop_target_register(DND_FILES)
                self.dnd_bind("<<Drop>>", self.on_drop)
            except Exception:
                pass

        self.refresh_all()

    # ---------- helpers ----------
    @property
    def instance(self):
        return find_instance(self.instances, self.current_instance_id)

    def save_cfg(self):
        self.cfg["lang"] = LANG
        self.cfg["settings"] = self.settings
        self.cfg["current_instance"] = self.current_instance_id
        save_json(PATHS["config"], self.cfg)

    def _instance_choices(self):
        return [f"{i['name']}  ({i['path']})" for i in self.instances]

    def _instance_id_from_choice(self, choice: str):
        for inst in self.instances:
            if f"{inst['name']}  ({inst['path']})" == choice:
                return inst["id"]
        return None

    def _first_launch_check(self):
        # Чистый бэкап и так создаётся автоматически в clean_backup,
        # отдельное предупреждение пользователю больше не нужно.
        if not self.cfg.get("launched"):
            self.cfg["launched"] = True
            self.save_cfg()
        if self.instance:
            self._ensure_clean_backup(prompt=False)

    def _ensure_clean_backup(self, prompt=True):
        inst = self.instance
        if not inst or not os.path.isdir(inst["path"]):
            return
        clean = get_instance_paths(inst["id"])["clean"]
        if os.path.isdir(clean) and os.listdir(clean):
            inst["has_clean_backup"] = True
            update_instance(inst)
            return

        if not inst.get("has_clean_backup"):
            try:
                shutil.copytree(inst["path"], clean)
                inst["has_clean_backup"] = True
                update_instance(inst)
                self._log_safe(tr("clean_backup_created"))
                return
            except Exception as e:
                self._log_safe(f"Auto clean backup failed: {e}")

        if not prompt:
            return

        choice = yesnocancel(
            self, tr("no_clean_backup_title"),
            tr("no_clean_backup_msg") + "\n\n"
            f"Yes = {tr('btn_make_clean')}, No = {tr('btn_pick_clean')}, Cancel = {tr('btn_skip')}")
        if choice is None:
            return
        if choice:
            try:
                if os.path.isdir(clean):
                    shutil.rmtree(clean, ignore_errors=True)
                shutil.copytree(inst["path"], clean)
                inst["has_clean_backup"] = True
                update_instance(inst)
                info_box(self, tr("info"), tr("clean_backup_created"))
            except Exception as e:
                error_box(self, tr("error"), str(e))
        else:
            picked = filedialog.askdirectory(parent=self, title=tr("btn_pick_clean"))
            if picked:
                try:
                    if os.path.isdir(clean):
                        shutil.rmtree(clean, ignore_errors=True)
                    shutil.copytree(picked, clean)
                    inst["has_clean_backup"] = True
                    update_instance(inst)
                except Exception as e:
                    error_box(self, tr("error"), str(e))

    # =====================================================
    # Меню
    # =====================================================
    def create_menu(self):
        menubar = tk.Menu(self)

        m_file = tk.Menu(menubar, tearoff=0)
        m_file.add_command(label=tr("menu_select_game"),
                           command=self.menu_select_game)
        m_file.add_command(label=tr("menu_setup_clean_backup"),
                           command=self.menu_setup_clean_backup)
        m_file.add_command(label=tr("menu_change_exe"),
                           command=self.menu_change_exe)
        menubar.add_cascade(label=tr("menu_file"), menu=m_file)

        m_settings = tk.Menu(menubar, tearoff=0)
        m_settings.add_command(label=tr("menu_settings_open"),
                               command=self.open_settings_dialog)
        menubar.add_cascade(label=tr("menu_settings"), menu=m_settings)

        m_about = tk.Menu(menubar, tearoff=0)
        m_about.add_command(label=tr("menu_about"),
                            command=self.open_about_dialog)
        menubar.add_cascade(label=tr("menu_about"), menu=m_about)

        self.config(menu=menubar)

    def menu_select_game(self):
        path = filedialog.askdirectory(parent=self, title=tr("menu_select_game"))
        if not path:
            return
        inst = upsert_instance(path)
        self.instances = load_json(PATHS["instances_json"], [])
        self.current_instance_id = inst["id"]
        self.save_cfg()
        self._ensure_clean_backup(prompt=True)
        self.refresh_all()

    def menu_setup_clean_backup(self):
        inst = self.instance
        if not inst:
            return
        clean = get_instance_paths(inst["id"])["clean"]
        choice = yesnocancel(self, tr("no_clean_backup_title"),
                             tr("no_clean_backup_msg"))
        if choice is None:
            return
        if choice:
            try:
                if os.path.isdir(clean):
                    shutil.rmtree(clean, ignore_errors=True)
                shutil.copytree(inst["path"], clean)
                inst["has_clean_backup"] = True
                update_instance(inst)
                info_box(self, tr("info"), tr("clean_backup_created"))
            except Exception as e:
                error_box(self, tr("error"), str(e))
        else:
            picked = filedialog.askdirectory(parent=self, title=tr("btn_pick_clean"))
            if picked:
                try:
                    if os.path.isdir(clean):
                        shutil.rmtree(clean, ignore_errors=True)
                    shutil.copytree(picked, clean)
                    inst["has_clean_backup"] = True
                    update_instance(inst)
                except Exception as e:
                    error_box(self, tr("error"), str(e))

    def menu_change_exe(self):
        inst = self.instance
        if not inst:
            return
        path = filedialog.askopenfilename(
            parent=self, title=tr("exe_select_title"),
            initialdir=inst["path"],
            filetypes=[("Executable", "*.exe"), (tr("all_files"), "*.*")])
        if path:
            inst["exe"] = os.path.basename(path)
            update_instance(inst)

    # ---------- Settings ----------
    def open_settings_dialog(self):
        win = tk.Toplevel(self)
        win.title(tr("settings_title"))
        win.geometry("440x190")
        win.transient(self)
        win.resizable(False, False)
        apply_icon(win)

        v_logo = tk.BooleanVar(value=self.settings.get("insert_logo", True))
        v_save = tk.BooleanVar(value=self.settings.get("save_space", False))

        ttk.Checkbutton(win, text=tr("settings_insert_logo"),
                        variable=v_logo).pack(anchor="w", padx=15, pady=10)
        ttk.Checkbutton(win, text=tr("settings_save_space"),
                        variable=v_save).pack(anchor="w", padx=15, pady=5)

        bar = ttk.Frame(win)
        bar.pack(side="bottom", pady=10)

        def do_save():
            self.settings["insert_logo"] = v_logo.get()
            self.settings["save_space"] = v_save.get()
            self.save_cfg()
            win.destroy()

        ttk.Button(bar, text=tr("settings_save"),
                   command=do_save).pack(side="left", padx=8)
        ttk.Button(bar, text=tr("settings_cancel"),
                   command=win.destroy).pack(side="left", padx=8)

    # ---------- About modal ----------
    def open_about_dialog(self):
        win = tk.Toplevel(self)
        win.title(tr("about_title"))
        win.geometry("560x520")
        win.transient(self)
        apply_icon(win)

        ttk.Label(win, text=APP_NAME,
                  font=("Arial", 16, "bold")).pack(pady=(20, 5))
        ttk.Label(win, text=tr("version"),
                  font=("Arial", 11)).pack(pady=(0, 10))
        ttk.Separator(win, orient="horizontal").pack(fill="x", padx=30, pady=8)

        body = tk.Text(win, wrap=tk.WORD, height=14, width=64,
                       font=("Arial", 10), borderwidth=0,
                       background=win.cget("background"))
        body.pack(padx=20, pady=10, fill="both", expand=True)
        body.insert("1.0", tr("about_text").format(DATA))
        body.config(state="disabled")
        body.bind("<Button-3>",
                  lambda e: self.show_context_menu(e, body))

        bar = ttk.Frame(win)
        bar.pack(fill="x", side="bottom", pady=10)
        ttk.Button(bar, text=tr("vk_button"),
                   command=lambda: webbrowser.open(
                       "https://vk.com/mafia_and_mafia2_modding")).pack(
            side="left", padx=15)
        ttk.Button(bar, text=tr("close"),
                   command=win.destroy).pack(side="right", padx=15)

    # =====================================================
    # UI
    # =====================================================
    def change_lang(self, *_):
        global LANG
        LANG = self.lang_var.get()
        self.save_cfg()
        self.rebuild_ui()

    def rebuild_ui(self):
        for w in self.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass
        self.create_menu()
        self.create_ui()
        self.refresh_all()

    def _log_safe(self, text):
        if hasattr(self, "logbox") and self.logbox.winfo_exists():
            self.log(text)
        else:
            append_log(f"[{now()}] {text}")

    def log(self, text):
        line = f"[{now()}] {text}"
        self.logbox.insert(tk.END, line + "\n")
        self.logbox.see(tk.END)
        append_log(line)

    def create_ui(self):
        style = ttk.Style(self)
        style.configure("TButton", padding=6)
        style.configure("TLabel", padding=3)

        # Верхняя панель
        top = ttk.Frame(self, padding=5)
        top.pack(fill="x")
        ttk.Label(top, text="Language:").pack(side="right", padx=5)
        self.lang_combo = ttk.Combobox(
            top, textvariable=self.lang_var,
            values=list(LANGS.keys()), state="readonly", width=8)
        self.lang_combo.pack(side="right")
        self.lang_combo.bind("<<ComboboxSelected>>", self.change_lang)

        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)

        notebook = ttk.Notebook(main)
        notebook.pack(fill="both", expand=True)

        self.tab_install = ttk.Frame(notebook, padding=10)
        self.tab_mods = ttk.Frame(notebook, padding=10)
        self.tab_upload = ttk.Frame(notebook, padding=10)

        notebook.add(self.tab_install, text=tr("install_tab"))
        notebook.add(self.tab_mods, text=tr("mods_tab"))
        notebook.add(self.tab_upload, text=tr("upload_tab"))

        self.build_install_tab()
        self.build_mods_tab()
        self.build_upload_tab()

    # ---------- INSTALL TAB ----------
    def build_install_tab(self):
        f = self.tab_install
        f.columnconfigure(1, weight=1)
        f.rowconfigure(3, weight=1)

        # Game instance row
        ttk.Label(f, text=tr("game")).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.game_var = tk.StringVar()
        cur_inst = self.instance
        if cur_inst:
            self.game_var.set(f"{cur_inst['name']}  ({cur_inst['path']})")
        self.game_combo = ttk.Combobox(
            f, textvariable=self.game_var,
            values=self._instance_choices(), state="readonly")
        self.game_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.game_combo.bind("<<ComboboxSelected>>", self._on_game_selected)
        ttk.Button(f, text=tr("add_game"),
                   command=self.menu_select_game).grid(row=0, column=2, padx=5, pady=5)

        # Action buttons (auxiliary)
        actions = ttk.Frame(f)
        actions.grid(row=1, column=0, columnspan=3, pady=10, sticky="ew")
        for i, (txt, cmd) in enumerate([
            (tr("backup"), self.create_backup),
            (tr("restore"), self.restore_backup),
            (tr("cleanup"), self.cleanup),
            (tr("patch_dll"), self.patch_dll),
            (tr("run_game"), self.run_game),
        ]):
            actions.columnconfigure(i, weight=1)
            ttk.Button(actions, text=txt, command=cmd).grid(
                row=0, column=i, padx=5, sticky="ew")

        ttk.Label(f, text=tr("log")).grid(row=2, column=0, sticky="w", padx=5, pady=(8, 0))

        # Split: log | mod manager
        split = ttk.Panedwindow(f, orient="horizontal")
        split.grid(row=3, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)

        log_frame = ttk.Frame(split)
        self.logbox = tk.Text(log_frame, height=18, wrap=tk.WORD)
        sb = ttk.Scrollbar(log_frame, orient="vertical", command=self.logbox.yview)
        self.logbox.configure(yscrollcommand=sb.set)
        self.logbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.logbox.bind("<Button-3>", lambda e: self.show_context_menu(e, self.logbox))

        mm = ttk.LabelFrame(split, text=tr("mod_manager"))
        ttk.Label(mm, text=tr("mod_manager_hint"),
                  wraplength=320).pack(anchor="w", padx=6, pady=(4, 2))
        self.mm_canvas = tk.Canvas(mm, highlightthickness=0)
        mm_sb = ttk.Scrollbar(mm, orient="vertical", command=self.mm_canvas.yview)
        self.mm_inner = ttk.Frame(self.mm_canvas)
        self.mm_inner.bind(
            "<Configure>",
            lambda e: self.mm_canvas.configure(scrollregion=self.mm_canvas.bbox("all")))
        self.mm_canvas.create_window((0, 0), window=self.mm_inner, anchor="nw")
        self.mm_canvas.configure(yscrollcommand=mm_sb.set)
        self.mm_canvas.pack(side="left", fill="both", expand=True, padx=(4, 0))
        mm_sb.pack(side="right", fill="y")

        split.add(log_frame, weight=2)
        split.add(mm, weight=1)

        # Bottom strip — install buttons (use grid so они не уезжают за кадр)
        bottom = ttk.Frame(f)
        bottom.grid(row=4, column=0, columnspan=3, sticky="ew", pady=8)
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=0)
        bottom.columnconfigure(2, weight=0)

        ttk.Button(bottom, text=tr("clear_log"),
                   command=self.clear_log).grid(row=0, column=0, sticky="w", padx=4)
        ttk.Button(bottom, text=tr("install_to_game"),
                   command=lambda: self.install_to_game(False)).grid(
            row=0, column=1, sticky="e", padx=4)
        ttk.Button(bottom, text=tr("install_and_run"),
                   command=lambda: self.install_to_game(True)).grid(
            row=0, column=2, sticky="e", padx=4)

    def _on_game_selected(self, *_):
        iid = self._instance_id_from_choice(self.game_var.get())
        if iid:
            self.current_instance_id = iid
            self.save_cfg()
            self._ensure_clean_backup(prompt=True)
            self.refresh_mods_list()
            self.refresh_mod_manager()

    # ---------- MODS TAB ----------
    def build_mods_tab(self):
        f = self.tab_mods
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=1)

        cols = ("name", "installed", "date", "files", "readme")
        self.mods_table = ttk.Treeview(f, columns=cols, show="headings", height=15)
        for col_id, col_text, col_w, anchor in [
            ("name", tr("name"), 260, "w"),
            ("installed", tr("installed_col"), 110, "center"),
            ("date", tr("date"), 150, "w"),
            ("files", tr("files"), 70, "center"),
            ("readme", tr("readme"), 240, "w"),
        ]:
            self.mods_table.heading(col_id, text=col_text)
            self.mods_table.column(col_id, width=col_w, anchor=anchor)
        self.mods_table.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        sb = ttk.Scrollbar(f, orient="vertical", command=self.mods_table.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.mods_table.configure(yscrollcommand=sb.set)

        # Bottom buttons in 2 rows so they never disappear when window narrows
        bf = ttk.Frame(f)
        bf.grid(row=1, column=0, columnspan=2, pady=8, sticky="ew")
        for i in range(4):
            bf.columnconfigure(i, weight=1)
        ttk.Button(bf, text=tr("refresh"), command=self.refresh_mods_list).grid(
            row=0, column=0, padx=3, sticky="ew")
        ttk.Button(bf, text=tr("rename_mod"), command=self.rename_selected_mod).grid(
            row=0, column=1, padx=3, sticky="ew")
        ttk.Button(bf, text=tr("open_mod_folder"), command=self.open_mod_folder).grid(
            row=0, column=2, padx=3, sticky="ew")
        ttk.Button(bf, text=tr("open_readme"), command=self.open_readme_file).grid(
            row=0, column=3, padx=3, sticky="ew")
        ttk.Button(bf, text=tr("create_mmi"), command=self.open_mmi_dialog).grid(
            row=1, column=0, padx=3, pady=(4, 0), sticky="ew")
        ttk.Button(bf, text=tr("remove_from_library"),
                   command=self.remove_selected_mod).grid(
            row=1, column=1, padx=3, pady=(4, 0), sticky="ew")

        self.mods_table.bind("<Double-1>", self.open_readme_file)
        self.mods_table.bind("<Button-3>", self.show_mod_context_menu)

    # ---------- UPLOAD TAB ----------
    def build_upload_tab(self):
        f = self.tab_upload
        ttk.Label(f, text=tr("upload_title"),
                  font=("Arial", 13, "bold")).pack(anchor="w", pady=(2, 8))
        ttk.Label(f, text=tr("upload_hint")).pack(anchor="w", pady=2)

        row1 = ttk.Frame(f)
        row1.pack(fill="x", pady=6)
        ttk.Entry(row1, textvariable=self.upload_path).pack(
            side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(row1, text="📂 " + tr("select"),
                   command=self.select_upload).pack(side="left")

        ttk.Label(f, text=tr("upload_name")).pack(anchor="w", pady=(8, 2))
        ttk.Entry(f, textvariable=self.upload_name).pack(fill="x")

        ttk.Button(f, text=tr("upload_btn"),
                   command=self.do_upload).pack(pady=14, anchor="w")

    # =====================================================
    # Контекстные меню
    # =====================================================
    def show_context_menu(self, event, widget):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label=tr("copy"),
                         command=lambda: self._copy_text(widget))
        menu.add_command(label=tr("select_all"),
                         command=lambda: widget.tag_add("sel", "1.0", "end"))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _copy_text(self, widget):
        try:
            self.clipboard_clear()
            self.clipboard_append(widget.selection_get())
        except Exception:
            pass

    def show_mod_context_menu(self, event):
        row = self.mods_table.identify_row(event.y)
        if row:
            self.mods_table.selection_set(row)
        if not self.get_selected_mod():
            return
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label=tr("rename_mod"), command=self.rename_selected_mod)
        menu.add_command(label=tr("open_mod_folder"), command=self.open_mod_folder)
        menu.add_command(label=tr("open_readme"), command=self.open_readme_file)
        menu.add_command(label=tr("create_mmi"), command=self.open_mmi_dialog)
        menu.add_separator()
        menu.add_command(label=tr("remove_from_library"),
                         command=self.remove_selected_mod)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # =====================================================
    # Действия
    # =====================================================
    def select_upload(self):
        path = filedialog.askopenfilename(
            parent=self, title=tr("upload_btn"),
            filetypes=[
                (tr("all_supported"), "*.zip;*.mmi;*.7z;*.rar;*.tar;*.gz"),
                (tr("mmi_archives"), "*.mmi"),
                (tr("zip_archives"), "*.zip"),
                (tr("all_files"), "*.*")])
        if not path:
            path = filedialog.askdirectory(parent=self, title=tr("select_mod_folder"))
        if path:
            self.upload_path.set(path)

    def do_upload(self):
        path = self.upload_path.get()
        name = self.upload_name.get().strip() or None
        if not path:
            return
        try:
            ids = add_mod_to_library(path, name=name)
            self.log(tr("upload_done") + f" ({len(ids)})")
            info_box(self, tr("ok"), tr("upload_done"))
            self.upload_path.set("")
            self.upload_name.set("")
        except zipfile.BadZipFile:
            error_box(self, tr("error"), tr("bad_archive"))
        except Exception as e:
            error_box(self, tr("error"), str(e))
        self.refresh_all()

    def create_backup(self):
        inst = self.instance
        if not inst:
            return
        name = simpledialog.askstring(
            tr("backup"), tr("backup_name"),
            initialvalue=tr("backup_default"), parent=self)
        if not name:
            return
        try:
            inst_paths = get_instance_paths(inst["id"])
            backup_path = os.path.join(inst_paths["user_backups"], slugify(name))
            shutil.copytree(inst["path"], backup_path)
            self.log(tr("backup_created").format(name))
            info_box(self, tr("ok"), tr("backup_created").format(name))
        except Exception as e:
            error_box(self, tr("error"), str(e))

    def restore_backup(self):
        inst = self.instance
        if not inst:
            return
        path = filedialog.askdirectory(
            parent=self,
            initialdir=get_instance_paths(inst["id"])["user_backups"],
            title=tr("select_backup"))
        if not path:
            return
        if not yesno(self, tr("confirm_execute"), tr("hard_confirm")):
            return
        try:
            hard_restore_from(path, inst["path"])
            self.log(tr("hard_restored") + " <- " + path)
            info_box(self, tr("ok"), tr("hard_restored"))
        except Exception as e:
            error_box(self, tr("error"), str(e))

    def cleanup(self):
        inst = self.instance
        if not inst:
            return
        if yesno(self, tr("cleanup"), tr("cleanup_confirm")):
            cleanup_resources(inst["path"], self.log)
            self.log(tr("cleanup_done"))

    def patch_dll(self):
        inst = self.instance
        if not inst:
            return
        src = res_path(os.path.join("assets", "rw_data.dll"))
        if not os.path.exists(src):
            error_box(self, tr("error"), tr("patch_dll_missing"))
            return
        if not yesno(self, tr("patch_dll"),
                     tr("patch_dll_confirm").format(inst["path"])):
            return
        try:
            patch_rw_data_dll(inst["path"], self.log)
            self.log(tr("patch_dll_done"))
            info_box(self, tr("ok"), tr("patch_dll_done"))
        except Exception as e:
            error_box(self, tr("error"), str(e))

    def run_game(self):
        inst = self.instance
        if not inst:
            return
        exe = os.path.join(inst["path"], inst.get("exe", "Game.exe"))
        if not os.path.exists(exe):
            error_box(self, tr("error"), tr("exe_not_found").format(exe))
            return
        self._maybe_update_logo()
        try:
            subprocess.Popen(exe)
        except Exception as e:
            error_box(self, tr("error"), str(e))

    def _maybe_update_logo(self):
        if not self.settings.get("insert_logo", True):
            return
        inst = self.instance
        if not inst:
            return
        all_mods = load_json(PATHS["mods_json"], [])
        active_ids = set(inst.get("active_mods", []))
        selected = [m for m in all_mods if m["id"] in active_ids]
        try:
            update_logo_in_game(selected, inst["path"], self.log)
        except Exception as e:
            self.log(tr("logo_failed").format(e))

    def install_to_game(self, run_after):
        inst = self.instance
        if not inst:
            return
        if not inst.get("has_clean_backup"):
            self._ensure_clean_backup(prompt=True)
        if not inst.get("has_clean_backup"):
            return
        ids = [mid for mid, var in self.mm_vars.items() if var.get()]
        all_mods = load_json(PATHS["mods_json"], [])
        selected = [m for m in all_mods if m["id"] in ids]
        try:
            install_mods_into_game(selected, inst, self.log)
            self.log(tr("install_to_game_complete"))
            self.instances = load_json(PATHS["instances_json"], [])
            self.refresh_mods_list()
            if run_after:
                self.run_game()
            else:
                info_box(self, tr("ok"), tr("install_to_game_complete"))
        except Exception as e:
            error_box(self, tr("error"), str(e))

    def clear_log(self):
        self.logbox.delete("1.0", tk.END)

    # =====================================================
    # Список модов / mod manager
    # =====================================================
    def refresh_all(self):
        if hasattr(self, "game_combo"):
            self.game_combo['values'] = self._instance_choices()
            cur = self.instance
            if cur:
                self.game_var.set(f"{cur['name']}  ({cur['path']})")
        self.refresh_mods_list()
        self.refresh_mod_manager()

    def refresh_mods_list(self):
        if not hasattr(self, "mods_table"):
            return
        for row in self.mods_table.get_children():
            self.mods_table.delete(row)
        self.mods_data = load_json(PATHS["mods_json"], [])
        inst = self.instance
        active_ids = set(inst.get("active_mods", [])) if inst else set()
        for mod in self.mods_data:
            readmes = find_readmes(mod.get("dir", ""))
            readme_str = ", ".join(os.path.relpath(r, mod.get("dir", ""))
                                   for r in readmes)
            mark = "✓" if mod["id"] in active_ids else "✗"
            self.mods_table.insert("", "end", values=(
                mod.get("name", ""),
                mark,
                mod.get("date", ""),
                mod.get("files_count", 0),
                readme_str,
            ))

    def refresh_mod_manager(self):
        if not hasattr(self, "mm_inner"):
            return
        for w in self.mm_inner.winfo_children():
            w.destroy()
        self.mm_vars = {}
        inst = self.instance
        active_ids = set(inst.get("active_mods", [])) if inst else set()
        for mod in load_json(PATHS["mods_json"], []):
            v = tk.BooleanVar(value=mod["id"] in active_ids)
            self.mm_vars[mod["id"]] = v
            ttk.Checkbutton(self.mm_inner,
                            text=mod.get("name", mod["id"]),
                            variable=v).pack(anchor="w", padx=6, pady=2)

    def get_selected_mod(self):
        sel = self.mods_table.selection()
        if not sel:
            return None
        idx = self.mods_table.index(sel[0])
        if 0 <= idx < len(self.mods_data):
            return self.mods_data[idx]
        return None

    def rename_selected_mod(self):
        mod = self.get_selected_mod()
        if not mod:
            return
        new = simpledialog.askstring(tr("rename_mod"), tr("name"),
                                     initialvalue=mod.get("name", ""), parent=self)
        if new is None or not new.strip():
            return
        rename_mod(mod["id"], new.strip())
        self.refresh_all()

    def remove_selected_mod(self):
        mod = self.get_selected_mod()
        if not mod:
            return
        if not yesno(self, tr("remove_from_library"),
                     tr("remove_confirm").format(mod.get("name", mod["id"]))):
            return
        remove_mod_from_library(mod["id"])
        self.refresh_all()

    def open_mod_folder(self):
        mod = self.get_selected_mod()
        if mod:
            open_path(mod.get("dir"))

    def open_readme_file(self, event=None):
        mod = self.get_selected_mod()
        if not mod:
            return
        readmes = find_readmes(mod.get("dir", ""))
        if not readmes:
            info_box(self, tr("info"), "Readme not found")
            return
        open_path(readmes[0])

    # =====================================================
    # MMI dialog
    # =====================================================
    def open_mmi_dialog(self):
        win = tk.Toplevel(self)
        win.title(tr("mmi_dialog_title"))
        win.geometry("540x520")
        win.minsize(460, 360)
        win.transient(self)
        apply_icon(win)

        search_var = tk.StringVar()
        bar = ttk.Frame(win)
        bar.pack(fill="x", padx=10, pady=8)
        ttk.Label(bar, text=tr("mmi_search")).pack(side="left")
        ttk.Entry(bar, textvariable=search_var).pack(
            side="left", fill="x", expand=True, padx=6)

        body = ttk.Frame(win)
        body.pack(fill="both", expand=True, padx=10, pady=4)
        canvas = tk.Canvas(body, highlightthickness=0)
        sb = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        all_mods = load_json(PATHS["mods_json"], [])
        vars_map = {}

        def render():
            for w in inner.winfo_children():
                w.destroy()
            q = search_var.get().lower()
            for m in all_mods:
                label = m.get("name") or m["id"]
                if q and q not in label.lower():
                    continue
                v = vars_map.setdefault(m["id"], tk.BooleanVar())
                ttk.Checkbutton(inner, text=label,
                                variable=v).pack(anchor="w", pady=2)

        search_var.trace_add("write", lambda *_: render())
        render()

        bbar = ttk.Frame(win)
        bbar.pack(fill="x", side="bottom", pady=10)

        def do_save():
            chosen_ids = {mid for mid, v in vars_map.items() if v.get()}
            chosen = [m for m in all_mods if m["id"] in chosen_ids]
            if not chosen:
                info_box(win, tr("info"), tr("no_mods_selected"))
                return
            out = filedialog.asksaveasfilename(
                parent=win, title=tr("mmi_save"),
                defaultextension=".mmi",
                filetypes=[(tr("mmi_archives"), "*.mmi"),
                           (tr("all_files"), "*.*")])
            if not out:
                return
            try:
                build_mmi(chosen, out)
                win.destroy()
                info_box(self, tr("ok"), out)
            except Exception as e:
                error_box(win, tr("error"), str(e))

        ttk.Button(bbar, text=tr("close"),
                   command=win.destroy).pack(side="left", padx=10)
        ttk.Button(bbar, text=tr("mmi_save"),
                   command=do_save).pack(side="right", padx=10)

    # =====================================================
    # DnD
    # =====================================================
    def on_drop(self, event):
        path = event.data.strip("{}").strip()
        if path:
            self.upload_path.set(path)


# =========================================================
if __name__ == "__main__":
    app = App()
    app.mainloop()
