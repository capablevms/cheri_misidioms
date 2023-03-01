// SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: MIT OR Apache-2.0

// This benchmark is a trivial busy-loop. The loop should be empty of
// ABI-sensitive instructions, so this should perform identically on purecap and
// hybrid targets and can act as a control.

#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

#include "cli.h"

// Prevent inlining, so we don't have to consider secondary effects (such as
// loop alignment).
uint64_t __attribute__((noinline)) loop(uint64_t count) {
    uint64_t i;
    for (i = 0; i < count; i++) {
        __asm__ volatile("" : : : "memory");
    }
    return i;
}

int main(int argc, char const * argv[]) {
    struct Args args = process_args(argc, argv);
    before_test(&args);
    uint64_t count = loop(args.fast ? 42 : 4200000000);
    after_test(&args);
    printf("Busy-looped %" PRIu64 " times.\n", count);
}
