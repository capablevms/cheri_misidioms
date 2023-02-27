#!/bin/bash

CHERI_PATH=${1:-$HOME/cheri}
rm -rf build && mkdir build && cd build
cmake -G "Unix Makefiles" -DCMAKE_C_COMPILER=$CHERI_PATH/output/morello-sdk/bin/clang -DCMAKE_C_FLAGS="--config cheribsd-morello-purecap.cfg" -DCMAKE_CXX_COMPILER=$CHERI_PATH/output/morello-sdk/bin/clang++ -DCMAKE_CXX_FLAGS="--config cheribsd-morello-purecap.cfg" -DCMAKE_BUILD_TYPE=Debug ..
make -j5
