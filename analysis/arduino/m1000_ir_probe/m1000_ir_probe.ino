// M1000 IR link probe and responder.
#include <stdio.h>
// Default: combined feedback harness, silent until a USB T or V command. See
// doc/re-notes/ir-feedback-protocol.md. FEEDBACK_HARNESS=0 enables the
// historical optical monitor/sweep modes described below.
//
// Listens to the handheld's outbound clock/data pair, decodes the
// inverted-HDLC frame documented in doc/re-notes/ir-wire-protocol.md, and
// answers on the return pair while sweeping the parameters we cannot yet
// derive from the ROM.
//
// The handheld retries a connect 50 times at 93.75 ms (ROM00:2F58 sets the
// 32h count), so one operator keypress yields ~50 free trials.  The sketch
// changes one sweep parameter per burst. A burst longer than SUCCESS_CELLS
// is a candidate for progress into payload TX, requiring scope/ROM evidence:
// noise or merged bursts can also increase the count. A short burst does not
// identify which controller wait failed.
//
// Wiring (5 V AVR assumed - Uno/Nano at 16 MHz):
// Select BLACK_USE_NPN just below this wiring section before uploading:
//   0 = direct 5 V TTL drive: D7 -> BLACK / scanner pin 5 (current default)
//   1 = external NPN interface
// Direct TTL mode: D7 HIGH is idle; D7 LOW asserts the command. Connect
// both powered boards' grounds; power Uno before handheld, and switch the
// handheld off before unplugging Uno USB. No NPN/base resistors are used.
//   CLK_IN   D2   handheld clock emitter drive (INT0); legacy modes only
//   DAT_IN   D4   handheld data emitter drive; legacy modes only
//   CLK_OUT  D5   physical return channel A; proposed clock role
//   DAT_OUT  D6   physical return channel B; proposed data role
//   BLACK_OUT D7  with BLACK_USE_NPN=1, wire the external transistor:
//                D7 -> 10k resistor -> external NPN BASE
//                NPN COLLECTOR -> BLACK; NPN EMITTER -> common GND
//                100k resistor from BASE to EMITTER (off during Uno reset)
//                D7 HIGH pulls BLACK low; D7 LOW releases BLACK.
//                Direct wiring instead requires BLACK_USE_NPN=0.
//   YELLOW_IN D8  handheld YELLOW / scanner pin 6 -> D8 (input only)
//                10k pull-up from YELLOW to UNO 5 V, NOT handheld Vcc
//                YELLOW carries ACK, START and 1200-baud result records.
//   GND          handheld BLUE / scanner pin 8 -> UNO GND and NPN EMITTER
//
// BLACK/YELLOW/GND are the three scanner-connector wires for feedback mode.
// Connector pin numbers/colours confirmed by owner, 2026-09-22.
// Check the actual NPN's B/C/E pinout. Remove old BLACK-to-ground test loads
// and YELLOW-to-orange/Vcc or YELLOW-to-ground test resistors.
// Leave ORANGE/pin 3 (handheld Vcc), RED/pin 1, BROWN/pin 2, VIOLET/pin 4
// and GREEN/pin 7 disconnected and insulated. Power Uno from USB and the
// handheld from batteries; share GND, not positive supplies.
// Keep the existing D5/D6 LED current limiting/drivers aimed at the top V24
// window. D5/D6 connect optically, not to scanner-connector contacts.
// D2/D4 monitoring is disabled and not required in feedback mode.
//
#ifndef BLACK_USE_NPN
#define BLACK_USE_NPN 0  // Current bench: D7 directly wired to BLACK / pin 5.
#endif
#if BLACK_USE_NPN != 0 && BLACK_USE_NPN != 1
#error "BLACK_USE_NPN must be 0 (direct TTL) or 1 (external NPN)"
#endif

// Owner clarification 2026-09-22: receive LED roles are unconfirmed. These
// names describe the generated signals, not identified handheld detectors.
// Both optical assignments need testing; 7E as a receive flag is SUSPECTED.
//
// For legacy D2/D4 monitoring, the handheld's drive lines swing to ~5.5 V,
// which is over VCC+0.5 on a 5 V
// part and well over a 3.3 V one.  Put 10k in series with each input, or a
// divider on a 3.3 V board.  Do not connect an input directly.
//
// Keep the two return channels optically separated - a mask or a short opaque
// tube per LED. Crosstalk between channels can confound protocol tests.

// Stage 1: build with LISTEN_ONLY 1, confirm the monitor prints 17- and
// 22-cell bursts every 93.75 ms and that they match the scope.  Only then set
// it to 0 and let the sweep transmit.  A responder debugged against a decoder
// you have not validated is two unknowns at once.
#ifndef LISTEN_ONLY
#define LISTEN_ONLY 0
#endif

// Exerciser readout.  The patched-ROM exerciser (analysis/rom_exerciser/)
// streams LINK_STATUS records as inverted-HDLC frames of 64 x 11-byte records.
// A record frame is ~6 KB of cells, far past the 160-cell burst buffer, so
// this mode de-stuffs the bits as they arrive and streams one hex token per
// byte; the burst gap ends the line, so decode_records.py --hex sees one frame
// per line exactly as it expects.  Needs LISTEN_ONLY 1 (it never transmits).
// Use it to read the exerciser's records over serial with no scope in the loop.
#ifndef RECORD_READOUT
#define RECORD_READOUT 0
#endif

// Stage 1b: point the Arduino's own emitters at its own detectors and build
// with LOOPBACK_TEST 1.  It transmits twice a second and reports what its
// receiver made of it, so the whole transmit chain -- framing, cell timing,
// port writes, LED drive, optics -- is proven against a receiver already known
// to work.  A correct flag+03h reply must come back as 10000001000001011, the
// handheld's own form A.  Until that passes, a silent handheld proves nothing:
// a dead or misaimed emitter looks exactly like a protocol we have not guessed.
#ifndef LOOPBACK_TEST
#define LOOPBACK_TEST 0
#endif

// Stage 2b: which of the handheld's two detectors is clock and which is data
// is NOT known.  Its two emitters identify themselves -- one is periodic, one
// is sparse -- but nothing identifies its receivers, so our two emitters may
// be feeding them backwards, and every negative result so far is suspect for
// that reason alone.  Build with ORIENTATION_TEST 1 to hold content, delay and
// clock mode fixed and alternate the orientation on every burst.  The handheld
// stretches its retry cadence from 93.75 ms to ~109 ms when it notices us, so
// comparing that stretch between the two interleaved populations decides the
// orientation without needing it to answer.
#ifndef ORIENTATION_TEST
#define ORIENTATION_TEST 0
#endif

// Stage 3: is the handheld reacting to our BITS, or just to light being
// present at a particular moment?  conn7 said the latter -- the disturbance
// tracked when our light went dark (92-100% at 3-9 ms after its burst, ~20%
// either side) and not what the frame encoded, with the long frame replies
// scoring 0% only because they ended too late.  This mode removes framing
// entirely: a featureless pulse of FIXED duration, swept only in start time,
// with a silent control interleaved at every start time so the baseline is
// measured under the same conditions rather than assumed.
//
// If a bare pulse reproduces the timing reaction, the reaction does not by
// itself prove content decoding.  If only the modulated variants do it, the
// front end is edge-sensitive and a carrier matters.  If nothing does it,
// conn7's correlation was an artefact and we are back to needing a channel.
#ifndef PULSE_TEST
#define PULSE_TEST 0
#endif

// Stage 4: sweep the address byte.  conn10 showed the handheld reacts to
// 00h/03h/1Fh but not to FFh under identical conditions, so the byte after the
// flag looks like it is being examined.  The handheld's own prelude is
// `id & 1Fh`, and bit 5 is the port select that LinkPortSelect drives from the
// link id -- so 00h-3Fh covers the whole of the field the firmware is known to
// use, and the bits above it are the interesting unknown.  Raise ADDR_HI to
// widen; 7Fh and FFh ride along as deliberate out-of-range controls.
#ifndef ADDR_SWEEP
#define ADDR_SWEEP 0
#endif

// Stage 5: a genuinely free-running return clock.  Everything tried so far has
// been a burst a few ms long, but the firmware dies waiting for LINK_STATUS
// bit 6 at ROM00:32F3 -- a controller status bit, not anything on the wire --
// and a controller might only report a live link while it is actually being
// clocked.  Here Timer2 drives the clock emitter continuously at 8192 Hz from
// power-on and never stops; data is gated on top, in phase, by the same ISR.
// Stimulus 4 gates the clock off and sends an ordinary burst instead, so the
// comparison against everything before is made inside one run rather than
// across two.
#ifndef FREERUN_TEST
#define FREERUN_TEST 0
#endif

// Stage 6: a completeness ladder.  conn7's complete frames (flag + body +
// closing flag) scored 0% where a bare flag+address scored 74%, which I put
// down to their length pushing them past the timing window -- but conn10 then
// showed start time barely matters between 1 and 9 ms, so that 0% may have
// been real.  If a COMPLETE frame is cheaply rejected while an INCOMPLETE one
// leaves the receiver hanging for 15.6 ms, then dropping to baseline is the
// receive path succeeding, not failing.
//
// Length and completeness are crossed so they cannot be confused: stim 3 is
// the same length as stim 4 but has no closing flag.  Everything starts early
// so no variant can fall outside the window.
#ifndef LADDER_TEST
#define LADDER_TEST 0
#endif

// Stage 7: receive-convention sweep.  The controller's receive path may not
// use the same HDLC sense, data polarity or clock phase as its transmit path
// (doc/re-notes/ir-wire-protocol.md, open question C).  This mode answers each
// handheld burst with the same frame under every combination of:
//   - flag sense: 1000_0001 (the handheld's own, ~7Eh) or 0111_1110 (7Eh);
//   - data polarity: normal or complemented;
//   - data-to-clock phase: +/-1/2, +/-1/4 and 0 cell (the transmit convention
//     is a 1/4-cell data lead, DATA_LEAD_US);
//   - content: flag only, flag+03h echo, or flag+03h plus a legal body.
// The controller's reaction is read from the ROM exerciser's --witness build
// (LINK_STATUS OR/AND, ISRC), not scored here.  Nothing in the handheld tells
// us which combination it accepted, so this mode only varies the stimulus and
// reports the parameters -- pair it with the witness on the glass.
#ifndef RX_SWEEP
#define RX_SWEEP 0
#endif

// Stage 8: free-running receive-convention sweep, for the stock-ROM receive
// hook (micron1_stockhook_rx.bin).  RX_SWEEP above answers the handheld's own
// bursts. During the stock TX wait LINK_CTRL bits 6/7 are clear; their
// electrical effect on reception is unconfirmed. This mode
// transmits one swept burst every FREE_TX_PERIOD_MS with no handheld burst at
// all, sampling different transaction phases. Axes are the
// same as RX_SWEEP: flag sense, data polarity, phase and content, one
// combination per burst, parameters printed.
#ifndef FREE_TX
#define FREE_TX 0
#endif
#ifndef FREE_TX_PERIOD_MS
#define FREE_TX_PERIOD_MS 250
#endif

// Stock-ROM receive-hook feedback on scanner yellow / Uno D8. Enable with a
// legacy optical mode (including LISTEN_ONLY silent control); it is separate
// from the black-command feedback harness used by the v1/v2 diagnostic ROMs.
#ifndef STOCK_CONTEXT_EVENTS
#define STOCK_CONTEXT_EVENTS 0
#endif
// Physical LED assignment and active level for stock optical trials. Values
// are fixed for a build; RX_NARROW_AXIS=3 alternates around STOCK_TX_SWAP.
#ifndef STOCK_TX_SWAP
#define STOCK_TX_SWAP 0
#endif
#ifndef STOCK_CLOCK_INVERT
#define STOCK_CLOCK_INVERT 0
#endif
#ifndef STOCK_DATA_INVERT
#define STOCK_DATA_INVERT 0
#endif
// Freeze the candidate axes for repeated attempts with the same waveform.
#ifndef STOCK_FIXED_CANDIDATE
#define STOCK_FIXED_CANDIDATE 0
#endif
#ifndef STOCK_FLAG_IDX
#define STOCK_FLAG_IDX 1       // 7E
#endif
#ifndef STOCK_PHASE_IDX
#define STOCK_PHASE_IDX 1      // -2/8 cell
#endif
#ifndef STOCK_POL_IDX
#define STOCK_POL_IDX 0
#endif
#ifndef STOCK_CONTENT_IDX
#define STOCK_CONTENT_IDX 2    // type-2 control ack
#endif
// Stock optical framing: -1 retains the historical flag-dependent choice;
// 0 disables stuffing, 1 inserts 0 after five 1s, 2 inserts 1 after five 0s
// on the emitted wire, after the data-polarity axis is applied.
#ifndef STOCK_STUFFING_MODE
#define STOCK_STUFFING_MODE -1
#endif
#ifndef STOCK_CLOSE_FLAG
#define STOCK_CLOSE_FLAG 0
#endif
// Optional raw closing marker byte, independent of the opening marker.
// -1 disables it; 0..255 appends it after terminal data stuffing. This is
// unstuffed delimiter behavior, not an FCS byte in the stuffed data region.
#ifndef STOCK_CLOSE_BYTE
#define STOCK_CLOSE_BYTE -1
#endif
// Optional raw prefix byte immediately before the opening flag for the fixed
// type-2 ACK. -1 leaves the historical frame unchanged; the byte is outside
// the stuffed payload (e.g. 7E repeats a flag, 00 adds eight data-low cells).
#ifndef STOCK_PREFIX_BYTE
#define STOCK_PREFIX_BYTE -1
#endif
// Diagnostic payload for fixed type-2 ACK replies: 10 zero bytes instead of
// the stock 10-byte ACK. This keeps the data field exactly 80 cells long.
#ifndef STOCK_ZERO_PAYLOAD
#define STOCK_ZERO_PAYLOAD 0
#endif
// One-bit diagnostic: second payload byte 07h -> 06h.
#ifndef STOCK_PAYLOAD07_TO06
#define STOCK_PAYLOAD07_TO06 0
#endif
#if STOCK_PAYLOAD07_TO06 != 0 && STOCK_PAYLOAD07_TO06 != 1
#error "STOCK_PAYLOAD07_TO06 must be 0 or 1"
#endif
// One-bit diagnostic: first payload byte 00h -> 80h.
#ifndef STOCK_PAYLOAD00_TO80
#define STOCK_PAYLOAD00_TO80 0
#endif
#if STOCK_PAYLOAD00_TO80 != 0 && STOCK_PAYLOAD00_TO80 != 1
#error "STOCK_PAYLOAD00_TO80 must be 0 or 1"
#endif
#if STOCK_PAYLOAD00_TO80 && (STOCK_PAYLOAD07_TO06 || STOCK_ZERO_PAYLOAD)
#error "STOCK_PAYLOAD00_TO80 requires the other payload controls off"
#endif
#ifndef STOCK_REPLY_DELAY_US
#define STOCK_REPLY_DELAY_US 4000
#endif
#ifndef STOCK_REPLY_DELAY_STEP_US
#define STOCK_REPLY_DELAY_STEP_US 0
#endif
#ifndef STOCK_REPLY_DELAY_COUNT
#define STOCK_REPLY_DELAY_COUNT 1
#endif
#ifndef STOCK_REPLY_EVERY_N
#define STOCK_REPLY_EVERY_N 1
#endif
#if (STOCK_TX_SWAP != 0 && STOCK_TX_SWAP != 1) || \
    (STOCK_CLOCK_INVERT != 0 && STOCK_CLOCK_INVERT != 1) || \
    (STOCK_DATA_INVERT != 0 && STOCK_DATA_INVERT != 1)
#error "STOCK_TX_SWAP, STOCK_CLOCK_INVERT, STOCK_DATA_INVERT must be 0 or 1"
#endif
#if STOCK_FIXED_CANDIDATE != 0 && STOCK_FIXED_CANDIDATE != 1
#error "STOCK_FIXED_CANDIDATE must be 0 or 1"
#endif
#if STOCK_FIXED_CANDIDATE && !(FREE_TX || RX_NARROW)
#error "STOCK_FIXED_CANDIDATE requires FREE_TX or RX_NARROW"
#endif
#if STOCK_FLAG_IDX < 0 || STOCK_FLAG_IDX > 1 || \
    STOCK_PHASE_IDX < 0 || STOCK_PHASE_IDX > 4 || \
    STOCK_POL_IDX < 0 || STOCK_POL_IDX > 1 || \
    STOCK_CONTENT_IDX < 0 || STOCK_CONTENT_IDX > 3
#error "STOCK candidate indices out of range"
#endif
#if STOCK_STUFFING_MODE < -1 || STOCK_STUFFING_MODE > 2 || \
    (STOCK_CLOSE_FLAG != 0 && STOCK_CLOSE_FLAG != 1)
#error "STOCK_STUFFING_MODE must be -1..2; STOCK_CLOSE_FLAG must be 0 or 1"
#endif
#if STOCK_CLOSE_BYTE < -1 || STOCK_CLOSE_BYTE > 255 || \
    STOCK_PREFIX_BYTE < -1 || STOCK_PREFIX_BYTE > 255 || \
    (STOCK_CLOSE_FLAG && STOCK_CLOSE_BYTE >= 0)
#error "STOCK_CLOSE_BYTE/STOCK_PREFIX_BYTE must be -1..255; close byte cannot combine with STOCK_CLOSE_FLAG"
#endif
#if STOCK_FIXED_CANDIDATE == 0 && STOCK_CONTENT_IDX == 3
#error "STOCK_CONTENT_IDX=3 requires STOCK_FIXED_CANDIDATE=1"
#endif
#if STOCK_ZERO_PAYLOAD != 0 && STOCK_ZERO_PAYLOAD != 1
#error "STOCK_ZERO_PAYLOAD must be 0 or 1"
#endif
#if STOCK_REPLY_DELAY_US < 500 || STOCK_REPLY_DELAY_US > 60000
#error "STOCK_REPLY_DELAY_US must be 500..60000"
#endif
#if STOCK_REPLY_DELAY_COUNT < 1 || STOCK_REPLY_DELAY_COUNT > 32 || \
    STOCK_REPLY_DELAY_STEP_US < 0 || \
    STOCK_REPLY_DELAY_US + \
    (STOCK_REPLY_DELAY_COUNT - 1) * STOCK_REPLY_DELAY_STEP_US > 60000
#error "STOCK reply delay sweep must contain 1..32 values in 500..60000 us"
#endif
#if STOCK_REPLY_DELAY_COUNT > 1 && !(STOCK_FIXED_CANDIDATE && RX_NARROW)
#error "STOCK reply delay sweep requires fixed RX_NARROW"
#endif
#if STOCK_REPLY_EVERY_N < 1 || STOCK_REPLY_EVERY_N > 32 || \
    (STOCK_REPLY_EVERY_N > 1 && !(STOCK_FIXED_CANDIDATE && RX_NARROW))
#error "STOCK_REPLY_EVERY_N must be 1..32 and requires fixed RX_NARROW"
#endif

// Stage 9: narrowed receive sweep.  The first handheld-paced RX_SWEEP run
// halted on flag=7E phase=-2/8 pol=0 content=2 (the controller reported a
// pending receive), while earlier 7E lines at phase -4 did not -- so the flag
// alone may not be sufficient. This mode fixes that trial baseline and
// varies exactly ONE axis, to isolate what the receive path actually needs:
//   RX_NARROW_AXIS 0 = phase (-4,-2,0,2,4 eighths of a cell)
//                  1 = data polarity (normal / complemented)
//                  2 = content (flag / flag+03h / open type-2 control ack)
//                  3 = optical clock/data assignment (normal / swapped)
// Flag is fixed to 7E (the current trial baseline); the data lead and the
// other axes stay at the handheld's own TX convention unless selected here. Reply
// to each handheld burst, handheld-paced.
#ifndef FEEDBACK_HARNESS
#if LISTEN_ONLY || RECORD_READOUT || LOOPBACK_TEST || ORIENTATION_TEST || PULSE_TEST || ADDR_SWEEP || FREERUN_TEST || LADDER_TEST || RX_SWEEP || FREE_TX || RX_NARROW
#define FEEDBACK_HARNESS 0
#else
#define FEEDBACK_HARNESS 1
#endif
#endif
#ifndef RX_NARROW
#if FEEDBACK_HARNESS
#define RX_NARROW 0
#else
#define RX_NARROW 1
#endif
#endif
#ifndef RX_NARROW_AXIS
#define RX_NARROW_AXIS 2
#endif
#if RX_NARROW_AXIS < 0 || RX_NARROW_AXIS > 3
#error "RX_NARROW_AXIS must be 0 (phase), 1 (polarity), 2 (content), or 3 (swap)"
#endif

// Feedback command syntax keeps its historical T fields and defaults. After
// payload, optional fields are `clk_inv dat_inv`; an additional trailing
// `repeat_count repeat_gap_ms` enables repeats only for `T ... X ...` trials.
// repeat_count is 2..3 total identical bursts; repeat_gap_ms is 1..60 ms
// between scheduled starts. delay_us + (count-1)*gap + 26 ms must be <=80 ms,
// reserving 192 encoded cells plus the maximum lead inside the ROM's ~100 ms
// pending poll. The runtime also checks the actual scheduled frame end.
// Older commands (omitting both pairs) retain one burst, or remain silent.

// Reply lead-in: the handheld's own bursts carry 4-5 clock-only cells before
// the flag (its framer's pipeline flush); a faithful reply should too.
#define RX_LEAD_CELLS 5
// The minimal Commstar type-2 control-ack reply -- i.e. the return handshake
// the firmware's Link_BlockTx waits for.  Content 7 in buildReply():
//   wire:  flag 7E + zero-stuffed( 00 07 00 02 seq id 00 00 02 seq )
//   frame: [u16 len=7][type=2][seq][id][spare 00][payload 00], trailer [02 seq]
#define RX_ACK_SEQ 1
#define RX_ACK_ID  0x43

// The three flags are not independent.  ORIENTATION_TEST alternates the
// orientation inside advanceSweep(), and both advanceSweep() and the reply are
// compiled out when LISTEN_ONLY or LOOPBACK_TEST is set -- so the wrong
// combination builds cleanly, transmits nothing, and wastes a run looking
// exactly like a negative result.  Fail at compile time instead.
#if LADDER_TEST && (LISTEN_ONLY || LOOPBACK_TEST || ORIENTATION_TEST || PULSE_TEST || ADDR_SWEEP || FREERUN_TEST)
#error "LADDER_TEST needs every other mode flag 0"
#endif
#if FREERUN_TEST && (LISTEN_ONLY || LOOPBACK_TEST || ORIENTATION_TEST || PULSE_TEST || ADDR_SWEEP)
#error "FREERUN_TEST needs every other mode flag 0"
#endif
#if PULSE_TEST && (LISTEN_ONLY || LOOPBACK_TEST || ORIENTATION_TEST)
#error "PULSE_TEST needs LISTEN_ONLY 0, LOOPBACK_TEST 0, ORIENTATION_TEST 0"
#endif
#if ORIENTATION_TEST && LISTEN_ONLY
#error "ORIENTATION_TEST needs LISTEN_ONLY 0 -- it has to transmit to alternate"
#endif
#if ORIENTATION_TEST && LOOPBACK_TEST
#error "ORIENTATION_TEST and LOOPBACK_TEST are mutually exclusive"
#endif
#if LISTEN_ONLY && LOOPBACK_TEST
#error "LOOPBACK_TEST needs LISTEN_ONLY 0 -- it transmits to hear itself"
#endif
#if ADDR_SWEEP && !PULSE_TEST
#error "ADDR_SWEEP is a PULSE_TEST variant and needs PULSE_TEST 1"
#endif
#if RECORD_READOUT && !LISTEN_ONLY
#error "RECORD_READOUT needs LISTEN_ONLY 1 -- it is a listen-only mode"
#endif
#if RX_SWEEP && (LADDER_TEST || FREERUN_TEST || PULSE_TEST || ADDR_SWEEP || ORIENTATION_TEST || LOOPBACK_TEST || LISTEN_ONLY || FREE_TX)
#error "RX_SWEEP needs every other mode flag 0"
#endif
#if FREE_TX && (LADDER_TEST || FREERUN_TEST || PULSE_TEST || ADDR_SWEEP || ORIENTATION_TEST || LOOPBACK_TEST || LISTEN_ONLY || RX_SWEEP || RX_NARROW)
#error "FREE_TX needs every other mode flag 0"
#endif
#if RX_NARROW && (LADDER_TEST || FREERUN_TEST || PULSE_TEST || ADDR_SWEEP || ORIENTATION_TEST || LOOPBACK_TEST || LISTEN_ONLY || RX_SWEEP || FREE_TX)
#error "RX_NARROW needs every other mode flag 0"
#endif
#if FEEDBACK_HARNESS && (LISTEN_ONLY || RECORD_READOUT || LOOPBACK_TEST || ORIENTATION_TEST || PULSE_TEST || ADDR_SWEEP || FREERUN_TEST || LADDER_TEST || RX_SWEEP || FREE_TX || RX_NARROW)
#error "FEEDBACK_HARNESS needs every legacy mode 0"
#endif
#if STOCK_CONTEXT_EVENTS && (FEEDBACK_HARNESS || !(FREE_TX || RX_NARROW || RX_SWEEP || LISTEN_ONLY))
#error "STOCK_CONTEXT_EVENTS needs a stock optical mode"
#endif

// ---------------------------------------------------------------- timing --
// True values, not raw measurements.  The handheld's drive is slew-limited
// with falls two to three times slower than rises, so 50%-threshold widths
// read ~3 us long.  De-biased, every edge lands on a 1/8-cell grid driven by a
// two-phase clock: with the clock's rising edge as phase 0, data rises at
// phase -2, the clock falls at +4, data falls at +3.  Data therefore changes
// at the midpoint of the clock's low phase, half a phase from the sampling
// edge.  See doc/re-notes/ir-wire-protocol.md.
const unsigned long CELL_US      = 122;   // 122.0703 us = 8192 bit/s exactly
                                          //   = 3686400/450 = 32768/4
const unsigned long DATA_LEAD_US = 30;    // 2/8 cell = 30.52 us
const unsigned long CLK_HIGH_US  = 61;    // 4/8 cell, 50% duty
const unsigned long DATA_HIGH_US = 76;    // 5/8 cell = 76.29 us
const unsigned long GAP_US       = 400;   // no clock for this long = burst over.
                                          // Must clear 244 us: form B really does
                                          // drop the cell-4 clock, and a 200 us
                                          // threshold split the burst there.
const unsigned long MIN_EDGE_US  = 60;    // a software Schmitt: legitimate clock
                                          // edges are 122 us apart, so anything
                                          // closer is chatter from a slow edge
                                          // crossing a non-hysteretic threshold

const uint8_t  FLAG        = 0x81;  // = ~0x7E, six 0s bracketed by 1s
const uint8_t  SUCCESS_CELLS = 30;  // a payload frame is 100+ cells; 17/22 is not

const uint8_t CLK_IN = 2, DAT_IN = 4, CLK_OUT = 5, DAT_OUT = 6;
const uint8_t BLACK_OUT = 7, YELLOW_IN = 8;

#if FEEDBACK_HARNESS
#include "feedback_harness.h"
#endif

// ------------------------------------------------------------- reception --
const uint8_t RX_BITS_CAPACITY = 160;
#if STOCK_CONTEXT_EVENTS
volatile uint8_t rxBitsA[RX_BITS_CAPACITY], rxBitsB[RX_BITS_CAPACITY];
volatile uint8_t *rxBits = rxBitsA;  // switch buffers before printing
#else
volatile uint8_t rxBits[RX_BITS_CAPACITY];  // a 12-byte frame is ~120 cells
#endif
volatile uint8_t  rxCount = 0;
volatile unsigned long lastEdgeUs = 0;
volatile bool     txActive = false;   // ignore our own crosstalk

// Data-line activity monitor.  If every sampled bit is 0 this says whether the
// data channel is carrying anything at all, and if so at what phase -- which
// separates "no signal" from "sampled at the wrong instant".
uint8_t  datPrev  = 0;
uint16_t datRises = 0;
unsigned long datPhase = 0;   // us from the previous clock edge to a data rise

#if RECORD_READOUT
// ------------------------------------------- streaming inverted-HDLC de-stuff
// The exerciser's record frame is 64 x 11 bytes (~6 KB of cells), so it cannot
// be buffered on an AVR and must be de-stuffed on the fly.  Bytes are handed
// to the main loop through a small single-producer/single-consumer ring; only
// uint8_t head/tail are shared, which is atomic on AVR.
const uint8_t RB_SIZE = 128;                  // power of two
volatile uint8_t rbBuf[RB_SIZE];
volatile uint8_t rbHead = 0, rbTail = 0;

volatile uint8_t dfHunting = 1;   // 1 = hunting for the 1000_0001 flag
volatile uint8_t dfShift   = 0;   // last 8 raw bits, for the flag hunt
volatile uint8_t dfByte    = 0;   // byte being assembled, MSB first
volatile uint8_t dfBits    = 0;   // bits collected in dfByte, 0..7
volatile uint8_t dfZeros   = 0;   // run of 0s since the last 1
volatile uint8_t dfStuff   = 0;   // set: the next bit is the stuffed 1
volatile uint8_t dfMalformed = 0; // set after a non-stuffed bit follows 5 zeros

// Inverted HDLC: idle 0, flag 1000_0001 sent raw, data bit-stuffed with a 1
// after five consecutive 0s, MSB first.  Stuffed data can never contain the
// flag (six 0s are forbidden), so a sliding 8-bit match is unambiguous.
inline void destuffBit(uint8_t b) {
  if (dfMalformed) return;
  if (dfHunting) {
    dfShift = (uint8_t)((dfShift << 1) | b);
    if (dfShift == FLAG) {                    // flag: start of a frame
      dfHunting = 0; dfByte = 0; dfBits = 0; dfZeros = 0; dfStuff = 0;
    }
    return;
  }
  if (dfStuff) {                              // drop the inserted 1
    if (b != 1) {                              // five zeros require a raw 1
      dfMalformed = 1;                        // do not emit corrupt bytes
      return;
    }
    dfStuff = 0; dfZeros = 0;
    return;
  }
  dfByte = (uint8_t)((dfByte << 1) | b);
  if (++dfBits == 8) {
    uint8_t next = (uint8_t)((rbHead + 1) & (RB_SIZE - 1));
    if (next != rbTail) { rbBuf[rbHead] = dfByte; rbHead = next; }
    dfByte = 0; dfBits = 0;
  }
  if (b) dfZeros = 0;
  else if (++dfZeros == 5) dfStuff = 1;       // five 0s: next bit is stuffed
}

// A burst gap ends the frame; re-arm the flag hunt for the next one.
void destuffReset() {
  noInterrupts();
  dfHunting = 1; dfShift = 0; dfByte = 0; dfBits = 0; dfZeros = 0;
  dfStuff = 0; dfMalformed = 0;
  interrupts();
}

// Stream whatever bytes have arrived.  Called every loop pass so the ring
// never backs up: printing is faster than an 8192 bit/s byte stream.
void drainRing() {
  while (rbTail != rbHead) {
    uint8_t b = rbBuf[rbTail];
    rbTail = (uint8_t)((rbTail + 1) & (RB_SIZE - 1));
    if (b < 0x10) Serial.print('0');
    Serial.print(b, HEX);
    Serial.print(' ');
  }
}
#endif

void onClockEdge() {
  if (txActive) return;
  // INT0 latches the clock edge, but D4 data must be sampled immediately on
  // ISR entry; digitalRead() and micros() each add avoidable sample latency.
  uint8_t b = (PIND & _BV(PD4)) != 0;
  unsigned long now = micros();
  // Reject chatter.  A plain CMOS inverter on the photodiode node crosses its
  // threshold over tens of ns of ambiguity, and one double-counted clock edge
  // fabricates a bit cell.  Real edges are a whole cell apart, so this costs
  // nothing and removes the need for a Schmitt-trigger part.
  if (rxCount && now - lastEdgeUs < MIN_EDGE_US) return;
  if (rxCount < RX_BITS_CAPACITY) rxBits[rxCount++] = b;
  lastEdgeUs = now;
#if RECORD_READOUT
  destuffBit(b);
#endif
}

#if STOCK_CONTEXT_EVENTS
// Uno D8 is PB0/PCINT0. Capture narrow yellow pulses even while sendFrame()
// is busy scheduling optical edges; printing stays outside the interrupt.
struct StockYellowEvent { uint32_t riseUs; uint32_t lowUs; };
const uint8_t STOCK_EVENT_RING = 8;
volatile StockYellowEvent stockEvents[STOCK_EVENT_RING];
volatile uint8_t stockEventHead = 0, stockEventTail = 0;
volatile uint16_t stockEventDrops = 0;
volatile uint32_t stockYellowLowAt = 0;
volatile bool stockYellowWasHigh = true;
volatile bool stockYellowHaveFall = false;
unsigned long stockLastReplyStartUs = 0;

ISR(PCINT0_vect) {
  bool high = (PINB & _BV(PB0)) != 0;
  if (high == stockYellowWasHigh) return;
  uint32_t at = micros();
  stockYellowWasHigh = high;
  if (!high) { stockYellowLowAt = at; stockYellowHaveFall = true; return; }
  // A low input at startup has no observed falling edge or known onset.
  if (!stockYellowHaveFall) return;
  stockYellowHaveFall = false;
  uint8_t next = (uint8_t)((stockEventHead + 1) & (STOCK_EVENT_RING - 1));
  if (next == stockEventTail) {
    if (stockEventDrops != 0xFFFFU) ++stockEventDrops;
    return;
  }
  stockEvents[stockEventHead].riseUs = at;
  stockEvents[stockEventHead].lowUs = at - stockYellowLowAt;
  stockEventHead = next;
}

void stockDrainYellowEvents() {
  // Format one complete line, then commit its dequeue only when the UART
  // ring can take it without blocking an incoming optical reply.
  char line[64];
  noInterrupts();
  bool haveEvent = stockEventTail != stockEventHead;
  StockYellowEvent event = {0, 0};
  if (haveEvent) {
    event.riseUs = stockEvents[stockEventTail].riseUs;
    event.lowUs = stockEvents[stockEventTail].lowUs;
  }
  uint16_t drops = stockEventDrops;
  interrupts();
  int len;
  if (haveEvent) {
    len = snprintf(line, sizeof(line), "# STOCK_YELLOW rise_us=%lu low_us=%lu\n",
                   (unsigned long)event.riseUs, (unsigned long)event.lowUs);
  } else if (drops) {
    len = snprintf(line, sizeof(line), "# STOCK_YELLOW_DROPS %u\n", drops);
  } else return;
  if (len <= 0 || len >= (int)sizeof(line) ||
      Serial.availableForWrite() < len) return;
  Serial.write((const uint8_t *)line, (size_t)len);
  noInterrupts();
  if (haveEvent) {
    stockEventTail = (uint8_t)((stockEventTail + 1) & (STOCK_EVENT_RING - 1));
  } else {
    // Drops may have accumulated while the line was sent; retain those.
    stockEventDrops -= drops;
  }
  interrupts();
}
#endif

// ------------------------------------------------------------ the framer --
// Inverted HDLC: idle 0, flag 1000_0001 sent raw, data bit-stuffed with a 1
// after five consecutive 0s, MSB first.
#if FEEDBACK_HARNESS
uint8_t frameBits[192];  // 16 data bytes + worst stuffing + two flags
#else
uint8_t frameBits[128];
#endif
uint8_t frameLen = 0;

#if RX_SWEEP || FREE_TX || RX_NARROW
// Receive-convention axes.  The flag byte and the data polarity are the two
// ways the same bits can appear on the wire; txPhaseEighths (set in the reply
// path) moves the data edges relative to a fixed clock.  Content maps onto
// buildReply()'s cases.  Declared here because putFlag() below uses them.
const uint8_t RX_N_FLAG = 2;
const uint8_t rxFlagTab[RX_N_FLAG] = { 0x81, 0x7E };
const int8_t  RX_N_PHASE = 5;
const int8_t  rxPhaseTab[RX_N_PHASE] = { -4, -2, 0, 2, 4 };  // eighths of a cell
const uint8_t RX_N_POL = 2;            // data polarity: normal / complemented
const uint8_t RX_N_CONTENT = 3;        // flag / flag+03h / type-2 ack (open)
const uint8_t rxContentMap[RX_N_CONTENT + 1] = { 0, 1, 7, 9 };
uint8_t rxFlagIdx = 0, rxPhaseIdx = 1, rxPolIdx = 0, rxContentIdx = 1;
#endif

void putBit(uint8_t b) { if (frameLen < sizeof(frameBits)) frameBits[frameLen++] = b; }

void putFlag() {
#if RX_SWEEP || FREE_TX || RX_NARROW
  uint8_t f = rxFlagTab[rxFlagIdx];
#else
  uint8_t f = FLAG;
#endif
  for (int8_t i = 7; i >= 0; i--) putBit((f >> i) & 1);
}

// Count the selected data-bit run only; flags are always sent raw. The stock
// setting can override the historical flag-dependent convention.
uint8_t stuffingMode = 2;
#if RX_SWEEP || FREE_TX || RX_NARROW
void selectStockStuffing() {
#if STOCK_STUFFING_MODE == -1
  stuffingMode = rxFlagTab[rxFlagIdx] == 0x7E ? 1 : 2;
#else
  stuffingMode = STOCK_STUFFING_MODE;
  if (rxPolIdx && stuffingMode) stuffingMode = 3 - stuffingMode;
#endif
}
uint8_t wireStuffingMode() {
  return rxPolIdx && stuffingMode ? 3 - stuffingMode : stuffingMode;
}
uint8_t wireFlagByte() {
  return rxFlagTab[rxFlagIdx] ^ (rxPolIdx ? 0xFF : 0);
}
#endif
void putStuffedByte(uint8_t v, uint8_t *zeroRun) {
  for (int8_t i = 7; i >= 0; i--) {
    if (stuffingMode && *zeroRun == 5) {
      putBit(stuffingMode == 1 ? 0 : 1); *zeroRun = 0;
    }
    uint8_t b = (v >> i) & 1;
    putBit(b);
    if (stuffingMode)
      *zeroRun = (stuffingMode == 1 ? b : !b) ? *zeroRun + 1 : 0;
  }
}

// A closing flag is outside the stuffed data stream, but a terminal run of
// five counted bits must still be terminated before that flag begins. Without
// this bit, the first one of the closing flag is consumed as the supposed
// stuff bit and the receiver sees a malformed frame.
void finishStuffing(uint8_t *zeroRun) {
  if (stuffingMode && *zeroRun == 5) {
    putBit(stuffingMode == 1 ? 0 : 1);
    *zeroRun = 0;
  }
}

void putClosingFlag(uint8_t *zeroRun) {
  finishStuffing(zeroRun);
  putFlag();
}

// Append an independently selected raw closing marker after stuffed data.
// This delimiter is outside the stuffed data region.
void putClosingByte(uint8_t value, uint8_t *zeroRun) {
  finishStuffing(zeroRun);
  for (int8_t i = 7; i >= 0; i--) putBit((value >> i) & 1);
}

#if LADDER_TEST
// ------------------------------------------------- completeness ladder ----
const uint8_t  LD_N_STIM  = 6;
const uint8_t  LD_N_START = 3;
const uint16_t ldStartTab[LD_N_START] = { 1000, 2000, 3000 };

const char *ldStimName(uint8_t k) {
  switch (k) {
    case 0: return "silent (control)";
    case 1: return "flag+addr                 short, open";
    case 2: return "flag+addr+FLAG            short, closed";
    case 3: return "flag+addr+body            long,  open";
    case 4: return "flag+addr+body+FLAG       long,  closed";
    default: return "flag+addr+body+FCS+FLAG   long,  closed+fcs";
  }
}
#endif

#if FREERUN_TEST
// -------------------------------------------- free-running clock: config ---
const uint8_t  FR_N_STIM  = 6;
const uint8_t  FR_N_START = 3;
const uint16_t frStartTab[FR_N_START] = { 2000, 5000, 8000 };
const uint8_t  FREE_ADDR[3] = { 0x03, 0x00, 0x1F };

const char *frStimName(uint8_t k) {
  switch (k) {
    case 0: return "free clock, no data";
    case 1: return "free clock + framed 03h";
    case 2: return "free clock + framed 00h";
    case 3: return "free clock + framed 1Fh";
    case 4: return "clock GATED OFF, burst framed 03h";
    default: return "silent (control)";
  }
}
#endif

// ------------------------------------------------------- the pulse test ---
// Duration is held constant so the length confound that wrecked the conn7
// content correlation cannot come back: only the start time moves.
const unsigned long PULSE_US = 2000;
#if ADDR_SWEEP
// One stimulus per address, all with the DC preamble and unswapped emitters --
// conn10 settled both of those, so they are held fixed to spend the budget on
// addresses instead.
const uint8_t  ADDR_LO = 0x00, ADDR_HI = 0x3F;      // inclusive
const uint8_t  EXTRA_ADDR[] = { 0x7F, 0xFF };       // out-of-range controls
const uint8_t  N_SWEPT = ADDR_HI - ADDR_LO + 1;
const uint8_t  N_EXTRA = sizeof(EXTRA_ADDR);
const uint8_t  N_FIXED = 1;                         // stimulus 0 = silent
const uint8_t  N_STIM  = N_FIXED + N_SWEPT + N_EXTRA;
const unsigned long PRE_US = 1000;

// start time barely matters between 1 and 9 ms (conn10: flat at ~67%, zero at
// 11 ms), so three points across the plateau are enough to catch an
// address-specific timing interaction without spending the run on it
const uint8_t  N_START = 3;
const uint16_t startUsTab[N_START] = { 2000, 5000, 8000 };

inline bool    stimFramed(uint8_t k) { return k >= N_FIXED; }
inline uint8_t stimAddr(uint8_t k) {
  uint8_t i = k - N_FIXED;
  return (i < N_SWEPT) ? (uint8_t)(ADDR_LO + i) : EXTRA_ADDR[i - N_SWEPT];
}
inline bool    stimHasPre(uint8_t k) { (void)k; return true; }
inline bool    stimSwap(uint8_t k)   { (void)k; return false; }
#else
// Framed variants, one row each, so the search is edited here and nowhere
// else.  `addr` is the byte after the flag -- what a reply should carry there
// is unknown.  `pre` prepends a DC preamble.  `swap` sends our clock on the
// data emitter and vice versa: conn9 showed steady light on the data emitter
// alone reproduces the whole effect while the clock emitter alone does
// nothing, so the frames may never have carried a clock the handheld could
// see.  Comparing swap=0 against swap=1 says whether the reaction follows the
// physical emitter or the signal it carries.
struct FramedVariant { uint8_t addr; bool pre; bool swap; };
const FramedVariant FRAMED[] = {
  { 0x03, false, false }, { 0x03, true,  false },   // conn9's best performer,
  { 0x03, false, true  }, { 0x03, true,  true  },   //   all four combinations
  { 0x00, true,  false }, { 0x00, true,  true  },
  { 0x1F, true,  false }, { 0x1F, true,  true  },
  { 0xFF, true,  false }, { 0xFF, true,  true  },   // FFh+DC was oddly null
};
const uint8_t N_FRAMED = sizeof(FRAMED) / sizeof(FRAMED[0]);
const uint8_t N_FIXED = 5;                       // stimuli 0-4 are not framed
const uint8_t N_STIM  = N_FIXED + N_FRAMED;
const unsigned long PRE_US = 1000;               // DC preamble length

const uint8_t  N_START = 12;
// finer near the front: that is where a 10 ms frame has to start if it is to
// finish inside the responsive window at all
const uint16_t startUsTab[N_START] =
    { 500, 1000, 1500, 2000, 2500, 3000, 4000, 5000, 6000, 7000, 9000, 11000 };

inline bool    stimFramed(uint8_t k) { return k >= N_FIXED; }
inline uint8_t stimAddr(uint8_t k)   { return FRAMED[k - N_FIXED].addr; }
inline bool    stimHasPre(uint8_t k) { return FRAMED[k - N_FIXED].pre; }
inline bool    stimSwap(uint8_t k)   { return FRAMED[k - N_FIXED].swap; }
#endif
uint8_t pulseStim = 0, pulseStart = 0;

const char *stimName(uint8_t k) {
#if ADDR_SWEEP
  return (k == 0) ? "silent (control)" : "DC + framed";
#else
  switch (k) {
    case 0: return "silent (control)";
    case 1: return "steady, both";
    case 2: return "steady, clock only";
    case 3: return "steady, data only";
    case 4: return "modulated in-phase (null control)";
    default: return stimHasPre(k) ? "DC + framed" : "framed";
  }
#endif
}

// ----------------------------------------------------------- the sweep ----
// Reply content variants.  0 = flag only ... see contentName().
const uint8_t N_CONTENT = 8;
const uint8_t N_DELAY   = 10;
const uint16_t delayUs[N_DELAY] = {
  500, 1000, 2000, 4000, 8000, 12000, 18000, 26000, 40000, 60000 };
// Reply delay is measured from the handheld burst END.  The handheld holds
// LINK_CTRL 6/7 clear for its ~10-12 ms transmit transaction (bit6 wait 9.92 ms
// at ROM00:32F0, 620 x 59 T on a 3.6864 MHz Z80) and raises them after, so a
// reply must land after that window: delays above ~10 ms are the safe ones.
// (The stock rx hook showed the receiver does accept a reply; the free-run
// test tripped it, but only the handheld-paced reply makes the pattern
// unambiguous.)  Below ~450 us is unreachable anyway: GAP_US is how the burst
// end is detected.

const uint8_t PREAMBLE_CELLS = 16;   // clock-only cells before and after the
                                     // frame in modes 2 and 3, so a receiver
                                     // that needs a running clock to lock has
                                     // one before the flag arrives

const char *contentName(uint8_t c) {
  switch (c) {
    case 0: return "flag only";
    case 1: return "flag+03h echo";
    case 2: return "flag+1Fh (LinkProbe id)";
    case 3: return "flag+00h";
    case 4: return "flag+7Fh";
    case 5: return "flag+frame+flag";
    case 6: return "flag+03h+frame+flag";
    case 7: return "type-2 control ack";
    case 9: return "00 00 FF FF 96 run probe";
    default: return "flag x4 (fill)";
  }
}

// A minimal type-2 control acknowledgement, the shortest thing the receive
// path can accept: [u16 length][u8 type=2][u8 seq][u8 id][u8 spare][payload].
// LinkBlockRx rejects frames under six bytes, frames whose embedded length
// differs from the byte count, and frames whose byte +4 is not the active link
// id -- so a one-byte reply can never be valid however well it is framed.
// 43h is (prelude & 1Fh) | 40h, which is what micronic.peer reconstructs.
const uint8_t ACK_FRAME[] = { 0x07, 0x00, 0x02, 0x00, 0x43, 0x00, 0x00 };
uint8_t replyContent = 0;
uint8_t replyPayload[10];
uint8_t replyPayloadLen = 0;

void recordReplyPayload(uint8_t content, const uint8_t *payload, uint8_t len) {
  replyContent = content;
  replyPayloadLen = (len <= sizeof(replyPayload)) ? len : sizeof(replyPayload);
  for (uint8_t i = 0; i < replyPayloadLen; i++) replyPayload[i] = payload[i];
}

void printReplyPayload() {
  Serial.print(F(" wire_content=")); Serial.print(replyContent);
  Serial.print(F(" payload="));
  if (!replyPayloadLen) Serial.print('-');
  for (uint8_t i = 0; i < replyPayloadLen; i++) {
    if (replyPayload[i] < 0x10) Serial.print('0');
    Serial.print(replyPayload[i], HEX);
  }
}

#if LADDER_TEST
// One builder for the whole ladder, so every rung shares the same flag, the
// same stuffing state and the same phasing -- only completeness changes.
void buildLadder(uint8_t k) {
  frameLen = 0; uint8_t zr = 0;
  putFlag();
  putStuffedByte(0x03, &zr);                       // the address
  if (k >= 3) for (uint8_t i = 0; i < sizeof(ACK_FRAME); i++)
                putStuffedByte(ACK_FRAME[i], &zr); // a legal 7-byte type-2 body
  if (k == 5) { putStuffedByte(0x00, &zr); putStuffedByte(0x00, &zr); }  // FCS slot
  if (k == 2 || k >= 4) putClosingFlag(&zr);       // closing flag, unstuffed
}
#endif

// flag + one address byte, stuffed, at the protocol's phase
void buildFramed(uint8_t addr) {
  frameLen = 0; uint8_t zr = 0;
  recordReplyPayload(0xFF, &addr, 1);
  putFlag(); putStuffedByte(addr, &zr);
}

void putFrame(uint8_t *zeroRun) {
  for (uint8_t i = 0; i < sizeof(ACK_FRAME); i++) putStuffedByte(ACK_FRAME[i], zeroRun);
}

void buildReply(uint8_t content) {
  frameLen = 0;
  uint8_t zeroRun = 0;
  replyContent = content;
  replyPayloadLen = 0;
#if (FREE_TX || RX_NARROW || RX_SWEEP) && STOCK_PREFIX_BYTE >= 0
  if (content == 7) {
    for (int8_t i = 7; i >= 0; --i)
      putBit((STOCK_PREFIX_BYTE >> i) & 1);
  }
#endif
  switch (content) {
    case 0: putFlag(); break;
    case 1: { const uint8_t p[] = { 0x03 };
      recordReplyPayload(content, p, sizeof(p));
      putFlag(); putStuffedByte(0x03, &zeroRun); break; }
    case 2: { const uint8_t p[] = { 0x1F };
      recordReplyPayload(content, p, sizeof(p));
      putFlag(); putStuffedByte(0x1F, &zeroRun); break; }
    case 3: { const uint8_t p[] = { 0x00 };
      recordReplyPayload(content, p, sizeof(p));
      putFlag(); putStuffedByte(0x00, &zeroRun); break; }
    case 4: { const uint8_t p[] = { 0x7F };
      recordReplyPayload(content, p, sizeof(p));
      putFlag(); putStuffedByte(0x7F, &zeroRun); break; }
    case 5: recordReplyPayload(content, ACK_FRAME, sizeof(ACK_FRAME));
      putFlag(); putFrame(&zeroRun); putClosingFlag(&zeroRun); break;
    case 6: replyPayloadLen = sizeof(ACK_FRAME) + 1;
      replyPayload[0] = 0x03;
      for (uint8_t i = 0; i < sizeof(ACK_FRAME); i++) replyPayload[i + 1] = ACK_FRAME[i];
      putFlag(); putStuffedByte(0x03, &zeroRun); putFrame(&zeroRun);
      putClosingFlag(&zeroRun); break;
    case 7: {                                  // type-2 control ack (handshake)
#if STOCK_ZERO_PAYLOAD
      static const uint8_t zeroPayload[10] = {};
      recordReplyPayload(content, zeroPayload, sizeof(zeroPayload));
      putFlag();
      for (uint8_t i = 0; i < sizeof(zeroPayload); i++)
        putStuffedByte(zeroPayload[i], &zeroRun);
#else
      static const uint8_t ack[10] = {
        (STOCK_PAYLOAD00_TO80 ? 0x80 : 0x00), (STOCK_PAYLOAD07_TO06 ? 0x06 : 0x07), 0x00, 0x02, RX_ACK_SEQ, RX_ACK_ID, 0x00, 0x00, 0x02, RX_ACK_SEQ };
      recordReplyPayload(content, ack, sizeof(ack));
      putFlag();
      for (uint8_t i = 0; i < sizeof(ack); i++) putStuffedByte(ack[i], &zeroRun);
#endif
      break;
    }
    case 9: { const uint8_t p[] = { 0x00, 0x00, 0xFF, 0xFF, 0x96 };
      recordReplyPayload(content, p, sizeof(p));
      putFlag();
      for (uint8_t i = 0; i < sizeof(p); i++) putStuffedByte(p[i], &zeroRun);
      break;
    }
    default: for (uint8_t i = 0; i < 4; i++) putFlag(); break;
  }
#if (FREE_TX || RX_NARROW || RX_SWEEP) && STOCK_CLOSE_FLAG
  if (content <= 4 || content == 7 || content == 9)
    putClosingFlag(&zeroRun);
#endif
#if (FREE_TX || RX_NARROW || RX_SWEEP) && STOCK_CLOSE_BYTE >= 0
  if (content <= 4 || content == 7 || content == 9)
    putClosingByte((uint8_t)STOCK_CLOSE_BYTE, &zeroRun);
#endif
}

// Clock modes.  The first version of this axis wasted itself: "data only" has
// no clock for a synchronous receiver to sample on, "clock only" is an
// all-zeros bit stream that can never contain a flag, and mode 3 was an
// accidental duplicate of mode 0 -- so a 500-burst run tested exactly one
// clock behaviour.  These four are all distinct and all plausible:
//   0  frame alone, started whenever the burst-end timer expires
//   1  frame alone, phase-locked to the handheld's own cell grid
//   2  frame wrapped in clock-only preamble and postamble
//   3  both: phase-locked and wrapped
uint8_t sweepContent = 1, sweepDelay = 0, sweepClock = 0, sweepInvert = 0;
uint8_t sweepSwap = 0;   // 1 exchanges physical D5/D6; receiver roles unconfirmed
unsigned long achievedUs = 0;   // reply delay actually achieved, us
uint8_t stockReplyDelayIndex = 0;
uint8_t stockReplyBurstIndex = 0;
bool stockReplySent = false;
uint32_t stockReplyDelayUs() {
  return (uint32_t)STOCK_REPLY_DELAY_US +
      (uint32_t)stockReplyDelayIndex * STOCK_REPLY_DELAY_STEP_US;
}
bool stockReplyDue(uint8_t observedCells) {
  // The handheld's normal retries have 17/22 cells. Ignore the 1/2-cell
  // fragments observed ahead of some retries so they cannot shift a sparse
  // cadence or trigger a reply of their own.
  if (observedCells < 9) return false;
  bool due = stockReplyBurstIndex == 0;
  if (++stockReplyBurstIndex >= STOCK_REPLY_EVERY_N)
    stockReplyBurstIndex = 0;
  return due;
}
int8_t  txPhaseEighths = -2;    // data-rise minus clock-rise, in 1/8 cells
                                // (-2 is the nominal 30 us data lead)

void advanceSweep() {
#if STOCK_FIXED_CANDIDATE && (FREE_TX || RX_NARROW)
#if RX_NARROW && STOCK_REPLY_DELAY_COUNT > 1
  if (++stockReplyDelayIndex >= STOCK_REPLY_DELAY_COUNT)
    stockReplyDelayIndex = 0;
#endif
  return;
#endif
#if LADDER_TEST
  if (++pulseStim < LD_N_STIM) return;
  pulseStim = 0;
  if (++pulseStart < LD_N_START) return;
  pulseStart = 0;
  return;
#elif FREERUN_TEST
  if (++pulseStim < FR_N_STIM) return;
  pulseStim = 0;
  if (++pulseStart < FR_N_START) return;
  pulseStart = 0;
  return;
#elif PULSE_TEST
  // stimulus innermost, so the variants are compared within a few hundred ms
  // of each other at the same start time
  if (++pulseStim < N_STIM) return;
  pulseStim = 0;
  if (++pulseStart < N_START) return;
  pulseStart = 0;
  return;
#elif ORIENTATION_TEST
  sweepSwap ^= 1;          // everything else held still
  return;
#elif RX_NARROW
  // Vary exactly one axis; flag fixed to 7E, the others to the trial baseline.
#if RX_NARROW_AXIS == 0
  if (++rxPhaseIdx < RX_N_PHASE) return;
  rxPhaseIdx = 0;
#elif RX_NARROW_AXIS == 1
  rxPolIdx ^= 1;
#elif RX_NARROW_AXIS == 2
  if (++rxContentIdx < RX_N_CONTENT) return;
  rxContentIdx = 0;
#else
  sweepSwap ^= 1;
#endif
  return;
#elif RX_SWEEP || FREE_TX || RX_NARROW
  // One axis per burst; content fastest, then polarity, phase and flag, so a
  // partial connect attempt still visits every content/polarity combination.
  if (++rxContentIdx < RX_N_CONTENT) return;
  rxContentIdx = 0;
  if (++rxPolIdx < RX_N_POL) return;
  rxPolIdx = 0;
  if (++rxPhaseIdx < RX_N_PHASE) return;
  rxPhaseIdx = 0;
  if (++rxFlagIdx < RX_N_FLAG) return;
  rxFlagIdx = 0;
  return;
#else
  // Content advances fastest.  It is the axis with the untested values on it,
  // and one connect attempt is only ~50 bursts -- with delay innermost, a run
  // that ends early never reaches the later contents at all.
  if (++sweepContent < N_CONTENT) return;
  sweepContent = 0;
  if (++sweepDelay < N_DELAY) return;
  sweepDelay = 0;
  if (++sweepClock < 4) return;
  sweepClock = 0;
  if (sweepInvert == 0) { sweepInvert = 1; return; }
  sweepInvert = 0;
  sweepSwap ^= 1;          // outermost: one full pass per orientation
#endif
}

// ------------------------------------------------------------- transmit ---
// Direct port writes and absolute scheduling.  digitalWrite() costs ~4 us on
// an AVR, which against a 31 us sub-interval is not slop we can afford, and
// chaining delayMicroseconds() accumulates that error across the frame.  Every
// edge is instead placed at a fixed offset from the frame's start time.
volatile uint8_t *clkReg, *datReg;
uint8_t clkMask, datMask;
uint8_t txClockLevelInvert = 0, txDataLevelInvert = 0;

// Swap selects the physical pin; inversion changes its driven level.
inline void drivePin(volatile uint8_t *reg, uint8_t mask, bool high) {
  if (high) *reg |= mask; else *reg &= (uint8_t)~mask;
#ifdef IR_HOST_TEST
  uint8_t pin = (mask == clkMask ? 5 : 6);
  bool outputHigh = (*reg & mask) != 0;
  extern void irHostGpio(uint8_t, bool);
  irHostGpio(pin, outputHigh);
#endif
}
inline void clkLevel(bool high) {
  drivePin(sweepSwap ? datReg : clkReg, sweepSwap ? datMask : clkMask,
           high ^ (txClockLevelInvert != 0));
}
inline void datLevel(bool high) {
  drivePin(sweepSwap ? clkReg : datReg, sweepSwap ? clkMask : datMask,
           high ^ (txDataLevelInvert != 0));
}
inline void clkHigh() { clkLevel(true); }
inline void clkLow()  { clkLevel(false); }
inline void datHigh() { datLevel(true); }
inline void datLow()  { datLevel(false); }
inline void txPhysicalDark() { drivePin(clkReg, clkMask, false); drivePin(datReg, datMask, false); }

inline int32_t txTimeDiff(uint32_t a, uint32_t b) {
  return (int32_t)(a - b);
}

inline void waitUntil(uint32_t t) {
  while (txTimeDiff((uint32_t)micros(), t) < 0) ;
}

struct TxEvent {
  uint32_t at;
  uint8_t type;                 // 0=data rise, 1=clock rise,
                                // 2=clock fall, 3=data fall
};

// Keep this declaration below the struct: the Arduino prototype generator
// otherwise emits txEventBefore before it has seen TxEvent.
inline bool txEventBefore(const TxEvent &a, const TxEvent &b);

// The event queue is deliberately small.  At most the tail of one cell and
// the head of the next can overlap: the largest phase tested puts a data fall
// 167 us after the cell origin, while the next cell's earliest data rise is
// 91 us after that origin.  The queue is filled lazily so events are executed
// in timestamp order without storing a whole frame in AVR RAM.
TxEvent txEvents[8];
uint8_t txEventCount = 0;
uint32_t txMaxLatenessUs = 0;
uint32_t txAppliedMaxLatenessUs = 0;  // post-write software upper bound

inline uint32_t txEventTime(uint32_t cell, int32_t offset) {
  return cell + (uint32_t)offset;
}

void addTxCellEvents(uint32_t cell, uint8_t cellIndex, uint8_t pre,
                     uint8_t post, int32_t phaseUs) {
  (void)post;
  bool inFrame = (cellIndex >= pre) && (cellIndex < pre + frameLen);
  bool wantData = inFrame && (frameBits[cellIndex - pre] ^ sweepInvert);
  int32_t clockRise = (int32_t)DATA_LEAD_US;
  int32_t dataRise = clockRise + phaseUs;
  int32_t dataFall = dataRise + (int32_t)DATA_HIGH_US;

  // Keep insertion order meaningful for equal timestamps: data is presented
  // before a simultaneous clock sample, and a falling edge is then applied.
  if (wantData) txEvents[txEventCount++] = {txEventTime(cell, dataRise), 0};
  txEvents[txEventCount++] = {txEventTime(cell, clockRise), 1};
  txEvents[txEventCount++] = {txEventTime(cell, clockRise + CLK_HIGH_US), 2};
  // Drive the data line low in every cell.  For a zero bit this is redundant,
  // but it makes the inter-cell state explicit and prevents a delayed data
  // fall from being lost when phases are swept.
  txEvents[txEventCount++] = {txEventTime(cell, dataFall), 3};
}

inline bool txEventBefore(const TxEvent &a, const TxEvent &b) {
  if (txTimeDiff(a.at, b.at) != 0) return txTimeDiff(a.at, b.at) < 0;
  return a.type < b.type;
}

inline int32_t txMinEventOffset(int32_t phaseUs) {
  // The first event is whichever rise comes first.  This bound is exact for
  // both phase polarities and lets the lazy queue handle adjacent cells.
  int32_t dataRise = (int32_t)DATA_LEAD_US + phaseUs;
  return dataRise < (int32_t)DATA_LEAD_US ? dataRise : (int32_t)DATA_LEAD_US;
}

// Feedback state machine uses this to dispatch the emitter before its first
// physical edge, leaving time for setup without shortening the first pulse.
uint32_t txFirstEventTime(uint32_t startUs, uint8_t pre) {
  if (pre) return txEventTime(startUs, (int32_t)DATA_LEAD_US);
  int32_t first = (int32_t)DATA_LEAD_US;
  if (frameLen && (frameBits[0] ^ sweepInvert)) {
    int32_t dataRise = first +
                       (int32_t)txPhaseEighths * (int32_t)CELL_US / 8;
    if (dataRise < first) first = dataRise;
  }
  return txEventTime(startUs, first);
}

uint32_t waitUntilMeasured(uint32_t t) {
  uint32_t now;
  do now = (uint32_t)micros();
  while (txTimeDiff(now, t) < 0);
  int32_t late = txTimeDiff(now, t);
  if (late > (int32_t)txMaxLatenessUs) txMaxLatenessUs = (uint32_t)late;
  return now;
}

void applyTxEvent(uint8_t type, uint32_t at, uint32_t actual) {
#if !LOOPBACK_TEST
  // Arm crosstalk masking at the first actual edge, after queue setup and
  // deadline waiting.  Masking during the requested reply delay loses RX.
  txActive = true;
#endif
#ifdef IR_HOST_TEST
  extern void irHostEvent(uint32_t, uint32_t, uint8_t);
  irHostEvent(at, actual, type);
#endif
  if (type == 0) datHigh();
  else if (type == 1) clkHigh();
  else if (type == 2) clkLow();
  else datLow();
  // Includes the GPIO write and micros() read. An ISR after the write can
  // inflate it; a scope is still needed for physical edge timing.
  int32_t appliedLate = txTimeDiff((uint32_t)micros(), at);
  if (appliedLate > (int32_t)txAppliedMaxLatenessUs)
    txAppliedMaxLatenessUs = (uint32_t)appliedLate;
}

inline void dispatchTxEvent(uint32_t cell, int32_t offset, uint8_t type) {
  uint32_t deadline = txEventTime(cell, offset);
  uint32_t actual = waitUntilMeasured(deadline);
  applyTxEvent(type, deadline, actual);
}

// When all four edges fit inside their cell, no adjacent-cell sorting is
// needed.  Dispatch in time order so a 16 MHz AVR does no queue scans between
// edges 15-30 us apart.  The feedback trial's phase=-2 uses this path.
void emitSimpleCells(uint32_t startUs, uint8_t pre, uint8_t total,
                     int32_t phaseUs) {
  int32_t dataRise = (int32_t)DATA_LEAD_US + phaseUs;
  int32_t dataFall = dataRise + (int32_t)DATA_HIGH_US;
  int32_t clockFall = (int32_t)DATA_LEAD_US + (int32_t)CLK_HIGH_US;
  bool dataFallsFirst = dataFall < clockFall;
  for (uint8_t index = 0; index < total; index++) {
    uint32_t cell = startUs + (uint32_t)index * (uint32_t)CELL_US;
    bool wantData = index >= pre && index < pre + frameLen &&
                    (frameBits[index - pre] ^ sweepInvert);
    if (wantData) dispatchTxEvent(cell, dataRise, 0);
    dispatchTxEvent(cell, (int32_t)DATA_LEAD_US, 1);
    if (dataFallsFirst) {
      dispatchTxEvent(cell, dataFall, 3);
      dispatchTxEvent(cell, clockFall, 2);
    } else {
      dispatchTxEvent(cell, clockFall, 2);
      dispatchTxEvent(cell, dataFall, 3);
    }
  }
}

// Fast path when each data fall lands before the next cell's clock rise.
// The generic event queue meets chronology but is too expensive on a 16 MHz
// Uno for a full +2/8-cell frame: its work accumulates hundreds of us of
// lateness. Schedule the previous cell's fall first in the next cell.
void emitEarlyCrossCellFall(uint32_t startUs, uint8_t pre, uint8_t total,
                            int32_t dataRise, int32_t dataFall) {
  const int32_t tail = dataFall - (int32_t)CELL_US;
  for (uint8_t index = 0; index < total; index++) {
    uint32_t cell = startUs + (uint32_t)index * (uint32_t)CELL_US;
    bool wantData = index >= pre && index < pre + frameLen &&
                    (frameBits[index - pre] ^ sweepInvert);
    if (index) dispatchTxEvent(cell, tail, 3);
    dispatchTxEvent(cell, (int32_t)DATA_LEAD_US, 1);
    if (wantData) dispatchTxEvent(cell, dataRise, 0);
    dispatchTxEvent(cell, (int32_t)(DATA_LEAD_US + CLK_HIGH_US), 2);
  }
  if (total) {
    uint32_t after = startUs + (uint32_t)total * (uint32_t)CELL_US;
    dispatchTxEvent(after, tail, 3);
  }
}

// The bit-cell emitter, shared by framed replies and pulse tests.  The phase
// setting is absolute: txPhaseEighths is data-rise minus clock-rise, in eighths
// of a cell.  A negative value therefore gives data setup before sampling.
void emitCells(uint32_t startUs, uint8_t pre, uint8_t post) {
  uint8_t total = pre + frameLen + post;
  int32_t phaseUs = (int32_t)txPhaseEighths * (int32_t)CELL_US / 8;
  uint8_t nextCell = 0;
  txEventCount = 0;
  txMaxLatenessUs = 0;
  txAppliedMaxLatenessUs = 0;

  // Establish the complemented baseline before the first scheduled edge.
  // With no lead cells and a negative data phase, that edge can precede
  // startUs; 16 us of setup avoids making the edge late.
  if (txClockLevelInvert || txDataLevelInvert) {
    uint32_t first = txFirstEventTime(startUs, pre);
    uint32_t baselineAt = txTimeDiff(first, startUs) < 0 ? first - 16U : startUs;
    waitUntil(baselineAt);
    datLow(); clkLow();
  }

  int32_t dataRise = (int32_t)DATA_LEAD_US + phaseUs;
  int32_t dataFall = dataRise + (int32_t)DATA_HIGH_US;
  if (dataRise >= 0 && dataRise <= (int32_t)DATA_LEAD_US &&
      dataFall < (int32_t)CELL_US &&
      DATA_LEAD_US + CLK_HIGH_US < CELL_US) {
    emitSimpleCells(startUs, pre, total, phaseUs);
    waitUntil(startUs + (uint32_t)total * (uint32_t)CELL_US);
    txPhysicalDark();
    return;
  }
  if (dataRise > (int32_t)DATA_LEAD_US &&
      dataRise < (int32_t)(DATA_LEAD_US + CLK_HIGH_US) &&
      dataFall >= (int32_t)CELL_US &&
      dataFall - (int32_t)CELL_US < (int32_t)DATA_LEAD_US &&
      DATA_LEAD_US + CLK_HIGH_US < CELL_US) {
    emitEarlyCrossCellFall(startUs, pre, total, dataRise, dataFall);
    txPhysicalDark();
    return;
  }

  while (txEventCount || nextCell < total) {
    // Add future cells only when their earliest possible edge cannot precede
    // an already queued event.  This is what handles data edges crossing a
    // cell boundary for positive and negative phase values.
    if (nextCell < total) {
      uint32_t cell = startUs + (uint32_t)nextCell * (uint32_t)CELL_US;
      uint32_t earliest = txEventTime(cell, txMinEventOffset(phaseUs));
      uint32_t earliestQueued = 0;
      for (uint8_t i = 0; i < txEventCount; i++) {
        if (i == 0 || txTimeDiff(txEvents[i].at, earliestQueued) < 0)
          earliestQueued = txEvents[i].at;
      }
      if (!txEventCount ||
          txTimeDiff(earliest, earliestQueued) <= 0) {
        addTxCellEvents(cell, nextCell, pre, post, phaseUs);
        nextCell++;
        continue;
      }
    }

    uint8_t best = 0;
    for (uint8_t i = 1; i < txEventCount; i++) {
      if (txEventBefore(txEvents[i], txEvents[best])) best = i;
    }
    TxEvent event = txEvents[best];
    txEvents[best] = txEvents[--txEventCount];
    uint32_t actual = waitUntilMeasured(event.at);
    applyTxEvent(event.type, event.at, actual);
  }
  waitUntil(startUs + (uint32_t)total * (uint32_t)CELL_US);
  txPhysicalDark();
}

// Clock-only lead-in / postamble, Micronic-style.  The handheld's own bursts
// carry 4-5 clock-only cells before the flag (its framer's pipeline flush), so
// a faithful reply should too; set by the RX modes.
uint8_t txPre = 0, txPost = 0;

void sendFrame(unsigned long startUs) {
  // Prepare the emitter before the first deadline.  applyTxEvent masks
  // crosstalk when the first edge is actually driven.
  if (sweepClock >= 2) emitCells(startUs, PREAMBLE_CELLS, PREAMBLE_CELLS);
  else                 emitCells(startUs, txPre, txPost);
#if !LOOPBACK_TEST
  txActive = false;
#endif
  delayMicroseconds(300);          // let any crosstalk settle, while listening
}

#if FEEDBACK_HARNESS
// Half-duplex connector controller. T-trial IR emission is below 24 ms;
// the ROM's 100 ms post-trial cooldown keeps UART reporting outside it.
// V is a separate, bounded camera check with no handheld transaction.
enum FbRunState : uint8_t { FB_IDLE, FB_WAIT_ACK, FB_HOLD, FB_WAIT_START,
                            FB_WAIT_RESULT, FB_VISUAL_RUN, FB_DESYNC };
FeedbackLineParser fbParser;
FeedbackConfig fbConfig = {};
FbRunState fbState = FB_IDLE;
uint32_t fbLastId = 0, fbStateAt = 0, fbHighAt = 0, fbStartAt = 0;
uint32_t fbSerialAt = 0, fbAckAt = 0, fbReleaseAt = 0;
uint32_t fbEmitStart = 0, fbEmitEnd = 0;
uint8_t fbRepeatIndex = 0;
uint32_t fbVisualAt = 0;
uint8_t fbVisualPhase = 0;
uint8_t fbResult[30], fbResultLen = 0;
bool fbReady = false, fbHighTracking = false, fbRequestLow = false;
bool fbEmitPending = false, fbManualLow = false;
bool fbHaveSequence = false;
uint16_t fbExpectedSequence = 0;
bool fbYellowWasHigh = true, fbUartActive = false;
uint8_t fbUartBit = 0, fbUartValue = 0;
uint32_t fbUartNext = 0;

inline bool fbYellowHigh() { return digitalRead(YELLOW_IN) != 0; }
// Direct TTL drives the idle high; the NPN interface releases its collector.
const uint8_t BLACK_IDLE_LEVEL = BLACK_USE_NPN ? 0 : 1;
inline void fbBlackRelease() { digitalWrite(BLACK_OUT, BLACK_IDLE_LEVEL); }
inline void fbBlackLow() { digitalWrite(BLACK_OUT, 1 - BLACK_IDLE_LEVEL); }
void fbPrintWiring() {
#if BLACK_USE_NPN
  Serial.println(F("BLACK: NPN; D7 LOW=idle, HIGH=command"));
#else
  Serial.println(F("BLACK: DIRECT_TTL; D7 HIGH=idle, LOW=command"));
#endif
}
inline uint32_t fbHoldUs() {
  return fbConfig.holdKind == 'W' ? 100000UL :
         fbConfig.holdKind == 'R' ? 300000UL :
         fbConfig.holdKind == 'P' ? 500000UL :
         fbConfig.holdKind == 'H' ? 575000UL :
         fbConfig.holdKind == 'J' ? 625000UL :
         fbConfig.holdKind == 'K' ? 400000UL : 700000UL;
}
inline bool fbElapsed(uint32_t now, uint32_t then, uint32_t us) {
  return (uint32_t)(now - then) >= us;
}
void fbPrintPrefix(const __FlashStringHelper *kind) {
  Serial.print(kind); Serial.print(F(" id=")); Serial.print(fbConfig.trialId);
}
void fbPrintHex(const uint8_t *bytes, uint8_t n) {
  if (!n) Serial.print('-');
  for (uint8_t i = 0; i < n; ++i) {
    if (bytes[i] < 0x10) Serial.print('0');
    Serial.print(bytes[i], HEX);
  }
}
void fbQuiet() {
  analogWrite(CLK_OUT, 0); analogWrite(DAT_OUT, 0);
  txClockLevelInvert = txDataLevelInvert = 0;
  fbBlackRelease(); clkLow(); datLow(); txPhysicalDark(); txActive = false;
  fbEmitPending = false; fbManualLow = false; fbRequestLow = false;
}
void fbVisualStop() {
  fbQuiet();
}
void fbResetUart() {
  fbUartActive = false; fbYellowWasHigh = fbYellowHigh(); fbResultLen = 0;
}
void fbError(const __FlashStringHelper *reason) {
  fbQuiet(); fbReady = false; fbState = FB_DESYNC;
  fbPrintPrefix(F("ERROR")); Serial.print(F(" reason=")); Serial.print(reason);
  Serial.print(F("; send R to resynchronise"));
  if (fbResultLen) { Serial.print(F(" raw=")); fbPrintHex(fbResult, fbResultLen); }
  Serial.println();
}
// Rejecting a command while idle cannot have changed the handheld's ROM
// sequence. Keep the current idle/READY state and trial ID so a corrected
// command can follow. Errors after a transaction starts still need R.
void fbCommandError(const __FlashStringHelper *reason) {
  if (fbState != FB_IDLE || fbManualLow) { fbError(reason); return; }
  fbPrintPrefix(F("ERROR")); Serial.print(F(" reason=")); Serial.print(reason);
  Serial.println(F("; no handheld transaction; no R needed"));
}
void fbBuildStimulus() {
  frameLen = 0;
  uint8_t run = 0;
  if (fbConfig.haveFlag)
    for (int8_t bit = 7; bit >= 0; --bit) putBit((fbConfig.flagByte >> bit) & 1);
  for (uint8_t i = 0; i < fbConfig.payloadLen; ++i) {
    uint8_t byte = fbConfig.payload[i];
    for (int8_t bit = 7; bit >= 0; --bit) {
      uint8_t value = (byte >> bit) & 1;
      if (fbConfig.stuffing && run == 5) {
        putBit(fbConfig.stuffing == 1 ? 0 : 1); run = 0;
      }
      putBit(value);
      if (fbConfig.stuffing)
        run = (fbConfig.stuffing == 1 ? value : !value) ? (uint8_t)(run + 1) : 0;
    }
  }
  // Finish the pending stuffed run at the end of data, even without a flag.
  if (fbConfig.stuffing && run == 5) putBit(fbConfig.stuffing == 1 ? 0 : 1);
  if (fbConfig.closeFlag)
    for (int8_t bit = 7; bit >= 0; --bit) putBit((fbConfig.flagByte >> bit) & 1);
}
bool fbResultValid() {
  if (fbResultLen != 30 || fbResult[0] != 0xA5 || fbResult[1] != 0x5A ||
      (fbResult[2] != 1 && fbResult[2] != 2) || fbResult[6] > 8) return false;
  // v2 modes 5-7 use the former preview area for controller status capture.
  // Keep v1 and v2 modes 1-4 on their original raw-RX validation path.
  if ((fbResult[2] == 1 && fbResult[3] > 4) || fbResult[3] > 7) return false;
  if (fbResult[2] == 2 && fbResult[3] >= 5 && fbResult[17] != 8) return false;
  if (fbResult[3] < 5 && (fbResult[17] > 8 || fbResult[16] != 0 ||
      fbResult[15] > 134 || fbResult[17] > fbResult[15])) return false;
  if (!fbResult[3] && (fbResult[6] < 1 || fbResult[6] > 3)) return false;
  uint8_t sum = 0; for (uint8_t i = 0; i < 30; ++i) sum += fbResult[i];
  return sum == 0;
}
void fbStoreResultByte(uint8_t value) {
  // Hunt for the sync word rather than treating a busy-low break as data.
  if (!fbResultLen && value != 0xA5) return;
  if (fbResultLen == 1 && value != 0x5A) {
    fbResultLen = value == 0xA5 ? 1 : 0; return;
  }
  if (fbResultLen < sizeof(fbResult)) fbResult[fbResultLen++] = value;
  if (fbResultLen != sizeof(fbResult)) return;
  if (!fbResultValid()) { fbError(F("result")); return; }
  uint16_t seq = (uint16_t)fbResult[4] | ((uint16_t)fbResult[5] << 8);
  uint8_t expectedMode = fbConfig.holdKind == 'W' ? 1 :
                        fbConfig.holdKind == 'R' ? 2 : fbConfig.holdKind == 'P' ? 3 :
                        fbConfig.holdKind == 'G' ? 4 : fbConfig.holdKind == 'H' ? 5 :
                        fbConfig.holdKind == 'J' ? 6 : 7;
  if (fbResult[3] && (fbResult[3] != expectedMode || fbState != FB_WAIT_RESULT)) {
    fbError(F("mode")); return;
  }
  if (fbHaveSequence && seq != (fbResult[3] ? fbExpectedSequence : (uint16_t)(fbExpectedSequence - 1))) {
    fbError(F("sequence")); return;
  }
  if (fbResult[3]) { fbExpectedSequence = (uint16_t)(seq + 1); fbHaveSequence = true; }
  fbQuiet();
  fbPrintPrefix(F("RESULT")); Serial.print(F(" rom_seq=")); Serial.print(seq);
  Serial.print(F(" mode=")); Serial.print(fbResult[3]);
  Serial.print(F(" err=")); Serial.print(fbResult[6]);
  Serial.print(F(" ack_us=")); Serial.print(fbAckAt);
  Serial.print(F(" release_us=")); Serial.print(fbReleaseAt);
  Serial.print(F(" start_us=")); Serial.print(fbStartAt);
  Serial.print(F(" emit_start_us=")); Serial.print(fbEmitStart);
  Serial.print(F(" emit_end_us=")); Serial.print(fbEmitEnd);
  Serial.print(F(" emit_late_max=")); Serial.print(txMaxLatenessUs);
  Serial.print(F(" emit_applied_late_max=")); Serial.print(txAppliedMaxLatenessUs);
  Serial.print(F(" raw=")); fbPrintHex(fbResult, sizeof(fbResult)); Serial.println();
  fbState = FB_IDLE; fbReady = false; fbHighTracking = false;
}
// Sample start, eight data bits and stop without blocking. A long busy-low
// interval is ignored before magic; a framing error inside a record fails it.
void fbUartTick(uint32_t now) {
  bool high = fbYellowHigh();
  if (!fbUartActive && fbYellowWasHigh && !high) {
    fbUartActive = true; fbUartBit = 0; fbUartValue = 0; fbUartNext = now + 416;
  }
  if (fbUartActive && txTimeDiff(now, fbUartNext) >= 0) {
    if (txTimeDiff(now, fbUartNext) > 200 ||
        (fbUartBit == 0 && high) || (fbUartBit == 9 && !high)) {
      fbUartActive = false;
      if (fbResultLen) fbError(F("uart_framing"));
    } else if (fbUartBit == 9) {
      fbUartActive = false; fbStoreResultByte(fbUartValue);
    } else {
      if (fbUartBit && high) fbUartValue |= (uint8_t)(1U << (fbUartBit - 1));
      ++fbUartBit; fbUartNext += 833;
    }
  }
  fbYellowWasHigh = high;
}
void fbLogTrial() {
  fbPrintPrefix(F("TRIAL")); Serial.print(F(" mode=")); Serial.print((char)fbConfig.holdKind);
  Serial.print(F(" kind=")); Serial.print(fbConfig.mode == FB_SILENT ? 'S' : 'X');
  Serial.print(F(" swap=")); Serial.print(fbConfig.swapRoles);
  Serial.print(F(" flag=")); if (fbConfig.haveFlag) fbPrintHex(&fbConfig.flagByte, 1); else Serial.print(F("--"));
  Serial.print(F(" stuff=")); Serial.print(fbConfig.stuffing);
  Serial.print(F(" close=")); Serial.print(fbConfig.closeFlag);
  Serial.print(F(" pol=")); Serial.print(fbConfig.polarity);
  Serial.print(F(" clk_inv=")); Serial.print(fbConfig.clockInvert);
  Serial.print(F(" dat_inv=")); Serial.print(fbConfig.dataInvert);
  Serial.print(F(" repeat_count=")); Serial.print(fbConfig.repeatCount);
  Serial.print(F(" repeat_gap_ms=")); Serial.print(fbConfig.repeatGapMs);
  Serial.print(F(" phase=")); Serial.print(fbConfig.phaseEighths);
  Serial.print(F(" lead=")); Serial.print(fbConfig.leadCells);
  Serial.print(F(" delay_us=")); Serial.print(fbConfig.delayUs);
  Serial.print(F(" cell_us=122 order=MSB payload="));
  fbPrintHex(fbConfig.payload, fbConfig.payloadLen); Serial.println();
}
void fbCommandTick() {
  while (Serial.available()) {
    FeedbackConfig parsed = {};
    uint32_t id = 0;
    char ch = (char)Serial.read();
    // Starting any new command cancels an outstanding optical stimulus.
    // Even an incomplete line must not leave an old trial armed.
    if (ch != '\r' && !fbParser.pending() && fbState != FB_IDLE && fbState != FB_DESYNC &&
        !(fbState == FB_VISUAL_RUN && ch == 'C')) {
      fbQuiet(); fbState = FB_DESYNC; fbReady = false;
    }
    FeedbackCommand command = fbParser.feed(ch, &parsed, &id);
    if (fbParser.pending()) fbSerialAt = micros();
    if (command == FB_NONE) continue;
    if (command == FB_RESYNC) {
      fbQuiet(); fbResetUart(); fbHaveSequence = false; fbExpectedSequence = 0;
      fbState = FB_IDLE; fbReady = false; fbHighTracking = false;
      Serial.println(F("SYNC")); fbPrintWiring(); continue;
    }
    if (command == FB_CANCEL) {
      if (fbState == FB_VISUAL_RUN && id == fbConfig.trialId) {
        fbVisualStop(); fbState = FB_IDLE; fbReady = false; fbHighTracking = false;
        Serial.print(F("VISUAL_CANCELLED visual_id=")); Serial.println(id); continue;
      }
      fbCommandError(F("cancel")); continue;
    }
    if (command == FB_BLACK_RELEASE && fbManualLow) {
      fbQuiet(); fbState = FB_DESYNC;
      Serial.println(F("BLACK released; send R to resynchronise")); continue;
    }
    if (command == FB_BLACK_LOW && fbState == FB_IDLE && fbReady && id > fbLastId) {
      fbConfig.trialId = id; fbLastId = id; fbManualLow = true;
      fbReady = false; fbStateAt = micros(); fbBlackLow();
      Serial.println(F("BLACK low (1000 ms maximum)")); continue;
    }
    if (command == FB_VISUAL_TEST && fbState == FB_IDLE && !fbManualLow) {
      fbBlackRelease();
      // Visual IDs identify a run for cancellation/logging; reusing one is
      // allowed because these checks do not consume ROM trial IDs.
      fbConfig.trialId = id; fbReady = false; fbHighTracking = false;
      fbVisualPhase = 0; fbVisualAt = micros(); fbState = FB_VISUAL_RUN;
      analogWrite(CLK_OUT, 26); analogWrite(DAT_OUT, 0);
      Serial.print(F("VISUAL visual_id=")); Serial.print(id);
      Serial.println(F(" trial_id=unchanged channel=A pin=D5 duty=10% duration_ms=1500")); continue;
    }
    if (command != FB_TRIAL || fbState != FB_IDLE || !fbReady || fbManualLow || parsed.trialId <= fbLastId ||
        (parsed.holdKind == 'P' && parsed.mode != FB_SILENT)) { fbCommandError(F("command")); continue; }
    fbConfig = parsed; fbLastId = parsed.trialId;
    fbResetUart(); fbBuildStimulus();
    fbAckAt = fbReleaseAt = fbStartAt = fbEmitStart = fbEmitEnd = 0;
    fbRepeatIndex = 0;
    txMaxLatenessUs = txAppliedMaxLatenessUs = 0;
    fbEmitPending = false; fbRequestLow = false;
    fbLogTrial(); fbState = FB_WAIT_ACK; fbStateAt = micros();
    fbReady = false; fbHighTracking = false;
  }
  if (fbParser.pending() && fbElapsed((uint32_t)micros(), fbSerialAt, 1000000UL)) {
    fbParser.timeout(); fbCommandError(F("serial_timeout"));
    Serial.println(F("Finish timed-out line with Enter before next command"));
  }
}
void feedbackTick() {
  fbCommandTick();
  uint32_t now = micros();
  bool high = fbYellowHigh();
  if (fbState == FB_VISUAL_RUN) {
    if (fbElapsed(now, fbVisualAt, 1500000UL)) {
      if (!fbVisualPhase) {
        analogWrite(CLK_OUT, 0); analogWrite(DAT_OUT, 26);
        fbVisualPhase = 1; fbVisualAt = now;
        Serial.print(F("VISUAL visual_id=")); Serial.print(fbConfig.trialId);
        Serial.println(F(" trial_id=unchanged channel=B pin=D6 duty=10% duration_ms=1500"));
      } else {
        fbVisualStop(); fbState = FB_IDLE; fbReady = false; fbHighTracking = false;
        Serial.print(F("VISUAL_DONE visual_id=")); Serial.println(fbConfig.trialId);
      }
    }
  } else if (fbState == FB_IDLE) {
    if (fbManualLow) {
      if (fbElapsed(now, fbStateAt, 1000000UL)) fbError(F("black_hold"));
      return;
    }
    if (!high) { fbReady = false; fbHighTracking = false; }
    else if (!fbHighTracking) { fbHighAt = now; fbHighTracking = true; }
    else if (!fbReady && fbElapsed(now, fbHighAt, 100000UL)) {
      fbReady = true; Serial.println(F("READY"));
    }
  } else if (fbState == FB_WAIT_ACK) {
    if (!fbRequestLow) {
      if (!high) fbHighTracking = false;
      else if (!fbHighTracking) { fbHighTracking = true; fbHighAt = now; }
      else if (fbElapsed(now, fbHighAt, 100000UL)) {
        fbBlackLow(); fbRequestLow = true; fbStateAt = now;
      }
    } else if (!high) { fbState = FB_HOLD; fbStateAt = fbAckAt = now; }
    if (fbState == FB_WAIT_ACK && fbElapsed(now, fbStateAt, 1500000UL)) fbError(F("ack"));
  } else if (fbState == FB_HOLD) {
    if (high) { fbError(F("ack_lost")); return; }
    if (fbElapsed(now, fbStateAt, fbHoldUs())) {
      fbBlackRelease(); fbState = FB_WAIT_START; fbStateAt = fbReleaseAt = now;
      fbHighTracking = false; fbResetUart();
    }
  } else if (fbState == FB_WAIT_START) {
    if (high) {
      if (!fbHighTracking) { fbHighTracking = true; fbHighAt = now; }
    } else {
      bool start = fbHighTracking && fbElapsed(now, fbHighAt, 40000UL);
      fbHighTracking = false;
      if (start && !fbResultLen) {
        fbStartAt = now; fbState = FB_WAIT_RESULT; fbResetUart();
        fbEmitPending = fbConfig.mode == FB_STIMULUS;
      }
    }
    if (fbState == FB_WAIT_START) {
      fbUartTick(now);
      if (fbState == FB_WAIT_START && fbElapsed(now, fbStateAt, 1000000UL)) fbError(F("start"));
    }
  } else if (fbState == FB_WAIT_RESULT) {
    // Enter the emitter ahead of the first physical edge.  Earlier versions
    // dispatched at the deadline and built the lazy queue afterward, making
    // the first clock late even when the requested delay was otherwise valid.
    // Keep cancellation/serial handling live until this bounded setup window.
    const uint32_t setupAheadUs = 256;
    sweepInvert = fbConfig.polarity; txPhaseEighths = fbConfig.phaseEighths;
    const uint32_t scheduled = fbStartAt + fbConfig.delayUs +
        (uint32_t)fbRepeatIndex * fbConfig.repeatGapMs * 1000UL;
    if (fbEmitPending && txTimeDiff(now, txFirstEventTime(
        scheduled, fbConfig.leadCells) - setupAheadUs) >= 0) {
      // All serial parsing and cancellation remain live during the delay.
      // A maximum frame plus lead takes under 26 ms. No serial prints occur
      // inside sendFrame; its deadline lateness is reported with the result.
      fbEmitPending = false; sweepClock = 0;
      sweepSwap = fbConfig.swapRoles; sweepInvert = fbConfig.polarity;
      txClockLevelInvert = fbConfig.mode == FB_STIMULUS ? fbConfig.clockInvert : 0;
      txDataLevelInvert = fbConfig.mode == FB_STIMULUS ? fbConfig.dataInvert : 0;
      txPhaseEighths = fbConfig.phaseEighths; txPre = fbConfig.leadCells; txPost = 0;
      // Hard end guard: repeated stimuli must finish within 80 ms of START.
      // Keep existing single-burst scheduling behavior unchanged.
      const uint32_t frameUs = (uint32_t)(txPre + frameLen) * 122UL + 100UL;
      const uint32_t repeatDeadline = fbStartAt + 80000UL;
      const bool repeatInWindow = fbConfig.repeatCount == 1 ||
          (txTimeDiff(scheduled + frameUs, repeatDeadline) <= 0 &&
           txTimeDiff(micros() + frameUs, repeatDeadline) <= 0);
      if (repeatInWindow) {
        if (!fbRepeatIndex) fbEmitStart = micros();
        sendFrame(scheduled); fbEmitEnd = micros();
        ++fbRepeatIndex;
        fbEmitPending = fbRepeatIndex < fbConfig.repeatCount;
      } else {
        fbEmitPending = false;
      }
      txClockLevelInvert = txDataLevelInvert = 0;
      fbResetUart();
    }
    fbUartTick((uint32_t)micros());
    if (fbState == FB_WAIT_RESULT && fbElapsed((uint32_t)micros(), fbStartAt, 6000000UL)) fbError(F("result_timeout"));
  }
}
#endif

#if FREERUN_TEST
// ------------------------------------------------- free-running clock ------
// Timer2 CTC, prescaler 1, OCR2A=243 -> an interrupt every 244/16e6 = 15.25 us,
// one eighth of a cell, so the whole 8-phase grid the handheld uses is
// available: clock high over phases 0-3, data rising at phase 6 of the
// previous cell and falling at phase 3 of this one.  122.0 us against a true
// 122.0703 is 0.06% out, about 1 us across a frame.
volatile uint8_t  fPhase = 0;
volatile bool     clkFree = true;      // false = gate the clock off entirely
volatile uint8_t  fBits[64];
volatile uint8_t  fLen = 0, fPos = 0;
volatile bool     fPending = false, fRunning = false;

ISR(TIMER2_COMPA_vect) {
  if (clkFree) {
    if (fPhase == 0)      clkHigh();
    else if (fPhase == 4) clkLow();
  }
  if (fPhase == 3) datLow();
  if (fPhase == 6) {
    if (fPending)      { fPending = false; fPos = 0; fRunning = true; }
    else if (fRunning) { if (++fPos >= fLen) fRunning = false; }
    if (fRunning && fBits[fPos]) datHigh();
  }
  if (++fPhase == 8) fPhase = 0;
}

void freerunBegin() {
  TCCR2A = _BV(WGM21);                 // CTC
  TCCR2B = _BV(CS20);                  // prescaler 1
  OCR2A  = 243;
  TIMSK2 = _BV(OCIE2A);
}

// hand the ISR a frame; it starts on the next cell boundary, so our cells are
// automatically aligned to our own clock grid
void freerunArm() {
  noInterrupts();
  fLen = frameLen;
  for (uint8_t i = 0; i < frameLen && i < sizeof(fBits); i++) fBits[i] = frameBits[i];
  fPending = true;
  interrupts();
}

#endif


#if PULSE_TEST
void steadyFor(unsigned long from, unsigned long len, bool useClk, bool useDat) {
  waitUntil(from);
  if (useClk) clkHigh();
  if (useDat) datHigh();
  waitUntil(from + len);
  clkLow(); datLow();
}

void sendPulse(unsigned long startUs, uint8_t stim) {
  txMaxLatenessUs = 0;
  txAppliedMaxLatenessUs = 0;
  if (stim == 0) return;                       // the control: emit nothing
  // Non-framed stimuli must drive the pins they name, so the emitter swap is
  // only ever applied to a framed variant that asks for it.
  sweepSwap = stimFramed(stim) && stimSwap(stim);
  bool preparedFrame = false;
  if (stimFramed(stim) && !stimHasPre(stim)) {
    buildFramed(stimAddr(stim));
    preparedFrame = true;
  }
  uint32_t maskAt = (uint32_t)startUs;
  if (stimFramed(stim) && !stimHasPre(stim))
    maskAt = txFirstEventTime((uint32_t)startUs, 0);
  waitUntil(maskAt);
  txActive = true;
#if ADDR_SWEEP
  if (false) { }                               // every non-zero stimulus is framed
#else
  if (stim <= 3) {                             // steady DC, both / clk / data
    steadyFor(startUs, PULSE_US, stim != 3, stim != 2);
  } else if (stim == 4) {                      // in-phase modulation: the null
    uint8_t n = PULSE_US / CELL_US;
    for (uint8_t i = 0; i < n; i++) {
      unsigned long cell = startUs + (unsigned long)i * CELL_US;
      waitUntil(cell);                clkHigh(); datHigh();
      waitUntil(cell + CLK_HIGH_US);  clkLow();  datLow();
    }
  }
#endif
  else {
    // "light detected, then it expects data": optionally hold DC to trip
    // whatever the detection is, then hand it a correctly phased frame with
    // no gap between the two.
    unsigned long pre = stimHasPre(stim) ? PRE_US : 0;
    if (pre) steadyFor(startUs, pre, true, true);
    if (!preparedFrame) buildFramed(stimAddr(stim));
    emitCells(startUs + pre, 0, 0);
  }
  clkLow(); datLow();
  txActive = false;
  delayMicroseconds(300);
}
#endif

#if LOOPBACK_TEST
void loopbackTick() {
  static unsigned long nextTx = 0;
  if ((long)(micros() - nextTx) < 0) return;
  nextTx = micros() + 500000UL;
  buildReply(sweepContent);
  sendFrame(micros() + 1000);
}
#endif

#if FREE_TX
// Transmit one swept burst every FREE_TX_PERIOD_MS, independent of the
// handheld: the idle receiver is what the stock receive hook is watching.
void freeTxTick() {
  static unsigned long nextTx = 0;
  unsigned long now = micros();
  if ((long)(now - nextTx) < 0) return;
  nextTx = now + (unsigned long)FREE_TX_PERIOD_MS * 1000UL;
  sweepInvert = rxPolIdx;                       // data polarity axis
  txPhaseEighths = rxPhaseTab[rxPhaseIdx];      // data-to-clock phase axis
  selectStockStuffing();
  buildReply(rxContentMap[rxContentIdx]);       // content axis (flag via putFlag)
  sendFrame(now + 1000);
  Serial.print(F("# TX flag=")); Serial.print(rxFlagTab[rxFlagIdx], HEX);
  Serial.print(F(" wire_flag=")); Serial.print(wireFlagByte(), HEX);
  Serial.print(F(" phase(data-clock)=")); Serial.print(rxPhaseTab[rxPhaseIdx]);
  Serial.print(F("/8cell pol=")); Serial.print(rxPolIdx);
  Serial.print(F(" content_idx=")); Serial.print(rxContentIdx);
  Serial.print(F(" stuff_cfg=")); Serial.print(STOCK_STUFFING_MODE);
  Serial.print(F(" wire_stuff=")); Serial.print(wireStuffingMode());
  Serial.print(F(" close=")); Serial.print(STOCK_CLOSE_FLAG);
  printReplyPayload();
  Serial.print(F(" tx_start_us=")); Serial.print(now + 1000UL);
  Serial.print(F(" swap=")); Serial.print(sweepSwap);
  Serial.print(F(" fixed=")); Serial.print(STOCK_FIXED_CANDIDATE);
  Serial.print(F(" clk_inv=")); Serial.print(txClockLevelInvert);
  Serial.print(F(" dat_inv=")); Serial.print(txDataLevelInvert);
  Serial.print(F(" emit_late_max=")); Serial.print(txMaxLatenessUs);
  Serial.print(F(" emit_applied_late_max=")); Serial.print(txAppliedMaxLatenessUs);
  Serial.println();
  advanceSweep();
}
#endif

// -------------------------------------------------------------- reports ---
void report(uint8_t n, const uint8_t *bits) {
  Serial.print(F("burst "));
  Serial.print(n);
  Serial.print(F(" cells  "));
  for (uint8_t i = 0; i < n; i++) Serial.write(bits[i] ? '1' : '0');
#if FREERUN_TEST || PULSE_TEST
  Serial.print(F("  [stim=")); Serial.print(stimName(pulseStim));
#if !FREERUN_TEST
  if (stimFramed(pulseStim)) {
    Serial.print(F(" addr=")); Serial.print(stimAddr(pulseStim));
    Serial.print(F(" pre=")); Serial.print(stimHasPre(pulseStim));
    Serial.print(F(" swap=")); Serial.print(stimSwap(pulseStim));
  }
#endif
  Serial.print(F(" start=")); Serial.print(startUsTab[pulseStart]);
  Serial.print(F("/")); Serial.print(achievedUs);
  Serial.print(F("us dur=")); Serial.print(PULSE_US);
  Serial.print(F("us emit_late_max=")); Serial.print(txMaxLatenessUs);
  Serial.print(F(" emit_applied_late_max=")); Serial.print(txAppliedMaxLatenessUs);
#elif RX_SWEEP || RX_NARROW
  Serial.print(F("  [flag=")); Serial.print(rxFlagTab[rxFlagIdx], HEX);
  Serial.print(F(" wire_flag=")); Serial.print(wireFlagByte(), HEX);
  Serial.print(F(" phase(data-clock)=")); Serial.print(rxPhaseTab[rxPhaseIdx]);
  Serial.print(F("/8cell pol=")); Serial.print(rxPolIdx);
  Serial.print(F(" content_idx=")); Serial.print(rxContentIdx);
  Serial.print(F(" stuff_cfg=")); Serial.print(STOCK_STUFFING_MODE);
  Serial.print(F(" wire_stuff=")); Serial.print(wireStuffingMode());
  Serial.print(F(" close=")); Serial.print(STOCK_CLOSE_FLAG);
  printReplyPayload();
  Serial.print(F(" delay_req="));
#if STOCK_FIXED_CANDIDATE && RX_NARROW
  Serial.print(stockReplyDelayUs());
#else
  Serial.print(delayUs[sweepDelay]);
#endif
  Serial.print(F("/")); Serial.print(achievedUs);
  Serial.print(F("us emit_late_max=")); Serial.print(txMaxLatenessUs);
  Serial.print(F(" emit_applied_late_max=")); Serial.print(txAppliedMaxLatenessUs);
#if STOCK_FIXED_CANDIDATE && RX_NARROW
  Serial.print(F(" reply_sent=")); Serial.print(stockReplySent ? 1 : 0);
#endif
  Serial.print(F(" swap=")); Serial.print(sweepSwap);
  Serial.print(F(" clk_inv=")); Serial.print(txClockLevelInvert);
  Serial.print(F(" dat_inv=")); Serial.print(txDataLevelInvert);
  Serial.print(F(" fixed=")); Serial.print(STOCK_FIXED_CANDIDATE);
#if STOCK_CONTEXT_EVENTS
  if (stockLastReplyStartUs) {
    Serial.print(F(" tx_start_us=")); Serial.print(stockLastReplyStartUs);
  }
#endif
#else
  Serial.print(F("  [content_idx=")); Serial.print(sweepContent);
  Serial.print(F(" name=")); Serial.print(contentName(sweepContent));
  printReplyPayload();
  Serial.print(F(" delay_req=")); Serial.print(delayUs[sweepDelay]);
  Serial.print(F("/")); Serial.print(achievedUs);
  Serial.print(F("us emit_late_max=")); Serial.print(txMaxLatenessUs);
  Serial.print(F(" clock=")); Serial.print(sweepClock);
  Serial.print(F(" invert=")); Serial.print(sweepInvert);
  Serial.print(F(" swap=")); Serial.print(sweepSwap);
#endif
  if (datRises == 0) Serial.print(F("]  NO DATA-LINE ACTIVITY OBSERVED"));
  else Serial.print(']');
  Serial.println();
  datRises = 0;
  if (n > SUCCESS_CELLS) {
    Serial.println(F("*** LONGER BURST - possible progress; verify on the scope ***"));
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(CLK_IN, INPUT);
  pinMode(DAT_IN, INPUT);
  pinMode(CLK_OUT, OUTPUT);
  pinMode(DAT_OUT, OUTPUT);
#if FEEDBACK_HARNESS
  fbBlackRelease();  // preload the selected idle level before enabling D7
  pinMode(BLACK_OUT, OUTPUT);
  pinMode(YELLOW_IN, INPUT);
#endif
#if STOCK_CONTEXT_EVENTS
  pinMode(YELLOW_IN, INPUT);  // external 10 kOhm pull-up is required
  PCIFR |= _BV(PCIF0);
  stockYellowWasHigh = (PINB & _BV(PB0)) != 0;
  PCMSK0 |= _BV(PCINT0);
  PCICR |= _BV(PCIE0);
#endif
  clkReg = portOutputRegister(digitalPinToPort(CLK_OUT));
  datReg = portOutputRegister(digitalPinToPort(DAT_OUT));
  clkMask = digitalPinToBitMask(CLK_OUT);
  datMask = digitalPinToBitMask(DAT_OUT);
  clkLow(); datLow();
#if !FEEDBACK_HARNESS && (FREE_TX || RX_NARROW || RX_SWEEP)
  sweepSwap = STOCK_TX_SWAP;
  txClockLevelInvert = STOCK_CLOCK_INVERT;
  txDataLevelInvert = STOCK_DATA_INVERT;
#endif
#if FEEDBACK_HARNESS
  fbBlackRelease();
#endif
#if !FEEDBACK_HARNESS
  attachInterrupt(digitalPinToInterrupt(CLK_IN), onClockEdge, RISING);
#endif
#if FREERUN_TEST
  // Enable Timer2 only after the ISR's GPIO pointers and masks are valid.
  freerunBegin();
#endif
  // State the build in the log.  The IDE will happily flash a stale sketch, so
  // the run must say which one it actually is.
#if FEEDBACK_HARNESS
  fbHighAt = micros();
  Serial.println(F("BOOT"));
#else
  Serial.println(F("M1000 IR probe. Expecting 17- or 22-cell bursts at 93.75 ms."));
#endif
#if FEEDBACK_HARNESS
  Serial.println(F("MODE: FEEDBACK v1/v2, SILENT until explicit T; D5=A D6=B D7=black driver D8=yellow input"));
  fbPrintWiring();
#elif LOOPBACK_TEST
  Serial.println(F("MODE: LOOPBACK -- transmitting to my own detectors."));
  Serial.println(F("  pass = 10000001000001011 comes back"));
#elif LISTEN_ONLY
  Serial.println(F("MODE: LISTEN ONLY -- not transmitting, sweep frozen."));
#if STOCK_CONTEXT_EVENTS
  Serial.println(F("  stock-context silent control: D8 yellow event capture"));
#endif
#if RECORD_READOUT
  Serial.println(F("  RECORD_READOUT: de-stuffed hex, one frame per line"));
#endif
#elif ORIENTATION_TEST
  Serial.println(F("MODE: ORIENTATION TEST -- swap alternates, all else held."));
  Serial.println(F("  compare retry cadence between swap=0 and swap=1"));
#elif LADDER_TEST
  Serial.println(F("MODE: COMPLETENESS LADDER -- length x closing flag."));
  Serial.println(F("  stim 3 and 4 are the same length; only 4 is closed"));
#elif FREERUN_TEST
  Serial.println(F("MODE: FREE-RUNNING CLOCK -- Timer2 clocks continuously."));
  Serial.println(F("  stim 4 gates it off, stim 5 is silent: both in-run controls"));
#elif PULSE_TEST
  Serial.println(F("MODE: PULSE TEST -- featureless light, fixed duration."));
  Serial.println(F("  silent control interleaved at every start time"));
#elif RX_NARROW
  Serial.println(F("MODE: RX NARROW -- flag fixed to 7E, one axis varied."));
#if RX_NARROW_AXIS == 0
  Serial.println(F("  axis = phase (-4,-2,0,2,4 eighths of a cell)"));
#elif RX_NARROW_AXIS == 1
  Serial.println(F("  axis = data polarity (normal / complemented)"));
#elif RX_NARROW_AXIS == 2
  Serial.println(F("  axis = content (flag / flag+03h / open type-2 ack)"));
#else
  Serial.println(F("  axis = optical clock/data assignment (normal / swapped)"));
#endif
  rxFlagIdx = 1;                  // 7E: current trial baseline
  rxPolIdx = 0;                   // baseline polarity, fixed unless swept
  rxContentIdx = 2;               // content index 2 -> map 7 = type-2 control ack
  rxPhaseIdx = 1;                 // -2/8: nominal data lead baseline
  sweepSwap = STOCK_TX_SWAP;      // baseline assignment, fixed unless swept
  txPre = RX_LEAD_CELLS;          // Micronic-style clock-only lead-in
  sweepDelay = 3;                 // 4 ms; hold the timing, vary only the axis
#elif RX_SWEEP
  Serial.println(F("MODE: RX SWEEP -- reply to each handheld burst, one"));
  Serial.println(F("  convention per burst: flag x polarity x phase x content."));
  Serial.println(F("  pair with micron1_stockhook_rx.bin; the handheld stops"));
  Serial.println(F("  polling once a reply changes state -- last line names it."));
  sweepDelay = 7;                 // 26 ms after the burst end: in the RX window
#elif FREE_TX
  Serial.print(F("MODE: FREE TX -- one swept burst every "));
  Serial.print(FREE_TX_PERIOD_MS); Serial.println(F(" ms, no handheld burst."));
#if STOCK_CONTEXT_EVENTS
  Serial.println(F("  stock-context hook: D8 yellow pulse widths; D7 unused"));
#else
  Serial.println(F("  pair with micron1_stockhook_rx.bin; watch its `I ss rr` row"));
#endif
#else
  Serial.println(F("MODE: SWEEP -- delay x content x clock x invert x swap."));
#endif
#if STOCK_CONTEXT_EVENTS && !FREE_TX && !LISTEN_ONLY
  Serial.println(F("STOCK_CONTEXT_EVENTS: D8 yellow pulse widths; D7 unused"));
#endif
#if STOCK_CONTEXT_EVENTS
  Serial.println(F("STOCK_CONTEXT_V3 width_us=32 drops=16"));
#endif
#if STOCK_FIXED_CANDIDATE
  rxFlagIdx = STOCK_FLAG_IDX;
  rxPhaseIdx = STOCK_PHASE_IDX;
  rxPolIdx = STOCK_POL_IDX;
  rxContentIdx = STOCK_CONTENT_IDX;
#endif
#if !FEEDBACK_HARNESS && (FREE_TX || RX_NARROW || RX_SWEEP)
  Serial.print(F("STOCK_TX swap=")); Serial.print(sweepSwap);
  Serial.print(F(" clk_inv=")); Serial.print(txClockLevelInvert);
  Serial.print(F(" dat_inv=")); Serial.println(txDataLevelInvert);
  Serial.print(F("STOCK_FRAMING stuff_cfg=")); Serial.print(STOCK_STUFFING_MODE);
  Serial.print(F(" wire_stuff="));
#if STOCK_STUFFING_MODE < 0
  Serial.print(F("auto"));
#else
  Serial.print(STOCK_STUFFING_MODE);
#endif
  Serial.print(F(" close=")); Serial.println(STOCK_CLOSE_FLAG);
  Serial.print(F("STOCK_CLOSE_BYTE="));
#if STOCK_CLOSE_BYTE < 0
  Serial.println(F("--"));
#else
  Serial.println(STOCK_CLOSE_BYTE, HEX);
#endif
  Serial.print(F("STOCK_PREFIX_BYTE="));
#if STOCK_PREFIX_BYTE < 0
  Serial.println(F("--"));
#else
  Serial.println(STOCK_PREFIX_BYTE, HEX);
#endif
  Serial.print(F("STOCK_PAYLOAD00_TO80="));
  Serial.println(STOCK_PAYLOAD00_TO80);
  Serial.print(F("STOCK_PAYLOAD07_TO06="));
  Serial.println(STOCK_PAYLOAD07_TO06);
  Serial.print(F("STOCK_ZERO_PAYLOAD="));
  Serial.println(STOCK_ZERO_PAYLOAD);
#if STOCK_FIXED_CANDIDATE
  Serial.print(F("STOCK_FIXED flag=")); Serial.print(rxFlagTab[rxFlagIdx], HEX);
  Serial.print(F(" phase=")); Serial.print(rxPhaseTab[rxPhaseIdx]);
  Serial.print(F(" pol=")); Serial.print(rxPolIdx);
  Serial.print(F(" content_idx=")); Serial.print(rxContentIdx);
  Serial.print(F(" delay_us=")); Serial.println(STOCK_REPLY_DELAY_US);
#if RX_NARROW && STOCK_REPLY_DELAY_COUNT > 1
  Serial.print(F("STOCK_DELAY_SWEEP step_us="));
  Serial.print(STOCK_REPLY_DELAY_STEP_US);
  Serial.print(F(" count=")); Serial.println(STOCK_REPLY_DELAY_COUNT);
#endif
#if RX_NARROW && STOCK_REPLY_EVERY_N > 1
  Serial.print(F("STOCK_REPLY_EVERY_N=")); Serial.println(STOCK_REPLY_EVERY_N);
#endif
#endif
#endif
}

void loop() {
#if FEEDBACK_HARNESS
  feedbackTick();
  return;
#endif
  // lastEdgeUs is four bytes on an 8-bit core, so reading it while the ISR may
  // be writing it can tear: catch it mid-update and the high bytes come from
  // the old value, "micros() - lastEdgeUs" goes huge, and the burst is falsely
  // declared over part-way through.  Snapshot both under noInterrupts().
  noInterrupts();
  uint8_t n = rxCount;
  unsigned long last = lastEdgeUs;
  interrupts();

  // Poll D4 for best-effort activity/phase context. Serial output and frame
  // emission can postpone this poll, so no observed rise does not prove that
  // the data line stayed low. The data rise is nominally ~91 us after the
  // previous clock edge.
#if LOOPBACK_TEST
  loopbackTick();
#endif
#if FREE_TX
  freeTxTick();
#endif
  uint8_t d = (PIND & _BV(PD4)) != 0;
  if (d && !datPrev) { datRises++; datPhase = micros() - last; }
  datPrev = d;

#if RECORD_READOUT
  drainRing();                                     // stream bytes continuously
#endif

  if (n == 0) {
#if STOCK_CONTEXT_EVENTS
    stockDrainYellowEvents();
#endif
    return;
  }
  if (micros() - last < GAP_US) return;            // burst still in progress

#if RECORD_READOUT
  noInterrupts();
  n = rxCount;
  rxCount = 0;
  interrupts();
#else
  uint8_t snapshot[160];
#if STOCK_CONTEXT_EVENTS
  // Swap ownership atomically, then copy with interrupts enabled. This keeps
  // the D8 interrupt masked for only a pointer/count update, not 160 bytes.
  noInterrupts();
  n = rxCount;
  volatile uint8_t *filled = rxBits;
  rxBits = (rxBits == rxBitsA) ? rxBitsB : rxBitsA;
  rxCount = 0;
  interrupts();
  for (uint8_t i = 0; i < n; i++) snapshot[i] = filled[i];
#else
  noInterrupts();
  n = rxCount;                                     // may have grown; re-read
  for (uint8_t i = 0; i < n; i++) snapshot[i] = rxBits[i];
  rxCount = 0;
  interrupts();
#endif
#endif

#if STOCK_CONTEXT_EVENTS
  stockLastReplyStartUs = 0;
#endif
#if STOCK_FIXED_CANDIDATE && RX_NARROW
  stockReplySent = false;
  achievedUs = 0;
  txMaxLatenessUs = 0;
  txAppliedMaxLatenessUs = 0;
#endif

  // Reply first, report afterwards.  One Serial line at 115200 is ~4 ms and
  // the LINK_STATUS bit-6-clear wait is about 9.92 ms; printing first would
  // lose every trial aimed at that window.
#if !LISTEN_ONLY && !LOOPBACK_TEST && !FREE_TX
#if LADDER_TEST
  if (n <= SUCCESS_CELLS) {
    unsigned long fire = last + ldStartTab[pulseStart];
    unsigned long now  = micros();
    if ((long)(fire - now) < 0) fire = now;
    achievedUs = fire - last;
    if (pulseStim > 0) {
      buildLadder(pulseStim);
      waitUntil(txFirstEventTime((uint32_t)fire, 0));
      txActive = true; emitCells(fire, 0, 0);
      txActive = false; delayMicroseconds(300);
    }
  }
#elif FREERUN_TEST
  if (n <= SUCCESS_CELLS) {
    unsigned long fire = last + frStartTab[pulseStart];
    unsigned long now  = micros();
    if ((long)(fire - now) < 0) fire = now;
    achievedUs = fire - last;
    if (pulseStim == 5) {                       // silent: clock off, no data
      clkFree = false; clkLow(); datLow();
    } else if (pulseStim == 4) {                // gate the clock, send a burst
      clkFree = false; clkLow(); datLow();
      buildFramed(0x03);
      waitUntil(txFirstEventTime((uint32_t)fire, 0));
      txActive = true; emitCells(fire, 0, 0);
      txActive = false; delayMicroseconds(300);
    } else {
      clkFree = true;                           // clock runs regardless
      if (pulseStim > 0) {
        buildFramed(FREE_ADDR[pulseStim - 1]);
        waitUntil(fire);
        freerunArm();
      }
    }
  }
#elif PULSE_TEST
  if (n <= SUCCESS_CELLS) {
    unsigned long fire = last + startUsTab[pulseStart];
    unsigned long now  = micros();
    if ((long)(fire - now) < 0) fire = now;
    achievedUs = fire - last;
    sendPulse(fire, pulseStim);
  }
#else
  if (n <= SUCCESS_CELLS) {
#if STOCK_FIXED_CANDIDATE && RX_NARROW
    stockReplySent = stockReplyDue(n);
    if (stockReplySent) {
#endif
    unsigned long fire = last +
#if STOCK_FIXED_CANDIDATE && RX_NARROW
        stockReplyDelayUs();
#else
        delayUs[sweepDelay];
#endif
    unsigned long now  = micros();
    // Burst-end detection costs GAP_US, so the requested delay may already have
    // passed.  Starting in the past would make every waitUntil() before the
    // present expire at once and squash the leading cells together, emitting a
    // malformed frame that looks like a protocol failure.  Start now instead,
    // and report what was actually achieved rather than what was asked for.
    if ((long)(fire - now) < 0) fire = now;
    // Modes 1 and 3 align our cells with the handheld's own bit grid rather
    // than starting at an arbitrary phase: step to the next whole cell
    // boundary measured from its last clock edge.
    if (sweepClock == 1 || sweepClock == 3) {
      unsigned long k = (fire - last + CELL_US - 1) / CELL_US;
      fire = last + k * CELL_US;
    }
    achievedUs = fire - last;
#if RX_SWEEP || RX_NARROW
    // Apply the receive-convention axes: data polarity, data-to-clock phase,
    // and the mapped buildReply() content (the flag sense lives in putFlag()).
    sweepInvert = rxPolIdx;
    txPhaseEighths = rxPhaseTab[rxPhaseIdx];
    selectStockStuffing();
    buildReply(rxContentMap[rxContentIdx]);
#if STOCK_CONTEXT_EVENTS
    stockLastReplyStartUs = fire;
#endif
#else
    buildReply(sweepContent);
#endif
    sendFrame(fire);
#if STOCK_FIXED_CANDIDATE && RX_NARROW
    }
#endif
  }
#endif
#endif

#if RECORD_READOUT
  drainRing();                                     // flush the frame's tail
  Serial.println();                                // one frame per line
  if (dfMalformed) Serial.println(F("! MALFORMED_STUFFING"));
  Serial.print(F("# burst ")); Serial.print(n);
  Serial.println(F(" cells"));
  destuffReset();                                  // re-arm for the next burst
#else
  report(n, snapshot);
#endif
#if !LISTEN_ONLY && !LOOPBACK_TEST && !FREE_TX
  if (n <= SUCCESS_CELLS) advanceSweep();
#endif
#if STOCK_CONTEXT_EVENTS
  stockDrainYellowEvents();
#endif
}
