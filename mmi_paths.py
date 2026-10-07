"""Пути и константы расположения программы и данных.

DATA — папка `data/` рядом с .exe (или main.py в dev). Все пользовательские
JSON / распакованные моды / бэкапы / логи лежат здесь.
"""

import os
import sys


def app_dir() -> str:
    """Папка, где лежит .exe или main.py."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(sys.argv[0]))


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
    "patches_dir": os.path.join(DATA, "patches"),
    "log_file": os.path.join(DATA, "logs.txt"),
}
for _k in ("mods_dir", "instances_dir", "logos_dir", "patches_dir"):
    os.makedirs(PATHS[_k], exist_ok=True)

ICON_PATH = res_path(os.path.join("assets", "mmi.ico"))


# Глобальные настройки приложения
APP_NAME = "Mafia Mod Installer"
APP_VERSION = "0.17.4"

DEFAULT_PRIORITY = 10
MMI_README_LIMIT = 2000
DEFAULT_RECOMMENDED_COUNT = 2

GAME_VERSIONS = ("1.0", "1.1", "1.2")

# Трекеры модов по умолчанию (меню «Трекеры»; свои добавляются через
# «Добавить свой…» и хранятся в config.json).
DEFAULT_TRACKERS = [
    {"name": "moddb", "url": "https://www.moddb.com/games/mafia"},
    {"name": "Коллекция модов Модостроя",
     "url": "https://vk.com/page-35850321_50557744"},
    {"name": "mafia.czech-games.net",
     "url": "https://mafia.czech-games.net/download/mody/mody-velke/"},
    {"name": "Awesome Mafia Tools and Resources",
     "url": "https://github.com/MafiaHub/awesome-mafia"},
]

# Страница Steam с решением проблемы «игра не запускает» (средство
# устранения неполадок).
GAME_WONT_START_URL = ("https://steamcommunity.com/sharedfiles/"
                       "filedetails/?id=1211005690")

DEFAULT_SETTINGS = {
    "insert_logo": True,
    "widescreen": False,
    "compress_backups": False,
    "compress_level": 5,
    "conflict_check": False,
    "immutable_saves": True,
    "auto_backup_saves": True,           # авто-бэкап savegame/ перед install
    "auto_extract_dta": True,            # автораспаковка .dta перед install
    "experimental_autodetect_target_version": False,  # экспериментально
    "use_alt_logo": False,               # logo1_alt.avi без оверлея
    "auto_widescreen_detect": True,      # автоопределение WidescreenFix
    "dark_theme": False,                 # тёмная тема интерфейса
    "new_install_ui": True,              # новый дизайн страницы «Установка»
    "recommended_count_on": True,
    "recommended_count": DEFAULT_RECOMMENDED_COUNT,
}
