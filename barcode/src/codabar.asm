;; ---------------------------------------------------------------------------
;; codabar.asm -- Codabar.
;;
;; Seven elements per character -- four bars and three spaces, alternating
;; and beginning with a bar -- separated by a narrow inter-character gap.
;; A symbol of k characters is therefore 8k - 1 elements.
;;
;; Unlike Code 39 the number of wide elements per character is not fixed, so
;; there is no "exactly three wide" invariant to lean on.  What Codabar does
;; give is dedicated delimiters: A, B, C and D are start/stop characters and
;; may not appear in the data.  A symbol must open and close with one, and
;; they are the only structural check available.
;;
;; The delimiters are returned along with the data, because which pair was
;; used carries meaning in some applications -- notably the four are used to
;; distinguish label types in blood banking and libraries.  Stripping them
;; would discard that.
;;
;; Wide/narrow, so no absolute calibration: each character is thresholded at
;; the midpoint of its own seven elements.
;; ---------------------------------------------------------------------------

    include "dipos.inc"

    public  codabar_decode
    extern  width_table, element_count, out_buffer
    extern  scratch, reverse_elements, symbology

CODABAR_ELEMS   equ 7              ; per character
CODABAR_STRIDE  equ 8              ; with the inter-character gap
CODABAR_MIN     equ 23             ; three characters: A0B

;; ---------------------------------------------------------------------------
;; codabar_decode
;; Out: carry clear and HL = character count, or carry set.
;; ---------------------------------------------------------------------------
codabar_decode:
    ld      hl,(width_table)
    call    cbr_attempt
    ret     nc

    ld      hl,(element_count)     ; try it backwards
    ld      a,l
    or      a
    ret     z
    ld      b,a
    dec     hl
    add     hl,hl
    ld      de,(width_table)
    add     hl,de
    ld      de,scratch
    call    reverse_elements
    ld      hl,scratch
    jp      cbr_attempt

cbr_attempt:
    ld      (cbr_base),hl
    ld      hl,(element_count)
    ld      a,h
    or      a
    jp      nz,cbr_reject
    ld      a,l
    cp      CODABAR_MIN
    jp      c,cbr_reject

;; A whole symbol is 8k-1 elements, so count+1 must divide by eight.
    inc     a
    ld      c,a
    ld      b,0
cbr_divide:
    ld      a,c
    cp      CODABAR_STRIDE
    jr      c,cbr_divided
    sub     CODABAR_STRIDE
    ld      c,a
    inc     b
    jr      cbr_divide
cbr_divided:
    or      a
    jp      nz,cbr_reject
    ld      a,b
    ld      (cbr_chars),a

    ld      hl,(cbr_base)
    ld      (cbr_cursor),hl
    ld      hl,out_buffer
    ld      (cbr_outptr),hl

;; --- the start delimiter ---------------------------------------------------
    call    cbr_char
    jp      c,cbr_reject
    call    cbr_is_delimiter
    jp      c,cbr_reject
    call    cbr_emit

;; --- the data --------------------------------------------------------------
    ld      a,(cbr_chars)
    sub     2
    ld      b,a
cbr_data_loop:
    push    bc
    call    cbr_char
    pop     bc
    jp      c,cbr_reject
    call    cbr_is_delimiter
    jp      nc,cbr_reject          ; a delimiter inside the data
    push    bc
    call    cbr_emit
    pop     bc
    djnz    cbr_data_loop

;; --- the stop delimiter ----------------------------------------------------
    call    cbr_char
    jp      c,cbr_reject
    call    cbr_is_delimiter
    jp      c,cbr_reject
    call    cbr_emit

    ld      a,SYM_CODABAR
    ld      (symbology),a
    ld      a,(cbr_chars)
    ld      l,a
    ld      h,0
    or      a
    ret

cbr_reject:
    scf
    ret

;; --- carry CLEAR if A is one of the A-D delimiters -------------------------
cbr_is_delimiter:
    cp      'A'
    jr      c,cbr_not_delim
    cp      'E'
    jr      nc,cbr_not_delim
    or      a                      ; clears carry
    ret
cbr_not_delim:
    scf
    ret

cbr_emit:
    ld      hl,(cbr_outptr)
    ld      (hl),a
    inc     hl
    ld      (cbr_outptr),hl
    ret

;; ---------------------------------------------------------------------------
;; cbr_char -- decode the character at (cbr_cursor).
;;
;; Two passes over its seven elements: the first for the extremes, the
;; second turning each into a bit.  Then the cursor steps over the gap.
;;
;; Out: A = ASCII and carry clear, or carry set.
;; ---------------------------------------------------------------------------
cbr_char:
    ld      hl,(cbr_cursor)
    push    hl

    call    cbr_next
    ld      (cbr_min),de
    ld      (cbr_max),de
    ld      b,CODABAR_ELEMS-1
cbr_minmax:
    push    bc
    call    cbr_next
    ld      hl,(cbr_min)
    or      a
    sbc     hl,de
    jr      c,cbr_not_min
    ld      hl,cbr_min
    ld      (hl),e
    inc     hl
    ld      (hl),d
cbr_not_min:
    ld      hl,(cbr_max)
    or      a
    sbc     hl,de
    jr      nc,cbr_not_max
    ld      hl,cbr_max
    ld      (hl),e
    inc     hl
    ld      (hl),d
cbr_not_max:
    pop     bc
    djnz    cbr_minmax

    ld      hl,(cbr_min)
    ld      de,(cbr_max)
    add     hl,de
    srl     h
    rr      l
    ld      (cbr_thresh),hl

    pop     hl
    ld      (cbr_cursor),hl        ; rewind
    xor     a
    ld      (cbr_pattern),a
    ld      b,CODABAR_ELEMS
cbr_classify:
    push    bc
    call    cbr_next
    ld      hl,(cbr_thresh)
    or      a
    sbc     hl,de                  ; carry set when this element is wider
    ld      a,(cbr_pattern)
    adc     a,a
    ld      (cbr_pattern),a
    pop     bc
    djnz    cbr_classify

    ld      hl,(cbr_cursor)        ; step over the inter-character gap
    inc     hl
    inc     hl
    ld      (cbr_cursor),hl

    ld      a,(cbr_pattern)
    ld      c,a
    ld      hl,codabar_table
    ld      a,(codabar_count)
    ld      b,a
cbr_lookup:
    ld      a,(hl)
    cp      c
    jr      z,cbr_lookup_hit
    inc     hl
    inc     hl
    djnz    cbr_lookup
    scf
    ret
cbr_lookup_hit:
    inc     hl
    ld      a,(hl)
    or      a                      ; clears carry
    ret

cbr_next:
    ld      hl,(cbr_cursor)
    ld      e,(hl)
    inc     hl
    ld      d,(hl)
    inc     hl
    ld      (cbr_cursor),hl
    ret

;; --- workspace -------------------------------------------------------------
cbr_base:    defw 0
cbr_cursor:  defw 0
cbr_min:     defw 0
cbr_max:     defw 0
cbr_thresh:  defw 0
cbr_outptr:  defw 0
cbr_chars:   defb 0
cbr_pattern: defb 0

    include "codabar_table.inc"
