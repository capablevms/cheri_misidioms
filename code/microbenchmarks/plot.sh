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
    # Add temporary sort keys to match the order in the text.
    sed -e 's/^Set,Benchmark,Result$/00-&/' |
    sed -e 's/\(hybrid\|purecap\),[0-9][0-9]-random-graph-walk-l1/10-&/' |
    sed -e 's/\(hybrid\|purecap\),[0-9][0-9]-random-graph-walk-fixed/11-&/' |
    sed -e 's/\(hybrid\|purecap\),[0-9][0-9]-ptr-add-asm/12-&/' |
    sed -e 's/\(hybrid\|purecap\),[0-9][0-9]-busy-loop/13-&/' |
    sed -e 's/\(hybrid\|purecap\),[0-9][0-9]-factorial-asm-minimal/20-&/' |
    sed -e 's/\(hybrid\|purecap\),[0-9][0-9]-factorial-asm-indirect/21-&/' |
    sed -e 's/\(hybrid\|purecap\),[0-9][0-9]-so-call/22-&/' |
    sed -e 's/\(hybrid\|purecap\),[0-9][0-9]-ptr-add-align/23-&/' |
    sort --stable --field-separator=- --key 1,1 |
    # Drop number prefixes, to save space (and match the text).
    # This also removes the temporary sort keys.
    sed -e 's/\<[0-9][0-9]-//g' |
    # l1 -> L1, to match the text.
    sed -e 's/-l1\>/-L1/' |
    "$BMPLOTTER" --width=0.5 --height=0.7 --no-legend-title --legend-position=top --colours=759DA0,E1A765,8A67BA,E06A4A --out="$out" --overplot=jitter
