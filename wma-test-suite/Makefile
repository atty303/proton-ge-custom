CC = x86_64-w64-mingw32-gcc
CC32 = i686-w64-mingw32-gcc
CFLAGS ?= -O2 -Wall -Wextra

.PHONY: all clean

all: bin/mf-decode.exe bin/mf-decode32.exe

bin/mf-decode.exe: mf_decode.c
	mkdir -p bin
	$(CC) $(CFLAGS) -municode -o $@ $< -lmfreadwrite -lmfplat -lmfuuid -lole32

bin/mf-decode32.exe: mf_decode.c
	mkdir -p bin
	$(CC32) $(CFLAGS) -municode -o $@ $< -lmfreadwrite -lmfplat -lmfuuid -lole32

clean:
	rm -f bin/mf-decode.exe bin/mf-decode32.exe
