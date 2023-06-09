cmake_minimum_required(VERSION 3.15.0)
project(cheri-bdwgc
        VERSION 0.1
        DESCRIPTION "mimalloc benchmarks"
        LANGUAGES CXX C)
set(CMAKE_CXX_STANDARD 14)

function(setup_static target)
    target_link_libraries(${target} PRIVATE ${staticlib})
    target_link_options(${target} PRIVATE -no-pie -static)
    if (DEFINED static_flags)
        target_link_options(${target} PRIVATE ${static_flags})
    endif()
    if (DEFINED static_lto)
        set_property(TARGET ${target} PROPERTY INTERPROCEDURAL_OPTIMIZATION TRUE)
    endif()
endfunction()

if (NOT CMAKE_BUILD_TYPE)
        message(STATUS "No build type selected, default to *** Release with Debug Info ***")
        set(CMAKE_BUILD_TYPE "Debug")
endif()

# Default to bdwgc - for testing purposes
#if (NOT gclib)
#    set(gclib bdwgc)
#endif()

if (${gclib} STREQUAL bdwgc)
    set(bdwgc_cmake_args
        -DCMAKE_INSTALL_PREFIX=${CMAKE_CURRENT_BINARY_DIR}/bdwgc
        -Denable_gcj_support=OFF
        -Denable_parallel_mark=OFF
        -Denable_threads=OFF
        -Denable_dynamic_loading=OFF
        -DCMAKE_BUILD_TYPE=${CMAKE_BUILD_TYPE})
    set(bdwgc_build_prefix ${CMAKE_CURRENT_BINARY_DIR}/bdwgc)

    if (DEFINED CMAKE_TOOLCHAIN_FILE)
        message("-- Use toolchain: " ${CMAKE_TOOLCHAIN_FILE})
        list(APPEND bdwgc_cmake_args -DCMAKE_TOOLCHAIN_FILE=${CMAKE_TOOLCHAIN_FILE})
    else()
        message("Information:  Using HOST toolchain")
    endif()

    if (DEFINED BUILD_SHARED_LIBS)
        list(APPEND bdwgc_cmake_args -DBUILD_SHARED_LIBS=${BUILD_SHARED_LIBS})
    endif()

    # Cannot use Ninja with this due to strict external library checking
    # Will work with Unix Make
    include(ExternalProject)
    ExternalProject_Add(project_bdwgc
            GIT_REPOSITORY https://github.com/djichthys/bdwgc.git
            GIT_TAG dj/perf
            CMAKE_ARGS ${bdwgc_cmake_args}
            PREFIX ${bdwgc_build_prefix})

    ExternalProject_Get_property(project_bdwgc install_dir)
    ExternalProject_Get_property(project_bdwgc source_dir)

    if (BUILD_SHARED_LIBS STREQUAL "OFF")
      add_library(gc STATIC IMPORTED)
      set_target_properties(gc PROPERTIES IMPORTED_LOCATION ${install_dir}/lib/libgc.a)
      add_dependencies(gc project_bdwgc)

      add_library(cord STATIC IMPORTED)
      set_target_properties(cord PROPERTIES IMPORTED_LOCATION ${install_dir}/lib/libcord.a)
      add_dependencies(cord project_bdwgc)

      # These libraries are built using ExternalPorject. install(TARGETS) does not work
      #file(GLOB gclibraries FOLLOW_SYMLINKS ${bdwgc_build_prefix}/lib/lib*)
      set(gclibraries libgc.a libcord.a)
    else()
      add_library(gc SHARED IMPORTED)
      set_target_properties(gc PROPERTIES IMPORTED_LOCATION ${install_dir}/lib/libgc.so)
      add_dependencies(gc project_bdwgc)

      add_library(cord SHARED IMPORTED)
      set_target_properties(cord PROPERTIES IMPORTED_LOCATION ${install_dir}/lib/libcord.so)
      add_dependencies(cord project_bdwgc)

      # These libraries are built using ExternalPorject. install(TARGETS) does not work
      #file(GLOB gclibraries FOLLOW_SYMLINKS ${bdwgc_build_prefix}/lib/lib*)
      set(gclibraries
              libgc.so.1.5.1 libgc.so.1 libgc.so
              libcord.so.1.5.0 libcord.so.1 libcord.so)
    endif()

    list(TRANSFORM gclibraries PREPEND ${bdwgc_build_prefix}/lib/)
    install(FILES
        ${gclibraries}
        DESTINATION lib
        PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE)
elseif (${gclib} STREQUAL cheribumpalloc)
    add_subdirectory(cheri_bump_alloc)
elseif (${gclib} STREQUAL static)
    if(NOT DEFINED staticlib)
        message(FATAL_ERROR "Not given a static library path!")
    elseif(NOT EXISTS ${staticlib})
        message(FATAL_ERROR "Static path ${staticlib} does not exist!")
    endif()
elseif (NOT ${gclib} STREQUAL jemalloc)
    message(FATAL_ERROR "Unrecognized lib type ${gclib}!")
endif()

# Each individual test has own subdir
add_subdirectory(barnes)
add_subdirectory(binary_tree)
add_subdirectory(cfrac)
add_subdirectory(espresso)
add_subdirectory(richards)
# add_subdirectory(simple_alloc)
if ( NOT ${gclib} STREQUAL bdwgc)
    add_subdirectory(glibc-bench)
    add_subdirectory(mstress)
    # add_subdirectory(rptest)
    # add_subdirectory(xmalloc)
endif()

# Check out this
# [link](https://www.jwlawson.co.uk/interest/2020/02/23/cmake-external-project.html)
# for embedding the external libgc and installation
