; ---------------------------------------------------------------------------
; Micronic 1000 link-controller exerciser
; CURRENT BUILD: startup diagnostic, wire version 0Eh. Only the top V24
; baseline is exercised. Historical phase/sweep discussion below describes
; version 0Dh, not this build. Every ready timeout is terminal and visible.
;
; Replaces the cold-boot entry so the machine becomes a dedicated test rig:
; no firmware, no menus, nothing else touching 4Ah-4Fh.  It drives the link
; controller through the states the firmware drives it through, and streams
; what the controller reports back onto the IR line, for as long as it is
; powered.
;
; The reporting channel is LINK_TXD itself: a write to 4Dh puts a byte on the
; wire, which the existing Arduino receiver already decodes.  The LCD mirrors
; the first ten record fields and the keyboard supplies a positive interrupt
; control, so no extra hardware beyond the existing receiver is required.
;
; --- what it is measuring --------------------------------------------------
;
; LinkBlockTx reports 0EEh -- the 238 on the error screen -- after either its
; LINK_STATUS bit-6-clear wait at ROM00:32F3 or a per-byte LINK_STATUS
; bit-7-set wait beginning at ROM00:3318.  Merely watching an idle controller
; cannot distinguish those paths.  Phase 1 arms the handshake with the exact
; sequence from ROM00:32CC and records the complete LINK_STATUS byte.
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
;   1  TX armed    the 32CC sequence, then held for the frame.  Does
;                  LINK_STATUS bit 6 become set, and if so does it clear?
;                  A frame is well over 0.5 s, where the firmware allows
;                  9.92 ms for the clear wait.
;   2  RX armed    the 3378 sequence, then held.  Does LINK_STATUS bit 0 ever
;                  set, and does LINK_RXD ever come back non-zero?
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
; both.  The wire-ID-bit-5-clear state is the top V24 port; it drives
; LINK_CTRL bit 1 SET and port 2Ch bit 5 SET.  The complementary state is
; still worth observing at the back window.  LINK_CTRL bit 1 is in every
; record, so a capture says which state was live.
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
;   record     COUNT OR AND RXD SIDE CTRL WD KEY IRQN ISTAT ISRC
;                                             (11 bytes; first ten fill LCD row)
;
;     COUNT   rolling record number; +1 per record, so a dropped or garbled
;             record is visible and the counter doubles as a time base.  Its
;             top two bits are the phase.
;     OR      every LINK_STATUS sample seen since the last record, OR'd
;     AND     every LINK_STATUS sample seen since the last record, AND'd
;     RXD     LINK_RXD, read once per record
;     SIDE    port 2Dh, the 5-pin side port, read once per record
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
;     ISRC    active-high IRQ_STATUS source bits OR'd across every interrupt.
;             Bit 0 is the keypad and bit 2 is the link controller, so this
;             distinguishes them without inferring the source from KEY.
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
; The first ten fields also occupy exactly one 20-column LCD row.  ISRC is
; wire-only: its job is source attribution in a recorded capture, while IRQN
; and ISTAT retain the live interrupt indication on the glass.
;
; SIDE is here to bootstrap the next burn rather than to measure the link.
; The firmware reads bits 0 and 1 of 2Dh (ROM00:1299), the barcode front end
; uses the port, and it is reachable from outside the case -- so it is a
; command channel into a future exerciser that does not depend on the IR link
; working.  Holding each side-port pin while watching SIDE identifies the
; wiring.  A different peripheral entirely, so it cannot confound the
; LINK_STATUS measurement.
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

; A real V24 Load/Run trace uses 43h: LinkPortSelect takes the wire-ID-bit-5-
; clear branch, sets LINK_CTRL bit 1 and port 2Ch bit 5, and the owner
; observed the transmission at the top V24 window.  The run still alternates
; both states.
LINK_ID         equ 0x43            ; top V24 state first; alternates with 63h
VERSION         equ 0x0E            ; baseline-only startup diagnostic, same fields
STACK           equ 0xC900          ; upper TPA, documented free in the RAM map

; Loop state.  The stack starts 0x113 bytes above the last state byte.  A
; bounded emulator run found the deepest write only ten bytes below its old
; C800h top; the larger separation also covers an interrupt at that point
; without relying on so narrow a margin.
V_OR            equ 0xC7E0          ; sticky OR of LINK_STATUS, this window
V_AND           equ 0xC7E1          ; sticky AND of LINK_STATUS, this window
V_COUNT         equ 0xC7E2          ; record counter; no phase meaning in version 0Eh
V_SWEEP         equ 0xC7E3          ; reserved former sweep state
V_WD_N          equ 0xC7E4          ; reserved; zero in version 0Eh records
V_IRQN          equ 0xC7E5          ; interrupt entries seen, rolling. Must stay
                                    ; directly below V_ISTAT: the ISR walks
                                    ; from V_ISTAT to V_IRQN with DEC HL
V_ISTAT         equ 0xC7E6          ; sticky OR of LINK_STATUS at interrupt time
V_ISRC          equ 0xC7E7          ; active-high IRQ sources, sticky for run
V_WD            equ 0xC7E8          ; waitready watchdog
V_BASE          equ 0xC7E9          ; LINK_CTRL as the frame opening left it
V_ID            equ 0xC7EA          ; current wire ID; wire-ID bit 5 alternates
V_CTRL          equ 0xC7EB          ; LINK_CTRL the phase asked for (see WD)
V_PSTAT         equ 0xC7EC          ; LINK_STATUS as LinkProbe left it
V_KEY           equ 0xC7ED          ; key index this record, or FFh
V_STAGE         equ 0xC7EE          ; startup stage, retained on terminal error
V_TX_COUNT      equ 0xC7EF          ; completed LINK_TXD writes, modulo 256
V_FAIL          equ 0xC7F0          ; LINK_STATUS sampled on entry to error path
KEY_NO          equ 0x11            ; matrix index 17; keycode 01h in table
KEY_ENTER       equ 0x16            ; matrix index 22; keycode 0Dh in table
KEY_YES         equ 0x17            ; matrix index 23; keycode 06h in table

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
LCD_CONTRAST    equ 0x46            ; display contrast latch
LCD_CONTRAST_SHADOW equ 0xFC05       ; value written to port 46h by LcdInit

; ---------------------------------------------------------------------------
; DISPLAY CONTRAST -- change this one number if the screen is unreadable.
;
; Port 46h is the contrast DAC.  The firmware keeps its level in ram:FC05 and
; pushes it out at ROM00:1FD4 (LD A,(FC05) / LD C,46h / OUT (C),A -- an ED 79
; form, which is why a scan for D3 46 does not find it).
;
;   range        00h to FFh
;   NO           decrements twice toward darker and clamps at 00h
;                (ROM00:1D4A).
;   YES          increments twice toward lighter and clamps at FFh
;                (ROM00:1D60).  The 1E3E hardware run confirmed the visual
;                polarity: 00h is black and FFh is clear.
;   firmware     70h, set at cold boot (ROM00:0257).  The owner reports this
;   default      is almost black on this unit and turns it down by hand every
;                time, which is exactly the thing this constant exists to
;                avoid -- there is no settings UI here to reach for.
;
; The 1E3E hardware run proved LcdInit returns and FFh clears the panel, but
; offered no text against which to judge contrast.  Start this candidate at
; C0h, display the live value, poll NO/YES continuously through the stock
; saturating routines, and wait for ENTER before starting the link test.
;
; Not to be confused with port 2Bh, which an earlier version of this file had
; wrong: 2Bh is the BEEPER, and writing a contrast value to it would have made
; the unit sound continuously.  ROM accesses confirm the first two identities;
; the MAME driver (micronic.cpp) agrees and identifies port-2Ch bit 4 as the
; backlight, which remains LIKELY rather than byte-confirmed here.
; ---------------------------------------------------------------------------
CONTRAST        equ 0xA4            ; owner-preferred level in controlled 2D4D test

KbdStrobe       equ 0x1A44          ; A = column mask -> A = row bits, 3Fh
KbdBitIndex     equ 0x1A52          ; A one-hot -> A bit index (0..5)
ContrastDecrement equ 0x1D4A        ; shadow -= 2, floor 00h; writes port 46h
ContrastIncrement equ 0x1D60        ; shadow += 2, ceiling FFh; writes port 46h
LcdInit         equ 0x1EEC          ; complete stock LCD init and VRAM clear
PORT_KBD_DRV    equ 0x02            ; write-only in the ROM
KBD_SHADOW      equ 0xF782          ; firmware's port-02h working copy
IRQ_MASK        equ 0x04            ; interrupt enable, ACTIVE LOW
IRQ_STATUS      equ 0x05            ; pending, active low; reading acknowledges
SOUND           equ 0x2B            ; beeper value; zero is silent
; ~05h: bit 2, the link, plus bit 0, the keypad.  The keypad is here on
; purpose.  With the link alone, a flat IRQN would be ambiguous between "the
; controller never interrupts" -- the result we want -- and "the interrupt
; setup is broken", which is not a result at all.  The keypad is a genuine
; interrupt source, so pressing keys proves the path works end to end.  ISRC
; records the source bits from IRQ_STATUS directly; KEY is too far from the
; interrupt in time to attribute one safely.
;
; Not a guess: the firmware writes exactly FAh to 04h when it sleeps
; (ROM00:1779), and all three of its sleep masks enable bit 0, because the
; keypad is what wakes the machine.  Note KEY itself does NOT come from the
; interrupt -- kbd_scan polls the matrix directly through ROM00:1A44 -- which
; is precisely why KEY alone could never have proved the interrupt path live.
IRQ_ENABLE      equ 0xFA
RST38_VECTOR    equ 0xF5F3          ; the ROM's 0038 jumps through this RAM
NMI_VECTOR      equ 0xF5F6          ; cell, and 0066 through this one
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
                cpl                         ; pending bits are active low
                ld hl,V_ISRC
                or (hl)
                ld (hl),a
                pop hl
                pop af
                ei
                ret
isr_end:

                org NMI_ORG

; Both initial-open failure and a later bounded ready timeout end here.
dead:           jp failure

; NMI at ROM00:0066 jumps through F5F6, which is uninitialised here.  Plant a
; RETN there so a stray NMI returns safely and restores IFF1 from IFF2.
nmi_safe:       ld hl,0x45ED                ; ED 45 = RETN
                ld (NMI_VECTOR),hl
                ret
nmi_end:

                org VEC_ORG

; --- Scan the 6x6 keypad the way Kbd_ScanMain does at ROM00:190D: drive one
; column at a time through the firmware's own strobe helper, which writes
; port 02h, settles with two PUSH/POP pairs, and returns port 00h masked to
; the six sense bits.  Stock ROM00:1921-1933 calculates the table index as
; 6*sense-bit-index + drive-bit-index; preserve that ordering exactly here.
; Returns that index, or FFh for none.
;
; This is the input channel the exerciser was missing.  It needs no wiring,
; unlike port 2Dh, and it is reported in every record, so pressing keys and
; watching the KEY field maps the keypad without knowing the keymap first.
;
; KbdStrobe preserves BC, DE and HL (it saves HL with PUSH/POP), so the scan
; needs no spills.
kbd_scan:       ld b,0x06                   ; six columns
                ld d,0x01                   ; column drive bit
ks_col:         ld a,d
                call KbdStrobe
                or a
                jr nz,ks_hit
                sla d
                djnz ks_col
                ld a,0xFF                   ; nothing pressed
                ret
ks_hit:         call KbdBitIndex            ; A = sense-bit index; preserves B
                sla a
                ld d,a                      ; 2*sense index
                sla a                       ; 4*sense index
                add a,d                     ; 6*sense index
                add a,0x06
                sub b                       ; plus drive index = 6-B
                ret

; Lee Davison's independent monitor writes LCD_CONTRAST before issuing any
; HD61830 commands.  Do the same, then allow an intentionally generous four
; pm_delay intervals (~462 ms at 3.6864 MHz) before the complete stock LcdInit.
; Stock LcdInit waits a further ~109 ms before its first LCD command and writes
; the shadow to LCD_CONTRAST again before returning.
lcd_preinit:    out (LCD_CONTRAST),a         ; A = CONTRAST from power_lcd_init
                ld b,0x04
lcd_settle:     call pm_delay
                djnz lcd_settle
                jp LcdInit

; Display C, contrast byte, decoded key, heartbeat, then six sense bytes.
; The sense bytes are a SECOND scan, in drive-mask order 01,02,04,08,10,20.
; Static text alone did not prove the failed 27E8 unit kept polling.
; V_COUNT is reused as a heartbeat before link mode initializes it; its
; initial battery-RAM value is immaterial, but each screen increments it.
; Stock adjusters keep LCD_CONTRAST_SHADOW and LCD_CONTRAST synchronized.
contrast_setup: call lcd_home
                ld a,'C'
                call lcd_putc
cs_value:       ld a,(LCD_CONTRAST_SHADOW)
                call lcd_hex
                call kbd_scan
                ld (V_KEY),a
                push af
                call lcd_hex
                ld hl,V_COUNT
                inc (hl)
                ld a,(hl)
                call lcd_hex
                ld b,0x06
                ld d,0x01
                call kbd_raw_display
                pop af
                cp KEY_ENTER
                ret z
                call contrast_keys
                call pm_delay
                jr contrast_setup

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

; Bound every LINK_STATUS bit-7 wait to WD_SAMPLES samples. A timeout ends
; the experiment with an LCD error, rather than restarting forever before
; the first record is visible. No missing-ready data byte is transmitted.
waitready:      ld a,WD_SAMPLES
                ld (V_WD),a
wr_loop:        call sample
                bit 7,a
                ret nz
                ld hl,V_WD
                dec (hl)
                jr nz,wr_loop
                jp dead

; The error reporter retains the stage and counts completed data writes.

; A = byte to put on the wire.
putbyte:        ld c,a
                call waitready
                ld a,c
                out (LINK_TXD),a
                ld hl,V_TX_COUNT
                inc (hl)
                ret

; An HDLC flag: same command as LinkPresent, with a bounded ready wait.
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
; carries the byte.  power_lcd_init below calls the complete stock LcdInit,
; including its own settling delay, register sequence, 160-cell VRAM clear,
; contrast write and cursor disable.  Keeping that known-good routine is safer
; than maintaining a second initialization sequence here.
;
; This is now the primary liveness indicator, and a better one than the
; side-port beacon it replaces: text on the glass cannot be mistaken for
; anything else.
;
; Port map confirmed from ROM accesses and corroborated by the MAME driver
; (micronic.cpp): 00h keypad read, 02h keypad drive, 03h/23h HD61830
; data/control, 08h/28h RTC, 2Bh BEEPER, 46h contrast, 47h bank select and
; 48h/49h status flag.  MAME additionally models port-2Ch bit 4 as the LIKELY
; backlight.  It does not model 4Ah-4Fh at all, which is why this exerciser
; exists.
; ---------------------------------------------------------------------------

; Set the VRAM cursor to cell zero.  HD61830 cursor-address low register R10
; must always be followed by cursor-address high register R11: changing R10
; from bit 7 set to clear can carry into R11.  The stock lcd_sync_status at
; ROM00:1F91-1F9E uses this same low-then-high sequence.
lcd_home:       ld a,0x0A
                out (LCD_REG),a
                xor a
                out (LCD_DAT),a
                ld a,0x0B
                out (LCD_REG),a
                ld a,0x00                  ; match ROM00:1F9C timing exactly
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

pm_delay:       ld hl,0x4000                ; ~116 ms at owner-stated 3.6864 MHz
pm_wait:        dec hl
                ld a,h
                or l
                jr nz,pm_wait
                ret
; Reproduce the sleep configuration paired with IRQ mask FAh at ROM00:1766:
; KBD_DRIVE bit 6 selects IRQ-wake mode and KBD_DRIVE bit 3 selects column 3.
kbd_irq_arm:    jp KbdStrobe                ; shadow + port + settling delay

; Poll a key and tail-call the contrast dispatcher.  Used where the main
; record loop is unavailable; exactly fills the remaining low-region bytes.
dead_adjust:    call kbd_scan
                ld (V_KEY),a
                call contrast_keys
                jp pm_delay                 ; human-scale adjustment rate
lo_end:

                org MID_ORG

; Reproduce the normal cold-start hardware state immediately before LcdInit.
; Reset at ROM00:0152 writes CTL_LATCH_2A=20h and waits 0FA0h iterations.
; The normal path then acknowledges STATUS_IN, masks every interrupt with
; IRQ_MASK=FFh and silences the beeper with SOUND=00h at ROM00:01B1-01B9.
; The delay loop below is the reset loop byte-for-byte.  lcd_preinit writes
; contrast first, adds ~462 ms of settling time, then calls LcdInit, whose own
; delay adds ~109 ms before its first controller command (3.6864 MHz).
power_lcd_init: ld a,0x20
                ld (PORT2A_SHADOW),a
                out (PORT_2A),a
                ld bc,0x0FA0
pwr_delay:      nop
                dec bc
                ld a,b
                or c
                jr nz,pwr_delay
                in a,(IRQ_STATUS)
                ld a,0xFF
                out (IRQ_MASK),a
                ld a,0x00
                out (SOUND),a
                ld a,CONTRAST
                ld (LCD_CONTRAST_SHADOW),a
                jp lcd_preinit

; Dispatch the last polled matrix index to the stock saturating contrast
; routines.  Used continuously on the setup screen and once per 64-record
; frame later.  KEY_NO and KEY_YES are matrix indices, not the translated
; keycodes 01h and 06h.
contrast_keys:  ld a,(V_KEY)
                cp KEY_NO
                jp z,ContrastDecrement
                cp KEY_YES
                jp z,ContrastIncrement
                ret
mid_end:

                org HI_ORG

start:          di
                ld sp,STACK
                call nmi_safe               ; protect the whole LCD init too
                call power_lcd_init
                call contrast_setup         ; ENTER begins the link test

                ; The ROM's RST 38h at 0038 jumps through F5F3 and NMI at 0066
                ; through F5F6, both uninitialised here.  Point the first at
                ; our handler -- the firmware installs its own the same way at
                ; ROM00:2893.  nmi_safe already protected the NMI path above.
                ld a,0xC3
                ld (RST38_VECTOR),a
                ld hl,isr
                ld (RST38_VECTOR+1),hl
                im 1

                ; The firmware's link routines are read-modify-write against
                ; these shadows.  Seed them rather than inheriting whatever
                ; battery RAM happens to hold, so the sequence is repeatable.
                xor a
                ld (CTRL_SHADOW),a
                ld (PORT2C_SHADOW),a
                ld hl,V_SWEEP              ; clear sweep, WD count and the
                ld b,0x0D                  ; through stage and TX count
init_clear:     ld (hl),a
                inc hl
                djnz init_clear
                ld a,LINK_ID
                ld (V_ID),a

                ; --- the cold-boot controller reset.  BEFORE the port
                ; select, not after: LinkProbe ends with XOR A / OUT (2Ch)
                ; at ROM00:34B1, which zeroes the port latch and would undo
                ; the selection.  It also calls 34D2, clearing LINK_CTRL bits
                ; 6 and 7 -- the state LinkBlockTx transmits in.
                ld a,0x01
                call progress
                call LinkProbe
                ld (V_PSTAT),a              ; it returns LINK_STATUS (34BA);
                                            ; the controller's state straight
                                            ; out of reset, worth having as a
                                            ; reference for every later sample

                ; --- select the port exactly as LinkBlockTx does at 3277
                ld a,0x02
                call progress
                xor a                       ; Z set selects top V24; A alone does not
                call LinkPortSelect

                ; --- LinkBlockTx opening: LINK_CTRL bit 0 low, then high;
                ;     LINK_CTRL bit 4 low
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
                ; concluding anything. Later reporting waits also fail visibly.
                ld a,0x03
                call progress
                ld b,0x10
open_try:       call LinkPresent            ; preserves BC
                jr nz,opened
                djnz open_try
                jp dead
opened:         call accreset
                ld a,0x04
                call progress

                ; --- preamble.  Identifies the image and its wire format, and
                ; gives the receiver five known bytes to confirm alignment on
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

                ld a,0x05
                call progress
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
                ld a,0x48                   ; ROM sleep's source-0 arm state
                call kbd_irq_arm            ; column 3: N/ENTER/YES are known

                ld a,(V_OR)                 ; snapshot the window just ended --
                ld b,a                      ; taken after the gap, so windows
                ld a,(V_AND)                ; are contiguous and the gap is not
                ld e,a                      ; a blind spot.  B and E, not C:
                                            ; putbyte uses C.
                call accreset

                call lcd_home               ; record also goes to the glass,
                                            ; top row, 20 hex digits

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
                call emit                   ; [8] interrupt entries so far
                ld a,(V_ISTAT)              ; [9] status at interrupt time,
                call emit                   ;     sticky across the whole run
                ld a,(V_ISRC)
                call putbyte                ; [10] source mask; wire-only so
                                            ; the first ten still fit the LCD

                ld hl,V_COUNT
                inc (hl)
                jr stream

; ---------------------------------------------------------------------------
; Frame boundary: idle, flag, then put the controller into this phase's state.
; ---------------------------------------------------------------------------
newframe:       call contrast_keys          ; YES increments; NO decrements
                call gap
                jp putflag                  ; startup diagnostic: baseline only

; A = stage number. Preserve BC so call sites can retain loop counters.
; Clear the row after the marker, removing the previous setup/error text.
progress:       ld (V_STAGE),a
                push bc
                push af
                call lcd_home
                pop af
                call lcd_hex
                ld b,0x12
                call blank_tail
                pop bc
                ret

blank_tail:     ld a,' '
bt_loop:        call lcd_putc
                djnz bt_loop
                ret

; Terminal timeout: EE, stage, fresh LINK_STATUS, CTRL shadow, TX count.
; Do not send another link command or data byte. Keep NO/YES polling live.
; The status is sampled on entry, not claimed to be the last polling sample.
failure:        di
                in a,(LINK_STAT)
                ld (V_FAIL),a
                ld sp,STACK                 ; abandon nested transmit calls
                call lcd_home
                ld a,0xEE
                call lcd_hex
                ld a,(V_STAGE)
                call lcd_hex
                ld a,(V_FAIL)
                call lcd_hex
                ld a,(CTRL_SHADOW)
                call lcd_hex
                ld a,(V_TX_COUNT)
                call lcd_hex
                ld b,0x0A
                call blank_tail
failure_loop:   call dead_adjust
                jr failure_loop

; No decoding or early exit: show all six masked KBD_SENSE readings.
; In: B=6, D=01h. Out: six hex bytes; clobbers AF, B, D.
kbd_raw_display: ld a,d
                call KbdStrobe
                call lcd_hex
                sla d
                djnz kbd_raw_display
                ret
hi_end:
