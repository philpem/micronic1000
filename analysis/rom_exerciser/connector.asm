; Dedicated connector experiment. Cold boot is redirected here; no OS tasks
; or barcode/link APIs execute. Known-working exerciser power/LCD startup.
; Candidate masks are experiment choices, not physical pin assignments.
; Every output change preserves the other baseline bits and updates shadows.
; Direct keyboard scan uses the ROM's byte-verified base keymap.
; Input polling continues in every wait. LCD/key work introduces pulse jitter.

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
STATE           equ 0xC700
BASE2A          equ STATE
BASE2C          equ STATE+1
SELECT          equ STATE+2
MASK            equ STATE+3
MODE            equ STATE+4
LEVEL           equ STATE+5
TICKS           equ STATE+6
REFRESH         equ STATE+7
LASTKEY         equ STATE+8
INPUT           equ STATE+9
INPUT_OR        equ STATE+10
INPUT_AND       equ STATE+11
HEART           equ STATE+12

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
                call LcdInit
                di
                ld hl,STATE
                ld b,13
                xor a
clear_state:    ld (hl),a
                inc hl
                djnz clear_state
                ld a,0xFF
                ld (LASTKEY),a
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

; ~5 ms sampled dwell at 3.6864 MHz; GUI work is outside this dwell.
; 184 reads, 99 T states per repeated path. No interrupt handler can change
; outputs: IFF1 remains clear throughout. Input OR/AND are per display window.
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
reset_samples:  xor a
                ld (INPUT_OR),a
                dec a
                ld (INPUT_AND),a
                ret

; MODE P: 50 dwells/half-cycle; T: 4. L/H hold, S restores baseline.
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
reload_ticks:   ld a,(MODE)
                cp 'P'
                ld a,50
                jr z,set_ticks
                ld a,4
set_ticks:      ld (TICKS),a
                ret

; Apply the chosen mode to one mask only. Both output shadows match OUTs.
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

stop:          ld a,'S'
                ld (MODE),a
                jp apply_output
reset_baseline:ld a,0x20
                ld (BASE2A),a
                ld (SHADOW2A),a
                out (PORT2A),a
                ld (BASE2C),a
                ld (SHADOW2C),a
                out (PORT2C),a
                ret

; Base keyboard characters: A-E choose candidates, P/T pulse, L/H hold,
; S stop, SPACE changes selected baseline bit, R restores both baselines.
handle_key:     cp 0x01
                jp z,ContrastDown
                cp 0x06
                jp z,ContrastUp
                cp 'A'
                jr c,key_mode
                cp 'F'
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

; Same column/sense ordering as the tested exerciser, then base keymap.
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

; Update three 20-column rows. The input byte is the last sample before LCD
; work; OR/AND cover the preceding sampled window, not unsampled LCD work.
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
lcd_text:      ld a,(hl)
                or a
                ret z
                call lcd_putc
                inc hl
                jr lcd_text
lcd_putc:      push af
                ld a,0x0C
                out (0x23),a
                pop af
                out (0x03),a
                ret
lcd_hex:       push af
                rrca
                rrca
                rrca
                rrca
                call lcd_nibble
                pop af
lcd_nibble:    and 0x0F
                add a,0x30
                cp 0x3A
                jr c,lcd_char
                add a,7
lcd_char:      jp lcd_putc
long_delay:    ld hl,0x4000
long_wait:     dec hl
                ld a,h
                or l
                jr nz,long_wait
                ret

candidates:    db 0x2C,0x01, 0x2C,0x02, 0x2A,0x02, 0x2A,0x01, 0x2A,0x10
banner:        db 'CONNECTOR PROBE 1   ',0
row1a:         db '2A=',0
row1c:         db ' 2C=',0
row1d:         db ' 2D=',0
row2:          db 'SEL=',0
mode_text:     db ' MODE=',0
; row2 has 16 characters before these four spaces finish the row.
row3:          db '    IN OR=',0
and_text:      db ' AND=',0
spaces:        db '     ',0
help:          db 'A-E:PIN P/T:PULSE   '
                db 'L/H:HOLD S:STOP     '
                db 'SPACE:BASE R:RESET  '
                db 'NO/YES:CONTRAST     ',0
end:
