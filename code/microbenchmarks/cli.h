// SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: MIT OR Apache-2.0

#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>

#ifndef TOGGLE_MTI_IMM
// This is the default used by cheribuild.
#define TOGGLE_MTI_IMM "0xbeef"
#endif

struct Args {
    bool fvp_mti_toggle;
    bool fast;
};

void usage(char const * exe) {
    printf("Usage: %s [OPTIONS]\n", exe);
    printf("\n");
    printf("OPTIONS\n");
    printf("\n");
    printf("  --fvp-mti-toggle\n");
    printf("    Execute `hlt #%s` before and after the test, to",
           TOGGLE_MTI_IMM);
    printf("    communicate with the Morello FVP model's ToggleMTIPlugin.");
    printf("\n");
    printf("  --fast\n");
    printf("    Perform very short test runs. Useful when tracing.\n");
    printf("\n");
    printf("  --help, -h\n");
    printf("    Print this usage information.\n");
}

struct Args process_args(int argc, char const * argv[]) {
    struct Args args;
    args.fvp_mti_toggle = false;
    args.fast = false;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--fvp-mti-toggle") == 0) {
            args.fvp_mti_toggle = true;
        } else if (strcmp(argv[i], "--fast") == 0) {
            args.fast = true;
        } else if ((strcmp(argv[i], "--help") == 0) ||
                   (strcmp(argv[i], "-h") == 0)) {
            usage(argv[0]);
            exit(0);
        } else {
            fprintf(stderr, "Error: Unrecognised argument ('%s').\n", argv[i]);
            exit(1);
        }
    }

    return args;
}

void before_test(struct Args const * args) {
    if (args->fvp_mti_toggle) {
        __asm__ volatile ("hlt #" TOGGLE_MTI_IMM "\n" : : : "memory");
    }
}

void after_test(struct Args const * args) {
    if (args->fvp_mti_toggle) {
        __asm__ volatile ("hlt #" TOGGLE_MTI_IMM "\n" : : : "memory");
    }
}
