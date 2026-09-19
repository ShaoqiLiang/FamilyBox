@echo off
setlocal
cd /d "%~dp0"

rem Package FamilyBox onedir EXE.
rem 1) Always rebuild C core (release) so package matches a fresh run.bat core.
rem 2) PyInstaller freeze.
rem 3) SHA256 compare src\window\familybox_core.dll vs packaged DLL.

echo [1/5] Force rebuild C core (release)...
call scripts\build.bat release
if errorlevel 1 (
  echo [ERROR] C core build failed
  exit /b 1
)
if not exist "src\window\familybox_core.dll" (
  echo [ERROR] expected DLL missing after build: src\window\familybox_core.dll
  exit /b 1
)

echo [2/5] Ensure PyInstaller (dev)...
uv add --dev pyinstaller
if errorlevel 1 exit /b 1

echo [3/5] Decrypt assets to build\assets (compile-time decrypt)...
uv run python scripts\prepare_assets.py
if errorlevel 1 (
  echo [ERROR] asset decrypt failed
  exit /b 1
)
if not exist "build\assets\familybox.ico" (
  echo [ERROR] familybox.ico missing after decrypt - is keys\logo_private present?
  exit /b 1
)

echo [4/5] Package EXE (onedir)...
rem ROM-less distribution. Launch, press O or drop a .nes to play.
rem Decrypted plaintext lives only in build\assets (gitignored); the repo
rem itself carries ciphertext (.enc) plus the local-only key keys\logo_private.
uv run pyinstaller --noconfirm --clean ^
  --name FamilyBox ^
  --windowed ^
  --icon "build\assets\familybox.ico" ^
  --add-data "build\assets;assets" ^
  --add-data "src\window\assets\GitHub_Lockup_Black.png;assets" ^
  --add-binary "src\window\familybox_core.dll;familybox" ^
  --hidden-import pygame ^
  --paths src ^
  src\window\main.py
set PKG_RC=%errorlevel%
del build\familybox.ico >nul 2>&1
if not "%PKG_RC%"=="0" (
  echo PACKAGE FAILED
  exit /b 1
)

echo [5/5] Verify packaged DLL hash...
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
