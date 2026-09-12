@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem Usage:
rem   run.bat                    -> release, windowed
rem   run.bat headless [ROM]     -> release, no window (for testing)
rem   run.bat debug [ROM]        -> debug build + debug logs
rem   run.bat trace [ROM]        -> debug build + per-write C trace (log-only, console off)
rem   run.bat release [ROM]      -> release build + custom rom
rem
rem "headless" may also be used as the second argument: run.bat debug headless
rem ROM paths must not contain '!' or ' (cmd delayed expansion / PS quoting).
rem
rem All console output is appended to:
rem   build\log\session.log
rem   build\log\run_YYYYMMDD_HHMMSS.log
rem Exit code: 0 = ok, 1 = build or run failed.

set MODE=release
set TRACE=0
set HEADLESS=
set ROMARG=rom\super-mario-bros.nes

if /i "%~1"=="headless" (
  set HEADLESS=--headless
  if not "%~2"=="" set ROMARG=%~2
)

if /i "%~1"=="debug" (
  set MODE=debug
  if /i "%~2"=="headless" (
    set HEADLESS=--headless
  ) else if not "%~2"=="" (
    if /i not "%~2"=="trace" set ROMARG=%~2
  )
) else if /i "%~1"=="trace" (
  set MODE=debug
  set TRACE=1
  if /i "%~2"=="headless" (
    set HEADLESS=--headless
  ) else if not "%~2"=="" (
    if /i not "%~2"=="debug" if /i not "%~2"=="release" set ROMARG=%~2
  )
) else if /i "%~1"=="release" (
  set MODE=release
  if /i "%~2"=="headless" (
    set HEADLESS=--headless
  ) else if not "%~2"=="" (
    set ROMARG=%~2
  )
) else if not "%~1"=="" (
  if /i not "%~1"=="headless" set ROMARG=%~1
)

set LOGDIR=build\log
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

rem timestamp for per-run file
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set TS=%%i
set RUNLOG=%LOGDIR%\run_!TS!.log
set SESSIONLOG=%LOGDIR%\session.log

echo [1/2] Rebuilding C core (!MODE!)...
call familybox\build.bat !MODE!
if errorlevel 1 (
  echo BUILD FAILED
  pause
  exit /b 1
)

rem clear inherited debug/trace flags so a release run stays quiet
set FAMILYBOX_DEBUG=
set FAMILYBOX_TRACE=
set PYTHONUNBUFFERED=
if /i "!MODE!"=="debug" (
  set FAMILYBOX_DEBUG=1
  set PYTHONUNBUFFERED=1
)
if "!TRACE!"=="1" set FAMILYBOX_TRACE=1

echo [2/2] Starting FamilyBox with !ROMARG! !HEADLESS!
echo Log file: !RUNLOG!
if "!TRACE!"=="1" echo TRACE is ON - output goes to !RUNLOG! only, console output disabled for speed

echo ===== RUN !TS! mode=!MODE! trace=!TRACE! headless=!HEADLESS! rom=!ROMARG! =====>> "%SESSIONLOG%"
echo ===== RUN !TS! mode=!MODE! trace=!TRACE! headless=!HEADLESS! rom=!ROMARG! =====> "%RUNLOG%"

rem powershell exit code == uv/python exit code via `exit $LASTEXITCODE`
rem ($global:LASTEXITCODE=1 first so a missing uv cannot slip through as success)
if "!TRACE!"=="1" (
  rem trace output is huge - no per-line tee, no powershell (its ">>" writes
  rem UTF-16); raw cmd redirect keeps the runlog plain text and grep-able
  uv run python main.py !HEADLESS! "!ROMARG!" >> "!RUNLOG!" 2>&1
) else (
  powershell -NoProfile -Command "$global:LASTEXITCODE=1; $ErrorActionPreference='Continue'; & uv run python main.py !HEADLESS! '!ROMARG!' 2>&1 | ForEach-Object { Write-Host $_; Add-Content -Path '!SESSIONLOG!' -Value $_ -Encoding UTF8; Add-Content -Path '!RUNLOG!' -Value $_ -Encoding UTF8 }; exit $LASTEXITCODE"
)

if %errorlevel% NEQ 0 (
  echo.
  echo GAME EXITED WITH ERROR - see !RUNLOG!
  pause
  set RC=1
)

echo.>> "%SESSIONLOG%"
echo ===== END !TS! =====>> "%SESSIONLOG%"
echo ===== END !TS! =====>> "%RUNLOG%"
echo Done. Logs: !RUNLOG!
if defined RC exit /b 1
exit /b 0
