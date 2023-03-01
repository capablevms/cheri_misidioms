CHERIBASE ?= ${HOME}/cheri
SSHPORT ?= 0

.PHONY: all clean

.c:
	${CC} ${CFLAGS} -Wall -Wextra -Wno-unused-parameter -o $@ $<

TARGETS = \
	narrow_widen \
	escbound \
	escperms \
	undef \
	overlap \
    validate

ALL_COPYEXEC_TARGETS = ${TARGETS}

all: ${TARGETS}

all-copyexec: ${ALL_COPYEXEC_TARGETS:%=copyexec-%}

copyexec-%: %
	scp -P $(SSHPORT) $< root@127.0.0.1:/root
	ssh -p $(SSHPORT) root@127.0.0.1 -t '/root/$<'

clean:
	rm -f ${TARGETS}
