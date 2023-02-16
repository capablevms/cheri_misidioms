// SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: MIT OR Apache-2.0

#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

// A reasonably good, no-stack factorial, but recursing indirectly (by invoking
// a capability).

#ifdef __CHERI_PURE_CAPABILITY__
#define REG_PTR(n) "c" # n
#else
#define REG_PTR(n) "x" # n
#endif

uint64_t fact_impl(uintptr_t self, uint64_t acc, uint64_t next);
__asm__("   .type fact_impl, @function\n"
        "   .balign 16\n"
        "fact_impl:\n"
        "   cmp     x2, #1\n"
        "   b.hi    1f\n"
        "   mov     x0, x1\n"
        "   ret\n"
        "1:\n"
        "   mul     x1, x1, x2\n"
        "   sub     x2, x2, #1\n"
        "   br      " REG_PTR(0) "\n"
        // .size is required for purecap to properly set capability bounds.
        "fact_impl_end:\n"
        "   .size fact_impl, fact_impl_end - fact_impl\n");

uint64_t fact(uint64_t n) {
    return fact_impl((uintptr_t)fact_impl, 1, n);
}

int main(void) {
    uint64_t start = 4200000000;
    uint64_t result = fact(start);
    printf("(%" PRIu64 "! mod 2^64) = %" PRIu64 "\n", start, result);
}
