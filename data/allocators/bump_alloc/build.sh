#!/bin/bash

cd listings
/home/cheriworker/cheri/output/morello-sdk/bin/clang --config cheribsd-morello-purecap.cfg -o libbumpalloc.so -shared -fPIC ./bump_alloc1.c
cd -
