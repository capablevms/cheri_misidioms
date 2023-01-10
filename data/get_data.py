#!/usr/bin/env python3

import argparse
import glob
import os
import shlex
import subprocess
import sys

################################################################################
# Constants
################################################################################

cmd_choices = ["headers", "api", "api-calls", "api-count", "cheri-line-count"]

CHERI_apis = [ "cheri", "cheric", "cheriintrin" ]
mk_search_cmd = lambda p : f"egrep -Iroh {p} {args.folder}"
undupe_and_split = lambda inp : os.linesep.join(set(inp.splitlines()))

api_func_pattern = "'(__builtin_)?cheri_[[:alnum:]_]+\('"

################################################################################
# Arguments
################################################################################

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument("command", type=str, action='store', choices=cmd_choices, help="Action to perform")
arg_parser.add_argument("folder", type=str, action='store', help="Target folder to inspect")
args = arg_parser.parse_args()

################################################################################
# Helper
################################################################################

def count_cheri_lines(path):
    cheri_ifdefs = ["___CHERI_PURE_CAPABILITY__", "__CHERI_"]
    endifs = ["#endif"]
    elses = ["#else", "#elif"]
    ifdefs = ["#ifdef", "#if defined", "#ifndef"]
    check_contains = lambda to_check, line: any(map(line.__contains__, to_check))

    with open(path, 'r') as cheri_file:
        in_cheri_ifdef = False
        num_cheri_lines = 0
        depth_ifdefs = 0
        for line in cheri_file.readlines():
            # check for an ifdef
            if check_contains(ifdefs, line) and check_contains(cheri_ifdefs, line):
                # if it's a cheri ifdef, start counting num lines
                assert (in_cheri_ifdef == False), "CHERI ifdef inside CHERI ifdef?"
                in_cheri_ifdef = True
                num_cheri_lines += 1
                depth_ifdefs += 1
            elif in_cheri_ifdef:
                # bump line counter
                num_cheri_lines += 1
                # and it's another ifdef, bump stack
                if check_contains(ifdefs, line):
                    depth_ifdefs += 1
                elif check_contains(endifs, line):
                    # if it's an endif, pop stack
                    depth_ifdefs -= 1
                    assert (depth_ifdefs >= 0), "improperly nested ifdefs"
                    # if we are at 0, stop counting num lines...
                    if depth_ifdefs==0:
                        in_cheri_ifdef = False
                elif check_contains(elses, line) and depth_ifdefs==1:
                    # end of CHERI clause in multi-armed conditional
                     in_cheri_ifdef = False
                     depth_ifdefs = 0
    return num_cheri_lines

################################################################################
# Main
################################################################################

if args.command == "headers":
    cmd = subprocess.run(shlex.split(mk_search_cmd('^#include.*cheri[^[:space:]]*')), capture_output=True, encoding='UTF-8')
    print(undupe_and_split(cmd.stdout))
elif args.command == "api":
    cmd = subprocess.run(shlex.split(mk_search_cmd('^#include.*cheri[^[:space:]]*')), capture_output=True, encoding='UTF-8')
    api = ""
    for curr_api in CHERI_apis:
        if f"{curr_api}.h" in cmd.stdout:
            assert(not api)
            api = curr_api
    assert(api)
    print(api)
elif args.command == "api-calls":
    cmd = subprocess.run(shlex.split(mk_search_cmd(api_func_pattern)), capture_output=True, encoding='UTF-8')
    calls = [call[:-1] for call in set(cmd.stdout.splitlines())]
    calls.sort()
    print(os.linesep.join(calls))
elif args.command == "api-count":
    cmd = subprocess.run(shlex.split(mk_search_cmd(api_func_pattern)), capture_output=True, encoding='UTF-8')
    print(len(set(cmd.stdout.splitlines())))
elif args.command == "cheri-line-count":
    total_cheri_lines = 0
    dict_cheri_lines = {}
    zero_cheri_lines = []
    for source_file in glob.iglob(f"{args.folder}/**/*.*", recursive = True):
        if not os.access(source_file, os.X_OK):
            try:
                new_cheri_lines = count_cheri_lines(source_file)
            except UnicodeDecodeError:
                print(f"Invalid format: {source_file}")
                continue
            except AssertionError as ae:
                print(f"Assertion error: {source_file} --- {ae}")
                continue
            if new_cheri_lines == 0:
                zero_cheri_lines.append(source_file)
            else:
                dict_cheri_lines[source_file] = new_cheri_lines
            total_cheri_lines += new_cheri_lines
    print(f"Files with zero cheri lines: {zero_cheri_lines}")
    print(dict_cheri_lines)
    print(f"Total CHERI lines: {total_cheri_lines}")
else:
    print(f"Unknown command {args.command}")
    sys.exit(1)
