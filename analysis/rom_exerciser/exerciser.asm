; ---------------------------------------------------------------------------
; Micronic 1000 link-controller exerciser
;
; Replaces the cold-boot entry so the machine becomes a dedicated test rig:
; no firmware, no menus, nothing else touching 4Ah-4Fh.  It opens a frame the
; way LinkBlockTx does, then streams LINK_STATUS onto the IR line, one byte
; per sample, for as long as it is powered.
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
; The firmware's own link routines are called rather than reimplemented, so
; the latch sequences are identical to the ones the real transmit path uses.
; ---------------------------------------------------------------------------

LINK_CTRL       equ 0x4A
LINK_STAT       equ 0x4B
LINK_TXD        equ 0x4D

CTRL_SHADOW     equ 0xF794          ; the firmware's LINK_CTRL shadow
PORT2A_SHADOW   equ 0xF78B
PORT2C_SHADOW   equ 0xF78D

LinkPortSelect  equ 0x3454
LinkProbe       equ 0x348A
LinkPresent     equ 0x34EC          ; polls TXRDY, then writes 81h to LINK_CMD
LinkWaitReady   equ 0x34F8          ; polls TXRDY, DE=02DAh; returns Z on timeout

LINK_ID         equ 0x43            ; id bit 5 clear; use 63h for the other port
STACK           equ 0xC800          ; upper TPA, documented free in the RAM map

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

                ; --- stream LINK_STATUS forever, one byte per sample
stream:         in a,(LINK_STAT)
                ld c,a
                call LinkWaitReady
                jr z,stream                 ; not ready: drop it, keep sampling
                ld a,c
                out (LINK_TXD),a
                jr stream

dead:           jr dead

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
