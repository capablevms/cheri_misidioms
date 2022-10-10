#!/usr/bin/env python3

import json
import glob

inputs = glob.glob("*.json")
for data_file in inputs:
    with open(data_file, 'r') as data_fd:
        data_json = json.load(data_fd)
    print(f"Mem alloc: {data_json['name']}")
    print(f"Version: {data_json['version']}")
    print(f"SLoC: {data_json['sloc']}")
    print(f"LoC change: {data_json['diff-loc']}")
    print(f"LoC percent: {data_json['diff-loc'] * 100.00 / data_json['sloc']}")

