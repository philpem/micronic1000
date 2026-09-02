;; ---------------------------------------------------------------------------
;; upc.asm -- EAN-13 and UPC-A decoder, either scan direction.
;;
;; Both standards are the same 95 modules, which the capture records as 59
;; elements:
;;
;;      elements  0..2    left guard      3 modules  (bar space bar)
;;                3..26   six digits      6 x 7 modules, 4 elements each
;;                27..31  centre guard    5 modules
;;                32..55  six digits      6 x 7 modules
;;                56..58  right guard     3 modules
;;
;; UPC-A is EAN-13 with a leading zero, and the two check-digit rules agree
;; under that reading, so this decodes in thirteen digits throughout and
;; emits the twelve-digit form when the leading digit is zero.
;;
;; THREE CODES, ONE TABLE.  Right-hand digits use the R code, the bitwise
;; complement of the left-hand L code -- complementing swaps bars for spaces
;; but leaves the run lengths alone, so L and R share a table.  The G code,
;; used by some left-hand digits in EAN-13, is R reversed, so its run lengths
;; are the L run lengths *backwards*.  That is how a digit's parity is
;; recovered: look the quad up as it stands for L, and reversed for G.
;;
;; THE THIRTEENTH DIGIT is drawn nowhere.  It exists only in which of the six
;; left-hand digits use G, which is what ean_parity translates.
;;
;; EITHER DIRECTION.  A wand can be drawn right-to-left, and the symbol is
;; structurally symmetric -- guard, six, centre, six, guard -- so a reversed
;; scan is a forward scan with the element list backwards.  We try forward,
;; and on failure reverse into a scratch buffer and try once more.
;;
;; NOT self-checking.  Any four elements classify to some pattern, so the
;; check digit is the only thing between a misread and a plausible wrong
;; number.  It is verified before anything is published.
;; ---------------------------------------------------------------------------

    include "dipos.inc"

    public  upc_decode
    extern  width_table, element_count, out_buffer

UPC_ELEMENTS    equ 59
EAN_DIGITS      equ 13
LEFT_DIGITS     equ 6

;; The module width is bounded by the capture itself: the widest element is
;; four modules and ROM00:13EA ends a capture at 1800h counts, so three
;; modules cannot exceed 1200h -- which is what keeps 7*guard inside 16 bits.
UPC_MAX_GUARD   equ 1200h

;; ---------------------------------------------------------------------------
;; upc_decode
;;
;; Out: carry clear and HL = 12 or 13, with that many ASCII digits in
;;      out_buffer; carry set if this is neither an EAN-13 nor a UPC-A.
;; ---------------------------------------------------------------------------
upc_decode:
    ld      hl,(element_count)
    ld      de,UPC_ELEMENTS
    or      a
    sbc     hl,de
    jp      nz,upc_reject          ; both standards are exactly 59 elements

;; --- first pass: as scanned --------------------------------------------
    ld      hl,(width_table)
    call    upc_attempt
    ret     nc

;; --- second pass: the scan reversed ------------------------------------
;; A right-to-left scan produces the same elements backwards, so reversing
;; the list turns it into a symbol this decoder already understands.
    call    upc_reverse
    ld      hl,scratch
    call    upc_attempt
    ret

upc_reject:
    scf
    ret

;; ---------------------------------------------------------------------------
;; upc_reverse -- copy the width table into `scratch`, back to front.
;; ---------------------------------------------------------------------------
upc_reverse:
    ld      hl,(width_table)
    ld      de,UPC_ELEMENTS*2-2
    add     hl,de                  ; -> the last element
    ld      de,scratch
    ld      b,UPC_ELEMENTS
upc_rev_loop:
    ld      a,(hl)
    inc     hl
    ld      c,(hl)                 ; a 16-bit width, still little-endian
    ld      (de),a
    inc     de
    ld      a,c
    ld      (de),a
    inc     de
    dec     hl
    dec     hl
    dec     hl                     ; back up one whole element
    djnz    upc_rev_loop
    ret

;; ---------------------------------------------------------------------------
;; upc_attempt -- decode the 59 elements starting at HL.
;;
;; Out: carry clear and HL = digit count, or carry set.
;; ---------------------------------------------------------------------------
upc_attempt:
    ld      (upc_cursor),hl

;; --- module width, from the left guard ---------------------------------
;; The guard's three elements are one module each, so their sum is three
;; modules.  Working in units of "three modules" avoids a division.
    call    upc_next_width
    ld      (guard),de
    call    upc_next_width
    ld      hl,(guard)
    add     hl,de
    ld      (guard),hl
    call    upc_next_width
    ld      hl,(guard)
    add     hl,de
    ld      (guard),hl

    ld      de,UPC_MAX_GUARD
    or      a
    sbc     hl,de
    jp      nc,upc_reject          ; implausibly wide; also keeps 7S in range

;; --- classification thresholds -----------------------------------------
;; An element of w modules is classified by comparing 6w against multiples
;; of the guard sum S (= 3 modules):
;;      w <= 1.5 modules  <=>  6w <= 3S
;;      w <= 2.5 modules  <=>  6w <= 5S
;;      w <= 3.5 modules  <=>  6w <= 7S
    ld      hl,(guard)
    ld      d,h
    ld      e,l
    add     hl,hl                  ; 2S
    add     hl,de                  ; 3S
    ld      (thr3),hl
    add     hl,de
    add     hl,de                  ; 5S
    ld      (thr5),hl
    add     hl,de
    add     hl,de                  ; 7S
    ld      (thr7),hl

;; --- the six left-hand digits, recording parity as we go ----------------
    ld      hl,digits+1            ; digits[0] is the leading digit, filled last
    ld      (upc_outptr),hl
    xor     a
    ld      (parity),a
    ld      b,LEFT_DIGITS
upc_left_loop:
    push    bc
    call    decode_digit_lr        ; A = value, carry set on failure
    pop     bc
    ret     c
    ld      hl,(upc_outptr)
    ld      (hl),a
    inc     hl
    ld      (upc_outptr),hl
    djnz    upc_left_loop

;; --- step over the centre guard ----------------------------------------
    ld      b,5
upc_skip_centre:
    push    bc
    call    upc_next_width
    pop     bc
    djnz    upc_skip_centre

;; --- the six right-hand digits, R code, no parity to record -------------
    ld      b,LEFT_DIGITS
upc_right_loop:
    push    bc
    call    decode_digit           ; plain lookup; R shares L's run lengths
    pop     bc
    ret     c
    ld      hl,(upc_outptr)
    ld      (hl),a
    inc     hl
    ld      (upc_outptr),hl
    djnz    upc_right_loop

;; --- the leading digit, from the parity pattern -------------------------
    ld      a,(parity)
    ld      c,a
    ld      hl,ean_parity
    ld      b,10
    ld      d,0
upc_parity_lookup:
    ld      a,(hl)
    cp      c
    jr      z,upc_parity_hit
    inc     hl
    inc     d
    djnz    upc_parity_lookup
    scf                            ; no such parity pattern: not an EAN-13
    ret
upc_parity_hit:
    ld      a,d
    ld      (digits),a

;; --- verify the check digit --------------------------------------------
;; Thirteen digits, weights 1,3,1,3,...  The twelve-digit UPC-A rule is the
;; same rule with the implied leading zero in place, which is why one loop
;; serves both.  Largest possible sum is 7*9 + 6*27 = 225, so eight bits do.
    ld      hl,digits
    ld      b,EAN_DIGITS
    ld      c,0                    ; running sum
    ld      e,1                    ; weight of the digit at hand
upc_checksum:
    ld      a,(hl)
    ld      d,a
    ld      a,e
    cp      1
    jr      z,upc_weight_one
    ld      a,d
    add     a,a
    add     a,d                    ; 3 * digit
    jr      upc_weighed
upc_weight_one:
    ld      a,d
upc_weighed:
    add     a,c
    ld      c,a
    ld      a,4
    sub     e
    ld      e,a                    ; 1 <-> 3
    inc     hl
    djnz    upc_checksum

    ld      a,c
upc_mod10:
    cp      10
    jr      c,upc_modded
    sub     10
    jr      upc_mod10
upc_modded:
    or      a
    jp      nz,upc_reject          ; the check digit does not agree

;; --- publish ------------------------------------------------------------
;; A leading zero means the symbol is a UPC-A, which is conventionally
;; reported as twelve digits rather than thirteen with a zero in front.
    ld      hl,digits
    ld      a,(hl)
    or      a
    ld      b,EAN_DIGITS
    jr      nz,upc_emit
    inc     hl                     ; skip the implied zero
    ld      b,EAN_DIGITS-1
upc_emit:
    ld      c,b                    ; keep the count
    ld      de,out_buffer
upc_emit_loop:
    ld      a,(hl)
    add     a,'0'
    ld      (de),a
    inc     hl
    inc     de
    djnz    upc_emit_loop

    ld      l,c
    ld      h,0
    or      a                      ; clear carry: decoded
    ret

;; ---------------------------------------------------------------------------
;; decode_digit_lr -- a left-hand digit, which may be L or G coded.
;;
;; Looks the quad up as it stands (L) and, failing that, reversed (G),
;; shifting the answer into `parity`.  A G digit is what carries one bit of
;; the thirteenth digit.
;;
;; Out: A = 0..9 and carry clear, or carry set.
;; ---------------------------------------------------------------------------
decode_digit_lr:
    call    read_quad              ; C = packed quad
    push    bc
    call    lookup_quad
    jr      nc,decode_lr_odd
    pop     bc
    call    reverse_quad           ; try it as a G code
    call    lookup_quad
    ret     c
    push    af
    ld      a,(parity)
    add     a,a
    inc     a                      ; shift in a 1: this digit was G
    ld      (parity),a
    pop     af
    or      a
    ret
decode_lr_odd:
    pop     bc
    push    af
    ld      a,(parity)
    add     a,a                    ; shift in a 0: this digit was L
    ld      (parity),a
    pop     af
    or      a
    ret

;; ---------------------------------------------------------------------------
;; decode_digit -- a right-hand digit: plain lookup, no parity.
;; ---------------------------------------------------------------------------
decode_digit:
    call    read_quad
    jp      lookup_quad

;; ---------------------------------------------------------------------------
;; read_quad -- four elements at (upc_cursor) packed into C.
;;
;; Each element classifies to 1..4 modules, so two bits apiece; the first
;; element lands in the high pair.
;; ---------------------------------------------------------------------------
read_quad:
    ld      c,0
    ld      b,4
read_quad_loop:
    push    bc
    call    upc_next_width
    call    classify               ; A = 1..4
    dec     a                      ; -> 0..3
    pop     bc
    sla     c
    sla     c
    or      c
    ld      c,a
    djnz    read_quad_loop
    ret

;; ---------------------------------------------------------------------------
;; reverse_quad -- reverse the four two-bit fields in C.
;;
;; aabbccdd becomes ddccbbaa.  Take the low pair, shift it into the result,
;; rotate the source down two, four times.
;; ---------------------------------------------------------------------------
reverse_quad:
    ld      a,c
    ld      c,0
    ld      b,4
reverse_quad_loop:
    push    af
    and     3                      ; the pair at the bottom
    ld      d,a
    ld      a,c
    add     a,a
    add     a,a                    ; make room in the result
    or      d
    ld      c,a
    pop     af
    rrca
    rrca                           ; bring the next pair down
    djnz    reverse_quad_loop
    ret

;; ---------------------------------------------------------------------------
;; lookup_quad -- C = a packed quad; returns A = 0..9, carry set if unknown.
;; ---------------------------------------------------------------------------
lookup_quad:
    ld      hl,upc_table
    ld      b,10
    ld      d,0
lookup_quad_loop:
    ld      a,(hl)
    cp      c
    jr      z,lookup_quad_hit
    inc     hl
    inc     d
    djnz    lookup_quad_loop
    scf
    ret
lookup_quad_hit:
    ld      a,d
    or      a                      ; clears carry
    ret

;; ---------------------------------------------------------------------------
;; classify -- DE = an element width; returns A = 1..4 modules.
;; ---------------------------------------------------------------------------
classify:
    ld      h,d
    ld      l,e
    add     hl,hl                  ; 2w
    ld      b,h
    ld      c,l
    add     hl,hl                  ; 4w
    add     hl,bc                  ; 6w
    push    hl
    ld      de,(thr3)
    or      a
    sbc     hl,de
    pop     hl
    jr      nc,classify_not1
    ld      a,1
    ret
classify_not1:
    push    hl
    ld      de,(thr5)
    or      a
    sbc     hl,de
    pop     hl
    jr      nc,classify_not2
    ld      a,2
    ret
classify_not2:
    push    hl
    ld      de,(thr7)
    or      a
    sbc     hl,de
    pop     hl
    jr      nc,classify_not3
    ld      a,3
    ret
classify_not3:
    ld      a,4
    ret

;; ---------------------------------------------------------------------------
;; upc_next_width -- DE = the 16-bit width at (upc_cursor); advance it.
;; ---------------------------------------------------------------------------
upc_next_width:
    ld      hl,(upc_cursor)
    ld      e,(hl)
    inc     hl
    ld      d,(hl)
    inc     hl
    ld      (upc_cursor),hl
    ret

;; --- workspace -------------------------------------------------------------
upc_cursor: defw 0
guard:      defw 0                 ; sum of the left guard = three modules
thr3:       defw 0                 ; 3S, 5S, 7S -- see above
thr5:       defw 0
thr7:       defw 0
upc_outptr: defw 0
parity:     defb 0                 ; one bit per left digit, G = 1
digits:     defs EAN_DIGITS        ; decoded values, leading digit first
scratch:    defs UPC_ELEMENTS*2    ; the reversed scan

    include "upc_table.inc"
    include "ean_parity.inc"
