#!/bin/bash

# SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: MIT OR Apache-2.0

set -eu

# Copy everything under `bin/` to `$SSHHOST:capablevms/...` and run it.

SSHHOST="${SSHHOST:?SSHHOST is unset (or empty)}"
dst="capablevms/microbenchmarks"

ssh -q "$SSHHOST" mkdir -p "$dst"
scp -q -r bin/ "$SSHHOST":"$dst/"

echo "Set,Benchmark,Result"
for n in $(seq 1 50); do
    for bin in bin/*-{hybrid,purecap}; do
        name="$(basename $bin)"
        set_name="${name##*-}"
        bm_name="${name%-*}"
        user=$(ssh -q -t "$SSHHOST" "cd $dst/bin; time ./$name" | grep -P --only-matching '\b[0-9]+\.[0-9]+(?= user)')
        echo "$set_name,$bm_name,$user"
    done
done
