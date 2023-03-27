#!/bin/bash

cat ../cheri_misidioms_preamble.ltx | sed -e 'r /dev/stdin' -e '1,2d' ../cheri_misidioms.ltx > ./cheri_misidioms.ltx
rm -rf arxiv.tar.gz
tar -cvhf arxiv.tar.gz -X prep_tar.sh *
