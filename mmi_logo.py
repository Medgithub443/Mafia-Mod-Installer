"""Генерация logo1.avi через bundled logoMaker.exe.

logoMaker.exe — нативный Win64 бинарник (~46 KB), без зависимостей.
Если бинарник не найден (например, при запуске из исходников на Mac/Linux) —
функция тихо логирует и пропускает обновление логотипа."""

import hashlib
import os
import shutil
import subprocess
import sys

from mmi_paths import PATHS, app_dir, res_path


def _logo_text(selected_mods) -> str:
    lines = ["INSTALLED MODS:"]
    if not selected_mods:
        lines.append(" (none)")
    else:
        for i, m in enumerate(selected_mods, 1):
            lines.append(f" {i}. {m.get('name') or m['id']}")
    return "\n".join(line for line in lines if line.strip())


def _logo_cache_key(selected_mods, widescreen: bool, alt: bool) -> str:
    payload = "|".join(sorted(m["id"] for m in selected_mods))
    payload += f"|ws={int(bool(widescreen))}|alt={int(bool(alt))}"
    return hashlib.md5(payload.encode("utf-8")).hexdigest()[:12]


def _find_logomaker() -> str:
    """Ищем logoMaker.exe рядом с программой и в assets/."""
    candidates = []
    base = app_dir()
    for name in ("logoMaker.exe", "logoMaker"):
        candidates.append(os.path.join(base, name))
        candidates.append(os.path.join(base, "assets", name))
        candidates.append(res_path(os.path.join("assets", name)))
    for c in candidates:
        if os.path.exists(c):
            return c
    return ""


def update_logo_in_game(selected_mods, game_path, settings, logger) -> None:
    widescreen = bool(settings.get("widescreen", False))
    use_alt = bool(settings.get("use_alt_logo", False))
    cache_key = _logo_cache_key(selected_mods, widescreen, use_alt)
    cached = os.path.join(PATHS["logos_dir"], f"{cache_key}.avi")

    # При use_alt берём logo1_alt.avi и НЕ накладываем текст со списком модов.
    template_name = "logo1_alt.avi" if use_alt else "logo1.avi"
    template = res_path(os.path.join("assets", template_name))
    if use_alt and not os.path.exists(template):
        # Если alt-шаблон не положен в assets/, fallback на logo1.avi
        # и обычный pipeline.
        logger("logo1_alt.avi не найден — fallback на logo1.avi с оверлеем")
        use_alt = False
        template = res_path(os.path.join("assets", "logo1.avi"))
    font = res_path(os.path.join("assets", "aurorabdcnbtrusbyme_bold.otf"))

    if not os.path.exists(template):
        raise FileNotFoundError(template)

    if use_alt:
        # Просто копируем шаблон без оверлея — без вызова logoMaker.
        shutil.copy2(template, os.path.join(game_path, "logo1.avi"))
        return

    if not os.path.exists(cached):
        exe = _find_logomaker()
        if not exe:
            logger("logoMaker.exe не найден — пропускаю обновление логотипа")
            return
        text = _logo_text(selected_mods)
        cmd = [exe, template, cached, font, text, "87", "361", "36"]
        if widescreen:
            cmd.append("--widescreen")
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        proc = subprocess.run(cmd, capture_output=True, startupinfo=startupinfo)
        if proc.returncode != 0:
            raise RuntimeError(
                f"logoMaker exit {proc.returncode}: "
                f"{proc.stderr.decode('utf-8', errors='replace')[:500]}")

    shutil.copy2(cached, os.path.join(game_path, "logo1.avi"))


def clear_logo_cache() -> int:
    n = 0
    if not os.path.isdir(PATHS["logos_dir"]):
        return 0
    for f in os.listdir(PATHS["logos_dir"]):
        full = os.path.join(PATHS["logos_dir"], f)
        try:
            if os.path.isfile(full):
                os.remove(full)
                n += 1
        except Exception:
            pass
    return n
