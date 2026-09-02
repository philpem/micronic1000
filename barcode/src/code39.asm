;; ---------------------------------------------------------------------------
;; code39.asm -- Code 39 decoder.
;;
;; Code 39 encodes each character as nine elements -- five bars and four
;; spaces, alternating and starting with a bar -- of which exactly three are
;; wide.  Characters are separated by one narrow inter-character gap, so a
;; symbol of k characters is 10k-1 elements.  Every symbol begins and ends
;; with the start/stop character '*', which is not valid inside the data.
;;
;; The decoder needs no absolute width calibration.  For each character it
;; takes the narrowest and widest of that character's OWN nine elements and
;; thresholds at the midpoint, so a scan that speeds up or slows down across
;; the symbol still decodes -- which matters for a hand-drawn wand.
;;
;; Because a pattern with no table entry simply fails, Code 39 is
;; self-checking: a misread rejects rather than producing wrong data.
;; ---------------------------------------------------------------------------

    include "dipos.inc"

    public  code39_decode
    extern  width_table, element_count, out_buffer

;; Shortest possible symbol is '*X*': three characters, 29 elements.
C39_MIN_ELEMENTS    equ 29
C39_ELEMS_PER_CHAR  equ 9
C39_CHAR_STRIDE     equ 10         ; nine elements plus the gap

;; ---------------------------------------------------------------------------
;; code39_decode
;;
;; Out: carry clear and HL = decoded byte count, with the bytes in
;;      out_buffer; carry set if this is not a valid Code 39 symbol.
;; ---------------------------------------------------------------------------
code39_decode:
    ld      hl,(element_count)
    ld      a,h
    or      a
    jp      nz,c39_reject             ; > 255 elements: not a symbol we can hold
    ld      a,l
    cp      C39_MIN_ELEMENTS
    jp      c,c39_reject

;; A whole symbol has count = 10k-1, so count+1 must divide by ten exactly.
;; The quotient is the character count, start and stop included.
    inc     a
    ld      c,a
    ld      b,0
c39_divide:
    ld      a,c
    cp      C39_CHAR_STRIDE
    jr      c,c39_divided
    sub     C39_CHAR_STRIDE
    ld      c,a
    inc     b
    jr      c39_divide
c39_divided:
    or      a
    jp      nz,c39_reject             ; a remainder means partial characters
    ld      a,b
    ld      (nchars),a

    ld      hl,(width_table)
    ld      (c39_cursor),hl
    ld      hl,out_buffer
    ld      (c39_outptr),hl
    xor     a
    ld      (outlen),a

;; --- the start character ---------------------------------------------------
    call    decode_char
    jp      c,c39_reject
    cp      '*'
    jp      nz,c39_reject

;; --- the data --------------------------------------------------------------
    ld      a,(nchars)
    sub     2                      ; less the start and stop characters
    ld      b,a
c39_data_loop:
    push    bc
    call    decode_char
    pop     bc
    jp      c,c39_reject
    cp      '*'
    jp      z,c39_reject              ; a delimiter inside the data
    ld      hl,(c39_outptr)
    ld      (hl),a
    inc     hl
    ld      (c39_outptr),hl
    ld      hl,outlen
    inc     (hl)
    djnz    c39_data_loop

;; --- the stop character ----------------------------------------------------
    call    decode_char
    jp      c,c39_reject
    cp      '*'
    jp      nz,c39_reject

    ld      a,(outlen)
    ld      l,a
    ld      h,0
    or      a                      ; clear carry: decoded
    ret

c39_reject:
    scf
    ret

;; ---------------------------------------------------------------------------
;; decode_char -- decode the character at (c39_cursor).
;;
;; Two passes over the same nine elements: the first finds the narrowest and
;; widest so we can threshold at their midpoint, the second turns each
;; element into one bit of a nine-bit key.  Then a linear search of the
;; pattern table.
;;
;; Out: A = ASCII and carry clear, or carry set if the pattern is not a
;;      Code 39 character.  Advances (c39_cursor) past the inter-character gap.
;; ---------------------------------------------------------------------------
decode_char:
    ld      hl,(c39_cursor)
    push    hl                     ; remember where this character starts

;; --- pass one: narrowest and widest ---------------------------------------
    call    c39_next_width
    ld      (wmin),de
    ld      (wmax),de
    ld      b,C39_ELEMS_PER_CHAR-1
c39_minmax:
    push    bc
    call    c39_next_width
    ld      hl,(wmin)
    or      a
    sbc     hl,de
    jr      c,c39_not_min
    ld      hl,wmin
    ld      (hl),e
    inc     hl
    ld      (hl),d
c39_not_min:
    ld      hl,(wmax)
    or      a
    sbc     hl,de
    jr      nc,c39_not_max
    ld      hl,wmax
    ld      (hl),e
    inc     hl
    ld      (hl),d
c39_not_max:
    pop     bc
    djnz    c39_minmax

    ld      hl,(wmin)
    ld      de,(wmax)
    add     hl,de
    srl     h
    rr      l
    ld      (thresh),hl            ; midpoint of this character's own extremes

;; --- pass two: nine elements into a nine-bit key --------------------------
    pop     hl
    ld      (c39_cursor),hl            ; rewind to the start of the character
    ld      hl,0
    ld      (pattern),hl
    ld      b,C39_ELEMS_PER_CHAR
c39_classify:
    push    bc
    call    c39_next_width
    ld      hl,(thresh)
    or      a
    sbc     hl,de                  ; carry set when this element is the wider
    ld      hl,(pattern)
    adc     hl,hl                  ; shift the decision straight into the key
    ld      (pattern),hl
    pop     bc
    djnz    c39_classify

    ld      hl,(c39_cursor)            ; step over the inter-character gap
    inc     hl
    inc     hl
    ld      (c39_cursor),hl

;; --- look the key up -------------------------------------------------------
    ld      de,(pattern)
    ld      hl,c39_table
    ld      a,(c39_count)
    ld      b,a
c39_lookup:
    ld      a,(hl)
    cp      e
    jr      nz,c39_lookup_next
    inc     hl
    ld      a,(hl)
    dec     hl
    cp      d
    jr      z,c39_lookup_hit
c39_lookup_next:
    inc     hl
    inc     hl
    inc     hl
    djnz    c39_lookup
    scf                            ; no such pattern
    ret
c39_lookup_hit:
    inc     hl
    inc     hl
    ld      a,(hl)
    or      a                      ; clears carry: success
    ret

;; ---------------------------------------------------------------------------
;; c39_next_width -- DE = the 16-bit width at (c39_cursor); (c39_cursor) += 2.
;; ---------------------------------------------------------------------------
c39_next_width:
    ld      hl,(c39_cursor)
    ld      e,(hl)
    inc     hl
    ld      d,(hl)
    inc     hl
    ld      (c39_cursor),hl
    ret

;; --- workspace -------------------------------------------------------------
c39_cursor:     defw 0                 ; walking pointer into the width table
wmin:       defw 0
wmax:       defw 0
thresh:     defw 0
pattern:    defw 0
nchars:     defb 0                 ; characters in the symbol, delimiters included
outlen:     defb 0
c39_outptr:     defw 0

    include "code39_table.inc"
