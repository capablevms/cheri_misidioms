#!/bin/bash

rm -rf build && mkdir build && cd build
cmake -G "Unix Makefiles" -DCMAKE_C_COMPILER=$CC -DCMAKE_C_FLAGS="$CFLAGS -O3" -DCMAKE_CXX_COMPILER=$CXX -DCMAKE_CXX_FLAGS="$CXXFLAGS -O3" -DCMAKE_BUILD_TYPE=Debug ..
make -j5
