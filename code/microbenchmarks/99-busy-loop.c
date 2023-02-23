// SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: MIT OR Apache-2.0

// This benchmark is a trivial busy-loop. The loop should be empty of
// ABI-sensitive instructions, so this should perform identically on purecap and
// hybrid targets and can act as a control.

#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

#include "cli.h"

int main(int argc, char const * argv[]) {
    struct Args args = process_args(argc, argv);
    before_test(&args);
    uint64_t i;
    uint64_t count = args.fast ? 42 : 4200000000;
    for (i = 0; i < count; i++) {
        __asm__ volatile("");
    }
    after_test(&args);
    printf("Busy-looped %" PRIu64 " times.\n", i);
}
