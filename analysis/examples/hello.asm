        org 0100h
        ld de,message
        ld c,09h
        call 0005h
        ld a,0a5h
        ld (0200h),a
        jp 0000h
message:
        db 'Hello World',13,10,'$'
