#!/bin/bash

# SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: MIT OR Apache-2.0

set -eu

# Copy everything under `bin/` to an FVP model with the ToggleMTETrace plugin
# enabled, run each test with --fvp-mti-toggle, and sort traces into separate
# files. Precise results will require that the model is run with
# `TRACE.TarmacTrace.unbuffered=true`.
#
# The easiest way to set up a model is to launch it as follows:
#
#   ./cheribuild.py run-fvp-morello-purecap --run-fvp/trace=FVPTRACE \
#       --run-fvp/trace-unbuffered
#
# At the time of writing, `--run-fvp/unbuffered` requires PR 351:
#   https://github.com/CTSRD-CHERI/cheribuild/pull/351

FVPTRACE="${FVPTRACE:?FVPTRACE is unset (or empty)}"
SSHHOST="${SSHHOST:?SSHHOST is unset (or empty)}"
dst="capablevms/microbenchmarks"

ssh "$SSHHOST" mkdir -p "$dst"
scp -r bin/ "$SSHHOST":"$dst/"

mkdir -p trace

for bin in bin/*; do
    tracefile="trace/${bin#bin/}"
    echo "Tracing $bin -> $tracefile..."
    before=$(stat -c '%s' "$FVPTRACE")
    ssh -t "$SSHHOST" "$dst/$bin" --fast --dump-map --fvp-mti-toggle
    after=$(stat -c '%s' "$FVPTRACE")
    echo "  Reading $(( after - before )) bytes from $FVPTRACE [$before,$after)..."
    dd bs=1 if="$FVPTRACE" skip="$before" of="$tracefile" status=none
done
