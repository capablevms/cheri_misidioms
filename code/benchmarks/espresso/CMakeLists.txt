cmake_minimum_required(VERSION 3.15.0)

set(espresso_sources
    cofactor.c cols.c compl.c contain.c cubestr.c cvrin.c cvrm.c cvrmisc.c cvrout.c
    dominate.c equiv.c espresso.c essen.c exact.c expand.c gasp.c getopt.c gimpel.c
    globals.c hack.c indep.c irred.c main.c map.c matrix.c mincov.c opo.c pair.c part.c
    primes.c reduce.c rows.c set.c setc.c sharp.c sminterf.c solution.c sparse.c unate.c
    utility.c verify.c)

if (DEFINED bm_logfile)
    add_compile_definitions(BM_LOGFILE=${bm_logfile})
    include_directories(AFTER ${CMAKE_SOURCE_DIR}/misc)
    list(APPEND espresso_sources ${CMAKE_SOURCE_DIR}/misc/harness.c)
endif()

add_executable(espresso.elf ${espresso_sources})

target_link_libraries(espresso.elf PRIVATE m)
if (${gclib} STREQUAL bdwgc)
    include_directories(AFTER ${install_dir}/include)
    target_link_libraries(espresso.elf PRIVATE gc)
    add_compile_definitions(BDWGC IGNOREFREE)
elseif (${gclib} STREQUAL cheribumpalloc)
    add_compile_definitions(BUMPALLOC)
    include_directories(AFTER ${CMAKE_SOURCE_DIR}/cheri_bump_alloc)
    target_link_libraries(espresso.elf PRIVATE cheribumpalloc)
elseif (${gclib} STREQUAL static)
    setup_static(espresso.elf)
endif()

install(TARGETS espresso.elf
	RUNTIME DESTINATION bin)

install(FILES largest.espresso
	DESTINATION data/espresso
	PERMISSIONS OWNER_READ OWNER_WRITE)
