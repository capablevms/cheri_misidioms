#!/usr/bin/env perl

# SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: MIT OR Apache-2.0

use strict;
use warnings;

use Getopt::Long;
use Data::Dumper;
$Data::Dumper::Sortkeys = 1;

my $n = 4;
my $full_elf = 0;
sub ExitWithUsage {
  my ($code) = @_;
  print(<<USAGE
Usage: $0 [option]... DATE-ABI-NAME.analysis...

E.g: $0 *.analysis | ./plot.r

Parse each analysis file and produce a CSV file suitable for plotting.

OPTIONS
  --full-elf
      Use the full ELF path, not just the basename.

  -n COUNT
      Only consider the top COUNT symbols. All others will be grouped as
      'other'. Defaults to $n.
  
  -h, --help
      Print this help text and exit.
USAGE
  );

  exit($code);
}

exit(1) unless GetOptions("help" => sub { ExitWithUsage(0) },
                          "full-elf!" => \$full_elf,
                          "n=i" => \$n);

my @available_colour_sets = (
  [qw/fbec86 f6c859 ee962d d35d16 a13315/], # Red-browns
  [qw/488178 81c09e d1ffbc/],               # Blue-greens
  #[qw/6c3cad a07dd0/],                      # Purples
);

# Purple-pinks.
my @self_colours = reverse qw/412c4a 6d4576 9f5fa2 bc8ab9 d6b6d0/;

my %colour_sets;
my %colours;

# We want to process hybrid traces first, because we use them to normalise.
my @hybrid;
my @purecap;
for my $file (@ARGV) {
  if ($file =~ /-hybrid-/) {
    push(@hybrid, $file);
  } else {
    push(@purecap, $file);
  }
}
my %hybrid_totals;

print("Benchmark,ABI,ELF,Symbol,Instruction Count,Normalised Instruction Count,Colour\n");
for my $file (@hybrid, @purecap) {
  $file =~ /^\d\d\d\d-\d\d-\d\d-(hybrid|purecap)-(.+)\.analysis$/ or die("Bad analysis file name: $file");
  my ($abi, $benchmark) = ($1, $2);
  my %symbols;
  my $elf = undef;
  open(my $fh, $file) or die("Could not open $file: $!");
  while (my $line = <$fh>) {
    chomp($line);
    if ($line =~ /^\[/) {
      next; # VM map, ignore.
    } elsif ($line eq '...') {
      next; # Omitted section, ignore.
    } elsif ($line eq '----------------') {
      # We just read an interim table. Discard it, and start again.
      %symbols = ();
      $elf = undef;
    } elsif ($line =~ /^Total:/) {
      next; # Ignore.
    } elsif ($line =~ /^(\S[^:]+): \d+$/) {
      $elf = $1;
      if (!$full_elf) {
        $elf =~ s@.*/@@;
        $elf =~ s@\.so\.\d+@.so@;
      }
      die("Unimplemented: ELF name contains a comma: $elf\n") if ($elf =~ /,/);;
    } elsif ($line =~ /^  (\S[^:]+): (\d+)$/) {
      my ($symbol, $count) = ($1, $2);
      die("Unimplemented: Symbol name contains a comma: $symbol\n") if ($elf =~ /,/);;
      $symbols{"$elf,$1"} = $2;
    } else {
      die("Unrecognised input: $line");
    }
  }
  close($fh);

  if ($file =~ /-hybrid-/) {
    $hybrid_totals{$benchmark} = 0;
    $hybrid_totals{$benchmark} += $_ for (values %symbols);
  }

  my $other = 0;
  my $i = 0;
  my @sorted = sort { $symbols{$b} <=> $symbols{$a} } keys(%symbols);
  for (my $i = 0; $i < $n; $i++) {
    my $elf_sym = shift(@sorted);
    my ($elf, $symbol) = split(',', $elf_sym);
    if ($symbol eq 'unknown symbol') {
      $other += $symbols{$elf_sym};
      next;
    }
    if (!exists($colour_sets{$elf})) {
      if ($elf =~ /\.so/) {
        $colour_sets{$elf} = shift(@available_colour_sets) or die("Ran out of colour sets");
      } else {
        $colour_sets{$elf} = [@self_colours];
      }
    }
    if (!exists($colours{$elf_sym})) {
      if (my $colour = shift(@{$colour_sets{$elf}})) {
        $colours{$elf_sym} = $colour;
      } else {
        warn("Ran out of colours for $elf");
        $colours{$elf_sym} = 'eeeeee';
      }

    }
    my $colour = $colours{$elf_sym};
    my $count = $symbols{$elf_sym};
    my $norm = $count / $hybrid_totals{$benchmark};
    print("$benchmark,$abi,$elf_sym,$count,$norm,#$colour\n");
  }
  for my $elf_sym (@sorted) {
    $other += $symbols{$elf_sym};
  }
  if ($other != 0) {
    my $norm = $other / $hybrid_totals{$benchmark};
    print("\"$benchmark\",$abi,[mixed],[other],$other,$norm,#ffffff\n");
  }
  # TODO: Normalise to something.
}
