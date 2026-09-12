add_library(fb_apu OBJECT apu.c)

target_include_directories(fb_apu
  PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/../include
)

set_target_properties(fb_apu PROPERTIES POSITION_INDEPENDENT_CODE ON)

if(MSVC)
  target_compile_options(fb_apu PRIVATE /W3)
else()
  target_compile_options(fb_apu PRIVATE -Wall -Wextra)
endif()
