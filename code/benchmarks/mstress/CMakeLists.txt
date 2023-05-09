cmake_minimum_required(VERSION 3.15.0)

set(mstress_sources mstress.c)

if (DEFINED bm_logfile)
    add_compile_definitions(BM_LOGFILE=${bm_logfile})
    include_directories(AFTER ${CMAKE_SOURCE_DIR}/misc)
    list(APPEND mstress_sources ${CMAKE_SOURCE_DIR}/misc/harness.c)
endif()

add_executable(mstress.elf ${mstress_sources})

target_link_libraries(mstress.elf PRIVATE pthread)
if (${gclib} STREQUAL bdwgc)
    include_directories(AFTER ${install_dir}/include)
    target_link_libraries(mstress.elf PRIVATE gc)
    add_compile_definitions(BDWGC IGNOREFREE)
elseif (${gclib} STREQUAL cheribumpalloc)
    add_compile_definitions(BUMPALLOC)
    include_directories(AFTER ${CMAKE_SOURCE_DIR}/cheri_bump_alloc)
    target_link_libraries(mstress.elf PRIVATE cheribumpalloc)
elseif (${gclib} STREQUAL static)
    target_link_libraries(mstress.elf PRIVATE ${staticlib})
    target_link_options(mstress.elf PRIVATE -no-pie -static)
endif()

install(TARGETS mstress.elf
        RUNTIME DESTINATION bin)

