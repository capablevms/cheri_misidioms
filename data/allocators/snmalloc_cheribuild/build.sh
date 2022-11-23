#!/bin/bash

mkdir -p build && cd build
#CC=/home/cheriworker/cheri/output/morello-sdk/bin/clang CXX=/home/cheriworker/cheri/output/morello-sdk/bin/clang++ CFLAGS="--config cheribsd-morello-purecap.cfg" CXXFLAGS="--config cheribsd-morello-purecap.cfg" cmake -G Ninja -DCMAKE_BUILD_TYPE=Debug ..
cmake -G Ninja -DCMAKE_BUILD_TYPE=Debug ..
ninja -j5
