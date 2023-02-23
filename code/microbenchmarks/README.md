These benchmarks do not set out to exercise any allocators, but seek to identify
differences between purecap and hybrid performance. These benchmarks are
probably not representative of typical application code.

All benchmarks will be statically linked and self-contained, so that
varying optimisation of system libraries is ignored.

The benchmarks will be affected by the hardware itself (because purecap targets
execute more capability operations), but also the toolchain and C library
(because purecap targets require different optimisations, and are likely to be
less mature).

# FVP Trace

If you run FVP with the ToggleMTITrace plugin enabled, these benchmarks can
toggle tracing before and after each run. The easiest way to arrange this with
CheriBSD is to start the model as follows:

```
% ./cheribuild.py run-fvp-morello-purecap --run-fvp/trace=/tmp/fvp-trace --run-fvp/unbuffered
...
```

At the time of writing, `--run-fvp/unbuffered` requires [PR 351][].

Then, run each benchmark with the `--fvp-mti-toggle` option. The `--fast` option
is also recommended here, since full runs are probably not required for
analysis, and may generate a lot of trace data.

```
% ./00-factorial-asm-minimal-purecap --fast --fvp-mti-toggle
(42! mod 2^64) = 7538058755741581312
```

Each run will append to the specified file (e.g. `/tmp/fvp-trace`). However,
note that the model keeps its file handle open (or at least behaves as if that's
what it is doing). Notably, it's not possible to clear unrelated traces by
simply truncating or removing the file, so analysis alongside a running model
will require careful tracking of the file size before and after each test.

For example, for the example above:

```
0 clk cluster1.cpu1 R cpsr 04000200
1 clk cluster1.cpu1 IT (11100998643) (1|b05dc00022e70004|0011118c):0000fcd2918c_NS 7100011f C EL0t_n : CMP      w8,#0
1 clk cluster1.cpu1 R cpsr 24000200
2 clk cluster1.cpu1 IT (11100998644) (1|b05dc00022e70004|00111190):0000fcd29190_NS 52800548 C EL0t_n : MOV      w8,#0x2a
2 clk cluster1.cpu1 R X8 000000000000002A
3 clk cluster1.cpu1 IT (11100998645) (1|b05dc00022e70004|00111194):0000fcd29194_NS 9a880273 C EL0t_n : CSEL     x19,x19,x8,EQ
3 clk cluster1.cpu1 R X19 000000000000002A
4 clk cluster1.cpu1 IT (11100998646) (1|b05dc00022e70004|00111198):0000fcd29198_NS 52800020 C EL0t_n : MOV      w0,#1
4 clk cluster1.cpu1 R X0 0000000000000001
...
```

The format of the tarmac trace is described in the [Fast Models Reference][].


[Fast Models Reference]: https://developer.arm.com/documentation/100964/1120/Plug-ins-for-Fast-Models/TarmacTrace/Instruction-trace
[PR 351]: https://github.com/CTSRD-CHERI/cheribuild/pull/351
