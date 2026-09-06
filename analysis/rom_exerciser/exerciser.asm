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
;                  256.  The firmware writes bits 0, 1, 4 and 5 directly, and
;                  bits 6 and 7 through the pair 34BD (sets both) and 34D2
;                  (clears both, called from LinkProbe and from LinkBlockTx's
;                  entry), so only bits 2 and 3 are genuinely untried -- but
;                  the *combinations* are not, and that is what this covers.
;                  Bit 1 is forced to the selected port so the sweep cannot
;                  switch ports underneath the measurement.
;
; The port alternates on every counter wrap, at phase 0, so one burn exercises
; both.  Which physical window a given latch state drives is NOT decidable
; from the ROM -- see port_swap -- so this measures it instead of assuming it.
; LINK_CTRL bit 1 is in every record, so a capture says which port was live.
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
;   preamble   A5 5A VER PSTAT STATUS         (5 bytes, sent once)
;              PSTAT = LINK_STATUS as LinkProbe left it, STATUS = after the
;              frame opening.  The link id is not here: CTRL bit 1 in every
;              record names the live port, and the port alternates anyway.
;   record     COUNT OR AND RXD SIDE CTRL WD KEY IRQN ISTAT
;                                             (10 bytes, ~12 ms apart --
;                                              exactly one 20-column LCD row)
;
;     COUNT   rolling record number; +1 per record, so a dropped or garbled
;             record is visible and the counter doubles as a time base.  Its
;             top two bits are the phase.
;     OR      every LINK_STATUS sample seen since the last record, OR'd
;     AND     every LINK_STATUS sample seen since the last record, AND'd
;     RXD     LINK_RXD, read once per record
;     SIDE    port 2Dh, the 8-pin side port, read once per record
;     CTRL    the LINK_CTRL value this phase asked for, so a capture is
;             self-describing and the sweep needs no schedule shared with
;             the decoder
;     KEY     the keypad index (col*6 + row) of the first key held, or FFh.
;             Press keys and watch this to map the keypad; it is also how
;             a future exerciser will be steered, with no wiring at all.
;     IRQN    rolling count of interrupts taken -- link (source 2) and
;             keypad (source 0), the latter only so the path can be proved
;             live by hand; see IRQ_ENABLE.  The firmware's
;             receive path is interrupt-driven (IRQ source 2, handler
;             ROM00:31B6), so a controller could signal without ever setting
;             a bit that a poll catches.  This is the only field that would
;             notice.
;     ISTAT   LINK_STATUS OR'd across every interrupt taken so far, sticky
;             for the whole run -- the status the controller had when it
;             decided to interrupt, which is not the same as any status a
;             poll happens to catch.
;     WD      rolling count of waitready watchdog trips.  It rises only when
;             a LINK_CTRL value stopped the controller accepting bytes, which
;             is the one sweep outcome that would otherwise be invisible:
;             the value that stalls the reporting channel cannot report
;             itself.  CTRL still names it because the watchdog restores the
;             hardware without touching V_CTRL.
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
SIDE_PORT       equ 0x2D            ; 8-pin side port in;  bits 0,1 read at 1299
PORT_2C         equ 0x2C            ; 8-pin side port out; bits 0,1 driven at 1283
PORT_2A         equ 0x2A

CTRL_SHADOW     equ 0xF794          ; the firmware's LINK_CTRL shadow
CMD_SHADOW      equ 0xF796          ; ... and its LINK_CMD shadow (see 34F2)
PORT2A_SHADOW   equ 0xF78B
PORT2C_SHADOW   equ 0xF78D

LinkPortSelect  equ 0x3454
LinkProbe       equ 0x348A
LinkPresent     equ 0x34EC          ; polls TXRDY, then writes 81h to LINK_CMD
LinkWaitReady   equ 0x34F8          ; polls TXRDY, DE=02DAh; returns Z on timeout

; 63h is the TOP port (V24 ADAPTOR), 43h the back one (PLINTH).  Established
; by driving the firmware's own menu in the emulator: selecting V24 ADAPTOR
; leaves FDD4 = 63h and LinkPortSelect takes the bit5-SET branch (2Ch = 00,
; LINK_CTRL bit 1 clear); PLINTH leaves 43h and the bit5-clear branch
; (2Ch = 20, bit 1 set).  The static trace agrees -- see the exerciser README.
; The port still alternates every cycle, so a wrong guess here costs nothing.
LINK_ID         equ 0x63            ; top port, and the first one exercised
VERSION         equ 0x0C            ; bumped whenever the wire format changes
STACK           equ 0xC800          ; upper TPA, documented free in the RAM map

; Loop state.  Well clear of the stack, which never goes more than 3 deep.
V_OR            equ 0xC7E0          ; sticky OR of LINK_STATUS, this window
V_AND           equ 0xC7E1          ; sticky AND of LINK_STATUS, this window
V_COUNT         equ 0xC7E2          ; record counter; top 2 bits are the phase
V_BASE          equ 0xC7E3          ; LINK_CTRL as the frame opening left it
V_SWEEP         equ 0xC7E4          ; phase 3's value, +1 each cycle
V_WD            equ 0xC7E5          ; waitready watchdog
V_ID            equ 0xC7E6          ; current link id; bit 5 alternates the port
V_CTRL          equ 0xC7E7          ; LINK_CTRL the phase asked for (see WD)
V_WD_N          equ 0xC7E8          ; rolling count of watchdog trips
V_PSTAT         equ 0xC7E9          ; LINK_STATUS as LinkProbe left it
V_KEY           equ 0xC7EA          ; key index this record, or FFh
V_IRQN          equ 0xC7EB          ; link interrupts seen, rolling.  Must stay
V_ISTAT         equ 0xC7EC          ; directly below V_ISTAT: the ISR walks
                                    ; from one to the other with DEC HL

ISR_ORG         equ 0x0047          ; fifth free block, 31 bytes, between the
                                    ; bank-init tail at 0044 and NMI at 0066
NMI_ORG         equ 0x0069          ; sixth free block, 23 bytes, the gap
                                    ; after the NMI vector at 0066
VEC_ORG         equ 0x00A2          ; third free block, 94 bytes, above every
                                    ; reset vector and below the boot vector
LO_ORG          equ 0x724C          ; second free block, 183 bytes
MID_ORG         equ 0x7CE0          ; fourth, 48 bytes, past the end of the
                                    ; module-A copy range (73CE-7C2E)
HI_ORG          equ 0x7E96          ; first free block, 356 bytes

LCD_REG         equ 0x23            ; HD61830 register index
LCD_DAT         equ 0x03            ; ... and its data port
LCD_CONTRAST    equ 0x46            ; contrast DAC; see CONTRAST below

; ---------------------------------------------------------------------------
; DISPLAY CONTRAST -- change this one number if the screen is unreadable.
;
; Port 46h is the contrast DAC.  The firmware keeps its level in ram:FC05 and
; pushes it out at ROM00:1FD4 (LD A,(FC05) / LD C,46h / OUT (C),A -- an ED 79
; form, which is why a scan for D3 46 does not find it).
;
;   range        00h to FFh
;   LOWER        lighter.  The firmware's adjust-down key steps DEC A twice
;                and clamps at 0 (ROM00:1D4A); adjust-up does INC A twice and
;                clamps at FFh (ROM00:1D60).  So the UI moves in steps of 2.
;   firmware     70h, set at cold boot (ROM00:0257).  The owner reports this
;   default      is almost black on this unit and turns it down by hand every
;                time, which is exactly the thing this constant exists to
;                avoid -- there is no settings UI here to reach for.
;
; If the screen is still too dark, lower it; if it has gone too faint, raise
; it.  Rebuild and reburn; nothing else depends on the value.
;
; Not to be confused with port 2Bh, which an earlier version of this file had
; wrong: 2Bh is the BEEPER, and writing a contrast value to it would have made
; the unit sound continuously.  Confirmed against the MAME driver
; (micronic.cpp): 2Bh beep_w, 46h lcd_contrast_w, 2Ch bit 4 backlight.
; ---------------------------------------------------------------------------
CONTRAST        equ 0x40            ; a good way below the stock 70h

KbdStrobeAll    equ 0x1A42          ; drive all six columns, then fall into...
KbdStrobe       equ 0x1A44          ; A = column mask -> A = row bits, 3Fh
PORT_KBD_DRV    equ 0x02            ; write-only in the ROM
IRQ_MASK        equ 0x04            ; interrupt enable, ACTIVE LOW
IRQ_STATUS      equ 0x05            ; pending, active low; reading acknowledges
; ~05h: bit 2, the link, plus bit 0, the keypad.  The keypad is here on
; purpose.  With the link alone, a flat IRQN would be ambiguous between "the
; controller never interrupts" -- the result we want -- and "the interrupt
; setup is broken", which is not a result at all.  The keypad is a genuine
; interrupt source, so pressing keys proves the path works end to end; KEY
; disambiguates afterwards, since an interrupt taken while KEY reads FFh had
; no key down.
;
; Not a guess: the firmware writes exactly FAh to 04h when it sleeps
; (ROM00:1779), and all three of its sleep masks enable bit 0, because the
; keypad is what wakes the machine.  Note KEY itself does NOT come from the
; interrupt -- kbd_scan polls the matrix directly through ROM00:1A44 -- which
; is precisely why KEY alone could never have proved the interrupt path live.
IRQ_ENABLE      equ 0xFA
RST38_VECTOR    equ 0xF5F3          ; the ROM's 0038 jumps through this RAM
NMI_VECTOR      equ 0xF5F6          ; cell, and 0066 through this one
PORTMAP_BITS    equ 0x33            ; which 2Ch bits the pin walk drives:
                                    ; 0, 1, 4 and 5, the ones the firmware
                                    ; itself drives.  FFh also walks 2, 3, 6
                                    ; and 7, which no ROM instruction ever
                                    ; sets -- unknown territory, and the unit
                                    ; powering off mid-walk would be the
                                    ; first thing you learn about them.

FRAME_RECS      equ 0x3F            ; mask: new frame when (COUNT and this) = 0
GAP_SAMPLES     equ 0xC0            ; ~4 ms of idle; must exceed the receiver's
                                    ; GAP_US plus the controller's drain time
WD_SAMPLES      equ 0xFF            ; ~9 ms before waitready restores the base
ARM_DELAY       equ 0x20            ; the firmware's own djnz count (32E1, 339B)


                org ISR_ORG

; --- The link interrupt.  ROM00:31B6 is the firmware's own handler for it
; (IRQ source 2, see reference/memory-map.md#link-interrupt): it tests
; LINK_STATUS bit 4 and enters LinkBlockRx if set.  So the receive path is
; normally interrupt-driven, and an exerciser that only ever polls would miss
; a controller that signals but never sets a bit a poll would catch.
;
; This one records rather than services: count the interrupts, and OR the
; status at interrupt time into its own accumulator, which is the value the
; controller had when it decided to interrupt -- not the same thing as any
; status a poll happens to catch.
;
; It masks everything on the way in and the record loop re-arms once per
; record, so a source that asserts continuously costs one interrupt per
; record instead of livelocking the machine.  Reading 05h acknowledges.
isr:            push af
                push hl
                ld a,0xFF
                out (IRQ_MASK),a
                in a,(LINK_STAT)
                ld hl,V_ISTAT
                or (hl)
                ld (hl),a
                dec hl                      ; V_IRQN sits just below V_ISTAT
                inc (hl)
                in a,(IRQ_STATUS)
                pop hl
                pop af
                ei
                ret
isr_end:

                org NMI_ORG

; Reached only when the controller will not open a frame at all.  Shows DEAD
; on the glass -- spelled with the hex printer, so it costs no string table
; -- which is otherwise indistinguishable from every other kind of silence.
dead:           xor a
                call lcd_at
                ld a,0xDE
                call lcd_hex
                ld a,0xAD
                call lcd_hex
dead_loop:      jr dead_loop

; NMI at ROM00:0066 jumps through F5F6, which is uninitialised here.  A bare
; RET there turns a non-maskable interrupt from a jump into whatever RAM holds
; into a no-op.  It lives in this block because this block is what follows the
; vector it protects.
nmi_safe:       ld a,0xC9
                ld (NMI_VECTOR),a
                ret
nmi_end:

                org VEC_ORG

; --- Scan the 6x6 keypad the way Kbd_ScanMain does at ROM00:190D: drive one
; column at a time through the firmware's own strobe helper, which writes
; port 02h, settles with two PUSH/POP pairs, and returns port 00h masked to
; the six row bits.  Returns the first key found as col*6 + row -- the same
; index tbl_kbd_map is built on -- or FFh for none.
;
; This is the input channel the exerciser was missing.  It needs no wiring,
; unlike port 2Dh, and it is reported in every record, so pressing keys and
; watching the KEY field maps the keypad without knowing the keymap first.
;
; KbdStrobe preserves BC, DE and HL (it saves HL with PUSH/POP), so the scan
; needs no spills.
kbd_scan:       ld b,0x06                   ; six columns
                ld c,0x00                   ; column index
                ld d,0x01                   ; column drive bit
ks_col:         ld a,d
                call KbdStrobe
                or a
                jr nz,ks_hit
                inc c
                sla d
                djnz ks_col
                ld a,0xFF                   ; nothing pressed
                ret
ks_hit:         ld e,a                      ; row bits
                ld a,c
                add a,a                     ; 2*col
                ld c,a
                add a,a                     ; 4*col
                add a,c                     ; 6*col
                ld c,a
                ld b,0x00
ks_row:         rr e                        ; lowest set row wins
                jr c,ks_done
                inc b
                jr ks_row
ks_done:        ld a,c
                add a,b
                ret

; --- Walk the port-2Ch output bits with a countable pulse code: bit 0 pulses
; once, bit 1 twice, and so on, each group separated by a long gap.  Probe a
; connector pin, count the pulses, and you have its bit -- no timing
; reference, no second channel, an LED and an eye would do.
;
; Entered by holding any key at power-up, and never left: it is a different
; job from measuring the link, and it drives 2Ch bits that are not connector
; pins at all.
;
; Two of the four groups identify themselves without a probe.  2Ch bit 4 is
; the LCD BACKLIGHT, so its five-pulse group flashes the screen; bit 5 is the
; IR port select.  That leaves bits 0 and 1 -- the pair the barcode front end
; drives at ROM00:1283 and 1519 -- as the real side-connector candidates, and
; the other two groups as a free calibration of the count.
portmap:        ld d,0x01                   ; bit under test
                ld c,0x01                   ; ... pulses that many times
pm_bit:         xor a
                call lcd_at
                ld a,d
                call lcd_hex                ; which bit is pulsing now
                ld a,PORTMAP_BITS
                and d
                jr z,pm_gap                 ; not in the set: silent slot, so
                ld b,c                      ; the count still equals the bit
pm_pulse:       ld a,d
                out (PORT_2C),a
                call pm_delay
                xor a
                out (PORT_2C),a
                call pm_delay
                djnz pm_pulse
pm_gap:         call pm_delay               ; four delays: a gap long enough
                call pm_delay               ; to be unmistakable between
                call pm_delay               ; groups
                call pm_delay
                inc c
                sla d
                jr nz,pm_bit
                jr portmap

vec_end:

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
                ld hl,V_WD_N                ; mark the trip in the record
                inc (hl)
                ld a,(V_BASE)               ; restore the hardware, but NOT
                ld (CTRL_SHADOW),a          ; V_CTRL: the record must still
                out (LINK_CTRL),a           ; name the value that stalled
                jr waitready

; A stall needs no separate signal now.  putbyte blocks, so the record loop
; stops and the LCD stops with it -- and a frozen display beside a counting
; one is unmistakable.  WD in the last record shown names how many trips it
; took to get there.

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
                ld (V_CTRL),a               ; what was asked for -- the
                out (LINK_CTRL),a           ; watchdog restores without
                ret                         ; touching this, so a stall stays
                                            ; attributable to its own value

; ---------------------------------------------------------------------------
; HD61830 LCD.  Register-indexed: port 23h picks the register, port 03h
; carries the byte.  Nothing here is invented -- the init values are the ones
; the firmware writes at boot, captured from a stock emulator run, and the
; contrast value is the firmware's own, turned down.  Skipping all of it is
; why a patched boot shows nothing usable: nothing has configured the
; controller, set the contrast DAC, or cleared 160 cells of power-on garbage
; out of the display RAM.
;
; This is now the primary liveness indicator, and a better one than the
; side-port beacon it replaces: text on the glass cannot be mistaken for
; anything else.  The beacon's other job, mapping pins, belongs to the pin
; walk.
;
; Port map, confirmed against the MAME driver (micronic.cpp) as well as the
; ROM: 00h keypad read, 02h keypad drive, 03h/23h HD61830 data/control,
; 08h/28h RTC, 2Bh BEEPER, 2Ch bit 4 backlight, 46h contrast, 47h bank select,
; 48h/49h status flag.  MAME does not model 4Ah-4Fh at all, which is the whole
; reason this exerciser exists.
; ---------------------------------------------------------------------------

; A = cell address 0..159.  The controller auto-increments after each data
; write, so a run of characters needs this once.
; R11, the address high byte, is always zero for 160 cells, so lcd_init sets
; it once and this only touches R10.
lcd_at:         push af
                ld a,0x0A
                out (LCD_REG),a
                pop af
                out (LCD_DAT),a
                ret

; A = character.  Clobbers A only, which is why it is not ROM00:1F79 -- that
; one uses BC, and every caller here is a counting loop.
lcd_putc:       push af
                ld a,0x0C
                out (LCD_REG),a
                pop af
                out (LCD_DAT),a
                ret

; A = byte, shown as two hex digits.  Falls into lcd_nib for the low one.
lcd_hex:        push af
                rrca
                rrca
                rrca
                rrca
                call lcd_nib
                pop af
lcd_nib:        and 0x0F
                add a,0x30
                cp 0x3A
                jr c,lh_out
                add a,0x07                  ; 'A' - '0' - 10
lh_out:         jp lcd_putc

; A = byte: put it on the wire and on the glass.  The LCD copy is what makes
; the headline result readable with no Arduino, no scope and no decode.
emit:           push af
                call putbyte
                pop af
                jp lcd_hex

pm_delay:       ld hl,0x4000                ; ~115 ms
pm_wait:        dec hl
                ld a,h
                or l
                jr nz,pm_wait
                ret
lcd_tab:        db 0x00,0x3C, 0x01,0x75, 0x02,0x13, 0x03,0x3F
                db 0x04,0x07, 0x08,0x00, 0x09,0x00, 0x0B,0x00
lo_end:

                org MID_ORG

; The values the firmware writes at boot: R0 mode, R1 character pitch,
; R2 = 13h = 20 characters, R3 = 3Fh = 64 lines, R4 cursor, R8/R9 display
; start.  R10/R11 are set by lcd_at, so they are not in the table.
lcd_init:       ld hl,lcd_tab
                ld b,0x08
li_loop:        ld a,(hl)
                out (LCD_REG),a
                inc hl
                ld a,(hl)
                out (LCD_DAT),a
                inc hl
                djnz li_loop
                ld a,CONTRAST               ; see the CONTRAST block above
                out (LCD_CONTRAST),a
                xor a                       ; clear 160 cells of power-on
                call lcd_at                 ; garbage
                ld b,0xA0
li_clr:         ld a,0x20
                call lcd_putc
                djnz li_clr
                ret
mid_end:

                org HI_ORG

start:          di
                ld sp,STACK
                call lcd_init

                ; The ROM's RST 38h at 0038 jumps through F5F3 and NMI at 0066
                ; through F5F6, both uninitialised here.  Point the first at
                ; our handler -- the firmware installs its own the same way at
                ; ROM00:2893 -- and make the second a bare RET, so a
                ; non-maskable interrupt cannot land in whatever RAM holds.
                ld a,0xC3
                ld (RST38_VECTOR),a
                ld hl,isr
                ld (RST38_VECTOR+1),hl
                call nmi_safe
                im 1

                ; A key held at power-up selects the pin walk instead of the
                ; link run.  Checked before anything else touches the
                ; hardware, and it never returns.
                call KbdStrobeAll
                or a
                jp nz,portmap

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
                ld (V_CTRL),a
                ld (V_WD_N),a
                ld (V_IRQN),a
                ld (V_ISTAT),a
                ld a,LINK_ID
                ld (V_ID),a

                ; --- the cold-boot controller reset.  BEFORE the port
                ; select, not after: LinkProbe ends with XOR A / OUT (2Ch)
                ; at ROM00:34B1, which zeroes the port latch and would undo
                ; the selection.  It also calls 34D2, clearing LINK_CTRL bits
                ; 6 and 7 -- the state LinkBlockTx transmits in.
                call LinkProbe
                ld (V_PSTAT),a              ; it returns LINK_STATUS (34BA);
                                            ; the controller's state straight
                                            ; out of reset, worth having as a
                                            ; reference for every later sample

                ; --- select the port exactly as LinkBlockTx does at 3277
                ld a,LINK_ID
                and 0x20
                call LinkPortSelect

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
                ; LinkPresent uses the firmware's own 9.7 ms timeout, which
                ; a slow-starting controller could miss once.  Retry before
                ; concluding anything; after this, putbyte's watchdog covers
                ; the wait, so there is no second timeout to fail.
                ld b,0x10
open_try:       call LinkPresent            ; preserves BC
                jr nz,opened
                djnz open_try
                jp dead
opened:         call accreset

                ; --- preamble.  Identifies the image and its wire format, and
                ; gives the receiver a known 6 bytes to confirm alignment on
                ; before any measurement is read.
                ld a,0xA5
                call putbyte
                ld a,0x5A
                call putbyte
                ld a,VERSION
                call putbyte
                ld a,(V_PSTAT)              ; status as the reset left it
                call putbyte
                in a,(LINK_STAT)
                call putbyte

                xor a
                ld (V_COUNT),a

                ; --- stream records forever
stream:         ld a,(V_COUNT)
                and FRAME_RECS
                call z,newframe             ; gap, flag, then the phase's state

                ld a,IRQ_ENABLE          ; re-arm: the ISR masks on entry,
                out (IRQ_MASK),a            ; so this bounds it to one
                ei                          ; interrupt per record

                call kbd_scan               ; before the snapshot: this
                ld (V_KEY),a                ; clobbers B, C, D and E

                ld a,(V_OR)                 ; snapshot the window just ended --
                ld b,a                      ; taken after the gap, so windows
                ld a,(V_AND)                ; are contiguous and the gap is not
                ld e,a                      ; a blind spot.  B and E, not C:
                                            ; putbyte uses C.
                call accreset

                xor a                       ; the record also goes to the
                call lcd_at                 ; glass, top row, 16 hex digits

                ld a,(V_COUNT)
                call emit                   ; [0] COUNT
                ld a,b
                call emit                   ; [1] OR of LINK_STATUS
                ld a,e
                call emit                   ; [2] AND of LINK_STATUS
                in a,(LINK_RXD)             ; read after status, so a status
                call emit                   ; [3] bit cleared by the read still
                in a,(SIDE_PORT)            ;     shows in this record
                call emit                   ; [4] SIDE
                ld a,(V_CTRL)
                call emit                   ; [5] CTRL this phase asked for
                ld a,(V_WD_N)
                call emit                   ; [6] watchdog trips so far
                ld a,(V_KEY)
                call emit                   ; [7] key index, or FFh
                ld a,(V_IRQN)
                call emit                   ; [8] link interrupts so far
                ld a,(V_ISTAT)              ; [9] status at interrupt time,
                call emit                   ;     sticky across the whole run

                ld hl,V_COUNT
                inc (hl)
                jr stream

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
                jr z,port_swap              ; 0: baseline, and swap ports
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
                jp ctrl_set

; Alternate the port on every counter wrap, so one burn covers both.  Which
; physical window each latch state drives cannot be settled from the ROM: the
; chain from the menu choice to the wire id runs through compiler-generated
; forwarding frames, and the two readings of it disagree.  So do not infer it
; -- drive both and watch which window lights.  ~1.9 s each, alternating, and
; LINK_CTRL bit 1 is already in every record, so the capture says which state
; was live without needing a schedule.
port_swap:      ld hl,V_ID
                ld a,(hl)
                and 0x20
                call LinkPortSelect         ; select the id we hold now, so
                ld a,(hl)                   ; the first cycle is LINK_ID
                xor 0x20                    ; ... then flip for the next
                ld (hl),a
                ld a,(CTRL_SHADOW)          ; the swap moved bit 1; rebase
                ld (V_BASE),a
                ret

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
