# Mafia Mod Installer

Универсальный установщик модов для **Mafia: The City of Lost Heaven**  
Univerzalni instalator modu pro **Mafia: The City of Lost Heaven**  
A universal mod installer for **Mafia: The City of Lost Heaven**

<img width="714" height="470" alt="image" src="https://github.com/user-attachments/assets/d2a93133-c610-4572-aee5-6a370c4de0ec" />


## Содержание / Obsah / Table of contents

- [Быстрый старт / Rychly start / Quick start](#быстрый-старт--rychly-start--quick-start)
- [Установка модов / Instalace modu / Installing mods](#установка-модов--instalace-modu--installing-mods)
- [Возврат к чистой игре / Navrat k ciste hre / Restoring clean game](#возврат-к-чистой-игре--navrat-k-ciste-hre--restoring-clean-game)
- [Возможности / Funkce / Features](#возможности--funkce--features)
- [Системные требования / Systemove pozadavky / System requirements](#системные-требования--systemove-pozadavky--system-requirements)
---

## Быстрый старт / Rychly start / Quick start

### RU

Чтобы установить свой первый мод:

1. Откройте вкладку **"Загрузка мода"**.
2. Нажмите кнопку выбора и укажите скачанный архив с модом.
3. Введите название мода и нажмите **"Загрузить"**.
4. Мод появится в библиотеке на вкладке **"Библиотека модов"**.

### CZ

Prvni instalace modu:

1. Otevřete zalozku **"Nahrat mod"**.
2. Kliknete na tlacitko vyberu a vyberte stazeny archiv s modem.
3. Zadejte nazev modu a kliknete na **"Nahrat"**.
4. Mod se objevi v knihovne na zalozce **"Knihovna modu"**.

### EN

To install your first mod:

1. Open the **"Upload mod"** tab.
2. Click the browse button and select the downloaded mod archive.
3. Enter a name for the mod and click **"Upload"**.
4. The mod will appear in your library under the **"Mod library"** tab.

---

## Установка модов / Instalace modu / Installing mods

### RU

1. Перейдите на вкладку **"Установка"**.
2. Убедитесь, что выбрана папка с игрой. Если нет — нажмите **"Добавить игру"** и укажите путь (например, папку Mafia в Steam).
3. В блоке **"Менеджер модов"** отметьте галочками нужные моды.
4. Нажмите **"Установить в игру"** или **"Установить и запустить"**.

### CZ

1. Prejdete na zalozku **"Instalace"**.
2. Ujistete se, ze je vybrana slozka se hrou. Pokud ne — kliknete na **"Pridat hru"** a vyberte cestu (napr. slozku Mafia ve Steamu).
3. V bloku **"Spravce modu"** zaskrtnete pozadovane mody.
4. Kliknete na **"Instalovat do hry"** nebo **"Instalovat a spustit"**.

### EN

1. Go to the **"Install"** tab.
2. Make sure the game folder is selected. If not — click **"Add game"** and browse to the game folder (e.g. the Mafia folder in Steam).
3. In the **"Mod manager"** panel, check the mods you want to install.
4. Click **"Install to game"** or **"Install and run"**.

---

## Возврат к чистой игре / Navrat k ciste hre / Restoring clean game

### RU

1. Закройте игру.
2. На вкладке **"Установка"** в **"Менеджере модов"** снимите все галочки.
3. Нажмите **"Установить в игру"**.

### CZ

1. Zavřete hru.
2. Na zalozce **"Instalace"** ve **"Spravci modu"** zruste vsechna zaskrtnuti.
3. Kliknete na **"Instalovat do hry"**.

### EN

1. Close the game.
2. On the **"Install"** tab, in the **"Mod manager"** panel, uncheck all mods.
3. Click **"Install to game"**.

---

## Возможности / Funkce / Features

### RU

- **Смена языка:** русский, английский, чешский, французский. Можно добавить свой язык — положите `.json` файл в папку `languages` рядом с программой.
- **Патч rw_data.dll:** исправление для поддержки модов.
- **Бэкапы игры:** сохранение и восстановление состояния игры. Можно откатить только один экземпляр, не трогая другие.
- **Автоматический чистый бэкап:** создаётся при первом добавлении игры. Всегда можно вернуться к оригинальным файлам.
- **Бэкап сохранений:** ручной и автоматический (включается в настройках). Для каждого бэкапа запоминается набор активных модов.
- **Очистка ресурсов:** удаление папок, созданных модами (tables, maps, models и т.д.).
- **Сборка .mmi:** упаковка нескольких модов в один файл. Можно указать целевую версию игры.
- **Проверка версии игры:** кнопка "?" рядом с путём показывает версию (1.0, 1.1, 1.2) и состояние rw_data.dll. При несовпадении версий — предупреждение в лог.
- **Несколько версий в архиве:** если мод содержит варианты для разных версий игры, программа добавит их отдельно.
- **Средство устранения неполадок:** проверяет совместимость и даёт рекомендации.

### CZ

- **Zmena jazyka:** rustina, anglictina, cestina, francouzstina. Muzete pridat vlastni jazyk — staci vlozit `.json` soubor do slozky `languages` vedle programu.
- **Patch rw_data.dll:** oprava pro podporu modu.
- **Zalohovani hry:** ulozeni a obnoveni stavu hry. Muzete vratit zmeny jen pro jednu instanci.
- **Automaticka cista zaloha:** vytvori se pri prvnim pridani hry. Vzdy se muzete vratit k puvodnim souborum.
- **Zalohovani uloznych pozic:** rucni i automaticke (zapina se v nastaveni). Kazda zaloha obsahuje informaci o aktivni sade modu.
- **Vycišteni zdroju:** odstraneni slozek vytvorenych mody (tables, maps, models atd.).
- **Vytvareni .mmi:** zabaleni nekolika modu do jednoho souboru. Muzete nastavit cilovou verzi hry.
- **Kontrola verze hry:** tlacitko "?" vedle cesty ukaze verzi (1.0, 1.1, 1.2) a stav rw_data.dll. Pri neshode verzi — varovani v logu.
- **Vice verzi v archivu:** pokud mod obsahuje varianty pro ruzne verze hry, program je prida zvlast.
- **Nastroj pro reseni problemu:** kontroluje kompatibilitu a dava doporuceni.

### EN

- **Language:** Russian, English, Czech, French. You can add your own language — just place a `.json` file in the `languages` folder next to the program.
- **rw_data.dll patch:** fix for mod support.
- **Game backups:** save and restore game state. You can roll back only one instance without affecting others.
- **Automatic clean backup:** created when you first add a game. You can always return to the original files.
- **Savegame backups:** manual and automatic (enabled in settings). Each backup remembers the active mod set.
- **Resource cleanup:** removes folders created by mods (tables, maps, models, etc.).
- **.mmi packaging:** pack multiple mods into a single file. You can set a target game version.
- **Game version check:** the "?" button next to the game path shows the version (1.0, 1.1, 1.2) and rw_data.dll status. Version mismatches are logged as warnings.
- **Multiple versions in one archive:** if a mod contains variants for different game versions, the program adds them separately.
- **Troubleshooter:** checks compatibility and provides recommendations.

---

## Системные требования / Systemove pozadavky / System requirements

### RU

- Windows
- Установленная игра Mafia: The City of Lost Heaven

### CZ

- Windows
- Instalovana hra Mafia: The City of Lost Heaven

### EN

- Windows
- Installed game Mafia: The City of Lost Heaven

---

---

Приятной игры! / Hezkou hru! / Enjoy the game!
