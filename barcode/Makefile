# Barcode decoder for the Micronic 1000 / PARCON 1000.
#
#   make            build decoder.bin, decoder.dip and decoder.com
#   make ASM=pasmo  build with pasmo instead of z88dk
#   make test       assemble, then run it against the firmware in the emulator
#   make clean
#
# z88dk is used through its Docker image, which needs no local install:
#   https://hub.docker.com/r/z88dk/z88dk
# Set DOCKER= if your user is in the docker group and needs no sudo.

ASM     ?= z88dk
ORIGIN  ?= 0xC000
BUILD   ?= build
DOCKER  ?= sudo docker
IMAGE   ?= z88dk/z88dk

SOURCES := src/hook.asm src/code39.asm src/upc.asm
DEPS    := $(SOURCES) src/dipos.inc src/code39_table.inc \
           src/upc_table.inc src/ean_parity.inc \
           $(BUILD)/origin.stamp

PYTHON  ?= python3
VENV    ?= ../analysis/venv/bin/python3

all: $(BUILD)/decoder.bin $(BUILD)/decoder.dip $(BUILD)/decoder.com

$(BUILD):
	mkdir -p $(BUILD)

# The link address is baked into the binary, so a change of ORIGIN has to
# force a rebuild.  Without this, `make ORIGIN=...` silently keeps the old
# binary and everything downstream is linked for the wrong address.
$(BUILD)/origin.stamp: | $(BUILD)
	@echo "$(ORIGIN)" | cmp -s - $@ || echo "$(ORIGIN)" > $@

ifeq ($(ASM),z88dk)
# -b makes a binary; -r sets the link origin.  The container runs as the
# invoking user so the outputs are not owned by root.
$(BUILD)/decoder.bin: $(DEPS) | $(BUILD)
	$(DOCKER) run --rm --user $$(id -u):$$(id -g) \
	    -v "$(CURDIR):/src" -w /src $(IMAGE) \
	    z88dk-z80asm -b -r$(ORIGIN) -o$(BUILD)/decoder.bin $(SOURCES)
	@rm -f src/*.o
else
# pasmo wants one translation unit, so concatenate.  Kept working as a
# fallback for anyone who would rather not run a container.
$(BUILD)/decoder.bin: $(DEPS) | $(BUILD)
	@printf '    org %s\n' $(ORIGIN) > $(BUILD)/all.asm
	@cat src/dipos.inc >> $(BUILD)/all.asm
	@cat $(SOURCES) | grep -v '^[[:space:]]*\(public\|extern\|include\)' \
	    >> $(BUILD)/all.asm
	@cat src/code39_table.inc src/upc_table.inc src/ean_parity.inc \
	    >> $(BUILD)/all.asm
	pasmo --bin $(BUILD)/all.asm $(BUILD)/decoder.bin
endif

$(BUILD)/decoder.dip: $(BUILD)/decoder.bin
	$(PYTHON) tools/mkdip.py $< -o $@ --addr $(patsubst 0x%,%,$(ORIGIN))

$(BUILD)/decoder.com: $(BUILD)/decoder.bin
	$(PYTHON) tools/mkcom.py $< -o $@ --addr $(patsubst 0x%,%,$(ORIGIN))

tables:
	$(PYTHON) tools/gen_tables.py

# FIRMWARE=1 adds the slow end-to-end run through the emulator.
test: $(BUILD)/decoder.bin
	$(VENV) tools/run_tests.py --binary $(BUILD)/decoder.bin \
	    --origin $(ORIGIN) $(if $(FIRMWARE),--firmware,)

clean:
	rm -rf $(BUILD) src/*.o

.PHONY: all clean test tables
