; ---------------------------------------------------------------------------
; Micronic 1000 link-controller exerciser
;
; Replaces the cold-boot entry so the machine becomes a dedicated test rig:
; no firmware, no menus, nothing else touching 4Ah-4Fh.  It opens a frame the
; way LinkBlockTx does, then streams the controller's own registers onto the
; IR line for as long as it is powered.
;
; That stream is the whole point.  LINK_STATUS bit 6 (HSBUSY) is what stops
; every session -- the firmware gives up waiting for it at ROM00:32F3 and
; reports 0EEh, which is the 238 on the error screen -- and it cannot be seen
; from outside the case.  Thirteen instrumented runs of external probing could
; not reach it.  This makes it a time series.
;
; The reporting channel is LINK_TXD itself: a write to 4Dh puts a byte on the
; wire, which the existing Arduino receiver already decodes.  No LCD, no
; keyboard, no extra hardware, and it exercises the transmit path at the same
; time.
;
; The firmware's own link routines are called rather than reimplemented for
; port select, controller reset and the frame opening, so those latch
; sequences are identical to the ones the real transmit path uses.
;
; --- wire format ------------------------------------------------------------
;
; One preamble frame, then record frames of 64 records forever.  Every frame
; is preceded by a ~4 ms idle gap and begins with an HDLC flag, and a record
; frame's first record always carries a counter that is a multiple of 64, so
; the receiver resynchronises every ~250 ms and byte alignment is never in
; doubt.
;
; The gap is not optional.  The Arduino receiver delimits bursts by an idle
; period (GAP_US), so an unbroken stream would never be emitted at all; the
; controller is simply not fed for long enough to drain its shifter and stop
; clocking.  Status is still sampled all the way through it, so it costs no
; coverage -- only 1.6% of the wire.
;
;   preamble   A5 5A VER ID PROBE STATUS      (6 bytes, sent once)
;   record     COUNT OR AND RXD               (4 bytes, ~4.9 ms apart)
;
;     COUNT   rolling record number; +1 per record, so a dropped or garbled
;             record is visible and the counter doubles as a time base
;     OR      every LINK_STATUS sample seen since the last record, OR'd
;     AND     every LINK_STATUS sample seen since the last record, AND'd
;     RXD     LINK_RXD, read once per record
;
; OR and AND are the reason a slow record rate costs nothing.  The wait for
; TXRDY between bytes is a tight polling loop -- roughly one LINK_STATUS
; sample every 21 us -- and every sample is folded into both accumulators, so
; a bit that pulses high for a single 122 us wire cell still appears in OR,
; and one that drops for a single cell still appears in AND.  A bit that is
; genuinely constant reads the same in both.  Nothing on the wire's own
; timescale can be aliased away; only the ordering of events inside one
; record is lost.
;
; LINK_PROBE is read once, into the preamble, rather than in the loop: its
; read side effects are unknown, and the point of this burn is to measure
; HSBUSY without confounds.
; ---------------------------------------------------------------------------

LINK_CTRL       equ 0x4A
LINK_STAT       equ 0x4B
LINK_CMD        equ 0x4C
LINK_TXD        equ 0x4D
LINK_RXD        equ 0x4E
LINK_PROBE      equ 0x4F

CTRL_SHADOW     equ 0xF794          ; the firmware's LINK_CTRL shadow
CMD_SHADOW      equ 0xF796          ; ... and its LINK_CMD shadow (see 34F2)
PORT2A_SHADOW   equ 0xF78B
PORT2C_SHADOW   equ 0xF78D

LinkPortSelect  equ 0x3454
LinkProbe       equ 0x348A
LinkPresent     equ 0x34EC          ; polls TXRDY, then writes 81h to LINK_CMD
LinkWaitReady   equ 0x34F8          ; polls TXRDY, DE=02DAh; returns Z on timeout

LINK_ID         equ 0x43            ; id bit 5 clear; use 63h for the other port
VERSION         equ 0x03            ; bumped whenever the wire format changes
STACK           equ 0xC800          ; upper TPA, documented free in the RAM map
V_OR            equ 0xC7E0          ; accumulator snapshot, well clear of the
V_AND           equ 0xC7E1          ; stack, which never goes more than 2 deep

FRAME_RECS      equ 0x3F            ; mask: new frame when (COUNT and this) = 0
GAP_SAMPLES     equ 0xC0            ; ~4 ms of idle; must exceed the receiver's
                                    ; GAP_US plus the controller's drain time

                org 0x7E96

PORT_2A         equ 0x2A

start:          di
                ld sp,STACK

                ; The cold boot we are replacing establishes 2Ah = 20h before
                ; anything touches the link (014B: LD A,20h / OUT (2Ah),A), so
                ; do the same -- LinkPortSelect only clears bit 1 there and
                ; preserves the rest through the shadow.
                ld a,0x20
                out (PORT_2A),a
                ld (PORT2A_SHADOW),a

                ; The firmware's link routines are read-modify-write against
                ; these shadows.  Seed them rather than inheriting whatever
                ; battery RAM happens to hold, so the sequence is repeatable.
                xor a
                ld (CTRL_SHADOW),a
                ld (PORT2C_SHADOW),a

                ; --- select the port exactly as LinkBlockTx does at 3277
                ld a,LINK_ID
                and 0x20
                call LinkPortSelect

                ; --- the cold-boot controller reset
                call LinkProbe

                ; --- LinkBlockTx's opening: bit 0 low, bit 0 high, bit 4 low
                ld a,0xFE
                call ctrl_and
                ld a,0x01
                call ctrl_or
                ld a,0xEF
                call ctrl_and
                ld b,0x80
settle:         djnz settle

                ; --- open the frame.  If the controller never reports ready
                ; there is nothing to report with, so silence on the wire is
                ; itself the result: it would mean TXRDY never asserts.
                call LinkPresent
                jr z,dead
                call LinkWaitReady
                jr z,dead

                ; --- preamble.  Identifies the image and its wire format, and
                ; gives the receiver a known 6 bytes to confirm alignment on
                ; before any measurement is read.
                ld hl,0x00FF                ; H = OR seed, L = AND seed
                ld c,0xA5
                call putbyte
                ld c,0x5A
                call putbyte
                ld c,VERSION
                call putbyte
                ld c,LINK_ID
                call putbyte
                in a,(LINK_PROBE)           ; read once, never in the loop
                ld c,a
                call putbyte
                in a,(LINK_STAT)
                ld c,a
                call putbyte

                ld b,0x00                   ; record counter

                ; --- stream records forever
stream:         ld a,b                      ; new frame every 64 records
                and FRAME_RECS
                call z,newframe             ; ... gap, then flag

                ld a,h                      ; snapshot the window just ended --
                ld (V_OR),a                 ; taken after the gap, so the
                ld a,l                      ; windows are contiguous and the
                ld (V_AND),a                ; gap is not a blind spot
                ld hl,0x00FF                ; start a fresh window

                ld c,b
                call putbyte                ; [0] COUNT
                ld a,(V_OR)
                ld c,a
                call putbyte                ; [1] OR of LINK_STATUS
                ld a,(V_AND)
                ld c,a
                call putbyte                ; [2] AND of LINK_STATUS
                in a,(LINK_RXD)             ; read after status, so a status
                ld c,a                      ; bit cleared by the read still
                call putbyte                ; [3] RXD -- shows in this record

                inc b
                jr stream

dead:           jr dead

; --- Take one LINK_STATUS sample and fold it into the sticky accumulators:
; H accumulates the OR of every sample, L the AND.  The raw sample is left in
; D.  Clobbers A, D.  Preserves B, C.
sample:         in a,(LINK_STAT)
                ld d,a
                or h
                ld h,a
                ld a,d
                and l
                ld l,a
                ret

; Poll until TXRDY (bit 7).  Blocks rather than timing out the way
; LinkWaitReady does, so records never fragment and byte alignment on the wire
; is exact; a controller that never reports ready shows as silence, which is
; itself a result.
waitready:      call sample
                bit 7,d
                jr z,waitready
                ret

; Idle long enough for the receiver to call it a gap: stop feeding LINK_TXD
; and let the controller drain and stop clocking, sampling throughout.
gap:            ld e,GAP_SAMPLES
gap_loop:       call sample
                dec e
                jr nz,gap_loop
                ret

newframe:       call gap
                call putflag
                ret

; C = byte to put on the wire.
putbyte:        call waitready
                ld a,c
                out (LINK_TXD),a
                ret

; An HDLC flag: what LinkPresent writes, but blocking and with the
; accumulators still running.  Also flushes the stuffer pipeline.
putflag:        call waitready
                ld a,0x81
                ld (CMD_SHADOW),a
                out (LINK_CMD),a
                ret

; LINK_CTRL read-modify-write, matching the firmware's own idiom
ctrl_and:       ld hl,CTRL_SHADOW
                and (hl)
                ld (hl),a
                out (LINK_CTRL),a
                ret

ctrl_or:        ld hl,CTRL_SHADOW
                or (hl)
                ld (hl),a
                out (LINK_CTRL),a
                ret
