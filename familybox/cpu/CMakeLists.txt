add_library(fb_cpu OBJECT cpu.c)

target_include_directories(fb_cpu
  PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/../include
)

set_target_properties(fb_cpu PROPERTIES POSITION_INDEPENDENT_CODE ON)

if(MSVC)
  target_compile_options(fb_cpu PRIVATE /W3)
else()
  target_compile_options(fb_cpu PRIVATE -Wall -Wextra)
endif()
