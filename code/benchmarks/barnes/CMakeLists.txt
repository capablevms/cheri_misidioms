cmake_minimum_required(VERSION 3.15.0)

set(barnes_sources
    code.c code_io.c load.c grav.c getparam.c util.c)

if (DEFINED bm_logfile)
    add_compile_definitions(BM_LOGFILE=${bm_logfile})
    include_directories(AFTER ${CMAKE_SOURCE_DIR}/misc)
    list(APPEND barnes_sources ${CMAKE_SOURCE_DIR}/misc/harness.c)
endif()

add_executable(barnes.elf ${barnes_sources})

target_link_libraries(barnes.elf PRIVATE m)
if (${gclib} STREQUAL bdwgc)
    add_compile_definitions(BDWGC)
    include_directories(AFTER ${install_dir}/include)
    target_link_libraries(barnes.elf PRIVATE gc)
elseif (${gclib} STREQUAL cheribumpalloc)
    add_compile_definitions(BUMPALLOC)
    include_directories(AFTER ${CMAKE_SOURCE_DIR}/cheri_bump_alloc)
    target_link_libraries(barnes.elf PRIVATE cheribumpalloc)
elseif (${gclib} STREQUAL static)
    setup_static(barnes.elf)
endif()

install(TARGETS barnes.elf
    RUNTIME DESTINATION bin)

install(FILES input
    DESTINATION conf/barnes
    PERMISSIONS OWNER_READ OWNER_WRITE)
