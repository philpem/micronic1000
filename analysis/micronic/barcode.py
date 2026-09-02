"""micronic.barcode - wand model, Code 39 codec, and a Z80 decode hook.

Three things live here:

  * ``Wand`` - a model of whatever the firmware reads on port 2Dh bit 0
    during an edge capture.  It turns a list of element widths into the
    level sequence the capture loop at ROM00:13BB sees.
  * Code 39 encode/decode in Python, sharing one pattern table.
  * ``decoder_source()`` / ``assemble_decoder()`` - a Code 39 decoder
    written in Z80 assembly, to be installed as the firmware's decode
    hook (see ``ExtDecodeHookInstall``, ROM00:1587).

Width units
-----------
Every width in this module is expressed in the unit the firmware records:
the value the capture loop pushes into the width table.  The loop counts
its own polls of port 2Dh, starting each element at HL=1 and
pre-incrementing, so an element the wand holds for N samples is recorded
as N+1.  ``Wand`` compensates, so a requested width of W appears in the
table at ram:F9B5 as exactly W.

The firmware imposes two limits on that number, both byte-verified:

  * ``ROM00:13FA`` ``SUB 0x8`` / ``JR C`` - an element recorded below 8
    aborts the whole capture and re-arms, so 8 is the minimum width.
  * ``ROM00:13EA`` ``CP D`` with ``D=0x18`` - an element that reaches
    0x1800 ends the capture, so 6143 is the maximum and the trailing
    quiet zone is what terminates a scan.
"""

__all__ = [
    "CODE39_PATTERNS", "Code39Error", "encode_code39", "decode_code39",
    "Wand", "MIN_WIDTH", "MAX_WIDTH", "MAX_ELEMENTS",
    "decoder_source", "assemble_decoder",
    "probe_source", "assemble_probe",
]

MIN_WIDTH = 8        # ROM00:13FA  SUB 8 / JR C  -> restart capture
MAX_WIDTH = 0x17FF   # ROM00:13EA  CP D (D=18h) -> end capture
MAX_ELEMENTS = 128   # ROM00:140F  CP 80h        -> reverse-copy cap

# Code 39.  Nine elements per character, alternating bar/space and
# beginning with a bar; N = narrow, W = wide.  Exactly three of the nine
# are wide in every character.
CODE39_PATTERNS = {
    "0": "NNNWWNWNN", "1": "WNNWNNNNW", "2": "NNWWNNNNW", "3": "WNWWNNNNN",
    "4": "NNNWWNNNW", "5": "WNNWWNNNN", "6": "NNWWWNNNN", "7": "NNNWNNWNW",
    "8": "WNNWNNWNN", "9": "NNWWNNWNN",
    "A": "WNNNNWNNW", "B": "NNWNNWNNW", "C": "WNWNNWNNN", "D": "NNNNWWNNW",
    "E": "WNNNWWNNN", "F": "NNWNWWNNN", "G": "NNNNNWWNW", "H": "WNNNNWWNN",
    "I": "NNWNNWWNN", "J": "NNNNWWWNN", "K": "WNNNNNNWW", "L": "NNWNNNNWW",
    "M": "WNWNNNNWN", "N": "NNNNWNNWW", "O": "WNNNWNNWN", "P": "NNWNWNNWN",
    "Q": "NNNNNNWWW", "R": "WNNNNNWWN", "S": "NNWNNNWWN", "T": "NNNNWNWWN",
    "U": "WWNNNNNNW", "V": "NWWNNNNNW", "W": "WWWNNNNNN", "X": "NWNNWNNNW",
    "Y": "WWNNWNNNN", "Z": "NWWNWNNNN",
    "-": "NWNNNNWNW", ".": "WWNNNNWNN", " ": "NWWNNNWNN", "$": "NWNWNWNNN",
    "/": "NWNWNNNWN", "+": "NWNNNWNWN", "%": "NNNWNWNWN", "*": "NWNNWNWNN",
}

# Pattern -> character, with the pattern as a 9-bit integer, first element
# in bit 8.  This is the exact key the Z80 decoder builds with ADC HL,HL.
_BITS = {}
for _ch, _pat in CODE39_PATTERNS.items():
    _BITS[int("".join("1" if c == "W" else "0" for c in _pat), 2)] = _ch


class Code39Error(ValueError):
    pass


def encode_code39(text, narrow=12, wide=30, gap=None, start_stop=True):
    """Return the element widths for TEXT as a Code 39 symbol.

    The list alternates bar, space, bar, ... beginning with a bar, which
    is what the capture loop records: it arms on the 0->1 edge, so
    element 0 is always the first dark bar after the quiet zone.

    ``gap`` is the inter-character space (default: ``narrow``).  The
    returned list has no trailing quiet zone; ``Wand`` appends that,
    because the firmware never records the element that ends a capture.
    """
    if narrow < MIN_WIDTH:
        raise Code39Error(
            f"narrow width {narrow} is below the firmware minimum {MIN_WIDTH} "
            "(ROM00:13FA SUB 8 restarts the capture)")
    if wide <= narrow:
        raise Code39Error("wide must be greater than narrow")
    if wide > MAX_WIDTH:
        raise Code39Error(f"wide width {wide} exceeds {MAX_WIDTH}")
    if gap is None:
        gap = narrow
    body = text.upper()
    if "*" in body:
        raise Code39Error("'*' is the start/stop character and cannot be data")
    chars = ("*" + body + "*") if start_stop else body
    widths = []
    for index, ch in enumerate(chars):
        pattern = CODE39_PATTERNS.get(ch)
        if pattern is None:
            raise Code39Error(f"{ch!r} is not in the Code 39 character set")
        if index:
            widths.append(gap)
        widths.extend(wide if p == "W" else narrow for p in pattern)
    if len(widths) > MAX_ELEMENTS:
        raise Code39Error(
            f"{len(widths)} elements exceeds the firmware's {MAX_ELEMENTS}-"
            "element reverse-copy limit (ROM00:140F CP 80h)")
    return widths


def decode_code39(widths, strip_start_stop=True):
    """Reference decoder: element widths -> ASCII.  Mirrors the Z80 hook."""
    n = len(widths)
    if n < 9 or (n + 1) % 10:
        raise Code39Error(f"{n} elements is not 10k-1, so not whole Code 39 characters")
    out = []
    for base in range(0, n, 10):
        block = widths[base:base + 9]
        threshold = (min(block) + max(block)) // 2
        key = 0
        for w in block:
            key = (key << 1) | (1 if w > threshold else 0)
        ch = _BITS.get(key)
        if ch is None:
            raise Code39Error(f"element {base}: pattern {key:09b} is not a Code 39 character")
        out.append(ch)
    if strip_start_stop:
        if len(out) < 3 or out[0] != "*" or out[-1] != "*":
            raise Code39Error("symbol is not delimited by the '*' start/stop character")
        if "*" in out[1:-1]:
            raise Code39Error("'*' appears inside the data")
        out = out[1:-1]
    return "".join(out)


class Wand:
    """Level source for port 2Dh bit 0 during one edge capture.

    Feed it element widths in recorded-count units; it hands back one
    sample per ``read()``, holding each element for width-1 samples so
    that the value the firmware pushes equals the width asked for.
    """

    def __init__(self, widths, idle=4, first_level=1, line2=0, tail=None):
        for w in widths:
            if not MIN_WIDTH <= w <= MAX_WIDTH:
                raise Code39Error(
                    f"width {w} outside {MIN_WIDTH}..{MAX_WIDTH}; the firmware "
                    "would restart or end the capture")
        self.widths = list(widths)
        self.idle = idle
        self.first_level = first_level & 1
        self.line2 = 1 if line2 else 0
        # After the last element the level must sit still long enough for
        # the width counter's high byte to reach 18h (ROM00:13EA).
        self.tail = MAX_WIDTH + 64 if tail is None else tail
        self.reads = 0
        self.transitions = 0
        self._schedule = self._build()
        self._index = 0
        self._left = self._schedule[0][1] if self._schedule else 0

    def _build(self):
        """(level, samples) runs.  Width W is held for W-1 samples."""
        runs = []
        idle_level = self.first_level ^ 1
        if self.idle:
            runs.append((idle_level, self.idle))
        level = self.first_level
        for w in self.widths:
            runs.append((level, w - 1))
            level ^= 1
        runs.append((level, self.tail))
        return runs

    def read(self):
        """One sample.  Returns the byte the firmware sees on port 2Dh."""
        self.reads += 1
        while self._left <= 0:
            if self._index + 1 >= len(self._schedule):
                break                      # hold the final level forever
            self._index += 1
            self._left = self._schedule[self._index][1]
            self.transitions += 1
        self._left -= 1
        level = self._schedule[self._index][0]
        return level | (self.line2 << 1)

    @property
    def exhausted(self):
        return self._index + 1 >= len(self._schedule)

    def idle_byte(self):
        """The level to report when no capture is running."""
        return (self.first_level ^ 1) | (self.line2 << 1)


# --------------------------------------------------------------------------
# Z80 decode hook
# --------------------------------------------------------------------------

def _pattern_table_source():
    lines = []
    for ch in sorted(CODE39_PATTERNS, key=lambda c: CODE39_PATTERNS[c]):
        key = int("".join("1" if c == "W" else "0" for c in CODE39_PATTERNS[ch]), 2)
        lines.append(f"    dw {key:#06x}\n    db '{ch}'"
                     if ch != "'" else f"    dw {key:#06x}\n    db 0x27")
    return "\n".join(lines)


_DECODER = r"""
; ---------------------------------------------------------------------------
; Code 39 decode hook for the Micronic 1000 edge-capture front end.
;
; Installed by pointing the hook thunk's address field (ram:FBC2) here;
; ROM00:1467 JP (HL) reaches it through the RST 10h thunk at ram:FBC0.
;
; On entry the parameter block at ram:FBB9 holds
;       FBB9  word  pointer to the width table (ram:F9B5)
;       FBBB  word  element count, as captured
; and the hook returns its result in the same three cells:
;       FBB9  word  pointer to the decoded bytes
;       FBBB  word  number of decoded bytes; zero rejects the scan
; The return address pushed at ROM00:1457 leads to ROM00:1468, which
; copies (FBBB) bytes from (FBB9) into the caller's receive buffer.
; ---------------------------------------------------------------------------

PARAM_PTR   equ 0xFBB9
PARAM_COUNT equ 0xFBBB

    jp  hook

; --- workspace -------------------------------------------------------------
cursor:  dw 0          ; walking pointer into the width table
wmin:    dw 0
wmax:    dw 0
thresh:  dw 0
pattern: dw 0
nchars:  db 0
outlen:  db 0
outptr:  dw 0

hook:
    ld  hl,(PARAM_COUNT)
    ld  a,h
    or  a
    jp  nz,reject             ; count > 255: more elements than the 128-entry
                              ; table can hold, so nothing here is trustworthy
    ld  a,l
    cp  29                    ; *X* is 3 chars = 29 elements: the shortest symbol
    jp  c,reject
    cp  129                   ; ROM00:1409 stores the UNCAPPED element count and
    jp  nc,reject             ; ROM00:1449 passes it on, but ROM00:140F caps the
                              ; reverse copy at 128, so a larger count describes
                              ; a table that was never filled
    inc a                     ; characters are 9 elements + 1 inter-character gap,
    ld  c,a                   ; so a whole symbol has count = 10k-1
    ld  b,0
divide:
    ld  a,c
    cp  10
    jr  c,divided
    sub 10
    ld  c,a
    inc b
    jr  divide
divided:
    or  a
    jp  nz,reject             ; leftover elements: not whole characters
    ld  a,b
    ld  (nchars),a

    ld  hl,(PARAM_PTR)
    ld  (cursor),hl
    ld  hl,outbuf
    ld  (outptr),hl
    xor a
    ld  (outlen),a

    call decode_char          ; start character
    jp  c,reject
    cp  '*'
    jp  nz,reject

    ld  a,(nchars)
    sub 2                     ; drop the start and stop characters
    ld  b,a
data_loop:
    push bc
    call decode_char
    pop bc
    jp  c,reject
    cp  '*'
    jp  z,reject              ; a start/stop character inside the data
    ld  hl,(outptr)
    ld  (hl),a
    inc hl
    ld  (outptr),hl
    ld  hl,outlen
    inc (hl)
    djnz data_loop

    call decode_char          ; stop character
    jp  c,reject
    cp  '*'
    jp  nz,reject

    ld  hl,outbuf
    ld  (PARAM_PTR),hl
    ld  a,(outlen)
    ld  l,a
    ld  h,0
    ld  (PARAM_COUNT),hl
    ret

reject:
    ld  hl,0
    ld  (PARAM_COUNT),hl      ; count 0 tells ROM00:146E to drop the scan
    ret

; --- decode_char -----------------------------------------------------------
; Reads nine widths from (cursor), classifies each as narrow or wide
; against the midpoint of that character's own widest and narrowest
; element, and looks the 9-bit pattern up.
; Out: A = ASCII, carry clear; carry set if the pattern is not Code 39.
; Advances (cursor) by ten elements, stepping over the inter-character gap.
; ---------------------------------------------------------------------------
decode_char:
    ld  hl,(cursor)
    push hl                   ; keep the block start for the second pass
    call next_width
    ld  (wmin),de
    ld  (wmax),de
    ld  b,8
minmax:
    push bc
    call next_width
    ld  hl,(wmin)
    or  a
    sbc hl,de
    jr  c,not_min
    ld  hl,wmin
    ld  (hl),e
    inc hl
    ld  (hl),d
not_min:
    ld  hl,(wmax)
    or  a
    sbc hl,de
    jr  nc,not_max
    ld  hl,wmax
    ld  (hl),e
    inc hl
    ld  (hl),d
not_max:
    pop bc
    djnz minmax

    ld  hl,(wmin)
    ld  de,(wmax)
    add hl,de
    srl h
    rr  l
    ld  (thresh),hl           ; midpoint of the narrowest and widest element

    pop hl
    ld  (cursor),hl           ; rewind to the start of this character
    ld  hl,0
    ld  (pattern),hl
    ld  b,9
classify:
    push bc
    call next_width
    ld  hl,(thresh)
    or  a
    sbc hl,de                 ; carry set when the element is wider
    ld  hl,(pattern)
    adc hl,hl                 ; shift that decision straight into the key
    ld  (pattern),hl
    pop bc
    djnz classify

    ld  hl,(cursor)           ; step over the inter-character gap
    inc hl
    inc hl
    ld  (cursor),hl

    ld  de,(pattern)
    ld  hl,table
    ld  b,44
lookup:
    ld  a,(hl)
    cp  e
    jr  nz,lookup_next
    inc hl
    ld  a,(hl)
    dec hl
    cp  d
    jr  z,lookup_hit
lookup_next:
    inc hl
    inc hl
    inc hl
    djnz lookup
    scf
    ret
lookup_hit:
    inc hl
    inc hl
    ld  a,(hl)
    or  a                     ; clears carry: success
    ret

; next_width: DE = word at (cursor); (cursor) += 2.
next_width:
    ld  hl,(cursor)
    ld  e,(hl)
    inc hl
    ld  d,(hl)
    inc hl
    ld  (cursor),hl
    ret

; --- pattern table: 44 x {9-bit pattern word, ASCII} -----------------------
table:
%%TABLE%%

outbuf:
    ds 64
"""


def decoder_source():
    """The Code 39 decode hook as Z80 assembly source text."""
    return _DECODER.replace("%%TABLE%%", _pattern_table_source())


def assemble_decoder(origin):
    """Assemble the decode hook for ORIGIN.  Returns (bytes, symbols)."""
    from .z80asm import assemble
    return assemble(decoder_source(), origin=origin)


_PROBE = r"""
; ---------------------------------------------------------------------------
; Decode-hook probe.  Records the whole machine state the firmware hands the
; hook, then rejects the scan so the delivery path is not entered.
; Every recorded cell is read back by the harness through the symbol table.
; ---------------------------------------------------------------------------
    jp  probe

p_af:    dw 0
p_bc:    dw 0
p_de:    dw 0
p_hl:    dw 0
p_ix:    dw 0
p_iy:    dw 0
p_sp:    dw 0
p_bank:  db 0
p_calls: db 0
p_param: ds 4          ; FBB9..FBBC exactly as the hook received them
p_stk:   ds 16         ; 16 bytes from the entry stack pointer

probe:
    ld  (p_hl),hl
    ld  (p_de),de
    ld  (p_bc),bc
    ld  (p_sp),sp
    ld  (p_ix),ix
    ld  (p_iy),iy
    push af
    pop hl
    ld  (p_af),hl
    ld  a,(0xF791)     ; g_bBankShadowP47: which bank is mapped in the hook
    ld  (p_bank),a
    ld  hl,p_calls
    inc (hl)
    ld  hl,(p_sp)
    ld  de,p_stk
    ld  bc,16
    ldir
    ld  hl,0xFBB9
    ld  de,p_param
    ld  bc,4
    ldir
    ld  hl,0
    ld  (0xFBBB),hl    ; reject, so ROM00:146E takes the re-arm path
    ret
"""


def probe_source():
    """Z80 source for the decode-hook probe."""
    return _PROBE


def assemble_probe(origin):
    """Assemble the probe for ORIGIN.  Returns (bytes, symbols)."""
    from .z80asm import assemble
    return assemble(_PROBE, origin=origin)
