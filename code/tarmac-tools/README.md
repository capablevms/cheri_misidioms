# Tarmac (FVP trace) tools

Use these to analyse tarmac traces produced by some benchmarks in this
repository.

For example

```
% cd microbenchmarks
% ./build.sh
% SSHHOST=fvp-morello-purecap FVPTRACE=/tmp/fvp-trace ./run-fast-fvp-trace.sh
...
% cd ../tarmac-tools
% cargo run -- ../microbenchmarks/trace/11-random-graph-walk-fixed-purecap.{tarmac,stdout}
...
/root/capablevms/microbenchmarks/bin/11-random-graph-walk-fixed-purecap: 488 instructions
Counted 488 EL0 instructions in total.
```
