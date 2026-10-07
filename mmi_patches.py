"""Патчи для игры: скачивание в data/patches/ и установка в выбранный
экземпляр (окно «Патчинг» в Сервисе).

Патчинг работает как загрузка мода: архив распаковывается, ищется корень
патча (mmi_utils.detect_root_folders — тот же алгоритм, что и для модов
при загрузке в библиотеку) и содержимое корня копируется в корень игры.
Если корень не найден — копируется всё распакованное дерево (fallback,
поведение старых версий). Патч нельзя удалить: он вносит постоянные
изменения в файлы игры.

Установленные патчи записываются в data/patches/installed.json
(путь цели → {patch_id: {name, date, files, source}}) — отчёт
траблшутера показывает их в разделе «Патчи».

Источники:
  • прямой URL (github raw, user-attachments, moddb mirror) — GET;
  • публичная ссылка Яндекс.Диска — сначала запрашиваем прямую ссылку
    через cloud-api.yandex.net, затем качаем её.
"""

import json
import os
import re
import shutil
import tempfile
import urllib.parse
import urllib.request

from mmi_paths import PATHS, APP_VERSION
from mmi_utils import detect_root_folders, now
from mmi_mods import extract_archive


USER_AGENT = (f"MafiaModInstaller/{APP_VERSION} "
              "(Windows NT 10.0; Win64; x64)")

# Скачанные патчи лежат здесь; index.json отображает id патча на имя файла.
PATCHES_DIR = PATHS["patches_dir"]
_INDEX_FILE = os.path.join(PATCHES_DIR, "index.json")
_INSTALLED_FILE = os.path.join(PATCHES_DIR, "installed.json")

# id → описание патча. name_key/desc_key — ключи языковых пакетов.
PATCHES = [
    {
        "id": "music",
        "name_key": "patch_name_music",
        "desc_key": "patch_desc_music",
        "url": "https://disk.yandex.ru/d/LBbsWdV33Pus7d",
        "fallback_name": "music_patch.zip",
    },
    {
        "id": "mafiacon",
        "name_key": "patch_name_mafiacon",
        "desc_key": "patch_desc_mafiacon",
        "url": ("https://raw.githubusercontent.com/Medgithub443/"
                "patches-for-mafia-tclh/main/MafiaCon.rar"),
        "fallback_name": "MafiaCon.rar",
    },
    {
        "id": "widescreen",
        "name_key": "patch_name_widescreen",
        "desc_key": "patch_desc_widescreen",
        "url": ("https://raw.githubusercontent.com/Medgithub443/"
                "patches-for-mafia-tclh/main/Widescreen-Fix.zip"),
        "fallback_name": "Widescreen-Fix.zip",
    },
]

# Имена патчей для отчёта траблшутера (отчёт, как и раньше, на русском).
REPORT_PATCH_NAMES = {
    "music": "Возвращение музыки HiT-FM",
    "mafiacon": "MafiaCon",
    "widescreen": "Widescreen Fix",
}

# Характерные файлы патча музыки: любые 2 из 3 ⇒ патч, скорее всего,
# установлен (эвристика для установок до появления installed.json).
MUSIC_MARKERS = ("sounds/MUSIC/city_music_13.ogg",
                 "sounds/14_Coucou.wav",
                 "sounds/s_music5.wav")


def get_patch(patch_id: str) -> dict:
    for p in PATCHES:
        if p["id"] == patch_id:
            return p
    return None


# ---------------------------------------------------------
# Кэш скачанных файлов (patches/index.json: id → имя файла)
# ---------------------------------------------------------

def _load_index() -> dict:
    try:
        with open(_INDEX_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_index(index: dict) -> None:
    try:
        with open(_INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def cached_patch_file(patch_id: str) -> str:
    """Путь к уже скачанному файлу патча или ''."""
    fname = _load_index().get(patch_id, "")
    if not fname:
        return ""
    full = os.path.join(PATCHES_DIR, fname)
    return full if os.path.isfile(full) else ""


# ---------------------------------------------------------
# Учёт установленных патчей (patches/installed.json)
# ---------------------------------------------------------

def _load_installed() -> dict:
    try:
        with open(_INSTALLED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_installed(data: dict) -> None:
    try:
        with open(_INSTALLED_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def record_patch_install(patch_id: str, patch_name: str, target_path: str,
                         files: list, source: str = "") -> None:
    """Записывает факт установки патча в цель (папку игры или чистую
    резервную копию). Патч снести нельзя — записи не удаляются."""
    data = _load_installed()
    entry = data.setdefault(target_path, {}).get(patch_id, {})
    entry.update({"name": patch_name,
                  "date": now(),
                  "files": sorted(files or []),
                  "source": source or entry.get("source", "")})
    data[target_path][patch_id] = entry
    _save_installed(data)


def installed_patches(target_path: str) -> dict:
    """{patch_id: {name, date, files, source}} — записи установки патчей
    для переданной цели (по нормализованному абсолютному пути)."""
    if not target_path:
        return {}
    norm = os.path.normcase(os.path.abspath(target_path))
    out = {}
    for path, patches in _load_installed().items():
        if os.path.normcase(os.path.abspath(path)) == norm:
            out.update(patches or {})
    return out


def detect_patches_in_game(game_path: str) -> dict:
    """Эвристика «патч установлен» по характерным файлам в папке игры.
    Покрывает установки, сделанные не через MMI или до v0.17.2.

    Возвращает {patch_id: {"name", "files", "source"}}."""
    found = {}
    if not game_path or not os.path.isdir(game_path):
        return found

    asi = os.path.join(game_path, "scripts", "Mafia.WidescreenFix.asi")
    if os.path.isfile(asi):
        ws_files = []
        for loader in ("d3d8.dll", "dinput8.dll"):
            if os.path.isfile(os.path.join(game_path, loader)):
                ws_files.append(loader)
        ws_files.append("scripts/Mafia.WidescreenFix.asi")
        found["widescreen"] = {"name": REPORT_PATCH_NAMES["widescreen"],
                               "files": ws_files, "source": ""}

    mc_files = [f for f in ("MafiaCon.exe", "Mafia.dll", "MHook.dll")
                if os.path.isfile(os.path.join(game_path, f))]
    if mc_files:
        found["mafiacon"] = {"name": REPORT_PATCH_NAMES["mafiacon"],
                             "files": mc_files, "source": ""}

    music_hits = [m for m in MUSIC_MARKERS
                  if os.path.isfile(os.path.join(game_path, m))]
    if len(music_hits) >= 2:
        found["music"] = {"name": REPORT_PATCH_NAMES["music"],
                          "files": music_hits, "source": ""}
    return found


# ---------------------------------------------------------
# Скачивание
# ---------------------------------------------------------

def _yandex_disk_direct_link(public_url: str) -> str:
    """Прямая ссылка на скачивание по публичной ссылке Яндекс.Диска."""
    api = ("https://cloud-api.yandex.net/v1/disk/public/resources/download"
           "?public_key=" + urllib.parse.quote(public_url, safe=""))
    req = urllib.request.Request(api, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    href = (data.get("href") or "").strip()
    if not href:
        raise RuntimeError("Yandex Disk API returned empty download link")
    return href


def _name_from_content_disposition(header: str) -> str:
    if not header:
        return ""
    # RFC 5987: filename*=UTF-8''name; классика: filename="name"
    m = (re.search(r"filename\*=(?:UTF-8|utf-8)''([^;]+)", header)
         or re.search(r'filename="([^"]+)"', header)
         or re.search(r"filename=([^;]+)", header))
    if not m:
        return ""
    name = m.group(1).strip().strip('"')
    return _sanitize(name)


def _name_from_url(url: str) -> str:
    path = urllib.parse.urlsplit(url).path
    name = os.path.basename(path)
    try:
        name = urllib.parse.unquote(name)
    except Exception:
        pass
    return _sanitize(name)


def _sanitize(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "_", name or "")
    return name.strip().strip(".")


def download_patch(patch: dict, log=print, progress=None) -> str:
    """Скачивает патч в PATCHES_DIR (если ещё не скачан) и возвращает путь.

    log(msg) — текст в лог окна; progress(done, total) — прогресс загрузки
    (total == 0, если сервер не отдал Content-Length).
    """
    cached = cached_patch_file(patch["id"])
    if cached:
        return cached

    url = patch["url"]
    direct = url
    if "disk.yandex." in urllib.parse.urlsplit(url).netloc:
        log(f"→ Yandex Disk: {url}")
        direct = _yandex_disk_direct_link(url)

    req = urllib.request.Request(direct, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        header = resp.headers.get("Content-Disposition", "")
        name = (_name_from_content_disposition(header)
                or _name_from_url(direct)
                or patch["fallback_name"])
        dest = os.path.join(PATCHES_DIR, name)
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        tmp = dest + ".part"
        with open(tmp, "wb") as f:
            while True:
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        os.replace(tmp, dest)

    index = _load_index()
    index[patch["id"]] = os.path.basename(dest)
    _save_index(index)
    return dest


# ---------------------------------------------------------
# Установка
# ---------------------------------------------------------

_ARCHIVE_EXTS = (".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz",
                 ".mmi")


def install_patch_file(file_path: str, game_path: str) -> dict:
    """Устанавливает скачанный патч в папку игры.

    Архив распаковывается во временную папку, ищется корень патча
    (detect_root_folders — тот же алгоритм, что и для модов) и СОДЕРЖИМОЕ
    корня копируется в корень игры — обёртки вида «Widescreen Fix/…»
    не создаются. Несколько корней = содержимое каждого копируется
    в игру. Корень не найден = копируется всё распакованное дерево.
    Одиночный (не архив) файл копируется в корень игры как есть.

    Возвращает {"mode": "extracted" | "copied", "files": [относ. пути]}.
    """
    if not os.path.isdir(game_path):
        raise FileNotFoundError(game_path)

    ext = os.path.splitext(file_path)[1].lower()
    if ext in _ARCHIVE_EXTS:
        installed = []
        with tempfile.TemporaryDirectory() as tmp:
            if not extract_archive(file_path, tmp):
                raise RuntimeError("Не удалось распаковать архив патча")
            roots = detect_root_folders(tmp)
            sources = roots if roots else [tmp]
            for src in sources:
                for root, _, files in os.walk(src):
                    for f in files:
                        full = os.path.join(root, f)
                        rel = os.path.relpath(full, src)
                        dst = os.path.join(game_path, rel)
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        shutil.copy2(full, dst)
                        installed.append(rel.replace("\\", "/"))
        return {"mode": "extracted", "files": sorted(installed)}

    dst = os.path.join(game_path, os.path.basename(file_path))
    shutil.copy2(file_path, dst)
    return {"mode": "copied",
            "files": [os.path.basename(file_path).replace("\\", "/")]}
