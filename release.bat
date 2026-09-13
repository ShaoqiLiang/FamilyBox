@echo off
setlocal
cd /d "%~dp0"

rem Package FamilyBox onedir EXE.
rem 1) Always rebuild C core (release) so package matches a fresh run.bat core.
rem 2) PyInstaller freeze.
rem 3) SHA256 compare src\window\familybox_core.dll vs packaged DLL.

echo [1/4] Force rebuild C core (release)...
call scripts\build.bat release
if errorlevel 1 (
  echo [ERROR] C core build failed
  exit /b 1
)
if not exist "src\window\familybox_core.dll" (
  echo [ERROR] expected DLL missing after build: src\window\familybox_core.dll
  exit /b 1
)

echo [2/4] Ensure PyInstaller (dev)...
uv add --dev pyinstaller
if errorlevel 1 exit /b 1

echo [3/4] Package EXE (onedir)...
rem ROM-less distribution. Launch, press O or drop a .nes to play.
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

echo [4/4] Verify packaged DLL hash...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\msi\verify_core_dll_hash.ps1"
if errorlevel 1 (
  echo.
  echo [ERROR] hash verification failed - do not ship this dist\FamilyBox
  exit /b 1
)

echo.
echo Done. Run: dist\FamilyBox\FamilyBox.exe
echo (ROM-less: press O or drop a .nes to play)
exit /b 0
