// SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: MIT OR Apache-2.0

#include <string.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdbool.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/user.h>
#include <libutil.h>

#ifndef TOGGLE_MTI_IMM
// This is the default used by cheribuild.
#define TOGGLE_MTI_IMM "0xbeef"
#endif

struct Args {
    bool fvp_mti_toggle;
    bool dump_map;
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
    printf("  --dump-map\n");
    printf("    Dump the virtual memory map (like `procstat vm`).\n");
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
    args.dump_map = false;
    args.fast = false;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--fvp-mti-toggle") == 0) {
            args.fvp_mti_toggle = true;
        } else if (strcmp(argv[i], "--dump-map") == 0) {
            args.dump_map = true;
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
        printf("Turning trace on. Avoid interrupting the process.\n");
        fflush(stdout);
        __asm__ volatile ("hlt #" TOGGLE_MTI_IMM "\n" : : : "memory");
    }
}

void after_test(struct Args const * args) {
    if (args->fvp_mti_toggle) {
        __asm__ volatile ("hlt #" TOGGLE_MTI_IMM "\n" : : : "memory");
        printf("Turned trace off.\n");
    }

    if (args->dump_map) {
        pid_t pid = getpid();
        int count;
        struct kinfo_vmentry * vm = kinfo_getvmmap(pid, &count);
        printf("---- BEGIN VM MAP ----\n");
        printf("Start,End,Permissions,Type,Offset,Path\n");
        for (int i = 0; i < count; i++) {
            char const * type = "UNKNOWN";
            switch (vm[i].kve_type) {
                case KVME_TYPE_NONE: type = "none"; break;
                case KVME_TYPE_DEFAULT: type = "default"; break;
                case KVME_TYPE_VNODE: type = "vnode"; break;
                case KVME_TYPE_SWAP: type = "swap"; break;
                case KVME_TYPE_DEVICE: type = "device"; break;
                case KVME_TYPE_PHYS: type = "phys"; break;
                case KVME_TYPE_DEAD: type = "dead"; break;
                case KVME_TYPE_SG: type = "sg"; break;
                case KVME_TYPE_MGTDEVICE: type = "mgtdevice"; break;
                case KVME_TYPE_GUARD: type = "guard"; break;
            }
            printf("0x%" PRIx64 ",0x%" PRIx64 ",%c%c%c%c%c,%s,0x%" PRIx64 ",%s\n",
                   vm[i].kve_start,
                   vm[i].kve_end,
                   (vm[i].kve_protection & KVME_PROT_READ) ? 'r' : '-',
                   (vm[i].kve_protection & KVME_PROT_WRITE) ? 'w' : '-',
                   (vm[i].kve_protection & KVME_PROT_EXEC) ? 'x' : '-',
                   (vm[i].kve_protection & KVME_PROT_READ_CAP) ? 'R' : '-',
                   (vm[i].kve_protection & KVME_PROT_WRITE_CAP) ? 'W' : '-',
                   type,
                   vm[i].kve_offset,
                   vm[i].kve_path);
        }
        printf("---- END VM MAP ----\n");
        free(vm);
    }
}
