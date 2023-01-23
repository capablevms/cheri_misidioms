* Python >= 3.10

Python modules:
* fabric
* GitPython

## Running the tests

Build the image with the provided Dockerfile:
`$ docker build --tag misidioms:eval .`

Execute a new container from the fresh image:
`$ docker exec --rm -ti misidioms:eval`

Run the evaluation script:
`$ python3.10 get_all.py`

### Terminal output stuck

If the terminal stops producing output after an experiment (e.g., if something
is typed, it does not appear on the terminal), type `reset` and hit enter; the
terminal will reset itself.

### Script going in background

In certain executions, it might be the case that the script automatically puts
itself in the background, usually after outputting a message `Waiting for
emulator...`. To resume, run `bg` on the console.
