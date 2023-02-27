#!/bin/bash
set -xe

for x in *.c
do
	~/cheri/output/morello-sdk/bin/clang --std=c11 -Wall --config cheribsd-morello-purecap.cfg -Wextra -Wno-unused-parameter -L. -o $(basename -s '.c' $x) ./$x -lxalloc
done
