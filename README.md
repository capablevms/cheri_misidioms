# Bad CHERI idioms

This draft paper describes some bad CHERI idioms we have encountered. The
`code/` directory gives executable examples of many of these bad idioms.

To run code examples on a CHERI emulator execute the following commands:

```
$ cd code
$ SSHPORT=<cheribsd port> make -f Makefile.<platform>-purecap copyexec-<benchmark>
```

For example, if you have a CHERI-BSD Morello emulator running on 127.0.0.1 on
port 12345 and want to to run the `privesc.c` code example:

```
$ SSHPORT=12345 make -f Makefile.morello-purecap copyexec-privesc
```

If you want to run *all* of the code examples in one go, use the `all-copyexec`
target:

```
$ SSHPORT=12345 make -f Makefile.morello-purecap all-copyexec
```
