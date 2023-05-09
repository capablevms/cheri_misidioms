#!/bin/bash

cd code
$CC --std=c11 $CFLAGS -O3 -DCHERI_AWARE -o libbumpalloc_cheri.so -shared -fPIC ./bump_alloc_lib.c
cd -
