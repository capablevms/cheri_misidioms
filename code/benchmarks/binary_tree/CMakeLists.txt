cmake_minimum_required(VERSION 3.15.0)

set(binary_tree_sources binary_tree.c)

if (DEFINED bm_logfile)
    add_compile_definitions(BM_LOGFILE=${bm_logfile})
    include_directories(AFTER ${CMAKE_SOURCE_DIR}/misc)
    list(APPEND binary_tree_sources ${CMAKE_SOURCE_DIR}/misc/harness.c)
endif()

add_executable(binary_tree.elf ${binary_tree_sources})

target_link_libraries(binary_tree.elf PRIVATE m)
if (${gclib} STREQUAL bdwgc)
	add_compile_definitions(BDWGC IGNOREFREE)
    include_directories(AFTER ${install_dir}/include)
    target_link_libraries(binary_tree.elf PRIVATE gc)
elseif (${gclib} STREQUAL cheribumpalloc)
    add_compile_definitions(BUMPALLOC)
    include_directories(AFTER ${CMAKE_SOURCE_DIR}/cheri_bump_alloc)
    target_link_libraries(binary_tree.elf PRIVATE cheribumpalloc)
elseif (${gclib} STREQUAL static)
    target_link_libraries(binary_tree.elf PRIVATE ${staticlib})
    target_link_options(binary_tree.elf PRIVATE -no-pie -static)
endif()

install(TARGETS binary_tree.elf 
	RUNTIME DESTINATION bin)
