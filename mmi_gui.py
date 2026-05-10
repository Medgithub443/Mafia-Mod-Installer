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


def yesno(parent, title, text):
    apply_icon(parent)
    return messagebox.askyesno(title, text, parent=parent)


def yesnocancel(parent, title, text):
    apply_icon(parent)
    return messagebox.askyesnocancel(title, text, parent=parent)
