@echo off
rem ============================================================
rem  Сборка WindowPresets.exe (onefile, без консоли).
rem  Результат: dist\WindowPresets_portable\WindowPresets.exe —
rem  единственный exe (без дубликатов в dist). Данные
rem  (config.json, presets.json, previews, logs) создаются
rem  рядом с exe. Иконка exe — ico\app.ico (автосборка из
rem  самого свежего PNG в ico\ при каждом запуске программы;
rem  если хочешь другую иконку exe — положи PNG в ico\ и
rem  запусти программу один раз из исходников).
rem ============================================================

cd /d "%~dp0"

if not exist "dist\WindowPresets_portable" mkdir "dist\WindowPresets_portable"

py -3.14 -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name WindowPresets ^
    --icon "ico\app.ico" ^
    --add-data "assets;assets" ^
    --add-data "ico;ico" ^
    main.py

echo.
if exist "dist\WindowPresets.exe" (
    rem 🔴 Единственный exe живёт в portable-папке: ПЕРЕНОСИМ,
    rem а не копируем — дублей в dist не остаётся.
    move /Y "dist\WindowPresets.exe" "dist\WindowPresets_portable\WindowPresets.exe" >nul
    echo Готово: dist\WindowPresets_portable\WindowPresets.exe
) else (
    echo ОШИБКА: exe не создан, смотри вывод выше.
)
pause
