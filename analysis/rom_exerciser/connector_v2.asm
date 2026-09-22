; Dedicated connector experiment. The ROM00 cold-boot entry jumps here before
; the stock session path, so this image deliberately never runs OS, barcode,
; or link code. It uses the established standalone power/LCD sequence only.
;
; Candidate masks are experiment choices, not physical connector assignments.
; F selects PORT2C bit 5.  The stock path at ROM00:1231 clears that bit; v1
; kept it high in the 20h baseline, which made that observed state unavailable.
; A waveform touches one selected mask without changing saved baselines;
; the matching shadow tracks each output. Keyboard scan uses the verified base
; keymap. Sampling happens only in sample_wait: startup delays, LCD writes,
; and keyboard scans are unsampled and make P/T timing non-uniform.

                org 0x6000
PORT2A          equ 0x2A
PORT2C          equ 0x2C
EDGE            equ 0x2D
SHADOW2A        equ 0xF78B
SHADOW2C        equ 0xF78D
CONTRAST        equ 0xFC05
NMI_VECTOR      equ 0xF5F6
LcdInit         equ 0x1EEC
KbdStrobe       equ 0x1A44
KbdBitIndex     equ 0x1A52
ContrastDown    equ 0x1D4A
ContrastUp      equ 0x1D60
KEYMAP          equ 0x1B58
; Private state is upper-TPA scratch for this boot-replacing image.
; BASE2A/BASE2C are the operator's resting latch bytes. SELECT/MASK choose
; exactly one experimental bit. LEVEL is the temporary driven state for
; L/H/P/T; it never changes the saved baseline. INPUT is the latest raw 2Dh
; byte, while INPUT_OR/INPUT_AND describe one display interval.
STATE           equ 0xC700
BASE2A          equ STATE
BASE2C          equ STATE+1
SELECT          equ STATE+2
MASK            equ STATE+3
MODE            equ STATE+4
LEVEL           equ STATE+5
TICKS           equ STATE+6
REFRESH         equ STATE+7          ; every 16 sampled dwells -> UI pass
LASTKEY         equ STATE+8          ; last sampled code, FFh = no key
INPUT           equ STATE+9
INPUT_OR        equ STATE+10
INPUT_AND       equ STATE+11
HEART           equ STATE+12

; Entered by the patched cold-boot JP, not by a callable API. DI remains in
; force so no maskable handler can alter outputs while a pattern is active.
; The RAM NMI vector is replaced before stock LCD code is called, because the
; normal boot has not installed its vector table in this image.
start:          di
                ld sp,0xC900
                ld hl,0x45ED                 ; standalone NMI returns, no OS
                ld (NMI_VECTOR),hl
                ld a,0x20
                ld (SHADOW2A),a
                out (PORT2A),a
                ld bc,0x0FA0                 ; stock reset settling loop
power_wait:     nop
                dec bc
                ld a,b
                or c
                jr nz,power_wait
                in a,(0x05)
                ld a,0xFF
                out (0x04),a                 ; known-working LCD power state
                xor a
                out (0x2B),a                 ; sound off
                ld a,0xA4
                ld (CONTRAST),a
                out (0x46),a
                ld b,4
lcd_wait:       call long_delay
                djnz lcd_wait
                call LcdInit                  ; established complete LCD init
                di
                ld hl,STATE
                ld b,13
                xor a
clear_state:    ld (hl),a
                inc hl
                djnz clear_state
                ld a,0xFF
                ld (LASTKEY),a                ; no prior key at first UI pass
                call reset_baseline
                ld a,0x2C
                ld (SELECT),a
                ld a,1
                ld (MASK),a
                call stop
                call reset_samples
                call lcd_home
                ld hl,banner
                call lcd_text
                ld a,80
                call lcd_at
                ld hl,help
                call lcd_text
                call sample_wait
                call display
                call reset_samples
; The UI runs after 16 dwells. LASTKEY is a held-key suppression latch, not a
; timed debounce filter: an unchanged decoded key is ignored. Release (FFh)
; or a different sampled key code allows a new command.
main_loop:      call sample_wait
                call wave_tick
                ld hl,REFRESH
                inc (hl)
                ld a,(hl)
                and 0x0F
                jr nz,main_loop
                call key_scan
                ld hl,LASTKEY
                cp (hl)
                jr z,key_done
                ld (hl),a
                cp 0xFF
                call nz,handle_key
key_done:       call display
                call reset_samples
                jr main_loop

; ~5 ms sampled dwell at 3.6864 MHz: 184 port-2Dh reads, with a 99-T-state
; repeated path. INPUT is the final read, not a latched hardware register.
; OR sets each input bit seen high; AND clears each input bit seen low since
; reset_samples. LCD/key/startup gaps contribute no samples. IFF1 stays clear;
; the installed NMI target returns without changing the pattern.
; In: accumulated INPUT_OR/INPUT_AND. Out: updated samples, no flag result.
; Clobbers: AF, BC, HL. Preserves: DE.
sample_wait:    ld b,184
sample_loop:    in a,(EDGE)
                ld c,a
                ld (INPUT),a
                ld hl,INPUT_OR
                or (hl)
                ld (hl),a
                inc hl
                ld a,c
                and (hl)
                ld (hl),a
                djnz sample_loop
                ret
; Start a fresh display interval: OR identity is 00h and AND identity is FFh.
; Leaves the latest INPUT byte intact. Clobbers: AF only.
reset_samples:  xor a
                ld (INPUT_OR),a
                dec a
                ld (INPUT_AND),a
                ret

; P uses 50 sampled dwells per half-cycle and T uses four. The count is in
; sampled dwells, not a precision clock: each sixteenth dwell includes UI
; work. L/H leave LEVEL fixed; S discards LEVEL's effect by restoring baseline.
; In: MODE/TICKS/LEVEL. Out: a toggle only when a P/T half-cycle expires.
; May clobber AF, BC, DE, HL; flags are not a result.
wave_tick:      ld a,(MODE)
                cp 'P'
                jr z,wave_active
                cp 'T'
                ret nz
wave_active:    ld hl,TICKS
                dec (hl)
                ret nz
                ld a,(LEVEL)
                xor 1
                ld (LEVEL),a
                call apply_output
; In: MODE=P or T. Out: TICKS reloaded for that mode. Clobbers: AF only.
reload_ticks:   ld a,(MODE)
                cp 'P'
                ld a,50
                jr z,set_ticks
                ld a,4
set_ticks:      ld (TICKS),a
                ret

; Build the one experimental output byte from the selected baseline. S writes
; baseline unchanged. Every other mode clears MASK from that baseline, then
; inserts LEVEL; therefore a high baseline bit remains high in H and S, while
; L/P temporarily select the requested state until S restores baseline. The
; unselected latch is neither recomputed nor written.
; The matching stock shadow is updated immediately before OUT so the display
; reports the byte actually driven.
; In: SELECT/MASK, MODE, LEVEL and saved baselines. Out: one shadow/OUT pair.
; Clobbers: AF, BC, DE, HL; flags are not a result.
apply_output:  ld a,(SELECT)
                cp PORT2A
                ld hl,BASE2A
                ld de,SHADOW2A
                jr z,apply_chosen
                ld hl,BASE2C
                ld de,SHADOW2C
apply_chosen:   ld a,(MODE)
                cp 'S'
                ld a,(hl)
                jr z,apply_write
                ld a,(MASK)
                cpl
                and (hl)
                ld c,a
                ld a,(LEVEL)
                or a
                ld a,c
                jr z,apply_write
                ld a,(MASK)
                or c
apply_write:    ld (de),a
                ld b,a
                ld a,(SELECT)
                ld c,a
                ld a,b
                out (c),a
                ret

; Stop is also the safe selection transition: it restores the old selected
; latch before handle_key changes SELECT/MASK to a different candidate.
stop:          ld a,'S'
                ld (MODE),a
                jp apply_output
; Restore both known startup baselines and their shadows. This is the only
; command that writes both experimental latches in one operation.
; Does not change MODE/SELECT/MASK; the R-key caller stops afterwards.
; Clobbers: A only; flags and BC/DE/HL are preserved.
reset_baseline:ld a,0x20
                ld (BASE2A),a
                ld (SHADOW2A),a
                out (PORT2A),a
                ld (BASE2C),a
                ld (SHADOW2C),a
                out (PORT2C),a
                ret

; Base keyboard characters: A-F choose candidates, P/T pulse, L/H hold,
; S stop, SPACE changes selected baseline bit, R restores both baselines.
; The contrast tail calls use stock routines: they own CONTRAST and drive the
; contrast latch, then RET directly to this routine's caller.
; In: A=base key code (01h=NO, 06h=YES), not a matrix index.
; Out: selected command applied, or no change for an unrecognised code.
; Caller treats AF, BC, DE, HL as scratch; flags are not a result.
handle_key:     cp 0x01
                jp z,ContrastDown
                cp 0x06
                jp z,ContrastUp
                cp 'A'
                jr c,key_mode
key_candidate_limit:
                cp 'G'
                jr nc,key_mode
                sub 'A'
                push af
                call stop                    ; restore old selection first
                pop af
                add a,a
                ld e,a
                ld d,0
                ld hl,candidates
                add hl,de
                ld a,(hl)
                ld (SELECT),a
                inc hl
                ld a,(hl)
                ld (MASK),a
                jp stop
key_mode:      cp 'R'
                jr nz,key_space
                call reset_baseline
                jp stop
key_space:     cp ' '
                jr nz,key_stop
                call stop
                ld a,(SELECT)
                cp PORT2A
                ld hl,BASE2A
                jr z,key_base
                ld hl,BASE2C
key_base:      ld a,(MASK)
                xor (hl)
                ld (hl),a
                jp apply_output
key_stop:      cp 'S'
                jp z,stop
                cp 'P'
                jr z,key_pulse
                cp 'T'
                jr z,key_pulse
                cp 'L'
                jr z,key_low
                cp 'H'
                ret nz
                ld (MODE),a
                ld a,1
                jr key_level
key_low:       ld (MODE),a
                xor a
key_level:     ld (LEVEL),a
                jp apply_output
key_pulse:     ld (MODE),a
                xor a
                ld (LEVEL),a
                call apply_output
                jp reload_ticks

; KbdStrobe takes A=one-hot drive and returns A=masked sense bits; its ROM
; body preserves BC, DE and HL. KbdBitIndex converts the nonzero one-hot sense
; value to its row index and preserves BC/DE. This derives
; 6*sense-row + drive-column, the same index used by the stock KEYMAP table.
; Multiple simultaneous keys depend on the ROM helper's one-bit selection;
; this diagnostic intentionally has no chord policy.
; Out: A=base key code, FFh if idle. Clobbers: F, BC, DE, HL.
; The main loop, not this scanner, suppresses repeated held-key commands.
key_scan:      ld b,6
                ld d,1
key_col:       ld a,d
                call KbdStrobe
                or a
                jr nz,key_hit
                sla d
                djnz key_col
                ld a,0xFF
                ret
key_hit:       call KbdBitIndex
                sla a
                ld d,a
                sla a
                add a,d
                add a,6
                sub b
                ld e,a
                ld d,0
                ld hl,KEYMAP
                add hl,de
                ld a,(hl)
                ret

; Update three 20-column rows. The input byte is the final pre-LCD sample;
; OR/AND cover the preceding sampled window, not LCD/key/startup work.
; The display stream starts at cell 20 and advances continuously. row3 begins
; with four spaces because row2 has 16 meaningful characters; those spaces
; complete row2 before the IN OR text begins on row3.
; In: state/shadows. Out: LCD rows and incremented HEART, no flag result.
; Clobbers: AF, HL. Preserves: BC, DE.
display:       ld a,20
                call lcd_at
                ld hl,row1a
                call lcd_text
                ld a,(SHADOW2A)
                call lcd_hex
                ld hl,row1c
                call lcd_text
                ld a,(SHADOW2C)
                call lcd_hex
                ld hl,row1d
                call lcd_text
                ld a,(INPUT)
                call lcd_hex
                ld a,' '
                call lcd_putc
                ld a,(HEART)
                inc a
                ld (HEART),a
                call lcd_hex
                ld hl,row2
                call lcd_text
                ld a,(SELECT)
                call lcd_hex
                ld a,'/'
                call lcd_putc
                ld a,(MASK)
                call lcd_hex
                ld hl,mode_text
                call lcd_text
                ld a,(MODE)
                call lcd_putc
                ld hl,row3
                call lcd_text
                ld a,(INPUT_OR)
                call lcd_hex
                ld hl,and_text
                call lcd_text
                ld a,(INPUT_AND)
                call lcd_hex
                ld hl,spaces
                jp lcd_text

; Position within the first 256 LCD cells; high address byte is always zero.
; lcd_home enters with address zero; lcd_at takes A=linear cell address.
; Clobbers: AF. Preserves: BC, DE, HL.
lcd_home:      xor a
lcd_at:        push af
                ld a,0x0A
                out (0x23),a
                pop af
                out (0x03),a
                ld a,0x0B
                out (0x23),a
                xor a
                out (0x03),a
                ret
; Write a NUL-terminated string; terminator is not sent to the LCD.
; In: HL=string. Out: HL=terminator, A=0, Z set. Clobbers: AF, HL.
lcd_text:      ld a,(hl)
                or a
                ret z
                call lcd_putc
                inc hl
                jr lcd_text
; In: A=character. LCD cursor advances. Preserves all registers and flags.
lcd_putc:      push af
                ld a,0x0C
                out (0x23),a
                pop af
                out (0x03),a
                ret
; In: A=byte. Emit high then low hex digit; clobber AF only.
lcd_hex:       push af
                rrca
                rrca
                rrca
                rrca
                call lcd_nibble
                pop af
; In: low nibble of A. Emit one uppercase hex digit; clobber AF only.
lcd_nibble:    and 0x0F
                add a,0x30
                cp 0x3A
                jr c,lcd_char
                add a,7
lcd_char:      jp lcd_putc
; Startup-only delay. It does not sample 2Dh or service the UI.
; Clobbers: AF, HL. Preserves: BC (outer delay count), DE.
long_delay:    ld hl,0x4000
long_wait:     dec hl
                ld a,h
                or l
                jr nz,long_wait
                ret

; Key A..F indexes this two-byte table. The table records latch/mask mechanics
; only; it deliberately does not name a physical scanner-port contact.
candidates:    db 0x2C,0x01, 0x2C,0x02, 0x2A,0x02, 0x2A,0x01, 0x2A,0x10
                db 0x2C,0x20
banner:        db 'CONNECTOR PROBE 2   ',0
row1a:         db '2A=',0
row1c:         db ' 2C=',0
row1d:         db ' 2D=',0
row2:          db 'SEL=',0
mode_text:     db ' MODE=',0
; row2 has 16 characters before these four spaces finish the row.
row3:          db '    IN OR=',0
and_text:      db ' AND=',0
spaces:        db '     ',0
help:          db 'A-F:PIN P/T:PULSE   '
                db 'L/H:HOLD S:STOP     '
                db 'SPACE:BASE R:RESET  '
                db 'NO/YES:CONTRAST     ',0
end:
