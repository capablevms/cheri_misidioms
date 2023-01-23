#!/bin/bash

CHERI_PATH=${1:-$HOME/cheri}
cd listings
$CHERI_PATH/cheribuild/output/morello-sdk/bin/clang --config cheribsd-morello-purecap.cfg -o libbumpalloc.so -shared -fPIC ./bump_alloc1.c
cd -
