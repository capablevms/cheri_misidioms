#!/bin/bash

# SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: MIT OR Apache-2.0

# The path to 'plot', from: https://gitlab.arm.com/application/bm-plotter/
BMPLOTTER="${BMPLOTTER:?BMPLOTTER is unset (or empty)}"

# Dejice's colour palette:
#   759DA0,F8E5B8,8A67BA,E1A765,B1ED95,E06A4A
#
# Some look too pale here, so I've picked the best examples, and changed the
# order to avoid similar adjacent colours.

out="$(dirname "${BASH_SOURCE[0]}")"/../../fig/microbenchmarks.pdf

# Skip 21-global and 22-global-other-so; they don't measure anything new and the
# names promise more than they actually offer.
grep -v '\<2.-global' results.csv |
    "$BMPLOTTER" --width=0.5 --colours=759DA0,E1A765,8A67BA,E06A4A --out="$out" --overplot=jitter

# TODO: The chart is too wide!
