// SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: MIT OR Apache-2.0

// Attempt to stress pointer-chasing.
//
// We construct randomised graph. Each node has a set of exits, each leading to
// a different node, and a value. We keep track of the sum of node values seen
// so far, and use the sum to decide where to step next.
//
// The size of the grid is chosen so as to fit into L1 cache. This means that
// hybrid and purecap workloads have DIFFERENT WORKING SETS, but that they are
// performing similar operations within them. We hope that this would allow
// examination of pointer-chasing performance without having to worry too much
// about cache misses.
//
// Morello has a 64KB L1 data cache for each core:
//    https://developer.arm.com/documentation/102278/latest

#include <assert.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>

#include "cli.h"
#include "random-graph-walk.h"

int main(int argc, char const * argv[]) {
    struct Args args = process_args(argc, argv);
    struct Node * entry = generate_with_max_size(64 * 1024);
    before_test(&args);
    size_t visits = args.fast ? 42 : 420000000;
    uint64_t result = walk(entry, visits);
    after_test(&args);
    printf("Visited %zu nodes. Value: 0x%016" PRIx64 ".\n", visits, result);
}
