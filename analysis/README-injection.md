# Keyboard matrix decode + injection plan

## Matrix layout (ROM00:1B58, copied to ram:FBDA by boot 026F-0272)

6x6 grid per SHIFT plane, index = row*6 + col.

UNSHIFTED plane (idx 0..35):
  row0 col0-5 : [.] A B [.] U [.]
  row1        :  C  D E F  V 0x7F
  row2        :  G  H I J  W 0x01
  row3        :  K  L M N 0D 0x06
  row4        :  O  P Q .  .  .
  row5        :  R  S T 0xD0 . .

SHIFTED plane (idx 36..71):
  row0:  .  (  )  .  1  0x7F
  row1:  .  %  #  &  2  0
  row2:  +  /  ,  ?  3  0x01
  row3:  -  *  .  0xDB 0D 0x06
  row4:  7  8  9  0xD0  .  .
  row5:  4  5  6  0x14  .  .

==> service keys H(13) L(19) P(25): rows2/3/4 col1 (all col INDEX 1)
Reset scanned with OUT(02)=0x02 (bit1 = col1) and expected
IN(00)&3F == 0x1C (bits 2,3,4 = rows 2,3,4). CONFIRMED consistent.

## Emulator injection

For the emulator's in_cb(on port 0x00): return the OR of sense bits
for all currently-claimed keys in the column the firmware is driving
(OUT port02 = col bitmask, e.g. col index c -> value 1<<c).

  '2'     = (col=4,row=1)  drive 0x10, sense 0x02
  ENTER   = (col=4,row=3)  drive 0x10, sense 0x08
  '5'     = (col=1,row=1)  drive 0x02, sense 0x02   [plane?]

Shift handling TBD empirically (numeric/alpha need plane; the first
real key reader reached will reveal whether a SHIFT line is needed).

## Emulator harness (next)

New file: trace_setclock.py
 - boot to steady state (reuse trace_io.py path)
 - inject ENTER at banner key-read (already works)
 - at menu, inject '2' (Set Clock), digits for the time, ENTER
 - log every OUT(08)/IN(28) index/data + all other port writes
