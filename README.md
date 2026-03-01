# Mafia Mod Installer
**v0.7-beta**

Портативный универсальный установщик модов  
для игры Mafia: The City of Lost Heaven

**Автор:** medved443  

---

## СОДЕРЖАНИЕ

**Русский язык**  
1. Введение ............................................................. 3  
2. Системные требования ............................................. 4  
3. Установка и первый запуск ..................................... 5  
4. Основной интерфейс ............................................... 6  
   4.1. Вкладка «Установка» ...................................... 7  
   4.2. Вкладка «Установленные моды» ......................... 9  
   4.3. Вкладка «О программе» ................................... 10  
5. Функции и возможности .......................................... 11  
   5.1. Установка модов ........................................... 11  
   5.2. Создание и восстановление бэкапов .................... 12  
   5.3. Hard Restore (жёсткое восстановление) .............. 13  
   5.4. Очистка распакованных ресурсов ........................ 14  
   5.5. Drag & Drop ................................................ 15  
   5.6. Мультиязычность ........................................... 15  
6. Возможные проблемы и решения ................................ 16  
7. Лицензия и контакты ............................................. 17  

**English**  
1. Introduction ...................................................... 18  
2. System Requirements ............................................. 19  
3. Installation and First Launch ................................ 20  
4. Main Interface ................................................... 21  
   4.1. "Install" Tab ............................................. 22  
   4.2. "Installed Mods" Tab ..................................... 24  
   4.3. "About" Tab ............................................... 25  
5. Features and Capabilities ...................................... 26  
   5.1. Mod Installation .......................................... 26  
   5.2. Backup Creation and Restoration ....................... 27  
   5.3. Hard Restore .............................................. 28  
   5.4. Cleanup Unpacked Resources ............................. 29  
   5.5. Drag & Drop ............................................... 30  
   5.6. Multilingual Interface ................................... 30  
6. Troubleshooting ................................................. 31  
7. License and Contacts ............................................ 32  

**Čeština**  
1. Úvod ................................................................. 33  
2. Systémové požadavky ............................................ 34  
3. Instalace a první spuštění ................................... 35  
4. Hlavní rozhraní ................................................. 36  
   4.1. Karta „Instalace“ ........................................ 37  
   4.2. Karta „Nainstalované mody“ ............................. 39  
   4.3. Karta „O aplikaci“ ....................................... 40  
5. Funkce a možnosti ............................................... 41  
   5.1. Instalace modů ............................................ 41  
   5.2. Vytváření a obnova záloh ............................... 42  
   5.3. Hard Restore .............................................. 43  
   5.4. Vyčištění rozbalených zdrojů ........................... 44  
   5.5. Drag & Drop ............................................... 45  
   5.6. Vícejazyčné rozhraní ..................................... 45  
6. Možné problémy a řešení ........................................ 46  
7. Licence a kontakty .............................................. 47  

---

## Русский язык

### 1. Введение

**Mafia Mod Installer v0.7-beta** — это полностью портативная программа (не требует установки), предназначенная для удобной установки модов в классическую игру Mafia: The City of Lost Heaven (2002 года).

Программа объединяет в себе лучшее из нескольких предыдущих версий и добавляет современные функции:
- Поддержка архивов ZIP, 7z, RAR, TAR, GZ (при наличии patoolib)
- Drag & Drop файлов и папок прямо в окно программы
- Автоматическое определение корневой папки мода
- Создание резервных копий (бэкапов) всей игры перед установкой
- Обычное и жёсткое (Hard Restore) восстановление из бэкапа
- Очистка распакованных папок ресурсов (maps, models, sounds и т.д.)
- Отдельная история модов, бэкапов и readme для каждой копии игры
- Многоязычный интерфейс: русский, английский, чешский
- Иконка приложения (mmi.ico) при сборке в .exe

Программа работает с любыми версиями игры (Steam, GOG, пиратские, репаки).

### 2. Системные требования

Минимальные:
- Windows 7 / 8 / 10 / 11 (32 или 64 бит)
- Установленная игра Mafia: The City of Lost Heaven (любая версия)
- ~50 МБ свободного места + место под бэкапы и моды

Для ручной сборки (если используете .pyw-файл):
- Python 3.9–3.12
- Библиотеки: patoolib (для 7z/rar), tkinterdnd2 (для drag & drop)
- Nuitka (для компиляции в .exe)

### 3. Установка и первый запуск

1. Скачайте готовый .exe (рекомендуется) или файл beta 0.7.pyw
2. Если .pyw — соберите в .exe с помощью Nuitka (см. инструкцию в конце)
3. Положите файл в удобную папку (можно на флешку)
4. Запустите программу
5. При первом запуске появится рекомендация сделать бэкап чистой игры
6. Выберите папку игры → программа запомнит её

### 4. Основной интерфейс

После запуска вы увидите три вкладки и верхнюю панель.

Верхняя панель:
- Выбор языка (ru / en / cz)
- Выбор копии игры (если добавлено несколько)

#### 4.1. Вкладка «Установка»

Основная вкладка для работы с модами:
- Поле «Папка игры» + кнопка «Добавить игру»
- Поле «Мод / архив» + кнопка «Выбрать» (или перетащите файл)
- Кнопки:
  - Установить мод
  - Создать бэкап
  - Восстановить (обычное)
  - Hard Restore
  - Очистить ресурсы
- Окно лога внизу

#### 4.2. Вкладка «Установленные моды»

Таблица со списком модов для выбранной копии игры:
- Название
- Дата установки
- Количество файлов
- Папка бэкапа
- Readme-файлы

Кнопки:
- Обновить список
- Открыть папку бэкапа
- Открыть readme
- Очистить список (только историю, файлы игры не удаляются)

#### 4.3. Вкладка «О программе»

- Краткое описание
- Версия v0.7-beta
- Автор и год
- Путь к папке данных
- Кнопка перехода в группу ВКонтакте

### 5. Функции и возможности

#### 5.1. Установка модов

Поддерживаемые форматы: .zip, .7z, .rar, .tar, .gz, папки  
Как работает:
1. Выберите или перетащите мод
2. Программа распаковывает (если архив) и ищет корневую папку
3. Копирует файлы в игру
4. Сохраняет readme в отдельную папку mods/
5. Создаёт запись в истории

#### 5.2. Создание и восстановление бэкапов

- «Создать бэкап» → копирует всю папку игры в backups/
- «Восстановить» → копирует файлы из выбранного бэкапа поверх существующих (без удаления лишнего)

#### 5.3. Hard Restore (жёсткое восстановление)

Опасная функция для полного отката:
1. Выбираете бэкап
2. Два подтверждения
3. Программа удаляет ВСЁ внутри папки игры
4. Копирует содержимое бэкапа

Используйте только если обычное восстановление не помогает.

#### 5.4. Очистка распакованных ресурсов

Удаляет папки (maps, models, sounds, textures, scripts, fonts и др.),  
если соответствующий .dta-файл есть в корне игры.

#### 5.5. Drag & Drop

Перетащите архив или папку мода прямо в окно — путь вставится автоматически.

#### 5.6. Мультиязычность

Автоматическое определение языка системы.  
Можно сменить вручную в правом верхнем углу.

### 6. Возможные проблемы и решения

Проблема                                 | Решение  
----------------------------------------|------------------------------------------------  
Нет Drag & Drop                         | Установите tkinterdnd2 перед сборкой  
Не распаковываются 7z/RAR               | Установите patoolib  
Hard Restore не работает                | Запустите от имени администратора  
Иконка не применяется                   | mmi.ico должен лежать рядом с .pyw при сборке  
Программа не видит игру                 | Добавьте путь вручную через «Добавить игру»

### 7. Лицензия и контакты

Программа бесплатна, распространяется «как есть».  
Автор не несёт ответственности за потерю данных игры.

Группа ВКонтакте: https://vk.com/mafia_and_mafia2_modding  
Автор: medved443

---

## English

### 1. Introduction

**Mafia Mod Installer v0.7-beta** is a fully portable mod installer for Mafia: The City of Lost Heaven (2002).

Key features:
- ZIP, 7z, RAR, TAR, GZ support
- Drag & Drop
- Automatic mod root detection
- Backup creation & restoration
- Hard Restore
- Unpacked resources cleanup
- Multilingual UI (English, Russian, Czech)
- Separate data per game copy

### 2. System Requirements

Windows 7+  
Mafia: The City of Lost Heaven installed  
~50 MB free space + space for backups/mods

### 3. Installation and First Launch

1. Download .exe or beta 0.7.pyw
2. Run the file
3. On first launch: recommendation to backup clean game
4. Select game folder

### 4. Main Interface

Three tabs + top bar (language & game selection).

#### 4.1. "Install" Tab
- Game folder selector
- Mod/archive field + Select button + Drag & Drop
- Buttons: Install, Create Backup, Restore, Hard Restore, Cleanup
- Log window

#### 4.2. "Installed Mods" Tab
- Table: Name, Date, Files, Backup folder, Readme
- Buttons: Refresh, Open backup, Open readme, Clear list

#### 4.3. "About" Tab
- Program info
- VK group link
- Data folder path

### 5. Features and Capabilities

#### 5.1. Mod Installation
Supports archives and folders, auto root detection, readme saving.

#### 5.2. Backup Creation and Restoration
Create full game copy, normal restore merges files.

#### 5.3. Hard Restore
Deletes everything in game folder and replaces with backup content (triple confirmation).

#### 5.4. Cleanup Unpacked Resources
Removes extracted folders if .dta files are present.

#### 5.5. Drag & Drop
Drag mod file/folder into window.

#### 5.6. Multilingual Interface
Auto language detection + manual switch.

### 6. Troubleshooting

No Drag & Drop → install tkinterdnd2  
No 7z/RAR support → install patoolib  
Hard Restore fails → run as Administrator

### 7. License and Contacts

Free software, use at your own risk.

VK group: https://vk.com/mafia_and_mafia2_modding  
Author: medved443

---

## Čeština

### 1. Úvod

**Mafia Mod Installer v0.7-beta** je přenosný instalátor modů pro hru Mafia: The City of Lost Heaven (2002).

Hlavní funkce:
- Podpora ZIP, 7z, RAR, TAR, GZ
- Drag & Drop
- Automatická detekce kořene modu
- Vytváření a obnova záloh
- Hard Restore
- Vyčištění rozbalených zdrojů
- Vícejazyčné rozhraní (čeština, ruština, angličtina)

### 2. Systémové požadavky

Windows 7+  
Nainstalovaná hra Mafia: The City of Lost Heaven  
~50 MB volného místa + místo pro zálohy/mody

### 3. Instalace a první spuštění

1. Stáhněte .exe nebo beta 0.7.pyw
2. Spusťte soubor
3. Při prvním spuštění: doporučení vytvořit zálohu čisté hry
4. Vyberte složku hry

### 4. Hlavní rozhraní

Tři karty + horní lišta (jazyk a výběr hry).

#### 4.1. Karta „Instalace“
- Výběr složky hry
- Pole pro mod/archiv + tlačítko „Vybrat“ + Drag & Drop
- Tlačítka: Instalovat, Vytvořit zálohu, Obnovit, Hard Restore, Vyčistit zdroje

#### 4.2. Karta „Nainstalované mody“
- Tabulka: Název, Datum, Souborů, Složka zálohy, Readme
- Tlačítka: Obnovit seznam, Otevřít zálohu, Otevřít readme, Vymazat seznam

#### 4.3. Karta „O aplikaci“
- Informace o programu
- Odkaz na VK skupinu
- Cesta k datové složce

### 5. Funkce a možnosti

#### 5.1. Instalace modů
Podpora archivů a složek, automatická detekce kořene, ukládání readme.

#### 5.2. Vytváření a obnova záloh
Plná kopie hry, normální obnova přepisuje soubory.

#### 5.3. Hard Restore
Smaže vše v herní složce a nahradí obsahem zálohy (trojí potvrzení).

#### 5.4. Vyčištění rozbalených zdrojů
Odstraní složky (maps, models, sounds atd.), pokud je přítomen .dta soubor.

#### 5.5. Drag & Drop
Přetáhněte mod do okna.

#### 5.6. Vícejazyčné rozhraní
Automatická detekce + ruční výběr.

### 6. Možné problémy a řešení

Žádný Drag & Drop → nainstalujte tkinterdnd2  
Žádná podpora 7z/RAR → nainstalujte patoolib  
Hard Restore nefunguje → spusťte jako administrátor

### 7. Licence a kontakty

Software zdarma, používáte na vlastní nebezpečí.

VK skupina: https://vk.com/mafia_and_mafia2_modding  
Autor: medved443
