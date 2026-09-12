@echo off
setlocal
cd /d "%~dp0"

echo [1/3] Ensure C core is built...
if not exist "familybox\familybox_core.dll" (
  call familybox\build.bat
  if errorlevel 1 exit /b 1
)

echo [2/3] Install PyInstaller (dev)...
uv add --dev pyinstaller
if errorlevel 1 exit /b 1

echo [3/3] Package EXE (onedir, more reliable with native DLL)...
uv run pyinstaller --noconfirm --clean ^
  --name FamilyBox ^
  --windowed ^
  --add-binary "familybox\familybox_core.dll;familybox" ^
  --add-data "rom\super-mario-bros.nes;rom" ^
  --hidden-import pygame ^
  main.py

if errorlevel 1 (
  echo PACKAGE FAILED
  exit /b 1
)

echo.
echo Done. Run: dist\FamilyBox\FamilyBox.exe
echo (ROM is bundled; you can also drop other .nes next to the exe)
