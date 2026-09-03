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
#define LISTEN_ONLY 1

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
uint8_t frameBits[96];
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

// ----------------------------------------------------------- the sweep ----
// Reply content variants.  0 = flag only ... see contentName().
const uint8_t N_CONTENT = 7;
const uint8_t N_DELAY   = 8;
const uint16_t delayUs[N_DELAY] = { 500, 750, 1000, 2000, 3000, 5000, 7000, 9000 };
// The HSBUSY deadline is 9.92 ms: DE=026Ch = 620 iterations of a 59 T loop at
// ROM00:32F0, on a 3.6864 MHz Z80.  Nothing past ~9.5 ms can ever work.
// The floor is set by GAP_US: a burst is not known to have ended until 400 us
// of silence, so anything below ~450 us is unreachable by this method.  If the
// sweep comes up empty everywhere, detect the end by pattern instead -- both
// burst forms end with the cells 1,0,1,1 -- which would reach ~150 us.

const char *contentName(uint8_t c) {
  switch (c) {
    case 0: return "flag only";
    case 1: return "flag+03h (echo address)";
    case 2: return "flag+7Fh";
    case 3: return "flag+43h";
    case 4: return "flag+63h";
    case 5: return "flag x4 (flag fill)";
    default: return "bare pulses, no framing";
  }
}

void buildReply(uint8_t content) {
  frameLen = 0;
  uint8_t zeroRun = 0;
  switch (content) {
    case 0: putFlag(); break;
    case 1: putFlag(); putStuffedByte(0x03, &zeroRun); break;
    case 2: putFlag(); putStuffedByte(0x7F, &zeroRun); break;
    case 3: putFlag(); putStuffedByte(0x43, &zeroRun); break;
    case 4: putFlag(); putStuffedByte(0x63, &zeroRun); break;
    case 5: for (uint8_t i = 0; i < 4; i++) putFlag(); break;
    default: for (uint8_t i = 0; i < 16; i++) putBit(i & 1); break;
  }
}

// clockMode: 0 = clock with the data, 1 = data only (no return clock),
//            2 = clock only (no data), 3 = clock free-runs, data on top
uint8_t sweepContent = 1, sweepDelay = 0, sweepClock = 0, sweepInvert = 0;
unsigned long achievedUs = 0;   // reply delay actually achieved, us

void advanceSweep() {
  if (++sweepDelay < N_DELAY) return;
  sweepDelay = 0;
  if (++sweepContent < N_CONTENT) return;
  sweepContent = 0;
  if (++sweepClock < 4) return;
  sweepClock = 0;
  sweepInvert ^= 1;
}

// ------------------------------------------------------------- transmit ---
// Direct port writes and absolute scheduling.  digitalWrite() costs ~4 us on
// an AVR, which against a 31 us sub-interval is not slop we can afford, and
// chaining delayMicroseconds() accumulates that error across the frame.  Every
// edge is instead placed at a fixed offset from the frame's start time.
volatile uint8_t *clkReg, *datReg;
uint8_t clkMask, datMask;

inline void clkHigh() { *clkReg |=  clkMask; }
inline void clkLow()  { *clkReg &= ~clkMask; }
inline void datHigh() { *datReg |=  datMask; }
inline void datLow()  { *datReg &= ~datMask; }

inline void waitUntil(unsigned long t) { while ((long)(micros() - t) < 0) ; }

void sendFrame(unsigned long startUs) {
  txActive = true;
  bool wantClk = (sweepClock != 1);
  for (uint8_t i = 0; i < frameLen; i++) {
    unsigned long cell = startUs + (unsigned long)i * CELL_US;
    uint8_t bit = frameBits[i] ^ sweepInvert;
    bool wantData = (sweepClock != 2) && bit;

    waitUntil(cell);                                  if (wantData) datHigh();
    waitUntil(cell + DATA_LEAD_US);                   if (wantClk)  clkHigh();
    waitUntil(cell + DATA_HIGH_US);                   datLow();
    waitUntil(cell + DATA_LEAD_US + CLK_HIGH_US);     clkLow();
  }
  waitUntil(startUs + (unsigned long)frameLen * CELL_US);
  clkLow(); datLow();
  delayMicroseconds(300);          // let any crosstalk settle
  txActive = false;
}

// -------------------------------------------------------------- reports ---
void report(uint8_t n, const uint8_t *bits) {
  Serial.print(F("burst "));
  Serial.print(n);
  Serial.print(F(" cells  "));
  for (uint8_t i = 0; i < n; i++) Serial.write(bits[i] ? '1' : '0');
  Serial.print(F("  [content=")); Serial.print(contentName(sweepContent));
  Serial.print(F(" delay=")); Serial.print(delayUs[sweepDelay]);
  Serial.print(F("/")); Serial.print(achievedUs);
  Serial.print(F("us clock=")); Serial.print(sweepClock);
  Serial.print(F(" invert=")); Serial.print(sweepInvert);
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
  pinMode(CLK_OUT, OUTPUT);
  pinMode(DAT_OUT, OUTPUT);
  clkReg = portOutputRegister(digitalPinToPort(CLK_OUT));
  datReg = portOutputRegister(digitalPinToPort(DAT_OUT));
  clkMask = digitalPinToBitMask(CLK_OUT);
  datMask = digitalPinToBitMask(DAT_OUT);
  clkLow(); datLow();
  attachInterrupt(digitalPinToInterrupt(CLK_IN), onClockEdge, RISING);
  Serial.println(F("M1000 IR probe. Expecting 17- or 22-cell bursts at 93.75 ms."));
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
#if !LISTEN_ONLY
  if (n <= SUCCESS_CELLS) {
    unsigned long fire = last + delayUs[sweepDelay];
    unsigned long now  = micros();
    // Burst-end detection costs GAP_US, so the requested delay may already have
    // passed.  Starting in the past would make every waitUntil() before the
    // present expire at once and squash the leading cells together, emitting a
    // malformed frame that looks like a protocol failure.  Start now instead,
    // and report what was actually achieved rather than what was asked for.
    if ((long)(fire - now) < 0) fire = now;
    achievedUs = fire - last;
    buildReply(sweepContent);
    sendFrame(fire);
  }
#endif

  report(n, snapshot);
#if !LISTEN_ONLY
  if (n <= SUCCESS_CELLS) advanceSweep();
#endif
}
