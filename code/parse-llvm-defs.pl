#!/usr/bin/env perl

# SPDX-FileCopyrightText: Copyright 2022 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: MIT OR Apache-2.0

use strict;
use warnings;

use Getopt::Long;
use Term::ANSIColor qw/colored colorstrip/;

sub ExitWithUsage {
  my ($code) = @_;
  print(<<USAGE
Usage: $0 [option]... < builtins.def
       $0 [option]... [builtins.def]...

E.g: $0 LLVM/clang/include/clang/Basic/Builtins{,AArch64}.def --fmt toml >> api-equiv.builtins.toml

Read LLVM builtins ".def" files, parse the prototype specifications, and convert
to the requested output format(s). This was intended to generate
`api-equiv.builtins.toml` for our analysis, but is also useful to discover the
(approximate) C function prototypes of the Morello and CHERI builtins.

Only CHERI and Morello builtins are supported. LLVM builtins are described using
a sequence of custom tokens, and this tool only decodes the tokens used by CHERI
and Morello. This is not a general-purpose decoder.

Note that a large proportion of the CHERI builtins implement custom
typechecking, and their described signatures are apparently "meaningless".
Despite this, the signatures derived by this tool do actually appear to match
their usage in real code, though LLVM may provide additional polymorphism, or
type checking that this analysis cannot detect.

OPTIONS

  -f, --fmt FMT[,FMT]...

      c:
        Print C function prototypes. This is useful for quick, command-line
        exploration. If combined with toml, prototypes are printed inline as
        comments.
      c++:
        Print C++ attributes (notably 'const'). Implies 'c'.
      toml:
        Print [apis.builtins.fns.*] TOML tables for analysis (e.g. by
        api-equiv.pl). Note that the legal notices and the [apis.builtins] table
        must be written manually.

      If no formats are specified, 'c' will be assumed.

  --colo[u]r WHEN

      Control rudimentary syntax highlighting, using ANSI escape sequences.

      auto (default): Emit colours if stdout is a tty.
      always/never: Force colours on or off, respectively.

      Colour output can also be disabled by setting ANSI_COLORS_DISABLED or
      NO_COLOR in the environment. See Term::ANSIColor documentation for
      details: https://perldoc.perl.org/Term::ANSIColor#ANSI_COLORS_DISABLED

  -h, --help
      Print this help text and exit.
USAGE
  );

  exit($code);
}

my %fmts = ();
my $colour = 'auto';
exit(1) unless GetOptions("help" => sub { ExitWithUsage(0) },
                          "fmt=s" => sub {
                            for my $fmt (split(',', $_[1])) {
                              if (lc($fmt) =~ /^(c|c\+\+|toml)$/) {
                                $fmts{$fmt} = 1;
                              } else {
                                die("Unrecognised FMT: $fmt");
                              }
                            }
                          },
                          "colour|color=s" => sub {
                            if (lc($_[1]) =~ /^(always|auto|never)$/) {
                              $colour = $_[1];
                            } else {
                              die("Unrecognised $_[0] option: $_[1]");
                            }
                          });

%fmts = (c => 1) unless (%fmts);
$fmts{c} = 1 if ($fmts{'c++'} // 0);

# Term::ANSIColor respects ANSI_COLORS_DISABLED; if set, `colored(...)` returns
# string arguments unmodified.
$ENV{ANSI_COLORS_DISABLED} = ($colour eq 'never') || (($colour eq 'auto') && !(-t STDOUT));

# Only types relevant to CHERI/Morello are supported here.

# https://git.morello-project.org/morello/llvm-project/-/blob/4f78985b2783297718f95bf4542e907f1295758f/clang/include/clang/Basic/Builtins.def#L51-L61
my %prefixes = ();
# https://git.morello-project.org/morello/llvm-project/-/blob/4f78985b2783297718f95bf4542e907f1295758f/clang/include/clang/Basic/Builtins.def#L20-L49
my %types = (
  b => colored(['bold yellow'], 'bool'),
  v => colored(['bold yellow'], 'void'),
  z => colored(['bold yellow'], 'size_t'),
  Y => colored(['bold yellow'], 'ptrdiff_t'),
  '.' => '...',
);
# https://git.morello-project.org/morello/llvm-project/-/blob/4f78985b2783297718f95bf4542e907f1295758f/clang/include/clang/Basic/Builtins.def#L63-L71
my %modifiers = (
  '*' => '*',
  'm' => colored(['yellow'], '__capability'),
  'C' => colored(['yellow'], 'const'),
);

sub starts_with {
  my ($str, $needle) = @_;
  return rindex($str, $needle, 0) == 0;
}

sub take_from_start {
  my ($str, $needles) = @_;
  for my $needle (@$needles) {
    if (starts_with($$str, $needle)) {
      $$str = substr($$str, length($needle));
      return $needle;
    }
  }
  return undef;
}

sub build_c_type {
  my ($entry) = @_;
  my $c = $types{$entry->{type}};
  for my $pre (@{$entry->{prefixes}}) {
    # No Morello/CHERI function uses prefixes yet.
    die("Unimplemented: '$pre' prefix");
  }
  $c .= ' '.$modifiers{$_} for (@{$entry->{modifiers}});
  $entry->{c} = $c;
}

sub parse_types {
  my ($name, $type_str) = @_;
  my @entries;
  my $remainder = $type_str;
  while ($remainder ne '') {
    my %entry = (
      str => '',
      prefixes => [],
      type => '',
      modifiers => [],
    );
    my $str = $remainder;
    push(@{$entry{prefixes}}, $_) while ($_ = take_from_start(\$remainder, [keys %prefixes]));
    $entry{type} = take_from_start(\$remainder, [keys %types]) // '';
    push(@{$entry{modifiers}}, $_) while ($_ = take_from_start(\$remainder, [keys %modifiers]));
    $entry{str} = substr($str, 0, length($str) - length($remainder));

    if (!$entry{type}) {
      warn(unsupported('type', $name, $str, $type_str));
      last;
    }
    build_c_type(\%entry);
    push(@entries, \%entry);
  }
  return @entries;
}

sub parse_attributes {
  my ($name, $attributes) = @_;
  my @cxx_attrs;
  my @notes;
  for my $attr (split(//, $attributes)) {
    if ($attr eq 'n') {
      push(@cxx_attrs, 'noexcept');
    } elsif ($attr eq 'c') {
      push(@cxx_attrs, 'const');
    } elsif ($attr eq 't') {
      # TODO: api-equiv.pl doesn't currently show the full prototype, so this
      # note isn't very useful.
      #push(@notes, 'Builtin uses custom typechecking.');
    } else {
      warn(unsupported('attribute', $name, $attr, $attributes));
    }
  }
  return (\@cxx_attrs, join("\n", @notes));
}

sub unsupported {
  my ($type, $name, $what, $context) = @_;
  return colored(['red'], "Unsupported $type for $name: ").
         colored(['bold red'], $what).
         colored(['red'], ' (in ').
         colored(['bold red'], $context).
         colored(['red'], ')');
}

sub print_toml_comment {
  print(colored(['magenta'], "# $_")."\n") for (colorstrip(@_));
}

sub print_toml_table_header {
  print(colored(['green'], '['.join('.', colorstrip(@_)).']')."\n");
}

sub print_toml_kv {
  my ($k, $v) = colorstrip(@_);
  print("$k = $v\n");
}

sub toml_literal_str {
  my ($in) = colorstrip(@_);
  # Literal strings can encode everything except ', \n and most control
  # characters. This serves our needs for now.
  return undef if ($in =~ /['\n\x00-\x08\x0a-\x1f\x7f]/);
  return "'$in'";
}

sub toml_str {
  my $in = join("\n", @_);
  return toml_literal_str($in) //
         die("Unimplemented: TOML string quoting for: $in");
}

sub toml_array_of_strs {
  my @strs = map { toml_str($_) } @_;
  return '['.join(', ', @strs).']';
}

for my $line (<>) {
  next unless ($line =~ /\bBUILTIN\((__builtin_(?:morello|cheri)_[^,]+),\s*"([^"]*)"\s*,\s*"([^"]*)"\s*\)/);
  my ($name, $type_str, $attribute_str) = ($1, $2, $3);
  my (@ctypes) = map { $_->{c} } parse_types($name, $type_str);
  my ($cxx_attrs, $notes) = parse_attributes($name, $attribute_str);
  if (@ctypes > 0) {
    my ($cret, @cargs) = @ctypes;
    my $fn_suffix = ($fmts{'c++'} // 0)
        ? join('', map { ' '.colored(['green'], $_) } @$cxx_attrs)
        : '';
    my $c = "$cret $name(".join(', ', @cargs).")$fn_suffix";
    if ($fmts{toml} // 0) {
      if ($fmts{c} // 0) {
        print_toml_comment($c);
      }
      print("\n");
      print_toml_table_header('apis', 'builtins', 'fns', $name);
      print_toml_kv('ret', toml_str($cret));
      print_toml_kv('args', toml_array_of_strs(@cargs));
      print_toml_kv('cxx_attrs', toml_array_of_strs(@$cxx_attrs)) if (@$cxx_attrs);
      print_toml_kv('notes', toml_str($notes)) if ($notes);
    } elsif ($fmts{c} // 0) {
      print("$c\n");
    }
  }
}
