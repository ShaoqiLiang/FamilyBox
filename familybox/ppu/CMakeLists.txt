add_library(fb_ppu OBJECT ppu.c)

target_include_directories(fb_ppu
  PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/../include
)

set_target_properties(fb_ppu PROPERTIES POSITION_INDEPENDENT_CODE ON)

if(MSVC)
  target_compile_options(fb_ppu PRIVATE /W3)
else()
  target_compile_options(fb_ppu PRIVATE -Wall -Wextra)
endif()
