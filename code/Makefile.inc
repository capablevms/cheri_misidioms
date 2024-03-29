CHERIBASE ?= ${HOME}/cheri
SSHPORT ?= 0

.PHONY: all clean

TARGETS = \
	narrow_widen_cap_leak \
	narrow_widen \
	escperms \
	escinauthentic \
	undef \
	overlap \
    validate

ALL_COPYEXEC_TARGETS = ${TARGETS}

all: ${TARGETS}

all-copyexec: ${ALL_COPYEXEC_TARGETS:%=copyexec-%}

copyexec-%: %
	scp -P $(SSHPORT) $< root@127.0.0.1:/root
	ssh -p $(SSHPORT) root@127.0.0.1 -t '/root/$<'

.c:
	${CC} ${CFLAGS} -Wall -Wextra -Wno-unused-parameter -o $@ $<

test_bump_alloc1: test_bump_alloc1.c bump_alloc1.c
	${CC} ${CFLAGS} -Wall -Wextra -Wno-unused-parameter -o $@ $<

test_bump_alloc2: test_bump_alloc2.c bump_alloc2.c
	${CC} ${CFLAGS} -Wall -Wextra -Wno-unused-parameter -o $@ $<

clean:
	rm -f ${TARGETS}
