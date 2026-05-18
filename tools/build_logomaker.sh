#!/bin/bash
# Сборка logoMaker.exe из logo_maker.cpp под Windows x64 через MinGW-w64.
# Требует: x86_64-w64-mingw32-g++ (на Ubuntu: apt install g++-mingw-w64-x86-64).

set -e
cd "$(dirname "$0")"

x86_64-w64-mingw32-g++ \
    -Os -s \
    -fno-exceptions -fno-rtti \
    -ffunction-sections -fdata-sections -Wl,--gc-sections \
    -static-libgcc -static-libstdc++ \
    logo_maker.cpp \
    -o logoMaker.exe \
    -lgdiplus -lole32 -luuid -lshlwapi -lshell32

ls -la logoMaker.exe
echo "Размер: $(stat -c %s logoMaker.exe 2>/dev/null || stat -f %z logoMaker.exe) байт"
