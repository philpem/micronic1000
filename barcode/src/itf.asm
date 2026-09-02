;; ---------------------------------------------------------------------------
;; itf.asm -- Interleaved 2 of 5.
;;
;; Digits travel in pairs: five bars carry the first, five spaces the
;; second, woven together.  Each group of five has exactly two wide
;; elements, so a pair is ten elements:
;;
;;      elements  0..3          start, four narrow
;;                4..           ten per digit pair
;;                last three    stop: wide, narrow, narrow
;;
;; so a symbol of 2k digits is 10k + 7 elements.  An odd digit count cannot
;; be drawn at all -- that is the symbology, not a limitation here.
;;
;; Like Code 39 this is a wide/narrow code needing no absolute calibration,
;; and the threshold is taken per digit pair: a group of ten always holds
;; four wide and six narrow, so its own extremes are always meaningful.
;;
;; NOT self-checking in the way Code 39 is.  An invalid five-bit group has
;; no table entry and rejects, but ITF's real hazard is different: a scan
;; that clips the start or stop can still decode as a shorter valid symbol.
;; The start and stop patterns are therefore both verified.  ITF's optional
;; mod-10 check digit is not verified here -- it is not part of the
;; symbology, and a host that wants it can check the returned digits.
;; ---------------------------------------------------------------------------

    include "dipos.inc"

    public  itf_decode
    extern  width_table, element_count, out_buffer
    extern  scratch, reverse_elements, symbology

ITF_OVERHEAD    equ 7              ; four start elements plus three stop
ITF_PER_PAIR    equ 10

;; ---------------------------------------------------------------------------
;; itf_decode
;; Out: carry clear and HL = digit count, or carry set.
;; ---------------------------------------------------------------------------
itf_decode:
    ld      hl,(width_table)
    call    itf_attempt
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
    jp      itf_attempt

itf_attempt:
    ld      (itf_base),hl
    ld      hl,(element_count)
    ld      a,h
    or      a
    jp      nz,itf_reject
    ld      a,l
    sub     ITF_OVERHEAD
    jp      c,itf_reject
    jr      z,itf_reject           ; overhead alone is not a symbol

;; The remainder must be a whole number of digit pairs.
    ld      c,a
    ld      b,0
itf_divide:
    ld      a,c
    cp      ITF_PER_PAIR
    jr      c,itf_divided
    sub     ITF_PER_PAIR
    ld      c,a
    inc     b
    jr      itf_divide
itf_divided:
    or      a
    jp      nz,itf_reject
    ld      a,b
    ld      (itf_pairs),a

;; --- the start: four narrow ------------------------------------------------
;; The threshold comes from the first digit pair, which is the nearest run
;; of elements guaranteed to contain both widths.
    ld      hl,(itf_base)
    ld      de,8                   ; skip the four start elements
    add     hl,de
    call    itf_threshold          ; over the ten elements at HL
    ld      hl,(itf_base)
    ld      (itf_cursor),hl
    ld      b,4
itf_start_loop:
    push    bc
    call    itf_next
    call    itf_wide               ; carry set if wide
    pop     bc
    jp      c,itf_reject           ; a wide element in the start pattern
    djnz    itf_start_loop

;; --- the digit pairs -------------------------------------------------------
    ld      hl,out_buffer
    ld      (itf_outptr),hl
    xor     a
    ld      (itf_count),a
    ld      a,(itf_pairs)
    ld      b,a
itf_pair_loop:
    push    bc
    ld      hl,(itf_cursor)
    call    itf_threshold          ; this pair's own extremes
    call    itf_pair
    pop     bc
    ret     c
    djnz    itf_pair_loop

;; --- the stop: wide, narrow, narrow ----------------------------------------
;; The last pair's threshold is still in place, which is the closest
;; calibration to these elements.
    call    itf_next
    call    itf_wide
    jp      nc,itf_reject
    ld      b,2
itf_stop_loop:
    push    bc
    call    itf_next
    call    itf_wide
    pop     bc
    jp      c,itf_reject
    djnz    itf_stop_loop

    ld      a,SYM_ITF
    ld      (symbology),a
    ld      a,(itf_count)
    ld      l,a
    ld      h,0
    or      a
    ret

itf_reject:
    scf
    ret

;; ---------------------------------------------------------------------------
;; itf_pair -- ten elements at (itf_cursor) into two digits.
;;
;; The bars are the even elements and the spaces the odd ones; each set of
;; five is a pattern in its own right.
;; ---------------------------------------------------------------------------
itf_pair:
    ld      hl,0
    ld      (itf_bars),hl          ; also clears itf_spaces, which follows
    ld      b,5
itf_pair_read:
    push    bc
    call    itf_next               ; a bar
    call    itf_wide
    ld      a,(itf_bars)
    adc     a,a                    ; shift the decision straight in
    ld      (itf_bars),a
    call    itf_next               ; and its space
    call    itf_wide
    ld      a,(itf_spaces)
    adc     a,a
    ld      (itf_spaces),a
    pop     bc
    djnz    itf_pair_read

    ld      a,(itf_bars)
    call    itf_lookup
    ret     c
    call    itf_emit
    ld      a,(itf_spaces)
    call    itf_lookup
    ret     c
    call    itf_emit
    or      a
    ret

itf_emit:
    push    af
    add     a,'0'
    ld      hl,(itf_outptr)
    ld      (hl),a
    inc     hl
    ld      (itf_outptr),hl
    ld      hl,itf_count
    inc     (hl)
    pop     af
    ret

;; --- A = a five-bit pattern; returns A = digit, carry set if unknown -------
itf_lookup:
    ld      c,a
    ld      hl,itf_table
    ld      b,10
    ld      d,0
itf_lookup_loop:
    ld      a,(hl)
    cp      c
    jr      z,itf_lookup_hit
    inc     hl
    inc     d
    djnz    itf_lookup_loop
    scf
    ret
itf_lookup_hit:
    ld      a,d
    or      a
    ret

;; ---------------------------------------------------------------------------
;; itf_threshold -- midpoint of the ten elements at HL, into (itf_thresh).
;; Does not disturb (itf_cursor).
;; ---------------------------------------------------------------------------
itf_threshold:
    ld      (itf_scan),hl
    call    itf_scan_next
    ld      (itf_min),de
    ld      (itf_max),de
    ld      b,ITF_PER_PAIR-1
itf_thr_loop:
    push    bc
    call    itf_scan_next
    ld      hl,(itf_min)
    or      a
    sbc     hl,de
    jr      c,itf_thr_notmin
    ld      hl,itf_min
    ld      (hl),e
    inc     hl
    ld      (hl),d
itf_thr_notmin:
    ld      hl,(itf_max)
    or      a
    sbc     hl,de
    jr      nc,itf_thr_notmax
    ld      hl,itf_max
    ld      (hl),e
    inc     hl
    ld      (hl),d
itf_thr_notmax:
    pop     bc
    djnz    itf_thr_loop
    ld      hl,(itf_min)
    ld      de,(itf_max)
    add     hl,de
    srl     h
    rr      l
    ld      (itf_thresh),hl
    ret

itf_scan_next:
    ld      hl,(itf_scan)
    ld      e,(hl)
    inc     hl
    ld      d,(hl)
    inc     hl
    ld      (itf_scan),hl
    ret

;; --- DE = the next element; advances (itf_cursor) --------------------------
itf_next:
    ld      hl,(itf_cursor)
    ld      e,(hl)
    inc     hl
    ld      d,(hl)
    inc     hl
    ld      (itf_cursor),hl
    ret

;; --- carry set if DE is a wide element -------------------------------------
itf_wide:
    ld      hl,(itf_thresh)
    or      a
    sbc     hl,de
    ret

;; --- workspace -------------------------------------------------------------
itf_base:   defw 0
itf_cursor: defw 0
itf_scan:   defw 0                 ; used only while measuring a group
itf_min:    defw 0
itf_max:    defw 0
itf_thresh: defw 0
itf_outptr: defw 0
itf_pairs:  defb 0
itf_count:  defb 0
itf_bars:   defb 0                 ; itf_spaces must follow: cleared together
itf_spaces: defb 0

    include "itf_table.inc"
