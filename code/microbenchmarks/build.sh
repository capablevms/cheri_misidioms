#!/bin/bash

# SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: MIT OR Apache-2.0

set -eu

CHERIBASE="$HOME/cheri"
SDKBASE="$CHERIBASE/output/morello-sdk"
CFLAGS_PURECAP="--config cheribsd-morello-purecap.cfg -O3"
CFLAGS_HYBRID="--config cheribsd-morello-hybrid.cfg -O3"

mkdir -p bin
mkdir -p obj
mkdir -p disasm

function build_with_clang {
    CFG=$1
    CLANG="$SDKBASE/bin/clang --config cheribsd-morello-$CFG.cfg -O3"
    OBJDUMP="$SDKBASE/bin/objdump -d --mcpu=rainier"
    LIBS=("-lutil")  # CheriBSD's libutil, used for `--dump-map`.
    for lib in lib/*.c; do
        libname=${lib#lib/}
        libname=${libname%%.c}-$CFG
        LIBS+=("-l$libname")
        name="lib$libname.so"
        echo "Building $name..."
        $CLANG -O3 -std=c99 -Wall -Wextra -pedantic -shared -fPIC $lib -o bin/$name
        $OBJDUMP bin/$name > disasm/$name.disasm
    done
    for src in *.c; do
        name=${src%%.c}-$CFG
        echo "Building $name..."
        $CLANG -O3 -std=c99 -Wall -Wextra -pedantic $src -c -o obj/$name.o
        $CLANG -O3 -std=c99 -Wall -Wextra -pedantic -Wl,-rpath,. -Lbin ${LIBS[@]} obj/$name.o -o bin/$name
        $OBJDUMP obj/$name.o > disasm/$name.disasm
    done
}

build_with_clang purecap
build_with_clang hybrid
