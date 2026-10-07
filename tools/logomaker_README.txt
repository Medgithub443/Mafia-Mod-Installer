logoMaker tiny — drop-in замена для logo_maker.py + ffmpeg_avi_mp3.exe
=======================================================================

Краткое описание
----------------
Инструмент делает то же, что `logo_maker.py` из Mafia Mod Installer 0.12:
накладывает чёрный текст из OTF-шрифта на каждый кадр AVI и пишет AVI
на выход с тем же аудио-стримом.

Главное отличие — размер. Вместо связки
    logo_maker.py  (~5 KB Python)
  + ffmpeg_avi_mp3.exe  (6 164 992 байт = 6.16 MB)
теперь один бинарь:
    logoMaker.exe  (47 104 байт ≈ 46 KB)

Внутри используется только Windows API: GDI+ для рисования и JPEG-кодека,
ole32/shlwapi/shell32 для аргументов и потоков. Ни одна из этих DLL не
ходит в комплекте — они есть в любой Windows со времён XP SP1.


Что нужно сделать перед использованием
--------------------------------------
В оригинальном проекте `logo1.avi` закодирован как MPEG-4 (FMP4 = ffmpeg
тег). Полноценный декодер MPEG-4 в 50 KB не помещается, поэтому исходник
нужно один раз на этапе сборки пакета сконвертировать в MJPEG:

    ffmpeg -i logo1.avi -c:v mjpeg -q:v 3 -c:a copy logo1_mjpeg.avi

Затем `logo1_mjpeg.avi` нужно положить в `assets/` вместо старого файла
(или под прежним именем `logo1.avi`).

Размер при этом вырастает: 3.6 MB → ~7 MB. Но т.к. ffmpeg_avi_mp3.exe
(6.16 MB) выкидывается, общий размер пакета даже уменьшается на ~2.7 MB.


CLI
---
    logoMaker <input.avi> <output.avi> <font.otf> "<text>" [x] [y] [size] [--widescreen]

Параметры:
    input.avi    — AVI с MJPG-видео (см. выше)
    output.avi   — куда писать результат (MJPG + копия аудио)
    font.otf     — путь к OTF/TTF шрифту (загружается в private font collection)
    text         — текст для наложения; \n внутри строки превращается в перенос
                   строки; пустые строки автоматически схлопываются (как в py)
    x, y         — позиция в пикселях (по умолчанию 87, 361)
    size         — размер шрифта в пикселях (по умолчанию 36)
    --widescreen — single-pass letterbox для Widescreen Fix:
                   контент масштабируется в 1920×812 и паддится чёрным
                   до 1920×1080. Выход остаётся MJPEG (не XviD —
                   см. «Известные ограничения»).

Примеры:
    logoMaker.exe logo1_mjpeg.avi out.avi aurora.otf "MAFIA MOD\nv0.12"
    logoMaker.exe logo1_mjpeg.avi out.avi aurora.otf "Текст" 87 361 36 --widescreen
    logoMaker.exe logo1_mjpeg.avi out.avi aurora.otf "Тест кириллицы"


Что проверено
-------------
* Многострочный текст, авто-схлопывание пустых строк.
* Кириллица в тексте (через CommandLineToArgvW + GDI+ wide-char).
* Кириллические пути к файлам (через CreateFileW).
* --widescreen режим: letterbox 1920×1080 с чёрной рамкой.
* Аудио-стрим (MP3) копируется побайтно, без перекодирования.
* Пустые видео-чанки в AVI («drop frame», размер 0) пропускаются —
  плеер использует предыдущий декодированный кадр.


Известные ограничения
---------------------
1. Вход должен быть MJPG, не FMP4/H.264/etc. См. «Что нужно сделать
   перед использованием».

2. --widescreen выдаёт MJPEG, а не XviD. Если Widescreen Fix
   принципиально требует именно `libxvid` для совместимости —
   придётся либо оставить старый ffmpeg, либо звать XviD-кодек,
   установленный в системе (что не bundle-friendly).

3. JPEG-качество (Q=85) даёт чуть больший выходной файл, чем
   ffmpeg `-q:v 3`: ~13 MB vs ~7 MB. Изменить можно константой
   `quality` в `logo_maker.cpp`. Визуально разницы при Q=85 нет.

4. Скорость: ~7 секунд на 246 кадров через WSL→Windows interop.
   На реальной Windows будет быстрее.


Как пересобрать
---------------
На любом Linux с MinGW-w64:

    apt install g++-mingw-w64-x86-64
    ./build.sh

Скрипт зовёт:

    x86_64-w64-mingw32-g++ -Os -s -fno-exceptions -fno-rtti \
        -ffunction-sections -fdata-sections -Wl,--gc-sections \
        -static-libgcc -static-libstdc++ \
        logo_maker.cpp -o logoMaker.exe \
        -lgdiplus -lole32 -luuid -lshlwapi -lshell32

На Windows можно собрать в MSVC или mingw из MSYS2 — флаги те же.


Состав папки
------------
    logoMaker.exe   — собранный бинарь Win64 (47 104 байт)
    logo_maker.cpp  — исходник C++
    build.sh        — скрипт пересборки через MinGW-w64
    README.txt      — этот файл


Лицензия / авторство
--------------------
Код написан как замена связки logo_maker.py + ffmpeg_avi_mp3.exe
для Mafia Mod Installer 0.12 (kolya / medved443). Используется только
системные Windows API (GDI+, ole32, shlwapi, shell32) — никаких
сторонних библиотек.
