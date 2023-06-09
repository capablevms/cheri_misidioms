cmake_minimum_required(VERSION 3.15.0)

set(richards_sources richards.c)

if (DEFINED bm_logfile)
    add_compile_definitions(BM_LOGFILE=${bm_logfile})
    include_directories(AFTER ${CMAKE_SOURCE_DIR}/misc)
    list(APPEND richards_sources ${CMAKE_SOURCE_DIR}/misc/harness.c)
endif()

add_executable(richards.elf ${richards_sources})

if (${gclib} STREQUAL bdwgc)
    add_compile_definitions(BDWGC)
    include_directories(AFTER ${install_dir}/include)
    target_link_libraries(richards.elf PRIVATE gc)
elseif (${gclib} STREQUAL cheribumpalloc)
    add_compile_definitions(BUMPALLOC)
    include_directories(AFTER ${CMAKE_SOURCE_DIR}/cheri_bump_alloc)
    target_link_libraries(richards.elf PRIVATE cheribumpalloc)
elseif (${gclib} STREQUAL static)
    setup_static(richards.elf)
endif()

install(TARGETS richards.elf
	RUNTIME DESTINATION bin)
