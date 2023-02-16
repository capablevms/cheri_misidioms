#!/bin/bash

# SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: MIT OR Apache-2.0

set -eu

# Copy everything under `bin/` to `$SSHHOST:capablevms/...` and run it.

SSHHOST="${SSHHOST:?SSHHOST is unset (or empty)}"
dst="capablevms/microbenchmarks"

ssh "$SSHHOST" mkdir -p "$dst"
scp -r bin/ "$SSHHOST":"$dst/"

for bin in bin/*; do
    echo "Running $bin..."
    ssh -t "$SSHHOST" time "$dst/$bin"
done
