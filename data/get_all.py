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
import sys

from fabric import Connection

################################################################################
# Constants
################################################################################

cheri_lines_pattern = "^Total CHERI lines: [[:digit:]]+$"

cheri_fn_pattern = "cheri_[a-zA-Z0-9_]+"
cheri_fn_grep_pattern = "\\bcheri_[[:alnum:]_]\+("

cheri_builtin_fn_pattern = "__builtin_cheri[a-zA-Z0-9_]+"
cheri_builtin_fn_grep_pattern = "BUILTIN(__builtin_cheri[[:alnum:]_]\+"
cheri_builtin_fn_call_grep_pattern = "__builtin_cheri[[:alnum:]_]\+"

################################################################################
# Arguments
################################################################################

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument("--alloc", type=str, action='store', required=False, help="Optional path to allocator. If not given, runs over all allocators given in `config.json`.")
args = arg_parser.parse_args()

################################################################################
# Functions
################################################################################

def make_ssh_cmd(cmd):
    return shlex.split(f"ssh -p{config['cheri_qemu_port']} -t root@localhost {cmd}")

def make_scp_cmd(path_from, path_to):
    return shlex.split(f"scp -P{config['cheri_qemu_port']} {path_from} root@localhost:{path_to}")

def make_cheribuild_cmd(target):
    return shlex.split(f"./cheribuild.py -d {target}")

def make_grep_pattern_cmd(pattern, target):
    return shlex.split(f"grep -oIrhe '{pattern}' {target}")

def make_install_alloc_cmd(alloc_name, alloc_ver):
    return make_ssh_cmd(f"pkg64c install -y {alloc_name}-{alloc_ver}")
    # TODO

def make_replace(path):
    path = path.replace('$HOME', os.getenv('HOME'))
    return path

def prepare_tests(tests_path, dest_path):
    tests = [x for x in glob.glob(os.path.join(tests_path, "*")) if os.access(x, os.X_OK)]
    assert(tests)
    subprocess.run(make_scp_cmd(" ".join(tests), f"{dest_path}"), check = True)
    subprocess.run(make_scp_cmd(f"{config['cheri_qemu_test_script_path']}", f"{config['cheri_qemu_test_folder']}"), check = True)
    return tests

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

################################################################################
# Main
################################################################################

def do_install(info, compile_env):
    if info['mode'] == 'cheribuild':
        os.chdir(config['cheribuild_folder'])
        subprocess.run(make_cheribuild_cmd(info['target']), stdout = None)
        repo_path = info['source'].replace("$HOME", os.getenv("HOME"))
        if 'commit' in info:
            repo = git.Repo(path = repo_path)
            repo.git.checkout(info['commit'])
        os.chdir(repo_path)
        if 'build_file' in info:
            subprocess.run(os.path.join(base_cwd, alloc_folder, info['build_file']), env = compile_env)
        if 'lib_file' in info and not 'no_copy' in info:
            subprocess.run(make_scp_cmd(info['lib_file'], work_dir_remote), check = True)
        os.chdir(base_cwd)
    elif info['mode'] == 'repo':
        alloc_path = os.path.join(work_dir_local, alloc_data['name'])
        if not os.path.exists(alloc_path):
            repo = git.Repo.clone_from(url = info['repo'], to_path = alloc_path)
        else:
            repo = git.Repo(alloc_path)
        repo.git.checkout(info['commit'])
        if 'build_file' in info:
            os.chdir(alloc_path)
            subprocess.run(os.path.join(base_cwd, alloc_folder, info['build_file']), env = compile_env)
            os.chdir(base_cwd)
        if 'lib_file' in info:
            cmd = make_scp_cmd(os.path.join(alloc_path, info['lib_file']), work_dir_remote)
            print(cmd)
            subprocess.run(cmd, check = True)
    elif info['mode'] == 'pkg64c':
        subprocess.run(make_install_alloc_cmd(info['target'], info['version']))
    else:
        return False
    return True

def do_cheri_line_count(alloc_path):
    proc = subprocess.run(shlex.split([config['data_get_script_path'], "cheri-line-count", alloc_path]), stdout = subprocess.PIPE)
    if proc.returncode == 0:
        with open(f"count_{alloc_data['name']}", 'w') as line_fd:
            line_fd.write(proc.stdout)
        alloc_data['cheri-lines'] = int(re.search(cheri_lines_pattern, proc.stdout).string().rsplit(' ', 1)[0])

def do_tests(tests, lib_path):
    results = {}
    for test in tests:
        test_conn = Connection(host="localhost", user="root", port=10086, inline_ssh_env = True)
        cmd = os.path.join(work_dir_remote, os.path.basename(test))
        print(f"- Running test {cmd}")
        remote_env = {}
        if lib_path:
            remote_env = { 'LD_PRELOAD' : lib_path }
        test_res = test_conn.run(cmd, env = remote_env, warn = True)
        results[test] = {}
        results[test]['exit_code'] = test_res.exited
        results[test]['stdout'] = test_res.stdout
        results[test]['stderr'] = test_res.stderr
    return results

def do_cheri_api(source_dir, apis_info):
    api_fns = set()
    get_funcs = lambda x : set(x.strip().split(os.linesep))
    try:
        api_fns.update(get_funcs(subprocess.check_output(make_grep_pattern_cmd(cheri_fn_grep_pattern, source_dir), encoding="UTF-8")))
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

config_path = "./config.json"
with open(config_path, 'r') as json_config:
    config = json.load(json_config)

allocators = []
if args.alloc:
    allocators = [args.alloc]
else:
    allocators = [alloc_dir.path for alloc_dir in os.scandir(config['allocators_folder']) if alloc_dir.is_dir()]

base_cwd = os.getcwd()
work_dir_local = tempfile.mkdtemp(prefix = "cheri_alloc_", dir = os.getcwd())
subprocess.run(make_ssh_cmd(f"mkdir -p {config['cheri_qemu_test_folder']}"), check = True)
work_dir_remote = subprocess.check_output(make_ssh_cmd(f"mktemp -d {config['cheri_qemu_test_folder']}/{config['cheri_qemu_test_exec_template']}"), encoding = "UTF-8")
work_dir_remote = work_dir_remote.strip()
tests = prepare_tests(config['tests_folder'], work_dir_remote)
api_fns = read_apis(config['cheri_api_path'])

compile_env = {
        "CC": config['cheribsd_cc'].replace('$HOME', os.getenv('HOME')),
        "CFLAGS": config['cheribsd_cflags'],
        "CXX": config['cheribsd_cxx'].replace('$HOME', os.getenv('HOME')),
        "CXXFLAGS": config['cheribsd_cxxflags'],
        "LD": config['cheribsd_ld'].replace('$HOME', os.getenv('HOME')),
        "PATH": os.getenv('PATH'),
        }

for alloc_folder in allocators:
    print(f"=== PARSING {alloc_folder}")
    assert(os.path.exists(f"{alloc_folder}/info.json"))
    with open(f"{alloc_folder}/info.json", 'r') as alloc_info_json:
        alloc_info = json.load(alloc_info_json)
    alloc_data = {}
    alloc_data['name'] = os.path.basename(alloc_folder.removesuffix('/'))
    if not do_install(alloc_info['install'], compile_env):
        print(f"Unsupported install mode: {alloc_data['mode']}")
    if alloc_info['install']['mode'] in ['cheribuild', 'repo'] \
            and 'lib_file' in alloc_info['install']:
        remote_lib_path = os.path.join(work_dir_remote, os.path.basename(alloc_info['install']['lib_file']))
    elif 'lib_file' in alloc_info['install']:
        remote_lib_path = alloc_info['install']['lib_file']
    else:
        remote_lib_path = None
    if 'no_run' in alloc_info['install']:
        alloc_data['results'] = "Not run"
    else:
        alloc_data['results'] = do_tests(tests, remote_lib_path)
    if 'source' in alloc_info['install']:
        alloc_data['api'] = do_cheri_api(alloc_info['install']['source'].replace('$HOME', os.getenv('HOME')), api_fns)
    elif alloc_info['install']['mode'] == 'repo':
        alloc_data['api'] = do_cheri_api(os.path.join(work_dir_local, alloc_data['name']), api_fns)
    print(alloc_data)
    print(f"=== DONE {alloc_folder}")
