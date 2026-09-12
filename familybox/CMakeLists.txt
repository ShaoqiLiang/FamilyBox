# FamilyBox C core — links module object libraries into one shared library.

add_subdirectory(cpu)
add_subdirectory(ppu)
add_subdirectory(apu)
add_subdirectory(bus)

add_library(familybox_core SHARED
  nes.c
)

target_include_directories(familybox_core
  PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_link_libraries(familybox_core
  PRIVATE
    fb_cpu
    fb_ppu
    fb_apu
    fb_bus
)

if(UNIX)
  target_link_libraries(familybox_core PRIVATE m)
endif()

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

# Propagate FB_DEBUG to module object libs
foreach(mod fb_cpu fb_ppu fb_apu fb_bus)
  if(FB_DEBUG)
    target_compile_definitions(${mod} PRIVATE FB_DEBUG)
  endif()
endforeach()
