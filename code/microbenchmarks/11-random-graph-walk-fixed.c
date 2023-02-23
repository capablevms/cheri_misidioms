// SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: MIT OR Apache-2.0

// Attempt to stress pointer-chasing.
//
// We construct randomised graph. Each node has a set of exits, each leading to
// a different node, and a value. We keep track of the sum of node values seen
// so far, and use the sum to decide where to step next.
//
// We pick an arbitrary, fixed number of nodes. This should stress the cache
// more for purecap than for hybrid (since the structures pointers are bigger).
// However, in practice, the effect seems to be small.

#include <assert.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>

#include "cli.h"
#include "random-graph-walk.h"

int main(int argc, char const * argv[]) {
    struct Args args = process_args(argc, argv);
    // 16K nodes is roughly the point at which hybrid and purecap start to diverge.
    // That's a working set of 1MB on hybrid, or 2MB on purecap.
    struct Node * entry = generate_n(16 * 1024);
    before_test(&args);
    size_t visits = args.fast ? 42 : 420000000;
    uint64_t result = walk(entry, visits);
    after_test(&args);
    printf("Visited %zu nodes. Value: 0x%016" PRIx64 ".\n", visits, result);
}
