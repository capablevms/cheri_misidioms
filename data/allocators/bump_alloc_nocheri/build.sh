#!/bin/bash

CHERI_PATH=${1:-$HOME/cheri}
cd code
$CHERI_PATH/cheribuild/output/morello-sdk/bin/clang --config cheribsd-morello-purecap.cfg -O3 -o libbumpalloc_nocheri.so -shared -fPIC ./bump_alloc_lib.c
cd -
