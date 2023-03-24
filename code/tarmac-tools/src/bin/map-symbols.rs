// SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: MIT OR Apache-2.0

use clap::Parser;
use elf::section::SectionHeader;
use elf::segment::ProgramHeader;
use elf::ElfStream;
use itertools::Itertools as _;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::cell::RefCell;
use std::collections::{BTreeSet, HashMap};
use std::error::Error;
use std::fmt;
use std::fs;
use std::io;
use std::io::{BufRead as _, Read as _, Seek as _};
use std::path::{Path, PathBuf};
use std::rc::Rc;

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

    #[arg(short, long, help = "Verbose output (e.g. including address calculations)", action = clap::ArgAction::Count)]
    verbose: u8,

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

type MorelloElfFile = ElfStream<elf::endian::LittleEndian, fs::File>;

#[derive(Clone)]
struct NamedMorelloElfFile {
    path: PathBuf,
    elf: Rc<RefCell<MorelloElfFile>>,
}

impl PartialOrd for NamedMorelloElfFile {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        self.path.partial_cmp(&other.path)
    }
}
impl Ord for NamedMorelloElfFile {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        self.path.cmp(&other.path)
    }
}
impl PartialEq for NamedMorelloElfFile {
    fn eq(&self, other: &Self) -> bool {
        self.path == other.path
    }
}
impl Eq for NamedMorelloElfFile {}

impl fmt::Debug for NamedMorelloElfFile {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "NamedMorelloElfFile {{ path: {}, .. }}",
            self.path.display()
        )
    }
}

impl NamedMorelloElfFile {
    /// Load the specified ELF.
    ///
    /// It's not an error if the file couldn't be opened (including if it doesn't exist). This
    /// results in `Ok(None)`.
    ///
    /// It is an error if a file exists that cannot be loaded as an ELF.
    pub fn try_load(path: PathBuf) -> Result<Option<Self>, Box<dyn Error>> {
        if let Ok(file) = fs::File::open(&path) {
            let elf = Rc::new(RefCell::new(MorelloElfFile::open_stream(file)?));
            Ok(Some(Self { path, elf }))
        } else {
            Ok(None)
        }
    }
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

    #[serde(skip)]
    local_elf: Option<NamedMorelloElfFile>,
}

impl VmMapEntry {
    pub fn contains(&self, va: u64) -> bool {
        self.start <= va && va < self.end
    }

    pub fn find_local_elf<'a>(
        &mut self,
        elf_dirs: &'a [PathBuf],
        rootfs: &'a [PathBuf],
    ) -> Result<Option<&Path>, Box<dyn Error>> {
        if let Some(ref tgt_elf) = self.path {
            if let Some(basename) = tgt_elf.file_name() {
                for dir in elf_dirs.iter() {
                    let path = dir.join(basename);
                    if let Some(elf) = NamedMorelloElfFile::try_load(path)? {
                        self.local_elf = Some(elf);
                        return Ok(self.local_elf_path());
                    }
                }
            }
            for dir in rootfs.iter() {
                let path = dir.join(tgt_elf.strip_prefix("/")?);
                if let Some(elf) = NamedMorelloElfFile::try_load(path)? {
                    self.local_elf = Some(elf);
                    return Ok(self.local_elf_path());
                }
            }
        }
        return Ok(None);
    }

    pub fn tgt_elf_path(&self) -> Option<&Path> {
        self.path.as_ref().map(|path| path.as_path())
    }

    pub fn local_elf_path(&self) -> Option<&Path> {
        self.local_elf.as_ref().map(|elf| elf.path.as_path())
    }

    pub fn vm_addr_info(&self, vm_addr: u64) -> Result<VmAddrInfo<'_>, Box<dyn Error>> {
        assert!(self.contains(vm_addr));
        // ELF symbols are defined in terms of the ELF's idea of the virtual address. The actual
        // virtual address (vm_addr) typically differs, due to dynamic loading, so we have to do
        // some work to map it back to the ELF address.

        let map_offset = vm_addr - self.start;
        let file_offset = map_offset + self.offset;

        // Find the segment that refers to `file_offset`.
        let mut elf_vm_addr = None;
        let mut sec_info = None;
        let mut sym_info = None;
        if let Some(NamedMorelloElfFile { ref elf, .. }) = self.local_elf {
            for segment in elf.borrow().segments() {
                let ProgramHeader {
                    p_offset,
                    p_vaddr,
                    p_memsz,
                    ..
                } = *segment;
                if p_offset <= file_offset && file_offset < (p_offset + p_memsz) {
                    elf_vm_addr = Some(file_offset - p_offset + p_vaddr);
                    break;
                }
            }

            if let Some(elf_vm_addr) = elf_vm_addr {
                if let (sections, Some(strtab)) = elf.borrow_mut().section_headers_with_strtab()? {
                    for section in sections {
                        let SectionHeader {
                            sh_name,
                            sh_addr,
                            sh_size,
                            sh_type,
                            ..
                        } = *section;
                        if sh_type == elf::abi::SHT_PROGBITS
                            && sh_addr <= elf_vm_addr
                            && elf_vm_addr < (sh_addr + sh_size)
                        {
                            sec_info = Some(strtab.get(sh_name.try_into().unwrap())?.to_string());
                            break;
                        }
                    }
                }

                if let Some((symtab, strtab)) = elf.borrow_mut().symbol_table()? {
                    for sym in symtab.iter() {
                        if sym.st_name == 0 || sym.st_size == 0 || sym.is_undefined() {
                            continue;
                        }
                        let start = sym.st_value & !1; // Strip C64 bit.
                        let end = start + sym.st_size;
                        if start <= elf_vm_addr && elf_vm_addr < end {
                            sym_info = Some(SymbolicVmAddrInfo {
                                name: strtab.get(sym.st_name.try_into().unwrap())?.to_string(),
                                sym_offset: elf_vm_addr - start,
                            });
                            break;
                        }
                    }
                }
            }
        }

        Ok(VmAddrInfo {
            entry: self,
            elf_vm_addr,
            sec_info,
            sym_info,
        })
    }
}

struct SymbolicVmAddrInfo {
    name: String,
    sym_offset: u64,
}

impl fmt::Display for SymbolicVmAddrInfo {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}{:+#x}", self.name, self.sym_offset)
    }
}

struct VmAddrInfo<'a> {
    entry: &'a VmMapEntry,
    elf_vm_addr: Option<u64>,
    sec_info: Option<String>,
    sym_info: Option<SymbolicVmAddrInfo>,
}

impl<'a> fmt::Display for VmAddrInfo<'a> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if let Some(path) = self.entry.local_elf_path() {
            if f.alternate() {
                write!(f, "{}", path.display())?;
            } else {
                let simple_name = path
                    .file_name()
                    .unwrap_or(path.as_os_str())
                    .to_string_lossy();
                write!(f, "{simple_name}")?;
            }
        } else {
            write!(f, "(no local ELF)")?;
        }
        if let Some(elf_vm_addr) = self.elf_vm_addr {
            write!(f, ":{elf_vm_addr:#x}")?;
        }
        match self.sym_info {
            None => write!(f, ": (unknown)")?,
            Some(ref sym_info) => write!(f, ": {sym_info}")?,
        };
        if let Some(sec_info) = self.sec_info.as_deref() {
            if sec_info != ".text" {
                write!(f, " in {sec_info}")?;
            }
        }
        Ok(())
    }
}

struct VmMap {
    map: Vec<VmMapEntry>,
}

impl VmMap {
    fn from_csv(source: &str) -> Result<Self, Box<dyn Error>> {
        let mut reader = csv::Reader::from_reader(source.as_bytes());
        let map = reader.deserialize().try_collect()?;
        // TODO: Check that entries don't overlap.
        // TODO: Discard entries that aren't executable.
        Ok(VmMap { map })
    }

    pub fn from_stdout(file: &str) -> Result<Self, Box<dyn Error>> {
        let text = fs::read_to_string(file)?;
        // If the file contains a delimited region, use that. Otherwise, use the whole file.
        let mut lines = text.lines();
        if let Some(begin) = lines.position(|line| line.trim() == "---- BEGIN VM MAP ----") {
            if let Some(len) = lines.position(|line| line.trim() == "---- END VM MAP ----") {
                Self::from_csv(&text.lines().skip(begin + 1).take(len).join("\n"))
            } else {
                Err("'BEGIN VM MAP' marker found with no matching 'END VM MAP'".into())
            }
        } else {
            Self::from_csv(&text)
        }
    }

    pub fn find_local_elfs<'a>(
        &mut self,
        elf_dirs: &'a [PathBuf],
        rootfs: &'a [PathBuf],
    ) -> Result<(), Box<dyn Error>> {
        // TODO: We already wrap the ElfStream in an Rc, and the same ELF tends to be mapped
        // multiple times, so it might make sense to coalesce them.
        for entry in self.map.iter_mut() {
            entry.find_local_elf(elf_dirs, rootfs)?;
        }
        Ok(())
    }

    pub fn iter(&self) -> impl Iterator<Item = &VmMapEntry> {
        self.map.iter()
    }

    pub fn entry_for(&self, vm_addr: u64) -> Option<&VmMapEntry> {
        self.iter().find(|entry| entry.contains(vm_addr))
    }
}

#[derive(Default, Debug, Clone)]
struct FileInsnCount {
    by_symbol: HashMap<Option<String>, u64>,
}

impl FileInsnCount {
    pub fn total(&self) -> u64 {
        self.by_symbol.values().sum()
    }

    pub fn add(&mut self, symbol: Option<String>) {
        *self.by_symbol.entry(symbol).or_default() += 1;
    }

    pub fn by_symbol(&self) -> impl Iterator<Item = (&Option<String>, &u64)> {
        self.by_symbol.iter()
    }
}

#[derive(Default, Debug, Clone)]
struct InsnCount<'a> {
    by_file: HashMap<Option<&'a Path>, FileInsnCount>,

    // We query this often, so cache it.
    total: u64,
}

impl<'a> InsnCount<'a> {
    pub fn total(&self) -> u64 {
        self.total
    }

    pub fn add(&mut self, file: Option<&'a Path>, symbol: Option<String>) {
        self.total += 1;
        self.by_file.entry(file).or_default().add(symbol);
    }

    pub fn by_file(&self) -> impl Iterator<Item = (&Option<&'a Path>, &FileInsnCount)> {
        self.by_file.iter()
    }

    pub fn report(&self) {
        println!("----------------");
        for (path, file_insn_count) in self.by_file().sorted_by_key(|(_, c)| !c.total()) {
            println!(
                "{path}: {total}",
                path = path.unwrap_or(Path::new("unknown file")).display(),
                total = file_insn_count.total()
            );
            for (name, symbol_insn_count) in file_insn_count.by_symbol().sorted_by_key(|(_, c)| !*c)
            {
                println!(
                    "  {name}: {symbol_insn_count}",
                    name = name.as_deref().unwrap_or("unknown symbol")
                );
            }
        }
        println!("Total: {total}", total = self.total());
    }
}

fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let mut vmmap = VmMap::from_stdout(&args.vmmap)?;
    vmmap.find_local_elfs(&args.elf_dir, &args.rootfs)?;

    // BTreeSet naturally sorts.
    let mut unique_elfs: BTreeSet<&NamedMorelloElfFile> = BTreeSet::new();

    if args.verbose >= 1 {
        for entry in vmmap.iter() {
            let VmMapEntry {
                start,
                end,
                offset,
                path,
                local_elf,
                ..
            } = entry;
            if let Some(path) = path {
                print!("[{start:#x},{end:#x})  {}  +{offset:#x}", path.display());
                if let Some(local_elf) = local_elf {
                    println!("  (represented by {})", local_elf.path.display());
                    // We might load an ELF multiple times, but only want to print it (with -v) once,
                    // so use a map to avoid duplication.
                    unique_elfs.insert(&local_elf);
                } else {
                    println!("  (no local ELF found)");
                }
            }
        }

        println!("Loaded ELFs for analysis:");
        for local_elf in unique_elfs.iter() {
            println!("  {}", local_elf.path.display());
            println!("    Loadable segments:");
            for segment in local_elf.elf.borrow().segments() {
                let elf::segment::ProgramHeader {
                    p_type,
                    p_offset,
                    p_vaddr,
                    p_filesz,
                    p_memsz,
                    p_flags,
                    ..
                } = segment;
                if *p_type == elf::abi::PT_LOAD {
                    print!("    ");
                    print!("  offset:{p_offset:#x}");
                    print!("  va:{p_vaddr:#x}");
                    print!("  file_sz:{p_filesz:#x}");
                    print!("  mem_sz:{p_memsz:#x}");
                    if (*p_flags & elf::abi::PF_X) != 0 {
                        print!("  (executable)");
                    }
                    println!();
                }
            }
            if let Some((symtab, strtab)) = local_elf.elf.borrow_mut().symbol_table()? {
                if args.verbose >= 2 {
                    println!("    Symbols with non-zero size:");
                    for sym in symtab.iter().sorted_by_key(|s| s.st_value) {
                        if sym.st_name == 0 || sym.st_size == 0 || sym.is_undefined() {
                            continue;
                        }
                        let name = strtab.get(sym.st_name.try_into().unwrap())?;
                        let isa = match sym.st_value & 1 {
                            1 => "C64",
                            _ => "A64/data",
                        };
                        let start = sym.st_value & !1;
                        let end = start + sym.st_size;
                        println!("      [{start:#x},{end:#x}) {name} ({isa})");
                    }
                }
            } else {
                println!("  (no symbol table)\n");
            }
        }
    }

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

    let mut insn_count = InsnCount::default();

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
            let pcc = caps.name("pcc").unwrap().as_str();
            let insn = caps.name("insn").unwrap().as_str();
            let asm = caps.name("asm").unwrap().as_str();

            let pcc_caps = cap_re.captures(pcc).unwrap();
            let pcc_addr = pcc_caps.name("low64").unwrap().as_str();
            let pcc_addr = u64::from_str_radix(pcc_addr, 16).unwrap();

            if args.annotate_trace {
                print!("{pcc}  {insn}  {asm:32}");
                // We'll append a comment below.
            }
            match vmmap.entry_for(pcc_addr) {
                Some(entry) => {
                    let info = entry.vm_addr_info(pcc_addr)?;
                    if args.annotate_trace {
                        println!("  # {info}");
                    }
                    let file = entry.tgt_elf_path();
                    let sym = info
                        .sym_info
                        .map(|sym| sym.name.clone())
                        .or_else(|| info.sec_info.map(|sec| format!("unknown ({sec})")));
                    insn_count.add(file, sym);
                }
                None => {
                    if args.annotate_trace {
                        println!("");
                    }
                    insn_count.add(None, None);
                }
            }
            if !args.annotate_trace && insn_count.total() % (1024 * 1024) == 0 {
                insn_count.report();
            }
        }
    }
    insn_count.report();
    Ok(())
}
