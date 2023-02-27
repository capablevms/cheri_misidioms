// SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: MIT OR Apache-2.0

use clap::Parser;
use elf::ElfStream;
use itertools::Itertools as _;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::error::Error;
use std::fs;
use std::io;
use std::io::{BufRead as _, Read as _, Seek as _};
use std::path::{Path, PathBuf};

#[derive(Clone, Debug, Parser)]
#[command()]
struct Args {
    #[arg(help = "Generated tarmac trace from Morello FVP model")]
    tarmac: String,

    #[arg(help = "CSV-formatted VM map, optionally embedded in a stdout recording")]
    vmmap: String,

    #[arg(
        long,
        help = "Start reading tarmac from (and including) the TARGET_START'th byte"
    )]
    tarmac_start: Option<u64>,

    #[arg(
        long,
        help = "Stop reading tarmac at (and not including) the TARGET_END'th byte"
    )]
    tarmac_end: Option<u64>,

    #[arg(short, long, help = "Show per-instruction analysis")]
    annotate_trace: bool,

    #[arg(
        long,
        help = "Local directories to search for ELF files",
        long_help = "
            Directories containing local copies of ELF files named in the VM map. All directory
            components from the VM map are ignored. This is most useful for locating the executable
            and non-system libraries.

            --elf-dir is searched before --rootfs, but otherwise in the order specified.
          "
    )]
    elf_dir: Vec<PathBuf>,

    #[arg(
        long,
        help = "Local directories reflecting the rootfs",
        long_help = "
            A local copy of the rootfs, used to find ELF files. May be specified multiple times, to
            support overlays (like cheribuild's --disk-image/extra-files).

            --elf-dir is searched before --rootfs, but otherwise in the order specified.
          "
    )]
    rootfs: Vec<PathBuf>,
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
    path: Option<PathBuf>,
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
    pub fn file_for_insn(&self, pc: u64) -> Option<&Path> {
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

type MorelloElfFile = ElfStream<elf::endian::LittleEndian, fs::File>;

fn try_load_elf(name: &Path) -> Result<Option<MorelloElfFile>, Box<dyn Error>> {
    if let Ok(file) = fs::File::open(name) {
        return Ok(Some(MorelloElfFile::open_stream(file)?));
    }
    // Failure to open the file is not an error.
    Ok(None)
}

fn find_elf(name: &Path, args: &Args) -> Result<Option<(PathBuf, MorelloElfFile)>, Box<dyn Error>> {
    if let Some(file_name) = name.file_name() {
        for dir in args.elf_dir.iter() {
            let local = dir.join(file_name);
            if let Some(elf) = try_load_elf(&local)? {
                println!(
                    "  Using '{}' to represent '{}'.",
                    local.display(),
                    name.display()
                );
                return Ok(Some((local, elf)));
            }
        }
    }

    for dir in args.rootfs.iter() {
        let local = dir.join(name.strip_prefix("/")?);
        if let Some(elf) = try_load_elf(&local)? {
            println!(
                "  Using '{}' to represent '{}'.",
                local.display(),
                name.display()
            );
            return Ok(Some((local, elf)));
        }
    }

    println!("  No local ELF found to represent '{}'.", name.display());
    Ok(None)
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
    let mut insn_count_by_file: HashMap<&Path, u64> = HashMap::new();

    let mut elf_map: HashMap<&Path, Option<(PathBuf, MorelloElfFile)>> = HashMap::new();

    let tarmac_start = args.tarmac_start.unwrap_or(0);
    let tarmac_end = args.tarmac_end.unwrap_or(u64::MAX);
    if tarmac_end <= tarmac_start {
        return Err(format!(
            "--tarmac-end ({tarmac_end}) <= --tarmac-start ({tarmac_start}); nothing to analyse"
        )
        .into());
    }
    let tarmac_length = tarmac_end - tarmac_start;

    let mut tarmac = fs::File::open(&args.tarmac)?;
    tarmac.seek(std::io::SeekFrom::Start(tarmac_start))?;
    let tarmac = tarmac.take(tarmac_length);
    for line in io::BufReader::new(tarmac).lines() {
        let line = line?;
        if let Some(caps) = it_re.captures(&line) {
            insn_count += 1;

            let pcc = caps.name("pcc").unwrap().as_str();
            let insn = caps.name("insn").unwrap().as_str();
            let asm = caps.name("asm").unwrap().as_str();

            let pcc_caps = cap_re.captures(pcc).unwrap();
            let pcc_addr = pcc_caps.name("low64").unwrap().as_str();
            let pcc_addr = u64::from_str_radix(pcc_addr, 16).unwrap();

            // TODO: Extend this to show the symbol and offset.
            let comment;
            if let Some(tgt_elf) = vmmap.file_for_insn(pcc_addr) {
                *insn_count_by_file.entry(tgt_elf).or_insert(0) += 1;

                let local = match elf_map.get(tgt_elf) {
                    Some(local) => local,
                    None => {
                        let local = find_elf(tgt_elf, &args)?;
                        elf_map.entry(tgt_elf).or_insert(local)
                    }
                };

                if let Some(local_elf) = local {
                    comment = format!("{} ({})", tgt_elf.display(), local_elf.0.display());
                } else {
                    comment = format!("{}", tgt_elf.display());
                }
            } else {
                comment = "Unknown file".to_string();
            }
            if args.annotate_trace {
                println!("{pcc} {insn} : {asm:32} // {comment}");
            }
        }
    }
    for (file, count) in insn_count_by_file.iter().sorted() {
        println!("{file}: {count} instructions", file = file.display());
    }
    println!("Counted {insn_count} EL0 instructions in total.");
    Ok(())
}
