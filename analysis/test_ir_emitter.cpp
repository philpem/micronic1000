// Host test for the Arduino sketch's real emitter. This file deliberately
// lives outside the .ino directory so Arduino IDE builders never see its
// main() or mock API definitions.
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <algorithm>
#include <string>
#include <utility>
#include <vector>

#define INPUT 0
#define OUTPUT 1
#define RISING 1
#define HEX 16
#define F(x) x
#define _BV(x) (1u << (x))
#define ISR(v) void v()
#define TIMER2_COMPA_vect timer2_compa_vect
#define WGM21 1
#define CS20 0
#define OCIE2A 1
#define PD4 4
#define PB0 0
#define PCINT0 0
#define PCIF0 0
#define PCIE0 0
#define PCINT0_vect pcint0_vect
typedef char __FlashStringHelper;

volatile uint8_t PORTD = 0, PORTB = 0, PIND = 0, PINB = 0;
volatile uint8_t PCIFR = 0, PCMSK0 = 0, PCICR = 0;
volatile uint8_t TCCR2A = 0, TCCR2B = 0, OCR2A = 0, TIMSK2 = 0;
struct SerialStub {
  int writable = 64;
  std::string output;
  void begin(unsigned long) {}
  int available() { return 0; }
  int read() { return -1; }
  template <typename T> void print(T) {}
  template <typename T> void print(T, int) {}
  template <typename T> void println(T) {}
  template <typename T> void println(T, int) {}
  void println() {}
  void write(char) {}
  int availableForWrite() { return writable; }
  size_t write(const uint8_t *data, size_t len) {
    output.append((const char *)data, len);
    return len;
  }
} Serial;

uint32_t fakeNow;
uint8_t fakeReads;
unsigned long micros() {
  uint32_t returned = fakeNow;
  if (++fakeReads == 4) {
    fakeReads = 0;
    ++fakeNow;
  }
  return (unsigned long)returned;
}
void delayMicroseconds(unsigned long) {}
void noInterrupts() {}
void interrupts() {}
void pinMode(uint8_t, uint8_t) {}
void digitalWrite(uint8_t, uint8_t) {}
void analogWrite(uint8_t, int) {}
void attachInterrupt(int, void (*)(), int) {}
int digitalPinToInterrupt(uint8_t p) { return p; }
int digitalPinToPort(uint8_t p) { return p < 8 ? 0 : 1; }
uint8_t digitalPinToBitMask(uint8_t p) { return (uint8_t)(1u << (p & 7)); }
volatile uint8_t *portOutputRegister(int p) { return p ? &PORTB : &PORTD; }
uint8_t digitalRead(uint8_t) { return 0; }

struct TraceEvent {
  uint32_t actual;
  uint32_t intended;
  uint8_t type;
};
std::vector<TraceEvent> trace;
struct GpioTraceEvent { uint8_t pin; bool high; };
std::vector<GpioTraceEvent> gpioTrace;
void irHostGpio(uint8_t pin, bool high) {
  gpioTrace.push_back({pin, high});
}
void irHostEvent(uint32_t intended, uint32_t actual, uint8_t type) {
  // The sketch passes the timestamp observed by its AVR-style wait loop.
  trace.push_back({actual, intended, type});
}
#define IR_HOST_TEST 1
#include "arduino/m1000_ir_probe/m1000_ir_probe.ino"

struct ExpectedEvent {
  uint32_t at;
  uint8_t type;
};

static bool before(const ExpectedEvent &left, const ExpectedEvent &right) {
  int32_t delta = (int32_t)(left.at - right.at);
  return delta ? delta < 0 : left.type < right.type;
}

static std::vector<ExpectedEvent> expected(
    uint32_t start, const std::vector<uint8_t> &bits, int phase) {
  std::vector<ExpectedEvent> result;
  int32_t phaseUs = (int32_t)phase * (int32_t)CELL_US / 8;
  for (uint32_t cellNo = 0; cellNo < bits.size(); ++cellNo) {
    uint32_t cell = start + cellNo * (uint32_t)CELL_US;
    int32_t dataRise = (int32_t)DATA_LEAD_US + phaseUs;
    if (bits[cellNo]) result.push_back({cell + (uint32_t)dataRise, 0});
    result.push_back({cell + (uint32_t)DATA_LEAD_US, 1});
    result.push_back({cell + (uint32_t)(DATA_LEAD_US + CLK_HIGH_US), 2});
    result.push_back({cell + (uint32_t)(dataRise + DATA_HIGH_US), 3});
  }
  std::sort(result.begin(), result.end(), before);
  return result;
}

static std::vector<uint8_t> sampled(const std::vector<TraceEvent> &events) {
  std::vector<uint8_t> result;
  bool data = false;
  for (const TraceEvent &event : events) {
    if (event.type == 0) data = true;
    else if (event.type == 3) data = false;
    else if (event.type == 1) result.push_back(data ? 1 : 0);
  }
  return result;
}

static void checkGpioTrace() {
  // Every scheduled event reaches its physical output, followed by the two
  // writes that leave the emitter dark after the frame.
  const size_t baseline = (txClockLevelInvert || txDataLevelInvert) ? 2 : 0;
  assert(gpioTrace.size() == trace.size() + baseline + 2);
  if (baseline) {
    // Present data before clock when establishing complemented idle levels.
    assert(gpioTrace[0].pin == (sweepSwap ? 5 : 6));
    assert(gpioTrace[0].high == (txDataLevelInvert != 0));
    assert(gpioTrace[1].pin == (sweepSwap ? 6 : 5));
    assert(gpioTrace[1].high == (txClockLevelInvert != 0));
  }
  for (size_t i = 0; i < trace.size(); ++i) {
    const uint8_t expectedPin =
        (trace[i].type == 1 || trace[i].type == 2)
            ? (sweepSwap ? 6 : 5) : (sweepSwap ? 5 : 6);
    const bool logicalHigh = trace[i].type == 0 || trace[i].type == 1;
    const bool invert = (trace[i].type == 1 || trace[i].type == 2)
                            ? txClockLevelInvert : txDataLevelInvert;
    assert(gpioTrace[i + baseline].pin == expectedPin);
    assert(gpioTrace[i + baseline].high == (logicalHigh ^ invert));
  }
  assert(gpioTrace[trace.size() + baseline].pin == 5 &&
         !gpioTrace[trace.size() + baseline].high);
  assert(gpioTrace[trace.size() + baseline + 1].pin == 6 &&
         !gpioTrace[trace.size() + baseline + 1].high);
}

static void runCase(uint32_t start, const std::vector<uint8_t> &bits,
                    int phase) {
  frameLen = (uint8_t)bits.size();
  for (uint8_t i = 0; i < frameLen; ++i) frameBits[i] = bits[i];
  txPhaseEighths = phase;
  sweepInvert = 0;
  sweepSwap = 0;
  std::vector<ExpectedEvent> want = expected(start, bits, phase);
  trace.clear();
  gpioTrace.clear();
  // Reset the simulated 32-bit AVR clock for every call, beginning at the
  // earliest event so negative phase offsets are physically representable.
  fakeNow = want.front().at;
  fakeReads = 0;
  emitCells(start, 0, 0);
  assert(txMaxLatenessUs == 0);
  assert(trace.size() == want.size());
  for (size_t i = 0; i < want.size(); ++i) {
    assert(trace[i].intended == want[i].at);
    assert(trace[i].actual == want[i].at);
    assert(trace[i].type == want[i].type);
  }
  checkGpioTrace();
}

#if RX_SWEEP || FREE_TX || RX_NARROW
static std::string framedWire() {
  std::string wire;
  for (uint8_t i = 0; i < frameLen; ++i)
    wire += (frameBits[i] ^ sweepInvert) ? '1' : '0';
  return wire;
}
#endif

static void checkStockFraming() {
#if RX_SWEEP || FREE_TX || RX_NARROW
  const std::string raw = "0000000000000000" "1111111111111111" "10010110";
  const std::string zeroStuff = "0000000000000000" "1111101111101111101" "10010110";
  const std::string oneStuff = "0000010000010000010" "1111111111111111" "10010110";
  for (uint8_t flag = 0; flag < 2; ++flag) {
    for (uint8_t polarity = 0; polarity < 2; ++polarity) {
      rxFlagIdx = flag;
      rxPolIdx = polarity;
      sweepInvert = polarity;
      selectStockStuffing();
      const uint8_t wanted = STOCK_STUFFING_MODE < 0
          ? (uint8_t)((flag ? 1 : 2) ^ 0) : (uint8_t)STOCK_STUFFING_MODE;
      const uint8_t effective = STOCK_STUFFING_MODE < 0 && polarity && wanted
          ? (uint8_t)(3 - wanted) : wanted;
      assert(wireStuffingMode() == effective);
      assert(wireFlagByte() == (uint8_t)((flag ? 0x7E : 0x81) ^
                                        (polarity ? 0xFF : 0)));
      buildReply(9);
      std::string body = stuffingMode == 0 ? raw :
                         stuffingMode == 1 ? zeroStuff : oneStuff;
      if (polarity)
        for (char &bit : body) bit = bit == '0' ? '1' : '0';
      const std::string flagBits = wireFlagByte() == 0x7E ?
                                   "01111110" : "10000001";
      assert(framedWire() == flagBits + body +
             (STOCK_CLOSE_FLAG ? flagBits : ""));
      assert(replyPayloadLen == 5);
      assert(replyPayload[0] == 0 && replyPayload[1] == 0 &&
             replyPayload[2] == 0xFF && replyPayload[3] == 0xFF &&
             replyPayload[4] == 0x96);
    }
  }
  sweepInvert = 0;
#endif
}

static void checkSampleMargins() {
  for (uint8_t swap = 0; swap < 2; ++swap) {
    for (uint8_t clockInvert = 0; clockInvert < 2; ++clockInvert) {
      for (uint8_t dataInvert = 0; dataInvert < 2; ++dataInvert) {
        for (int phase : {-2, 2}) {
          frameLen = 2;
          frameBits[0] = frameBits[1] = 1;
          sweepInvert = 0;
          sweepSwap = swap;
          txClockLevelInvert = clockInvert;
          txDataLevelInvert = dataInvert;
          txPhaseEighths = phase;
          fakeNow = 1000;
          fakeReads = 0;
          trace.clear();
          gpioTrace.clear();
          emitCells(1000, 0, 0);
          checkGpioTrace();
          // At -2/8, the sampled first 1 is established 30 us before the
          // clock rise and held for 46 us. At +2/8, the second clock rise
          // samples the low interval between pulses: setup 16, hold 30 us.
          const uint32_t clockRise = phase == -2 ? 1030 : 1152;
          const uint32_t dataBefore = phase == -2 ? 1000 : 1136;
          const uint32_t dataAfter = phase == -2 ? 1076 : 1182;
          assert(clockRise - dataBefore == (phase == -2 ? 30u : 16u));
          assert(dataAfter - clockRise == (phase == -2 ? 46u : 30u));
          auto has = [](uint8_t type, uint32_t at) {
            return std::any_of(trace.begin(), trace.end(),
                               [=](const TraceEvent &e) {
                                 return e.type == type && e.actual == at;
                               });
          };
          assert(has(1, clockRise));
          assert(has(phase == -2 ? 0 : 3, dataBefore));
          assert(has(phase == -2 ? 3 : 0, dataAfter));
          if (phase == 2) {
            // The first falling clock edge samples a 1 with 31 us of
            // setup and 45 us of hold in this candidate phase.
            assert(has(0, 1060));
            assert(has(2, 1091));
            assert(has(3, 1136));
            assert(1091u - 1060u == 31u);
            assert(1136u - 1091u == 45u);
          }
        }
      }
    }
  }
  txClockLevelInvert = txDataLevelInvert = 0;
  sweepSwap = 0;
}

static void checkTerminalStuffing() {
#if RX_SWEEP || FREE_TX || RX_NARROW
  rxFlagIdx = 0;
#endif
  for (uint8_t mode = 1; mode <= 2; ++mode) {
    stuffingMode = mode;
    frameLen = 0;
    uint8_t run = 0;
    putFlag();
    putStuffedByte(mode == 1 ? 0x1F : 0xE0, &run);
    assert(run == 5);
    putClosingFlag(&run);
    std::string bits;
    for (uint8_t i = 0; i < frameLen; ++i)
      bits += frameBits[i] ? '1' : '0';
    assert(bits == std::string("10000001") +
           (mode == 1 ? "000111110" : "111000001") + "10000001");
  }
}

int main() {
  clkReg = &PORTD;
  datReg = &PORTD;
  clkMask = 0x01;
  datMask = 0x02;

  for (int phase : {-4, -2, -1, 0, 2, 4}) {
    for (const std::vector<uint8_t> &bits : {
        std::vector<uint8_t>{1, 1, 1},
        std::vector<uint8_t>{1, 0},
        std::vector<uint8_t>{1, 0, 1},
        std::vector<uint8_t>{0, 1, 0}}) {
      runCase(100, bits, phase);
    }
  }

  // Both optical assignments and all four active-level combinations must
  // reach the requested physical pins and return both LEDs to dark.
  for (uint8_t swap = 0; swap < 2; ++swap) {
    for (uint8_t clockInvert = 0; clockInvert < 2; ++clockInvert) {
      for (uint8_t dataInvert = 0; dataInvert < 2; ++dataInvert) {
        runCase(1000, {1, 0, 1}, -2);
        sweepSwap = swap;
        txClockLevelInvert = clockInvert;
        txDataLevelInvert = dataInvert;
        trace.clear();
        gpioTrace.clear();
        fakeNow = 1000;
        fakeReads = 0;
        emitCells(1000, 0, 0);
        assert(txMaxLatenessUs == 0);
        checkGpioTrace();
      }
    }
  }
  txClockLevelInvert = txDataLevelInvert = 0;
  sweepSwap = 0;

  // A +4/8 phase intentionally shifts the pulse into the following sample;
  // the test documents that waveform consequence rather than pretending the
  // phase sweep must decode to the original logical bits.
  frameLen = 2;
  frameBits[0] = 1;
  frameBits[1] = 0;
  txPhaseEighths = 4;
  std::vector<ExpectedEvent> want = expected(100, {1, 0}, 4);
  fakeNow = want.front().at;
  fakeReads = 0;
  trace.clear();
  gpioTrace.clear();
  emitCells(100, 0, 0);
  assert(txMaxLatenessUs == 0);
  assert(sampled(trace) == (std::vector<uint8_t>{0, 1}));
  checkGpioTrace();

  checkStockFraming();
  checkSampleMargins();
  checkTerminalStuffing();

  // Exercise both sides of the explicit 32-bit micros() wrap.
  for (uint32_t start : {0x7fffff00u, 0xffffff00u})
    runCase(start, {1, 0, 1}, -2);

  // Exercise the exact current feedback stimulus through the new simple
  // dispatch path: five lead clocks followed by the candidate 7Eh bits.
  const std::vector<uint8_t> flagBits{0, 1, 1, 1, 1, 1, 1, 0};
  frameLen = (uint8_t)flagBits.size();
  for (uint8_t i = 0; i < frameLen; ++i) frameBits[i] = flagBits[i];
  txPhaseEighths = -2;
  sweepInvert = 0;
  const uint32_t feedbackStart = 1000;
  fakeNow = feedbackStart;
  fakeReads = 0;
  trace.clear();
  gpioTrace.clear();
  emitCells(feedbackStart, 5, 0);
  assert(txMaxLatenessUs == 0);
  const std::vector<uint8_t> feedbackSampled = sampled(trace);
  assert(feedbackSampled.size() == 13);
  assert(std::vector<uint8_t>(feedbackSampled.begin() + 5,
                              feedbackSampled.end()) == flagBits);
  assert(std::count_if(trace.begin(), trace.end(),
                       [](const TraceEvent &e) { return e.type == 0; }) == 6);
  checkGpioTrace();

#if RX_SWEEP || FREE_TX || RX_NARROW
  rxFlagIdx = 0;
#endif
  stuffingMode = 2;
  buildReply(5);
  std::string wire;
  for (uint8_t i = 0; i < frameLen; ++i)
    wire += frameBits[i] ? '1' : '0';
  const std::string flag = "10000001";
  size_t closing = wire.find(flag, 8);
  assert(closing != std::string::npos);
  size_t trailingZeros = 0;
  while (trailingZeros < closing &&
         wire[closing - 1 - trailingZeros] == '0') ++trailingZeros;
  assert(trailingZeros < 5);

#if STOCK_CONTEXT_EVENTS
  // Rising from a low level present at startup has no known pulse onset.
  stockEventHead = stockEventTail = 0;
  stockEventDrops = 0;
  stockYellowWasHigh = false;
  stockYellowHaveFall = false;
  PINB = _BV(PB0);
  fakeNow = 100;
  PCINT0_vect();
  assert(stockEventHead == 0);
  PINB = 0;
  fakeNow = 200;
  PCINT0_vect();
  PINB = _BV(PB0);
  fakeNow = 70000;
  PCINT0_vect();
  assert(stockEventHead == 1);
  assert(stockEvents[0].riseUs == 70000);
  assert(stockEvents[0].lowUs == 69800);  // no 16-bit width clamp
  Serial.writable = 0;
  stockDrainYellowEvents();
  assert(stockEventTail == 0);
  Serial.writable = 64;
  stockDrainYellowEvents();
  assert(stockEventTail == 1);
  assert(Serial.output.find("rise_us=70000 low_us=69800\n") != std::string::npos);
  stockEventHead = stockEventTail = 0;
  // A full ring counts losses beyond 255 instead of wrapping to zero.
  stockEventHead = 7;
  stockEventTail = 0;
  stockEventDrops = 255;
  for (int i = 0; i < 2; ++i) {
    PINB = 0;
    PCINT0_vect();
    PINB = _BV(PB0);
    PCINT0_vect();
  }
  assert(stockEventDrops == 257);
  stockEventDrops = 0xFFFFU;
  PINB = 0;
  PCINT0_vect();
  PINB = _BV(PB0);
  PCINT0_vect();
  assert(stockEventDrops == 0xFFFFU);
  stockEventTail = stockEventHead;
  Serial.writable = 0;
  stockDrainYellowEvents();
  assert(stockEventDrops == 0xFFFFU);
  Serial.writable = 64;
  stockDrainYellowEvents();
  assert(stockEventDrops == 0);
  assert(Serial.output.find("# STOCK_YELLOW_DROPS 65535\n") !=
         std::string::npos);
#endif

#if STOCK_CONTEXT_EVENTS && (FREE_TX || RX_NARROW)
  setup();
  assert(sweepSwap == STOCK_TX_SWAP);
  assert(txClockLevelInvert == STOCK_CLOCK_INVERT);
  assert(txDataLevelInvert == STOCK_DATA_INVERT);
#if STOCK_FIXED_CANDIDATE
  assert(rxFlagIdx == STOCK_FLAG_IDX);
  assert(rxPhaseIdx == STOCK_PHASE_IDX);
  assert(rxPolIdx == STOCK_POL_IDX);
  assert(rxContentIdx == STOCK_CONTENT_IDX);
  advanceSweep();
  assert(sweepSwap == STOCK_TX_SWAP);
  assert(rxFlagIdx == STOCK_FLAG_IDX);
  assert(rxPhaseIdx == STOCK_PHASE_IDX);
  assert(rxPolIdx == STOCK_POL_IDX);
  assert(rxContentIdx == STOCK_CONTENT_IDX);
#if RX_NARROW && STOCK_REPLY_DELAY_COUNT > 1
  assert(stockReplyDelayUs() ==
         STOCK_REPLY_DELAY_US + STOCK_REPLY_DELAY_STEP_US);
  for (int i = 1; i < STOCK_REPLY_DELAY_COUNT; ++i) advanceSweep();
  assert(stockReplyDelayUs() == STOCK_REPLY_DELAY_US);
#endif
#if RX_NARROW && STOCK_REPLY_EVERY_N > 1
  for (int i = 0; i < STOCK_REPLY_EVERY_N * 2; ++i)
    assert(stockReplyDue() == (i % STOCK_REPLY_EVERY_N == 0));
#endif
#elif RX_NARROW && RX_NARROW_AXIS == 3
  advanceSweep();
  assert(sweepSwap == (STOCK_TX_SWAP ^ 1));
  advanceSweep();
  assert(sweepSwap == STOCK_TX_SWAP);
#endif
#endif

  puts("host emitter chronology/phase/wrap/stuffing: ok");
  return 0;
}
