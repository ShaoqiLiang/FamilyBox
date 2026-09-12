add_library(fb_bus OBJECT bus.c)

target_include_directories(fb_bus
  PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/../include
)

set_target_properties(fb_bus PROPERTIES POSITION_INDEPENDENT_CODE ON)

if(MSVC)
  target_compile_options(fb_bus PRIVATE /W3)
else()
  target_compile_options(fb_bus PRIVATE -Wall -Wextra)
endif()
