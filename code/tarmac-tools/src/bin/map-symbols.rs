// SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: MIT OR Apache-2.0

use clap::Parser;
use elf::section::SectionHeader;
use elf::symbol::Symbol;
use elf::ElfStream;
use itertools::Itertools as _;
use lazy_static::lazy_static;
use regex::Regex;
use serde::Deserialize;
use std::borrow::Cow;
use std::cell::RefCell;
use std::cmp::Ordering;
use std::collections::{BTreeMap, HashMap};
use std::error::Error;
use std::ffi::OsStr;
use std::fmt;
use std::fs;
use std::io;
use std::io::{BufRead as _, Read as _, Seek as _};
use std::ops::RangeInclusive;
use std::path::{Path, PathBuf};
use std::rc::Rc;
use std::str::FromStr;

#[derive(Clone, Debug, Parser)]
#[command()]
struct Cli {
    #[arg(
        help = "CSV-formatted VM map, optionally embedded in other logs",
        long_help = "
              CSV-formatted VM map, optionally embedded in other logs. If the embedded VMMAP is
              followed by a line like this:

                  Generated 1234 bytes in /absolute/path/to/foo.tarmac [42,4200)...

              ... then suitable defaults will be derived for other arguments, enabling simple,
              single-argument invocation. Explicit arguments always override values inferred in
              this way.
            "
    )]
    vmmap: PathBuf,

    #[arg(
        help = "Generated tarmac trace from Morello FVP model",
        long_help = "
              Generated tarmac trace from Morello FVP model. This can be omitted if it can be
              derived from VMMAP. Otherwise, it is required.
            "
    )]
    tarmac: Option<PathBuf>,

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

            If nothing is specified explicitly, the directory containing VMMAP is used.

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

            If nothing is specified explicitly, ~/cheri/output/rootfs-morello-purecap is used.

            --elf-dir is searched before --rootfs, but otherwise in the order specified.
          "
    )]
    rootfs: Vec<PathBuf>,
}

type MorelloElfFile = ElfStream<elf::endian::LittleEndian, fs::File>;
type Result<T> = core::result::Result<T, Box<dyn Error>>;

pub trait AddrRange {
    fn display(&self) -> String;
    fn overlaps(&self, other: &Self) -> bool;
}

impl AddrRange for RangeInclusive<u64> {
    fn display(&self) -> String {
        let start = *self.start();
        let end = u128::from(*self.end()) + 1;
        format!("[{start:#x},{end:#x})")
    }

    fn overlaps(&self, other: &Self) -> bool {
        self.start() <= other.end() && self.end() >= other.start()
    }
}

/// Mappings are ordered if they are equal or non-overlapping.
fn cmp_mappings(a: &RangeInclusive<u64>, b: &RangeInclusive<u64>) -> Option<Ordering> {
    if a == b {
        Some(Ordering::Equal)
    } else if a.overlaps(b) {
        None
    } else {
        Some(a.start().cmp(b.start()))
    }
}

fn cmp_mappings_with_eq_check(
    a: &RangeInclusive<u64>,
    b: &RangeInclusive<u64>,
    eq: impl FnOnce() -> bool,
) -> Option<Ordering> {
    match cmp_mappings(a, b) {
        Some(Ordering::Equal) => eq().then_some(Ordering::Equal),
        ord => ord,
    }
}

#[derive(Clone, Debug)]
struct VmMapInferredTarmac {
    start: u64,
    end: u64,
    file: PathBuf,
}

/// A map of various properties of all virtual memory.
#[derive(Clone, Debug)]
struct VmMap {
    elfs: BTreeMap<PathBuf, Option<Rc<LocalMorelloElfFile>>>,
    // Non-overlapping, sorted by address, so slice::binary_search* functions can be used.
    mappings: Vec<VmMapping>,

    // Inferred arguments.
    tarmac: Option<VmMapInferredTarmac>,
}

impl VmMap {
    fn from_csv(source: &str, elf_dirs: &[PathBuf], rootfs: &[PathBuf]) -> Result<Self> {
        let mut reader = csv::Reader::from_reader(source.as_bytes());
        let mut elfs = Default::default();
        let mut mappings: Vec<VmMapping> = reader
            .deserialize::<DumpedVmMapEntry>()
            .map(|maybe_entry| maybe_entry?.into_vm_mapping(&mut elfs, elf_dirs, rootfs))
            .try_collect()?;
        mappings.sort_by_key(|mapping| *mapping.va.start());
        if let Some((a, b)) = mappings
            .iter()
            .tuple_windows()
            .find(|(a, b)| a.va.overlaps(&b.va))
        {
            let e = format!(
                "Mappings {a} and {b} overlap.",
                a = a.va.display(),
                b = b.va.display()
            );
            Err(e.into())
        } else {
            Ok(VmMap {
                elfs,
                mappings,
                tarmac: None,
            })
        }
    }

    pub fn from_stdout(file: &Path, elf_dirs: &[PathBuf], rootfs: &[PathBuf]) -> Result<Self> {
        let text = fs::read_to_string(file)?;
        // If the file contains a delimited region, use that. Otherwise, use the whole file.
        let mut lines = text.lines();
        if let Some(begin) = lines.position(|line| line.trim() == "---- BEGIN VM MAP ----") {
            if let Some(len) = lines.position(|line| line.trim() == "---- END VM MAP ----") {
                lazy_static! {
                    static ref RE: Regex =
                        Regex::new(r#"^Generated \d+ bytes in (.*) \[(\d+),(\d+)\)...$"#).unwrap();
                }
                Self::from_csv(
                    &text.lines().skip(begin + 1).take(len).join("\n"),
                    elf_dirs,
                    rootfs,
                )
                .map(|from_csv| Self {
                    tarmac: lines.find_map(|line| RE.captures(line)).map(|caps| {
                        VmMapInferredTarmac {
                            start: caps.get(2).unwrap().as_str().parse().unwrap(),
                            end: caps.get(3).unwrap().as_str().parse().unwrap(),
                            file: caps.get(1).unwrap().as_str().into(),
                        }
                    }),
                    ..from_csv
                })
            } else {
                Err("'BEGIN VM MAP' marker found with no matching 'END VM MAP'".into())
            }
        } else {
            Self::from_csv(&text, elf_dirs, rootfs)
        }
    }

    pub fn iter(&self) -> impl Iterator<Item = &VmMapping> {
        self.mappings.iter()
    }

    pub fn addr_info(&self, va: u64) -> Result<Option<VmAddrInfo<'_>>> {
        self.mappings
            .iter()
            .find(|mapping| mapping.va.contains(&va))
            .map(|mapping| mapping.addr_info(va))
            .transpose()
    }
}

/// A single, contiguous virtual memory mapping, typically from part of an ELF file to part of the
/// virtual memory space.
#[derive(Clone, Debug)]
struct VmMapping {
    va: RangeInclusive<u64>,
    offset_into_file: u64,
    target_path: Option<PathBuf>,
    perms: VmPerms,
    // Non-overlapping, sorted by address, so slice::binary_search* fucntions can be used.
    sections: Vec<VmSectionMapping>,
}

impl VmMapping {
    pub fn target_path(&self) -> Option<Cow<'_, str>> {
        self.target_path.as_deref().map(Path::to_string_lossy)
    }

    pub fn simple_path(&self) -> Option<Cow<'_, str>> {
        self.target_path
            .as_deref()
            .and_then(Path::file_name)
            .map(OsStr::to_string_lossy)
    }

    fn addr_info(&self, va: u64) -> Result<VmAddrInfo<'_>> {
        // The caller should check this first.
        debug_assert!(self.va.contains(&va));

        // We call this for every traced instruction, so it needs to be fast.
        // We already did all the VA calculations up front, so we just need to look it up.

        let search = |range: &RangeInclusive<u64>| -> Ordering {
            if *range.end() < va {
                Ordering::Less
            } else if *range.start() > va {
                Ordering::Greater
            } else {
                Ordering::Equal
            }
        };

        let (section, symbol) = match self.sections.binary_search_by(|sec| search(&sec.va)) {
            Err(_) => (None, None),
            Ok(idx) => {
                let sec = &self.sections[idx];
                match sec.symbols.binary_search_by(|sym| search(&sym.va)) {
                    Err(_) => (Some(sec), None),
                    Ok(idx) => (Some(sec), sec.symbols.get(idx)),
                }
            }
        };

        Ok(VmAddrInfo {
            va,
            mapping: self,
            section,
            symbol,
        })
    }

    pub fn sections(&self) -> &[VmSectionMapping] {
        &self.sections
    }
}

#[derive(Clone, Copy, Debug)]
pub struct VmAddrInfo<'m> {
    // We build one of these for every queried address, so keep it fast to construct.
    va: u64,
    mapping: &'m VmMapping,
    section: Option<&'m VmSectionMapping>,
    symbol: Option<&'m VmSymbolMapping>,
}

impl<'m> fmt::Display for VmAddrInfo<'m> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self.mapping.simple_path() {
            Some(path) => write!(f, "{path}")?,
            None => write!(f, "[anonymous]")?,
        };
        // TODO: Can we retrieve this?
        //if let Some(elf_addr) = self.elf_addr {
        //    write!(f, ":{elf_addr:#x}")?;
        //}
        match self.symbol {
            Some(VmSymbolMapping { va, name, .. }) => {
                write!(f, ": {name}+{:#x}", self.va - va.start())?
            }
            None => write!(f, ": unknown symbol")?,
        };
        match self.section {
            Some(VmSectionMapping { va, name, .. }) => {
                if name != ".text" {
                    write!(f, " at {name}+{:#x}", self.va - va.start())?
                }
            }
            None => write!(f, " in unknown section")?,
        };
        Ok(())
    }
}

#[derive(Clone, Copy, Debug)]
pub struct VmPerms {
    pub read: bool,
    pub write: bool,
    pub execute: bool,
    pub read_cap: bool,
    pub write_cap: bool,
}

impl FromStr for VmPerms {
    type Err = Box<dyn Error>;
    fn from_str(s: &str) -> Result<Self> {
        let perm = |c: Option<char>, t: char| -> Result<bool> {
            match c {
                Some('-') => Ok(false),
                Some(c) if c == t => Ok(true),
                Some(_) => Err("Unrecognised permission: {c} in '{s}'.".into()),
                None => Err("Expected another char ('-', '{t}') in '{s}'.".into()),
            }
        };
        let mut chars = s.chars();
        let perms = Self {
            read: perm(chars.next(), 'r')?,
            write: perm(chars.next(), 'w')?,
            execute: perm(chars.next(), 'x')?,
            read_cap: perm(chars.next(), 'R')?,
            write_cap: perm(chars.next(), 'W')?,
        };
        match chars.next() {
            None => Ok(perms),
            Some(_) => Err("Too many permission chars: '{s}'.".into()),
        }
    }
}

impl fmt::Display for VmPerms {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "{}{}{}{}{}",
            if self.read { 'r' } else { '-' },
            if self.write { 'w' } else { '-' },
            if self.execute { 'x' } else { '-' },
            if self.read_cap { 'R' } else { '-' },
            if self.write_cap { 'W' } else { '-' },
        )
    }
}

/// A single, contigous section in virtual memory.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
struct VmSectionMapping {
    va: RangeInclusive<u64>,
    name: String,
    // Non-overlapping, sorted by address, so slice::binary_search* fucntions can be used.
    symbols: Vec<VmSymbolMapping>,
}

impl VmSectionMapping {
    pub fn symbols(&self) -> &[VmSymbolMapping] {
        &self.symbols
    }
}

impl PartialOrd for VmSectionMapping {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        cmp_mappings_with_eq_check(&self.va, &other.va, || self.name == other.name)
    }
}

/// A single symbol (with non-zero size) in virtual memory.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
struct VmSymbolMapping {
    va: RangeInclusive<u64>,
    name: String,
    isa: Isa,
}

impl PartialOrd for VmSymbolMapping {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        cmp_mappings_with_eq_check(&self.va, &other.va, || self.name == other.name)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
enum Isa {
    A64,
    C64,
}

impl fmt::Display for Isa {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::A64 => write!(f, "A64"),
            Self::C64 => write!(f, "C64"),
        }
    }
}

/// A local ELF file that we can inspect, assuming that it is the same as the one that ran on the
/// target.
struct LocalMorelloElfFile {
    path: PathBuf,
    elf: RefCell<MorelloElfFile>,
}

impl fmt::Debug for LocalMorelloElfFile {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "LocalMorelloElfFile {{ path: {}, .. }}",
            self.path.display()
        )
    }
}

impl LocalMorelloElfFile {
    /// Load the specified ELF.
    ///
    /// It's not an error if the file couldn't be opened (including if it doesn't exist). This
    /// results in `Ok(None)`.
    ///
    /// It is an error if a file exists that cannot be loaded as an ELF.
    pub fn try_load(path: PathBuf) -> Result<Option<Self>> {
        if let Ok(file) = fs::File::open(&path) {
            let elf = RefCell::new(MorelloElfFile::open_stream(file)?);
            Ok(Some(Self { path, elf }))
        } else {
            Ok(None)
        }
    }
}

#[derive(Clone, Debug, Deserialize)]
struct DumpedVmMapEntry {
    #[serde(rename = "Start")]
    start: u64, // Inclusive
    #[serde(rename = "End")]
    end: u64, // Exclusive
    #[serde(rename = "Permissions")]
    perms: String,
    // #[serde(rename = "Type")]
    // map_type: String,
    #[serde(rename = "Offset")]
    offset: u64,
    #[serde(rename = "Path")]
    path: Option<PathBuf>,
}

impl DumpedVmMapEntry {
    fn into_vm_mapping(
        self,
        elfs: &mut BTreeMap<PathBuf, Option<Rc<LocalMorelloElfFile>>>,
        elf_dirs: &[PathBuf],
        rootfs: &[PathBuf],
    ) -> Result<VmMapping> {
        assert!(
            self.end > self.start,
            "Empty VM mapping: {}..{}",
            self.start,
            self.end
        );
        let target_path = self.path;
        let local_elf = match target_path.as_deref() {
            None => None,
            Some(target_path) => {
                if let Some(local) = elfs.get(target_path) {
                    local.as_ref().map(Rc::clone)
                } else {
                    let local = Self::find_and_load_local_elf(target_path, elf_dirs, rootfs)?;
                    elfs.insert(target_path.to_path_buf(), local.as_ref().map(Rc::clone));
                    local
                }
            }
        };
        let va = self.start..=(self.end - 1);
        let file_range = self.offset..=(self.offset + self.end + 1 - self.start);
        // Read section and symbol data from the ELF up front.
        let mut sections = Vec::new();
        let mut section_map = Vec::new();
        if let Some(ref local_elf) = local_elf {
            if let (headers, Some(strtab)) =
                local_elf.elf.borrow_mut().section_headers_with_strtab()?
            {
                for header in headers {
                    let SectionHeader {
                        sh_name,
                        sh_addr,
                        sh_offset,
                        sh_size,
                        sh_flags,
                        ..
                    } = *header;
                    let overlaps = *file_range.start() < (sh_offset + sh_size)
                        && *file_range.end() >= sh_offset;
                    // Filter out non-page-aligned collateral.
                    let has_instrs = (sh_flags & u64::from(elf::abi::SHF_EXECINSTR)) != 0;
                    if overlaps && has_instrs {
                        let sec_va_start = va.start() + sh_offset - *file_range.start();
                        let sec_va_end = sec_va_start + sh_size - 1;
                        section_map.push(Some((sections.len(), sh_addr, sec_va_start)));
                        sections.push(VmSectionMapping {
                            va: sec_va_start..=sec_va_end,
                            name: strtab.get(sh_name.try_into().unwrap())?.to_string(),
                            symbols: Vec::new(),
                        });
                    } else {
                        section_map.push(None);
                    }
                }
            }

            if let Some((symtab, strtab)) = local_elf.elf.borrow_mut().symbol_table()? {
                for symbol in symtab.iter() {
                    let Symbol {
                        st_name,

                        st_value,
                        st_size,
                        st_shndx,
                        ..
                    } = symbol;
                    if st_name == 0 || st_size == 0 || symbol.is_undefined() {
                        continue;
                    }
                    let st_shndx = usize::from(st_shndx);
                    if let Some((mapped_section_index, sh_addr, sec_va_start)) =
                        section_map[st_shndx]
                    {
                        let isa = match st_value & 1 {
                            0 => Isa::A64,
                            _ => Isa::C64,
                        };
                        let value = st_value & !1; // Strip C64 bit.
                        let sym_va_start = sec_va_start + value - sh_addr;
                        let sym_va_end = sym_va_start + st_size - 1;
                        sections[mapped_section_index]
                            .symbols
                            .push(VmSymbolMapping {
                                va: sym_va_start..=sym_va_end,
                                name: strtab.get(st_name.try_into().unwrap())?.to_string(),
                                isa,
                            });
                    }
                }
            }
        }

        // Ensure that sections are sorted and non-overlapping.
        sections.sort_by_key(|sec| *sec.va.start());
        assert!(!sections
            .iter()
            .tuple_windows()
            .any(|(a, b)| a.va.overlaps(&b.va)));
        for section in sections.iter_mut() {
            let mut symbols = std::mem::take(&mut section.symbols);
            // Ensure that symbols are sorted and non-overlapping.
            symbols.sort_by_key(|sym| *sym.va.start());
            // Symbols are often aliased.
            section.symbols = symbols
                .into_iter()
                .coalesce(|a, b| {
                    if a.va == b.va {
                        if a.name.len() <= b.name.len() {
                            Ok(a)
                        } else {
                            Ok(b)
                        }
                    } else if a.va.overlaps(&b.va) {
                        // TODO: What else can we do here?
                        panic!(
                            "{a} {ava} overlaps {b} {bva}",
                            a = &a.name,
                            ava = a.va.display(),
                            b = &b.name,
                            bva = b.va.display()
                        );
                    } else {
                        Err((a, b))
                    }
                })
                .collect();
            assert!(!section
                .symbols
                .iter()
                .tuple_windows()
                .any(|(a, b)| a.va.overlaps(&b.va)));
        }

        Ok(VmMapping {
            va,
            offset_into_file: self.offset,
            target_path,
            perms: VmPerms::from_str(&self.perms)?,
            sections,
        })
    }

    fn find_and_load_local_elf(
        target_path: &Path,
        elf_dirs: &[PathBuf],
        rootfs: &[PathBuf],
    ) -> Result<Option<Rc<LocalMorelloElfFile>>> {
        if let Some(basename) = target_path.file_name() {
            for dir in elf_dirs.iter() {
                let path = dir.join(basename);
                if let Some(local_elf) = LocalMorelloElfFile::try_load(path)? {
                    return Ok(Some(Rc::new(local_elf)));
                }
            }
        }
        if let Ok(suffix) = target_path.strip_prefix("/") {
            for dir in rootfs.iter() {
                if let Some(local_elf) = LocalMorelloElfFile::try_load(dir.join(suffix))? {
                    return Ok(Some(Rc::new(local_elf)));
                }
            }
        }
        Ok(None)
    }
}

#[derive(Clone, Copy, Debug)]
struct InsnCountKey<'m> {
    // Fields from VmAddrInfo, but without the address.
    mapping: &'m VmMapping,
    section: Option<&'m VmSectionMapping>,
    symbol: Option<&'m VmSymbolMapping>,
}

impl<'m> PartialEq for InsnCountKey<'m> {
    fn eq(&self, other: &Self) -> bool {
        // Mappings don't overlap and are not duplicated, so we can use fast pointer comparisons.
        fn eq_opt<T>(a: Option<&T>, b: Option<&T>) -> bool {
            match (a, b) {
                (None, None) => true,
                (Some(a), Some(b)) => std::ptr::eq(a, b),
                _ => false,
            }
        }
        std::ptr::eq(self.mapping, other.mapping)
            && eq_opt(self.section, other.section)
            && eq_opt(self.symbol, other.symbol)
    }
}
impl<'m> Eq for InsnCountKey<'m> {}

impl<'m> std::hash::Hash for InsnCountKey<'m> {
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        (self.mapping as *const VmMapping).hash(state);
        self.section
            .map(|sec| sec as *const VmSectionMapping)
            .hash(state);
        self.symbol
            .map(|sym| sym as *const VmSymbolMapping)
            .hash(state);
    }
}

#[derive(Default, Debug, Clone)]
struct InsnCount<'m> {
    total: u64,
    unknown_mapping: u64,
    counts: HashMap<InsnCountKey<'m>, u64>,
}

impl<'m> InsnCount<'m> {
    pub fn total(&self) -> u64 {
        self.total
    }

    pub fn add_unknown(&mut self) {
        self.total += 1;
        self.unknown_mapping += 1;
    }

    pub fn add(&mut self, info: VmAddrInfo<'m>) {
        let VmAddrInfo {
            mapping,
            section,
            symbol,
            ..
        } = info;
        let key = InsnCountKey {
            mapping,
            section,
            symbol,
        };
        *self.counts.entry(key).or_default() += 1;
        self.total += 1;
    }

    pub fn report(&self) {
        println!("----------------");

        // Collate first.
        #[derive(Default)]
        struct FileCount<'m> {
            total: u64,
            by_symbol: HashMap<u64, (u64, &'m VmSectionMapping, &'m VmSymbolMapping)>,
            unknown_by_section: HashMap<u64, (u64, &'m VmSectionMapping)>,
            unknown: u64,
        }
        let mut by_file: HashMap<_, FileCount> = HashMap::new();
        for (
            &InsnCountKey {
                mapping,
                section,
                symbol,
            },
            count,
        ) in self.counts.iter()
        {
            let entry = by_file.entry(mapping.target_path()).or_default();
            entry.total += count;
            match (section, symbol) {
                (None, _) => entry.unknown += count,
                (Some(sec), None) => {
                    let v = entry
                        .unknown_by_section
                        .entry(*sec.va.start())
                        .or_insert((0, sec));
                    assert!(v.1 == sec);
                    v.0 += count;
                }
                (Some(sec), Some(sym)) => {
                    let v = entry
                        .by_symbol
                        .entry(*sym.va.start())
                        .or_insert((0, sec, sym));
                    assert!(v.1 == sec);
                    assert!(v.2 == sym);
                    v.0 += count;
                }
            }
        }

        for (path, file_count) in by_file.iter().sorted_by_key(|(_, fc)| !fc.total) {
            println!(
                "{path}: {total}",
                path = path.as_deref().unwrap_or("unknown file"),
                total = file_count.total,
            );
            for (_, (count, sec, sym)) in file_count
                .by_symbol
                .iter()
                .sorted_by_key(|(_, (count, ..))| !count)
            {
                if sec.name == ".text" {
                    println!("  {sym}: {count}", sym = &sym.name);
                } else {
                    println!(
                        "  {sym} (in {sec}): {count}",
                        sym = &sym.name,
                        sec = &sec.name
                    );
                }
            }
            for (_, (count, sec)) in file_count
                .unknown_by_section
                .iter()
                .sorted_by_key(|(_, (count, ..))| !count)
            {
                println!("  unknown symbol (in {sec}): {count}", sec = &sec.name);
            }
            if file_count.unknown != 0 {
                println!(
                    "  unknown symbol (in unknown section): {}",
                    file_count.unknown
                );
            }
        }

        println!("Total: {total}", total = self.total());
    }
}

fn main() -> Result<()> {
    let args = Cli::parse();

    let elf_dirs = if args.elf_dir.is_empty() {
        if args.verbose >= 1 {
            println!("Inferring elf_dirs from VMMAP...");
        }
        args.vmmap
            .parent()
            .map(Path::to_path_buf)
            .into_iter()
            .collect()
    } else {
        args.elf_dir
    };
    let rootfs = if args.rootfs.is_empty() {
        if let Some(home) = std::env::var_os("HOME") {
            vec![PathBuf::from(home).join("cheri/output/rootfs-morello-purecap")]
        } else {
            vec![]
        }
    } else {
        args.rootfs
    };

    if args.verbose >= 1 {
        println!(
            "Using elf_dirs: [{}]",
            elf_dirs.iter().map(|p| p.display()).format(", ")
        );
        println!(
            "Using rootfs: [{}]",
            rootfs.iter().map(|p| p.display()).format(", ")
        );
        println!()
    }
    let vmmap = VmMap::from_stdout(&args.vmmap, &elf_dirs, &rootfs)?;

    if args.verbose >= 1 {
        for (target_path, local) in vmmap.elfs.iter() {
            match local {
                None => println!("No local ELF found to represent {}.", target_path.display()),
                Some(elf) => println!(
                    "Using {} to represent {}.",
                    elf.path.display(),
                    target_path.display()
                ),
            }
        }

        println!();
        for mapping in vmmap.iter() {
            let perms = mapping.perms;
            if perms.execute || args.verbose >= 3 {
                println!(
                    "{range:24}  {perms}  {file}  +{offset:#x}",
                    range = mapping.va.display(),
                    offset = mapping.offset_into_file,
                    file = mapping.target_path().unwrap_or("(no target file)".into()),
                );
                if args.verbose >= 1 {
                    for section in mapping.sections() {
                        println!(
                            "  - {range:24}  {name} ({n} symbols)",
                            range = section.va.display(),
                            name = &section.name,
                            n = section.symbols().len(),
                        );
                        if args.verbose >= 2 {
                            for symbol in section.symbols() {
                                println!(
                                    "     - {range:24}  {isa}  {name}",
                                    range = symbol.va.display(),
                                    isa = symbol.isa,
                                    name = &symbol.name
                                );
                            }
                        }
                    }
                }
            }
        }
        println!();
    }

    // Reference:
    // https://developer.arm.com/documentation/102225/0200/Reference-information/Morello-specific-changes-to-tarmac-trace
    let it_re = Regex::new(
        r"(?x)
        ^\d+\s+                                              # Timestamp
        (?:ps|clk)\s+                                        # Timestamp units
        \S+\s+                                               # CPU name
        IT\s+                                                # Instruction taken
        \(\d+\)\s+                                           # Tick count
        \([01]\|[[:xdigit:]]+\|(?P<pcc_addr>[[:xdigit:]]+)\) # PCC (including virtual address)
        :[[:xdigit:]]+_NS\s+                                 # Physical address (non-secure)
        (?P<insn>[[:xdigit:]]{8})\s+                         # Instruction
        [OC]\s+                                              # ISA (A64 or C64)
        EL0t_n\s+                                            # EL0, non-secure only
        :\s+
        (?P<asm>.*)                                          # Disassembly
    ",
    )
    .unwrap();

    let mut insn_count = InsnCount::default();

    let tarmac_start = args
        .tarmac_start
        .or(vmmap.tarmac.as_ref().map(|t| t.start))
        .unwrap_or(0);
    let tarmac_end = args
        .tarmac_end
        .or(vmmap.tarmac.as_ref().map(|t| t.end))
        .unwrap_or(u64::MAX);
    let tarmac_file = match args
        .tarmac
        .as_ref()
        .or(vmmap.tarmac.as_ref().map(|t| &t.file))
    {
        None => return Err("No tarmac file specified.".into()),
        Some(f) => f,
    };
    if args.verbose >= 1 {
        println!(
            "Using tarmac: {file} [{tarmac_start},{tarmac_end})...",
            file = tarmac_file.display()
        );
    }
    if tarmac_end <= tarmac_start {
        return Err(format!(
            "--tarmac-end ({tarmac_end}) <= --tarmac-start ({tarmac_start}); nothing to analyse"
        )
        .into());
    }
    let tarmac_length = tarmac_end - tarmac_start;

    let mut tarmac = fs::File::open(tarmac_file)?;
    tarmac.seek(std::io::SeekFrom::Start(tarmac_start))?;
    let tarmac = tarmac.take(tarmac_length);
    for line in io::BufReader::new(tarmac).lines() {
        let line = line?;
        if let Some(caps) = it_re.captures(&line) {
            let pcc_addr = caps.name("pcc_addr").unwrap().as_str();
            let insn = caps.name("insn").unwrap().as_str();
            let asm = caps.name("asm").unwrap().as_str();

            let pcc_addr = u64::from_str_radix(pcc_addr, 16).unwrap();

            if args.annotate_trace {
                print!("{pcc_addr:>#18x}  {insn}  {asm:32}");
                // We'll append a comment below.
            }
            match vmmap.addr_info(pcc_addr)? {
                Some(info) => {
                    if args.annotate_trace {
                        println!("  # {info}");
                    }
                    insn_count.add(info);
                }
                None => {
                    if args.annotate_trace {
                        println!();
                    }
                    insn_count.add_unknown();
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
