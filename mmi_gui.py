"""Маленькие GUI-хелперы: иконка для всех Toplevel, обёртки для messagebox."""

import os
from tkinter import messagebox

from mmi_paths import ICON_PATH


def apply_icon(window) -> None:
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


def yesno(parent, title, text, yes_text=None, no_text=None):
    """Если yes_text/no_text заданы — открывает свой Toplevel с этими
    подписями (нужно для случаев типа OK/Позже). Иначе — стандартный
    messagebox с локализованными OS-кнопками Yes/No."""
    apply_icon(parent)
    if yes_text is None and no_text is None:
        return messagebox.askyesno(title, text, parent=parent)
    import tkinter as tk
    from tkinter import ttk
    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent)
    win.resizable(False, False)
    apply_icon(win)
    result = {"v": False}
    body = ttk.Frame(win, padding=18)
    body.pack(fill="both", expand=True)
    ttk.Label(body, text=text, wraplength=520, justify="left").pack(
        anchor="w", pady=(0, 12))
    bf = ttk.Frame(body)
    bf.pack(anchor="e")

    def on_yes():
        result["v"] = True
        win.destroy()

    def on_no():
        result["v"] = False
        win.destroy()

    ttk.Button(bf, text=yes_text or "OK", command=on_yes,
               width=14).pack(side="left", padx=4)
    ttk.Button(bf, text=no_text or "Cancel", command=on_no,
               width=14).pack(side="left", padx=4)
    win.grab_set()
    win.wait_window()
    return result["v"]


def yesnocancel(parent, title, text):
    apply_icon(parent)
    return messagebox.askyesnocancel(title, text, parent=parent)
