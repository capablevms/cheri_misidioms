#!/bin/bash

cd code
$CC --std=c11 $CFLAGS -O3 -o libbumpalloc_nocheri.so -shared -fPIC ./bump_alloc_lib.c
cd -
