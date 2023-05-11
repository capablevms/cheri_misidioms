#!/usr/bin/env perl

# SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: MIT OR Apache-2.0

use strict;
use warnings;
use Getopt::Long;
use Data::Dumper;
$Data::Dumper::Sortkeys = 1;
use File::Basename;
use feature qw/say/;

my $fmt = 'plain';
sub ExitWithUsage {
  my ($code) = @_;
  print(<<USAGE
Usage: $0 [option]... DATE-ABI-NAME.analysis...

E.g: $0 *.analysis

Parse each analysis file and produce a table showing instruction classification
breakdowns (from the "of which..." breakdowns produced by the analyser).

OPTIONS
  -f, --fmt FMT
      Table format. FMT must be one of:

        plain:      One line per result.
        table:      Plain text table.
        table-perc: Plain text table with percentages.
        latex:      LaTeX table.
        latex-perc: LaTeX table with percentages.
        ...

  -h, --help
      Print this help text and exit.
USAGE
  );

  exit($code);
}

exit(1) unless GetOptions("help" => sub { ExitWithUsage(0) },
                          "f|fmt=s" => \$fmt);

my @results;
my %of_which_cols;
for my $file (@ARGV) {
  fileparse($file) =~ /^\d\d\d\d-\d\d-\d\d(?:T\d\d:\d\d\+\d\d:\d\d)?-(hybrid|purecap)-(.+)\.analysis$/ or die("Bad analysis file name: $file");
  my ($abi, $benchmark) = ($1, $2);
  open(my $fh, $file) or die("Could not open $file: $!");
  my $total = undef;
  my %of_which = ();
  while (my $line = <$fh>) {
    chomp($line);
    if ($line =~ /^\[/) {
      # VM map, ignore.
    } elsif ($line eq '...') {
      # Omitted section, ignore.
    } elsif ($line eq '----------------') {
      # We just read an interim table. Discard it, and start again.
    } elsif ($line =~ /^Total: (\d+), of which...$/) {
      $total = $1;
      %of_which = ();
      next; # Don't reset $total.
    } elsif ($line =~ /^(\S[^:]+): \d+$/) {
      # Ignore symbol reports.
    } elsif ($line =~ /^  (\S[^:]+): (\d+)(, of which...)?$/) {
      # Ignore ELF reports.
    } elsif ($line =~ /^ *- (\d+) (.*) \((\d+\.\d+)%\)$/) {
      if (defined($total)) {
        my ($event, $abs, $perc) = ($2, $1, $3);
        if ($fmt =~ /latex/) {
          $event = '\\texttt{.plt} entries' if ($event eq "branched to a '.plt' section");
          $event = "\\texttt{$1}" if ($event =~ /^were (.*)$/);
        }
        $of_which{$event} = { abs => $abs, perc => $perc };
        next; # Don't reset $total.
      }
    } else {
      die("Unrecognised input: $line");
    }
    $total = undef;
  }
  close($fh);

  $of_which_cols{$_}++ for (keys %of_which);

  push(@results, {
      abi => $abi,
      benchmark => $benchmark,
      name => "$abi-$benchmark",
      total => $total,
      of_which => \%of_which,
  });
}

sub benchmark_sort_key {
  my ($bm) = @_;
  return "0-$bm" if ($bm =~ /^binary-tree/);
  return "1-$bm" if ($bm =~ /^mstress/);
  return "2-$bm" if ($bm =~ /^richards/);
  return "9-$bm";
}

# Sort in the order in the paper.
@results = sort {
  (benchmark_sort_key($a->{benchmark}) cmp benchmark_sort_key($b->{benchmark}))
  || ($a->{abi} cmp $b->{abi})
  || ($a->{total} <=> $b->{total})
} @results;

if ($fmt eq 'plain') {
  for my $result (@results) {
    my @cols = sort keys %{$result->{of_which}};
    print("$result->{name}: $result->{total}");
    if (@cols) {
      print(", of which ");
      print(join(", ", map {
            my $of_which = $result->{of_which}->{$_};
            "$of_which->{abs} ($of_which->{perc}%) $_"
          } @cols));
    }
    print("\n");
  }
} elsif (($fmt eq 'table') or ($fmt eq 'table-perc')) {
  my @cols;
  push(@cols, ['Benchmark', map { $_->{name} } @results]);
  push(@cols, ['Total', map { $_->{total} } @results]);
  my $type = ($fmt eq 'table-perc') ? 'perc' : 'abs';
  my $unit = ($fmt eq 'table-perc') ? '%' : '';
  for my $of_which_col (sort keys %of_which_cols) {
    push(@cols, [$of_which_col, map {
          my $v = $_->{of_which}->{$of_which_col}->{$type} // '';
          $v = "$v$unit" if ($v);
          $v
        } @results]);
  }
  my @col_widths = map {
    my $width = 0;
    for my $cell (@$_) {
      $width = length($cell) if length($cell) > $width;
    }
    $width
  } @cols;
  for (my $y = 0; $y < (1 + @results); $y++) {
    for (my $x = 0; $x < @cols; $x++) {
      print("  ") unless ($x == 0);
      printf("%$col_widths[$x]s", $cols[$x]->[$y]);
    }
    print("\n");
  }
} elsif ($fmt eq 'latex') {
  my $n_of_which = keys %of_which_cols;
  my $first_of_which = 3;
  my $last_of_which = $first_of_which + $n_of_which - 1;
  say('\\begin{table}[tb]');
  say('\\begin{center}');
  say('\\begin{tabular}{lr' . ('r' x $n_of_which) . '}');
  say('\\toprule');
  say("Name & Total & \\multicolumn{$n_of_which}{c}{of which}\\\\");
  say("\\cmidrule(lr){$first_of_which-$last_of_which}");
  say('  &   &  ' . join(' & ', sort keys %of_which_cols) . '\\\\');
  say('\\midrule');
  for my $result (@results) {
    my $row = "$result->{name} & \\numprint{$result->{total}}";
    for my $col (sort keys %of_which_cols) {
      my $v = $result->{of_which}->{$col}->{abs} // '0';
      $row = "$row & \\numprint{$v}";
    }
    say("$row\\\\");
  }
  say('\\bottomrule');
  say('\\end{tabular}');
  say('\\end{center}');
  say('\\end{table}');
} elsif ($fmt eq 'latex-perc') {
  # Remove columns with all-zero data (after rounding to a percentage).
  for my $col (keys %of_which_cols) {
    my $all_zero = 1;
    for my $result (@results) {
      $all_zero = 0 if (($result->{of_which}->{$col}->{perc} // '0.00') ne '0.00');
    }
    if ($all_zero) {
      delete $of_which_cols{$col};
    }
  }

  my $n_of_which = keys %of_which_cols;
  my $first_of_which = 2;
  my $last_of_which = $first_of_which + $n_of_which - 1;
  say('\\begin{table*}[htp]');
  say('  \\begin{center}');
  say('    \\begin{tabular}{l' . ('r' x $n_of_which) . '}');
  say('      \\toprule');
  say("      Name & \\multicolumn{$n_of_which}{c}{\\% of instructions}\\\\");
  say("      \\cmidrule(lr){$first_of_which-$last_of_which}");
  say('        & ' . join(' & ', sort keys %of_which_cols) . '\\\\');
  print('      \\midrule');
  my $last_stem = undef;
  for my $result (@results) {
    my $row = "$result->{name}";
    my $stem = $row =~ s/^(hybrid|purecap)-//r;
    print("[6pt]") if (defined($last_stem) and ($stem ne $last_stem));
    $last_stem = $stem;
    print("\n");
    for my $col (sort keys %of_which_cols) {
      my $v = $result->{of_which}->{$col}->{perc} // '0.00';
      $row = "$row & $v";
    }
    print("      $row\\\\");
  }
  print("\n");
  say('      \\bottomrule');
  say('    \\end{tabular}');
  say('  \\end{center}');
  say('\\end{table*}');
} else {
  die("Bad value for '--fmt': $fmt\n");
}
