# FamilyBox C core — single shared library from the nes/ modules.
# Public ABI header: include/familybox.h (v1, frozen — add-only; the
# fb_core.h rename lands with the v2 contract, design doc §4).
cmake_minimum_required(VERSION 3.16)

# MinGW latches its default _WIN32_WINNT at the first standard header, which
# hides GetTickCount64 from fb_debug.h; define it project-wide, before targets.
if(WIN32)
  add_compile_definitions(_WIN32_WINNT=0x0600)
endif()

add_library(familybox_core SHARED
  src/nes/nes.c
  src/nes/cpu.c
  src/nes/ppu.c
  src/nes/apu.c
  src/nes/bus.c
)

target_include_directories(familybox_core
  PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_compile_definitions(familybox_core
  PRIVATE
    FAMILYBOX_CORE_BUILD
)

if(FB_DEBUG)
  target_compile_definitions(familybox_core PRIVATE FB_DEBUG)
endif()

set_target_properties(familybox_core PROPERTIES
  OUTPUT_NAME "familybox_core"
  POSITION_INDEPENDENT_CODE ON
)

if(MSVC)
  target_compile_options(familybox_core PRIVATE /W3)
else()
  target_compile_options(familybox_core PRIVATE -Wall -Wextra)
endif()

if(UNIX)
  target_link_libraries(familybox_core PRIVATE m)
endif()
