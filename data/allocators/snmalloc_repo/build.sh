#!/bin/bash

rm -rf build && mkdir build && cd build
cmake -G "Unix Makefiles" -DCMAKE_C_COMPILER=/home/cheriworker/cheri/output/morello-sdk/bin/clang -DCMAKE_C_FLAGS="--config cheribsd-morello-purecap.cfg" -DCMAKE_CXX_COMPILER=/home/cheriworker/cheri/output/morello-sdk/bin/clang++ -DCMAKE_CXX_FLAGS="--config cheribsd-morello-purecap.cfg" -DCMAKE_BUILD_TYPE=Debug ..
make -j5
