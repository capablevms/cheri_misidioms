## Requirements

* Python >= 3.10

Python modules:

* fabric
* GitPython
* matplotlib
* numpy

A `requirements.txt` file is provided to install the required dependencies.
This can be achieved by running:

`pip install -r ./requirements.txt`

## Running the tests

Build the image with the provided Dockerfile:

`$ docker build --tag misidioms:eval .`

Execute a new container from the fresh image:

`$ docker exec --rm -ti misidioms:eval`

Run the evaluation script:

`$ python3.10 ./get_all.py`

### Static linking

We additionally provide an option to run the benchmarks with static linking
(mainly due to observing that shared object could potentially be expensive
enough to induce a significant execution time overhead). By using the flag
`--benchs-static`, an additional benchmark evaluation will be performed using
statically linked version of the benchmarks. The argument to this flag will
determine what kind of CHERI mode the benchmarks should be run in.

An additional script, `parse_statics.py` can be used, given a `results.json`
produced by `get_all.py`, to parse some of the metrics computed by the
evaluation run, and see a general overview of dynamic versus static linkage
results. The script will only output benchmarks which have a "margin" (the
percentage difference in runtime, with dynamic considered 100%) higher than a
given threshold (by default, 7%).

Furthermore, an additional flag called `--bench-static-lto` can be used to
compile the benchmarks with link-time optimisation turned on.

## Experimental artifact

To provide a reproducible artifact of our ISMM paper [^1], we provide an
archive [^2] with a pre-built specific version of the CHERI infrastructure we
used to generate the results discussed in the paper. To reuse the provided
infrastructure, please run the script with the following minimal options:

`$ python 3.10 ./get_all.py --no-build-cheri --local-dir ./cheri_alloc_b7_l38au`

This will ensure that the prepared version of CHERI is used, instead of
re-building a new one, which might lead to different results.

Additionally, to obtain the results in the paper, we ran the benchmarks with 30
repetitions. By default, the number of repetitions in the script is 3, and can
be controlled via the flag `--benchs-rep-count`.

## Known issues

While the script has been thoroughly tested, during implementation, we
non-deterministically observed the following issues:

### Terminal output stuck

If the terminal stops producing output after an experiment (e.g., if something
is typed, it does not appear on the terminal), type `reset` and hit enter; the
terminal will reset itself.

### Script going in background

In certain executions, it might be the case that the script automatically puts
itself in the background, usually after outputting a message `Waiting for
emulator...`. To resume, run `bg` on the console.

[^1]: https://arxiv.org/abs/2303.15130

[^2]: https://archive.org/details/cheri_allocator_ismm
