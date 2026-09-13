@echo off
setlocal
cd /d "%~dp0"

echo [1/3] Ensure C core is built...
if not exist "src\window\familybox_core.dll" (
  call scripts\build.bat
  if errorlevel 1 exit /b 1
)

echo [2/3] Install PyInstaller (dev)...
uv add --dev pyinstaller
if errorlevel 1 exit /b 1

echo [3/3] Package EXE (onedir, more reliable with native DLL)...
rem ROM-less distribution: no ROM is bundled. The app opens in cartridge-
rem loader mode (O-key file dialog / drag & drop). To bundle one anyway,
rem add back:  --add-data "rom\super-mario-bros-ntsc.nes;rom" ^
uv run pyinstaller --noconfirm --clean ^
  --name FamilyBox ^
  --windowed ^
  --add-binary "src\window\familybox_core.dll;familybox" ^
  --hidden-import pygame ^
  --paths src ^
  src\window\main.py

if errorlevel 1 (
  echo PACKAGE FAILED
  exit /b 1
)

echo.
echo Done. Run: dist\FamilyBox\FamilyBox.exe
echo (ROM-less build: launch, press O or drop a .nes to play)
