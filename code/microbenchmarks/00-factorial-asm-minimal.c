// SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: MIT OR Apache-2.0

#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

#include "cli.h"

// A reasonably good, no-stack factorial.
//
// The only difference between purecap and hybrid is that purecap will return to
// a capability (c30) each time.

uint64_t fact_impl(uint64_t acc, uint64_t next);
__asm__("   .type fact_impl, @function\n"
        "fact_impl:\n"
        "   cmp     x1, #1\n"
        "   b.hi    1f\n"
        "   ret\n"
        "1:\n"
        "   mul     x0, x0, x1\n"
        "   sub     x1, x1, #1\n"
        "   b       fact_impl\n"
        // .size is required for the FVP tracing tools to identify the symbol.
        "fact_impl_end:\n"
        "   .size fact_impl, fact_impl_end - fact_impl\n");

uint64_t fact(uint64_t n) {
    return fact_impl(1, n);
}

int main(int argc, char const * argv[]) {
    struct Args args = process_args(argc, argv);
    before_test(&args);
    uint64_t start = args.fast ? 42 : 4200000000;
    uint64_t result = fact(start);
    after_test(&args);
    printf("(%" PRIu64 "! mod 2^64) = %" PRIu64 "\n", start, result);
}
