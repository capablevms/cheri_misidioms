// SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: MIT OR Apache-2.0

use clap::Parser;
use itertools::Itertools as _;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::error::Error;
use std::fs;
use std::io;
use std::io::BufRead as _;

#[derive(Clone, Debug, Parser)]
#[command()]
struct Args {
    #[arg(help = "Generated tarmac trace from Morello FVP model")]
    tarmac: String,

    #[arg(help = "CSV-formatted VM map, optionally embedded in a stdout recording")]
    vmmap: String,

    #[arg(short, long, help = "Show per-instruction analysis")]
    annotate_trace: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct VmMapEntry {
    #[serde(rename = "Start")]
    start: u64, // Inclusive
    #[serde(rename = "End")]
    end: u64, // Exclusive
    #[serde(rename = "Permissions")]
    perms: String,
    #[serde(rename = "Type")]
    map_type: String,
    #[serde(rename = "Offset")]
    offset: u64,
    #[serde(rename = "Path")]
    path: Option<String>,
}

impl VmMapEntry {
    pub fn contains(&self, va: u64) -> bool {
        self.start <= va && va < self.end
    }
}

#[derive(Clone, Debug)]
struct VmMap {
    map: Vec<VmMapEntry>,
}

impl VmMap {
    pub fn file_for_insn(&self, pc: u64) -> Option<&str> {
        self.map
            .iter()
            .find(|entry| entry.contains(pc) && entry.path.is_some())
            .map(|entry| entry.path.as_deref().unwrap())
    }
}

fn read_vmmap_csv(source: &str) -> Result<VmMap, Box<dyn Error>> {
    let mut reader = csv::Reader::from_reader(source.as_bytes());
    let map = reader.deserialize().try_collect()?;
    Ok(VmMap { map })
}

fn read_vmmap(file: &str) -> Result<VmMap, Box<dyn Error>> {
    let text = fs::read_to_string(file)?;
    // If the file contains a delimited region, use that. Otherwise, use the whole file.
    let mut lines = text.lines();
    if let Some(begin) = lines.position(|line| line.trim() == "---- BEGIN VM MAP ----") {
        if let Some(len) = lines.position(|line| line.trim() == "---- END VM MAP ----") {
            read_vmmap_csv(&text.lines().skip(begin + 1).take(len).join("\n"))
        } else {
            Err("'BEGIN VM MAP' marker found with no matching 'END VM MAP'".into())
        }
    } else {
        read_vmmap_csv(&text)
    }
}

fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let vmmap = read_vmmap(&args.vmmap)?;

    // Reference:
    // https://developer.arm.com/documentation/102225/0200/Reference-information/Morello-specific-changes-to-tarmac-trace
    let it_re = Regex::new(
        r"(?x)
        ^\d+\s+                                         # Timestamp
        (?:ps|clk)\s+                                   # Timestamp units
        \S+\s+                                          # CPU name
        IT\s+                                           # Instruction taken
        \(\d+\)\s+                                      # Tick count
        \((?P<pcc>[01]\|[[:xdigit:]]+\|[[:xdigit:]]+)\) # PCC (including virtual address)
        :[[:xdigit:]]+_NS\s+                            # Physical address (non-secure)
        (?P<insn>[[:xdigit:]]{8})\s+                    # Instruction
        [OC]\s+                                         # ISA (A64 or C64)
        EL0t_n\s+                                       # EL0, non-secure only
        :\s+
        (?P<asm>.*)                                     # Disassembly
    ",
    )
    .unwrap();

    let cap_re =
        Regex::new(r"^(?P<tag>[01])\|(?P<high64>[[:xdigit:]]+)\|(?P<low64>[[:xdigit:]]+)$")
            .unwrap();

    let mut insn_count: u64 = 0;
    let mut insn_count_by_file: HashMap<&str, u64> = HashMap::new();

    let tarmac = fs::File::open(args.tarmac)?;
    for line in io::BufReader::new(tarmac).lines() {
        let line = line?;
        if let Some(caps) = it_re.captures(&line) {
            let pcc = caps.name("pcc").unwrap().as_str();
            let insn = caps.name("insn").unwrap().as_str();
            let asm = caps.name("asm").unwrap().as_str();

            let pcc_caps = cap_re.captures(pcc).unwrap();
            let pcc_addr = pcc_caps.name("low64").unwrap().as_str();
            let pcc_addr = u64::from_str_radix(pcc_addr, 16).unwrap();

            // TODO: Extend this to show the symbol and offset.
            let file = vmmap.file_for_insn(pcc_addr).unwrap_or("Unknown file");
            if args.annotate_trace {
                println!("{pcc} {insn} : {asm:32} // {file}");
            }

            insn_count += 1;
            *insn_count_by_file.entry(file).or_insert(0) += 1;
        }
    }
    for (file, count) in insn_count_by_file.iter().sorted() {
        println!("{file}: {count} instructions");
    }
    println!("Counted {insn_count} EL0 instructions in total.");
    Ok(())
}
