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
    extern  scratch, reverse_elements, symbology

UPC_ELEMENTS    equ 59
EAN_DIGITS      equ 13
LEFT_DIGITS     equ 6
UPCE_ELEMENTS   equ 33
UPCE_DIGITS     equ 6

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
    jr      z,upc_ean              ; 59 elements: EAN-13 or UPC-A
    ld      hl,(element_count)
    ld      de,UPCE_ELEMENTS
    or      a
    sbc     hl,de
    jp      z,upce_entry           ; 33 elements: UPC-E
    jp      upc_reject

upc_ean:
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
    jp      reverse_elements

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
    call    upc_thresholds

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
    call    checksum13
    jp      nz,upc_reject          ; the check digit does not agree

;; --- publish ------------------------------------------------------------
;; A leading zero means the symbol is a UPC-A, which is conventionally
;; reported as twelve digits rather than thirteen with a zero in front.
    ld      hl,digits
    ld      a,(hl)
    or      a
    ld      b,EAN_DIGITS
    ld      a,SYM_EAN13
    jr      nz,upc_have_sym
    inc     hl                     ; skip the implied zero
    ld      b,EAN_DIGITS-1
    ld      a,SYM_UPCA             ; all-L parity: this is a UPC-A
upc_have_sym:
    ld      (symbology),a
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
;; upc_thresholds -- from (guard) = three modules, derive the three
;; classification limits.  See classify for why they are these multiples.
;; ---------------------------------------------------------------------------
upc_thresholds:
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

;; ---------------------------------------------------------------------------
;; checksum13 -- HL points at thirteen digit values.
;;
;; Weights alternate 1,3,1,3,... from the first digit.  The twelve-digit
;; UPC-A rule is this same rule with the implied leading zero in place,
;; which is why one routine serves EAN-13, UPC-A and the UPC-E expansion.
;;
;; Out: Z set if the total is a multiple of ten.  Largest total is
;;      7*9 + 6*27 = 225, so eight bits suffice.
;; ---------------------------------------------------------------------------
checksum13:
    ld      b,EAN_DIGITS
    ld      c,0                    ; running sum
    ld      e,1                    ; weight of the digit at hand
checksum13_loop:
    ld      a,(hl)
    ld      d,a
    ld      a,e
    cp      1
    jr      z,checksum13_one
    ld      a,d
    add     a,a
    add     a,d                    ; 3 * digit
    jr      checksum13_add
checksum13_one:
    ld      a,d
checksum13_add:
    add     a,c
    ld      c,a
    ld      a,4
    sub     e
    ld      e,a                    ; 1 <-> 3
    inc     hl
    djnz    checksum13_loop
    ld      a,c
checksum13_mod:
    cp      10
    jr      c,checksum13_done
    sub     10
    jr      checksum13_mod
checksum13_done:
    or      a
    ret

;; ===========================================================================
;; UPC-E
;;
;; Six digits in 51 modules, which the capture sees as 33 elements:
;;
;;      elements  0..2    left guard    3 modules  (bar space bar)
;;                3..26   six digits    6 x 7 modules, 4 elements each
;;                27..32  end guard     6 modules  (010101)
;;
;; There are no R codes here: every digit is L or G.  Neither the number
;; system nor the check digit is drawn -- both live in the parity pattern,
;; which upce_parity translates.  Number system 1 is the same pattern set
;; complemented, so a failed lookup is retried against XOR 3Fh.
;;
;; The symbol is not symmetric -- three elements of guard at one end, six at
;; the other -- but that does not matter for a reversed scan: reversing the
;; captured elements restores the original order, so the second pass is an
;; ordinary forward decode.  (An earlier version read the mirrored symbol
;; in place, which needed its own layout and inverted every parity bit.
;; Restoring the order first is both smaller and obviously correct.)
;; ===========================================================================
upce_entry:
    ld      hl,(width_table)
    xor     a                      ; forward
    call    upce_attempt
    ret     nc
    call    upce_reverse
    ld      hl,scratch             ; reversing a reversed scan restores the
    xor     a                      ; original order, so this is a forward
    call    upce_attempt           ; decode like any other
    ret

;; --- copy the 33 elements back to front ------------------------------------
upce_reverse:
    ld      hl,(width_table)
    ld      de,UPCE_ELEMENTS*2-2
    add     hl,de                  ; -> the last element
    ld      de,scratch
    ld      b,UPCE_ELEMENTS
    jp      reverse_elements

;; ---------------------------------------------------------------------------
;; upce_attempt -- HL = the elements, A = 0 forward or 1 reversed.
;; Out: carry clear and HL = 8, or carry set.
;; ---------------------------------------------------------------------------
upce_attempt:
    ld      (upc_cursor),hl

;; --- module width ---------------------------------------------------------
;; Forward, the left guard's three elements are one module each.  Reversed,
;; the six-element end guard arrives first and is six modules, so halving
;; its sum gives the same three-module figure the thresholds want.
    ld      b,3
    ld      hl,0
    ld      (guard),hl
upce_guard_loop:
    push    bc
    call    upc_next_width
    ld      hl,(guard)
    add     hl,de
    ld      (guard),hl
    pop     bc
    djnz    upce_guard_loop

    ld      hl,(guard)
    ld      de,UPC_MAX_GUARD
    or      a
    sbc     hl,de
    jp      nc,upc_reject

    call    upc_thresholds

;; --- the six digits --------------------------------------------------------
    ld      hl,digits
    ld      (upc_outptr),hl
    xor     a
    ld      (parity),a
    ld      b,UPCE_DIGITS
upce_digit_loop:
    push    bc
    call    decode_digit_lr
    pop     bc
    ret     c
    ld      hl,(upc_outptr)
    ld      (hl),a
    inc     hl
    ld      (upc_outptr),hl
    djnz    upce_digit_loop

;; --- number system and check digit, from the parity ------------------------
    ld      a,(parity)
    ld      c,a
    call    upce_parity_lookup
    jr      nc,upce_system0
    ld      a,(parity)
    xor     3Fh                    ; number system 1 is the complement
    ld      c,a
    call    upce_parity_lookup
    ret     c                      ; no such pattern: not a UPC-E
    push    af                     ; A is the check digit -- keep it
    ld      a,1
    ld      (upce_ns),a
    pop     af
    jr      upce_have_check
upce_system0:
    push    af
    xor     a
    ld      (upce_ns),a
    pop     af
upce_have_check:
    ld      (upce_check),a

;; --- expand, and verify the check digit against the expansion --------------
    call    upce_expand
    ld      hl,upce_ean
    call    checksum13
    jp      nz,upc_reject

;; --- publish the eight-digit form ------------------------------------------
;; Number system, the six data digits, then the check digit -- what is
;; printed on the label.  Eight digits also tells a host the symbology
;; apart from UPC-A's twelve and EAN-13's thirteen by length alone.
    ld      de,out_buffer
    ld      a,(upce_ns)
    add     a,'0'
    ld      (de),a
    inc     de
    ld      hl,digits
    ld      b,UPCE_DIGITS
upce_emit:
    ld      a,(hl)
    add     a,'0'
    ld      (de),a
    inc     hl
    inc     de
    djnz    upce_emit
    ld      a,(upce_check)
    add     a,'0'
    ld      (de),a

    ld      a,SYM_UPCE
    ld      (symbology),a
    ld      hl,UPCE_DIGITS+2
    or      a
    ret

;; --- look C up in upce_parity; A = check digit, carry set if absent --------
upce_parity_lookup:
    ld      hl,upce_parity
    ld      b,10
    ld      d,0
upce_pl_loop:
    ld      a,(hl)
    cp      c
    jr      z,upce_pl_hit
    inc     hl
    inc     d
    djnz    upce_pl_loop
    scf
    ret
upce_pl_hit:
    ld      a,d
    or      a
    ret

;; ---------------------------------------------------------------------------
;; upce_expand -- build the twelve-digit UPC-A this symbol stands for.
;;
;; The last data digit says where the suppressed zeros belong; that is the
;; whole of the format.  The result is written to upce_ean+1, with a zero in
;; upce_ean so checksum13 can treat it as an EAN-13.
;; ---------------------------------------------------------------------------
upce_expand:
    xor     a
    ld      (upce_ean),a           ; the implied EAN-13 leading zero
    ld      a,(upce_ns)
    ld      (upce_ean+1),a

    ld      hl,digits
    ld      a,(hl)
    ld      (upce_ean+2),a         ; X1
    inc     hl
    ld      a,(hl)
    ld      (upce_ean+3),a         ; X2

    ld      a,(digits+5)           ; X6 selects the layout
    cp      3
    jr      c,upce_exp012
    cp      4
    jr      z,upce_exp4
    cp      3
    jr      z,upce_exp3
    jr      upce_exp59

;; X6 is 0, 1 or 2:  N X1 X2 X6 0 0 0 0 X3 X4 X5 C
upce_exp012:
    ld      a,(digits+5)
    ld      (upce_ean+4),a
    call    upce_zero4             ; upce_ean+5 .. +8
    ld      a,(digits+2)
    ld      (upce_ean+9),a
    ld      a,(digits+3)
    ld      (upce_ean+10),a
    ld      a,(digits+4)
    ld      (upce_ean+11),a
    jr      upce_exp_check

;; X6 = 3:  N X1 X2 X3 0 0 0 0 0 X4 X5 C
upce_exp3:
    ld      a,(digits+2)
    ld      (upce_ean+4),a
    call    upce_zero4
    xor     a
    ld      (upce_ean+9),a
    ld      a,(digits+3)
    ld      (upce_ean+10),a
    ld      a,(digits+4)
    ld      (upce_ean+11),a
    jr      upce_exp_check

;; X6 = 4:  N X1 X2 X3 X4 0 0 0 0 0 X5 C
upce_exp4:
    ld      a,(digits+2)
    ld      (upce_ean+4),a
    ld      a,(digits+3)
    ld      (upce_ean+5),a
    xor     a
    ld      (upce_ean+6),a
    ld      (upce_ean+7),a
    ld      (upce_ean+8),a
    ld      (upce_ean+9),a
    ld      a,(digits+4)
    ld      (upce_ean+11),a
    xor     a
    ld      (upce_ean+10),a
    jr      upce_exp_check

;; X6 is 5..9:  N X1 X2 X3 X4 X5 0 0 0 0 X6 C
upce_exp59:
    ld      a,(digits+2)
    ld      (upce_ean+4),a
    ld      a,(digits+3)
    ld      (upce_ean+5),a
    ld      a,(digits+4)
    ld      (upce_ean+6),a
    xor     a
    ld      (upce_ean+7),a
    ld      (upce_ean+8),a
    ld      (upce_ean+9),a
    ld      (upce_ean+10),a
    ld      a,(digits+5)
    ld      (upce_ean+11),a

upce_exp_check:
    ld      a,(upce_check)
    ld      (upce_ean+12),a
    ret

;; four zeros at upce_ean+5..+8
upce_zero4:
    xor     a
    ld      (upce_ean+5),a
    ld      (upce_ean+6),a
    ld      (upce_ean+7),a
    ld      (upce_ean+8),a
    ret

upce_ns:    defb 0                 ; number system, 0 or 1
upce_check: defb 0                 ; check digit, recovered from the parity
upce_ean:   defs EAN_DIGITS        ; the expansion, as an EAN-13

    include "upc_table.inc"
    include "ean_parity.inc"
    include "upce_parity.inc"
