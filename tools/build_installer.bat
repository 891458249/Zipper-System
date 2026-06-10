@echo off
REM ====================================================================
REM Zipper System standalone installer build script
REM ====================================================================
REM
REM One-shot build: installs PyInstaller (idempotent) and packages
REM installer_gui.py + modules/ + zipper_system/ + resources/ into a
REM single windowed installer\ZipperSystemInstaller.exe.
REM
REM Distribution: copy installer\ZipperSystemInstaller.exe to any
REM Windows machine -- no Python installation needed on the target.
REM
REM Usage: double-click this file, or run from a shell in the repo root.
REM ====================================================================

REM bat lives in tools/, so step up to the repo root as cwd.
cd /d "%~dp0..\"

echo.
echo [1/3] Ensuring PyInstaller is installed...
python -m pip install pyinstaller --quiet --disable-pip-version-check
if errorlevel 1 (
    echo [ERROR] pip install pyinstaller failed.
    pause
    exit /b 1
)

echo.
echo [2/3] Building ZipperSystemInstaller.exe ^(this takes ~30s^)...
python -m PyInstaller tools\build_installer.spec --noconfirm --clean --distpath installer
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Done.
echo Output: %~dp0..\installer\ZipperSystemInstaller.exe
echo.
echo Distribute that single .exe to any Windows machine and double-click
echo to install Zipper System onto the selected Maya versions.
echo.
pause
