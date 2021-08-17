CHERIBASE ?= ${HOME}/cheri
SSHPORT ?= 0

.PHONY: all clean

.c:
	${CC} ${CFLAGS} -o $@ $<

all: narrow narrow_realloc narrow_widen privesc privesc2 unrepresentable_length

copyexec-%: %
	scp -P $(SSHPORT) $< root@127.0.0.1:/root
	ssh -p $(SSHPORT) root@127.0.0.1 -t '/root/$<'

clean:
	rm -f narrow
