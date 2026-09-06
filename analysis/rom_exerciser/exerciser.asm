; ---------------------------------------------------------------------------
; Micronic 1000 link-controller exerciser
;
; Replaces the cold-boot entry so the machine becomes a dedicated test rig:
; no firmware, no menus, nothing else touching 4Ah-4Fh.  It drives the link
; controller through the states the firmware drives it through, and streams
; what the controller reports back onto the IR line, for as long as it is
; powered.
;
; The reporting channel is LINK_TXD itself: a write to 4Dh puts a byte on the
; wire, which the existing Arduino receiver already decodes.  No LCD, no
; keyboard, no extra hardware, and it exercises the transmit path at the same
; time.
;
; --- what it is measuring --------------------------------------------------
;
; LinkBlockTx dies at ROM00:32F3 waiting for LINK_STATUS bit 6 (HSBUSY) to go
; CLEAR, and reports 0EEh -- the 238 on the error screen.  The direction
; matters and is easy to get backwards: the bit is asserted by the controller
; when the handshake starts and the firmware waits for it to fall.  So merely
; watching an idle controller says nothing.  The handshake has to be armed
; first, and that is what phase 1 below does, using the exact sequence from
; ROM00:32CC.
;
; The three sequences this replays are all byte-verified:
;
;   32CC-32EE   TX handshake arm:  CTRL |= 20h, CTRL |= 10h, delay, CTRL &= DFh
;   3378-33A6   RX arm:            CTRL &= FEh, CTRL |= 20h, dummy read of
;                                  LINK_RXD, CTRL |= 10h, delay, CTRL &= DFh
;   3358-3374   teardown:          CTRL &= EFh, CTRL &= FEh
;
; The firmware transmits with CTRL in the state the TX arm leaves (32F3 falls
; through to the OUTI loop at 3311), so phase 1 can stay armed for a whole
; frame without endangering the reporting channel.
;
; Two status bits besides HSBUSY are known, both from the firmware's own
; polls: bit 7 is TXRDY, waited high at 34FB, and bit 0 is "receive byte
; available", gating the INI loop at 33CF.  Bit 0, not bit 4, is the bit that
; says something arrived.
;
; --- phases -----------------------------------------------------------------
;
; Four, one per frame, cycling forever.  The phase is the top two bits of the
; record counter, so it costs nothing to encode and cannot drift out of step
; with the frame boundaries.
;
;   0  baseline    CTRL as LinkBlockTx's opening leaves it.  Establishes the
;                  resting value of every status bit, which is the control
;                  every other phase is read against.
;   1  TX armed    the 32CC sequence, then held for the frame.  THE question:
;                  does HSBUSY fall?  A frame is ~470 ms, where the firmware
;                  allows 9.92 ms -- so this is far more patient than the
;                  firmware, and a late fall would itself explain everything.
;   2  RX armed    the 3378 sequence, then held.  Does bit 0 ever set, and
;                  does LINK_RXD ever come back non-zero?
;   3  CTRL sweep  one value per frame, advancing each cycle, covering all
;                  256.  The firmware only ever writes bits 0, 1, 4 and 5, so
;                  bits 2, 3, 6 and 7 are untried.  Bit 1 is forced to the
;                  selected port so the sweep cannot switch ports underneath
;                  the measurement.
;
; A CTRL value that stops the controller accepting bytes would stall the
; reporting channel, so waitready has a watchdog: after ~9 ms with no TXRDY it
; puts the baseline back and carries on.  No phase can wedge the run.
;
; --- wire format ------------------------------------------------------------
;
; One preamble frame, then record frames of 64 records forever.  Every frame
; is preceded by a ~4 ms idle gap and begins with an HDLC flag, and a record
; frame's first record always carries a counter that is a multiple of 64, so
; the receiver resynchronises every ~440 ms and byte alignment is never in
; doubt.
;
; The gap is not optional.  The Arduino receiver delimits bursts by an idle
; period (GAP_US), so an unbroken stream would never be emitted at all; the
; controller is simply not fed for long enough to drain its shifter and stop
; clocking.  Status is still sampled all the way through it.
;
;   preamble   A5 5A VER ID PROBE STATUS      (6 bytes, sent once)
;   record     COUNT OR AND RXD SIDE CTRL     (6 bytes, ~7.3 ms apart)
;
;     COUNT   rolling record number; +1 per record, so a dropped or garbled
;             record is visible and the counter doubles as a time base.  Its
;             top two bits are the phase.
;     OR      every LINK_STATUS sample seen since the last record, OR'd
;     AND     every LINK_STATUS sample seen since the last record, AND'd
;     RXD     LINK_RXD, read once per record
;     SIDE    port 2Dh, the 5-pin side port, read once per record
;     CTRL    the LINK_CTRL value in force, so a capture is self-describing
;             and the sweep needs no schedule shared with the decoder
;
; OR and AND are why a slow record rate costs nothing.  Waiting for TXRDY is a
; tight polling loop -- one LINK_STATUS sample every ~35 us -- and every
; sample folds into both accumulators, so a bit that pulses high for a single
; 122 us wire cell still appears in OR, and one that drops for a single cell
; still appears in AND.  A genuinely constant bit reads the same in both.
; Nothing on the wire's own timescale can be aliased away; only the ordering
; of events inside one record is lost.
;
; LINK_PROBE is read once, into the preamble, rather than in the loop: its
; read side effects are unknown, and the point is to measure HSBUSY without
; confounds.
;
; SIDE is here to bootstrap the next burn rather than to measure the link.
; The firmware reads bits 0 and 1 of 2Dh (ROM00:1299), the barcode front end
; uses the port, and it is reachable from outside the case -- so it is a
; command channel into a future exerciser that does not depend on the IR link
; working.  Holding each side-port pin while watching SIDE identifies the
; wiring.  A different peripheral entirely, so it cannot confound the
; LINK_STATUS measurement.
;
; Before any of that, a ~1.9 s beacon squares the two side-port output bits,
; so that a silent IR line can be told from a CPU that never ran.
;
; All loop state lives in memory rather than registers, so every register is
; free scratch inside the helpers.  It costs a few microseconds of sample
; period and buys freedom from the aliasing bugs that register pressure
; produces.
; ---------------------------------------------------------------------------

LINK_CTRL       equ 0x4A
LINK_STAT       equ 0x4B
LINK_CMD        equ 0x4C
LINK_TXD        equ 0x4D
LINK_RXD        equ 0x4E
LINK_PROBE      equ 0x4F
SIDE_PORT       equ 0x2D            ; 5-pin side port in;  bits 0,1 read at 1299
PORT_2C         equ 0x2C            ; 5-pin side port out; bits 0,1 driven at 1283
PORT_2A         equ 0x2A

CTRL_SHADOW     equ 0xF794          ; the firmware's LINK_CTRL shadow
CMD_SHADOW      equ 0xF796          ; ... and its LINK_CMD shadow (see 34F2)
PORT2A_SHADOW   equ 0xF78B
PORT2C_SHADOW   equ 0xF78D

LinkPortSelect  equ 0x3454
LinkProbe       equ 0x348A
LinkPresent     equ 0x34EC          ; polls TXRDY, then writes 81h to LINK_CMD
LinkWaitReady   equ 0x34F8          ; polls TXRDY, DE=02DAh; returns Z on timeout

; Bit 5 clear is the TOP port (V24 ADAPTOR): selecting V24 ADAPTOR resolves to
; g_bDeviceWireId4 = 43h, whose AND 20h at LinkBlockTx is zero, and the owner
; captured the handheld's bursts at the top port under that selection.  63h
; takes the other latch path, which is the back port (PLINTH) by elimination.
LINK_ID         equ 0x43            ; top port
VERSION         equ 0x06            ; bumped whenever the wire format changes
STACK           equ 0xC800          ; upper TPA, documented free in the RAM map

; Loop state.  Well clear of the stack, which never goes more than 3 deep.
V_OR            equ 0xC7E0          ; sticky OR of LINK_STATUS, this window
V_AND           equ 0xC7E1          ; sticky AND of LINK_STATUS, this window
V_COUNT         equ 0xC7E2          ; record counter; top 2 bits are the phase
V_BASE          equ 0xC7E3          ; LINK_CTRL as the frame opening left it
V_SWEEP         equ 0xC7E4          ; phase 3's value, +1 each cycle
V_WD            equ 0xC7E5          ; waitready watchdog

LO_ORG          equ 0x724C          ; the second free block, 183 bytes
HI_ORG          equ 0x7E96          ; the first, 356 bytes

FRAME_RECS      equ 0x3F            ; mask: new frame when (COUNT and this) = 0
GAP_SAMPLES     equ 0xC0            ; ~4 ms of idle; must exceed the receiver's
                                    ; GAP_US plus the controller's drain time
WD_SAMPLES      equ 0xFF            ; ~9 ms before waitready restores the base
ARM_DELAY       equ 0x20            ; the firmware's own djnz count (32E1, 339B)


                org LO_ORG

; ---------------------------------------------------------------------------
; Sampling and the wire
; ---------------------------------------------------------------------------

; Take one LINK_STATUS sample and fold it into the sticky accumulators.
; Returns the raw sample in A.  Clobbers A, D, HL.
sample:         in a,(LINK_STAT)
                ld d,a
                ld hl,V_OR
                or (hl)
                ld (hl),a
                inc hl
                ld a,d
                and (hl)
                ld (hl),a
                ld a,d
                ret

accreset:       xor a
                ld (V_OR),a
                ld a,0xFF
                ld (V_AND),a
                ret

; Poll until TXRDY (bit 7).  Blocks rather than timing out the way
; LinkWaitReady does, so records never fragment and byte alignment on the wire
; is exact.  The watchdog is what makes the CTRL sweep safe: a value that
; stops the controller accepting bytes would otherwise wedge the run, so after
; ~9 ms of no TXRDY the baseline goes back and the wait restarts.  A silent
; wire therefore means the controller never asserts TXRDY even at the
; baseline, which is a real result rather than a hang.
waitready:      ld a,WD_SAMPLES
                ld (V_WD),a
wr_loop:        call sample
                bit 7,a
                ret nz
                ld hl,V_WD
                dec (hl)
                jr nz,wr_loop
                ld a,(V_BASE)
                call ctrl_set
                jr waitready

; A = byte to put on the wire.
putbyte:        ld c,a
                call waitready
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

; Idle long enough for the receiver to call it a gap: stop feeding LINK_TXD
; and let the controller drain and stop clocking, sampling throughout.
gap:            ld b,GAP_SAMPLES
gap_loop:       call sample                 ; sample leaves B alone
                djnz gap_loop
                ret

; ---------------------------------------------------------------------------
; LINK_CTRL, always through the firmware's shadow so a read-modify-write never
; loses a bit another routine set.
; ---------------------------------------------------------------------------
ctrl_and:       ld hl,CTRL_SHADOW
                and (hl)
                jr ctrl_put
ctrl_or:        ld hl,CTRL_SHADOW
                or (hl)
                jr ctrl_put
ctrl_set:       ld hl,CTRL_SHADOW
ctrl_put:       ld (hl),a
                out (LINK_CTRL),a
                ret

; ---------------------------------------------------------------------------
; Waggle the two side-port output bits for ~1.9 s before anything touches the
; link.  Two jobs, and the second is why it is worth the bytes.
;
; It proves the patch is running.  A silent IR line is otherwise ambiguous
; between "the controller never asserts TXRDY", which is a real result, and
; "the CPU never got here", which is a bad burn or a bad socket -- and telling
; those apart afterwards would cost a swap cycle.
;
; And it maps the side port outwards.  Bit 0 squares at ~8.7 Hz and bit 1 at
; ~4.3 Hz, so a probe on any external pin identifies which bit it carries;
; SIDE in the record stream does the same for the inputs.  Together they give
; the two-wire command channel the next exerciser needs.
;
; Bits 0 and 1 of 2Ch are what the barcode front end itself drives (1283,
; 1292, 1519, 1528), so this stays inside behaviour the firmware already has.
; It finishes by writing 0, which is where LinkPortSelect expects to start.
beacon:         ld b,0x20                   ; 32 half-steps
bcn_step:       ld a,b
                and 0x03                    ; bit 0 every step, bit 1 every 2
                ld (PORT2C_SHADOW),a
                out (PORT_2C),a
                ld de,0x2000                ; ~58 ms
bcn_wait:       dec de
                ld a,d
                or e
                jr nz,bcn_wait
                djnz bcn_step
                xor a
                ld (PORT2C_SHADOW),a
                out (PORT_2C),a
                ret
lo_end:

                org HI_ORG

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
                ld (V_SWEEP),a
                ld (V_BASE),a

                call beacon

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

                ; Whatever that left is the baseline every phase returns to,
                ; and the state the watchdog restores.
                ld a,(CTRL_SHADOW)
                ld (V_BASE),a

                ; --- open the frame.  If the controller never reports ready
                ; there is nothing to report with, so silence on the wire is
                ; itself the result: it would mean TXRDY never asserts.
                call LinkPresent
                jr z,dead
                call LinkWaitReady
                jr z,dead

                call accreset

                ; --- preamble.  Identifies the image and its wire format, and
                ; gives the receiver a known 6 bytes to confirm alignment on
                ; before any measurement is read.
                ld a,0xA5
                call putbyte
                ld a,0x5A
                call putbyte
                ld a,VERSION
                call putbyte
                ld a,LINK_ID
                call putbyte
                in a,(LINK_PROBE)           ; read once, never in the loop
                call putbyte
                in a,(LINK_STAT)
                call putbyte

                xor a
                ld (V_COUNT),a

                ; --- stream records forever
stream:         ld a,(V_COUNT)
                and FRAME_RECS
                call z,newframe             ; gap, flag, then the phase's state

                ld a,(V_OR)                 ; snapshot the window just ended --
                ld b,a                      ; taken after the gap, so windows
                ld a,(V_AND)                ; are contiguous and the gap is not
                ld e,a                      ; a blind spot.  B and E, not C:
                                            ; putbyte uses C.
                call accreset

                ld a,(V_COUNT)
                call putbyte                ; [0] COUNT
                ld a,b
                call putbyte                ; [1] OR of LINK_STATUS
                ld a,e
                call putbyte                ; [2] AND of LINK_STATUS
                in a,(LINK_RXD)             ; read after status, so a status
                call putbyte                ; [3] bit cleared by the read still
                in a,(SIDE_PORT)            ;     shows in this record
                call putbyte                ; [4] SIDE
                ld a,(CTRL_SHADOW)
                call putbyte                ; [5] CTRL in force

                ld hl,V_COUNT
                inc (hl)
                jr stream

dead:           jr dead

; ---------------------------------------------------------------------------
; Frame boundary: idle, flag, then put the controller into this phase's state.
; ---------------------------------------------------------------------------
newframe:       call gap
                call putflag

                ld a,(V_BASE)               ; every phase starts from the
                call ctrl_set               ; baseline, so phases cannot
                                            ; accumulate on one another
                ld a,(V_COUNT)
                and 0xC0                    ; the phase
                jr z,nf_done                ; 0: baseline, nothing more
                cp 0x40
                jr z,tx_arm                 ; 1: TX handshake armed
                cp 0x80
                jr z,rx_arm                 ; 2: RX armed
                                            ; 3: falls into the sweep

; Phase 3.  One CTRL value per frame, advancing each cycle so all 256 are
; covered.  Bit 1 is forced back to the selected port: sweeping it would
; switch ports underneath the measurement, which is a confound rather than an
; experiment.
sweep:          ld hl,V_SWEEP
                inc (hl)
                ld a,(V_BASE)
                and 0x02
                ld c,a
                ld a,(hl)
                and 0xFD
                or c
                call ctrl_set
nf_done:        ret

; ROM00:32CC-32EE, byte for byte.  This is what makes HSBUSY mean anything:
; the controller asserts it here, and the firmware's 9.92 ms wait at 32F3 is
; for it to fall again.
tx_arm:         ld a,0x20
                call ctrl_or
                ld a,0x10
                call ctrl_or
                ld b,ARM_DELAY
tx_wait:        djnz tx_wait
                ld a,0xDF
                jp ctrl_and

; ROM00:3378-33A6, byte for byte, dummy LINK_RXD read included -- it is what
; flushes the receiver before arming.
rx_arm:         ld a,0xFE
                call ctrl_and
                ld a,0x20
                call ctrl_or
                in a,(LINK_RXD)
                ld a,0x10
                call ctrl_or
                ld b,ARM_DELAY
rx_wait:        djnz rx_wait
                ld a,0xDF
                jp ctrl_and
hi_end:
