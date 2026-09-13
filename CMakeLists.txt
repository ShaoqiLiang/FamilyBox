cmake_minimum_required(VERSION 3.16)
project(familybox_core LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
# Core language: C++ (decision doc/find/2026-09-13T14-41-41.md) — window
# C++11-C++20, pinned here to the ceiling. No C++23+ features allowed.
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_C_VISIBILITY_PRESET hidden)

option(FB_DEBUG "Enable FamilyBox debug logging" OFF)

if(FB_DEBUG)
  set(CMAKE_BUILD_TYPE Debug CACHE STRING "Build type" FORCE)
else()
  if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
  endif()
endif()

set(FB_OUTPUT_DIR "${CMAKE_CURRENT_SOURCE_DIR}/src/window")
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${FB_OUTPUT_DIR}")
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${FB_OUTPUT_DIR}")

if(WIN32)
  set(CMAKE_SHARED_LIBRARY_PREFIX "")
endif()

# Marker so Python knows which flavour was built
if(FB_DEBUG)
  file(WRITE "${FB_OUTPUT_DIR}/.fb_debug" "1\n")
else()
  file(REMOVE "${FB_OUTPUT_DIR}/.fb_debug")
endif()

add_subdirectory(src/core)
