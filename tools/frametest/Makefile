# Point SW at the LiteX-generated software dir of your c1100_pcie build, e.g.
#   make SW=../../../MiSTeX-ports/build/c1100_pcie/software
SW ?= $(MISTEX_PORTS)/build/c1100_pcie/software

CFLAGS = -O2 -Wall -g -I$(SW)/kernel -I$(SW)/user/liblitepcie
LDLIBS = $(SW)/user/liblitepcie/liblitepcie.a -lm

frametest: frametest.c
	@test -d "$(SW)/kernel" || { echo "set SW=<build>/c1100_pcie/software (got '$(SW)')" >&2; exit 1; }
	$(CC) $(CFLAGS) -o $@ $< $(LDLIBS)

clean:
	rm -f frametest
