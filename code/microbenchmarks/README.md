These benchmarks do not set out to exercise any allocators, but seek to identify
differences between purecap and hybrid performance. These benchmarks are
probably not representative of typical application code.

All benchmarks will be statically linked and self-contained, so that
varying optimisation of system libraries is ignored.

The benchmarks will be affected by the hardware itself (because purecap targets
execute more capability operations), but also the toolchain and C library
(because purecap targets require different optimisations, and are likely to be
less mature).
