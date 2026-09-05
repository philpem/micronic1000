// M1000 IR link probe and responder.
//
// Listens to the handheld's outbound clock/data pair, decodes the
// inverted-HDLC frame documented in doc/re-notes/ir-wire-protocol.md, and
// answers on the return pair while sweeping the parameters we cannot yet
// derive from the ROM.
//
// The handheld retries a connect 50 times at 93.75 ms (ROM00:2F58 sets the
// 32h count), so one operator keypress yields ~50 free trials.  The sketch
// changes one sweep parameter per burst and scores itself: any burst longer
// than SUCCESS_CELLS means the HSBUSY wait at ROM00:32F3 cleared and the
// handheld went on to stream its payload.  That is the whole experiment.
//
// Wiring (5 V AVR assumed - Uno/Nano at 16 MHz):
//   CLK_IN   D2   handheld clock emitter drive   (INT0)
//   DAT_IN   D4   handheld data emitter drive
//   CLK_OUT  D5   our clock emitter -> handheld's clock detector
//   DAT_OUT  D6   our data emitter  -> handheld's data detector
//
// The handheld's drive lines swing to ~5.5 V, which is over VCC+0.5 on a 5 V
// part and well over a 3.3 V one.  Put 10k in series with each input, or a
// divider on a 3.3 V board.  Do not connect an input directly.
//
// Keep the two return channels optically separated - a mask or a short opaque
// tube per LED.  Crosstalk from our clock into the handheld's data detector
// will look exactly like a protocol failure.

// Stage 1: build with LISTEN_ONLY 1, confirm the monitor prints 17- and
// 22-cell bursts every 93.75 ms and that they match the scope.  Only then set
// it to 0 and let the sweep transmit.  A responder debugged against a decoder
// you have not validated is two unknowns at once.
#define LISTEN_ONLY 0

// Stage 1b: point the Arduino's own emitters at its own detectors and build
// with LOOPBACK_TEST 1.  It transmits twice a second and reports what its
// receiver made of it, so the whole transmit chain -- framing, cell timing,
// port writes, LED drive, optics -- is proven against a receiver already known
// to work.  A correct flag+03h reply must come back as 10000001000001011, the
// handheld's own form A.  Until that passes, a silent handheld proves nothing:
// a dead or misaimed emitter looks exactly like a protocol we have not guessed.
#define LOOPBACK_TEST 0

// Stage 2b: which of the handheld's two detectors is clock and which is data
// is NOT known.  Its two emitters identify themselves -- one is periodic, one
// is sparse -- but nothing identifies its receivers, so our two emitters may
// be feeding them backwards, and every negative result so far is suspect for
// that reason alone.  Build with ORIENTATION_TEST 1 to hold content, delay and
// clock mode fixed and alternate the orientation on every burst.  The handheld
// stretches its retry cadence from 93.75 ms to ~109 ms when it notices us, so
// comparing that stretch between the two interleaved populations decides the
// orientation without needing it to answer.
#define ORIENTATION_TEST 0

// Stage 3: is the handheld reacting to our BITS, or just to light being
// present at a particular moment?  conn7 said the latter -- the disturbance
// tracked when our light went dark (92-100% at 3-9 ms after its burst, ~20%
// either side) and not what the frame encoded, with the long frame replies
// scoring 0% only because they ended too late.  This mode removes framing
// entirely: a featureless pulse of FIXED duration, swept only in start time,
// with a silent control interleaved at every start time so the baseline is
// measured under the same conditions rather than assumed.
//
// If a bare pulse reproduces the band-pass, HSBUSY is not decoding bits and
// content sweeping is the wrong tool.  If only the modulated variants do it,
// the front end is edge-sensitive and a carrier matters.  If nothing does it,
// conn7's correlation was an artefact and we are back to needing a channel.
#define PULSE_TEST 1

// Stage 4: sweep the address byte.  conn10 showed the handheld reacts to
// 00h/03h/1Fh but not to FFh under identical conditions, so the byte after the
// flag looks like it is being examined.  The handheld's own prelude is
// `id & 1Fh`, and bit 5 is the port select that LinkPortSelect drives from the
// link id -- so 00h-3Fh covers the whole of the field the firmware is known to
// use, and the bits above it are the interesting unknown.  Raise ADDR_HI to
// widen; 7Fh and FFh ride along as deliberate out-of-range controls.
#define ADDR_SWEEP 0

// Stage 5: a genuinely free-running return clock.  Everything tried so far has
// been a burst a few ms long, but the firmware dies waiting for LINK_STATUS
// bit 6 at ROM00:32F3 -- a controller status bit, not anything on the wire --
// and a controller might only report a live link while it is actually being
// clocked.  Here Timer2 drives the clock emitter continuously at 8192 Hz from
// power-on and never stops; data is gated on top, in phase, by the same ISR.
// Stimulus 4 gates the clock off and sends an ordinary burst instead, so the
// comparison against everything before is made inside one run rather than
// across two.
#define FREERUN_TEST 0

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
#define LADDER_TEST 1

// The three flags are not independent.  ORIENTATION_TEST alternates the
// orientation inside advanceSweep(), and both advanceSweep() and the reply are
// compiled out when LISTEN_ONLY or LOOPBACK_TEST is set -- so the wrong
// combination builds cleanly, transmits nothing, and wastes a run looking
// exactly like a negative result.  Fail at compile time instead.
#if LADDER_TEST && (LISTEN_ONLY || LOOPBACK_TEST || ORIENTATION_TEST || ADDR_SWEEP || FREERUN_TEST)
#error "LADDER_TEST needs every other mode flag 0"
#endif
#if FREERUN_TEST && (LISTEN_ONLY || LOOPBACK_TEST || ORIENTATION_TEST || ADDR_SWEEP)
#error "FREERUN_TEST needs LISTEN_ONLY/LOOPBACK_TEST/ORIENTATION_TEST/ADDR_SWEEP all 0"
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

// ------------------------------------------------------------- reception --
volatile uint8_t  rxBits[160];  // a 12-byte payload frame is ~120 cells
volatile uint8_t  rxCount = 0;
volatile unsigned long lastEdgeUs = 0;
volatile bool     txActive = false;   // ignore our own crosstalk

// Data-line activity monitor.  If every sampled bit is 0 this says whether the
// data channel is carrying anything at all, and if so at what phase -- which
// separates "no signal" from "sampled at the wrong instant".
uint8_t  datPrev  = 0;
uint16_t datRises = 0;
unsigned long datPhase = 0;   // us from the previous clock edge to a data rise

void onClockEdge() {
  if (txActive) return;
  unsigned long now = micros();
  // Reject chatter.  A plain CMOS inverter on the photodiode node crosses its
  // threshold over tens of ns of ambiguity, and one double-counted clock edge
  // fabricates a bit cell.  Real edges are a whole cell apart, so this costs
  // nothing and removes the need for a Schmitt-trigger part.
  if (rxCount && now - lastEdgeUs < MIN_EDGE_US) return;
  if (rxCount < sizeof(rxBits)) rxBits[rxCount++] = digitalRead(DAT_IN);
  lastEdgeUs = now;
}

// ------------------------------------------------------------ the framer --
// Inverted HDLC: idle 0, flag 1000_0001 sent raw, data bit-stuffed with a 1
// after five consecutive 0s, MSB first.
uint8_t frameBits[128];
uint8_t frameLen = 0;

void putBit(uint8_t b) { if (frameLen < sizeof(frameBits)) frameBits[frameLen++] = b; }

void putFlag() { for (int8_t i = 7; i >= 0; i--) putBit((FLAG >> i) & 1); }

void putStuffedByte(uint8_t v, uint8_t *zeroRun) {
  for (int8_t i = 7; i >= 0; i--) {
    if (*zeroRun == 5) { putBit(1); *zeroRun = 0; }
    uint8_t b = (v >> i) & 1;
    putBit(b);
    *zeroRun = b ? 0 : *zeroRun + 1;
  }
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
const uint8_t N_DELAY   = 8;
const uint16_t delayUs[N_DELAY] = { 500, 750, 1000, 2000, 3000, 5000, 7000, 9000 };
// The HSBUSY deadline is 9.92 ms: DE=026Ch = 620 iterations of a 59 T loop at
// ROM00:32F0, on a 3.6864 MHz Z80.  Nothing past ~9.5 ms can ever work.
// The floor is set by GAP_US: a burst is not known to have ended until 400 us
// of silence, so anything below ~450 us is unreachable by this method.  If the
// sweep comes up empty everywhere, detect the end by pattern instead -- both
// burst forms end with the cells 1,0,1,1 -- which would reach ~150 us.

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
  if (k == 2 || k >= 4) putFlag();                 // closing flag, unstuffed
}
#endif

// flag + one address byte, stuffed, at the protocol's phase
void buildFramed(uint8_t addr) {
  frameLen = 0; uint8_t zr = 0;
  putFlag(); putStuffedByte(addr, &zr);
}

void putFrame(uint8_t *zeroRun) {
  for (uint8_t i = 0; i < sizeof(ACK_FRAME); i++) putStuffedByte(ACK_FRAME[i], zeroRun);
}

void buildReply(uint8_t content) {
  frameLen = 0;
  uint8_t zeroRun = 0;
  switch (content) {
    case 0: putFlag(); break;
    case 1: putFlag(); putStuffedByte(0x03, &zeroRun); break;
    case 2: putFlag(); putStuffedByte(0x1F, &zeroRun); break;
    case 3: putFlag(); putStuffedByte(0x00, &zeroRun); break;
    case 4: putFlag(); putStuffedByte(0x7F, &zeroRun); break;
    case 5: putFlag(); putFrame(&zeroRun); putFlag(); break;
    case 6: putFlag(); putStuffedByte(0x03, &zeroRun); putFrame(&zeroRun); putFlag(); break;
    default: for (uint8_t i = 0; i < 4; i++) putFlag(); break;
  }
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
uint8_t sweepSwap = 0;   // 1 = our clock drives their data detector and vice versa
unsigned long achievedUs = 0;   // reply delay actually achieved, us

void advanceSweep() {
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

// The swap is applied here, so one flag re-points both lines at once.
inline void clkHigh() { if (sweepSwap) *datReg |=  datMask; else *clkReg |=  clkMask; }
inline void clkLow()  { if (sweepSwap) *datReg &= ~datMask; else *clkReg &= ~clkMask; }
inline void datHigh() { if (sweepSwap) *clkReg |=  clkMask; else *datReg |=  datMask; }
inline void datLow()  { if (sweepSwap) *clkReg &= ~clkMask; else *datReg &= ~datMask; }

inline void waitUntil(unsigned long t) { while ((long)(micros() - t) < 0) ; }

// The bit-cell emitter, shared by the framed reply and the pulse test so both
// use identical phasing: data rises a quarter cell before the clock.
void emitCells(unsigned long startUs, uint8_t wrap) {
  uint8_t total = wrap + frameLen + wrap;
  for (uint8_t i = 0; i < total; i++) {
    unsigned long cell = startUs + (unsigned long)i * CELL_US;
    bool inFrame = (i >= wrap) && (i < wrap + frameLen);
    bool wantData = inFrame && (frameBits[i - wrap] ^ sweepInvert);

    waitUntil(cell);                                  if (wantData) datHigh();
    waitUntil(cell + DATA_LEAD_US);                   clkHigh();
    waitUntil(cell + DATA_HIGH_US);                   datLow();
    waitUntil(cell + DATA_LEAD_US + CLK_HIGH_US);     clkLow();
  }
  waitUntil(startUs + (unsigned long)total * CELL_US);
  clkLow(); datLow();
}

void sendFrame(unsigned long startUs) {
#if !LOOPBACK_TEST
  txActive = true;          // in loopback we deliberately listen to ourselves
#endif
  emitCells(startUs, (sweepClock >= 2) ? PREAMBLE_CELLS : 0);
  delayMicroseconds(300);          // let any crosstalk settle
  txActive = false;
}

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
  if (stim == 0) return;                       // the control: emit nothing
  // Non-framed stimuli must drive the pins they name, so the emitter swap is
  // only ever applied to a framed variant that asks for it.
  sweepSwap = stimFramed(stim) && stimSwap(stim);
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
    buildFramed(stimAddr(stim));
    emitCells(startUs + pre, 0);
  }
  clkLow(); datLow();
  delayMicroseconds(300);
  txActive = false;
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
  Serial.print(F("us"));
#else
  Serial.print(F("  [content=")); Serial.print(contentName(sweepContent));
  Serial.print(F(" delay=")); Serial.print(delayUs[sweepDelay]);
  Serial.print(F("/")); Serial.print(achievedUs);
  Serial.print(F("us clock=")); Serial.print(sweepClock);
  Serial.print(F(" invert=")); Serial.print(sweepInvert);
  Serial.print(F(" swap=")); Serial.print(sweepSwap);
#endif
  if (datRises == 0) Serial.print(F("]  NO DATA-LINE ACTIVITY"));
  else Serial.print(']');
  Serial.println();
  datRises = 0;
  if (n > SUCCESS_CELLS) {
    Serial.println(F("*** HANDSHAKE CLEARED - stop and capture this on the scope ***"));
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(CLK_IN, INPUT);
  pinMode(DAT_IN, INPUT);
#if FREERUN_TEST
  freerunBegin();
#endif
  pinMode(CLK_OUT, OUTPUT);
  pinMode(DAT_OUT, OUTPUT);
  clkReg = portOutputRegister(digitalPinToPort(CLK_OUT));
  datReg = portOutputRegister(digitalPinToPort(DAT_OUT));
  clkMask = digitalPinToBitMask(CLK_OUT);
  datMask = digitalPinToBitMask(DAT_OUT);
  clkLow(); datLow();
  attachInterrupt(digitalPinToInterrupt(CLK_IN), onClockEdge, RISING);
  // State the build in the log.  The IDE will happily flash a stale sketch, so
  // the run must say which one it actually is.
  Serial.println(F("M1000 IR probe. Expecting 17- or 22-cell bursts at 93.75 ms."));
#if LOOPBACK_TEST
  Serial.println(F("MODE: LOOPBACK -- transmitting to my own detectors."));
  Serial.println(F("  pass = 10000001000001011 comes back"));
#elif LISTEN_ONLY
  Serial.println(F("MODE: LISTEN ONLY -- not transmitting, sweep frozen."));
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
#else
  Serial.println(F("MODE: SWEEP -- delay x content x clock x invert x swap."));
#endif
}

void loop() {
  // lastEdgeUs is four bytes on an 8-bit core, so reading it while the ISR may
  // be writing it can tear: catch it mid-update and the high bytes come from
  // the old value, "micros() - lastEdgeUs" goes huge, and the burst is falsely
  // declared over part-way through.  Snapshot both under noInterrupts().
  noInterrupts();
  uint8_t n = rxCount;
  unsigned long last = lastEdgeUs;
  interrupts();

  // Poll the data line every pass.  loop() spins in a few us when idle, so a
  // 76 us pulse cannot be missed, and the phase tells us where it sits: the
  // data rises a quarter cell BEFORE a clock edge, so ~91 us after the
  // previous one.
#if LOOPBACK_TEST
  loopbackTick();
#endif

  uint8_t d = digitalRead(DAT_IN);
  if (d && !datPrev) { datRises++; datPhase = micros() - last; }
  datPrev = d;

  if (n == 0) return;
  if (micros() - last < GAP_US) return;            // burst still in progress

  uint8_t snapshot[160];
  noInterrupts();
  n = rxCount;                                     // may have grown; re-read
  for (uint8_t i = 0; i < n; i++) snapshot[i] = rxBits[i];
  rxCount = 0;
  interrupts();

  // Reply first, report afterwards.  One Serial line at 115200 is ~4 ms and
  // the HSBUSY window is 10.22 ms; printing first would lose every trial.
#if !LISTEN_ONLY && !LOOPBACK_TEST
#if LADDER_TEST
  if (n <= SUCCESS_CELLS) {
    unsigned long fire = last + ldStartTab[pulseStart];
    unsigned long now  = micros();
    if ((long)(fire - now) < 0) fire = now;
    achievedUs = fire - last;
    if (pulseStim > 0) {
      buildLadder(pulseStim);
      txActive = true; emitCells(fire, 0); delayMicroseconds(300); txActive = false;
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
      txActive = true; emitCells(fire, 0); delayMicroseconds(300); txActive = false;
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
    unsigned long fire = last + delayUs[sweepDelay];
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
    buildReply(sweepContent);
    sendFrame(fire);
  }
#endif
#endif

  report(n, snapshot);
#if !LISTEN_ONLY && !LOOPBACK_TEST
  if (n <= SUCCESS_CELLS) advanceSweep();
#endif
}
