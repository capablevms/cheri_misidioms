// SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: MIT OR Apache-2.0

// This benchmark is a trivial busy-loop, except that each iteration reads,
// modifies and writes a global variable. In purecap, the compiler obtains tight
// bounds, but it hoists that out of the loop and so the overheads should be
// negligible.

#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

#include "cli.h"

uint64_t i;

// Prevent inlining, so we don't have to consider secondary effects (such as
// loop alignment).
void __attribute__((noinline)) loop(uint64_t count) {
    for (i = 0; i < count; i++) {
        __asm__ volatile("" : : : "memory");
    }
}

int main(int argc, char const * argv[]) {
    struct Args args = process_args(argc, argv);
    before_test(&args);
    loop(args.fast ? 42 : 4200000000);
    after_test(&args);
    printf("Busy-looped %" PRIu64 " times.\n", i);
}
