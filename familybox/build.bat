@echo off
setlocal
cd /d "%~dp0.."

rem Usage: familybox\build.bat [debug|release]
set MODE=release
if /i "%~1"=="debug" set MODE=debug
if /i "%~1"=="release" set MODE=release

set CC=gcc
where gcc >nul 2>&1 && set "CMAKE_C_COMPILER=gcc"

if /i "%MODE%"=="debug" (
  set FB_DEBUG_FLAG=ON
  set CMAKE_TYPE=Debug
) else (
  set FB_DEBUG_FLAG=OFF
  set CMAKE_TYPE=Release
)

echo === FamilyBox C core build (%MODE%) ===
if not exist build mkdir build
cmake -S . -B build -G "MinGW Makefiles" ^
  -DCMAKE_BUILD_TYPE=%CMAKE_TYPE% ^
  -DFB_DEBUG=%FB_DEBUG_FLAG% ^
  -DCMAKE_C_COMPILER=%CC%
if errorlevel 1 (
  echo CMAKE CONFIGURE FAILED
  exit /b 1
)
cmake --build build --config %CMAKE_TYPE%
if errorlevel 1 (
  echo BUILD FAILED
  exit /b 1
)
echo Built familybox\familybox_core.dll  [%MODE%]
if /i "%MODE%"=="debug" (
  echo Debug logging is ON - stderr lines start with [FB]
) else (
  echo Debug logging is OFF
)
