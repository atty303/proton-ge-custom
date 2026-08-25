CC = x86_64-w64-mingw32-gcc
CC32 = i686-w64-mingw32-gcc
CFLAGS ?= -O2 -Wall -Wextra
PYTHON ?= python3
STEAM_CLIENT_INSTALL ?= $(HOME)/.local/share/Steam

.PHONY: all clean test test-mf

all: bin/mf-decode.exe bin/mf-decode32.exe

bin/mf-decode.exe: mf_decode.c
	mkdir -p bin
	$(CC) $(CFLAGS) -municode -o $@ $< -lmfreadwrite -lmfplat -lmfuuid -lole32

bin/mf-decode32.exe: mf_decode.c
	mkdir -p bin
	$(CC32) $(CFLAGS) -municode -o $@ $< -lmfreadwrite -lmfplat -lmfuuid -lole32

test:
	$(PYTHON) -m unittest discover -s tests -v

test-mf: bin/mf-decode.exe
	@test -n "$(PROTON)" || { echo "PROTON is required" >&2; exit 2; }
	@test -n "$(BASELINE)" || { echo "BASELINE is required" >&2; exit 2; }
	@test -n "$(CORPUS)" || { echo "CORPUS is required" >&2; exit 2; }
	@test -n "$(ARTIFACT)" || { echo "ARTIFACT is required" >&2; exit 2; }
	$(PYTHON) run_mf_regression.py "$(BASELINE)" "$(CORPUS)" "$(ARTIFACT)" --proton "$(PROTON)" --steam-client-install "$(STEAM_CLIENT_INSTALL)"

clean:
	rm -f bin/mf-decode.exe bin/mf-decode32.exe
