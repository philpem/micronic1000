;; ---------------------------------------------------------------------------
;; hook.asm -- DIPOS-B barcode decode hook: entry, dispatch and result.
;;
;; The firmware hands us a table of captured element widths and expects
;; either decoded bytes or a rejection.  We try each symbology in turn and
;; publish the first that decodes cleanly.
;;
;; Order matters.  Code 39 is tried first because it is self-checking: an
;; invalid element pattern has no table entry, so a mis-scan rejects itself
;; rather than producing plausible wrong data.  UPC has no such property --
;; only the check digit stands between a misread and a wrong number -- so it
;; goes second, where it only sees scans Code 39 has already declined.
;; ---------------------------------------------------------------------------

    include "dipos.inc"

    public  decoder_entry
    extern  code39_decode, upc_decode, itf_decode, codabar_decode

;; ---------------------------------------------------------------------------
;; decoder_entry -- the address installed in the hook socket.
;;
;; In:   nothing in registers; [SP+2] = PARAM_BLOCK (we use the constant
;;       directly, so the argument is not read).
;; Out:  PARAM_WIDTHS/PARAM_COUNT updated; all registers clobbered.
;; ---------------------------------------------------------------------------
decoder_entry:
    ld      hl,(PARAM_COUNT)

;; The firmware can hand us a count larger than the buffer really holds --
;; ROM00:1409 stores the uncapped value and ROM00:1446 reads it back, while
;; only MAX_ELEMENTS entries were ever written.  Clamp before trusting it.
    ld      a,h
    or      a
    jr      nz,hk_clamp               ; >= 256, certainly too many
    ld      a,l
    cp      MAX_ELEMENTS+1
    jr      c,hk_counted
hk_clamp:
    ld      hl,MAX_ELEMENTS
hk_counted:
    ld      (element_count),hl

    ld      hl,(PARAM_WIDTHS)
    ld      (width_table),hl

;; --- try each symbology ----------------------------------------------------
    call    code39_decode
    jr      nc,hk_publish             ; carry clear = decoded
    call    upc_decode
    jr      nc,hk_publish
    call    itf_decode
    jr      nc,hk_publish
    call    codabar_decode
    jr      nc,hk_publish

;; --- nothing decoded: reject and re-arm ------------------------------------
;; A zero count is the documented rejection, and is all the ROM's own default
;; hook does.  PARAM_WIDTHS is left alone: the firmware does not read it when
;; the count is zero.
    ld      hl,0
    ld      (PARAM_COUNT),hl
    ret

;; --- publish the decode ----------------------------------------------------
;; On entry here: HL = byte count, out_buffer holds the bytes.
hk_publish:
    ld      a,h
    or      a
    jr      nz,hk_toolong             ; a count that large is a bug in us
    ld      a,l
    cp      MAX_OUTPUT+1
    jr      nc,hk_toolong

    ld      (PARAM_COUNT),hl
    ld      hl,out_buffer
    ld      (PARAM_WIDTHS),hl
    ret

;; The delivery copy at ROM00:148B is an unbounded LDIR into a 26-byte
;; buffer, so over-long output would corrupt the device table rather than
;; being truncated.  Refuse instead.
hk_toolong:
    ld      hl,0
    ld      (PARAM_COUNT),hl
    ret

;; ---------------------------------------------------------------------------
;; Shared state.  Set up by decoder_entry, read by each symbology.
;; ---------------------------------------------------------------------------
    public  width_table, element_count, out_buffer
    public  scratch, reverse_elements

;; ---------------------------------------------------------------------------
;; reverse_elements -- copy B 16-bit elements from (HL) to (DE), back to
;; front, so the last element read is written first.
;;
;; HL must point at the LAST element, not the first.
;; ---------------------------------------------------------------------------
reverse_elements:
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
    djnz    reverse_elements
    ret

width_table:    defw 0              ; -> the captured widths (16-bit each)
element_count:  defw 0              ; clamped element count

;; Decoded output.  MAX_OUTPUT is the firmware's hard limit; see dipos.inc.
;; Room to reverse the longest capture the firmware can hand us.  Shared by
;; every symbology: a reversed scan is decoded by restoring the original
;; element order here and running the ordinary forward decode over it.
scratch:        defs MAX_ELEMENTS*2

;; Decoded output.  MAX_OUTPUT is the firmware's hard limit; see dipos.inc.
out_buffer:     defs MAX_OUTPUT
