#!/usr/bin/env perl

# SPDX-FileCopyrightText: Copyright 2022 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: MIT OR Apache-2.0

use strict;
use warnings;

use Getopt::Long;
use Text::Table;
use TOML::Parser qw/from_toml/;

my $fmt = 'text';
my $group_basis = 1;
my $group_equiv = 1;
sub ExitWithUsage {
  my ($code) = @_;
  print(<<USAGE
Usage: $0 [option]... < spec.toml
       $0 [option]... [spec.toml]...

E.g: $0 api-equiv/*/api-equiv.*.toml

Analyse and summarise APIs as described in each spec.toml.

OPTIONS
  --fmt FMT

      text (default): Print a text table for fixed-width fonts.
      latex: Print a LaTeX table.

  --[no-]group-basis

      Group API functions along with dependencies, even if they aren't
      equivalents. This uses the 'basis' TOML field. If multiple dependencies
      exist, functions will be grouped with the first one encountered.

      Enabled by default.

  --[no-]group-equiv

      Group API functions along with equivalents. This uses the 'equiv' TOML
      field.

      Enabled by default.

  -h, --help
      Print this help text and exit.
USAGE
  );

  exit($code);
}

exit(1) unless GetOptions("help" => sub { ExitWithUsage(0) },
                          "fmt=s" => sub {
                            if ($_[1] =~ /^(text|latex)$/) {
                              $fmt = $_[1];
                            } else {
                              die("Unrecognised FMT: $_[1]");
                            }
                          },
                          "group-basis!" => \$group_basis,
                          "group-equiv!" => \$group_equiv);

# Sort APIs such that dependencies appear first.
# Returns a sorted list, and also adds a '_column' field to each API to
# make reverse queries easy later.
sub resolve_api_dependencies {
  my ($apis) = @_;
  my @names = sort keys %$apis;
  my %seen;
  my @result;
  while (@names > @result) {
    my $count = @result;
    for my $name (@names) {
      next if ($seen{$name});
      next if (grep { !$seen{$_} } @{$apis->{$name}->{dependencies}});
      $apis->{$name}->{_column} = @result;
      push(@result, $name);
      $seen{$name} = 1;
    }
    if (@result == $count) {
      my $unseen = join(', ', grep { $seen{$_} } @names);
      die("Circular dependency ($unseen)");
    }
  }
  return @result;
}

# Look for a function in the specified scope. This is used, for example, to
# group equivalent functions in different APIs onto the same table row.
sub qualify {
  my ($spec, $name, @scope) = @_;
  for my $api (@scope) {
    my $fns = $spec->{apis}->{$api}->{fns};
    if (exists($fns->{$name})) {
      return {
        api => $api,
        fn => $name,
      };
    }
  }
  if ($name =~ /^__builtin_/) {
    # Don't warn in this case; a few CHERI/Morello builtins depend on generic
    # builtins, which we don't analyse.
  } else {
    warn("Could not qualify '$name' in scope (".join(', ', @scope).')');
  }
  return { fn => $name };
}

# Place each function alongside dependencies (including equivalent functions in
# other APIs).
sub resolve_dependencies {
  my ($spec, $api) = @_;
  my @allowed_apis = ($api, @{$spec->{apis}->{$api}->{dependencies} // []});
  for my $fn_name (keys %{$spec->{apis}->{$api}->{fns}}) {
    my $fn = $spec->{apis}->{$api}->{fns}->{$fn_name};
    my %qualified_fn = (
      api => $api,
      name => $fn_name,
    );
    if (exists($fn->{equiv})) {
      my $q = qualify($spec, $fn->{equiv}, @allowed_apis);
      if (exists($q->{api}) && exists($q->{fn})) {
        # Add a reverse link.
        my $dep = $spec->{apis}->{$q->{api}}->{fns}->{$q->{fn}};
        push(@{$dep->{fwd_equivs}}, \%qualified_fn);
      }
    }
    for my $basis (@{$fn->{basis} // []}) {
      my $q = qualify($spec, $basis, @allowed_apis);
      if (exists($q->{api}) && exists($q->{fn})) {
        # Add a reverse link.
        my $dep = $spec->{apis}->{$q->{api}}->{fns}->{$q->{fn}};
        push(@{$dep->{fwd_bases}}, \%qualified_fn);
      }
    }
  }
}

sub render_fn {
  my ($spec, $api, $name) = @_;
  # TODO: It'd be nice to print the full C prototype here, but it takes a lot of
  # space. For now, just print the name.
  #
  #my $desc = $spec->{apis}->{$api}->{fns}->{$name};
  #if (exists($desc->{ret}) || exists($desc->{args})) {
  #  my $ret = $desc->{ret} // 'void';
  #  my $args = join(', ', @{$desc->{args} // []});
  #  return "$ret $name($args)";
  #}
  return $name;
}
my $spec = TOML::Parser->new()->parse(join('', <>));
my @apis = resolve_api_dependencies($spec->{apis});
resolve_dependencies($spec, $_) for (@apis);

my $notes_column = @apis;

sub fn {
  if ((@_ == 1) && (ref $_[0] eq ref {})) {
    return fn($_[0]->{api}, $_[0]->{name});
  }
  my ($api, $name) = @_;
  return $spec->{apis}->{$api}->{fns}->{$name};
}

sub mark_printed {
  my ($fn) = @_;
  return 0 if (exists($fn->{_printed}));
  $fn->{_printed} = 1;
  return 1;
}

sub escape_for_fmt {
  my ($text) = @_;
  if ($fmt eq 'latex') {
    $text =~ s/_/\\_/g;
    $text =~ s/\^/\\^/g;
  }
  return $text;
}

sub make_row {
  my ($api, $fn_name, $default_notes) = @_;
  my @row;
  $row[$spec->{apis}->{$api}->{_column}] = render_fn($spec, $api, $fn_name);
  my $notes = $spec->{apis}->{$api}->{fns}->{$fn_name}->{notes} // $default_notes;
  $row[$notes_column] = $notes if ($notes);
  return [map { escape_for_fmt($_ // '') } @row];
}

# Recursively add rows for the named function, and any direct equivalents or
# simple derived functions. Does not add functions that have already been
# printed.
sub add_rows {
  my ($rows, $api, $fn_name, $default_notes) = @_;
  return unless (mark_printed(fn($api, $fn_name)));
  push(@$rows, make_row($api, $fn_name, $default_notes));

  if ($group_equiv) {
    # Add equivalences, putting custom notes last (for optimal compaction).
    for my $q (sort {
        exists(fn($a)->{notes}) <=> exists(fn($b)->{notes})
      } @{fn($api, $fn_name)->{fwd_equivs} // []}) {
      add_rows($rows, $q->{api}, $q->{name}, "Trivial pass-through to $fn_name.");
    }
  }

  if ($group_basis) {
    # Add simple derivations, putting custom notes last (for optimal compaction).
    for my $q (sort {
        exists(fn($a)->{notes}) <=> exists(fn($b)->{notes})
      } grep {
        @{fn($_)->{basis}} == 1
      } @{fn($api, $fn_name)->{fwd_bases} // []}) {
      add_rows($rows, $q->{api}, $q->{name}, "Based on $fn_name.");
    }
  }
}

# Compact:
#
#   | aaa    |        |        |            |
#   |        | bbb    |        | Comment... |
#   |        |        | ccc    | Comment... |
#
# ... becomes ...
#
#   | aaa    | bbb    | ccc    | Comment... |
#
# ... as long as the comments match.
sub compact_rows {
  my @old = @_;
  my @new;
  for my $row (@old) {
    push(@new, []) if (@new == 0);
    my $can_merge = 1;
    my @merged = @{$new[$#new]};
    for my $col (0..$notes_column) {
      if ($col == $notes_column) {
        if (!$merged[$col]) {
          $merged[$col] = $row->[$col];
        } elsif ($merged[$col] ne $row->[$col]) {
          $can_merge = 0;
          last;
        }
      } else {
        if ($merged[$col]) {
          if ($row->[$col]) {
            $can_merge = 0;
            last;
          }
        } else {
          $merged[$col] = $row->[$col];
        }
      }
    }
    if ($can_merge) {
      $new[$#new] = \@merged;
    } else {
      push(@new, $row);
    }
  }
  return @new;
}

my $vsep = ' | ';
my $hsep = '-';
my $xsep = '+';
if ($fmt eq 'latex') {
  $vsep = ' & ';
}

my %tb_rules;
my $tb = Text::Table->new((map { ($spec->{apis}->{$_}->{name} // $_, \$vsep) } @apis), 'Notes');
for my $api (@apis) {
  my $fns = $spec->{apis}->{$api}->{fns};
  for my $fn_name (sort keys %$fns) {
    my $fn = $fns->{$fn_name};
    my @rows;
    my $default_notes = undef;
    $default_notes = "Trivial pass-through to (unlisted) $fn->{equiv}." if (exists($fn->{equiv}));
    add_rows(\@rows, $api, $fn_name, $default_notes);
    $tb_rules{$tb->height()} = 1;
    $tb->load(compact_rows(@rows));
  }
}

if ($fmt eq 'text') {
  my @rows = $tb->table();
  for my $i (0..$#rows) {
    print($tb->rule($hsep, $xsep)) if ($tb_rules{$i});
    print($rows[$i]);
  }
} elsif ($fmt eq 'latex') {
  print("\\begin{table}\n");
  print("  \\begin{center}\n");
  print("    \\begin{tabular}{".('l' x (@apis + 1))."}\n");
  print("    \\toprule\n");
  my @rows = $tb->table();
  for my $i (0..$#rows) {
    print("    \\midrule\n") if ($tb_rules{$i});
    print("    ".($rows[$i] =~ s/\s+$//gr)." \\\\\n");
  }
  print("    \\bottomrule\n");
  print("    \\end{tabular}\n");
  print("  \\end{center}\n");
  print("\\end{table}\n");
}
