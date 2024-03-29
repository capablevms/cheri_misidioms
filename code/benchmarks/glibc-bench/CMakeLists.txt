cmake_minimum_required(VERSION 3.15.0)

set(glibc_simple_sources bench-malloc-simple.c)
set(glibc_thread_sources bench-malloc-thread.c)

if (DEFINED bm_logfile)
    add_compile_definitions(BM_LOGFILE=${bm_logfile})
    include_directories(AFTER ${CMAKE_SOURCE_DIR}/misc)
    list(APPEND glibc_simple_sources ${CMAKE_SOURCE_DIR}/misc/harness.c)
    list(APPEND glibc_thread_sources ${CMAKE_SOURCE_DIR}/misc/harness.c)
endif()

add_executable(glibc_bench_simple.elf ${glibc_simple_sources})
add_executable(glibc_bench_thread.elf ${glibc_thread_sources})

target_link_libraries(glibc_bench_simple.elf PRIVATE pthread)
target_link_libraries(glibc_bench_thread.elf PRIVATE pthread m)
if (${gclib} STREQUAL bdwgc)
    include_directories(AFTER ${install_dir}/include)
    target_link_libraries(glibc_bench_simple.elf PRIVATE gc)
    target_link_libraries(glibc_bench_thread.elf PRIVATE gc)
    add_compile_definitions(BDWGC IGNOREFREE)
elseif (${gclib} STREQUAL cheribumpalloc)
    add_compile_definitions(BUMPALLOC)
    include_directories(AFTER ${CMAKE_SOURCE_DIR}/cheri_bump_alloc)
    target_link_libraries(glibc_bench_simple.elf PRIVATE cheribumpalloc)
    target_link_libraries(glibc_bench_thread.elf PRIVATE cheribumpalloc)
elseif (${gclib} STREQUAL static)
    setup_static(glibc_bench_simple.elf)
    setup_static(glibc_bench_thread.elf)
endif()

install(TARGETS glibc_bench_simple.elf  glibc_bench_thread.elf
	RUNTIME DESTINATION bin)
