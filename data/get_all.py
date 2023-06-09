#!/usr/bin/env python3

import argparse
import datetime
import enum
import glob
import json
import os
import operator
import pprint
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

from operator import itemgetter

# External dependencies
import git
import numpy as np

from fabric import Connection

# Local dependencies
import graphplot

################################################################################
# Constants
################################################################################

cheri_lines_pattern = "Total CHERI lines: (\d+)"

cheri_fn_pattern = "cheri_[a-zA-Z0-9_]+"
cheri_fn_grep_pattern = "\\bcheri_[[:alnum:]_]\+("

cheri_builtin_fn_pattern = "__builtin_cheri[a-zA-Z0-9_]+"
cheri_builtin_fn_grep_pattern = "BUILTIN(__builtin_cheri[[:alnum:]_]\+"
cheri_builtin_fn_call_grep_pattern = "__builtin_cheri[[:alnum:]_]\+"

execution_targets = {"attacks" : None, "benchmarks" : None}

pmc_events_names = [ 'L1D_CACHE', 'L1I_CACHE', 'L2D_CACHE', 'CPU_CYCLES',
                     'INST_RETIRED', 'MEM_ACCESS', 'BUS_ACCESS',
                     'BUS_ACCESS_RD_CTAG' ]

default_mode = "purecap"
benchmark_modes = {
        "purecap": {
            "environ" : "LD_PRELOAD",
            "cflags" : "--config cheribsd-morello-purecap",
            "pkg_manager": "pkg64c",
            },
        "hybrid":  {
            "environ" : "LD_64_PRELOAD",
            "cflags" : "--config cheribsd-morello-hybrid",
            "pkg_manager": "pkg64",
            },
        }

benchmarks_graph_folder = "benchs_graphs"

################################################################################
# Arguments
################################################################################

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument("--alloc", type=str, action='store', required=False,
        help="""Optional path to allocator folder, containing `info.json`. If
        not given, runs over all allocators given in `config.json`.""")
arg_parser.add_argument("--local-dir", type=str, action='store', default=None,
        required=False, metavar="path",
        help="Where to store local data, instead of generating a folder.")
arg_parser.add_argument("--log-file", type=str, action='store',
        default='cheri_alloc.log', metavar="path",
        help="File to store log data to")
arg_parser.add_argument("--no-build-cheri", action="store_true",
        help="""Whether to build CheriBSD and the QEMU image from scratch. Only
        set if `local-dir` is set with a pre-existing build within.""")
arg_parser.add_argument("--no-wait-qemu", action="store_true",
        help="If set, assumes the QEMU instance is running, and skip waiting.")
arg_parser.add_argument("--parse-data-only", action='store', default="",
        type=str, metavar="path",
        help="Parse given results file to generate LaTeX tables.")
arg_parser.add_argument("--bench-machine", action='store', default="",
        type=str, metavar="address",
        help="""Similar to `target-machine`, but to be used to run only the
        benchmarks on, not the attacks.""")
arg_parser.add_argument("--table-context", action='store_true',
        help="""If set, will emit Latex tables with prologue and epilogue.
        Otherwise, simply generates the table content""")
arg_parser.add_argument("--slocs-table-template", action='store', type=str,
        help="""Path to a file containing a simple template to order allocators
        in the SLoCs table as desired, `---` indicates a separator line.""")
arg_parser.add_argument("--benchs-rep-count", action='store', type=int,
        default = 3,
        help="""Number of repetitions for benchmarks""")
arg_parser.add_argument("--benchs-static", action='store',
        choices=["all", "purecap", "hybrid"], default=None,
        help="""If set, will also execute benchmarks against a statically
        linked version of an allocator.""")
arg_parser.add_argument("--benchs-static-lto", action='store_true',
        help="""If set, will compile benchmarks with LTO (link-time
        optimisation) enabled.""")
for targets in execution_targets:
    arg_parser.add_argument(f"--{targets}-machine", action='store', default="",
            type=str, metavar="address",
            help=f"""Address (`user@host:port`) of a CHERI-enabled machine to run
            {targets} on. If none given, uses a QEMU instance.""")
    arg_parser.add_argument(f"--no-run-{targets}", action='store_true',
            help = f"If set, will skip running {targets} for the execution.")
args = arg_parser.parse_args()

################################################################################
# Helper Functions
################################################################################

def make_cheribuild_cmd(target, source, flags = ""):
    cmd = shlex.split(f'./cheribuild.py -d -f --skip-update --source-root {source} {flags} {target}')
    print(cmd)
    return cmd

def make_grep_pattern_cmd(pattern, target):
    return shlex.split(f"grep -oIrhe '{pattern}' {target}")

def make_cloc_cmd(path):
    return shlex.split(f"cloc --json {path}")

def get_config(to_get, machine = None):
    gotten = config[to_get]
    if isinstance(gotten, str):
        return parse_path(gotten, machine)
    else:
        return gotten

def parse_path(to_parse, machine = None):
    parses = {
            "HOME"  : 'os.getenv("HOME")',
            "WORK"  : 'work_dir_local',
            "CWD"   : 'base_cwd',
            "RHOME" : 'machine.rhome',
            }
    for holder in parses.keys():
        if to_parse.startswith(f"${holder}"):
            to_parse = to_parse.replace(f"${holder}", eval(parses[holder]))
            break
    assert('$' not in to_parse)
    return to_parse

#TODO check intersection
def read_apis(apis_path):
    api_fns = {}
    with open(f"{apis_path}", 'r') as api_info_json:
        api_info = json.load(api_info_json)
        for api in api_info:
            api_fns[api] = set()
            if api == "builtin":
                pattern = cheri_builtin_fn_grep_pattern
            else:
                pattern = cheri_fn_grep_pattern
            for api_file in api_info[api]['path']:
                api_file = parse_path(api_file)
                if not os.path.exists(api_file):
                    print(f"Could not find file {api_file}; exiting...")
                    sys.exit(1)
                log_message(f"Checking API file {api_file} for API {api}.")
                fns = subprocess.check_output(make_grep_pattern_cmd(pattern, api_file), encoding = "UTF-8")
                fns = fns.strip().split(os.linesep)
                if api == "builtin":
                    fns = [x.removeprefix("BUILTIN(") for x in fns]
                else:
                    fns = [x.removesuffix("(") for x in fns]
                api_fns[api].update(fns)
    return api_fns

def get_timestamp():
    return datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")

def log_message(msg):
    print(msg)
    log_fd.write(msg + '\n')

def prep_data(results, event, empty = False, func = None):
    results[f"raw-{event}"] = results[event]
    if not empty:
        results[event] = func(results[event])
    else:
        results[event] = 0.0
    return results

################################################################################
# Objects
################################################################################

class InstallMode(enum.Enum):
    REPO = enum.auto()
    PKG = enum.auto()
    CHERIBUILD = enum.auto()

    def parse_version(self, install_data):
        if self == InstallMode.PKG:
            return install_data['version']
        return install_data['commit']

    @classmethod
    def parse_mode(cls, mode):
        if mode == "repo":
            return InstallMode.REPO
        elif mode == "pkg64c":
            return InstallMode.PKG
        elif mode == "cheribuild":
            return InstallMode.CHERIBUILD
        else:
            print(f"Wrong mode parsed: {mode}")
            assert(False)

to_parse_time = {
    "total-time" : re.compile(r'real (\d+\.\d+)'),
    "rss-kb" : re.compile(r'\s*(\d+)  maximum resident set size'),
    }

class ExecutorType(enum.Enum):
    TIME = enum.auto()
    PMC = enum.auto()

    def parse_output(self, exec_res):
        fail_condition = not exec_res or exec_res.exited != 0
        result = {}
        if self == ExecutorType.TIME:
            if fail_condition:
                result = { k : 0.0 for k in to_parse_time.keys() }
            else:
                for row in exec_res.stderr.splitlines():
                    for parse_key, parse_re in to_parse_time.items():
                        match = parse_re.match(row)
                        if match:
                            assert parse_key not in result
                            result[parse_key] = float(match.group(1))
                assert(len(result) == len(to_parse_time))
            result["returncode"] = exec_res.exited
            result["stdout"] = exec_res.stdout
            result["stderr"] = exec_res.stderr
        elif self == ExecutorType.PMC:
            if fail_condition: # or not r"p/" in output.splitlines()[0]:
                result = { k : 0 for k in pmc_events_names }
            else:
                output = exec_res.stderr
                counters = list(map(str.strip, output.splitlines()[0].split("p/")))[1:]
                values = map(int, output.splitlines()[1].split())
                try:
                    result = dict(zip(counters, values, strict = True))
                except ValueError:
                    result = { k : 0 for k in pmc_events_names }
            result["pmc-returncode"] = exec_res.exited
            result["pmc-stdout"] = exec_res.stdout
            result["pmc-stderr"] = exec_res.stderr
        else:
            assert False
        return result

class Allocator:
    def __init__(self, folder, json_data):
        self.name = os.path.basename(folder.removesuffix('/')).replace('_', '-')
        self.info_folder = os.path.abspath(folder)
        self.install_mode = InstallMode.parse_mode(json_data['install']['mode'])
        self.install_target = json_data['install']['target']
        if self.install_mode == InstallMode.PKG:
            # self.source_path =
            self.cheribsd_ports_path = json_data['cheribsd_ports_path']
            self.cheribsd_ports_commit = json_data['commit']
        elif self.install_mode == InstallMode.CHERIBUILD:
            # self.source_path = parse_path(json_data['install']['source'])
            self.build_path = os.path.join(work_dir_local, self.name)
            self.source_path = os.path.join(work_dir_local, self.name, json_data['install']['source'])
        elif self.install_mode == InstallMode.REPO:
            self.source_path = os.path.join(work_dir_local, self.name)
        self.version = self.install_mode.parse_version(json_data['install'])
        self.no_attacks = False if not "no_attacks" in json_data else json_data['no_attacks']
        self.no_benchs  = False if not "no_benchs"  in json_data else json_data['no_benchs']
        self.raw_data = json_data

    def get_build_file_path(self):
        print(self.info_folder)
        return os.path.join(self.info_folder, self.raw_data['install']['build_file'])

    def get_remote_lib_path(self, machine, mode):
        return os.path.join(machine.get_work_dir(mode), os.path.basename(self.get_libfile(mode)))

    def get_cheribuild_target(self, mode):
        return self.install_target[mode]["name"]

    def get_libfile(self, mode):
        if self.install_mode == InstallMode.PKG:
            lib_file_path = parse_path(self.install_target[mode]["lib_file"])
        elif self.install_mode == InstallMode.CHERIBUILD:
            lib_file_path = os.path.join(self.build_path, self.install_target[mode]["lib_file"])
        elif self.install_mode == InstallMode.REPO:
            lib_file_path = parse_path(self.raw_data['install']['lib_file'])
            lib_file_path = f"-{mode}.so".join(lib_file_path.rsplit(".so", 1))
            if not os.path.isabs(lib_file_path):
                lib_file_path = os.path.join(self.source_path, lib_file_path)
        else:
            assert(False)
        assert(os.path.isabs(lib_file_path))
        return lib_file_path

    def get_static_libfile(self, mode):
        if self.install_mode == InstallMode.REPO:
            static_lib_path = self.raw_data['install']['lib_file_static']
            if not os.path.isabs(static_lib_path):
                static_lib_path = os.path.join(self.source_path, static_lib_path)
        elif self.install_mode == InstallMode.CHERIBUILD:
            static_lib_path = self.raw_data['install']['target'][mode]['lib_file_static']
            if not os.path.isabs(static_lib_path):
                static_lib_path = os.path.join(self.build_path, static_lib_path)
        else:
            assert(False)
        return static_lib_path

    def get_raw_libfile(self):
        assert(self.install_mode == InstallMode.REPO)
        raw_lib_path = self.raw_data['install']['lib_file']
        if not os.path.isabs(raw_lib_path):
            raw_lib_path = os.path.join(self.source_path, raw_lib_path)
        return raw_lib_path

    def do_source(self):
        if self.install_mode == InstallMode.CHERIBUILD:
            to_install = benchmark_modes.keys() if not self.no_benchs else [default_mode]
            os.makedirs(self.build_path, exist_ok = True)
            os.chdir(get_config('cheribuild_folder'))
            for mode in to_install:
                subprocess.run(
                    make_cheribuild_cmd(self.get_cheribuild_target(mode), source = self.build_path, flags = ""),
                    stdout = None)
                repo = git.Repo(path = subprocess.check_output(
                    shlex.split("git rev-parse --show-toplevel"),
                    cwd = self.source_path, encoding = 'UTF-8').strip())
                repo.git.fetch("origin", self.version)
                repo.git.checkout(self.version)
            os.chdir(base_cwd)
        elif self.install_mode == InstallMode.REPO:
            if not os.path.exists(self.source_path):
                repo = git.Repo.clone_from(
                        url = self.install_target, to_path = self.source_path)
            else:
                repo = git.Repo(self.source_path)
            repo.git.fetch("origin", self.version)
            repo.git.checkout(self.version)
        elif self.install_mode == InstallMode.PKG:
            # TODO
            pass

    def do_install(self, compile_env):
        to_install = benchmark_modes.keys() if not self.no_benchs else [default_mode]
        for mode in to_install:
            log_message(f"Installing {self.name} Mode {mode}")
            compile_env["CFLAGS"]   = benchmark_modes[mode]["cflags"]
            compile_env["CXXFLAGS"] = benchmark_modes[mode]["cflags"]
            if self.install_mode == InstallMode.CHERIBUILD:
                os.chdir(get_config('cheribuild_folder'))
                flags = "-c"
                if mode == "hybrid":
                    flags = " ".join([flags, "--enable-hybrid-targets"])
                subprocess.run(make_cheribuild_cmd(self.get_cheribuild_target(mode), source = self.build_path, flags = flags), stdout = None)
                os.chdir(base_cwd)
                for machine in execution_targets.values():
                    machine.put_file(self.get_libfile(mode), machine.get_work_dir(mode))
            elif self.install_mode == InstallMode.REPO:
                subprocess.run([self.get_build_file_path(), work_dir_local], env = compile_env, cwd = self.source_path)
                assert(os.path.exists(self.get_raw_libfile()))
                shutil.move(self.get_raw_libfile(), self.get_libfile(mode))
                for machine in execution_targets.values():
                    machine.put_file(self.get_libfile(mode), machine.get_work_dir(mode))
            elif self.install_mode == InstallMode.PKG:
                for machine in execution_targets.values():
                    machine.install_alloc(self.install_target[mode]["name"], self.version, mode)
                    machine.run_cmd(f"cp {self.get_libfile(mode)} {machine.get_work_dir(mode)}")

    def do_install_static(self, compile_env):
        if self.install_mode in [InstallMode.REPO, InstallMode.CHERIBUILD]:
            return
        else:
            assert(False)

class Benchmark:
    def __init__(self, name):
        self.name = name
        self.paths = dict.fromkeys(benchmark_modes.keys(), {"remote": None, "local": None})

    def add_path(self, path_type, mode, path):
        assert(path_type in ["remote", "local"])
        assert(not self.paths[mode][path_type])
        self.paths[mode][path_type] = path

    def get_path(self, path_type, mode):
        assert(self.paths[mode][path_type])
        return self.paths[mode][path_type]

class ExecEnvironment:
    def __init__(self, addr):
        addr_regex = "(\w+)@([\w\.]+):(\d+)"
        self.user, self.host, self.port = re.match(addr_regex, addr).groups()
        self.conn = Connection(host = self.host, user = self.user, port = self.port)

    def __del__(self):
        self.conn.close()

    def install_alloc(self, alloc, version, mode):
        pkg = benchmark_modes[mode]["pkg_manager"]
        if self.user == "root":
            self.run_cmd(f"{pkg} install -y {alloc}-{version}", check = True)
        else:
            assert(self.run_cmd(f"{pkg} info {alloc}-{version}").exited == 0)

    def run_cmd(self, cmd, env = {}, check = False):
        return self.conn.run(cmd, env = env, warn = not check, hide = 'both')

    def put_file(self, src, dest):
        return self.conn.put(src, remote = dest)

    def set_rhome(self, path):
        self.rhome = path

    def set_work_dir(self, path):
        self.work_dir = path

    def get_work_dir(self, mode):
        return os.path.join(self.work_dir, mode)

class BenchExecutor:
    def __init__(self, cmd):
        if cmd.startswith("time"):
            self.type = ExecutorType.TIME
        elif cmd.startswith("pmcstat"):
            self.type = ExecutorType.PMC
        else:
            print(f"Cannot parse executor type for cmd {cmd}")
            sys.exit(1)
        self.cmd = cmd

    def do_exec(self, target, target_dir, environ, machine):
        cmd = f"cd {target_dir} ; {self.cmd} {target}"
        log_message(f" - {cmd}")
        exec_res = machine.run_cmd(cmd, env = environ, check = False)
        return self.type.parse_output(exec_res)

################################################################################
# Preparation
################################################################################

def prepare_cheri():
    if args.no_build_cheri:
        assert(args.local_dir)
        assert(os.path.exists(args.local_dir))
        return
    log_message(f"Building new CHERI components in {work_dir_local}")
    targets = ["morello-llvm-native", "cheribsd-morello-purecap"]
    if not args.no_run_benchmarks:
        targets.extend(["cheribsd-morello-hybrid", "--enable-hybrid-targets"])
    cmd = shlex.split(f"./cheribuild.py -d -f --source-root {work_dir_local}/cheribuild {' '.join(targets)}")
    subprocess.check_call(cmd, cwd = get_config('cheribuild_folder'))
    return

def prepare_qemu():
    if args.no_build_cheri:
        assert(args.local_dir)
        assert(os.path.exists(args.local_dir))
    else:
        log_message(f"Building new QEMU instance in {work_dir_local}")
        cmd = make_cheribuild_cmd(" ". join(["qemu", "disk-image-morello-purecap"]), source = f"{work_dir_local}/cheribuild")
        # cmd = shlex.split(f"./cheribuild.py -d -f --source-root {work_dir_local}/cheribuild qemu disk-image-morello-purecap")
        subprocess.check_call(cmd, cwd = get_config('cheribuild_folder'))
    artifact_path = os.path.join(work_dir_local, "cheribuild")
    assert(os.path.exists(os.path.join(artifact_path, "output", "sdk", "bin", "qemu-system-morello")))
    port = config['cheri_qemu_port']
    qemu_cmd = f"""
        {artifact_path}/output/sdk/bin/qemu-system-morello
        -M virt,gic-version=3 -cpu morello -bios edk2-aarch64-code.fd -m 2048
        -nographic
        -drive if=none,file={artifact_path}/output/cheribsd-morello-purecap.img,id=drv,format=raw
        -device virtio-blk-pci,drive=drv -device virtio-net-pci,netdev=net0
        -netdev 'user,id=net0,smb={artifact_path}<<<source_root@ro:{artifact_path}/build<<<build_root:{artifact_path}/output<<<output_root@ro:{artifact_path}/output/rootfs-morello-purecap<<<rootfs,hostfwd=tcp::{port}-:22'
        -device virtio-rng-pci
    """
    log_message(re.compile(r'\s+').sub(' ', qemu_cmd))
    with open(os.path.join(work_dir_local, "qemu_child.log"), 'w') as qemu_child_log:
        qemu_child = subprocess.Popen(shlex.split(qemu_cmd), stdin = subprocess.PIPE, stdout = qemu_child_log, stderr = qemu_child_log)
    print("Waiting for emulator...")
    if not args.no_wait_qemu:
        time.sleep(2 * 60) # wait for instance to boot
    attempts = 0
    attempts_max = 5
    attempts_cd = 10
    while attempts < attempts_max:
        print(f"-- checking if QEMU running; try {attempts}...")
        with Connection(f"root@localhost:{port}") as qemu_conn:
            check_proc = qemu_conn.run("echo hi", warn = False)
        print(f"-- saw return code {check_proc.exited}")
        if check_proc.exited == 0:
            return qemu_child
        attempts += 1
        time.sleep(attempts_cd)
    return None

def prepare_cheribsd_ports():
    to_path = os.path.join(work_dir_local, 'cheribsd-ports')
    if not os.path.exists(to_path):
        repo = git.Repo.clone_from(url = get_config('cheribsd_ports_url'),
                                   to_path = to_path,
                                   multi_options = ["--depth 1", "--single-branch"])
    else:
        repo = git.Repo(to_path)
    return repo

def prepare_attacks(attacks_path, machine):
    attack_sources = glob.glob(os.path.join(attacks_path, "*.c"))
    for to_ignore in config["attacks_to_ignore"]:
        attack_sources = [x for x in attack_sources if not to_ignore in x]
    log_message(f"Found attacks in {attacks_path}: {attack_sources}")
    assert(attack_sources)
    attacks = []
    compile_cmd = f"{os.path.join(work_dir_local, 'cheribuild', 'output', 'morello-sdk', 'bin', 'clang')} --std=c11 -Wall --config cheribsd-morello-purecap.cfg"
    compile_cmd = shlex.split(compile_cmd)
    for source in attack_sources:
        attack = os.path.join(work_dir_local, os.path.splitext(os.path.basename(source))[0])
        subprocess.run(compile_cmd + ['-o', attack, source], check = True)
        attacks.append(attack)
        machine.put_file(attack, machine.work_dir)
    return attacks

def prepare_benchs(bench_sources, machine, static_alloc = None):
    assert(os.path.exists(bench_sources))
    cmake_config_cmd = """cmake -S {source} -B {dest}/build
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX={dest}/install
    -Dgclib={lib} -Dbm_logfile=out.json -DSDK={sdk}
    -DCMAKE_TOOLCHAIN_FILE={toolchain}"""
    benchs =  {}
    for mode in benchmark_modes.keys():
        if static_alloc:
            dest = os.path.join(work_dir_local, f"static-benchs-{mode}-{static_alloc.name}")
            machine_dest_dir = os.path.join(machine.get_work_dir(mode), f"static-{mode}-{static_alloc.name}")
            lib = "static"
            cmake_config_cmd = f"{cmake_config_cmd} -Dstaticlib={static_alloc.get_static_libfile(mode)}"
            if "static_flags" in static_alloc.raw_data["install"]:
                cmake_config_cmd = f"{cmake_config_cmd} -Dstatic_flags='{static_alloc.raw_data['install']['static_flags']}'"
            if args.benchs_static_lto:
                cmake_config_cmd = f"{cmake_config_cmd} -Dstatic_lto=TRUE"
        else:
            dest = os.path.join(work_dir_local, f"benchs-{mode}")
            machine_dest_dir = machine.get_work_dir(mode)
            lib = "jemalloc"
        cmake_config_cmd = cmake_config_cmd.format(
                source = bench_sources, dest = dest, lib = lib,
                sdk = os.path.join(work_dir_local, "cheribuild", "output", "morello-sdk"),
                toolchain = os.path.join(bench_sources, f"morello-{mode}.cmake"))
        log_message(f"Preparing benchmarks (static alloca {static_alloc.name if static_alloc else None})\n -- {cmake_config_cmd}")
        subprocess.check_call(shlex.split(cmake_config_cmd))
        subprocess.check_call(shlex.split(f"cmake --build {os.path.join(dest, 'build')}"))
        subprocess.check_call(shlex.split(f"cmake --install {os.path.join(dest, 'build')}"))
        for dir_path, _, new_bench_files in os.walk(os.path.join(dest, "install")):
            for filn in new_bench_files:
                machine.run_cmd(f"mkdir -p {machine_dest_dir}")
                machine.put_file(os.path.join(dir_path, filn), machine_dest_dir)
                if filn.endswith(".elf"):
                    benchs[filn] = {mode: {"local_path" : dir_path, "remote_path" : machine_dest_dir } }
    bench_objs = []
    for bench_name,bench_paths in benchs.items():
        new_bench = Benchmark(bench_name)
        for mode,paths in bench_paths.items():
            new_bench.add_path("local", mode, paths["local_path"])
            new_bench.add_path("remote", mode, paths["remote_path"])
        bench_objs.append(new_bench)
    return bench_objs

################################################################################
# Application
################################################################################

def do_line_count(source_path):
    cloc_data = json.loads(subprocess.check_output(make_cloc_cmd(source_path), encoding = 'UTF-8'))
    return cloc_data['SUM']['code']

def do_cheri_line_count(alloc_path):
    data = subprocess.check_output([get_config('data_get_script_path'), "cheri-line-count", alloc_path], encoding = 'UTF-8')
    return int(re.search(cheri_lines_pattern, data).group(1))

def do_attacks(alloca, attacks, machine):
    if alloca.no_attacks:
        return {}, False
    results = {}
    for attack in attacks:
        cmd = os.path.join(machine.work_dir, os.path.basename(attack))
        remote_env = { 'LD_PRELOAD' : alloca.get_remote_lib_path(machine, "purecap") }
        log_message(f'{get_timestamp()} RUN {cmd} WITH ENV {remote_env}')
        start_time = time.perf_counter_ns()
        attack_res = machine.run_cmd(cmd, env = remote_env, check = False)
        runtime = time.perf_counter_ns() - start_time
        if "validate" in attack:
            validated = attack_res.exited == 0
        results[attack] = {}
        results[attack]['exit_code'] = attack_res.exited
        results[attack]['stdout'] = attack_res.stdout
        results[attack]['stderr'] = attack_res.stderr
        results[attack]['time'] = runtime
    return results, validated

def do_benchs(alloca, benchs, machine, static = False):
    if alloca.no_benchs:
        return {}
    results = {}
    wrappers = ["time -p -l"]
    pmc_timeout = 1200
    pmc_events = [ f"-p {event}" for event in pmc_events_names ]
    wrappers.append(f"pmcstat -d -w {pmc_timeout} {' '.join(pmc_events)}")
    executors = [BenchExecutor(x) for x in wrappers]
    do_mean = lambda x: np.mean(x)
    do_geomean = lambda x: np.exp(np.log(x).mean())
    iteration_count = args.benchs_rep_count
    for mode in benchmark_modes:
        results[mode] = {}
        for bench_obj in benchs:
            bench = bench_obj.name
            results[mode][bench] = {}
            for time_entries in to_parse_time:
                results[mode][bench][time_entries] = []
            for pmc_event in pmc_events_names:
                results[mode][bench][pmc_event] = []
            for extras in ["stdout", "stderr", "returncode", "pmc-stdout", "pmc-stderr", "pmc-returncode"]:
                results[mode][bench][extras] = []
            bench_cmd = " ".join(["./" + bench, get_config("benchmarks_params").get(os.path.splitext(bench)[0], "").strip()])
            remote_env = { } if static else { benchmark_modes[mode]["environ"] : alloca.get_remote_lib_path(machine, mode) }
            for it in range(iteration_count):
                it_result = {}
                for executor in executors:
                    log_message(f"{get_timestamp()} RUN {bench} ({it + 1} / {iteration_count}) TYPE {executor.type} WITH ENV {remote_env}")
                    it_result.update(executor.do_exec(bench_cmd, bench_obj.get_path("remote", mode), remote_env, machine))
                results[mode][bench] = {k : v + [it_result[k]] for k,v in results[mode][bench].items()}
            if 0 in results[mode][bench]["returncode"]:
                for event in to_parse_time:
                    results[mode][bench] = prep_data(results[mode][bench], event, False, do_mean)
                for event in pmc_events_names:
                    results[mode][bench] = prep_data(results[mode][bench], event, False, do_geomean)
            else:
                for event in [*to_parse_time.keys(), *pmc_events_names]:
                    results[mode][bench] = prep_data(results[mode][bench], event, True)
    for mode in benchmark_modes:
        for bench in results[mode]:
            for event in [*to_parse_time.keys(), *pmc_events_names]:
                if {"purecap", "hybrid"} <= set(benchmark_modes) and results["hybrid"][bench][event] > 0.0:
                    results[mode][bench][f"normalised-{event}"] = results[mode][bench][event] / results["hybrid"][bench][event]
                else:
                    results[mode][bench][f"normalised-{event}"] = 0.0
    return results

def get_source_data(alloca):
    source_data = {}
    if alloca.install_mode == InstallMode.PKG:
        cheribsd_ports_repo.git.fetch("origin", alloca.cheribsd_ports_commit)
        cheribsd_ports_repo.git.checkout(alloca.cheribsd_ports_commit)
        alloc_path = os.path.join(cheribsd_ports_repo.working_dir, alloca.cheribsd_ports_path)
        assert(os.path.exists(alloc_path))
        source_data['api'] = do_cheri_api(alloc_path, api_fns)
        source_data['cheri_loc'] = do_cheri_line_count(alloc_path)
    else:
        source_data['api'] = do_cheri_api(alloca.source_path, api_fns)
        source_data['sloc'] = do_line_count(alloca.source_path)
        source_data['cheri_loc'] = do_cheri_line_count(alloca.source_path)
    return source_data

def do_cheri_api(source_dir, apis_info):
    api_fns = set()
    get_funcs = lambda x : set(x.strip().split(os.linesep))
    try:
        api_fns.update(get_funcs(subprocess.check_output(make_grep_pattern_cmd(cheri_fn_grep_pattern, source_dir), encoding = 'UTF-8')))
        api_fns = set([x.removesuffix("(") for x in api_fns])
    except subprocess.CalledProcessError:
        pass
    try:
        api_fns.update(get_funcs(subprocess.check_output(make_grep_pattern_cmd(cheri_builtin_fn_call_grep_pattern, source_dir), encoding="UTF-8")))
    except subprocess.CalledProcessError:
        pass
    found_apis = dict.fromkeys(apis_info.keys(), 0)
    not_found_funcs = []
    for api_fn in api_fns:
        found = False
        for api in apis_info:
            if api_fn in apis_info[api]:
                found_apis[api] += 1
                found= True
                break
        if not found:
            not_found_funcs.append(api_fn)
    return found_apis, not_found_funcs

################################################################################
# Latex Tables
################################################################################

def do_table_cheri_api(results):
    preamble = []
    epilogue = []
    if args.table_context:
        preamble = [r'\begin{table}[t]', r'\begin{center}', r'\begin{tabular}{lcrr}']
        preamble += [r'\toprule', r'allocator & API & \# API calls & \# builtin calls \\']
        preamble += [r'\midrule']

        epilogue = [r'\\ \bottomrule', r'\end{tabular}']
        epilogue += [r'\caption{\label{tab:rq1}Coverage of CHERI API calls by various allocators}']
        epilogue += [r'\label{tab:atks}', r'\end{center}', r'\end{table}']
    entries = []
    for result in results:
        if not 'api' in result:
            continue
        api_key = max(result['api'][0], key = result['api'][0].get)
        entry = [result['name']]
        entry.append(api_key)
        entry.append(result['api'][0][api_key])
        entry.append(result['api'][0]['builtin'])
        entries.append(' & '.join(map(str, entry)))
    table = '\n'.join(['\n'.join(preamble), '\\\\\n'.join(entries), '\n'.join(epilogue)])
    return table

def do_table_attacks_parse_result(result, attack):
    if result["results_attacks"][attack]["exit_code"] == 0:
        result_stdout = result["results_attacks"][attack]["stdout"]
        if "Attack unsuccessful" in result_stdout:
            return r'$\checkmark$'
        elif "Attack successful" in result_stdout:
            return r'$\times$'
        else:
            return 'P'
    else:
        return r'$\oslash$'

def do_table_attacks_entries(result, attack_names):
    new_entry = []
    attack_sources = attacks if not args.parse_data_only else sorted(result["results"].keys())
    for attack in attack_sources:
        if os.path.basename(attack) in config["table_attacks_to_ignore"]:
            continue
        new_entry.append(do_table_attacks_parse_result(result, attack))
    return new_entry

def do_table_attacks(results):
    attack_names = [os.path.splitext(x)[0] for x in map(os.path.basename, sorted(attacks)) if not os.path.splitext(x)[0] in (config["table_attacks_to_ignore"] + config["attacks_to_ignore"])]
    preamble = f'% {" & ".join(attack_names)}'
    epilogue = []
    if args.table_context:
        latexify = lambda x : r'\tbl' + x.replace('_', '').replace('2', "two").replace('3', "three")
        header_fields = len(attack_names) * 'c'
        preamble += [r'\begin{table}[t]', r'\begin{center}', r'\begin{tabular}{l' + header_fields + r'}']
        preamble += [r'\toprule', r'Allocator & ' + ' & '.join(map(latexify, attack_names)) + r'\\']
        preamble += [r'\midrule']

        epilogue = [r'\input{./data/results/attacks_extra.tex}']
        epilogue += [r'\\ \bottomrule', r'\end{tabular}']
        epilogue += [r'''\caption{Attacks which succeed on a given allocator
        are marked with a $\times$, while unsuccessful attacks are marked with
        a $\checkmark$; attack executions which fail due to other reasons
        (e.g., segmentation faults) are marked with $\oslash$.}''']
        epilogue += [r'\label{tab:atks}', r'\end{center}', r'\end{table}']
    entries = []
    for result in results:
        if not result['results_attacks'] or not result['validated']:
            continue
        entry = [result['name']]
        entry.extend(do_table_attacks_entries(result, attack_names))
        entries.append(' & '.join(entry))
    table = '\n'.join(['\n'.join(preamble), '\\\\\n'.join(entries), '\n'.join(epilogue)])
    return table

def do_table_slocs(results):
    preamble = []
    epilogue = []
    if args.table_context:
        preamble += [r'\begin{table}[tb]', r'\begin{center}', r'\begin{tabular}{lcrrr}']
        preamble += [r'\toprule', ' & '.join(['Allocator', 'Version', 'SLoC', r'\multicolumn{2}{c}{Changed}']) + r'\\']
        preamble += [r'\cmidrule(lr){4-5}', ' & '.join([' ', ' ', ' ', 'LoC', r'\multicolumn{1}{c}{\%}']) + r'\\']
        preamble += [r'\midrule']

        epilogue += [r'\\ \bottomrule', r'\end{tabular}', r'\end{center}']
        epilogue += [r'''\caption{The allocators we examined, their size in
                Source Lines of Code (SLoC), and the number of lines changed to
                adapt them for pure capability CheriBSD.}''']
        epilogue += [r'\label{tab:allocator_summary}', r'\end{table}']
    entries = []
    for result in results:
        entry = [result['name']]
        entry.append(result['version'][:10].replace('_', r"\_"))
        if 'sloc' in result:
            entry.append(r'\numprint{' + str(result['sloc']) + r'}')
            entry.append(r'\numprint{' + str(result['cheri_loc']) + r'}')
            entry.append("{:.2f}".format(result['cheri_loc'] * 100 / result['sloc']))
        else:
            entry.extend(['-', '-', '-'])
        entries.append(' & '.join(map(str, entry)))
    if args.slocs_table_template:
        ordered_entries = []
        with open(args.slocs_table_template, 'r') as tmpl:
            for alloc in tmpl.readlines():
                if alloc == "---":
                    ordered_entries.append(r'\midrule')
                    continue
                entry = [x for x in entries if x.startswith(alloc)]
                assert(len(entry) == 1)
                ordered_entries.extend(entry)
        entries = ordered_entries
    table = '\n'.join(['\n'.join(preamble), '\\\\\n'.join(entries), '\n'.join(epilogue)])
    return table

def do_all_tables(results):
    results = sorted(results, key = itemgetter("name"))
    with open(os.path.join(work_dir_local, "cheri_api.tex"), 'w') as cheri_api_fd:
        cheri_api_fd.write(do_table_cheri_api(results))
    if not args.no_run_attacks:
        with open(os.path.join(work_dir_local, "tests.tex"), 'w') as attacks_fd:
            attacks_fd.write(do_table_attacks(results))
    with open(os.path.join(work_dir_local, "slocs.tex"), 'w') as slocs_fd:
        slocs_fd.write(do_table_slocs(results))

################################################################################
# Main
################################################################################

# Initial setup
config_path = "./config.json"
with open(config_path, 'r') as json_config:
    config = json.load(json_config)
base_cwd = os.getcwd()

# Gather allocator folders
allocators = []
if args.alloc:
    allocators = [args.alloc]
else:
    allocators = [alloc_dir.path for alloc_dir in os.scandir(get_config('allocators_folder')) if alloc_dir.is_dir()]

# Prepare local work directories
work_dir_prefix = "cheri_alloc_"
if args.local_dir:
    work_dir_local = os.path.abspath(args.local_dir)
else:
    work_dir_local = tempfile.mkdtemp(prefix = work_dir_prefix, dir = os.getcwd())

# Local files
results_tmp_path = os.path.join(work_dir_local, "results_tmp.json")
results_path = os.path.join(work_dir_local, "results.json")
log_fd = open(os.path.join(work_dir_local, args.log_file), 'w')
log_message(f"Set local work directory to {work_dir_local}")

if args.parse_data_only:
    log_message(f"Parsing results file at {args.parse_data_only}.")
    with open(args.parse_data_only, 'r') as results_fd:
        results = json.load(results_fd)
    attacks = sorted([x for x in glob.glob(os.path.join(get_config('attacks_folder'), "*.c"))])
    api_fns = read_apis(get_config('cheri_api_path'))
    do_all_tables(results)
    log_message(f"DONE in {work_dir_local}")
    log_fd.close()
    sys.exit(0)

# Symlink last execution work directory
symlink_name = f"{work_dir_prefix}last"
if os.path.exists(symlink_name):
    os.remove(symlink_name)
os.symlink(work_dir_local, symlink_name)

# Build new CHERI infrastructure
prepare_cheri()
api_fns = read_apis(get_config('cheri_api_path'))

# Build and run new CHERI QEMU instance
qemu_proc = None
qemu_env = None
for targets in execution_targets.copy():
    if f"no_run_{targets}" in vars(args) and vars(args)[f"no_run_{targets}"]:
        assert(not f"{targets}_machine" in vars(args) or not vars(args)[f"{targets}_machine"])
        del execution_targets[targets]
        continue
    if f"{targets}_machine" in vars(args) and vars(args)[f"{targets}_machine"]:
        execution_targets[targets] = ExecEnvironment(vars(args)[f"{targets}_machine"])
    else:
        if not qemu_env:
            qemu_proc = prepare_qemu()
            if not qemu_proc:
                log_message("Unable to build or run QEMU instance; exiting...")
                sys.exit(1)
            qemu_env = ExecEnvironment("root@localhost:10086")
        execution_targets[targets] = qemu_env
assert(execution_targets)
cheribsd_ports_repo = prepare_cheribsd_ports()

# Prepare remote work directories
for machine in execution_targets.values():
    machine.set_rhome(machine.run_cmd("printf $HOME", check = True).stdout)
    machine.run_cmd(f"mkdir -p {get_config('cheri_qemu_test_folder', machine)}", check = True)
    machine.work_dir = machine.run_cmd(f"mktemp -d {get_config('cheri_qemu_test_folder', machine)}/{work_dir_prefix}XXX", check = True).stdout.strip()
    for mode in benchmark_modes:
        machine.run_cmd(f"mkdir -p {os.path.join(machine.work_dir, mode)}")

# Prepare attacks and read API data
if not args.no_run_attacks:
    attacks = sorted(prepare_attacks(get_config('attacks_folder'), execution_targets["attacks"]))

# Prepare benchmarks
if not args.no_run_benchmarks:
    # Only run purecap benchmarks in static mode (TODO at least for now?)
    if args.benchs_static:
        if not args.benchs_static == "all":
            benchmark_modes = { args.benchs_static : benchmark_modes[args.benchs_static] }
    benchs = sorted(prepare_benchs(get_config('benchmarks_folder'), execution_targets["benchmarks"]), key = operator.attrgetter("name"))
    os.makedirs(os.path.join(work_dir_local, benchmarks_graph_folder), exist_ok = True)

# Environment for cross-compiling
compile_env = {
        "CC": get_config('cheribsd_cc'),
        "CXX": get_config('cheribsd_cxx'),
        "LD": get_config('cheribsd_ld'),
        "PATH": os.getenv('PATH'),
        }

results = []
for alloc_folder in allocators:
    log_message(f"=== PARSING {alloc_folder}")
    if not os.path.exists(f"{alloc_folder}/info.json"):
        log_message("No `info.json` found; skipping...")
        continue
    with open(f"{alloc_folder}/info.json", 'r') as alloc_info_json:
        alloca = Allocator(alloc_folder, json.load(alloc_info_json))
    alloc_data = {"name": alloca.name}

    # Get source for default mode (NOTE currently "purecap")
    alloca.do_source()

    # SLoCs, CHERI API calls count
    alloc_data.update(get_source_data(alloca))

    # Install
    alloca.do_install(compile_env)

    # Prepare static library is needed
    if args.benchs_static:
        alloca.do_install_static(compile_env)

    # Attacks and validation
    if not args.no_run_attacks:
        alloc_data['results_attacks'], alloc_data['validated'] = do_attacks(alloca, attacks, execution_targets["attacks"])

    # Benchmarks
    if not args.no_run_benchmarks and not alloca.no_benchs:
        alloc_data['results_benchs'] = do_benchs(alloca, benchs, execution_targets["benchmarks"])
        if args.benchs_static:
            static_benchs = prepare_benchs(get_config('benchmarks_folder'), execution_targets["benchmarks"], alloca)
            alloc_data['results_benchs_static'] = do_benchs(alloca, static_benchs, execution_targets["benchmarks"])
        # Only produce graphs if we run both purecap and hybrid benchmarks
        if {"purecap", "hybrid"} <= set(benchmark_modes):
            tmp_results_path = os.path.join(work_dir_local, "benchs_temp.json")
            with open(tmp_results_path, 'w') as benchs_tmp_fd:
                json.dump(alloc_data['results_benchs'], benchs_tmp_fd)
                graphs_folder = os.path.join(work_dir_local, benchmarks_graph_folder, alloca.name)
                if os.path.exists(graphs_folder):
                    shutil.rmtree(graphs_folder)
                os.mkdir(graphs_folder)
                graphplot.plot("histogram", \
                               tmp_results_path,
                               os.path.join(work_dir_local, benchmarks_graph_folder, alloca.name, f"{alloca.name}.pdf"),
                               ([*to_parse_time.keys(), *pmc_events_names], []),
                               True, conf_interval = 98)
            #pdfs = map(str,
            #           pathlib.Path(os.path.join(
            #               work_dir_local, benchmarks_graph_folder, alloca.name))
            #           .glob("*.pdf"))
            #subprocess.check_call(f"qpdf --empty --pages {' '.join(pdfs)} -- out-full-{alloca.name}.pdf")

    # Version info
    alloc_data['version'] = alloca.version

    pprint.pprint(alloc_data, width = shutil.get_terminal_size().columns)
    results.append(alloc_data)
    with open(os.path.join(work_dir_local, "results_tmp.json"), 'w') as results_file:
        json.dump(results, results_file, indent = 4)
    log_message(f"=== DONE {alloc_folder}")

# Terminate QEMU instance
if qemu_proc:
    qemu_proc.kill()

os.rename(results_tmp_path, results_path)
do_all_tables(results)

log_message(f"DONE in {work_dir_local}")

log_fd.close()
