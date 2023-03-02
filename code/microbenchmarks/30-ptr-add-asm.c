// SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: MIT OR Apache-2.0

#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

#include "cli.h"

// Pointer arithmetic (addition), using assembly to avoid C compiler
// differences.

#ifdef __CHERI_PURE_CAPABILITY__
#define REG_PTR(n) "%w[" #n "]"
#else
#define REG_PTR(n) "%[" #n "]"
#endif

// Prevent inlining, so we don't have to consider secondary effects (such as
// loop alignment).
void * __attribute__((noinline)) loop(void * ptr, uint64_t count) {
    for (uint64_t i = 0; i < count; i++) {
        __asm__ (
            "   add    " REG_PTR(ptr) ", " REG_PTR(ptr) ", %[delta]\n"
            : [ptr]"+&r"(ptr)
            : [delta]"r"((uint64_t)((i % 2) ? -1 : 1)));
    }
    return ptr;
}

int main(int argc, char const * argv[]) {
    struct Args args = process_args(argc, argv);
    before_test(&args);
    uint64_t count = args.fast ? 42 : 4200000000;
    void * result = loop(malloc(1024), count);
    after_test(&args);
    printf("Result: %#p\n", result);
}
