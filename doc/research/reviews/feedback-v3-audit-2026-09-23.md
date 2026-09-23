# Feedback-v3 experiment review — 2026-09-23

Scope: stock-context ROM00 wrapper, Elegoo Uno R3 emitter/input capture,
passive host logger, and the operator test plan. This reviews the whole
measurement chain; compiled code and simulated ports alone cannot prove
optical reception on the handheld.

## Findings that affect interpretation

1. **The original release had no positive control.** An absent receive
   marker could mean no receive, wrong ROM execution, failed yellow wiring,
   or missed Uno capture. Revision 2 adds a distinct initialization marker
   at the stock latch initialization. Require that marker in LISTEN_ONLY
   before interpreting any negative receive attempt. It proves execution of
   the patched initialization, not a complete cold reset of retained RAM.
2. **The original yellow release gaps were too short to guarantee capture.**
   They lasted only a few microseconds when the saved port-2A bit 0 was set.
   AVR pin-change flags are not an edge queue: a rise and fall before the
   ISR samples the pin can disappear. Revision 2 adds bounded high guards
   around the marker and tests actual assembled output timings. The marker
   is still a post-receive perturbation, delaying subsequent stock work.
3. **The old stock sweep omitted important physical hypotheses.** FREE_TX
   and RX_NARROW left the proposed LED role assignment at zero, and physical
   clock/data inversion was only configurable in the standalone feedback
   harness. Explicit stock configuration and fixed-candidate replay now
   make these choices available without another EPROM burn. Serialized data
   complement and electrical LED-level inversion remain different axes.
4. **Logging could disturb the response it was measuring.** Yellow serial
   output ran before the handheld-paced response decision. A blocking print
   could move a reply out of its intended window. Event capture belongs in
   the ISR; draining/printing must follow time-sensitive response work.
5. **The logger could turn missing evidence into a false control.** Missing
   TX records were called silent/control; reset epochs, capped widths and
   dropped events were not adequately distinguished. Analysis now leaves
   unmatched events unmatched, separates Uno restart epochs, marks losses,
   and uses timestamps even when the TX report arrives after its event.
   Initialization signatures are not associated with candidate IR replies.
6. **The original tests were mostly component checks.** They verified the
   wrapper's registers and a stubbed receive return, but did not validate the
   ROM-to-Uno timing contract or the real-time effects of Arduino libraries.
   Revision 2 adds marker timing, capture corner cases and stock-mode output
   tests. These are software checks; a physical scope/capture remains the
   check for analog rise time, ISR timing under real traffic and optical
   signal delivery.
7. **Longer optical bursts were labelled as proven handshake success.**
   Noise, merged bursts or a full capture buffer can also increase the
   count. The banner now reports possible progress and requests scope
   verification. The 160-bit input buffer is suitable for the short initial
   exchange; it is not a lossless full-session capture.

## Arduino Uno real-time audit

The installed Arduino AVR core is 1.8.8, targeting ATmega328P at 16 MHz.
The audit inspected its `wiring.c`, `HardwareSerial.cpp`, `WInterrupts.c`,
the sketch, and compiled AVR instructions. These library behaviors matter:

* **Do not disable interrupts for a whole IR burst.** Timer0 overflows every
  1,024 us; `micros()` can compensate for one pending overflow, not an
  arbitrary number. Long interrupt blackouts corrupt the clock used by the
  emitter's absolute deadlines. `micros()` itself saves/restores SREG around
  a short snapshot and is callable inside an ISR. See the official
  [Arduino timekeeping source](https://github.com/arduino/ArduinoCore-avr/blob/master/cores/arduino/wiring.c).
* **An interrupt flag is not an edge FIFO.** INT0 detects D2 rising edges,
  but software samples D4 only after ISR entry. AVR ISRs block other ISRs;
  priority selects the next pending vector, not preemption of the active
  ISR. Multiple PCINT changes before servicing can collapse into one flag.
  Thus even zero software ring drops cannot prove every physical edge was
  captured. See the interrupt and external-interrupt chapters of the
  [Microchip ATmega328P datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/Atmel-7810-Automotive-Microcontrollers-ATmega328P_Datasheet.pdf).
* **`digitalRead()` delays the data sample.** The previous ELF called
  `micros()`, performed debounce arithmetic, then called the generic pin
  API. The revised callback samples D4 directly through `PIND` before
  timekeeping/debounce. INT0 remains configured for RISING. This removes
  avoidable sample delay, but the Arduino interrupt trampoline and an
  already-running ISR still contribute latency. Physical D2/D4 setup and
  hold timing must be measured if errors persist. The reviewed stock-mode
  ELF reads `PIND` before the `micros()` call: estimated best-case edge to
  sample is about 60 AVR cycles (3.8 us), assuming no blocking ISR. This is
  an instruction-count estimate, not a measured worst-case bound.
* **Serial output can block foreground work.** The Uno's default TX ring is
  64 bytes; writing when it is full waits for room. UART interrupts also
  compete with GPIO scheduling. Yellow-event output now checks capacity
  before writing a complete line and runs after time-sensitive reply work.
  See the official [Arduino serial implementation](https://github.com/arduino/ArduinoCore-avr/blob/master/cores/arduino/HardwareSerial.cpp).
* **The old lateness metric was incomplete.** `emit_late_max` timestamps
  before the GPIO write, so an intervening ISR can delay the actual edge
  without appearing in that number. The additional
  `emit_applied_late_max` samples after the write and is a conservative
  software bound; an interrupt after the edge can inflate it. Timer0's
  four-microsecond resolution remains. It includes redundant writes that
  do not change a pin level, so it can exceed actual edge lateness. Neither
  field measures light.

Revision 2 also swaps RX buffer ownership in a short critical section and
copies bytes with interrupts enabled. It discards an incomplete low interval
present when D8 capture starts, keeps full 32-bit pulse widths, and saturates
the loss counter instead of letting it wrap to zero. The roughly 0.46-ms
ROM high guards provide substantial room for normal ISR service, but this
is not a formal worst-case proof under arbitrary external interrupt noise.
Measure D8 together with Uno D5/D6 on the scope for a representative run;
measure D2/D4 together when investigating received-bit sampling.

## What this test can establish

**CONFIRMED (stock bytes and wrapper tests):** the original link worker
tests `LINK_STATUS` bit 4 before calling the receive dispatcher. The v3
wrapper runs stock `Link_BlockRx` once, then reports its returned carry
class while preserving returned registers. A receive marker therefore
locates progress beyond the previous hook that halted before stock RX.
Carry clear is not proof of subsequent header/session validation.

**OPEN:** receive framing, the physical receiver channel assignments,
electrical polarity at the controller, and successful session validation.
The candidate `7Eh` flag is still SUSPECTED. A negative optical candidate
does not eliminate its framing unless the initialization marker, optical
monitor, emitted timing and experiment coverage checks have passed.

## Release and acceptance

Verification: 64 focused tests cover the ROM, logger, emitter and feedback
regression paths. Actual stock receive simulations cover both carry-set
and carry-clear returns, matching register/stack state, received bytes and
controller I/O before the added marker writes. The compiled Uno builds
cover LISTEN_ONLY, fixed FREE_TX, fixed swapped/inverted RX_NARROW, and
the existing feedback mode. The stock configurations use at most 911 bytes
of static SRAM out of 2048 in those builds. Strict site and rendered-page
checks pass. A separate reviewer inspected the compiled AVR sample order
and short critical sections. These checks do not substitute for the new
initialization-marker bench test or a representative scope capture.

The original `37D9B7` / MD5 `c3cc1fa00b4573566068ee5f441f89e1` image is
superseded by revision 2. Use the current checksum manifest and bench plan;
retain old logs as historical evidence and do not combine their schemas
silently. The new binary remains a generated local artifact.

Before calling the experiment a valid negative result, record the Uno
build settings and startup banner, the handheld initialization marker in a
silent capture, outbound optical activity during the stock V24 attempt,
zero reported capture losses, and the actual candidate rows sent during
that attempt. A 60-row FREE_TX cycle takes 15 seconds; a single roughly
five-second handheld retry batch cannot cover it. Repeated stock attempts
must overlap a full cycle, or use a fixed candidate for matched repeats.
Repeat any promising candidate with identical settings and an interleaved
silent control. Do not choose the nearest logged TX as a proven causal
frame merely because it precedes a marker.
