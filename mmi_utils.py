"""Общие утилиты: JSON, FS, slugify, sha256, открытие путей, README-детект."""

import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

from mmi_paths import PATHS


# ---------------------------------------------------------
# Время / JSON / FS
# ---------------------------------------------------------

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


def sha256_dir(directory: str) -> str:
    """SHA-256 контрольная сумма содержимого папки (детерминированная)."""
    h = hashlib.sha256()
    if not os.path.isdir(directory):
        return ""
    for root, _, files in os.walk(directory):
        for fname in sorted(files):
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, directory).replace("\\", "/")
            h.update(rel.encode("utf-8"))
            h.update(b"\x00")
            try:
                with open(full, "rb") as f:
                    while True:
                        chunk = f.read(1 << 20)
                        if not chunk:
                            break
                        h.update(chunk)
            except Exception:
                pass
            h.update(b"\xff")
    return h.hexdigest()


# ---------------------------------------------------------
# README-детект
# ---------------------------------------------------------

GAME_DIRS = {"maps", "missions", "models", "sounds", "tables", "textures",
             "records", "animations", "anims", "music"}
GAME_EXTS = (".dta", ".exe", ".dll", ".cfg")

README_KEYWORDS = [
    # English
    "readme", "read_me", "read me", "readthis", "instruction", "instructions",
    "guide", "manual", "setup", "install", "notes", "howto", "how_to", "info",
    "description", "about",
    # Русский
    "прочитай", "прочти", "читай", "инструкция", "руководство", "установка",
    "заметки", "описание", "информация", "помощь", "о_моде", "о моде",
    "как_установить", "как установить", "руководство_по_установке",
    # Czech / Slovak
    "navod", "pokyny", "prirucka", "instalace", "návod", "pokyny", "příručka",
    "popis", "informace", "informacie",
    # Polish
    "przeczytaj", "instrukcja", "instalacja", "czytaj", "opis",
    # German
    "liesmich", "lies_mich", "anleitung", "handbuch", "installation",
    "hinweise", "beschreibung", "info_de",
    # Ukrainian
    "інструкція", "керівництво", "опис",
    # Italian / Spanish / French / Portuguese
    "leggimi", "istruzioni", "manuale", "installazione",
    "leeme", "instrucciones", "descripcion",
    "lisezmoi", "instructions_fr",
    "leiame", "instrucoes",
    # Hungarian / Romanian / Serbian / Turkish / Bulgarian
    "olvassel", "utasitas", "kezikonyv", "telepites",
    "citeste", "instructiuni", "instalare",
    "procitaj", "uputstvo", "instalacija",
    "oku", "talimat", "kilavuz", "kurulum",
    "procheti", "rukovodstvo",
]
README_EXTS = (".txt", ".pdf", ".md", ".rtf", ".doc", ".docx", ".html", ".htm")


def is_readme_filename(file_name: str) -> bool:
    """Совпадение по ключевым словам в имени и подходящему расширению."""
    lower = file_name.lower()
    if not lower.endswith(README_EXTS):
        return False
    if any(kw in lower for kw in README_KEYWORDS):
        return True
    return False


def is_readme_path(rel_path: str) -> bool:
    """Использует только проверку имени — для фильтрации списков."""
    return is_readme_filename(os.path.basename(rel_path))


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
    """Возвращает первый найденный корень мода (для совместимости)."""
    roots = detect_root_folders(path)
    return roots[0] if roots else path


def detect_root_folders(path: str) -> list:
    """Находит ВСЕ корни мода внутри переданной папки.

    Корнем считается папка, в которой есть подпапка из GAME_DIRS или
    файл с GAME_EXTS. Используется когда архив содержит несколько версий
    одного мода (mod/ver1/, mod/ver2/, …) — каждая из них должна стать
    отдельным модом в библиотеке."""
    if is_game_like_folder(path):
        return [path]
    found = []
    for root, dirs, _ in os.walk(path):
        depth = root.replace(path, "").count(os.sep)
        if depth > 3:
            continue
        # Не углубляемся внутрь уже найденного корня — иначе сами GAME_DIRS
        # вроде sounds/ начнут "выглядеть" как корни.
        if any(root.startswith(f + os.sep) or root == f for f in found):
            dirs[:] = []
            continue
        for d in list(dirs):
            candidate = os.path.join(root, d)
            if is_game_like_folder(candidate):
                found.append(candidate)
        # Если текущая папка сама game-like, тоже добавим (вне корня)
        if root != path and is_game_like_folder(root) and root not in found:
            found.append(root)
    return found


def find_readmes(mod_dir: str):
    """Сканер readme в распакованном моде.

    Алгоритм:
      1. Все файлы, чьё имя матчится README_KEYWORDS, добавляем сразу.
      2. Дополнительно: если в каком-то каталоге (особенно в корне мода)
         есть только ОДИН текстовый файл — считаем его readme,
         даже если имя на него не указывает (типичный случай:
         «Описание.txt» / «Прочти.txt» / просто «mod.txt»).

    Это нужно потому что русские/китайские/чешские названия часто не
    совпадают с английскими ключевыми словами.
    """
    out = []
    if not mod_dir or not os.path.isdir(mod_dir):
        return out
    seen = set()
    for root, _, files in os.walk(mod_dir):
        # фаза 1 — keyword-match
        for f in files:
            if is_readme_filename(f):
                full = os.path.join(root, f)
                if full not in seen:
                    out.append(full)
                    seen.add(full)
        # фаза 2 — единственный текстовый в каталоге
        text_files = [f for f in files if f.lower().endswith(README_EXTS)]
        if len(text_files) == 1:
            full = os.path.join(root, text_files[0])
            if full not in seen:
                out.append(full)
                seen.add(full)
    return out
