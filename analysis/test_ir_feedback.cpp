#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include <deque>
#include <sstream>
#include <string>
#include <vector>

#define INPUT 0
#define OUTPUT 1
#define RISING 1
#define HEX 16
#define F(x) x
#define _BV(x) (1u << (x))
#define ISR(x) void x()
#define TIMER2_COMPA_vect timer2
#define WGM21 1
#define CS20 0
#define OCIE2A 1

#ifndef BLACK_USE_NPN
#error "host test must select BLACK_USE_NPN explicitly"
#endif

typedef char __FlashStringHelper;

volatile uint8_t PORTD = 0, PORTB = 0;
volatile uint8_t TCCR2A = 0, TCCR2B = 0, OCR2A = 0, TIMSK2 = 0;

static uint32_t hostNow = 0;
static bool hostYellow = true;
static bool hostD7Latch = false;
static bool hostD7Output = false;
static bool hostBlack = false;

struct GpioEvent {
  uint32_t at;
  uint8_t pin;
  bool latch;
  bool output;
  bool blackAsserted;
};

struct IrEvent {
  uint32_t requested;
  uint32_t actual;
  uint8_t type;
  uint8_t physicalPin;
};

static std::vector<GpioEvent> gpioEvents;
static std::vector<IrEvent> irEvents;

struct UartWaveform {
  bool active;
  uint32_t start;
  std::vector<uint8_t> bytes;
  int badStopByte;

  UartWaveform() : active(false), start(0), badStopByte(-1) {}

  bool level(uint32_t now) {
    if (!active) return hostYellow;
    if ((int32_t)(now - start) < 0) return true;
    const uint32_t elapsed = (uint32_t)(now - start);
    const uint32_t cell = elapsed / 833U;
    const uint32_t byteIndex = cell / 10U;
    const uint32_t bit = cell % 10U;
    if (byteIndex >= bytes.size()) {
      active = false;
      return true;
    }
    if (bit == 0) return false;
    if (bit == 9) return (int)byteIndex != badStopByte;
    return (bytes[byteIndex] & (uint8_t)(1U << (bit - 1))) != 0;
  }
} uartWave;

struct FakeSerial {
  std::deque<char> input;
  std::string output;

  void begin(unsigned long) {}
  int available() { return (int)input.size(); }
  int read() {
    if (input.empty()) return -1;
    const unsigned char value = (unsigned char)input.front();
    input.pop_front();
    return value;
  }
  void inject(const std::string &text) {
    input.insert(input.end(), text.begin(), text.end());
  }
  void clearOutput() { output.clear(); }

  void print(const char *value) { output += value; }
  void print(char value) { output += value; }
  void print(unsigned char value) { appendUnsigned(value, 10); }
  void print(signed char value) { appendSigned(value); }
  void print(unsigned short value) { appendUnsigned(value, 10); }
  void print(short value) { appendSigned(value); }
  void print(unsigned int value) { appendUnsigned(value, 10); }
  void print(int value) { appendSigned(value); }
  void print(unsigned long value) { appendUnsigned(value, 10); }
  void print(long value) { appendSigned(value); }
  void print(unsigned char value, int base) { appendUnsigned(value, base); }
  void print(unsigned int value, int base) { appendUnsigned(value, base); }
  void print(unsigned long value, int base) { appendUnsigned(value, base); }

  template <typename T> void println(T value) {
    print(value);
    output += '\n';
  }
  template <typename T> void println(T value, int base) {
    print(value, base);
    output += '\n';
  }
  void println() { output += '\n'; }
  void write(char value) { output += value; }

 private:
  void appendUnsigned(unsigned long value, int base) {
    if (base == 16) {
      static const char digits[] = "0123456789ABCDEF";
      char reversed[2 * sizeof(value) + 1];
      unsigned int count = 0;
      do {
        reversed[count++] = digits[value & 0xFU];
        value >>= 4;
      } while (value);
      while (count) output += reversed[--count];
      return;
    }
    std::ostringstream stream;
    stream << value;
    output += stream.str();
  }
  void appendSigned(long value) {
    std::ostringstream stream;
    stream << value;
    output += stream.str();
  }
} Serial;

unsigned long micros() { return hostNow++; }
void delayMicroseconds(unsigned long us) { hostNow += (uint32_t)us; }
void noInterrupts() {}
void interrupts() {}
static bool blackAssertedByD7() {
  if (!hostD7Output) return false;
  return BLACK_USE_NPN ? hostD7Latch : !hostD7Latch;
}
static void recordD7() {
  hostBlack = blackAssertedByD7();
  gpioEvents.push_back(
      GpioEvent{hostNow, 7, hostD7Latch, hostD7Output, hostBlack});
}
void pinMode(uint8_t pin, uint8_t mode) {
  if (pin == 7) {
    hostD7Output = mode == OUTPUT;
    recordD7();
  }
}
void attachInterrupt(int, void (*)(), int) {}
int digitalPinToInterrupt(uint8_t pin) { return pin; }
int digitalPinToPort(uint8_t pin) { return pin < 8 ? 0 : 1; }
uint8_t digitalPinToBitMask(uint8_t pin) { return (uint8_t)(1U << (pin & 7)); }
volatile uint8_t *portOutputRegister(int port) { return port ? &PORTB : &PORTD; }
void digitalWrite(uint8_t pin, uint8_t value) {
  if (pin == 7) {
    hostD7Latch = value != 0;
    recordD7();
  }
}
int digitalRead(uint8_t pin) {
  return pin == 8 ? (uartWave.level(hostNow) ? 1 : 0) : 0;
}

void irHostEvent(uint32_t requested, uint32_t actual, uint8_t type);

#define IR_HOST_TEST 1
#define FEEDBACK_HARNESS 1
#include "arduino/m1000_ir_probe/m1000_ir_probe.ino"

void irHostEvent(uint32_t requested, uint32_t actual, uint8_t type) {
  const bool clockEdge = type == 1 || type == 2;
  const uint8_t physicalPin = clockEdge ? (sweepSwap ? 6 : 5)
                                        : (sweepSwap ? 5 : 6);
  irEvents.push_back(IrEvent{requested, actual, type, physicalPin});
}

static void fail(const char *expression, int line) {
  fprintf(stderr, "CHECK failed at line %d: %s\n"
          "now=%u state=%u ready=%d highTrack=%d request=%d black=%d\n"
          "serial output:\n%s\n",
          line, expression, hostNow, (unsigned)fbState, fbReady,
          fbHighTracking, fbRequestLow, hostBlack, Serial.output.c_str());
  exit(1);
}

#define CHECK(x) do { if (!(x)) fail(#x, __LINE__); } while (0)

static bool contains(const std::string &needle) {
  return Serial.output.find(needle) != std::string::npos;
}

static void tick() { feedbackTick(); }

static void advanceUs(uint32_t duration, uint32_t step = 20) {
  const uint32_t began = hostNow;
  while ((uint32_t)(hostNow - began) < duration) {
    tick();
    hostNow += step;
  }
}

template <typename Predicate>
static void spinUntil(Predicate done, uint32_t limitUs) {
  const uint32_t began = hostNow;
  while (!done() && (uint32_t)(hostNow - began) < limitUs) {
    tick();
    hostNow += 20;
  }
  CHECK(done());
}

static void setYellow(bool high) {
  uartWave.active = false;
  hostYellow = high;
}

static void send(const std::string &line) {
  Serial.inject(line);
  tick();
}

static void waitReady() {
  setYellow(true);
  spinUntil([] { return fbReady; }, 110000);
  CHECK(fbState == FB_IDLE);
  CHECK(contains("READY\n"));
}

static void resyncAndReady() {
  Serial.clearOutput();
  setYellow(true);
  send("R\n");
  CHECK(fbState == FB_IDLE);
  CHECK(!fbReady);
  CHECK(!hostBlack);
  CHECK(contains("SYNC\n"));
#if BLACK_USE_NPN
  CHECK(contains("BLACK: NPN;"));
#else
  CHECK(contains("BLACK: DIRECT_TTL;"));
#endif
  advanceUs(90000);
  CHECK(!fbReady);
  advanceUs(12000);
  CHECK(fbReady);
  CHECK(contains("READY\n"));
}

struct TrialObservation {
  size_t firstIrEvent;
  uint32_t ackAt;
  uint32_t releaseAt;
  uint32_t startAt;
};

static TrialObservation beginTrial(const std::string &command,
                                   uint32_t expectedHoldUs) {
  CHECK(fbState == FB_IDLE);
  CHECK(fbReady);
  Serial.clearOutput();
  setYellow(true);
  const size_t firstIrEvent = irEvents.size();
  send(command + "\n");
  CHECK(fbState == FB_WAIT_ACK);
  CHECK(contains("TRIAL id="));
  spinUntil([] { return fbRequestLow; }, 110000);
  CHECK(hostBlack);

  setYellow(false);
  tick();
  CHECK(fbState == FB_HOLD);
  const uint32_t ackAt = fbAckAt;
  spinUntil([] { return fbState == FB_WAIT_START; }, expectedHoldUs + 1000);
  CHECK(!hostBlack);
  const uint32_t held = (uint32_t)(fbReleaseAt - ackAt);
  CHECK(held >= expectedHoldUs && held <= expectedHoldUs + 100);

  setYellow(true);
  advanceUs(50000);
  setYellow(false);
  tick();
  CHECK(fbState == FB_WAIT_RESULT);
  CHECK(fbStartAt != 0);
  return TrialObservation{firstIrEvent, ackAt, fbReleaseAt, fbStartAt};
}

static std::vector<uint8_t> resultRecord(uint8_t mode, uint16_t sequence,
                                         uint8_t error = 0) {
  std::vector<uint8_t> result(30, 0);
  result[0] = 0xA5;
  result[1] = 0x5A;
  result[2] = 1;
  result[3] = mode;
  result[4] = (uint8_t)sequence;
  result[5] = (uint8_t)(sequence >> 8);
  result[6] = error;
  result[10] = result[11] = 0xFF;
  result[26] = 0x02;
  uint8_t sum = 0;
  for (size_t i = 0; i < result.size() - 1; ++i) sum += result[i];
  result[29] = (uint8_t)(0U - sum);
  return result;
}

static void startUart(const std::vector<uint8_t> &bytes, int badStopByte = -1) {
  hostYellow = true;
  uartWave.bytes = bytes;
  uartWave.badStopByte = badStopByte;
  uartWave.start = hostNow + 80;
  uartWave.active = true;
}

static void deliverResult(const std::vector<uint8_t> &bytes,
                          int badStopByte = -1) {
  setYellow(false);
  advanceUs(100000);
  setYellow(true);
  advanceUs(20000);
  startUart(bytes, badStopByte);
  spinUntil([] { return fbState == FB_IDLE || fbState == FB_DESYNC; }, 400000);
  uartWave.active = false;
  hostYellow = true;
}

static void expectSuccessfulResult(uint8_t mode, uint16_t sequence) {
  deliverResult(resultRecord(mode, sequence));
  CHECK(fbState == FB_IDLE);
  CHECK(!hostBlack);
  CHECK(contains("RESULT id="));
  CHECK(contains(" mode=" + std::to_string(mode)));
  CHECK(!contains("ERROR"));
}

static void assertOneBurst(size_t first, uint8_t clockPin, uint8_t dataPin) {
  CHECK(irEvents.size() > first);
  bool sawClockRise = false, sawClockFall = false, sawData = false;
  for (size_t i = first; i < irEvents.size(); ++i) {
    if (irEvents[i].type == 1) {
      sawClockRise = true;
      CHECK(irEvents[i].physicalPin == clockPin);
    } else if (irEvents[i].type == 2) {
      sawClockFall = true;
      CHECK(irEvents[i].physicalPin == clockPin);
    } else {
      sawData = true;
      CHECK(irEvents[i].physicalPin == dataPin);
    }
  }
  CHECK(sawClockRise && sawClockFall && sawData);
  const size_t after = irEvents.size();
  advanceUs(5000);
  CHECK(irEvents.size() == after);
}

static uint32_t nextId = 1;

static std::string command(uint32_t id, char hold, char kind, int swap,
                           const char *payload = "03") {
  std::ostringstream text;
  text << "T " << id << ' ' << hold << ' ' << kind << ' ' << swap
       << " 7E 0 0 0 -2 3 1000 " << payload;
  return text.str();
}

static void successfulTrials() {
  TrialObservation w = beginTrial(command(nextId++, 'W', 'S', 0), 100000);
  advanceUs(2000);
  CHECK(irEvents.size() == w.firstIrEvent);
  expectSuccessfulResult(1, 0xFFFE);
  waitReady();

  TrialObservation r = beginTrial(command(nextId++, 'R', 'X', 0), 300000);
  spinUntil([] { return !fbEmitPending; }, 5000);
  assertOneBurst(r.firstIrEvent, 5, 6);
  expectSuccessfulResult(2, 0xFFFF);
  waitReady();

  TrialObservation p = beginTrial(command(nextId++, 'P', 'S', 1, "-"), 500000);
  advanceUs(2000);
  CHECK(irEvents.size() == p.firstIrEvent);
  expectSuccessfulResult(3, 0x0000);
  waitReady();

  TrialObservation g = beginTrial(command(nextId++, 'G', 'X', 1), 700000);
  spinUntil([] { return !fbEmitPending; }, 5000);
  assertOneBurst(g.firstIrEvent, 6, 5);
  expectSuccessfulResult(4, 0x0001);
  CHECK(fbHaveSequence && fbExpectedSequence == 2);
  waitReady();
}

static void preStartErrorNeverEmits() {
  Serial.clearOutput();
  setYellow(true);
  const size_t before = irEvents.size();
  send(command(nextId++, 'W', 'X', 0) + "\n");
  spinUntil([] { return fbRequestLow; }, 110000);
  setYellow(false);
  tick();
  spinUntil([] { return fbState == FB_WAIT_START; }, 101000);

  setYellow(true);
  advanceUs(20000);
  startUart(resultRecord(0, 1, 1));
  spinUntil([] { return fbState == FB_IDLE || fbState == FB_DESYNC; }, 400000);
  uartWave.active = false;
  hostYellow = true;
  CHECK(fbState == FB_IDLE);
  CHECK(contains(" mode=0"));
  CHECK(irEvents.size() == before);
  waitReady();
}

static void malformedResultCases() {
  beginTrial(command(nextId++, 'W', 'S', 0), 100000);
  std::vector<uint8_t> bad = resultRecord(1, 2);
  ++bad[29];
  deliverResult(bad);
  CHECK(fbState == FB_DESYNC && contains("reason=result"));
  resyncAndReady();

  beginTrial(command(nextId++, 'W', 'S', 0), 100000);
  deliverResult(resultRecord(2, 100));
  CHECK(fbState == FB_DESYNC && contains("reason=mode"));
  resyncAndReady();

  beginTrial(command(nextId++, 'W', 'S', 0), 100000);
  expectSuccessfulResult(1, 0x1234);
  waitReady();
  beginTrial(command(nextId++, 'W', 'S', 0), 100000);
  deliverResult(resultRecord(1, 0x1236));
  CHECK(fbState == FB_DESYNC && contains("reason=sequence"));
  resyncAndReady();

  beginTrial(command(nextId++, 'W', 'S', 0), 100000);
  deliverResult(resultRecord(1, 7), 2);
  CHECK(fbState == FB_DESYNC && contains("reason=uart_framing"));
  CHECK(!contains("RESULT id="));
  resyncAndReady();
}

static void commandFailureCases() {
  Serial.clearOutput();
  const size_t before = irEvents.size();
  setYellow(true);
  send(command(nextId++, 'W', 'X', 0) + "\n");
  spinUntil([] { return fbRequestLow; }, 110000);
  advanceUs(1501000);
  CHECK(fbState == FB_DESYNC && contains("reason=ack"));
  CHECK(!hostBlack && irEvents.size() == before);
  resyncAndReady();

  Serial.clearOutput();
  send(command(nextId - 1, 'W', 'S', 0) + "\n");
  CHECK(fbState == FB_DESYNC && contains("reason=command"));
  CHECK(!hostBlack);
  resyncAndReady();

  Serial.clearOutput();
  const uint32_t cancelId = nextId++;
  send(command(cancelId, 'R', 'X', 0) + "\n");
  CHECK(fbState == FB_WAIT_ACK);
  send("C " + std::to_string(cancelId) + "\n");
  CHECK(fbState == FB_DESYNC && contains("reason=cancel"));
  CHECK(!hostBlack && !fbEmitPending);
  resyncAndReady();

  Serial.clearOutput();
  send(std::string(110, 'X') + "\n");
  CHECK(fbState == FB_DESYNC && contains("reason=command"));
  CHECK(!hostBlack && !fbEmitPending);
  resyncAndReady();

  Serial.clearOutput();
  send("T 999 W");
  CHECK(fbParser.pending());
  advanceUs(1001000);
  CHECK(fbState == FB_DESYNC && contains("reason=serial_timeout"));
  CHECK(!hostBlack && !fbEmitPending);
  // The timed-out line remains in discard-through-newline mode; terminate
  // that physical line before sending the explicit resynchronisation line.
  send("\n");
  resyncAndReady();
}

static void payloadAndEarlyEdgeCases() {
  // The documented maximum is 16 bytes.  Exercise it through the command
  // path and verify every parsed byte before cancelling the armed trial.
  Serial.clearOutput();
  const uint32_t maxId = nextId++;
  send("T " + std::to_string(maxId) +
       " W S 0 -- 0 0 0 -4 0 0 000102030405060708090A0B0C0D0E0F\n");
  CHECK(fbState == FB_WAIT_ACK);
  CHECK(fbConfig.payloadLen == 16 && frameLen == 128);
  for (uint8_t i = 0; i < 16; ++i) CHECK(fbConfig.payload[i] == i);
  send("C " + std::to_string(maxId) + "\n");
  CHECK(fbState == FB_DESYNC && contains("reason=cancel"));
  resyncAndReady();

  // Seventeen bytes must be rejected without arming GPIO or emission.
  Serial.clearOutput();
  const size_t before = irEvents.size();
  send("T " + std::to_string(nextId++) +
       " W S 0 -- 0 0 0 -4 0 0 000102030405060708090A0B0C0D0E0F10\n");
  CHECK(fbState == FB_DESYNC && contains("reason=command"));
  CHECK(!hostBlack && !fbEmitPending && irEvents.size() == before);
  resyncAndReady();

  // With phase=-4, lead=0 and a first data bit of one, the data rise is
  // 31 us before the nominal cell origin.  The state machine must wake for
  // that edge rather than starting at the later cell origin.
  const uint32_t edgeId = nextId++;
  TrialObservation edge = beginTrial(
      "T " + std::to_string(edgeId) + " W X 0 -- 0 0 0 -4 0 1000 80",
      100000);
  spinUntil([] { return !fbEmitPending; }, 5000);
  CHECK(irEvents.size() > edge.firstIrEvent);
  const IrEvent &first = irEvents[edge.firstIrEvent];
  CHECK(first.type == 0);
  CHECK(first.requested == edge.startAt + 1000U - 31U);
  CHECK((uint32_t)(first.actual - first.requested) <= 25U);
  assertOneBurst(edge.firstIrEvent, 5, 6);
  expectSuccessfulResult(1, 42);
  waitReady();
}

int main() {
  hostNow = 0xFFFF0000U;
  hostYellow = true;
  setup();
  CHECK(contains("BOOT\n"));
#if BLACK_USE_NPN
  CHECK(contains("BLACK: NPN;"));
#else
  CHECK(contains("BLACK: DIRECT_TTL;"));
#endif
  CHECK(hostD7Output);
  CHECK(hostD7Latch == (BLACK_USE_NPN ? false : true));
  CHECK(!hostBlack);
  CHECK(gpioEvents.size() >= 3);
  for (size_t i = 0; i < gpioEvents.size(); ++i)
    CHECK(!gpioEvents[i].blackAsserted);
  resyncAndReady();

  successfulTrials();
  preStartErrorNeverEmits();
  malformedResultCases();
  commandFailureCases();
  payloadAndEarlyEdgeCases();

  puts(BLACK_USE_NPN
           ? "feedback public state-machine integration (NPN): ok"
           : "feedback public state-machine integration (DIRECT_TTL): ok");
  return 0;
}
