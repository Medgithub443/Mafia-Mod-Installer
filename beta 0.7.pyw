# =========================================================
# Mafia Mod Installer v0.7-beta
# =========================================================

import os
import shutil
import zipfile
import json
import datetime
import tempfile
import subprocess
import locale
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import hashlib
import webbrowser

# Поддержка различных архивов (7z, rar и т.д.)
try:
    import patoolib
    PATOOL_AVAILABLE = True
except ImportError:
    PATOOL_AVAILABLE = False

# Поддержка drag & drop
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False
    TkinterDnD = tk

APP_NAME = "MafiaModInstaller"

# =========================================================
# ПУТИ (глобальные)
# =========================================================

DOCS = os.path.join(os.path.expanduser("~"), "Documents", APP_NAME)
CONFIG = os.path.join(DOCS, "config.json")
os.makedirs(DOCS, exist_ok=True)

# =========================================================
# DTA MAP (для очистки ресурсов)
# =========================================================

DTA_MAP = {
    "a0.dta": "sounds",
    "a1.dta": "missions",
    "a2.dta": "models",
    "a3.dta": "animations",
    "a4.dta": "animations2",
    "a5.dta": "difference",
    "a6.dta": "textures",
    "a7.dta": "records",
    "a8.dta": "patch",
    "a9.dta": "system",
    "aa.dta": "tables",
    "ab.dta": "music",
    "ac.dta": "animations3",
}

# =========================================================
# ЯЗЫК
# =========================================================

def detect_lang():
    try:
        loc = locale.getlocale()[0] or "en"
        loc = loc.lower()
        if "ru" in loc: return "ru"
        if "cs" in loc or "cz" in loc: return "cz"
    except:
        pass
    return "en"

T = {
    "ru": {
        # Вкладки
        "install_tab": "Установка",
        "mods_tab": "Установленные моды",
        "about_tab": "О программе",
        
        # Установка
        "game": "Папка игры:",
        "mod": "Мод / архив:",
        "install": "Установить мод",
        "backup": "Создать бэкап",
        "restore": "Восстановить",
        "cleanup": "Очистить ресурсы",
        "log": "Лог операций",
        "clear_log": "Очистить лог",
        "add_game": "Добавить игру",
        "select": "Выбрать",
        "select_mod_folder": "Выберите папку с модом",
        "all_supported": "Все поддерживаемые",
        "zip_archives": "ZIP архивы",
        "7z_archives": "7z архивы",
        "rar_archives": "RAR архивы",
        "all_files": "Все файлы",
        "cleanup_confirm": "Удалить распакованные ресурсы?",
        "hard_restore": "Hard Restore",
        "select_backup": "Выберите бэкап",
        "confirm_execute": "Подтвердить и выполнить?",
        "hard_confirm": "Вы уверены? Эта функция удалит все файлы выбранной директории и заменит их на файлы бэкапа.",
        "hard_restored": "Hard Restore выполнен",
        
        # Моды
        "name": "Название",
        "date": "Дата",
        "files": "Файлов",
        "backup_folder": "Папка бэкапа",
        "readme": "Readme",
        "refresh": "Обновить список",
        "open_backup": "Открыть папку бэкапа",
        "open_readme": "Открыть readme",
        "clear_list": "Очистить список",
        "clear_confirm": "Вы уверены? Очищайте список установленных модов только если уверены что делаете. ЭТО НЕ УДАЛИТ УСТАНОВЛЕННЫЕ МОДЫ!",
        
        # О программе
        "about_text": "Mafia Mod Installer v0.7b\n\nУниверсальный установщик модов для Mafia: The City of Lost Heaven\n\nОсобенности:\n• Поддержка ZIP, 7z, RAR архивов\n• Drag & Drop\n• Создание бэкапов\n\n\nАвтор: medved443\nГод: 2026\n\nПуть к папке с данными:\n{}",
        "vk_button": "Перейти в VK группу",
        "version": "Версия v0.7-beta",
        "close": "Закрыть",
        
        # Сообщения
        "first_launch": "Первый запуск",
        "first_launch_msg": "Рекомендуется создать резервную копию чистой игры перед установкой модов.",
        "backup_name": "Название бэкапа:",
        "backup_default": "игра без модов",
        "backup_created": "Создан бэкап: {}",
        "restored": "Восстановлено из бэкапа",
        "cleanup_done": "Очистка завершена",
        "install_complete": "Мод установлен!",
        "bad_archive": "Архив повреждён",
        "error": "Ошибка",
        "installed_files": "Установлено файлов: {}"
    },
    "en": {
        "install_tab": "Install",
        "mods_tab": "Installed Mods",
        "about_tab": "About",
        
        "game": "Game folder:",
        "mod": "Mod / archive:",
        "install": "Install mod",
        "backup": "Create backup",
        "restore": "Restore",
        "cleanup": "Cleanup resources",
        "log": "Log",
        "clear_log": "Clear log",
        "add_game": "Add game",
        "select": "Select",
        "select_mod_folder": "Select mod folder",
        "all_supported": "All supported",
        "zip_archives": "ZIP archives",
        "7z_archives": "7z archives",
        "rar_archives": "RAR archives",
        "all_files": "All files",
        "cleanup_confirm": "Delete unpacked resources?",
        "hard_restore": "Hard Restore",
        "select_backup": "Select backup",
        "confirm_execute": "Confirm and execute?",
        "hard_confirm": "Are you sure? This function will delete all files in the selected directory and replace them with backup files.",
        "hard_restored": "Hard Restore completed",
        
        "name": "Name",
        "date": "Date",
        "files": "Files",
        "backup_folder": "Backup folder",
        "readme": "Readme",
        "refresh": "Refresh list",
        "open_backup": "Open backup folder",
        "open_readme": "Open readme",
        "clear_list": "Clear list",
        "clear_confirm": "Are you sure? Clear the list of installed mods only if you know what you're doing. THIS WILL NOT REMOVE INSTALLED MODS!",
        
        "about_text": "Mafia Mod Installer v0.7-beta\n\nUniversal mod installer for Mafia: The City of Lost Heaven\n\nFeatures:\n• ZIP, 7z, RAR archives support\n• Drag & Drop\n• Backup creation\n\n\nAuthor: medved443 (Assisted by Grok from xAI)\nYear: 2026\n\nPath to data folder:\n{}",
        "vk_button": "Go to VK group",
        "version": "Version v0.7-beta",
        "close": "Close",
        
        "first_launch": "First launch",
        "first_launch_msg": "It is recommended to create a backup of the clean game before installing mods.",
        "backup_name": "Backup name:",
        "backup_default": "clean game",
        "backup_created": "Backup created: {}",
        "restored": "Restored from backup",
        "cleanup_done": "Cleanup completed",
        "install_complete": "Mod installed!",
        "bad_archive": "Archive is corrupted",
        "error": "Error",
        "installed_files": "Installed files: {}"
    },
    "cz": {
        "install_tab": "Instalace",
        "mods_tab": "Nainstalované mody",
        "about_tab": "O aplikaci",
        
        "game": "Složka hry:",
        "mod": "Mod / archiv:",
        "install": "Nainstalovat mod",
        "backup": "Vytvořit zálohu",
        "restore": "Obnovit",
        "cleanup": "Vyčistit zdroje",
        "log": "Log",
        "clear_log": "Vymazat log",
        "add_game": "Přidat hru",
        "select": "Vybrat",
        "select_mod_folder": "Vyberte složku s modem",
        "all_supported": "Všechny podporované",
        "zip_archives": "Archivy ZIP",
        "7z_archives": "Archivy 7z",
        "rar_archives": "Archivy RAR",
        "all_files": "Všechny soubory",
        "cleanup_confirm": "Odstranit rozbalené zdroje?",
        "hard_restore": "Hard Restore",
        "select_backup": "Vyberte zálohu",
        "confirm_execute": "Potvrdit a provést?",
        "hard_confirm": "Jste si jisti? Tato funkce smaže všechny soubory ve vybraném adresáři a nahradí je soubory ze zálohy.",
        "hard_restored": "Hard Restore dokončeno",
        
        "name": "Název",
        "date": "Datum",
        "files": "Souborů",
        "backup_folder": "Složka zálohy",
        "readme": "Readme",
        "refresh": "Obnovit seznam",
        "open_backup": "Otevřít složku zálohy",
        "open_readme": "Otevřít readme",
        "clear_list": "Vymazat seznam",
        "clear_confirm": "Jste si jisti? Vymažte seznam nainstalovaných modů pouze pokud víte, co děláte. TO NEODSTRANÍ NAINSTALOVANÉ MODY!",
        
        "about_text": "Mafia Mod Installer v0.7-beta\n\nUniverzální instalátor modů pro Mafia: The City of Lost Heaven\n\nFunkce:\n• Podpora ZIP, 7z, RAR archivů\n• Drag & Drop\n• Vytváření záloh\n\n\nAutor: medved443 (Assisted by Grok from xAI)\nRok: 2026\n\nCesta k složce s daty:\n{}",
        "vk_button": "Přejít do VK skupiny",
        "version": "Verze v0.7-beta",
        "close": "Zavřít",
        
        "first_launch": "První spuštění",
        "first_launch_msg": "Doporučujeme vytvořit zálohu čisté hry před instalací modů.",
        "backup_name": "Název zálohy:",
        "backup_default": "čistá hra",
        "backup_created": "Záloha vytvořena: {}",
        "restored": "Obnoveno ze zálohy",
        "cleanup_done": "Čištění dokončeno",
        "install_complete": "Mod nainstalován!",
        "bad_archive": "Archiv je poškozen",
        "error": "Chyba",
        "installed_files": "Nainstalováno souborů: {}"
    }
}

def tr(key):
    """Перевод текста"""
    return T[LANG].get(key, key)

# =========================================================
# УТИЛИТЫ
# =========================================================

def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def now_compact():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def load_json(path, default=None):
    if default is None:
        default = [] if "mods.json" in path else {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def safe_copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)

def detect_steam_path():
    path = r"C:\Program Files (x86)\Steam\steamapps\common\Mafia\Mafia"
    return path if os.path.exists(path) else ""

def open_path(path):
    if os.path.exists(path):
        subprocess.Popen(f'explorer "{path}"')

def log_file_write(game_id, text):
    logs_dir = os.path.join(DOCS, game_id, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_path = os.path.join(logs_dir, "log.txt")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(text + "\n")

def first_launch():
    cfg = load_json(CONFIG, {})
    if not cfg.get("launched"):
        messagebox.showinfo(tr("first_launch"), tr("first_launch_msg"))
        cfg["launched"] = True
        save_json(CONFIG, cfg)

def get_game_id(game_path):
    return hashlib.md5(game_path.encode()).hexdigest()[:8]

def get_game_paths(game_id):
    backups = os.path.join(DOCS, game_id, "backups")
    logs = os.path.join(DOCS, game_id, "logs")
    mods_dir = os.path.join(DOCS, game_id, "mods")
    mods_json = os.path.join(DOCS, game_id, "mods.json")
    os.makedirs(backups, exist_ok=True)
    os.makedirs(logs, exist_ok=True)
    os.makedirs(mods_dir, exist_ok=True)
    return backups, logs, mods_dir, mods_json

# =========================================================
# ОПРЕДЕЛЕНИЕ КОРНЯ МОДА
# =========================================================

GAME_DIRS = {"maps", "missions", "models", "sounds", "tables", "textures", "records", "animations"}
GAME_EXTS = (".dta", ".exe", ".dll", ".cfg")

def is_game_like_folder(path):
    """Проверяет, похожа ли папка на корень игры/мода"""
    try:
        entries = os.listdir(path)
        
        # Проверяем наличие типичных папок
        for e in entries:
            full = os.path.join(path, e)
            if os.path.isdir(full) and e.lower() in GAME_DIRS:
                return True
        
        # Проверяем наличие типичных файлов
        for e in entries:
            full = os.path.join(path, e)
            if os.path.isfile(full) and e.lower().endswith(GAME_EXTS):
                return True
    except:
        pass
    
    return False

def detect_root_folder(path):
    """Умное определение корня мода"""
    # Если текущая папка уже подходит
    if is_game_like_folder(path):
        return path
    
    # Ищем внутри (максимальная глубина 3)
    for root, dirs, _ in os.walk(path):
        depth = root.replace(path, "").count(os.sep)
        if depth > 3:
            continue
        
        for d in dirs:
            candidate = os.path.join(root, d)
            if is_game_like_folder(candidate):
                return candidate
    
    # Возвращаем исходную, если ничего не нашли
    return path

# =========================================================
# УСТАНОВКА МОДА
# =========================================================

def backup_replaced_files(game_path, files, backups_dir):
    """Создаёт бэкап файлов, которые будут заменены"""
    stamp = now_compact()
    backup_dir = os.path.join(backups_dir, f"auto_backup_{stamp}")
    
    for f in files:
        target = os.path.join(game_path, f)
        if os.path.exists(target):
            backup_path = os.path.join(backup_dir, f)
            safe_copy(target, backup_path)
    
    return backup_dir

def extract_archive(archive_path, extract_to):
    """Распаковывает архив с поддержкой различных форматов"""
    ext = os.path.splitext(archive_path)[1].lower()
    
    # ZIP
    if ext == ".zip":
        with zipfile.ZipFile(archive_path) as z:
            z.extractall(extract_to)
        return True
    
    # Другие форматы через patoolib
    if PATOOL_AVAILABLE:
        try:
            patoolib.extract_archive(archive_path, outdir=extract_to, verbosity=-1)
            return True
        except:
            pass
    
    return False

def is_readme_file(file):
    lower = file.lower()
    exts = (".txt", ".pdf", ".md", ".rtf", ".doc", ".docx")
    keywords = ["readme", "read me", "читай", "прочитай", "instruk", "instructions", "návod", "guide", "прочти"]
    return lower.endswith(exts) and any(k in lower for k in keywords)

def install_mod(mod_path, game_path, logger, game_id, backups_dir, mods_dir, mods_json_path):
    """Основная функция установки мода"""
    temp_dir = None
    
    try:
        logger("Начало установки...")
        
        # Проверка путей
        if not os.path.exists(game_path):
            raise Exception("Папка игры не найдена")
        
        if not os.path.exists(mod_path):
            raise Exception("Мод не найден")
        
        # Распаковка архива если нужно
        if os.path.isfile(mod_path) and mod_path.lower().endswith(('.zip', '.7z', '.rar', '.tar', '.gz')):
            logger("Распаковка архива...")
            temp_dir = tempfile.mkdtemp()
            
            if not extract_archive(mod_path, temp_dir):
                raise Exception("Не удалось распаковать архив")
            
            mod_root = detect_root_folder(temp_dir)
        else:
            mod_root = detect_root_folder(mod_path)
        
        # Создание поддиректории для мода и копирование всех файлов
        mod_name = os.path.basename(mod_path)
        mod_subdir = os.path.join(mods_dir, f"{mod_name}_{now_compact()}")
        os.makedirs(mod_subdir, exist_ok=True)
        shutil.copytree(mod_root, mod_subdir, dirs_exist_ok=True)
        
        # Сбор файлов для установки
        file_list = []
        
        for root, _, files in os.walk(mod_root):
            for file in files:
                rel = os.path.relpath(os.path.join(root, file), mod_root)
                file_list.append(rel)
        
        if not file_list:
            raise Exception("В моде нет файлов для установки")
        
        # Создание бэкапа
        logger(f"Создание бэкапа {len(file_list)} файлов...")
        backup_dir = backup_replaced_files(game_path, file_list, backups_dir)
        
        # Установка файлов
        logger("Копирование файлов...")
        for rel in file_list:
            src = os.path.join(mod_root, rel)
            dst = os.path.join(game_path, rel)
            safe_copy(src, dst)
        
        # Сохранение в историю
        mods = load_json(mods_json_path, [])
        mods.append({
            "name": mod_name,
            "date": now(),
            "files": len(file_list),
            "backup": backup_dir,
            "readmes_dir": mod_subdir
        })
        save_json(mods_json_path, mods)
        
        logger(tr("installed_files").format(len(file_list)))
        messagebox.showinfo("OK", tr("install_complete"))
        
    except zipfile.BadZipFile:
        messagebox.showerror(tr("error"), tr("bad_archive"))
    except Exception as e:
        messagebox.showerror(tr("error"), str(e))
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)

# =========================================================
# ОЧИСТКА РЕСУРСОВ
# =========================================================

def cleanup_resources(game_path, logger):
    """Удаляет распакованные ресурсы (папки соответствующие .dta файлам)"""
    removed = []
    
    folders_to_clean = [
        "maps", "models", "textures", "scripts", "fonts",
        "missions", "animations", "animations2", "difference", "records",
        "patch", "system", "tables", "music", "animations3"
    ]  # Список всех распаковываемых папок

    for folder in folders_to_clean:
        folder_path = os.path.join(game_path, folder)
        if os.path.isdir(folder_path):
            try:
                shutil.rmtree(folder_path)
                removed.append(folder)
            except Exception as e:
                logger(f"Ошибка при удалении {folder}: {e}")

    if removed:
        logger(f"Удалены папки: {', '.join(removed)}")
    else:
        logger("Папки для удаления не найдены")

# =========================================================
# ГРАФИЧЕСКИЙ ИНТЕРФЕЙС
# =========================================================

class App(TkinterDnD.Tk if DND_AVAILABLE else tk.Tk):
    
    def __init__(self):
        super().__init__()
        
        self.title("Mafia Mod Installer v0.7b by medved443")
        self.geometry("1000x720")
        self.iconbitmap("mmi.ico")  # Добавление иконки
        
        # Глобальные переменные
        self.cfg = load_json(CONFIG, {})
        global LANG
        LANG = self.cfg.get("lang", detect_lang())
        self.lang_var = tk.StringVar(value=LANG)
        
        self.games = self.cfg.get("games", [detect_steam_path()])
        self.current_game = tk.StringVar(value=self.cfg.get("current_game", self.games[0]))
        self.mod_path = tk.StringVar()
        self.mods_data = []
        
        self.game_id = get_game_id(self.current_game.get())
        self.backups_dir, self.logs_dir, self.mods_dir, self.mods_json = get_game_paths(self.game_id)
        
        # Проверка первого запуска
        first_launch()
        
        # Создание интерфейса
        self.create_ui()
        
        # Drag & Drop
        if DND_AVAILABLE:
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self.on_drop)
        
        # Загрузка списка модов
        self.refresh_mods_list()
    
    def save_cfg(self):
        self.cfg["lang"] = LANG
        self.cfg["games"] = self.games
        self.cfg["current_game"] = self.current_game.get()
        save_json(CONFIG, self.cfg)
    
    def change_lang(self, *args):
        global LANG
        LANG = self.lang_var.get()
        self.save_cfg()
        self.rebuild_ui()
    
    def change_game(self, *args):
        self.game_id = get_game_id(self.current_game.get())
        self.backups_dir, self.logs_dir, self.mods_dir, self.mods_json = get_game_paths(self.game_id)
        self.save_cfg()
        self.refresh_mods_list()
    
    def add_game(self):
        path = filedialog.askdirectory(title=tr("game"))
        if path and path not in self.games:
            self.games.append(path)
            self.current_game.set(path)
            self.change_game()
            self.game_combo['values'] = self.games
            self.save_cfg()
    
    def rebuild_ui(self):
        for widget in self.winfo_children():
            widget.destroy()
        self.create_ui()
        self.refresh_mods_list()
    
    # =====================================================
    # ЛОГИРОВАНИЕ
    # =====================================================
    
    def log(self, text):
        """Добавляет сообщение в лог"""
        line = f"[{now()}] {text}"
        self.logbox.insert(tk.END, line + "\n")
        self.logbox.see(tk.END)
        log_file_write(self.game_id, line)
    
    # =====================================================
    # СОЗДАНИЕ ИНТЕРФЕЙСА
    # =====================================================
    
    def create_ui(self):
        """Создаёт вкладки интерфейса"""
        
        # Настройка стиля
        style = ttk.Style(self)
        style.configure("TButton", padding=6)
        style.configure("TLabel", padding=3)
        
        # Верхняя панель для языка и игр
        top_frame = ttk.Frame(self, padding=5)
        top_frame.pack(fill="x")
        
        # Выбор языка
        lang_label = ttk.Label(top_frame, text="Language:")
        lang_label.pack(side="right", padx=5)
        
        self.lang_combo = ttk.Combobox(top_frame, textvariable=self.lang_var, values=["ru", "en", "cz"], state="readonly", width=5)
        self.lang_combo.pack(side="right")
        self.lang_combo.bind("<<ComboboxSelected>>", self.change_lang)
        
        # Основной контейнер
        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)
        
        # Блокнот с вкладками
        notebook = ttk.Notebook(main)
        notebook.pack(fill="both", expand=True)
        
        # Создание вкладок
        self.tab_install = ttk.Frame(notebook, padding=15)
        self.tab_mods = ttk.Frame(notebook, padding=15)
        self.tab_about = ttk.Frame(notebook, padding=15)
        
        notebook.add(self.tab_install, text=tr("install_tab"))
        notebook.add(self.tab_mods, text=tr("mods_tab"))
        notebook.add(self.tab_about, text=tr("about_tab"))
        
        # Заполнение вкладок
        self.build_install_tab()
        self.build_mods_tab()
        self.build_about_tab()
    
    # -----------------------------------------------------
    # ВКЛАДКА УСТАНОВКИ
    # -----------------------------------------------------
    
    def build_install_tab(self):
        """Создаёт интерфейс вкладки установки"""
        f = self.tab_install
        
        # Настройка сетки
        f.columnconfigure(1, weight=1)
        f.rowconfigure(4, weight=1)
        
        # Путь к игре (combobox)
        ttk.Label(f, text=tr("game")).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.game_combo = ttk.Combobox(f, textvariable=self.current_game, values=self.games, state="readonly")
        self.game_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.game_combo.bind("<<ComboboxSelected>>", self.change_game)
        ttk.Button(f, text=tr("add_game"), command=self.add_game).grid(row=0, column=2, padx=5, pady=5)
        
        # Путь к моду
        ttk.Label(f, text=tr("mod")).grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(f, textvariable=self.mod_path).grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(f, text="📂 " + tr("select"), command=self.select_mod).grid(row=1, column=2, padx=5, pady=5)
        
        # Кнопки действий
        btn_frame = ttk.Frame(f)
        btn_frame.grid(row=2, column=0, columnspan=3, pady=15)
        
        ttk.Button(btn_frame, text=tr("install"), command=self.install, width=18).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=tr("backup"), command=self.create_backup, width=18).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=tr("restore"), command=self.restore_backup, width=18).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=tr("cleanup"), command=self.cleanup, width=18).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=tr("hard_restore"), command=self.hard_restore, width=18).pack(side="left", padx=5)
        
        # Лог
        ttk.Label(f, text=tr("log")).grid(row=3, column=0, sticky="w", padx=5, pady=(10,0))
        
        self.logbox = tk.Text(f, height=15, wrap=tk.WORD)
        self.logbox.grid(row=4, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)
        
        # Скроллбар для лога
        scrollbar = ttk.Scrollbar(f, orient="vertical", command=self.logbox.yview)
        scrollbar.grid(row=4, column=3, sticky="ns", pady=5)
        self.logbox.configure(yscrollcommand=scrollbar.set)
        
        # Кнопка очистки лога
        ttk.Button(f, text=tr("clear_log"), command=self.clear_log).grid(row=5, column=1, pady=5)
    
    # -----------------------------------------------------
    # ВКЛАДКА УСТАНОВЛЕННЫХ МОДОВ
    # -----------------------------------------------------
    
    def build_mods_tab(self):
        """Создаёт интерфейс вкладки со списком модов"""
        f = self.tab_mods
        
        # Настройка сетки
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=1)
        
        # Таблица модов
        columns = ("name", "date", "files", "backup", "readme")
        
        self.mods_table = ttk.Treeview(f, columns=columns, show="headings", height=15)
        
        # Настройка колонок
        col_config = [
            ("name", tr("name"), 250),
            ("date", tr("date"), 160),
            ("files", tr("files"), 80),
            ("backup", tr("backup_folder"), 200),
            ("readme", tr("readme"), 200)
        ]
        
        for col_id, col_text, col_width in col_config:
            self.mods_table.heading(col_id, text=col_text)
            self.mods_table.column(col_id, width=col_width)
        
        self.mods_table.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Скроллбар для таблицы
        scrollbar = ttk.Scrollbar(f, orient="vertical", command=self.mods_table.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.mods_table.configure(yscrollcommand=scrollbar.set)
        
        # Кнопки управления
        btn_frame = ttk.Frame(f)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=10)
        
        ttk.Button(btn_frame, text=tr("refresh"), command=self.refresh_mods_list).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=tr("open_backup"), command=self.open_backup).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=tr("open_readme"), command=self.open_readme).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=tr("clear_list"), command=self.clear_mods_list).pack(side="left", padx=5)
        
        # Двойной клик для открытия readme
        self.mods_table.bind("<Double-1>", self.open_readme)
    
    # -----------------------------------------------------
    # ВКЛАДКА О ПРОГРАММЕ
    # -----------------------------------------------------
    
    def build_about_tab(self):
        """Создаёт интерфейс вкладки 'О программе'"""
        f = self.tab_about
        
        # Центрирование содержимого
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=1)
        f.rowconfigure(2, weight=1)
        
        # Информация о программе
        about_frame = ttk.Frame(f, relief="solid", borderwidth=1)
        about_frame.grid(row=1, column=0, padx=50, pady=50, sticky="nsew")
        
        # Заголовок
        title_label = ttk.Label(about_frame, text="Mafia Mod Installer", font=("Arial", 16, "bold"))
        title_label.pack(pady=(30, 10))
        
        # Версия
        version_label = ttk.Label(about_frame, text=tr("version"), font=("Arial", 11))
        version_label.pack(pady=(0, 20))
        
        # Разделитель
        ttk.Separator(about_frame, orient="horizontal").pack(fill="x", padx=40, pady=10)
        
        # Описание
        about_text = tr("about_text").format(DOCS)
        
        text_widget = tk.Text(about_frame, wrap=tk.WORD, height=15, width=60, font=("Arial", 10))
        text_widget.pack(padx=30, pady=20, fill="both", expand=True)
        text_widget.insert("1.0", about_text)
        text_widget.config(state="disabled")  # Делаем текст только для чтения
        
        # Кнопка VK
        ttk.Button(about_frame, text=tr("vk_button"), command=lambda: webbrowser.open("https://vk.com/mafia_and_mafia2_modding")).pack(pady=10)
        
        # Кнопка закрытия
        ttk.Button(about_frame, text=tr("close"), command=lambda: self.focus()).pack(pady=(0, 20))
    
    # =====================================================
    # ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ
    # =====================================================
    
    def select_mod(self):
        """Выбор мода (файл или папка)"""
        # Сначала предлагаем выбрать файл
        path = filedialog.askopenfilename(
            title=tr("mod"),
            filetypes=[
                (tr("all_supported"), "*.zip;*.7z;*.rar;*.tar;*.gz"),
                (tr("zip_archives"), "*.zip"),
                (tr("7z_archives"), "*.7z"),
                (tr("rar_archives"), "*.rar"),
                (tr("all_files"), "*.*")
            ]
        )
        
        # Если файл не выбран, предлагаем папку
        if not path:
            path = filedialog.askdirectory(title=tr("select_mod_folder"))
        
        if path:
            self.mod_path.set(path)
    
    def install(self):
        """Установка мода"""
        install_mod(self.mod_path.get(), self.current_game.get(), self.log, self.game_id, self.backups_dir, self.mods_dir, self.mods_json)
        self.refresh_mods_list()
    
    def create_backup(self):
        """Создание резервной копии"""
        name = simpledialog.askstring(tr("backup"), tr("backup_name"), 
                                      initialvalue=tr("backup_default"))
        if not name:
            return
        
        try:
            backup_path = os.path.join(self.backups_dir, name)
            shutil.copytree(self.current_game.get(), backup_path)
            self.log(tr("backup_created").format(name))
            messagebox.showinfo("OK", tr("backup_created").format(name))
        except Exception as e:
            messagebox.showerror(tr("error"), str(e))
    
    def restore_backup(self):
        """Восстановление из резервной копии"""
        path = filedialog.askdirectory(initialdir=self.backups_dir, title=tr("restore"))
        if path:
            try:
                shutil.copytree(path, self.current_game.get(), dirs_exist_ok=True)
                self.log(tr("restored"))
                messagebox.showinfo("OK", tr("restored"))
            except Exception as e:
                messagebox.showerror(tr("error"), str(e))
    

    def hard_restore(self):
        """Жёсткое восстановление: удаляет всё в папке игры и заменяет на бэкап"""
        backup_path = filedialog.askdirectory(initialdir=self.backups_dir, title=tr("select_backup"))
        if not backup_path:
            return  # Отмена
        
        # Первое подтверждение
        if not messagebox.askyesno(tr("confirm_execute"), tr("confirm_execute")):
            return  # Отмена
        
        # Финальное подтверждение
        if not messagebox.askyesno(tr("hard_confirm"), tr("hard_confirm")):
            return  # Отмена
        
        game_path = self.current_game.get()
        try:
            # Удаление всего содержимого game_path
            for item in os.listdir(game_path):
                item_path = os.path.join(game_path, item)
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            
            # Копирование из бэкапа
            shutil.copytree(backup_path, game_path, dirs_exist_ok=True)
            
            self.log(tr("hard_restored") + " из " + backup_path)
            messagebox.showinfo("OK", tr("hard_restored"))
        except Exception as e:
            messagebox.showerror(tr("error"), str(e))

    def cleanup(self):
        """Очистка ресурсов"""
        if messagebox.askyesno(tr("cleanup"), tr("cleanup_confirm")):
            cleanup_resources(self.current_game.get(), self.log)
            self.log(tr("cleanup_done"))
    
    def clear_log(self):
        """Очистка лога"""
        self.logbox.delete("1.0", tk.END)
    
    # =====================================================
    # РАБОТА СО СПИСКОМ МОДОВ
    # =====================================================
    
    def refresh_mods_list(self):
        """Обновление списка установленных модов"""
        # Очистка таблицы
        for row in self.mods_table.get_children():
            self.mods_table.delete(row)
        
        # Загрузка данных
        self.mods_data = load_json(self.mods_json, [])
        
        # Заполнение таблицы
        for mod in self.mods_data:
            mod_dir = mod.get("readmes_dir", "")
            readme_names = ", ".join([os.path.relpath(os.path.join(root, file), mod_dir) 
                                      for root, _, files in os.walk(mod_dir) 
                                      for file in files if is_readme_file(file)])
            self.mods_table.insert("", "end", values=(
                mod["name"],
                mod["date"],
                mod["files"],
                os.path.basename(mod["backup"]),
                readme_names
            ))
    
    def clear_mods_list(self):
        if messagebox.askyesno("Confirm", tr("clear_confirm")):
            save_json(self.mods_json, [])
            self.refresh_mods_list()
    
    def get_selected_mod(self):
        """Возвращает выбранный мод"""
        selection = self.mods_table.selection()
        if not selection:
            return None
        
        index = self.mods_table.index(selection[0])
        if 0 <= index < len(self.mods_data):
            return self.mods_data[index]
        return None
    
    def open_readme(self, event=None):
        """Открывает папку с readme файлами"""
        mod = self.get_selected_mod()
        if mod and mod.get("readmes_dir"):
            open_path(mod["readmes_dir"])
        else:
            messagebox.showinfo("Info", "Readme файлы не найдены")
    
    def open_backup(self):
        """Открывает папку с бэкапом"""
        mod = self.get_selected_mod()
        if mod:
            open_path(mod["backup"])
    
    # =====================================================
    # DRAG & DROP
    # =====================================================
    
    def on_drop(self, event):
        """Обработка перетаскивания файла"""
        # Очистка от лишних символов
        path = event.data.strip("{}")
        self.mod_path.set(path)

# =========================================================
# ЗАПУСК
# =========================================================

if __name__ == "__main__":
    app = App()
    app.mainloop()
