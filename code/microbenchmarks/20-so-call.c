// SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: MIT OR Apache-2.0

// Repeatedly call a no-op function in another shared object. This exercises the
// dynamic linker/loader veneers, and attempts to highlight any inherent
// performance difference. The callee does no operations (other than return),
// and does not allocate a stack frame.

#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

#include "cli.h"

extern void nop(void);

int main(int argc, char const * argv[]) {
    struct Args args = process_args(argc, argv);
    before_test(&args);
    uint64_t i;
    uint64_t count = args.fast ? 42 : 420000000;
    for (i = 0; i < count; i++) {
        nop();
    }
    after_test(&args);
    printf("Busy-looped %" PRIu64 " times.\n", i);
}
