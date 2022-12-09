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
import signal
import sys

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
        help="Optional path to allocator. If not given, runs over all allocators given in `config.json`.")
arg_parser.add_argument("--local-dir", type=str, action='store', required=False,
        help="Where to store local data, instead of generating a folder.")
args = arg_parser.parse_args()

################################################################################
# Functions
################################################################################

def make_ssh_cmd(cmd):
    return shlex.split(f"ssh -p{config['cheri_qemu_port']} -t root@localhost {cmd}")

def make_scp_cmd(path_from, path_to):
    return shlex.split(f"scp -P{config['cheri_qemu_port']} {path_from} root@localhost:{path_to}")

def make_cheribuild_cmd(target, flags = ""):
    cmd = shlex.split(f"./cheribuild.py -d -f --skip-update --source-root {work_dir_local}/cheribuild {flags} {target}")
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
    tests = [x for x in glob.glob(os.path.join(tests_path, "*")) if os.access(x, os.X_OK)]
    assert(tests)
    subprocess.run(make_scp_cmd(" ".join(tests), f"{dest_path}"), check = True)
    subprocess.run(make_scp_cmd(f"{config['cheri_qemu_test_script_path']}", f"{config['cheri_qemu_test_folder']}"), check = True)
    return tests

def parse_path(to_parse):
    to_parse = to_parse.replace("$HOME", os.getenv("HOME"))
    to_parse = to_parse.replace("$WORK", work_dir_local)
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
                fns = subprocess.check_output(make_grep_pattern_cmd(pattern, api_file), encoding = "UTF-8")
                fns = fns.strip().split(os.linesep)
                if api == "builtin":
                    fns = [x.removeprefix("BUILTIN(") for x in fns]
                else:
                    fns = [x.removesuffix("(") for x in fns]
                api_fns[api].update(fns)
    return api_fns

def tstp_handler(signum, frame):
    print("Saw SIGTSTP; ignoring...")

################################################################################
# Main
################################################################################

def do_install(info, compile_env):
    if info['mode'] == 'cheribuild':
        os.chdir(config['cheribuild_folder'])
        subprocess.run(make_cheribuild_cmd(info['target'], "--configure-only"), stdout = None)
        repo_path = parse_path(info['source'])
        assert('commit' in info)
        repo = git.Repo(path = subprocess.check_output(shlex.split("git rev-parse --show-toplevel"), cwd = repo_path, encoding = 'UTF-8').strip())
        repo.git.fetch("origin", info['commit'])
        repo.git.checkout(info['commit'])
        subprocess.run(make_cheribuild_cmd(info['target']), stdout = None)
        os.chdir(repo_path)
        if 'build_file' in info and info['build_file']:
            subprocess.run(os.path.join(base_cwd, alloc_folder, info['build_file']), env = compile_env)
        if 'lib_file' in info and info['lib_file'] and not 'no_copy' in info:
            subprocess.run(make_scp_cmd(parse_path(info['lib_file']), work_dir_remote), check = True)
        os.chdir(base_cwd)
    elif info['mode'] == 'repo':
        alloc_path = os.path.join(work_dir_local, alloc_data['name'])
        if not os.path.exists(alloc_path):
            repo = git.Repo.clone_from(url = info['repo'], to_path = alloc_path)
        else:
            repo = git.Repo(alloc_path)
        repo.git.checkout(info['commit'])
        if 'build_file' in info and info['build_file']:
            os.chdir(alloc_path)
            subprocess.run(os.path.join(base_cwd, alloc_folder, info['build_file']), env = compile_env)
            os.chdir(base_cwd)
        if 'lib_file' in info and info['lib_file'] and not 'no_copy' in info:
            subprocess.run(make_scp_cmd(os.path.join(alloc_path, info['lib_file']), work_dir_remote), check = True)
    elif info['mode'] == 'pkg64c':
        subprocess.run(make_install_alloc_cmd(info['target'], info['version']))
    else:
        return False
    return True

def do_line_count(source_path):
    cloc_data = json.loads(subprocess.check_output(make_cloc_cmd(source_path), encoding = 'UTF-8'))
    return cloc_data['SUM']['code']

def do_cheri_line_count(alloc_path):
    data = subprocess.check_output([config['data_get_script_path'], "cheri-line-count", alloc_path], encoding = 'UTF-8')
    return int(re.search(cheri_lines_pattern, data).group(1))
    # if proc.returncode == 0:
        # with open(f"count_{alloc_data['name']}", 'w') as line_fd:
            # line_fd.write(proc.stdout)
        # alloc_data['cheri-lines'] = int(re.search(cheri_lines_pattern, proc.stdout).string().rsplit(' ', 1)[0])

def do_tests(tests, lib_path):
    results = {}
    for test in tests:
        test_conn = Connection(host="localhost", user="root", port=10086, inline_ssh_env = True)
        cmd = os.path.join(work_dir_remote, os.path.basename(test))
        print(f"- Running test {cmd}")
        remote_env = {}
        if lib_path:
            print(f"-- with `LD_PRELOAD` at {lib_path}")
            remote_env = { 'LD_PRELOAD' : lib_path }
        test_res = test_conn.run(cmd, env = remote_env, warn = True)
        if "validate" in test:
            validated = test_res.exited == 0
        results[test] = {}
        results[test]['exit_code'] = test_res.exited
        results[test]['stdout'] = test_res.stdout
        results[test]['stderr'] = test_res.stderr
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
    preamble = [r'\begin{table}', r'\begin{center}', r'\begin{tabular}{ccrr}']
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

def do_table_tests(results):
    sanitize = lambda x : x.replace('_', '-')
    preamble = [r'\begin{table}', r'\begin{center}', r'\begin{tabular}{ccrr}']
    preamble += [r'\toprule', r' & ' + ' & '.join(map(sanitize, map(os.path.basename, tests))) + r'\\']
    preamble += [r'\midrule']
    entries = []
    for result in results:
        if not result['results'] or not result['validated']:
            continue
        entry = [result['name']]
        for test in tests:
            if result['results'][test] == 0:
                entry.append(r'\checkmark')
            else:
                entry.append(r'$\times$')
        entries.append(' & '.join(entry))
    epilogue = [r'\\ \bottomrule', r'\end{tabular}']
    epilogue += [r'\caption{Attacks which succeed on a given allocator are marked with a $\times$.}']
    epilogue += [r'\label{tab:atks}', r'\end{center}', r'\end{table}']
    table = '\n'.join(['\n'.join(preamble), '\\\\\n'.join(entries), '\n'.join(epilogue)])
    return table

def do_table_slocs(results):
    preamble = [r'\begin{table}[tb]', r'\begin{center}', r'\begin{tabular}{lllll}']
    preamble += [r'\toprule', ' & '.join(['Allocator', 'Version', 'SLoC', r'\multicolumn{2}{c}{Changed}']) + r'\\']
    preamble += [r'\cmidrule(lr){4-5}', ' & '.join([' ', ' ', ' ', 'LoC', r'\multicolumn{1}{c}{\%}']) + r'\\']
    preamble += [r'\midrule']
    entries = []
    for result in results:
        if 'sloc' in result:
            entry = [result['name']]
            entry.append(result['version'])
            entry.append(result['sloc'])
            entry.append(result['cheri_loc'])
            entry.append("{:.2f}%".format(result['cheri_loc'] * 100 / result['sloc']))
            entries.append(' & '.join(map(str, entry)))
    epilogue = [r'\\ \bottomrule', r'\end{tabular}', r'\end{center}']
    epilogue += [r'\caption{The allocators we examined, their size in Source Lines of Code (SLoC), and the number of lines changed to adapt them for pure capability CheriBSD.}']
    epilogue += [r'\label{tab:allocator_summary}', r'\end{table}']
    table = '\n'.join(['\n'.join(preamble), '\\\\\n'.join(entries), '\n'.join(epilogue)])
    return table

signal.signal(signal.SIGTSTP, tstp_handler)

config_path = "./config.json"
with open(config_path, 'r') as json_config:
    config = json.load(json_config)

allocators = []
if args.alloc:
    allocators = [args.alloc]
else:
    allocators = [alloc_dir.path for alloc_dir in os.scandir(config['allocators_folder']) if alloc_dir.is_dir()]

base_cwd = os.getcwd()

# Prepare work directories
work_dir_prefix = "cheri_alloc_"
if args.local_dir:
    work_dir_local = args.local_dir
else:
    work_dir_local = tempfile.mkdtemp(prefix = work_dir_prefix, dir = os.getcwd())
subprocess.run(make_ssh_cmd(f"mkdir -p {config['cheri_qemu_test_folder']}"), check = True)
work_dir_remote = subprocess.check_output(make_ssh_cmd(f"mktemp -d {config['cheri_qemu_test_folder']}/{work_dir_prefix}XXX"), encoding = "UTF-8")
work_dir_remote = work_dir_remote.strip()

# Symlink last execution work directory
symlink_name = f"{work_dir_prefix}last"
if os.path.exists(symlink_name):
    os.remove(symlink_name)
os.symlink(work_dir_local, symlink_name)

tests = prepare_tests(config['tests_folder'], work_dir_remote)
api_fns = read_apis(config['cheri_api_path'])

# Environment for cross-compiling
compile_env = {
        "CC": config['cheribsd_cc'].replace('$HOME', os.getenv('HOME')),
        "CFLAGS": config['cheribsd_cflags'],
        "CXX": config['cheribsd_cxx'].replace('$HOME', os.getenv('HOME')),
        "CXXFLAGS": config['cheribsd_cxxflags'],
        "LD": config['cheribsd_ld'].replace('$HOME', os.getenv('HOME')),
        "PATH": os.getenv('PATH'),
        }

results = []
for alloc_folder in allocators:
    print(f"=== PARSING {alloc_folder}")
    assert(os.path.exists(f"{alloc_folder}/info.json"))
    with open(f"{alloc_folder}/info.json", 'r') as alloc_info_json:
        alloc_info = json.load(alloc_info_json)
    alloc_data = {}
    alloc_data['name'] = os.path.basename(alloc_folder.removesuffix('/')).replace('_', '-')

    # Install
    if not do_install(alloc_info['install'], compile_env):
        print(f"Unsupported install mode: {alloc_data['mode']}")

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

    # Version info
    if alloc_info['install']['mode'] in ['repo', 'cheribuild'] :
        alloc_data['version'] = alloc_info['install']['commit']
    elif alloc_info['install']['mode'] in ['pkg64c']:
        alloc_data['version'] = alloc_info['install']['version']
    else:
        assert(False)

    print(alloc_data)
    results.append(alloc_data)
    print(f"=== DONE {alloc_folder}")

with open(os.path.join(work_dir_local, "cheri_api.tex"), 'w') as cheri_api_fd:
    cheri_api_fd.write(do_table_cheri_api(results))
with open(os.path.join(work_dir_local, "tests.tex"), 'w') as tests_fd:
    tests_fd.write(do_table_tests(results))
with open(os.path.join(work_dir_local, "slocs.tex"), 'w') as slocs_fd:
    slocs_fd.write(do_table_slocs(results))
with open(os.path.join(work_dir_local, "results.json"), 'w') as results_file:
    json.dump(results, results_file)
print(f"DONE in {work_dir_local}")
