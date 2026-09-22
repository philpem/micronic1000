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
typedef char __FlashStringHelper;

volatile uint8_t PORTD = 0, PORTB = 0;
volatile uint8_t TCCR2A = 0, TCCR2B = 0, OCR2A = 0, TIMSK2 = 0;
struct SerialStub {
  void begin(unsigned long) {}
  int available() { return 0; }
  int read() { return -1; }
  template <typename T> void print(T) {}
  template <typename T> void print(T, int) {}
  template <typename T> void println(T) {}
  template <typename T> void println(T, int) {}
  void println() {}
  void write(char) {}
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

static void runCase(uint32_t start, const std::vector<uint8_t> &bits,
                    int phase) {
  frameLen = (uint8_t)bits.size();
  for (uint8_t i = 0; i < frameLen; ++i) frameBits[i] = bits[i];
  txPhaseEighths = phase;
  sweepInvert = 0;
  sweepSwap = 0;
  std::vector<ExpectedEvent> want = expected(start, bits, phase);
  trace.clear();
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
  emitCells(100, 0, 0);
  assert(txMaxLatenessUs == 0);
  assert(sampled(trace) == (std::vector<uint8_t>{0, 1}));

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
  emitCells(feedbackStart, 5, 0);
  assert(txMaxLatenessUs == 0);
  const std::vector<uint8_t> feedbackSampled = sampled(trace);
  assert(feedbackSampled.size() == 13);
  assert(std::vector<uint8_t>(feedbackSampled.begin() + 5,
                              feedbackSampled.end()) == flagBits);
  assert(std::count_if(trace.begin(), trace.end(),
                       [](const TraceEvent &e) { return e.type == 0; }) == 6);

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

  puts("host emitter chronology/phase/wrap/stuffing: ok");
  return 0;
}
