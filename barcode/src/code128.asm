;; ---------------------------------------------------------------------------
;; code128.asm -- Code 128, code sets A, B and C.
;;
;; Six elements per symbol character -- three bars, three spaces -- always
;; eleven modules, plus a seven-element thirteen-module stop.  A symbol of
;; n characters is 6n + 7 elements.
;;
;; This is a delta code: an element is 1..4 modules and means nothing
;; absolutely.  But every character is eleven modules, so each one carries
;; its own calibration -- the best of any symbology here, and the reason a
;; long Code 128 survives a scan that speeds up badly.
;;
;; Structure: start, data, checksum, stop.  The checksum is the start value
;; plus each data value times its position, modulo 103, which makes Code 128
;; genuinely self-checking -- unlike Codabar or ITF.
;;
;; Code sets.  A carries control characters and upper case, B printable
;; ASCII, C two digits per character.  The start value picks one and values
;; 99/100/101 switch between them; 98 SHIFTs a single character into the
;; other of A/B.  FNC1-4 carry no data and are skipped rather than emitted,
;; which is a deliberate simplification: a host wanting GS1 application
;; identifiers would need FNC1 surfaced.
;; ---------------------------------------------------------------------------

    include "dipos.inc"

    public  code128_decode
    extern  width_table, element_count, out_buffer
    extern  scratch, reverse_elements

C128_ELEMS      equ 6              ; per symbol character
C128_STOP_ELEMS equ 7
C128_MIN        equ 19             ; start, checksum, stop and nothing else

;; Each character is eleven modules; the classification below multiplies an
;; element by 22 and the character's own total by up to 7, so an
;; over-large character would overflow sixteen bits.  A capture that wide
;; cannot be a real symbol anyway.
C128_MAX_TOTAL  equ 1E00h

START_A         equ 103
START_B         equ 104
START_C         equ 105
CODE_C          equ 99
CODE_B          equ 100
CODE_A          equ 101
SHIFT           equ 98

;; ---------------------------------------------------------------------------
;; code128_decode
;; Out: carry clear and HL = byte count, or carry set.
;; ---------------------------------------------------------------------------
code128_decode:
    ld      hl,(width_table)
    call    c128_attempt
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
    jp      c128_attempt

c128_attempt:
    ld      (c128_cursor),hl
    ld      hl,(element_count)
    ld      a,h
    or      a
    jp      nz,c128_reject
    ld      a,l
    cp      C128_MIN
    jp      c,c128_reject
    sub     C128_STOP_ELEMS

;; The rest must be a whole number of six-element characters.
    ld      c,a
    ld      b,0
c128_divide:
    ld      a,c
    cp      C128_ELEMS
    jr      c,c128_divided
    sub     C128_ELEMS
    ld      c,a
    inc     b
    jr      c128_divide
c128_divided:
    or      a
    jp      nz,c128_reject
    ld      a,b
    cp      3                      ; start, checksum and at least nothing
    jp      c,c128_reject
    ld      (c128_chars),a

;; --- the start character ---------------------------------------------------
    call    c128_symbol
    ret     c
    cp      START_A
    jr      z,c128_start_ok
    cp      START_B
    jr      z,c128_start_ok
    cp      START_C
    jp      nz,c128_reject
c128_start_ok:
    ld      (c128_set),a           ; 103/104/105 -- normalised below
    ld      (c128_sum),a           ; the checksum starts at the start value
    sub     START_A
    ld      (c128_set),a           ; now 0 = A, 1 = B, 2 = C
    xor     a
    ld      (c128_shift),a
    ld      hl,out_buffer
    ld      (c128_outptr),hl
    xor     a
    ld      (c128_len),a

;; --- the data, then the checksum -------------------------------------------
;; Every character but the last two is data; the last is the checksum, and
;; the stop follows it.
    ld      a,(c128_chars)
    sub     2
    ld      b,a
    ld      c,1                    ; position weight for the checksum
c128_data_loop:
    push    bc
    call    c128_symbol
    jr      c,c128_data_fail
    ld      (c128_value),a
    pop     bc
    push    bc
    call    c128_weigh             ; checksum += position * value
    call    c128_translate         ; may emit, switch set, or do nothing
    jr      c,c128_data_fail
    pop     bc
    inc     c
    djnz    c128_data_loop
    jr      c128_checksum
c128_data_fail:
    pop     bc
    scf
    ret

;; --- verify the checksum ---------------------------------------------------
c128_checksum:
    call    c128_symbol
    ret     c
    ld      c,a                    ; the transmitted checksum
;; The running sum is sixteen bits -- start + sum of position*value reaches
;; a few thousand on a symbol of any length -- so the modulo must be too.
    ld      hl,(c128_sum)
    ld      de,103
c128_mod103:
    or      a
    sbc     hl,de
    jr      nc,c128_mod103
    add     hl,de                  ; one subtraction too far
    ld      a,l
    cp      c
    jp      nz,c128_reject

;; --- the stop --------------------------------------------------------------
;; Seven elements, thirteen modules, checked against the literal pattern.
    call    c128_total7
    ld      hl,code128_stop
    ld      b,C128_STOP_ELEMS
c128_stop_loop:
    push    bc
    push    hl
    call    c128_next
    pop     hl
    push    hl
    call    c128_classify13        ; A = this element in modules
    pop     hl
    cp      (hl)
    jr      nz,c128_stop_bad
    inc     hl
    pop     bc
    djnz    c128_stop_loop

    ld      a,(c128_len)
    ld      l,a
    ld      h,0
    or      a
    ret
c128_stop_bad:
    pop     bc
    scf
    ret

c128_reject:
    scf
    ret

;; --- checksum += C * value -------------------------------------------------
c128_weigh:
    ld      a,(c128_value)
    ld      b,c
    ld      hl,0
c128_weigh_loop:
    ld      e,a
    ld      d,0
    add     hl,de
    djnz    c128_weigh_loop
    ld      de,(c128_sum)
    add     hl,de
    ld      (c128_sum),hl
    ret

;; ---------------------------------------------------------------------------
;; c128_translate -- turn (c128_value) into output, or act on it.
;;
;; Out: carry set only on a value this decoder will not handle.
;; ---------------------------------------------------------------------------
c128_translate:
    ld      a,(c128_set)
    cp      2
    jr      z,c128_set_c

;; --- code sets A and B -----------------------------------------------------
    ld      a,(c128_value)
    cp      96
    jr      c,c128_ab_char         ; 0..95 carry data

    cp      SHIFT
    jr      nz,c128_ab_not_shift
    ld      a,1
    ld      (c128_shift),a
    or      a
    ret
c128_ab_not_shift:
    cp      CODE_C
    jr      nz,c128_ab_not_c
    ld      a,2
    ld      (c128_set),a
    or      a
    ret
c128_ab_not_c:
    cp      CODE_B
    jr      z,c128_ab_switch
    cp      CODE_A
    jr      z,c128_ab_switch
    or      a                      ; FNC1-4: carry no data, so skip
    ret
c128_ab_switch:
;; 100 means "code B" while in A and "FNC4" while in B, and 101 the mirror.
;; Either way the useful reading is: switch to the other of A and B.
    ld      a,(c128_set)
    xor     1
    ld      (c128_set),a
    or      a
    ret

c128_ab_char:
;; In B a value is ASCII 32+v.  In A, 0..63 is 32+v as well and 64..95 are
;; the control characters 0..31.
    ld      b,a
    ld      a,(c128_set)
    ld      c,a
    ld      a,(c128_shift)
    or      a
    jr      z,c128_ab_noshift
    xor     a
    ld      (c128_shift),a
    ld      a,c
    xor     1                      ; this one character only
    ld      c,a
c128_ab_noshift:
    ld      a,c
    or      a
    jr      nz,c128_ab_setb
    ld      a,b
    cp      64
    jr      c,c128_ab_setb
    sub     64                     ; a control character
    jr      c128_emit
c128_ab_setb:
    ld      a,b
    add     a,32
    jr      c128_emit

;; --- code set C: two digits per value --------------------------------------
c128_set_c:
    ld      a,(c128_value)
    cp      100
    jr      c,c128_c_digits
    cp      CODE_B
    jr      nz,c128_c_not_b
    ld      a,1
    ld      (c128_set),a
    or      a
    ret
c128_c_not_b:
    cp      CODE_A
    jr      nz,c128_c_other
    xor     a
    ld      (c128_set),a
    or      a
    ret
c128_c_other:
    or      a                      ; FNC1 and friends
    ret
c128_c_digits:
    ld      b,0
c128_c_tens:
    cp      10
    jr      c,c128_c_done
    sub     10
    inc     b
    jr      c128_c_tens
c128_c_done:
    push    af
    ld      a,b
    add     a,'0'
    call    c128_emit
    pop     af
    add     a,'0'
;; falls into c128_emit

c128_emit:
    ld      hl,(c128_outptr)
    ld      (hl),a
    inc     hl
    ld      (c128_outptr),hl
    ld      hl,c128_len
    inc     (hl)
    or      a
    ret

;; ---------------------------------------------------------------------------
;; c128_symbol -- the six elements at (c128_cursor) into a symbol value.
;;
;; Each character is eleven modules, so its own six widths calibrate it.
;; Out: A = 0..105 and carry clear, or carry set.
;; ---------------------------------------------------------------------------
c128_symbol:
    ld      hl,(c128_cursor)
    push    hl
    call    c128_total6            ; (c128_total) = the character's modules
    pop     hl
    ld      (c128_cursor),hl       ; rewind and classify

    ld      hl,0
    ld      (c128_key),hl
    ld      b,C128_ELEMS
c128_sym_loop:
    push    bc
    call    c128_next
    call    c128_classify11        ; A = 1..4
    dec     a
    ld      c,a
    ld      hl,(c128_key)
    add     hl,hl
    add     hl,hl                  ; make room for two bits
    ld      a,l
    or      c
    ld      l,a
    ld      (c128_key),hl
    pop     bc
    djnz    c128_sym_loop

    ld      de,(c128_key)
    ld      hl,code128_table
    ld      b,106
    ld      c,0
c128_lookup:
    ld      a,(hl)
    cp      e
    jr      nz,c128_lookup_next
    inc     hl
    ld      a,(hl)
    dec     hl
    cp      d
    jr      z,c128_lookup_hit
c128_lookup_next:
    inc     hl
    inc     hl
    inc     c
    djnz    c128_lookup
    scf
    ret
c128_lookup_hit:
    ld      a,c
    or      a
    ret

;; --- sum the next six elements without moving the cursor -------------------
c128_total6:
    ld      b,C128_ELEMS
    jr      c128_total
c128_total7:
    ld      b,C128_STOP_ELEMS
c128_total:
    ld      hl,(c128_cursor)
    ld      (c128_scan),hl
    ld      hl,0
    ld      (c128_total_v),hl
c128_total_loop:
    push    bc
    ld      hl,(c128_scan)
    ld      e,(hl)
    inc     hl
    ld      d,(hl)
    inc     hl
    ld      (c128_scan),hl
    ld      hl,(c128_total_v)
    add     hl,de
    ld      (c128_total_v),hl
    pop     bc
    djnz    c128_total_loop
    ld      hl,(c128_total_v)
    ld      de,C128_MAX_TOTAL
    or      a
    sbc     hl,de
    ret     c
    ld      hl,0                   ; too wide to classify without overflow
    ld      (c128_total_v),hl
    ret

;; ---------------------------------------------------------------------------
;; c128_classify11 / c128_classify13 -- DE = an element; A = its modules.
;;
;; The character spans (c128_total_v) over 11 modules (13 for the stop), so
;; an element of w modules satisfies  w <= k + 0.5  <=>  2*11*e <= (2k+1)*T.
;; ---------------------------------------------------------------------------
c128_classify11:
    ld      a,11
    jr      c128_classify
c128_classify13:
    ld      a,13
c128_classify:
    ld      (c128_span),a
;; HL = 2 * span * element
    ld      hl,0
    ld      b,a
c128_cl_mul:
    add     hl,de
    djnz    c128_cl_mul
    add     hl,hl
    ld      (c128_scaled),hl

    ld      c,1                    ; candidate module count
c128_cl_try:
    ld      a,c
    add     a,a
    inc     a                      ; 2k+1
    ld      b,a
    ld      hl,0
    ld      de,(c128_total_v)
c128_cl_acc:
    add     hl,de
    djnz    c128_cl_acc            ; HL = (2k+1) * total
    ld      de,(c128_scaled)
    or      a
    sbc     hl,de
    jr      nc,c128_cl_found       ; scaled <= (2k+1)*total
    inc     c
    ld      a,c
    cp      4
    jr      c,c128_cl_try
c128_cl_found:
    ld      a,c
    ret

;; --- DE = the next element; advances the cursor ----------------------------
c128_next:
    ld      hl,(c128_cursor)
    ld      e,(hl)
    inc     hl
    ld      d,(hl)
    inc     hl
    ld      (c128_cursor),hl
    ret

;; --- workspace -------------------------------------------------------------
c128_cursor:  defw 0
c128_scan:    defw 0
c128_total_v: defw 0               ; the current character's total width
c128_scaled:  defw 0
c128_key:     defw 0
c128_sum:     defw 0               ; running checksum
c128_outptr:  defw 0
c128_chars:   defb 0
c128_value:   defb 0
c128_set:     defb 0               ; 0 = A, 1 = B, 2 = C
c128_shift:   defb 0
c128_span:    defb 0
c128_len:     defb 0

    include "code128_table.inc"
