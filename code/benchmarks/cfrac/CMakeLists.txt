cmake_minimum_required(VERSION 3.15.0)

set(cfrac_sources
    cfrac.c
    pops.c pconst.c pio.c
    pabs.c pneg.c pcmp.c podd.c phalf.c
    padd.c psub.c pmul.c pdivmod.c psqrt.c ppowmod.c
    atop.c ptoa.c itop.c utop.c ptou.c errorp.c
    pfloat.c pidiv.c pimod.c picmp.c
    primes.c pcfrac.c pgcd.c)

if (DEFINED bm_logfile)
    add_compile_definitions(BM_LOGFILE=${bm_logfile})
    include_directories(AFTER ${CMAKE_SOURCE_DIR}/misc)
    list(APPEND cfrac_sources ${CMAKE_SOURCE_DIR}/misc/harness.c)
endif()

add_executable(cfrac.elf ${cfrac_sources})

target_link_libraries(cfrac.elf PRIVATE m)
if (${gclib} STREQUAL bdwgc)
        include_directories(AFTER ${install_dir}/include)
	target_link_libraries(cfrac.elf PRIVATE gc)
        add_compile_definitions(BWGC BDWGC IGNOREFREE)
elseif (${gclib} STREQUAL cheribumpalloc)
    add_compile_definitions(BUMPALLOC)
    include_directories(AFTER ${CMAKE_SOURCE_DIR}/cheri_bump_alloc)
    target_link_libraries(cfrac.elf PRIVATE cheribumpalloc)
elseif (${gclib} STREQUAL static)
    target_link_libraries(cfrac.elf PRIVATE ${staticlib})
    target_link_options(cfrac.elf PRIVATE -no-pie -static)
endif()

install(TARGETS cfrac.elf
	RUNTIME DESTINATION bin)

