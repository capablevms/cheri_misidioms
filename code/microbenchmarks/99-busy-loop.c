// SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: MIT OR Apache-2.0

// This benchmark is a trivial busy-loop. The loop should be empty of
// ABI-sensitive instructions, so this should perform identically on purecap and
// hybrid targets and can act as a control.

#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

int main(void) {
    uint64_t i;
    for (i = 0; i < 4200000000; i++) {
        __asm__ volatile("");
    }
    printf("Busy-looped %" PRIu64 " times.\n", i);
}
