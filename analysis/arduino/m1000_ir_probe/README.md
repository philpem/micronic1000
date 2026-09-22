# M1000 IR probe

This sketch targets an Elegoo Uno R3 (`arduino:avr:uno`). Build it with the
Arduino CLI or IDE and open the serial monitor at **115200 baud**.

The pin assignments are defined at the top of the sketch:

| Signal | Uno pin | Direction |
|---|---:|---|
| `CLK_IN` | D2 | handheld clock input / interrupt |
| `DAT_IN` | D4 | handheld data input |
| `CLK_OUT` | D5 | return clock output |
| `DAT_OUT` | D6 | return data output |

The input lines must be protected from the handheld voltage as described in
the sketch comments. The output channels should remain optically separated.

The checked-in default is `RX_NARROW=1`, with `RX_NARROW_AXIS=2`. It sends a
reply to each completed handheld burst using flag `7Eh`, baseline polarity and
phase `-2/8` (data rise 30 us before clock rise), while varying the content
axis. The three content trials are flag only, flag plus `03h`, and an open
type-2 control acknowledgement. The startup banner and each burst line state
the active settings; the per-burst `payload=` field is the logical payload
bytes actually passed to the wire builder.

Other modes are compile-time flags in the sketch (`LISTEN_ONLY`, `LOOPBACK_TEST`,
`PULSE_TEST`, `FREERUN_TEST`, `LADDER_TEST`, `RX_SWEEP`, `FREE_TX`, and related
axes). They are mutually checked with preprocessor errors. Set
`RX_NARROW=0` when enabling another mode. `LISTEN_ONLY=1` is the safe monitor
configuration and does not drive the return outputs.

The emitter defines phase as data-rise minus clock-rise and schedules absolute
timestamps on an eighth-cell grid. `emit_late_max` in a burst report is the
largest `micros()` deadline lateness observed while dispatching that emitted
burst. It measures software deadline lateness only; it does not measure LED,
detector, wiring, interrupt or scope timing, and a zero value is not a physical
waveform guarantee. The host event test is an ideal scheduler check. Confirm
the actual waveform and electrical levels with an independent scope.

The host-only emitter harness is outside this directory at
`analysis/test_ir_emitter.cpp`; keeping it outside the sketch directory avoids
Arduino builders compiling its mock API and `main()` as sketch sources.
