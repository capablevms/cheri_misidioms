#!/bin/bash

CHERI_PATH=${1:-$HOME/cheri}
cd code
$CHERI_PATH/cheribuild/output/morello-sdk/bin/clang --std=c11 --config cheribsd-morello-purecap.cfg -O3 -DCHERI_AWARE -o libbumpalloc_cheri.so -shared -fPIC ./bump_alloc_lib.c
cd -
