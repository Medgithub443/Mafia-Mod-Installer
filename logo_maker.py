"""
logo_maker.py — оборачивает ffmpeg для наложения текста на logo1.avi.

Используется как logoMaker.exe внутри Mafia Mod Installer и как Python-модуль.

ffmpeg берётся из imageio_ffmpeg (имеет встроенный минимальный официальный
бинарник для Win/Linux/Mac, лицензированный под GPL/LGPL). При сборке
PyInstaller бинарник попадает внутрь exe.

Использование как CLI:
    logoMaker <input.avi> <output.avi> <font.otf> "<text>" [x] [y] [size]

Текст рисуется ЧЁРНЫМ, без теней и эффектов (drawtext без shadow/box).
По умолчанию x=87 y=361 size=24, как требует logoMakerPrompt.
"""

import os
import sys
import subprocess
import tempfile


def _ffmpeg_path() -> str:
    """Возвращает путь к ffmpeg.exe.

    Приоритет:
      1. ffmpeg.exe рядом с этим файлом / .exe
      2. imageio_ffmpeg.get_ffmpeg_exe()
      3. ffmpeg в PATH
    """
    base = os.path.dirname(
        sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
    for name in ("ffmpeg.exe", "ffmpeg"):
        candidate = os.path.join(base, name)
        if os.path.exists(candidate):
            return candidate

    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass

    return "ffmpeg"


def _escape_drawtext(text: str) -> str:
    """drawtext-фильтр имеет особый синтаксис экранирования.
    Безопаснее писать текст в файл и использовать textfile=, что мы и делаем."""
    return text


def render(input_path: str, output_path: str, font_path: str, text: str,
           x: int = 87, y: int = 361, font_size: int = 36,
           line_spacing: int = -6) -> None:
    """Накладывает text на input_path.avi и сохраняет в output_path.avi.
    Звук копируется без перекодирования.

    По умолчанию шрифт 36pt и плотный межстрочный интервал (-6 пикселей).
    Пустые строки в тексте игнорируются (схлопываются), чтобы не было
    «дырок» в логотипе."""

    if not os.path.exists(input_path):
        raise FileNotFoundError(input_path)
    if not os.path.exists(font_path):
        raise FileNotFoundError(font_path)

    # Убираем пустые строки между непустыми, чтобы не было визуальных дырок
    text = "\n".join(line for line in text.split("\n") if line.strip())

    # drawtext в ffmpeg любит особое экранирование пути на Windows
    # (двоеточие и обратные слэши). Копируем шрифт во временное место
    # с простым относительным путём, чтобы фильтр не сломался.
    tmp_dir = tempfile.mkdtemp(prefix="logomaker_")
    try:
        tmp_font = os.path.join(tmp_dir, "font.otf")
        tmp_text = os.path.join(tmp_dir, "text.txt")
        with open(font_path, "rb") as fin, open(tmp_font, "wb") as fout:
            fout.write(fin.read())
        with open(tmp_text, "w", encoding="utf-8") as fout:
            fout.write(text)

        # ffmpeg на Windows ожидает прямые слэши в путях фильтра
        font_for_filter = tmp_font.replace("\\", "/").replace(":", "\\:")
        text_for_filter = tmp_text.replace("\\", "/").replace(":", "\\:")

        vf = (
            f"drawtext="
            f"fontfile='{font_for_filter}':"
            f"textfile='{text_for_filter}':"
            f"x={x}:y={y}:"
            f"fontsize={font_size}:"
            f"fontcolor=black:"
            f"line_spacing={line_spacing}:"
            f"box=0:shadowx=0:shadowy=0"
        )

        cmd = [
            _ffmpeg_path(),
            "-y",                  # перезапись output
            "-loglevel", "error",
            "-i", input_path,
            "-vf", vf,
            "-c:v", "mjpeg",       # сохраняем формат AVI/MJPEG
            "-q:v", "3",
            "-c:a", "copy",        # звук без перекодирования
            output_path,
        ]
        # На Windows прячем консольное окно
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        proc = subprocess.run(cmd, capture_output=True, startupinfo=startupinfo)
        if proc.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed (code {proc.returncode}):\n"
                f"{proc.stderr.decode('utf-8', errors='replace')}")
    finally:
        try:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


def _unescape(s: str) -> str:
    return s.replace("\\n", "\n")


def main():
    if len(sys.argv) < 5:
        print('Usage: logoMaker <input.avi> <output.avi> <font.otf> "<text>" [x] [y] [size]')
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    font_path = sys.argv[3]
    text = _unescape(sys.argv[4])
    x = int(sys.argv[5]) if len(sys.argv) > 5 else 87
    y = int(sys.argv[6]) if len(sys.argv) > 6 else 361
    font_size = int(sys.argv[7]) if len(sys.argv) > 7 else 36

    render(input_path, output_path, font_path, text, x, y, font_size)
    print(f"Done: {output_path}")


if __name__ == "__main__":
    main()
