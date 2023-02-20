#!/usr/bin/env python3

import argparse
import git
import json
import os
import glob
import subprocess
import shlex
import re
import tempfile
import time
import sys

from operator import itemgetter

from fabric import Connection

################################################################################
# Constants
################################################################################

cheri_lines_pattern = "Total CHERI lines: (\d+)"

cheri_fn_pattern = "cheri_[a-zA-Z0-9_]+"
cheri_fn_grep_pattern = "\\bcheri_[[:alnum:]_]\+("

cheri_builtin_fn_pattern = "__builtin_cheri[a-zA-Z0-9_]+"
cheri_builtin_fn_grep_pattern = "BUILTIN(__builtin_cheri[[:alnum:]_]\+"
cheri_builtin_fn_call_grep_pattern = "__builtin_cheri[[:alnum:]_]\+"

################################################################################
# Arguments
################################################################################

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument("--alloc", type=str, action='store', required=False,
        help="""Optional path to allocator. If not given, runs over all
        allocators given in `config.json`.""")
arg_parser.add_argument("--local-dir", type=str, action='store', default=None,
        required=False, metavar="path",
        help="Where to store local data, instead of generating a folder.")
arg_parser.add_argument("--log-file", type=str, action='store',
        default='cheri_alloc.log', metavar="path",
        help="File to store log data to")
arg_parser.add_argument("--no-build-cheri", action="store_true",
        help="""Whether to build CheriBSD and the QEMU image from scratch. Only
        set if `local-dir` is set with a pre-existing build within.""")
arg_parser.add_argument("--parse-data-only", action='store', default="",
        type=str, metavar="path",
        help="Parse given results file to generate LaTeX tables.")
arg_parser.add_argument("--target-machine", action='store', default="",
        type=str, metavar="IP",
        help="""IP address of a CHERI-enabled machine on the network to run
        experiments on instead of using a QEMU instance. NOTE: This requires
        appropriate keys being set-up between the machines to communicate
        without further user input""")
args = arg_parser.parse_args()

################################################################################
# Functions
################################################################################

def make_ssh_cmd(cmd):
    if args.target_machine:
        target = args.target_machine
        port = ""
    else:
        target = "root@localhost"
        port = f'-p{config["cheri_qemu_port"]}'
    return shlex.split(f'ssh -o "StrictHostKeyChecking=no" -o "UserKnownHostsFile=/dev/null" {port} -t {target} {cmd}')

def make_scp_cmd(path_from, path_to):
    if args.target_machine:
        target = args.target_machine
        port = ""
    else:
        target = "root@localhost"
        port = f'-P{config["cheri_qemu_port"]}'
    return shlex.split(f'scp -o "StrictHostKeyChecking=no" -o "UserKnownHostsFile=/dev/null" {port} {path_from} {target}:{path_to}')

def make_cheribuild_cmd(target, flags = ""):
    cmd = shlex.split(f'./cheribuild.py -d -f --skip-update --source-root {work_dir_local}/cheribuild {flags} {target}')
    print(f"MADE {cmd}")
    return cmd

def make_grep_pattern_cmd(pattern, target):
    return shlex.split(f"grep -oIrhe '{pattern}' {target}")

def make_install_alloc_cmd(alloc_name, alloc_ver):
    return make_ssh_cmd(f"pkg64c install -y {alloc_name}-{alloc_ver}")

def make_cloc_cmd(path):
    return shlex.split(f"cloc --json {path}")

def make_replace(path):
    path = path.replace('$HOME', os.getenv('HOME'))
    return path

def prepare_tests(tests_path, dest_path):
    test_sources = glob.glob(os.path.join(tests_path, "*.c"))
    for to_ignore in config["tests_to_ignore"]:
        test_sources = [x for x in test_sources if not to_ignore in x]
    log_message(f"Found tests in {tests_path}: {test_sources}")
    assert(test_sources)
    tests = []
    compile_cmd = f"{os.path.join(work_dir_local, 'cheribuild', 'output', 'morello-sdk', 'bin', 'clang')} --std=c11 -Wall --config cheribsd-morello-purecap.cfg"
    for source in test_sources:
        test = os.path.join(work_dir_local, os.path.splitext(os.path.basename(source))[0])
        subprocess.run(shlex.split(compile_cmd) + ['-o', test, source], check = True)
        tests.append(test)
    subprocess.run(make_scp_cmd(" ".join(tests), f"{dest_path}"), check = True)
    return tests

def get_config(to_get):
    return parse_path(config[to_get])

def parse_path(to_parse):
    if to_parse.startswith("$HOME"):
        to_parse = to_parse.replace("$HOME", os.getenv("HOME"))
    elif to_parse.startswith("$WORK"):
        to_parse = to_parse.replace("$WORK", work_dir_local)
    elif to_parse.startswith("$CWD"):
        to_parse = to_parse.replace("$CWD", base_cwd)
    elif to_parse.startswith("$RHOME"):
        to_parse = to_parse.replace("$RHOME", remote_homedir)
    else:
        print(f"Did not parse anything for path {to_parse}.")
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

def log_message(msg):
    print(msg)
    log_fd.write(msg + '\n')

################################################################################
# Main
################################################################################

def prepare_cheri():
    if args.no_build_cheri:
        assert(args.local_dir)
        assert(os.path.exists(args.local_dir))
    else:
        log_message(f"Building new QEMU instance in {work_dir_local}")
        cmd = shlex.split(f"./cheribuild.py -d -f --source-root {work_dir_local}/cheribuild qemu disk-image-morello-purecap")
        subprocess.run(cmd, cwd = get_config('cheribuild_folder'))
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
    time.sleep(2 * 60) # wait for instance to boot
    attempts = 0
    attempts_max = 5
    attempts_cd = 10
    while attempts < attempts_max:
        print(f"-- checking if QEMU running; try {attempts}...")
        check_proc = subprocess.run(make_ssh_cmd('echo hi'), check = False)
        print(f"-- saw return code {check_proc.returncode}")
        if check_proc.returncode == 0:
            return qemu_child
        attempts += 1
        time.sleep(attempts_cd)
    return None

def prepare_cheribsd_ports():
    repo = git.Repo.clone_from(url = get_config('cheribsd_ports_url'),
                               to_path = os.path.join(work_dir_local,
                                                      'cheribsd-ports'),
                               multi_options = ["--depth 1", "--single-branch"])
    return repo

def do_install(info, compile_env):
    if info['mode'] == 'cheribuild':
        os.chdir(get_config('cheribuild_folder'))
        subprocess.run(make_cheribuild_cmd(info['target'], "--configure-only"), stdout = None)
        repo_path = parse_path(info['source'])
        assert('commit' in info)
        repo = git.Repo(path = subprocess.check_output(shlex.split("git rev-parse --show-toplevel"), cwd = repo_path, encoding = 'UTF-8').strip())
        repo.git.fetch("origin", info['commit'])
        repo.git.checkout(info['commit'])
        subprocess.run(make_cheribuild_cmd(info['target'], "-c"), stdout = None)
        if 'build_file' in info and info['build_file']:
            subprocess.run(os.path.join(base_cwd, alloc_folder, info['build_file']), env = compile_env, cwd = repo_path)
        os.chdir(base_cwd)
        if 'lib_file' in info and info['lib_file'] and not 'no_copy' in info:
            subprocess.run(make_scp_cmd(parse_path(info['lib_file']), work_dir_remote), check = True)
    elif info['mode'] == 'repo':
        alloc_path = os.path.join(work_dir_local, alloc_data['name'])
        if not os.path.exists(alloc_path):
            repo = git.Repo.clone_from(url = info['repo'], to_path = alloc_path)
        else:
            repo = git.Repo(alloc_path)
        repo.git.checkout(info['commit'])
        if 'build_file' in info and info['build_file']:
            os.chdir(alloc_path)
            subprocess.run([os.path.join(base_cwd, alloc_folder, info['build_file']), work_dir_local], env = compile_env)
            os.chdir(base_cwd)
        if 'lib_file' in info and info['lib_file'] and not 'no_copy' in info:
            subprocess.run(make_scp_cmd(os.path.join(alloc_path, info['lib_file']), work_dir_remote), check = True)
    elif info['mode'] == 'pkg64c':
        if args.target_machine:
            check_cmd = subprocess.run(make_ssh_cmd(f"pkg64c info {info['target']}"))
            return check_cmd.returncode == 0
        else:
            subprocess.run(make_install_alloc_cmd(info['target'], info['version']))
        assert(os.path.exists(os.path.join(cheribsd_ports_repo.working_tree_dir, info['ports_path'])))
    else:
        return False
    return True

def do_line_count(source_path):
    cloc_data = json.loads(subprocess.check_output(make_cloc_cmd(source_path), encoding = 'UTF-8'))
    return cloc_data['SUM']['code']

def do_cheri_line_count(alloc_path):
    data = subprocess.check_output([get_config('data_get_script_path'), "cheri-line-count", alloc_path], encoding = 'UTF-8')
    return int(re.search(cheri_lines_pattern, data).group(1))

def do_tests(tests, lib_path):
    results = {}
    if args.target_machine:
        assert('@' in args.target_machine)
        conn_user, conn_host = args.target_machine.split('@')
        conn_port = None
    else:
        conn_user = "root"
        conn_host = "localhost"
        conn_port = config['cheri_qemu_port']
    for test in tests:
        cmd = os.path.join(work_dir_remote, os.path.basename(test))
        print(f"- Running test {cmd}")
        remote_env = {}
        if lib_path:
            print(f"-- with `LD_PRELOAD` at {lib_path}")
            remote_env = { 'LD_PRELOAD' : lib_path }
        log_message(f"RUN {cmd} WITH ENV {remote_env}")
        # test_conn = Connection(host="localhost", user="root", port=10086, inline_ssh_env = True)
        start_time = time.perf_counter_ns()
        with Connection(host=conn_host, user=conn_user, port=conn_port) as test_conn:
            test_res = test_conn.run(cmd, env = remote_env, warn = True)
        runtime = time.perf_counter_ns() - start_time
        if "validate" in test:
            validated = test_res.exited == 0
        results[test] = {}
        results[test]['exit_code'] = test_res.exited
        results[test]['stdout'] = test_res.stdout
        results[test]['stderr'] = test_res.stderr
        results[test]['time'] = runtime
    return results, validated

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

def do_table_cheri_api(results):
    preamble = [r'\begin{table}[t]', r'\begin{center}', r'\begin{tabular}{lcrr}']
    preamble += [r'\toprule', r'allocator & API & \# API calls & \# builtin calls \\']
    preamble += [r'\midrule']
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
    epilogue = [r'\\ \bottomrule', r'\end{tabular}']
    epilogue += [r'\caption{\label{tab:rq1}Coverage of CHERI API calls by various allocators}']
    epilogue += [r'\label{tab:atks}', r'\end{center}', r'\end{table}']
    table = '\n'.join(['\n'.join(preamble), '\\\\\n'.join(entries), '\n'.join(epilogue)])
    return table

def do_table_tests_entries(result, test_names):
    new_entry = []
    if args.parse_data_only:
        for test in sorted(result["results"].keys()):
            if os.path.basename(test) in config["table_tests_to_ignore"]:
                continue
            assert(os.path.basename(test) in test_names)
            if result["results"][test]["exit_code"] == 0:
                new_entry.append(r'\times')
            elif "Assertion failed" in result["results"][test]["stderr"]:
                new_entry.append(r'$\checkmark$')
            else:
                new_entry.append(r'$\oslash$')
    else:
        for test in tests:
            if result["results"][test]["exit_code"] == 0:
                new_entry.append(r'\checkmark')
            else:
                new_entry.append(r'$\times$')
    return new_entry

def do_table_tests(results):
    latexify = lambda x : r'\tbl' + x.replace('_', '').replace('2', "two")
    test_names = [os.path.splitext(x)[0] for x in map(os.path.basename, sorted(tests)) if not os.path.splitext(x)[0] in (config["table_tests_to_ignore"] + config["tests_to_ignore"])]
    header_fields = len(test_names) * 'c'
    preamble = [r'\begin{table}[t]', r'\begin{center}', r'\begin{tabular}{l' + header_fields + r'}']
    preamble += [r'\toprule', r'Allocator & ' + ' & '.join(map(latexify, test_names)) + r'\\']
    preamble += [r'\midrule']
    entries = []
    for result in results:
        if not result['results'] or not result['validated']:
            continue
        entry = [result['name']]
        entry.extend(do_table_tests_entries(result, test_names))
        entries.append(' & '.join(entry))
    epilogue = [r'\input{./data/results/tests_extra.tex}']
    epilogue += [r'\\ \bottomrule', r'\end{tabular}']
    epilogue += [r'\caption{Attacks which succeed on a given allocator are marked with a $\times$; attack executions which fail due to other reasons (e.g., segmentation faults) are marked with $\oslash$.}']
    epilogue += [r'\label{tab:atks}', r'\end{center}', r'\end{table}']
    table = '\n'.join(['\n'.join(preamble), '\\\\\n'.join(entries), '\n'.join(epilogue)])
    return table

def do_table_slocs(results):
    preamble = [r'\begin{table}[tb]', r'\begin{center}', r'\begin{tabular}{lcrrr}']
    preamble += [r'\toprule', ' & '.join(['Allocator', 'Version', 'SLoC', r'\multicolumn{2}{c}{Changed}']) + r'\\']
    preamble += [r'\cmidrule(lr){4-5}', ' & '.join([' ', ' ', ' ', 'LoC', r'\multicolumn{1}{c}{\%}']) + r'\\']
    preamble += [r'\midrule']
    entries = []
    for result in results:
        entry = [result['name']]
        entry.append(result['version'][:10].replace('_', r"\_"))
        if 'sloc' in result:
            entry.append(r'\numprint{' + str(result['sloc']) + r'}')
            entry.append(r'\numprint{' + str(result['cheri_loc']) + r'}')
            entry.append("{:.2f}\%".format(result['cheri_loc'] * 100 / result['sloc']))
        else:
            entry.extend(['-', '-', '-'])
        entries.append(' & '.join(map(str, entry)))
    epilogue = [r'\\ \bottomrule', r'\end{tabular}', r'\end{center}']
    epilogue += [r'\caption{The allocators we examined, their size in Source Lines of Code (SLoC), and the number of lines changed to adapt them for pure capability CheriBSD.}']
    epilogue += [r'\label{tab:allocator_summary}', r'\end{table}']
    table = '\n'.join(['\n'.join(preamble), '\\\\\n'.join(entries), '\n'.join(epilogue)])
    return table

def do_all_tables(results):
    results = sorted(results, key = itemgetter("name"))
    with open(os.path.join(work_dir_local, "cheri_api.tex"), 'w') as cheri_api_fd:
        cheri_api_fd.write(do_table_cheri_api(results))
    with open(os.path.join(work_dir_local, "tests.tex"), 'w') as tests_fd:
        tests_fd.write(do_table_tests(results))
    with open(os.path.join(work_dir_local, "slocs.tex"), 'w') as slocs_fd:
        slocs_fd.write(do_table_slocs(results))

#-------------------------------------------------------------------------------

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
    tests = sorted([x for x in glob.glob(os.path.join(get_config('tests_folder'), "*.c"))])
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

# Build and run new CHERI QEMU instance
if not args.target_machine:
    qemu_child = prepare_cheri()
    if not qemu_child:
        log_message("Unable to build or run QEMU instance; exiting...")
        sys.exit(1)

# Prepare remote work directories
remote_homedir = subprocess.check_output(make_ssh_cmd("printf '$HOME'"), encoding = "UTF-8")
subprocess.run(make_ssh_cmd(f"mkdir -p {get_config('cheri_qemu_test_folder')}"), check = True)
work_dir_remote = subprocess.check_output(make_ssh_cmd(f"mktemp -d {get_config('cheri_qemu_test_folder')}/{work_dir_prefix}XXX"), encoding = "UTF-8")
work_dir_remote = work_dir_remote.strip()
log_message(f"Set remote work directory to {work_dir_remote}")

# Prepare tests and read API data
tests = sorted(prepare_tests(get_config('tests_folder'), work_dir_remote))
api_fns = read_apis(get_config('cheri_api_path'))
cheribsd_ports_repo = prepare_cheribsd_ports()

# Environment for cross-compiling
compile_env = {
        "CC": get_config('cheribsd_cc'),
        "CFLAGS": config['cheribsd_cflags'],
        "CXX": get_config('cheribsd_cxx'),
        "CXXFLAGS": config['cheribsd_cxxflags'],
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
        alloc_info = json.load(alloc_info_json)
    alloc_data = {}
    alloc_data['name'] = os.path.basename(alloc_folder.removesuffix('/')).replace('_', '-')

    # Install
    if not do_install(alloc_info['install'], compile_env):
        if args.target_machine:
            log_message(f"Unable to find package {alloc_info['install']['target']}; please install manually!")
        else:
            log_message(f"Unsupported install mode: {alloc_data['mode']}")
        continue

    # Tests and validation
    if alloc_info['install']['mode'] in ['cheribuild', 'repo'] \
            and 'lib_file' in alloc_info['install'] \
            and alloc_info['install']['lib_file'] \
            and not os.path.isabs(alloc_info['install']['lib_file']):
        remote_lib_path = os.path.join(work_dir_remote, os.path.basename(alloc_info['install']['lib_file']))
    elif 'lib_file' in alloc_info['install']:
        remote_lib_path = alloc_info['install']['lib_file']
    else:
        remote_lib_path = None
    if 'no_run' in alloc_info['install'] or ('lib_file' in alloc_info['install'] and not alloc_info['install']['lib_file']):
        alloc_data['results'] = False
        alloc_data['validated'] = False
    else:
        alloc_data['results'], alloc_data['validated'] = do_tests(tests, remote_lib_path)

    # SLoCs, CHERI API calls count
    if 'source' in alloc_info['install']:
        # alloc_path = alloc_info['install']['source'].replace('$HOME', os.getenv('HOME'))
        alloc_path = parse_path(alloc_info['install']['source'])
        alloc_data['api'] = do_cheri_api(alloc_path, api_fns)
        alloc_data['sloc'] = do_line_count(alloc_path)
        alloc_data['cheri_loc'] = do_cheri_line_count(alloc_path)
    elif alloc_info['install']['mode'] == 'repo':
        alloc_path = os.path.join(work_dir_local, alloc_data['name'])
        alloc_data['api'] = do_cheri_api(alloc_path, api_fns)
        alloc_data['sloc'] = do_line_count(alloc_path)
        alloc_data['cheri_loc'] = do_cheri_line_count(alloc_path)
    elif alloc_info['install']['mode'] == 'pkg64c':
        cheribsd_ports_repo.checkout(alloc_info['commit'])
        alloc_path = os.path.join(cheribsd_ports_repo.working_dir, alloc_info['cheribsd_ports_path'])
        alloc_data['api'] = do_cheri_api(alloc_path, api_fns)
        alloc_data['cheri_loc'] = do_cheri_line_count(alloc_path)

    # Version info
    if alloc_info['install']['mode'] in ['repo', 'cheribuild'] :
        alloc_data['version'] = alloc_info['install']['commit']
    elif alloc_info['install']['mode'] in ['pkg64c']:
        alloc_data['version'] = alloc_info['install']['version']
    else:
        assert(False)

    print(alloc_data)
    results.append(alloc_data)
    with open(os.path.join(work_dir_local, "results_tmp.json"), 'w') as results_file:
        json.dump(results, results_file)
    log_message(f"=== DONE {alloc_folder}")

# Terminate QEMU instance
if not args.target_machine:
    qemu_child.kill()

os.rename(results_tmp_path, results_path)
do_all_tables(results)

log_message(f"DONE in {work_dir_local}")

log_fd.close()
