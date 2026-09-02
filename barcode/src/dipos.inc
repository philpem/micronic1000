;; ---------------------------------------------------------------------------
;; dipos.inc -- the DIPOS-B decode-hook contract.
;;
;; Every address here was measured against the firmware, not inferred; see
;; doc/re-notes/barcode-capture.md for the evidence behind each one.
;;
;; HOW THE HOOK IS CALLED
;;
;;   The firmware captures a scan as a table of element widths, then calls
;;   whatever address is installed in the socket.  The hook is entered with
;;   ONE argument, on the stack -- nothing useful is in any register:
;;
;;       [SP+0]   return address
;;       [SP+2]   PARAM_BLOCK  (that is, the constant 0FBB9h)
;;
;;   Interrupts are off, the bank named in HOOK_BANK is paged in, and every
;;   register except SP may be clobbered: the caller reloads everything from
;;   memory after the hook returns.
;; ---------------------------------------------------------------------------

;; --- the parameter block ---------------------------------------------------
;; On entry PARAM_WIDTHS points at the captured width table and PARAM_COUNT
;; holds the element count.  To return decoded data, repoint PARAM_WIDTHS at
;; your bytes and set PARAM_COUNT to the byte count.  Setting PARAM_COUNT to
;; zero rejects the scan and re-arms the scanner -- that is all the ROM's own
;; default hook does.
PARAM_BLOCK     equ 0FBB9h
PARAM_WIDTHS    equ 0FBB9h      ; word: pointer to the width table (in: 0F9B5h)
PARAM_COUNT     equ 0FBBBh      ; WORD, not a byte -- 0FBBCh is its high half

;; The firmware reads PARAM_COUNT with `LD BC,(0FBBBh)` and uses it directly as
;; an LDIR length (ROM00:147E).  Writing a status byte into 0FBBCh -- as older
;; documentation suggested -- would copy 256 extra bytes per unit.

;; --- limits that will bite you ---------------------------------------------
;; The capture buffer holds at most 128 elements, but the firmware hands the
;; hook an UNCAPPED count: ROM00:1409 stores the raw value, the cap at
;; ROM00:140F applies only to the reverse-copy loop, and ROM00:1446 reads the
;; raw value back.  Feed 140 elements and the hook is told 140 while only 128
;; entries exist.  ALWAYS CLAMP.
MAX_ELEMENTS    equ 128

;; The delivery buffer's descriptor gives it 20h bytes, six of which are the
;; record header, so 26 bytes of payload fit at 0F95Eh-0F977h.  The copy at
;; ROM00:148B is an unbounded LDIR: a longer result overruns the device-table
;; pointer at 0F978h.
MAX_OUTPUT      equ 26

;; --- do not touch ----------------------------------------------------------
;; 0FBB5h is the delivery record's status byte.  A nonzero value there is
;; written into the record and then suppresses the completion event, so a
;; blocked BDOS 03h call hangs until the scanner re-arms.
;; STATUS_BYTE   equ 0FBB5h     -- listed only so nobody reuses the address

;; --- the hook socket -------------------------------------------------------
;; A complete four-byte RST 10h banked-call thunk, not a bare pointer.  All
;; four cells matter.  See install.asm.
HOOK_THUNK      equ 0FBC0h      ; byte: 0D7h, the RST 10h opcode
HOOK_BANK       equ 0FBC1h      ; byte: the bank the hook lives in
HOOK_ADDR       equ 0FBC2h      ; word: the hook's address

;; The supported installer is BIOS jump-table entry 24, reached as
;; (0001h)+45h, with DE = hook address and HL = re-arm window (stored as
;; HL*64 at 0F9B0h).  HL is easy to miss and is not optional.
BIOS_TABLE_PTR  equ 0001h       ; CP/M convention: jump-table base + 3
BIOS_INSTALL_OFF equ 0045h      ; entry 24, install decode hook
