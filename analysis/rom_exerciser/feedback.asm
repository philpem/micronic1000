; Combined feedback ROM.  This is test firmware, not a reconstruction of a
; Micronic protocol.  It starts through the cold-boot patch before the OS,
; restores the measured black-input gate only while idle, and reports raw
; Link_BlockRx facts without equating any status bit to frame acceptance.

                org 0x6000
PORT2A          equ 0x2A
PORT2C          equ 0x2C
EDGE             equ 0x2D
LINK_CTRL        equ 0x4A
LINK_STAT        equ 0x4B
LINK_CMD         equ 0x4C
LINK_TXD         equ 0x4D
LINK_RXD         equ 0x4E
SHADOW2A         equ 0xF78B
SHADOW2C         equ 0xF78D
CTRL_SHADOW      equ 0xF794
DESC_PTR         equ 0xFDDC
CONTRAST         equ 0xFC05
NMI_VECTOR       equ 0xF5F6
LcdInit          equ 0x1EEC
KbdStrobe        equ 0x1A44
KbdBitIndex      equ 0x1A52
ContrastDown     equ 0x1D4A
ContrastUp       equ 0x1D60
KEYMAP           equ 0x1B58
LinkPortSelect   equ 0x3454
LinkProbe        equ 0x348A
LinkPresent      equ 0x34EC
LinkWaitReady    equ 0x34F8
LinkBlockRx      equ 0x3378
LinkFinish       equ 0x34BD

; Private upper-TPA state.  It is initialised, so poisoned battery RAM cannot
; select an old mode, leak an old RX preview, or leave yellow asserted.
STATE            equ 0xC700
S_MODE           equ STATE            ; 0 invalid, 1 W, 2 R, 3 P, 4 G
S_ERR            equ STATE+1
S_SEQLO          equ STATE+2
S_SEQHI          equ STATE+3
S_PROBE          equ STATE+4
S_BEFORE         equ STATE+5
S_AFTER          equ STATE+6
S_P4             equ STATE+7
S_P6             equ STATE+8
S_ARM            equ STATE+9
S_RXA            equ STATE+10
S_RXF            equ STATE+11
S_RXL            equ STATE+12
S_RXH            equ STATE+13
S_PREVLEN        equ STATE+14
S_PREVIEW        equ STATE+15          ; eight bytes
S_RAW2D          equ STATE+23
S_TICKS          equ STATE+24
S_RELEASE        equ STATE+25
S_LASTKEY        equ STATE+26
RESULT           equ 0xC740            ; exact 30-byte UART record
RXDESC           equ 0xC770            ; {len=134,dest=RXBUF, terminator}
RXBUF            equ 0xC780            ; private descriptor payload C780-C805
STACK            equ 0xC900

; Result error values from ir-feedback-protocol.md.
E_OK             equ 0
E_WIDTH          equ 1
E_STUCK          equ 2
E_RELEASE        equ 3
E_READY          equ 4
E_P4             equ 5
E_P6             equ 6
E_RX             equ 7
E_PENDING        equ 8

; Entry from patched cold boot.  The NMI return is installed before calling
; stock LCD code, as the normal firmware boot has not created RAM vectors.
start:           di
                ld sp,STACK
                ld hl,0x45ED
                ld (NMI_VECTOR),hl
                ld a,0x20
                ld (SHADOW2A),a
                out (PORT2A),a
                ld bc,0x0FA0
boot_wait:      nop
                dec bc
                ld a,b
                or c
                jr nz,boot_wait
                in a,(0x05)
                ld a,0xFF
                out (0x04),a
                xor a
                out (0x2B),a
                ld a,0xA4
                ld (CONTRAST),a
                out (0x46),a
                ld b,4
boot_lcd_wait:  call long_delay
                djnz boot_lcd_wait
                call LcdInit
                di
                ld hl,STATE
                ld bc,0x0080
clear_private:  ld (hl),0
                inc hl
                dec bc
                ld a,b
                or c
                jr nz,clear_private
                ld a,0xFF
                ld (S_LASTKEY),a
                xor a
                ld (SHADOW2C),a
                ld (CTRL_SHADOW),a
                out (0x07),a
                ld a,3
                out (0x48),a
                call restore_gate
                call reset_trial
                call show_idle

; Idle permits black commands only with 2A.bit1 high and 2C.bit5 low.
; LCD/key work returns here, so an asserted black line remains pending.
idle:            call key_scan
                ld hl,S_LASTKEY
                cp (hl)
                jr z,idle_poll
                ld (hl),a
                cp 0xFF
                call nz,handle_key
idle_poll:       in a,(EDGE)
                ld (S_RAW2D),a
                bit 0,a
                jr z,command_begin
                jr idle

; ACK then measure black-low width in approximately 5 ms polling ticks.  No
; LCD, keyboard, marker, or stock-link work occurs until black has released.
command_begin:   call reset_trial
                call yellow_sink
                xor a
                ld (S_TICKS),a
cmd_low:         call tick5
                in a,(EDGE)
                ld (S_RAW2D),a
                bit 0,a
                jr nz,cmd_released
                ld hl,S_TICKS
                inc (hl)
                ld a,(hl)
                cp 160
                jr c,cmd_low
                ld a,E_STUCK
                jp command_error
cmd_released:    ld a,6
                ld (S_RELEASE),a
cmd_release:     call tick5
                in a,(EDGE)
                ld (S_RAW2D),a
                bit 0,a
                jr z,release_unstable
                ld hl,S_RELEASE
                dec (hl)
                jr nz,cmd_release
                call classify_command
                ld a,(S_MODE)
                or a
                jr z,width_error
                jp accepted_trial
width_error:     ld a,E_WIDTH
                jp command_error
release_unstable: ld a,E_RELEASE
command_error:   ld (S_ERR),a
                xor a
                ld (S_MODE),a
                call restore_gate
                call result_leadin
                call send_result
                call show_result
wait_physical_release:
                in a,(EDGE)
                bit 0,a
                jr z,wait_physical_release
                jp idle

; Inclusive command-width windows: W=15..30, R=50..70, P=90..110.
classify_command:
                xor a
                ld (S_MODE),a
                ld a,(S_TICKS)
                cp 15
                ret c
                cp 31
                jr nc,try_rx
                ld a,1
                ld (S_MODE),a
                ret
try_rx:          ld a,(S_TICKS)
                cp 50
                ret c
                cp 71
                jr nc,try_probe
                ld a,2
                ld (S_MODE),a
                ret
try_probe:       ld a,(S_TICKS)
                cp 90
                ret c
                cp 111
                jr nc,try_pending
                ld a,3
                ld (S_MODE),a
                ret
try_pending:     ld a,(S_TICKS)
                cp 130
                ret c
                cp 151
                ret nc
                ld a,4
                ld (S_MODE),a
                ret

; Accepted commands and keypad W/R/P share the same guard, START marker,
; stock teardown, result and idle restoration path.  The 50 ms high guard is
; intentionally longer than the UART result lead-in (20 ms).
accepted_trial:  ld hl,S_SEQLO
                inc (hl)
                jr nz,seq_done
                inc hl
                inc (hl)
seq_done:        call yellow_release
                ld b,10
guard50:         call tick5
                djnz guard50
                call yellow_sink
                call tick2
                ld a,(S_MODE)
                cp 1
                jr nz,trial_rx
                call run_witness
                jr trial_done
trial_rx:       ld a,(S_MODE)
                cp 2
                jr nz,trial_probe
                call run_rx
                jr trial_done
trial_probe:    ld a,(S_MODE)
                cp 3
                jr nz,trial_pending
                call run_probe
                jr trial_done
trial_pending:  ld a,(S_MODE)
                cp 4
                jr nz,trial_done
                call run_pending_rx
trial_done:
                ; START remains low for a fixed 100 ms post-trial cooldown.
                ; This lets the Uno finish its bounded response before the
                ; 20 ms UART lead-in can resemble another marker edge.
                ld b,20
cooldown100:     call tick5
                djnz cooldown100
                call restore_gate
                call result_leadin
                call send_result
                call show_result
                jp idle

; Manual mode invokes the same result path.  It does not impersonate an
; automatic pending request; the host must resynchronise after keypad use.
manual_trial:    push af
                call reset_trial
                pop af
                ld (S_MODE),a
                ld b,6
manual_release:  call tick5
                in a,(EDGE)
                bit 0,a
                jr z,manual_blocked
                djnz manual_release
                jp accepted_trial
manual_blocked:  ld a,E_RELEASE
                ld (S_ERR),a
                xor a
                ld (S_MODE),a
                call restore_gate
                call show_error
                call result_leadin
                call send_result
                call show_result
manual_wait:     in a,(EDGE)
                bit 0,a
                jr z,manual_wait
                jp idle

; The witness follows the stock LinkBlockTx opening order.  Its two status
; polls preserve stock's 0x026c bound and run with no LCD/marker work inside.
run_witness:     ld a,0xE0
                out (0x04),a
                call link_reset_select
                in a,(LINK_STAT)
                ld (S_BEFORE),a
                ld a,0xFE
                call ctrl_and
                ld a,0x01
                call ctrl_or
                ld a,0xEF
                call ctrl_and
                ld b,0x80
w_open_settle:   djnz w_open_settle
                ld b,0x10
w_ready:         call LinkPresent
                jr nz,w_open
                djnz w_ready
                ld a,E_READY
                ld (S_ERR),a
                jp witness_finish
w_open:          call LinkWaitReady
                jr nz,w_prelude
                ld a,E_READY
                ld (S_ERR),a
                jp witness_finish
w_prelude:       ld a,0x03
                out (LINK_TXD),a
                call stock_wait_p4
                ld (S_P4),a
                or a
                jr nz,w_arm
                ld a,E_P4
                ld (S_ERR),a
                jp witness_finish
w_arm:           ld a,0x20
                call ctrl_or
                ld a,0x10
                call ctrl_or
                ld a,1
                ld (S_ARM),a
                push bc
                ld b,0x20
w_arm_settle:    djnz w_arm_settle
                pop bc
                ld a,0xDF
                call ctrl_and
                call stock_wait_p6
                ld (S_P6),a
                or a
                jr nz,witness_finish
                ld a,E_P6
                ld (S_ERR),a
witness_finish:  ld a,0xEF
                call ctrl_and
                ld a,0xFE
                call ctrl_and
                call LinkFinish
                in a,(LINK_STAT)
                ld (S_AFTER),a
                ret

; RX resets/selects the controller before each invocation, then calls the
; unmodified stock Link_BlockRx with one private 134-byte descriptor.  Return
; A/F and only bytes that stock actually placed in that descriptor are sent.
run_rx:          call link_reset_select
                in a,(LINK_STAT)
                ld (S_BEFORE),a
                call rx_collect
                ret

; G mode waits after reset/select for a bit-4-pending condition, bounded to
; 100 ms, then enters the same raw stock reader as R.  Timeout is a condition
; record only, not an inferred received frame.
run_pending_rx:  call link_reset_select
                call LinkFinish
                in a,(LINK_STAT)
                ld (S_BEFORE),a
                ld b,20
pending_wait:    in a,(LINK_STAT)
                bit 4,a
                jr nz,pending_read
                call tick5
                djnz pending_wait
                ld a,E_PENDING
                ld (S_ERR),a
                ld a,0xEF
                call ctrl_and
                ld a,0xFE
                call ctrl_and
                call LinkFinish
                in a,(LINK_STAT)
                ld (S_AFTER),a
                ret
pending_read:    call rx_collect
                ret

; Build the private terminated 134-byte descriptor, then retain stock raw
; return A/F/DE.  No session dispatcher pointer or destination is reused.
rx_collect:
                ld hl,RXDESC
                ld (DESC_PTR),hl
                ld a,0x86
                ld (RXDESC),a
                xor a
                ld (RXDESC+1),a
                ld hl,RXBUF
                ld (RXDESC+2),hl
                ld (RXDESC+4),a
                ld (RXDESC+5),a
                ld hl,RXBUF
                ld b,0x86
rxbuf_clear:     ld (hl),0
                inc hl
                djnz rxbuf_clear
                ld hl,RXDESC
                call LinkBlockRx
                push af
                pop bc
                ld a,b
                ld (S_RXA),a
                ld a,c
                ld (S_RXF),a
                bit 0,c
                jr nz,rx_error
                ld a,e
                ld (S_RXL),a
                ld a,d
                ld (S_RXH),a
                call preview_rx
                jr rx_done
rx_error:        ld a,E_RX
                ld (S_ERR),a
rx_done:         in a,(LINK_STAT)
                ld (S_AFTER),a
                ret

run_probe:       call link_reset_select
                in a,(LINK_STAT)
                ld (S_BEFORE),a
                ld (S_AFTER),a
                ret

; Reset first, then take LinkProbe's raw LINK_STATUS result and use the stock
; Z-flag top-V24 selection.  Link_PortSelect necessarily destroys black gate.
link_reset_select:
                xor a
                ld (CTRL_SHADOW),a
                ld (SHADOW2C),a
                call LinkProbe
                ld (S_PROBE),a
                xor a
                call LinkPortSelect
                ret

; These preserve the stock poll bodies' read/LD B/CPL/AND-immediate sequence
; and 0x026c bound at ROM00:32B8 and ROM00:32F0.  The return value records
; only whether the selected LINK_STATUS bit cleared; it has no wire meaning.
stock_wait_p4:
                ld de,0x026C
poll4:           in a,(LINK_STAT)
                ld b,a
                cpl
                and 0x10
                jr nz,poll4_ok
                dec de
                ld a,d
                or e
                jr nz,poll4
                xor a
                ret
poll4_ok:        ld a,0x10
                or a
                ret
stock_wait_p6:   ld de,0x026C
poll6:           in a,(LINK_STAT)
                ld b,a
                cpl
                and 0x40
                jr nz,poll6_ok
                dec de
                ld a,d
                or e
                jr nz,poll6
                xor a
                ret
poll6_ok:        ld a,0x40
                or a
                ret

ctrl_or:         ld b,a
                ld a,(CTRL_SHADOW)
                or b
                ld (CTRL_SHADOW),a
                out (LINK_CTRL),a
                ret
ctrl_and:        ld b,a
                ld a,(CTRL_SHADOW)
                and b
                ld (CTRL_SHADOW),a
                out (LINK_CTRL),a
                ret

; preview=min(raw stock DE return, 8) while the first descriptor admits
; 134 bytes.  Stock's carry-clear DE is retained verbatim; it is not relabelled
; as a physical byte count.  It runs only
; after carry-clear stock return; stale RXBUF bytes never become a preview.
preview_rx:      xor a
                ld (S_PREVLEN),a
                ld a,(S_RXH)
                or a
                jr nz,preview_eight
                ld a,(S_RXL)
                cp 8
                jr nc,preview_eight
                ld (S_PREVLEN),a
                jr preview_copy
preview_eight:   ld a,8
                ld (S_PREVLEN),a
preview_copy:    ld b,a
                ld hl,RXBUF
                ld de,S_PREVIEW
preview_loop:    ld a,b
                or a
                ret z
                ld a,(hl)
                ld (de),a
                inc hl
                inc de
                djnz preview_loop
                ret

; Restore the confirmed idle black gate while releasing yellow.  This runs
; only after stock link activity has torn down.  The complete final shadows
; are copied into the record after transmission is constructed.
restore_gate:    ld a,(SHADOW2A)
                and 0xFE
                or 0x02
                ld (SHADOW2A),a
                out (PORT2A),a
                ld a,(SHADOW2C)
                and 0xDF
                ld (SHADOW2C),a
                out (PORT2C),a
                ret
yellow_sink:     ld a,(SHADOW2A)
                or 1
                ld (SHADOW2A),a
                out (PORT2A),a
                ret
yellow_release:  ld a,(SHADOW2A)
                and 0xFE
                ld (SHADOW2A),a
                out (PORT2A),a
                ret

; Format the fixed 30-byte result, then transmit it as 1200 baud 8N1 on
; yellow.  Check byte makes unsigned sum(record) modulo 256 equal zero.
result_leadin:   call yellow_release
                ld b,4
lead_wait:       call tick5
                djnz lead_wait
                ret
send_result:     call make_result
                ld hl,RESULT
                ld b,30
record_loop:     ld a,(hl)
                push hl
                push bc
                call uart_byte
                pop bc
                pop hl
                inc hl
                djnz record_loop
                call yellow_release
                ret
; Sample after the restored gate has settled through the result lead-in;
; retaining the command-time sample would hide the current input level.
make_result:     in a,(EDGE)
                ld (S_RAW2D),a
                ld hl,RESULT
                ld (hl),0xA5
                inc hl
                ld (hl),0x5A
                inc hl
                ld (hl),1
                inc hl
                ld a,(S_MODE)
                ld (hl),a
                inc hl
                ld a,(S_SEQLO)
                ld (hl),a
                inc hl
                ld a,(S_SEQHI)
                ld (hl),a
                inc hl
                ld a,(S_ERR)
                ld (hl),a
                inc hl
                ld a,(S_PROBE)
                ld (hl),a
                inc hl
                ld a,(S_BEFORE)
                ld (hl),a
                inc hl
                ld a,(S_AFTER)
                ld (hl),a
                inc hl
                ld a,(S_P4)
                ld (hl),a
                inc hl
                ld a,(S_P6)
                ld (hl),a
                inc hl
                ld a,(S_ARM)
                ld (hl),a
                inc hl
                ld a,(S_RXA)
                ld (hl),a
                inc hl
                ld a,(S_RXF)
                ld (hl),a
                inc hl
                ld a,(S_RXL)
                ld (hl),a
                inc hl
                ld a,(S_RXH)
                ld (hl),a
                inc hl
                ld a,(S_PREVLEN)
                ld (hl),a
                inc hl
                ld de,S_PREVIEW
                ld b,8
result_preview:  ld a,(de)
                ld (hl),a
                inc de
                inc hl
                djnz result_preview
                ld a,(SHADOW2A)
                ld (hl),a
                inc hl
                ld a,(SHADOW2C)
                ld (hl),a
                inc hl
                ld a,(S_RAW2D)
                ld (hl),a
                inc hl
                xor a
                ld (hl),a
                ld hl,RESULT
                ld b,30
                xor a
result_sum:      add a,(hl)
                inc hl
                djnz result_sum
                neg
                ld (RESULT+29),a
                ret

; 1200 baud at 3.6864 MHz: each bit uses a conservative 3072-cycle loop
; envelope.  Low is sink, high is release.  Start + 8 LSB-first + stop.
uart_byte:       push af
                call yellow_sink
                call bit_delay
                pop af
                ld b,8
uart_bits:       rra
                push af
                jr c,uart_high
                call yellow_sink
                jr uart_wait
uart_high:       call yellow_release
uart_wait:       call bit_delay
                pop af
                djnz uart_bits
                call yellow_release
                call bit_delay
                ret
; 111 loop iterations plus the preserved outer BC and line-write path yield
; a measured cell near 3072 T at 3.6864 MHz (1200 baud).
bit_delay:       push bc
                ld bc,0x006F
bit_delay_loop:  dec bc
                ld a,b
                or c
                jr nz,bit_delay_loop
                pop bc
                ret
tick5:           push bc
                ld bc,0x02C0
tick5_loop:      dec bc
                ld a,b
                or c
                jr nz,tick5_loop
                pop bc
                ret
tick2:           push bc
                ld bc,0x011A
tick2_loop:      dec bc
                ld a,b
                or c
                jr nz,tick2_loop
                pop bc
                ret

reset_trial:     ld hl,S_MODE
                ld b,2
                xor a
reset_fields:    ld (hl),a
                inc hl
                djnz reset_fields
                ld hl,S_PROBE
                ld b,20
reset_measurements:
                ld (hl),a
                inc hl
                djnz reset_measurements
                ld a,0xFF
                ld (S_P4),a
                ld (S_P6),a
                ret

; Verified keyboard mapping and stock contrast helpers.  W/R/P select the
; same manual trial path as the black command modes; all other keys are idle.
handle_key:      cp 0x01
                jp z,ContrastDown
                cp 0x06
                jp z,ContrastUp
                cp 'W'
                jr nz,key_r
                ld a,1
                jp manual_trial
key_r:           cp 'R'
                jr nz,key_p
                ld a,2
                jp manual_trial
key_p:           cp 'P'
                jr nz,key_g
                ld a,3
                jp manual_trial
key_g:           cp 'G'
                ret nz
                ld a,4
                jp manual_trial
key_scan:        ld b,6
                ld d,1
key_col:         ld a,d
                call KbdStrobe
                or a
                jr nz,key_hit
                sla d
                djnz key_col
                ld a,0xFF
                ret
key_hit:         call KbdBitIndex
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
show_idle:       call lcd_home
                ld hl,banner
                jp lcd_text
show_error:      call lcd_home
                ld hl,error_text
                jp lcd_text
; Three compact LCD rows mirror the record after UART has completed.  LCD
; writes are deliberately outside all command, marker, stock-poll and UART
; windows.  Row 0: mode/sequence/error/before/after.  Row 1 starts Q= and
; carries PSTAT,P4,P6,RXA,RXF,DElo,DEhi.  Row 2 carries preview length and
; eight preview bytes; row 3 has final idle-gate 2A/2C and raw 2D.
show_result:     call lcd_home
                ld a,'M'
                call lcd_putc
                ld a,(S_MODE)
                add a,0x30
                call lcd_putc
                ld a,' '
                call lcd_putc
                ld a,'S'
                call lcd_putc
                ld a,(S_SEQHI)
                call lcd_hex
                ld a,(S_SEQLO)
                call lcd_hex
                ld a,' '
                call lcd_putc
                ld a,'E'
                call lcd_putc
                ld a,(S_ERR)
                call lcd_hex
                ld a,' '
                call lcd_putc
                ld a,'B'
                call lcd_putc
                ld a,(S_BEFORE)
                call lcd_hex
                ld a,'A'
                call lcd_putc
                ld a,(S_AFTER)
                call lcd_hex
                ld hl,tail1
                call lcd_text
                ld a,20
                call lcd_at
                ld hl,result_row1
                call lcd_text
                ld a,(S_PROBE)
                call lcd_hex
                ld a,(S_P4)
                call lcd_hex
                ld a,(S_P6)
                call lcd_hex
                ld a,(S_RXA)
                call lcd_hex
                ld a,(S_RXF)
                call lcd_hex
                ld a,(S_RXL)
                call lcd_hex
                ld a,(S_RXH)
                call lcd_hex
                ld hl,tail4
                call lcd_text
                ld a,40
                call lcd_at
                ld a,'D'
                call lcd_putc
                ld a,(S_PREVLEN)
                call lcd_hex
                ld a,'='
                call lcd_putc
                ld hl,S_PREVIEW
                ld b,8
show_preview:    ld a,(hl)
                call lcd_hex
                inc hl
                djnz show_preview
                ld a,60
                call lcd_at
                ld hl,result_row3
                call lcd_text
                ld a,(SHADOW2A)
                call lcd_hex
                ld a,'C'
                call lcd_putc
                ld a,(SHADOW2C)
                call lcd_hex
                ld a,'I'
                call lcd_putc
                ld a,(S_RAW2D)
                call lcd_hex
                ld hl,spaces
                call lcd_text
                ret
lcd_home:        xor a
lcd_at:          push af
                ld a,0x0A
                out (0x23),a
                pop af
                out (0x03),a
                ld a,0x0B
                out (0x23),a
                xor a
                out (0x03),a
                ret
lcd_text:        ld a,(hl)
                or a
                ret z
                call lcd_putc
                inc hl
                jr lcd_text
lcd_putc:        push af
                ld a,0x0C
                out (0x23),a
                pop af
                out (0x03),a
                ret
lcd_hex:         push af
                rrca
                rrca
                rrca
                rrca
                call lcd_nibble
                pop af
lcd_nibble:      and 0x0F
                add a,0x30
                cp 0x3A
                jr c,lcd_nibble_out
                add a,7
lcd_nibble_out:  jp lcd_putc
long_delay:      ld hl,0x4000
long_delay_loop: dec hl
                ld a,h
                or l
                jr nz,long_delay_loop
                ret

banner:          db 'IR FEEDBACK W/R/P/G ',0
error_text:      db 'IR CMD ERROR        ',0
result_row1:     db 'Q=',0
result_row3:     db 'A',0
tail4:           db '    ',0
tail1:           db ' ',0
spaces:          db '           ',0
end:
