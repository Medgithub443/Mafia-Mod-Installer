# =========================================================
# Mafia Mod Installer v0.14
# main.py — точка входа и GUI
#
# Бизнес-логика разнесена по модулям:
#   mmi_paths.py       — пути и константы
#   mmi_lang.py        — переводы
#   mmi_utils.py       — общие утилиты, README-детект
#   mmi_mods.py        — библиотека модов и .mmi
#   mmi_instances.py   — экземпляры игры
#   mmi_installer.py   — установка/откат/cleanup/patch_dll
#   mmi_saves.py       — savegame backup/restore
#   mmi_logo.py        — генерация logo1.avi через bundled logoMaker.exe
#   mmi_service.py     — revert all/one, find duplicates, troubleshooter
#   mmi_version.py     — детекция версии игры (LS3DF.dll)
#   mmi_gui.py         — иконки и обёртки messagebox
# =========================================================

import datetime
import os
import subprocess
import sys
import webbrowser
import zipfile
import shutil

import tkinter as tk
from tkinter import ttk, filedialog, simpledialog

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False
    TkinterDnD = tk

from mmi_paths import (PATHS, DATA, APP_NAME, APP_VERSION,
                       DEFAULT_SETTINGS, DEFAULT_PRIORITY,
                       DEFAULT_RECOMMENDED_COUNT, MMI_README_LIMIT,
                       GAME_VERSIONS, res_path)
from mmi_lang import (LANGS, load_languages, detect_lang, set_lang, tr,
                       add_language_file)
from mmi_utils import (load_json, save_json, slugify, open_path,
                       detect_steam_path, find_readmes, append_log, now)
from mmi_mods import (add_mod_to_library, remove_mod_from_library,
                      update_mod_field, build_mmi, mod_has_saves)
from mmi_instances import (get_instance_paths, find_instance,
                           upsert_instance, update_instance,
                           estimate_clean_backup_size_bytes,
                           forget_instance)
from mmi_installer import (cleanup_resources, hard_restore_from,
                           install_mods_into_game, patch_rw_data_dll)
from mmi_saves import (make_saves_backup, restore_saves_backup,
                       delete_saves_backup, delete_saves_backups,
                       saves_folder)
from mmi_logo import update_logo_in_game, clear_logo_cache
from mmi_service import (revert_all_instances, revert_one_instance,
                         find_duplicate_mods, troubleshoot_scope,
                         build_troubleshooter_report)
from mmi_version import (detect_game_version, is_rw_data_patched,
                          detect_widescreen_fix, is_mafia_game_folder)
from mmi_dta import (compute_dtas_for_dirs, extract_dtas,
                     is_available as dta_cli_available)
from mmi_cache import (cache_sounds_from_folder, apply_sounds_cache,
                       cache_status as sounds_cache_status,
                       clear_cache as sounds_clear_cache)
from mmi_finder import scan as scan_for_games
from mmi_gui import apply_icon, info_box, error_box, yesno, yesnocancel


# =========================================================
class App(TkinterDnD.Tk if DND_AVAILABLE else tk.Tk):

    def __init__(self):
        super().__init__()
        load_languages()

        self.cfg = load_json(PATHS["config"], {})
        lang = self.cfg.get("lang", detect_lang())
        if lang not in LANGS:
            lang = "en" if "en" in LANGS else next(iter(LANGS), "en")
        set_lang(lang)

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1140x720")
        self.minsize(980, 640)
        apply_icon(self)

        self.lang_var = tk.StringVar(value=lang)
        self.settings = dict(DEFAULT_SETTINGS)
        self.settings.update(self.cfg.get("settings", {}))

        self.upload_path = tk.StringVar()
        self.upload_name = tk.StringVar()
        self.upload_priority = tk.IntVar(value=DEFAULT_PRIORITY)

        self.instances = load_json(PATHS["instances_json"], [])
        if not self.instances:
            steam = detect_steam_path()
            if steam:
                upsert_instance(steam)
                self.instances = load_json(PATHS["instances_json"], [])

        cur_id = self.cfg.get("current_instance")
        if cur_id and find_instance(self.instances, cur_id):
            self.current_instance_id = cur_id
        elif self.instances:
            self.current_instance_id = self.instances[0]["id"]
        else:
            self.current_instance_id = None

        self._first_launch_check()
        self._auto_widescreen_detect()
        self.create_menu()
        self.create_ui()

        if DND_AVAILABLE:
            try:
                self.drop_target_register(DND_FILES)
                self.dnd_bind("<<Drop>>", self.on_drop)
            except Exception:
                pass

        self.refresh_all()

    @property
    def instance(self):
        return find_instance(self.instances, self.current_instance_id)

    def _auto_widescreen_detect(self):
        """Если включено `auto_widescreen_detect`, и в ХОТЯ БЫ одном
        зарегистрированном экземпляре найден Mafia.WidescreenFix —
        автоматически включаем настройку `widescreen` (использовать
        widescreen-фикс при построении логотипа). Если нет ни в одном —
        не трогаем выбор пользователя.
        """
        if not self.settings.get("auto_widescreen_detect", True):
            return
        any_found = False
        for inst in self.instances:
            try:
                if detect_widescreen_fix(inst.get("path", ""))["present"]:
                    any_found = True
                    break
            except Exception:
                continue
        if any_found and not self.settings.get("widescreen", False):
            self.settings["widescreen"] = True
            self.save_cfg()

    def save_cfg(self):
        from mmi_lang import LANG
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
        if not self.cfg.get("launched"):
            self.cfg["launched"] = True
            self.save_cfg()
        inst = self.instance
        if not inst:
            return
        # Свежий, ни разу не виденный экземпляр (нет clean_backup и нет
        # отметки pending) — это первый показ, спрашиваем сразу.
        # Иначе — тихо обновляем флаг has_clean_backup, если бэкап успели
        # сделать снаружи.
        first_seen = (not inst.get("has_clean_backup")
                      and not inst.get("pending_clean_backup"))
        self._ensure_clean_backup(prompt=first_seen)

    def _human_bytes(self, n: int) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if n < 1024 or unit == "TB":
                return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
            n /= 1024.0
        return f"{n:.1f} TB"

    def _make_clean_backup_now(self, inst: dict) -> bool:
        """Создаёт clean_backup. Возвращает True/False."""
        clean = get_instance_paths(inst["id"])["clean"]
        try:
            if os.path.isdir(clean):
                shutil.rmtree(clean, ignore_errors=True)
            shutil.copytree(inst["path"], clean)
            inst["has_clean_backup"] = True
            inst["pending_clean_backup"] = False
            update_instance(inst)
            self._log_safe(tr("clean_backup_created"))
            return True
        except Exception as e:
            error_box(self, tr("error"), str(e))
            return False

    def _ensure_clean_backup(self, prompt=True):
        """Проверяет/создаёт clean_backup для текущего экземпляра.

        Поведение v0.16:
          • Если clean_backup уже есть — отмечаем флаг и выходим.
          • Если нет и prompt=True — показываем диалог OK / Позже с
            оценкой размера. OK → делаем сразу, Позже → ставим флаг
            `pending_clean_backup=True`; install_to_game повторно
            спросит. Без prompt — просто ставим флаг pending.
        """
        inst = self.instance
        if not inst or not os.path.isdir(inst["path"]):
            return
        clean = get_instance_paths(inst["id"])["clean"]
        if os.path.isdir(clean) and os.listdir(clean):
            inst["has_clean_backup"] = True
            inst["pending_clean_backup"] = False
            update_instance(inst)
            return

        if not prompt:
            inst["pending_clean_backup"] = True
            update_instance(inst)
            return

        size = estimate_clean_backup_size_bytes(inst["path"])
        msg = tr("clean_backup_required_msg").format(self._human_bytes(size))
        if yesno(self, tr("clean_backup_required_title"), msg,
                 yes_text=tr("ok"), no_text=tr("btn_later")):
            self._make_clean_backup_now(inst)
        else:
            inst["pending_clean_backup"] = True
            update_instance(inst)
            self._log_safe(tr("clean_backup_postponed"))

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

        m_service = tk.Menu(menubar, tearoff=0)
        m_service.add_command(label=tr("menu_service_open"),
                              command=self.open_service_dialog)
        menubar.add_cascade(label=tr("menu_service"), menu=m_service)

        m_help = tk.Menu(menubar, tearoff=0)
        m_help.add_command(label=tr("menu_help_open"), command=self.open_help)
        menubar.add_cascade(label=tr("menu_help"), menu=m_help)

        m_about = tk.Menu(menubar, tearoff=0)
        # «О программе» в v0.16 переоткрывает help.html (по промпту).
        m_about.add_command(label=tr("menu_about"),
                            command=self.open_help)
        menubar.add_cascade(label=tr("menu_about"), menu=m_about)

        self.config(menu=menubar)

    def open_help(self):
        path = res_path(os.path.join("assets", "help.html"))
        if os.path.exists(path):
            webbrowser.open("file://" + os.path.abspath(path))
        else:
            error_box(self, tr("error"), "help.html not found")

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
        # Бывшее 560x540 — расширил по вертикали и горизонтали:
        # тексты с длинными словами не обрезаются.
        win.geometry("780x720")
        win.transient(self)
        win.resizable(True, True)
        win.minsize(680, 600)
        apply_icon(win)

        s = self.settings
        v_logo = tk.BooleanVar(value=s.get("insert_logo", True))
        v_widescreen = tk.BooleanVar(value=s.get("widescreen", False))
        v_compress = tk.BooleanVar(value=s.get("compress_backups", False))
        v_compress_lvl = tk.IntVar(value=s.get("compress_level", 5))
        v_conflict = tk.BooleanVar(value=s.get("conflict_check", False))
        v_immutable = tk.BooleanVar(value=s.get("immutable_saves", True))
        v_auto_backup = tk.BooleanVar(value=s.get("auto_backup_saves", True))
        v_autodetect_tv = tk.BooleanVar(
            value=s.get("experimental_autodetect_target_version", False))
        v_alt_logo = tk.BooleanVar(value=s.get("use_alt_logo", False))
        v_auto_ws = tk.BooleanVar(
            value=s.get("auto_widescreen_detect", True))
        v_recommend_on = tk.BooleanVar(value=s.get("recommended_count_on", True))
        v_recommend_n = tk.IntVar(
            value=s.get("recommended_count", DEFAULT_RECOMMENDED_COUNT))

        body = ttk.Frame(win, padding=18)
        body.pack(fill="both", expand=True)

        ttk.Checkbutton(body, text=tr("settings_insert_logo"),
                        variable=v_logo).pack(anchor="w", pady=4)
        ttk.Checkbutton(body, text=tr("settings_widescreen"),
                        variable=v_widescreen).pack(anchor="w", pady=4)
        ttk.Checkbutton(body, text=tr("settings_conflict_check"),
                        variable=v_conflict).pack(anchor="w", pady=4)
        ttk.Checkbutton(body, text=tr("settings_immutable_saves"),
                        variable=v_immutable).pack(anchor="w", pady=4)
        ttk.Checkbutton(body, text=tr("settings_auto_backup_saves"),
                        variable=v_auto_backup).pack(anchor="w", pady=4)
        ttk.Checkbutton(
            body, text=tr("settings_experimental_autodetect_target_version"),
            variable=v_autodetect_tv).pack(anchor="w", pady=4)
        ttk.Checkbutton(body, text=tr("settings_use_alt_logo"),
                        variable=v_alt_logo).pack(anchor="w", pady=4)
        ttk.Checkbutton(body, text=tr("settings_auto_widescreen_detect"),
                        variable=v_auto_ws).pack(anchor="w", pady=4)

        rcrow = ttk.Frame(body)
        rcrow.pack(anchor="w", pady=6, fill="x")
        ttk.Checkbutton(rcrow, text=tr("settings_recommended_count_on"),
                        variable=v_recommend_on).pack(side="left")
        ttk.Label(rcrow, text=tr("settings_recommended_count_value")).pack(
            side="left", padx=(20, 4))
        ttk.Spinbox(rcrow, from_=1, to=99, textvariable=v_recommend_n,
                    width=4).pack(side="left")

        cmprow = ttk.Frame(body)
        cmprow.pack(anchor="w", pady=6, fill="x")
        ttk.Checkbutton(cmprow, text=tr("settings_compress_backups"),
                        variable=v_compress).pack(side="left")
        ttk.Label(cmprow, text=tr("settings_compress_level")).pack(
            side="left", padx=(20, 4))
        ttk.Combobox(cmprow, textvariable=v_compress_lvl,
                     values=[1, 3, 5, 7], state="readonly",
                     width=4).pack(side="left")

        ttk.Separator(body).pack(fill="x", pady=14)

        btns = ttk.Frame(body)
        btns.pack(anchor="w", pady=4, fill="x")
        ttk.Button(btns, text=tr("patch_dll"),
                   command=lambda: self.patch_dll(parent=win)).pack(
            side="left", padx=4)
        ttk.Button(btns, text=tr("settings_clear_cache"),
                   command=lambda: self._clear_cache_action(parent=win)).pack(
            side="left", padx=4)

        bar = ttk.Frame(win)
        bar.pack(side="bottom", pady=14)

        def do_save():
            self.settings["insert_logo"] = v_logo.get()
            self.settings["widescreen"] = v_widescreen.get()
            self.settings["compress_backups"] = v_compress.get()
            self.settings["compress_level"] = int(v_compress_lvl.get())
            self.settings["conflict_check"] = v_conflict.get()
            self.settings["immutable_saves"] = v_immutable.get()
            self.settings["auto_backup_saves"] = v_auto_backup.get()
            self.settings["experimental_autodetect_target_version"] = v_autodetect_tv.get()
            self.settings["use_alt_logo"] = v_alt_logo.get()
            self.settings["auto_widescreen_detect"] = v_auto_ws.get()
            self.settings["recommended_count_on"] = v_recommend_on.get()
            try:
                self.settings["recommended_count"] = max(
                    1, int(v_recommend_n.get()))
            except Exception:
                self.settings["recommended_count"] = DEFAULT_RECOMMENDED_COUNT
            self.save_cfg()
            win.destroy()

        ttk.Button(bar, text=tr("settings_save"),
                   command=do_save).pack(side="left", padx=10)
        ttk.Button(bar, text=tr("settings_cancel"),
                   command=win.destroy).pack(side="left", padx=10)

    def _clear_cache_action(self, parent=None):
        n = clear_logo_cache()
        info_box(parent or self, tr("info"),
                 f"{tr('settings_clear_cache_done')} ({n})")

    # ---------- Service ----------
    def open_service_dialog(self):
        win = tk.Toplevel(self)
        win.title(tr("service_title"))
        win.geometry("560x520")
        win.transient(self)
        apply_icon(win)

        body = ttk.Frame(win, padding=14)
        body.pack(fill="both", expand=True)

        ttk.Button(body, text=tr("service_revert_one"),
                   command=lambda: self._service_revert_one(win)).pack(
            fill="x", pady=4)
        ttk.Button(body, text=tr("service_revert_all"),
                   command=lambda: self._service_revert_all(win)).pack(
            fill="x", pady=4)
        ttk.Button(body, text=tr("service_find_dupes"),
                   command=lambda: self._service_find_dupes(win)).pack(
            fill="x", pady=4)
        ttk.Button(body, text=tr("service_troubleshoot"),
                   command=lambda: self._service_troubleshoot(win)).pack(
            fill="x", pady=4)
        ttk.Separator(body, orient="horizontal").pack(fill="x", pady=6)
        ttk.Button(body, text=tr("service_instance_finder"),
                   command=lambda: self._service_instance_finder(win)).pack(
            fill="x", pady=4)
        ttk.Button(body, text=tr("service_manage_instances"),
                   command=lambda: self._service_manage_instances(win)).pack(
            fill="x", pady=4)
        ttk.Button(body, text=tr("service_cache_sounds"),
                   command=lambda: self._service_cache_sounds(win)).pack(
            fill="x", pady=4)
        ttk.Button(body, text=tr("close"),
                   command=win.destroy).pack(side="bottom", pady=10)

    def _service_revert_one(self, parent):
        inst = self.instance
        if not inst:
            return
        if not yesno(parent, tr("service_revert_one"),
                     tr("service_revert_one_confirm").format(inst["name"])):
            return
        ok = revert_one_instance(inst, self.log)
        if ok:
            info_box(parent, tr("info"),
                     tr("service_revert_one_done").format(inst["name"]))
            self.instances = load_json(PATHS["instances_json"], [])
            self.refresh_all()

    def _service_revert_all(self, parent):
        if not self.instances:
            return
        if not yesno(parent, tr("service_title"),
                     tr("service_revert_all_confirm1")):
            return
        if not yesno(parent, tr("service_title"),
                     tr("service_revert_all_confirm2").format(len(self.instances))):
            return
        n = revert_all_instances(self.log)
        info_box(parent, tr("info"), tr("service_revert_all_done").format(n))
        self.instances = load_json(PATHS["instances_json"], [])
        self.refresh_all()

    def _service_find_dupes(self, parent):
        dupes = find_duplicate_mods()
        if not dupes:
            info_box(parent, tr("info"), tr("service_no_dupes"))
            return
        lines = []
        for cs, lst in dupes.items():
            names = " | ".join(m.get("name") or m["id"] for m in lst)
            lines.append(f"  {cs[:12]}…  {names}")
        info_box(parent, tr("info"),
                 tr("service_dupes_found").format("\n".join(lines)))

    # ---------- Troubleshooter wizard ----------
    def _service_troubleshoot(self, parent):
        win = tk.Toplevel(parent)
        win.title(tr("service_troubleshoot"))
        win.geometry("680x520")
        win.transient(parent)
        apply_icon(win)

        body = ttk.Frame(win, padding=16)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text=tr("ts_step1_title"),
                  font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 6))
        ttk.Label(body, text=tr("ts_step1_hint")).pack(anchor="w", pady=(0, 8))

        scope_var = tk.StringVar(value="active_in_game")
        ttk.Radiobutton(body, text=tr("ts_scope_active"),
                        variable=scope_var, value="active_in_game").pack(
            anchor="w", pady=2)
        ttk.Radiobutton(body, text=tr("ts_scope_one_mod"),
                        variable=scope_var, value="one_mod").pack(
            anchor="w", pady=2)

        ttk.Label(body, text=tr("ts_pick_mod")).pack(anchor="w", pady=(8, 2))
        all_mods = load_json(PATHS["mods_json"], [])
        choices = [(m.get("name") or m["id"]) for m in all_mods]
        mod_var = tk.StringVar(value=choices[0] if choices else "")
        cb = ttk.Combobox(body, textvariable=mod_var, values=choices,
                          state="readonly")
        cb.pack(fill="x", pady=2)

        out = tk.Text(body, wrap=tk.WORD, height=14)
        out.pack(fill="both", expand=True, pady=(10, 4))
        out.config(state="disabled")

        def _print(line):
            out.config(state="normal")
            out.insert(tk.END, line + "\n")
            out.config(state="disabled")
            out.see(tk.END)

        def _run():
            out.config(state="normal")
            out.delete("1.0", tk.END)
            out.config(state="disabled")
            inst = self.instance
            scope = scope_var.get()
            if scope == "one_mod":
                name = mod_var.get()
                target = next((m for m in all_mods
                               if (m.get("name") or m["id"]) == name), None)
                if not target:
                    _print(tr("ts_no_active"))
                    return
                reports = troubleshoot_scope("one_mod", target["id"], inst)
            else:
                if not inst or not inst.get("active_mods"):
                    _print(tr("ts_no_active"))
                    return
                reports = troubleshoot_scope("active_in_game", None, inst)

            _print("=== " + tr("ts_report_title") + " ===")
            any_issue = False
            for r in reports:
                _print(f"\n[{r['name']}]")
                for issue in r["issues"]:
                    k = issue.get("kind")
                    if k == "ok":
                        _print("  ✓ " + tr("ts_no_problems"))
                        continue
                    any_issue = True
                    if k == "version_mismatch":
                        _print("  ✗ " + tr("ts_issue_version_mismatch").format(
                            mod_version=issue["mod_version"],
                            game_version=issue["game_version"]))
                    elif k == "rw_data_unpatched":
                        _print("  ✗ " + tr("ts_issue_rw_unpatched"))
                    elif k == "standalone_installer":
                        _print("  ✗ " + tr("ts_issue_standalone").format(
                            files=", ".join(issue["files"])))
                    elif k == "no_resource_dirs":
                        _print("  ✗ " + tr("ts_issue_no_dirs"))
                for rec in r["recommendations"]:
                    _print("    → " + rec)
            if any_issue:
                _print("\n" + tr("ts_help_links"))

        last_ctx = {"scope": None, "mod_id": None}

        def _run_and_track():
            inst = self.instance
            scope = scope_var.get()
            mod_id = None
            if scope == "one_mod":
                name = mod_var.get()
                target = next((m for m in all_mods
                               if (m.get("name") or m["id"]) == name), None)
                if target:
                    mod_id = target["id"]
            last_ctx["scope"] = scope
            last_ctx["mod_id"] = mod_id
            _run()

        def _build_report_text():
            if not last_ctx["scope"]:
                _run_and_track()
            return build_troubleshooter_report(
                last_ctx["scope"], last_ctx["mod_id"], self.instance)

        def _save_report():
            text = _build_report_text()
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = filedialog.asksaveasfilename(
                parent=win, title=tr("ts_report_btn"),
                defaultextension=".txt",
                initialfile=f"mmi_report_{ts}.txt",
                filetypes=[("Text files", "*.txt")])
            if not path:
                return
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                info_box(win, tr("ok"),
                         tr("ts_report_saved").format(path))
            except Exception as e:
                error_box(win, tr("error"), str(e))

        def _copy_report():
            text = _build_report_text()
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
            info_box(win, tr("ok"), tr("ts_report_copied"))

        row = ttk.Frame(body)
        row.pack(fill="x", pady=(4, 0))
        ttk.Button(row, text=tr("ts_run"),
                   command=_run_and_track).pack(side="left", padx=2)
        ttk.Button(row, text=tr("ts_report_btn"),
                   command=_save_report).pack(side="left", padx=2)
        ttk.Button(row, text=tr("ts_report_clipboard"),
                   command=_copy_report).pack(side="left", padx=2)
        ttk.Button(row, text=tr("close"),
                   command=win.destroy).pack(side="right", padx=2)

    # ---------- Instance Finder ----------
    def _service_instance_finder(self, parent):
        win = tk.Toplevel(parent)
        win.title(tr("service_instance_finder"))
        win.geometry("780x560")
        win.transient(parent)
        apply_icon(win)

        body = ttk.Frame(win, padding=14)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text=tr("finder_hint"),
                  wraplength=720, foreground="gray").pack(
            anchor="w", pady=(0, 8))

        mode_var = tk.StringVar(value="auto")
        modes = ttk.Frame(body)
        modes.pack(anchor="w", pady=4)
        ttk.Radiobutton(modes, text=tr("finder_mode_auto"),
                        variable=mode_var, value="auto").pack(
            side="left", padx=4)
        ttk.Radiobutton(modes, text=tr("finder_mode_full"),
                        variable=mode_var, value="full").pack(
            side="left", padx=4)
        ttk.Radiobutton(modes, text=tr("finder_mode_selective"),
                        variable=mode_var, value="selective").pack(
            side="left", padx=4)

        log_frame = ttk.LabelFrame(body, text=tr("finder_log"))
        log_frame.pack(fill="both", expand=True, pady=8)
        log_box = tk.Text(log_frame, height=8, wrap=tk.WORD)
        log_box.pack(fill="both", expand=True, padx=4, pady=4)
        log_box.config(state="disabled")

        def log(line):
            log_box.config(state="normal")
            log_box.insert(tk.END, line + "\n")
            log_box.config(state="disabled")
            log_box.see(tk.END)
            win.update_idletasks()

        result_frame = ttk.LabelFrame(body, text=tr("finder_results"))
        result_frame.pack(fill="both", expand=True, pady=8)
        cols = ("name", "version", "path")
        tree = ttk.Treeview(result_frame, columns=cols, show="headings",
                            height=6, selectmode="browse")
        for cid, txt, w in [("name", tr("finder_col_name"), 160),
                            ("version", tr("game_version_title"), 80),
                            ("path", tr("finder_col_path"), 480)]:
            tree.heading(cid, text=txt)
            tree.column(cid, width=w)
        tree.pack(fill="both", expand=True, padx=4, pady=4)

        found = []  # list of dicts

        def populate():
            for r in tree.get_children():
                tree.delete(r)
            for i, g in enumerate(found):
                tree.insert("", "end", iid=str(i),
                            values=(g["name"], g["version"], g["path"]))

        def start_scan():
            log_box.config(state="normal")
            log_box.delete("1.0", tk.END)
            log_box.config(state="disabled")
            found.clear()
            populate()
            mode = mode_var.get()
            custom = ""
            if mode == "selective":
                custom = filedialog.askdirectory(parent=win,
                                                 title=tr("finder_pick_dir"))
                if not custom:
                    return
            try:
                results = scan_for_games(mode, custom_path=custom, on_log=log)
            except Exception as e:
                error_box(win, tr("error"), str(e))
                return
            found.extend(results)
            populate()
            log(tr("finder_done").format(len(results)))

        def open_folder():
            sel = tree.selection()
            if not sel:
                return
            g = found[int(sel[0])]
            open_path(g["path"])

        def add_instance():
            sel = tree.selection()
            if not sel:
                return
            g = found[int(sel[0])]
            inst = upsert_instance(g["path"])
            self.instances = load_json(PATHS["instances_json"], [])
            self.current_instance_id = inst["id"]
            self.save_cfg()
            self.refresh_all()
            # Триггерим диалог OK / Позже (пункт 4 промпта)
            self._ensure_clean_backup(prompt=True)
            info_box(win, tr("ok"),
                     tr("finder_added").format(g["path"]))

        bf = ttk.Frame(body)
        bf.pack(fill="x", pady=(6, 0))
        ttk.Button(bf, text=tr("finder_start"),
                   command=start_scan).pack(side="left", padx=4)
        ttk.Button(bf, text=tr("finder_open_folder"),
                   command=open_folder).pack(side="left", padx=4)
        ttk.Button(bf, text=tr("finder_add_instance"),
                   command=add_instance).pack(side="left", padx=4)
        ttk.Button(bf, text=tr("close"),
                   command=win.destroy).pack(side="right", padx=4)

    # ---------- Manage Instances ----------
    def _service_manage_instances(self, parent):
        win = tk.Toplevel(parent)
        win.title(tr("service_manage_instances"))
        win.geometry("760x440")
        win.transient(parent)
        apply_icon(win)

        body = ttk.Frame(win, padding=14)
        body.pack(fill="both", expand=True)

        cols = ("name", "version", "path")
        tree = ttk.Treeview(body, columns=cols, show="headings",
                            height=10, selectmode="browse")
        for cid, txt, w in [("name", tr("finder_col_name"), 160),
                            ("version", tr("game_version_title"), 80),
                            ("path", tr("finder_col_path"), 480)]:
            tree.heading(cid, text=txt)
            tree.column(cid, width=w)
        tree.pack(fill="both", expand=True, pady=4)

        def populate():
            for r in tree.get_children():
                tree.delete(r)
            for inst in self.instances:
                v = detect_game_version(inst.get("path", "")).get("version") \
                    or "?"
                tree.insert("", "end", iid=inst["id"],
                            values=(inst.get("name", inst["id"]), v,
                                    inst.get("path", "")))

        def get_selected():
            sel = tree.selection()
            if not sel:
                return None
            return find_instance(self.instances, sel[0])

        def do_open():
            inst = get_selected()
            if not inst:
                return
            open_path(inst.get("path", ""))

        def do_check_version():
            inst = get_selected()
            if not inst:
                return
            info = detect_game_version(inst.get("path", ""))
            ver = info.get("version") or tr("game_version_unknown")
            info_box(win, tr("game_version_title"),
                     f"{inst.get('name')}: {ver}\n{inst.get('path', '')}")

        def do_forget():
            inst = get_selected()
            if not inst:
                return
            if not yesno(win, tr("service_manage_instances"),
                         tr("manage_forget_confirm").format(
                             inst.get("name", inst["id"]))):
                return
            if forget_instance(inst["id"]):
                self.instances = load_json(PATHS["instances_json"], [])
                if self.current_instance_id == inst["id"]:
                    self.current_instance_id = (
                        self.instances[0]["id"] if self.instances else None)
                    self.save_cfg()
                self.refresh_all()
                populate()
                info_box(win, tr("ok"),
                         tr("manage_forgotten").format(
                             inst.get("name", inst["id"])))

        bf = ttk.Frame(body)
        bf.pack(fill="x", pady=8)
        ttk.Button(bf, text=tr("manage_open_path"),
                   command=do_open).pack(side="left", padx=4)
        ttk.Button(bf, text=tr("manage_check_version"),
                   command=do_check_version).pack(side="left", padx=4)
        ttk.Button(bf, text=tr("manage_forget"),
                   command=do_forget).pack(side="left", padx=4)
        ttk.Button(bf, text=tr("close"),
                   command=win.destroy).pack(side="right", padx=4)

        populate()

    # ---------- Cache Sounds ----------
    def _service_cache_sounds(self, parent):
        """Кэширование папки sounds/ во внутренний кэш MMI и применение
        к выбранному экземпляру.

        Это НЕ распаковка .dta — у лицензий вырезанные треки изначально
        отсутствуют в файлах игры, поэтому распаковывать нечего.
        Нужен внешний источник (диск, старая инсталляция, бэкап).
        """
        win = tk.Toplevel(parent)
        win.title(tr("service_cache_sounds"))
        win.geometry("760x560")
        win.transient(parent)
        apply_icon(win)

        body = ttk.Frame(win, padding=14)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text=tr("cache_sounds_title"),
                  font=("Arial", 13, "bold")).pack(anchor="w")
        ttk.Label(body, text=tr("cache_sounds_explainer"),
                  wraplength=720, justify="left",
                  foreground="#cccccc").pack(anchor="w", pady=(4, 8))
        ttk.Label(body, text=tr("cache_sounds_advice"),
                  wraplength=720, justify="left",
                  foreground="#9aa0a6").pack(anchor="w", pady=(0, 12))

        # Текущее состояние кэша
        status_frame = ttk.LabelFrame(body, text=tr("cache_sounds_status"))
        status_frame.pack(fill="x", pady=4)
        status_lbl = ttk.Label(status_frame, text="")
        status_lbl.pack(anchor="w", padx=8, pady=6)

        def refresh_status():
            s = sounds_cache_status()
            if s["cached"]:
                mb = s["size"] / (1024 * 1024)
                txt = tr("cache_sounds_status_cached").format(
                    s["files"], f"{mb:.1f}", s.get("date") or "?")
            else:
                txt = tr("cache_sounds_status_empty")
            status_lbl.config(text=txt)

        # Лог операций
        log_frame = ttk.LabelFrame(body, text=tr("finder_log"))
        log_frame.pack(fill="both", expand=True, pady=8)
        log_box = tk.Text(log_frame, height=10, wrap=tk.WORD)
        log_box.pack(fill="both", expand=True, padx=4, pady=4)
        log_box.config(state="disabled")

        def log(line):
            log_box.config(state="normal")
            log_box.insert(tk.END, line + "\n")
            log_box.config(state="disabled")
            log_box.see(tk.END)
            win.update_idletasks()
            # дублируем в основной лог приложения
            self.log(line)

        # --- Действия ---
        def cache_from_current():
            inst = self.instance
            if not inst:
                error_box(win, tr("error"), tr("ts_no_active"))
                return
            res = cache_sounds_from_folder(inst["path"], log)
            if res["ok"]:
                info_box(win, tr("ok"),
                         tr("cache_sounds_cached_ok").format(res["files"]))
            else:
                error_box(win, tr("error"),
                          res.get("error") or tr("error"))
            refresh_status()

        def cache_from_folder():
            d = filedialog.askdirectory(
                parent=win, title=tr("cache_sounds_pick_source"))
            if not d:
                return
            res = cache_sounds_from_folder(d, log)
            if res["ok"]:
                info_box(win, tr("ok"),
                         tr("cache_sounds_cached_ok").format(res["files"]))
            else:
                error_box(win, tr("error"),
                          res.get("error") or tr("error"))
            refresh_status()

        def apply_to_current():
            inst = self.instance
            if not inst:
                error_box(win, tr("error"), tr("ts_no_active"))
                return
            res = apply_sounds_cache(inst["path"], log)
            if res["ok"]:
                info_box(win, tr("ok"),
                         tr("cache_sounds_applied_ok").format(res["files"]))
            else:
                error_box(win, tr("error"),
                          res.get("error") or tr("error"))

        def clear_cache():
            if not yesno(win, tr("service_cache_sounds"),
                         tr("cache_sounds_clear_confirm")):
                return
            sounds_clear_cache()
            log(tr("cache_sounds_cleared"))
            refresh_status()

        # --- Кнопки ---
        row1 = ttk.LabelFrame(body, text=tr("cache_sounds_step1"))
        row1.pack(fill="x", pady=4)
        rb = ttk.Frame(row1)
        rb.pack(anchor="w", padx=8, pady=6)
        ttk.Button(rb, text=tr("cache_sounds_from_current"),
                   command=cache_from_current).pack(side="left", padx=4)
        ttk.Button(rb, text=tr("cache_sounds_from_folder"),
                   command=cache_from_folder).pack(side="left", padx=4)
        ttk.Button(rb, text=tr("cache_sounds_clear"),
                   command=clear_cache).pack(side="left", padx=4)

        row2 = ttk.LabelFrame(body, text=tr("cache_sounds_step2"))
        row2.pack(fill="x", pady=4)
        rb2 = ttk.Frame(row2)
        rb2.pack(anchor="w", padx=8, pady=6)
        ttk.Button(rb2, text=tr("cache_sounds_apply_current"),
                   command=apply_to_current).pack(side="left", padx=4)

        ttk.Button(body, text=tr("close"),
                   command=win.destroy).pack(side="bottom", anchor="e",
                                             pady=(8, 0))

        refresh_status()

    # ---------- Version info ----------
    def show_version_dialog(self):
        inst = self.instance
        if not inst:
            return
        info = detect_game_version(inst["path"])
        ver = info.get("version") or tr("game_version_unknown")
        if info.get("dll_present"):
            dll_state = f"{info.get('dll_size'):,} bytes"
        else:
            dll_state = tr("game_version_unknown")
        # rw_data.dll
        patched = is_rw_data_patched(inst["path"])
        if patched is True:
            rw_state = tr("rw_state_patched")
        elif patched is False:
            rw_state = tr("rw_state_vanilla")
        else:
            rw_state = tr("rw_state_unknown")

        wf = detect_widescreen_fix(inst["path"])
        wf_state = tr("widescreen_fix_present") if wf["present"] \
            else tr("widescreen_fix_absent")

        text = tr("game_version_text").format(
            path=inst["path"], version=ver, dll=dll_state,
            dll_state=rw_state)
        text += "\n" + tr("widescreen_fix_label") + ": " + wf_state
        info_box(self, tr("game_version_title"), text)

    # ---------- About modal ----------
    def open_about_dialog(self):
        win = tk.Toplevel(self)
        win.title(tr("about_title"))
        win.geometry("580x540")
        win.transient(self)
        apply_icon(win)

        ttk.Label(win, text=APP_NAME,
                  font=("Arial", 16, "bold")).pack(pady=(20, 5))
        ttk.Label(win, text=tr("version"),
                  font=("Arial", 11)).pack(pady=(0, 10))
        ttk.Separator(win, orient="horizontal").pack(fill="x", padx=30, pady=8)

        body = tk.Text(win, wrap=tk.WORD, height=15, width=64,
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
    ADD_LANG_SENTINEL = "+ Add language…"

    def _lang_dropdown_values(self):
        return list(LANGS.keys()) + [self.ADD_LANG_SENTINEL]

    def change_lang(self, *_):
        choice = self.lang_var.get()
        if choice == self.ADD_LANG_SENTINEL:
            # Откатываем выбор, чтобы пользователь не остался с виртуальным «языком»
            prev = next((c for c in LANGS.keys() if c != self.ADD_LANG_SENTINEL),
                        "en")
            self.lang_var.set(prev)
            self._open_add_language_dialog()
            return
        set_lang(choice)
        self.save_cfg()
        self.rebuild_ui()

    def _open_add_language_dialog(self):
        """Диалог добавления языка (ВСЕГДА на английском, чтобы был
        универсальным независимо от текущего интерфейса)."""
        win = tk.Toplevel(self)
        win.title("Add language")
        win.geometry("620x420")
        win.transient(self)
        win.resizable(False, False)
        apply_icon(win)

        body = ttk.Frame(win, padding=16)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text="Add a new language pack",
                  font=("Arial", 14, "bold")).pack(anchor="w")
        ttk.Label(
            body,
            text=("Drop a *.json file with translations next to your existing\n"
                  "languages (data/languages/ is user-writable and works\n"
                  "without admin rights), or generate an AI prompt and ask\n"
                  "an LLM to translate the English pack for you."),
            justify="left", foreground="gray").pack(anchor="w", pady=(4, 12))

        # Кнопки 1 и 2
        row1 = ttk.Frame(body)
        row1.pack(fill="x", pady=4)

        def pick_json():
            p = filedialog.askopenfilename(
                parent=win, title="Pick *.json", filetypes=[("JSON", "*.json")])
            if not p:
                return
            try:
                name = add_language_file(p)
                if not name:
                    error_box(win, "Error",
                              "Translation file has no '_lang_name' key.")
                    return
                info_box(win, "OK", f"Language '{name}' added.")
                self.rebuild_ui()
                win.destroy()
            except Exception as e:
                error_box(win, "Error", f"Failed to add: {e}")

        def open_lang_folder():
            from mmi_lang import user_languages_dir
            d = user_languages_dir()
            try:
                open_path(d)
            except Exception as e:
                error_box(win, "Error", str(e))

        ttk.Button(row1, text="Pick *.json", command=pick_json,
                   width=22).pack(side="left", padx=4)
        ttk.Button(row1, text="Open languages folder",
                   command=open_lang_folder, width=22).pack(side="left", padx=4)

        ttk.Separator(body, orient="horizontal").pack(fill="x", pady=12)

        # AI-промпт
        ttk.Label(body, text="Generate AI prompt").pack(anchor="w")
        ttk.Label(body,
                  text=("Type the target language name (e.g. 'Spanish',\n"
                        "'日本語', 'Polski'). Clicking the button copies a\n"
                        "prompt with full en.json contents to clipboard."),
                  justify="left", foreground="gray").pack(anchor="w", pady=(2, 6))

        row2 = ttk.Frame(body)
        row2.pack(fill="x")
        lang_name_var = tk.StringVar()
        ttk.Label(row2, text="Enter Language:").pack(side="left", padx=(0, 6))
        ttk.Entry(row2, textvariable=lang_name_var,
                  width=24).pack(side="left")

        def gen_prompt():
            lang_name = lang_name_var.get().strip()
            if not lang_name:
                error_box(win, "Error", "Type a language name first.")
                return
            try:
                en_path = os.path.join(
                    res_path("languages"), "en.json")
                if not os.path.isfile(en_path):
                    # fallback: user-writable dir
                    en_path = os.path.join(
                        os.path.join(DATA, "languages"), "en.json")
                with open(en_path, "r", encoding="utf-8") as f:
                    en_text = f.read()
            except Exception as e:
                error_box(win, "Error", f"Cannot read en.json: {e}")
                return
            prompt = (
                "You are a localization translator. Produce a complete "
                f"Mafia Mod Installer language pack in {lang_name}.\n\n"
                "Rules:\n"
                "  1. Output a SINGLE valid JSON object (no commentary, no "
                "markdown fences).\n"
                "  2. Keep every key from the English source EXACTLY as is.\n"
                "  3. Set the value of \"_lang_name\" to the language's "
                f"endonym (its name in {lang_name}, e.g. 'Deutsch' for German).\n"
                "  4. Preserve placeholders like {} and {name}.\n"
                "  5. Use natural, idiomatic phrasing.\n"
                "  6. Save the result as <code>.json (e.g. 'es.json' for "
                "Spanish) and place it in data/languages/ next to the "
                "MafiaModInstaller.exe.\n\n"
                "Below is the full English source:\n\n"
                + en_text
            )
            self.clipboard_clear()
            self.clipboard_append(prompt)
            self.update()
            info_box(win, "OK",
                     "Prompt copied to clipboard. Paste it into "
                     "ChatGPT/Claude and save the result as data/languages/"
                     "<code>.json.")

        ttk.Button(row2, text="Generate prompt and copy to clipboard",
                   command=gen_prompt).pack(side="left", padx=8)

        ttk.Button(body, text="Close",
                   command=win.destroy).pack(side="bottom", anchor="e",
                                             pady=(16, 0))

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
        if hasattr(self, "logbox"):
            self.logbox.insert(tk.END, line + "\n")
            self.logbox.see(tk.END)
        append_log(line)

    def create_ui(self):
        style = ttk.Style(self)
        style.configure("TButton", padding=6)
        style.configure("TLabel", padding=3)

        top = ttk.Frame(self, padding=5)
        top.pack(fill="x")
        ttk.Label(top, text="Language:").pack(side="right", padx=5)
        self.lang_combo = ttk.Combobox(
            top, textvariable=self.lang_var,
            values=self._lang_dropdown_values(), state="readonly", width=20)
        self.lang_combo.pack(side="right")
        self.lang_combo.bind("<<ComboboxSelected>>", self.change_lang)

        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)

        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill="both", expand=True)

        self.tab_install = ttk.Frame(self.notebook, padding=10)
        self.tab_mods = ttk.Frame(self.notebook, padding=10)
        self.tab_upload = ttk.Frame(self.notebook, padding=10)
        self.tab_saves = ttk.Frame(self.notebook, padding=10)

        self.notebook.add(self.tab_install, text=tr("install_tab"))
        self.notebook.add(self.tab_mods, text=tr("mods_tab"))
        self.notebook.add(self.tab_upload, text=tr("upload_tab"))
        self.notebook.add(self.tab_saves, text=tr("saves_tab"))

        self.build_install_tab()
        self.build_mods_tab()
        self.build_upload_tab()
        self.build_saves_tab()

    # ---------- INSTALL TAB ----------
    def build_install_tab(self):
        f = self.tab_install
        f.columnconfigure(1, weight=1)
        f.rowconfigure(3, weight=1)

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
        self.game_combo.bind("<Button-3>", self._on_game_right_click)

        right = ttk.Frame(f)
        right.grid(row=0, column=2, padx=5, pady=5, sticky="e")
        ttk.Button(right, text=tr("add_game"),
                   command=self.menu_select_game).pack(side="left")
        ver_btn = ttk.Button(right, text="?", width=3,
                             command=self.show_version_dialog)
        ver_btn.pack(side="left", padx=(4, 0))
        # tooltip-эмуляция: текст кнопки уже самодокументирующийся,
        # но добавим tip через title-attr нет смысла в tk; просто
        # обновляем подсказку при наведении в lable status баре —
        # упрощённо: bind для отображения в логе.
        ver_btn.bind("<Enter>", lambda e: None)

        actions = ttk.Frame(f)
        actions.grid(row=1, column=0, columnspan=3, pady=10, sticky="ew")
        for i, (txt, cmd, with_ctx) in enumerate([
            (tr("backup"), self.create_backup, False),
            (tr("restore"), self.restore_backup, False),
            (tr("cleanup"), self.cleanup, False),
            (tr("run_game"), self.run_game, True),
        ]):
            actions.columnconfigure(i, weight=1)
            btn = ttk.Button(actions, text=txt, command=cmd)
            btn.grid(row=0, column=i, padx=5, sticky="ew")
            if with_ctx:
                btn.bind("<Button-3>", self._run_context_menu)

        ttk.Label(f, text=tr("log")).grid(row=2, column=0, sticky="w", padx=5, pady=(8, 0))

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

        bottom = ttk.Frame(f)
        bottom.grid(row=4, column=0, columnspan=3, sticky="ew", pady=8)
        bottom.columnconfigure(0, weight=1)

        ttk.Button(bottom, text=tr("clear_log"),
                   command=self.clear_log).grid(row=0, column=0, sticky="w", padx=4)
        self.auto_dta_var = tk.BooleanVar(
            value=bool(self.settings.get("auto_extract_dta", True)))
        self.auto_dta_var.trace_add("write", self._on_auto_dta_toggled)
        cb = ttk.Checkbutton(bottom, text=tr("auto_extract_dta"),
                             variable=self.auto_dta_var)
        cb.grid(row=0, column=1, sticky="e", padx=4)
        b1 = ttk.Button(bottom, text=tr("install_to_game"),
                        command=lambda: self.install_to_game(False))
        b1.grid(row=0, column=2, sticky="e", padx=4)
        b1.bind("<Button-3>", self._run_context_menu)
        b2 = ttk.Button(bottom, text=tr("install_and_run"),
                        command=lambda: self.install_to_game(True))
        b2.grid(row=0, column=3, sticky="e", padx=4)
        b2.bind("<Button-3>", self._run_context_menu)

    def _on_game_selected(self, *_):
        iid = self._instance_id_from_choice(self.game_var.get())
        if iid:
            self.current_instance_id = iid
            self.save_cfg()
            self._ensure_clean_backup(prompt=True)
            self.refresh_mods_list()
            self.refresh_mod_manager()
            self.refresh_saves_list()

    def _on_game_right_click(self, event):
        inst = self.instance
        if not inst:
            return
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label=tr("game_open_explorer"),
                         command=lambda: open_path(inst["path"]))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _run_context_menu(self, event):
        inst = self.instance
        if not inst:
            return
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label=tr("run_setup"),
                         command=lambda: self._run_aux("setup.exe", admin=True))
        menu.add_command(label=tr("run_mafiacon"),
                         command=lambda: self._run_aux("MafiaCon.exe", admin=False))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _run_aux(self, exe_name, admin=False):
        inst = self.instance
        if not inst:
            return
        target = os.path.join(inst["path"], exe_name)
        if not os.path.exists(target):
            error_box(self, tr("error"), tr("exe_not_found").format(target))
            return
        try:
            self._launch_executable(target, inst["path"], admin=admin)
            self.log(f"Запущено: {target}")
        except Exception as e:
            error_box(self, tr("error"), str(e))

    def _launch_executable(self, exe_path, cwd, admin=False):
        """Запуск .exe с правильной рабочей директорией.
        MafiaCon.exe ищет Game.exe относительно cwd; setup.exe требует UAC."""
        if sys.platform.startswith("win"):
            if admin:
                import ctypes
                ret = ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", exe_path, None, cwd, 1)
                if ret <= 32:
                    raise RuntimeError(f"ShellExecute runas failed: {ret}")
            else:
                subprocess.Popen(exe_path, cwd=cwd, shell=False)
        else:
            subprocess.Popen([exe_path], cwd=cwd)

    # ---------- MODS TAB ----------
    def build_mods_tab(self):
        f = self.tab_mods
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=1)

        cols = ("name", "priority", "target_version", "installed", "date",
                "files", "checksum", "readme")
        self.mods_table = ttk.Treeview(f, columns=cols, show="headings",
                                       height=15, selectmode="extended")
        for col_id, col_text, col_w, anchor in [
            ("name", tr("name"), 220, "w"),
            ("priority", tr("priority"), 70, "center"),
            ("target_version", tr("target_version_col"), 90, "center"),
            ("installed", tr("installed_col"), 90, "center"),
            ("date", tr("date"), 140, "w"),
            ("files", tr("files"), 60, "center"),
            ("checksum", tr("checksum_col"), 120, "w"),
            ("readme", tr("readme"), 180, "w"),
        ]:
            self.mods_table.heading(col_id, text=col_text)
            self.mods_table.column(col_id, width=col_w, anchor=anchor)
        self.mods_table.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        sb = ttk.Scrollbar(f, orient="vertical", command=self.mods_table.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.mods_table.configure(yscrollcommand=sb.set)

        bf = ttk.Frame(f)
        bf.grid(row=1, column=0, columnspan=2, pady=8, sticky="ew")
        for i in range(4):
            bf.columnconfigure(i, weight=1)
        ttk.Button(bf, text=tr("refresh"), command=self.refresh_mods_list).grid(
            row=0, column=0, padx=3, sticky="ew")
        ttk.Button(bf, text=tr("rename_mod"), command=self.rename_selected_mod).grid(
            row=0, column=1, padx=3, sticky="ew")
        ttk.Button(bf, text=tr("priority_change"),
                   command=self.change_selected_priority).grid(
            row=0, column=2, padx=3, sticky="ew")
        ttk.Button(bf, text=tr("open_mod_folder"), command=self.open_mod_folder).grid(
            row=0, column=3, padx=3, sticky="ew")
        ttk.Button(bf, text=tr("open_readme"), command=self.open_readme_file).grid(
            row=1, column=0, padx=3, pady=(4, 0), sticky="ew")
        ttk.Button(bf, text=tr("open_mmi_readme"),
                   command=self.open_mmi_readme_file).grid(
            row=1, column=1, padx=3, pady=(4, 0), sticky="ew")
        ttk.Button(bf, text=tr("create_mmi"), command=self.open_mmi_dialog).grid(
            row=1, column=2, padx=3, pady=(4, 0), sticky="ew")
        ttk.Button(bf, text=tr("remove_from_library"),
                   command=self.remove_selected_mod).grid(
            row=1, column=3, padx=3, pady=(4, 0), sticky="ew")

        self.mods_table.bind("<Double-1>", self.open_readme_file)
        self.mods_table.bind("<Button-3>", self.show_mod_context_menu)

        if DND_AVAILABLE:
            try:
                self.mods_table.drop_target_register(DND_FILES)
                self.mods_table.dnd_bind("<<Drop>>", self.on_drop_to_mods)
            except Exception:
                pass

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
        ttk.Button(row1, text=tr("upload_select_folder_btn"),
                   command=self.select_upload_folder).pack(side="left", padx=4)

        ttk.Label(f, text=tr("upload_name")).pack(anchor="w", pady=(8, 2))
        ttk.Entry(f, textvariable=self.upload_name).pack(fill="x")

        row2 = ttk.Frame(f)
        row2.pack(fill="x", pady=(8, 2))
        ttk.Label(row2, text=tr("upload_priority")).pack(side="left")
        ttk.Spinbox(row2, from_=1, to=999,
                    textvariable=self.upload_priority,
                    width=5).pack(side="left", padx=8)
        ttk.Label(row2, text=tr("priority_hint"),
                  foreground="gray").pack(side="left")

        # Целевая версия игры — опционально (по умолчанию игнорируется)
        row3 = ttk.Frame(f)
        row3.pack(fill="x", pady=(8, 2))
        self.upload_use_target_version = tk.BooleanVar(value=False)
        ttk.Checkbutton(row3, text=tr("upload_target_version_check"),
                        variable=self.upload_use_target_version,
                        command=self._toggle_target_version_combo).pack(side="left")
        self.upload_target_version_var = tk.StringVar(value="")
        self.upload_target_version_combo = ttk.Combobox(
            row3, textvariable=self.upload_target_version_var,
            values=("",) + GAME_VERSIONS, state="disabled", width=10)
        self.upload_target_version_combo.pack(side="left", padx=10)

        ttk.Button(f, text=tr("upload_btn"),
                   command=self.do_upload).pack(pady=14, anchor="w")

    def _toggle_target_version_combo(self):
        if self.upload_use_target_version.get():
            self.upload_target_version_combo.configure(state="readonly")
            if not self.upload_target_version_var.get():
                self.upload_target_version_var.set("1.2")
        else:
            self.upload_target_version_combo.configure(state="disabled")
            self.upload_target_version_var.set("")

    # ---------- SAVES TAB ----------
    def build_saves_tab(self):
        f = self.tab_saves
        f.columnconfigure(0, weight=1)
        f.rowconfigure(2, weight=1)

        ttk.Label(f, text=tr("saves_title"),
                  font=("Arial", 13, "bold")).grid(row=0, column=0, sticky="w", pady=(2, 4))
        ttk.Label(f, text=tr("saves_hint"),
                  wraplength=900,
                  foreground="gray").grid(row=1, column=0, sticky="w", pady=(0, 8))

        cols = ("date", "type", "label", "mods")
        self.saves_table = ttk.Treeview(f, columns=cols, show="headings",
                                        height=12, selectmode="extended")
        for col_id, col_text, col_w in [
            ("date", tr("saves_col_date"), 180),
            ("type", tr("saves_col_type"), 90),
            ("label", tr("saves_col_label"), 280),
            ("mods", tr("saves_col_mods"), 240),
        ]:
            self.saves_table.heading(col_id, text=col_text)
            self.saves_table.column(col_id, width=col_w)
        self.saves_table.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)

        bf = ttk.Frame(f)
        bf.grid(row=3, column=0, sticky="ew", pady=8)
        for i in range(3):
            bf.columnconfigure(i, weight=1)
        ttk.Button(bf, text=tr("saves_make_backup"),
                   command=self.do_saves_backup).grid(row=0, column=0, padx=3, sticky="ew")
        ttk.Button(bf, text=tr("saves_restore"),
                   command=self.do_saves_restore).grid(row=0, column=1, padx=3, sticky="ew")
        ttk.Button(bf, text=tr("saves_delete"),
                   command=self.do_saves_delete).grid(row=0, column=2, padx=3, sticky="ew")

    # =====================================================
    # Контекстные меню
    # =====================================================
    def show_context_menu(self, event, widget):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label=tr("copy"),
                         command=lambda: self._copy_text(widget))
        menu.add_command(label=tr("select_all_action"),
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
        menu.add_command(label=tr("priority_change"),
                         command=self.change_selected_priority)
        menu.add_command(label=tr("edit_target_version"),
                         command=self.change_selected_target_version)
        menu.add_command(label=tr("open_mod_folder"), command=self.open_mod_folder)
        menu.add_command(label=tr("open_readme"), command=self.open_readme_file)
        menu.add_command(label=tr("open_mmi_readme"),
                         command=self.open_mmi_readme_file)
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
        if path:
            self.upload_path.set(path)

    def select_upload_folder(self):
        path = filedialog.askdirectory(parent=self, title=tr("select_mod_folder"))
        if path:
            self.upload_path.set(path)

    def do_upload(self):
        path = self.upload_path.get()
        name = self.upload_name.get().strip() or None
        try:
            priority = int(self.upload_priority.get())
            if priority < 1:
                priority = DEFAULT_PRIORITY
        except Exception:
            priority = DEFAULT_PRIORITY
        target_version = None
        if self.upload_use_target_version.get():
            v = (self.upload_target_version_var.get() or "").strip()
            if v in GAME_VERSIONS:
                target_version = v
        if not path:
            return
        try:
            ids, mmi_readme = add_mod_to_library(
                path, name=name, priority=priority,
                target_version=target_version,
                autodetect_target_version=bool(
                    self.settings.get(
                        "experimental_autodetect_target_version", False)))
            self.log(tr("upload_done") + f" ({len(ids)})")
            if mmi_readme:
                self._show_mmi_readme_popup(mmi_readme)
            info_box(self, tr("ok"), tr("upload_done"))
            self.upload_path.set("")
            self.upload_name.set("")
            self.upload_priority.set(DEFAULT_PRIORITY)
            self.upload_use_target_version.set(False)
            self._toggle_target_version_combo()
        except zipfile.BadZipFile:
            error_box(self, tr("error"), tr("bad_archive"))
        except Exception as e:
            error_box(self, tr("error"), str(e))
        self.refresh_all()

    def _show_mmi_readme_popup(self, text: str):
        win = tk.Toplevel(self)
        win.title(tr("import_mmi_readme_title"))
        win.geometry("520x400")
        win.transient(self)
        apply_icon(win)
        tx = tk.Text(win, wrap=tk.WORD, font=("Arial", 10))
        tx.pack(fill="both", expand=True, padx=10, pady=10)
        tx.insert("1.0", text)
        tx.config(state="disabled")
        ttk.Button(win, text=tr("ok"),
                   command=win.destroy).pack(pady=(0, 10))

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
            if self.settings.get("compress_backups"):
                level = int(self.settings.get("compress_level", 5))
                target_zip = os.path.join(inst_paths["user_backups"],
                                          slugify(name) + ".zip")
                comp_arg = max(0, min(9, level))
                with zipfile.ZipFile(target_zip, "w",
                                     zipfile.ZIP_DEFLATED, comp_arg) as z:
                    for root, _, files in os.walk(inst["path"]):
                        for fname in files:
                            full = os.path.join(root, fname)
                            rel = os.path.relpath(full, inst["path"])
                            z.write(full, rel)
                self.log(tr("backup_created").format(target_zip))
            else:
                target_dir = os.path.join(inst_paths["user_backups"], slugify(name))
                shutil.copytree(inst["path"], target_dir)
                self.log(tr("backup_created").format(target_dir))
            info_box(self, tr("ok"), tr("backup_created").format(name))
        except Exception as e:
            error_box(self, tr("error"), str(e))

    def restore_backup(self):
        inst = self.instance
        if not inst:
            return
        ub = get_instance_paths(inst["id"])["user_backups"]
        path = filedialog.askopenfilename(
            parent=self, initialdir=ub, title=tr("select_backup"),
            filetypes=[(tr("zip_archives"), "*.zip"),
                       (tr("all_files"), "*.*")])
        if not path:
            path = filedialog.askdirectory(parent=self, initialdir=ub,
                                           title=tr("select_backup"))
        if not path:
            return
        if not yesno(self, tr("confirm_execute"), tr("hard_confirm")):
            return
        try:
            if os.path.isfile(path) and path.lower().endswith(".zip"):
                for item in os.listdir(inst["path"]):
                    full = os.path.join(inst["path"], item)
                    try:
                        if os.path.isfile(full) or os.path.islink(full):
                            os.unlink(full)
                        elif os.path.isdir(full):
                            shutil.rmtree(full, ignore_errors=True)
                    except Exception:
                        pass
                with zipfile.ZipFile(path) as z:
                    z.extractall(inst["path"])
            else:
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

    def patch_dll(self, parent=None):
        inst = self.instance
        if not inst:
            return
        src = res_path(os.path.join("assets", "rw_data.dll"))
        if not os.path.exists(src):
            error_box(parent or self, tr("error"), tr("patch_dll_missing"))
            return
        if not yesno(parent or self, tr("patch_dll"),
                     tr("patch_dll_confirm").format(inst["path"])):
            return
        try:
            patch_rw_data_dll(inst["path"], self.log)
            self.log(tr("patch_dll_done"))
            info_box(parent or self, tr("ok"), tr("patch_dll_done"))
        except Exception as e:
            error_box(parent or self, tr("error"), str(e))

    def run_game(self):
        inst = self.instance
        if not inst:
            return
        exe_name = inst.get("exe", "Game.exe")
        exe_path = os.path.join(inst["path"], exe_name)
        if not os.path.exists(exe_path):
            error_box(self, tr("error"), tr("exe_not_found").format(exe_path))
            return
        self._maybe_update_logo()
        try:
            self._launch_executable(exe_path, inst["path"], admin=False)
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
            update_logo_in_game(selected, inst["path"], self.settings, self.log)
        except Exception as e:
            self.log(tr("logo_failed").format(e))

    def _on_auto_dta_toggled(self, *_):
        new_val = bool(self.auto_dta_var.get())
        if not new_val:
            # Двойное предупреждение перед отключением
            if not yesno(self, tr("auto_extract_dta"),
                         tr("auto_extract_dta_off_confirm1")):
                self.auto_dta_var.set(True)
                return
            if not yesno(self, tr("auto_extract_dta"),
                         tr("auto_extract_dta_off_confirm2")):
                self.auto_dta_var.set(True)
                return
        self.settings["auto_extract_dta"] = new_val
        self.save_cfg()

    def install_to_game(self, run_after):
        inst = self.instance
        if not inst:
            return
        if not inst.get("has_clean_backup"):
            self._ensure_clean_backup(prompt=True)
        if not inst.get("has_clean_backup"):
            info_box(self, tr("info"), tr("install_blocked_no_clean"))
            return

        ids = [mid for mid, var in self.mm_vars.items() if var.get()]
        all_mods = load_json(PATHS["mods_json"], [])
        selected = [m for m in all_mods if m["id"] in ids]

        if (self.settings.get("recommended_count_on", True)
                and len(selected) > self.settings.get(
                    "recommended_count", DEFAULT_RECOMMENDED_COUNT)):
            if not yesno(self, tr("install_to_game"),
                         tr("mod_recommended_warn").format(
                             len(selected),
                             self.settings.get("recommended_count",
                                               DEFAULT_RECOMMENDED_COUNT))):
                return

        with_saves = [m for m in selected if mod_has_saves(m)]
        if with_saves:
            names = ", ".join(m.get("name") or m["id"] for m in with_saves)
            if not yesno(self, tr("install_to_game"),
                         tr("mod_saves_warn").format(names)):
                return

        # Проверка соответствия версий: только пишем в лог, не блокируем
        game_info = detect_game_version(inst["path"])
        game_v = game_info.get("version")
        if game_v:
            for m in selected:
                mv = (m.get("target_version") or "").strip()
                if mv and mv != game_v:
                    self.log(tr("version_mismatch_log").format(
                        m.get("name") or m["id"], mv, game_v))

        # Auto-бэкап savegame перед установкой (только если включено)
        if self.settings.get("auto_backup_saves", True):
            try:
                sid = make_saves_backup(inst, type_="auto",
                                        label="before-install")
                if not sid:
                    self.log("savegame/ не найдена в папке игры — "
                             "авто-бэкап пропущен")
            except Exception as e:
                self.log(f"Авто-бэкап savegame не удался: {e}")
        else:
            self.log(tr("auto_backup_off_log"))

        if self.settings.get("auto_extract_dta", True):
            try:
                mod_dirs = [m.get("dir") for m in selected if m.get("dir")]
                needed = compute_dtas_for_dirs(mod_dirs)
                if needed:
                    if not dta_cli_available():
                        self.log(tr("auto_extract_dta_no_cli"))
                    else:
                        self.log(tr("auto_extract_dta_start").format(
                            ", ".join(needed)))
                        extract_dtas(inst["path"], needed, self.log)
            except Exception as e:
                self.log(tr("auto_extract_dta_failed").format(e))

        try:
            install_mods_into_game(selected, inst, self.settings, self.log)
            self.log(tr("install_to_game_complete"))
            self.instances = load_json(PATHS["instances_json"], [])
            self.refresh_mods_list()
            self.refresh_saves_list()
            # После установки повторяем auto-detect widescreen (мод мог
            # положить dinput8.dll / scripts/Mafia.WidescreenFix.asi).
            self._auto_widescreen_detect()
            # Логотип формируется СРАЗУ после установки — иначе при первом
            # запуске игры пользователь увидит ванильный logo1.avi.
            self._maybe_update_logo()
            if run_after:
                self.run_game()
            else:
                info_box(self, tr("ok"), tr("install_to_game_complete"))
        except Exception as e:
            error_box(self, tr("error"), str(e))

    def clear_log(self):
        self.logbox.delete("1.0", tk.END)

    # =====================================================
    # Refresh
    # =====================================================
    def refresh_all(self):
        if hasattr(self, "game_combo"):
            self.game_combo['values'] = self._instance_choices()
            cur = self.instance
            if cur:
                self.game_var.set(f"{cur['name']}  ({cur['path']})")
        self.refresh_mods_list()
        self.refresh_mod_manager()
        self.refresh_saves_list()

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
            cs = (mod.get("checksum") or "")[:12]
            tv = mod.get("target_version") or tr("any_version")
            # iid = mod_id чтобы multi-select давал нам id-ы
            self.mods_table.insert("", "end", iid=mod["id"], values=(
                mod.get("name", ""),
                mod.get("priority", DEFAULT_PRIORITY),
                tv,
                mark,
                mod.get("date", ""),
                mod.get("files_count", 0),
                cs,
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
        for mod in sorted(load_json(PATHS["mods_json"], []),
                          key=lambda m: int(m.get("priority", DEFAULT_PRIORITY))):
            v = tk.BooleanVar(value=mod["id"] in active_ids)
            self.mm_vars[mod["id"]] = v
            label = (mod.get("name") or mod["id"]) + \
                    f"  [p{mod.get('priority', DEFAULT_PRIORITY)}]"
            ttk.Checkbutton(self.mm_inner, text=label,
                            variable=v).pack(anchor="w", padx=6, pady=2)

    def refresh_saves_list(self):
        if not hasattr(self, "saves_table"):
            return
        for row in self.saves_table.get_children():
            self.saves_table.delete(row)
        inst = self.instance
        if not inst:
            return
        for s in reversed(inst.get("saves", [])):
            type_ = s.get("type", "manual")
            type_str = tr(f"saves_type_{type_}")
            mods_meta = s.get("active_mods") or []
            mods_str = ", ".join(
                (m.get("name") or m.get("id") or "?") for m in mods_meta
            ) if mods_meta else ""
            self.saves_table.insert("", "end", iid=s["id"],
                                    values=(s.get("date", ""),
                                            type_str,
                                            s.get("label", ""),
                                            mods_str))

    def get_selected_mod(self):
        """Возвращает первый выделенный мод (для одиночных операций)."""
        ids = self.mods_table.selection()
        if not ids:
            return None
        by_id = {m["id"]: m for m in self.mods_data}
        return by_id.get(ids[0])

    def get_selected_mods(self):
        """Возвращает список всех выделенных модов (для multi-select)."""
        ids = self.mods_table.selection()
        by_id = {m["id"]: m for m in self.mods_data}
        return [by_id[i] for i in ids if i in by_id]

    def rename_selected_mod(self):
        mod = self.get_selected_mod()
        if not mod:
            return
        new = simpledialog.askstring(tr("rename_mod"), tr("name"),
                                     initialvalue=mod.get("name", ""), parent=self)
        if new is None or not new.strip():
            return
        update_mod_field(mod["id"], "name", new.strip())
        self.refresh_all()

    def change_selected_priority(self):
        mod = self.get_selected_mod()
        if not mod:
            return
        new = simpledialog.askinteger(
            tr("priority_change"), tr("priority_hint"),
            initialvalue=int(mod.get("priority", DEFAULT_PRIORITY)),
            minvalue=1, maxvalue=9999, parent=self)
        if new is None:
            return
        update_mod_field(mod["id"], "priority", int(new))
        self.refresh_all()

    def change_selected_target_version(self):
        mod = self.get_selected_mod()
        if not mod:
            return
        win = tk.Toplevel(self)
        apply_icon(win)
        win.title(tr("edit_target_version_title").format(
            mod.get("name") or mod["id"]))
        win.transient(self)
        win.resizable(False, False)
        ttk.Label(win, text=tr("edit_target_version_prompt"),
                  wraplength=320).pack(padx=12, pady=(12, 6))
        current = (mod.get("target_version") or "").strip()
        var = tk.StringVar(value=current if current in GAME_VERSIONS else "")
        choices = [tr("any_version")] + list(GAME_VERSIONS)
        display_var = tk.StringVar(
            value=current if current in GAME_VERSIONS else tr("any_version"))
        ttk.Combobox(win, textvariable=display_var, values=choices,
                     state="readonly", width=20).pack(padx=12, pady=4)

        def on_ok():
            v = display_var.get()
            new = v if v in GAME_VERSIONS else ""
            update_mod_field(mod["id"], "target_version", new)
            win.destroy()
            self.refresh_all()

        bf = ttk.Frame(win)
        bf.pack(pady=10)
        ttk.Button(bf, text=tr("ok"), command=on_ok).pack(side="left", padx=4)
        ttk.Button(bf, text=tr("cancel"),
                   command=win.destroy).pack(side="left", padx=4)
        win.grab_set()
        win.wait_window()

    def remove_selected_mod(self):
        mods = self.get_selected_mods()
        if not mods:
            return
        if len(mods) == 1:
            m = mods[0]
            if not yesno(self, tr("remove_from_library"),
                         tr("remove_confirm").format(m.get("name", m["id"]))):
                return
        else:
            if not yesno(self, tr("remove_from_library"),
                         tr("delete_multiple_confirm").format(len(mods))):
                return
        for m in mods:
            remove_mod_from_library(m["id"])
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
        if len(readmes) == 1:
            open_path(readmes[0])
            return
        # Несколько readme — диалог выбора
        self._show_readme_picker(mod, readmes)

    def _show_readme_picker(self, mod, readmes):
        win = tk.Toplevel(self)
        win.title(tr("multi_readme_title"))
        win.geometry("520x340")
        win.transient(self)
        apply_icon(win)

        ttk.Label(win, text=mod.get("name", ""),
                  font=("Arial", 11, "bold")).pack(anchor="w", padx=12,
                                                   pady=(10, 6))

        list_frame = ttk.Frame(win)
        list_frame.pack(fill="both", expand=True, padx=12, pady=4)
        lst = tk.Listbox(list_frame, height=8, activestyle="dotbox")
        lst.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=lst.yview)
        sb.pack(side="right", fill="y")
        lst.configure(yscrollcommand=sb.set)

        mod_dir = mod.get("dir", "")
        for r in readmes:
            lst.insert(tk.END, os.path.relpath(r, mod_dir))

        def _open_selected():
            sel = lst.curselection()
            if not sel:
                return
            open_path(readmes[sel[0]])
            win.destroy()

        lst.bind("<Double-1>", lambda e: _open_selected())

        bar = ttk.Frame(win)
        bar.pack(side="bottom", fill="x", pady=10)
        ttk.Button(bar, text=tr("close"),
                   command=win.destroy).pack(side="right", padx=10)
        ttk.Button(bar, text=tr("open_readme"),
                   command=_open_selected).pack(side="right", padx=4)

    def open_mmi_readme_file(self):
        mod = self.get_selected_mod()
        if not mod:
            return
        text = mod.get("mmi_readme", "")
        if not text:
            info_box(self, tr("info"), tr("no_mmi_readme"))
            return
        self._show_mmi_readme_popup(text)

    # =====================================================
    # Saves actions
    # =====================================================
    def do_saves_backup(self):
        inst = self.instance
        if not inst:
            return
        if not os.path.isdir(saves_folder(inst)):
            info_box(self, tr("info"), tr("saves_folder_missing"))
            return
        label = simpledialog.askstring(tr("saves_make_backup"),
                                       tr("saves_label"), parent=self) or ""
        try:
            sid = make_saves_backup(inst, type_="manual", label=label)
            if sid:
                self.log(tr("saves_done"))
                self.refresh_saves_list()
            else:
                info_box(self, tr("info"), tr("saves_folder_missing"))
        except Exception as e:
            error_box(self, tr("error"), str(e))

    def do_saves_restore(self):
        inst = self.instance
        if not inst:
            return
        if self.settings.get("immutable_saves", True):
            error_box(self, tr("error"), tr("saves_immutable_off"))
            return
        sel = self.saves_table.selection()
        if not sel:
            info_box(self, tr("info"), tr("saves_no_select"))
            return
        sid = sel[0]
        if not yesno(self, tr("saves_restore"), tr("confirm_execute")):
            return
        try:
            restore_saves_backup(inst, sid)
            self.log(tr("saves_restored"))
            info_box(self, tr("ok"), tr("saves_restored"))
        except Exception as e:
            error_box(self, tr("error"), str(e))

    def do_saves_delete(self):
        inst = self.instance
        if not inst:
            return
        sel = list(self.saves_table.selection())
        if not sel:
            info_box(self, tr("info"), tr("saves_no_select"))
            return
        if len(sel) == 1:
            if not yesno(self, tr("saves_delete"), tr("confirm_execute")):
                return
        else:
            if not yesno(self, tr("saves_delete"),
                         tr("delete_multiple_confirm").format(len(sel))):
                return
        delete_saves_backups(inst, sel)
        self.refresh_saves_list()

    # =====================================================
    # MMI dialog
    # =====================================================
    def open_mmi_dialog(self):
        win = tk.Toplevel(self)
        win.title(tr("mmi_dialog_title"))
        win.geometry("620x640")
        win.minsize(500, 460)
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

        def select_all_action():
            for m in all_mods:
                v = vars_map.setdefault(m["id"], tk.BooleanVar())
                v.set(True)
            render()

        ttk.Button(bar, text=tr("mmi_select_all"),
                   command=select_all_action).pack(side="left", padx=4)

        search_var.trace_add("write", lambda *_: render())
        render()

        # Целевая версия (применяется ко всем выбранным модам при упаковке)
        tv_row = ttk.Frame(win)
        tv_row.pack(fill="x", padx=12, pady=(6, 2))
        ttk.Label(tv_row, text=tr("target_version") + ":").pack(side="left")
        mmi_target_var = tk.StringVar(value="")
        ttk.Combobox(tv_row, textvariable=mmi_target_var,
                     values=("",) + GAME_VERSIONS, state="readonly",
                     width=10).pack(side="left", padx=6)
        ttk.Label(tv_row, text=tr("any_version"),
                  foreground="gray").pack(side="left")

        ttk.Label(win, text=tr("mmi_readme_label")).pack(
            anchor="w", padx=12, pady=(8, 2))
        readme_text = tk.Text(win, height=5, wrap=tk.WORD)
        readme_text.pack(fill="x", padx=12, pady=2)

        bbar = ttk.Frame(win)
        bbar.pack(fill="x", side="bottom", pady=10)

        def do_save():
            chosen_ids = {mid for mid, v in vars_map.items() if v.get()}
            chosen = [dict(m) for m in all_mods if m["id"] in chosen_ids]
            if not chosen:
                info_box(win, tr("info"), tr("no_mods_selected"))
                return
            mmi_readme = readme_text.get("1.0", "end-1c")
            if len(mmi_readme) > MMI_README_LIMIT:
                error_box(win, tr("error"), tr("mmi_too_long"))
                return
            # Переопределяем target_version у выбранных модов, если задан в форме
            tv = (mmi_target_var.get() or "").strip()
            if tv:
                for m in chosen:
                    m["target_version"] = tv
            out = filedialog.asksaveasfilename(
                parent=win, title=tr("mmi_save"),
                defaultextension=".mmi",
                filetypes=[(tr("mmi_archives"), "*.mmi"),
                           (tr("all_files"), "*.*")])
            if not out:
                return
            try:
                build_mmi(chosen, out, mmi_readme=mmi_readme)
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
            self._dropped_to_upload(path)

    def on_drop_to_mods(self, event):
        path = event.data.strip("{}").strip()
        if path:
            self._dropped_to_upload(path)

    def _dropped_to_upload(self, path: str):
        self.upload_path.set(path)
        try:
            self.notebook.select(self.tab_upload)
        except Exception:
            pass


# =========================================================
if __name__ == "__main__":
    app = App()
    app.mainloop()
