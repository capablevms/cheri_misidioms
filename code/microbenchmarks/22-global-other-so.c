// SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: MIT OR Apache-2.0

// Like 21-global, but access the global from a distinct, no-inline function so
// the compiler cannot hoist the access of the global's address.

#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

#include "cli.h"

extern uint64_t global_i;

uint64_t __attribute__((noinline)) inc_i(void) {
    // This access requires an extra indirection for purecap.
    return ++global_i;
}

// Prevent inlining, so we don't have to consider secondary effects (such as
// loop alignment).
void __attribute__((noinline)) loop(uint64_t count) {
    for (global_i = 0; global_i < count; global_i++) {
        __asm__ volatile("" : : : "memory");
    }
}

int main(int argc, char const * argv[]) {
    struct Args args = process_args(argc, argv);
    before_test(&args);
    loop(args.fast ? 42 : 4200000000);
    after_test(&args);
    printf("Busy-looped %" PRIu64 " times.\n", global_i);
}
