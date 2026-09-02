;; ---------------------------------------------------------------------------
;; upc.asm -- UPC-A decoder.
;;
;; UPC-A is 95 modules wide, which the capture records as 59 elements:
;;
;;      elements  0..2    left guard      3 modules  (bar space bar)
;;                3..26   six digits      6 x 7 modules, 4 elements each
;;                27..31  centre guard    5 modules
;;                32..55  six digits      6 x 7 modules
;;                56..58  right guard     3 modules
;;
;; Unlike Code 39 this is a *delta* symbology: an element is 1, 2, 3 or 4
;; modules and only means something relative to the module width.  We take
;; the module width from the left guard, whose three elements are one module
;; each by definition.
;;
;; The left-hand codes have odd parity and the right-hand codes are their
;; bitwise complement, which leaves the run lengths identical -- so one
;; ten-entry table decodes both halves.
;;
;; UPC is NOT self-checking the way Code 39 is: any four elements classify
;; to *some* pattern.  The check digit is the only thing standing between a
;; misread and a plausible wrong number, so it is verified before we return.
;;
;; Not handled: a symbol scanned right-to-left.  A wand can be drawn either
;; way, and a reversed UPC-A decodes to a different valid-looking pattern,
;; so supporting it means decoding both directions and preferring the one
;; whose check digit passes.  See README.
;; ---------------------------------------------------------------------------

    include "dipos.inc"

    public  upc_decode
    extern  width_table, element_count, out_buffer

UPC_ELEMENTS    equ 59
UPC_DIGITS      equ 12

;; The module width is bounded by the capture itself: the widest UPC element
;; is four modules, and ROM00:13EA ends a capture at 1800h counts, so a
;; module cannot exceed 17FFh/4.  Three modules therefore cannot exceed
;; 1200h, which is what keeps 7*guard below 16 bits below.
UPC_MAX_GUARD   equ 1200h

;; ---------------------------------------------------------------------------
;; upc_decode
;;
;; Out: carry clear and HL = 12, with twelve ASCII digits in out_buffer;
;;      carry set if this is not a valid UPC-A symbol.
;; ---------------------------------------------------------------------------
upc_decode:
    ld      hl,(element_count)
    ld      de,UPC_ELEMENTS
    or      a
    sbc     hl,de
    jp      nz,upc_reject             ; UPC-A is exactly 59 elements

;; --- module width, from the left guard ------------------------------------
;; The guard's three elements are one module each, so their sum is three
;; modules.  Working in units of "three modules" avoids dividing.
    ld      hl,(width_table)
    ld      (upc_cursor),hl
    call    upc_next_width
    ld      (guard),de
    call    upc_next_width
    ld      hl,(guard)
    add     hl,de
    ld      (guard),hl
    call    upc_next_width
    ld      hl,(guard)
    add     hl,de
    ld      (guard),hl             ; guard = 3 modules

    ld      de,UPC_MAX_GUARD
    or      a
    sbc     hl,de
    jp      nc,upc_reject             ; implausibly wide; also keeps 7*guard in range

;; --- classification thresholds --------------------------------------------
;; An element of w modules is classified by comparing 6w against multiples
;; of the guard sum S (= 3 modules):
;;      w <= 1.5 modules  <=>  6w <= 3S
;;      w <= 2.5 modules  <=>  6w <= 5S
;;      w <= 3.5 modules  <=>  6w <= 7S
;; With S < 1200h every product below stays inside 16 bits.
    ld      hl,(guard)             ; S
    ld      d,h
    ld      e,l
    add     hl,hl                  ; 2S
    add     hl,de                  ; 3S
    ld      (thr3),hl
    add     hl,de                  ; 4S
    add     hl,de                  ; 5S
    ld      (thr5),hl
    add     hl,de                  ; 6S
    add     hl,de                  ; 7S
    ld      (thr7),hl

;; --- the twelve digits -----------------------------------------------------
;; Skip the three guard elements already consumed, then six digits, the five
;; centre-guard elements, then six more.
;; Digits are collected as VALUES in `digits`, not as ASCII in out_buffer:
;; the check digit has to be verified before anything is published, and the
;; conversion to ASCII happens once, at the end.
    ld      hl,digits
    ld      (upc_outptr),hl
    ld      a,UPC_DIGITS/2
    ld      (todo),a
    call    upc_six_digits
    ret     c

    ld      b,5                    ; step over the centre guard
upc_skip_centre:
    push    bc
    call    upc_next_width
    pop     bc
    djnz    upc_skip_centre

    ld      a,UPC_DIGITS/2
    ld      (todo),a
    call    upc_six_digits
    ret     c

;; --- verify the check digit ------------------------------------------------
;; 3*(digits at even indices) + (digits at odd indices) must be a multiple of
;; ten, the check digit itself being the last odd-indexed digit.  Taking the
;; digits in pairs makes the alternating weight fall out of the loop shape.
;; The largest possible sum is 6*3*9 + 6*9 = 216, so eight bits suffice.
    ld      hl,digits
    ld      b,UPC_DIGITS/2
    ld      c,0                    ; running sum
upc_checksum:
    ld      a,(hl)                 ; even index: weight 3
    add     a,a
    add     a,(hl)
    add     a,c
    ld      c,a
    inc     hl
    ld      a,(hl)                 ; odd index: weight 1
    add     a,c
    ld      c,a
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

;; --- publish ---------------------------------------------------------------
    ld      hl,digits
    ld      de,out_buffer
    ld      b,UPC_DIGITS
upc_emit:
    ld      a,(hl)
    add     a,'0'
    ld      (de),a
    inc     hl
    inc     de
    djnz    upc_emit

    ld      hl,UPC_DIGITS
    or      a                      ; clear carry: decoded
    ret

upc_reject:
    scf
    ret

;; --- six digits from the current upc_cursor ------------------------------------
upc_six_digits:
    ld      a,(todo)
    ld      b,a
upc_digit_loop:
    push    bc
    call    decode_digit
    pop     bc
    ret     c
    ld      hl,(upc_outptr)
    ld      (hl),a
    inc     hl
    ld      (upc_outptr),hl
    djnz    upc_digit_loop
    or      a
    ret

;; ---------------------------------------------------------------------------
;; decode_digit -- four elements at (upc_cursor) into one digit.
;;
;; Each element classifies to 1..4 modules; the four are packed two bits
;; apiece, first element in the high pair, and looked up.
;;
;; Out: A = 0..9 and carry clear, or carry set if the quad matches no digit.
;; ---------------------------------------------------------------------------
decode_digit:
    ld      c,0                    ; the packed key
    ld      b,4
upc_pack:
    push    bc
    call    upc_next_width
    call    classify               ; A = 1..4
    dec     a                      ; -> 0..3
    pop     bc
    sla     c
    sla     c
    or      c
    ld      c,a
    djnz    upc_pack

    ld      hl,upc_table
    ld      b,10
    ld      d,0                    ; candidate digit
upc_lookup:
    ld      a,(hl)
    cp      c
    jr      z,upc_hit
    inc     hl
    inc     d
    djnz    upc_lookup
    scf
    ret
upc_hit:
    ld      a,d
    or      a                      ; clears carry
    ret

;; ---------------------------------------------------------------------------
;; classify -- DE = an element width; returns A = 1..4 modules.
;; ---------------------------------------------------------------------------
classify:
    ld      h,d                    ; 6 * width
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
    jr      nc,upc_not1
    ld      a,1
    ret
upc_not1:
    push    hl
    ld      de,(thr5)
    or      a
    sbc     hl,de
    pop     hl
    jr      nc,upc_not2
    ld      a,2
    ret
upc_not2:
    push    hl
    ld      de,(thr7)
    or      a
    sbc     hl,de
    pop     hl
    jr      nc,upc_not3
    ld      a,3
    ret
upc_not3:
    ld      a,4
    ret

;; ---------------------------------------------------------------------------
;; upc_next_width -- DE = the 16-bit width at (upc_cursor); (upc_cursor) += 2.
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
upc_cursor:     defw 0
guard:      defw 0                 ; sum of the left guard = three modules
thr3:       defw 0                 ; 3S, 5S, 7S -- see the comment above
thr5:       defw 0
thr7:       defw 0
upc_outptr:     defw 0
todo:       defb 0
digits:     defs UPC_DIGITS        ; the decoded values, 0..9

    include "upc_table.inc"
