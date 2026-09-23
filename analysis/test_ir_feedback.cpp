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
struct PwmEvent { uint32_t at; uint8_t pin; uint8_t duty; };
static std::vector<PwmEvent> pwmEvents;
static void irHostGpio(uint8_t pin, bool high) {
  gpioEvents.push_back(GpioEvent{hostNow, pin, high, true, false});
}

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
void analogWrite(uint8_t pin, int duty) {
  pwmEvents.push_back(PwmEvent{hostNow, pin, (uint8_t)duty});
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
  size_t firstGpioEvent;
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
  const size_t firstGpioEvent = gpioEvents.size();
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
  return TrialObservation{firstIrEvent, firstGpioEvent, ackAt, fbReleaseAt, fbStartAt};
}

static std::vector<uint8_t> resultRecord(uint8_t mode, uint16_t sequence,
                                         uint8_t error = 0, uint8_t version = 1) {
  std::vector<uint8_t> result(30, 0);
  result[0] = 0xA5;
  result[1] = 0x5A;
  result[2] = version;
  result[3] = mode;
  result[4] = (uint8_t)sequence;
  result[5] = (uint8_t)(sequence >> 8);
  result[6] = error;
  result[10] = result[11] = 0xFF;
  if (version == 2 && mode >= 5 && mode <= 7) result[17] = 8;
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

static void expectSuccessfulResult(uint8_t mode, uint16_t sequence,
                                   uint8_t version = 1) {
  deliverResult(resultRecord(mode, sequence, 0, version));
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
static uint32_t nextVisualId = 1;

static std::string command(uint32_t id, char hold, char kind, int swap,
                           const char *payload = "03", int clkInv = -1,
                           int datInv = -1) {
  std::ostringstream text;
  text << "T " << id << ' ' << hold << ' ' << kind << ' ' << swap
       << " 7E 0 0 0 -2 3 1000 " << payload;
  if (clkInv >= 0 && datInv >= 0) text << ' ' << clkInv << ' ' << datInv;
  return text.str();
}

static std::string repeatCommand(uint32_t id, uint8_t count, uint8_t gapMs,
                                 uint16_t delayUs = 1000,
                                 uint8_t clkInv = 0, uint8_t datInv = 0) {
  std::ostringstream text;
  text << "T " << id << " G X 0 7E 0 0 0 -2 3 " << delayUs
       << " 03 " << (unsigned)clkInv << ' ' << (unsigned)datInv
       << ' ' << (unsigned)count << ' ' << (unsigned)gapMs;
  return text.str();
}

static void opticalInversionTrials() {
  for (int swap = 0; swap < 2; ++swap) {
    for (int clkInv = 0; clkInv < 2; ++clkInv) {
      for (int datInv = 0; datInv < 2; ++datInv) {
        TrialObservation trial = beginTrial(
            command(nextId++, 'W', 'X', swap, "03", clkInv, datInv), 100000);
        spinUntil([] { return !fbEmitPending; }, 5000);
        const uint8_t clockPin = swap ? 6 : 5;
        const uint8_t dataPin = swap ? 5 : 6;
        assertOneBurst(trial.firstIrEvent, clockPin, dataPin);
        CHECK(fbConfig.clockInvert == clkInv && fbConfig.dataInvert == datInv);
        CHECK(contains("clk_inv=" + std::to_string(clkInv)));
        CHECK(contains("dat_inv=" + std::to_string(datInv)));

        const uint32_t baselineAt = trial.startAt + 1000U;
        bool sawClockBaseline = false, sawDataBaseline = false;
        for (size_t i = trial.firstGpioEvent; i < gpioEvents.size(); ++i) {
          const GpioEvent &gpio = gpioEvents[i];
          if ((uint32_t)(gpio.at - baselineAt) > 4U) continue;
          if (gpio.pin == clockPin) {
            CHECK(gpio.latch == (clkInv != 0)); sawClockBaseline = true;
          } else if (gpio.pin == dataPin) {
            CHECK(gpio.latch == (datInv != 0)); sawDataBaseline = true;
          }
        }
        if (clkInv || datInv) CHECK(sawClockBaseline && sawDataBaseline);

        bool clockLevel = clkInv != 0, dataLevel = datInv != 0;
        for (size_t i = trial.firstIrEvent; i < irEvents.size(); ++i) {
          const IrEvent &event = irEvents[i];
          if (event.type == 1) clockLevel = !clkInv;
          else if (event.type == 2) clockLevel = clkInv;
          else if (event.type == 0) dataLevel = !datInv;
          else dataLevel = datInv;
          bool found = false, levelAtEvent = false;
          for (size_t gpioIndex = 0; gpioIndex < gpioEvents.size(); ++gpioIndex) {
            const GpioEvent &gpio = gpioEvents[gpioIndex];
            if (gpio.pin == event.physicalPin &&
                (uint32_t)(gpio.at - event.actual) <= 3U) {
              found = true; levelAtEvent = gpio.latch;
            }
          }
          CHECK(found);
          CHECK(levelAtEvent == (event.physicalPin == clockPin
                                     ? clockLevel : dataLevel));
        }
        CHECK((PORTD & (1U << 5)) == 0 && (PORTD & (1U << 6)) == 0);
        expectSuccessfulResult(1, fbExpectedSequence);
        waitReady();
      }
    }
  }

  // With no lead and phase=-4, the first data edge precedes startUs.
  // Inversion must establish its baseline before that edge, not delay it.
  const uint32_t earlyId = nextId++;
  TrialObservation early = beginTrial(
      "T " + std::to_string(earlyId) +
      " W X 0 -- 0 0 0 -4 0 1000 80 1 1", 100000);
  spinUntil([] { return !fbEmitPending; }, 5000);
  CHECK(irEvents.size() > early.firstIrEvent);
  CHECK(irEvents[early.firstIrEvent].type == 0);
  CHECK(irEvents[early.firstIrEvent].requested == early.startAt + 1000U - 31U);
  CHECK((uint32_t)(irEvents[early.firstIrEvent].actual -
                   irEvents[early.firstIrEvent].requested) <= 16U);
  CHECK((PORTD & ((1U << 5) | (1U << 6))) == 0);
  expectSuccessfulResult(1, fbExpectedSequence);
  waitReady();

  TrialObservation silent = beginTrial(
      command(nextId++, 'W', 'S', 1, "03", 1, 1), 100000);
  advanceUs(2000);
  CHECK(irEvents.size() == silent.firstIrEvent);
  CHECK((PORTD & ((1U << 5) | (1U << 6))) == 0);
  expectSuccessfulResult(1, fbExpectedSequence);
  waitReady();
}

static void inversionParserRejections() {
  const uint32_t badIds[] = {nextId++, nextId++, nextId++, nextId++, nextId++};
  const std::string base = "T ";
  const std::string commands[] = {
      "T " + std::to_string(badIds[0]) + " W S 0 7E 0 0 0 -2 3 1000 03 2 0",
      "T " + std::to_string(badIds[1]) + " W S 0 7E 0 0 0 -2 3 1000 03 0 2",
      "T " + std::to_string(badIds[2]) + " W S 0 7E 0 0 0 -2 3 1000 03 0",
      "T " + std::to_string(badIds[3]) + " W S 0 7E 0 0 0 -2 3 1000 03 0 0 extra",
      base + std::to_string(badIds[4]) + " Q S 0 7E 0 0 0 -2 3 1000 03"};
  for (size_t i = 0; i < 5; ++i) {
    send(commands[i] + "\n");
    CHECK(fbState == FB_IDLE && fbReady && contains("reason=command"));
  }
}

static void successfulTrials() {
  TrialObservation w = beginTrial(command(nextId++, 'W', 'S', 0), 100000);
  advanceUs(2000);
  CHECK(irEvents.size() == w.firstIrEvent);
  expectSuccessfulResult(1, 0xFFFE);
  waitReady();

  TrialObservation r = beginTrial(command(nextId++, 'R', 'X', 0), 300000);
  CHECK(fbConfig.clockInvert == 0 && fbConfig.dataInvert == 0);
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

  TrialObservation h = beginTrial(command(nextId++, 'H', 'S', 0), 575000);
  advanceUs(2000);
  CHECK(irEvents.size() == h.firstIrEvent);
  expectSuccessfulResult(5, 2, 2);
  waitReady();

  TrialObservation j = beginTrial(command(nextId++, 'J', 'X', 1), 625000);
  spinUntil([] { return !fbEmitPending; }, 5000);
  assertOneBurst(j.firstIrEvent, 6, 5);
  expectSuccessfulResult(6, 3, 2);
  CHECK(fbExpectedSequence == 4);
  waitReady();

  TrialObservation k = beginTrial(command(nextId++, 'K', 'S', 0), 400000);
  advanceUs(2000);
  CHECK(irEvents.size() == k.firstIrEvent);
  expectSuccessfulResult(7, 4, 2);
  CHECK(fbExpectedSequence == 5);
  waitReady();
}

static void v2RecordValidation() {
  TrialObservation h = beginTrial(command(nextId++, 'H', 'S', 0), 575000);
  advanceUs(2000);
  (void)h;
  // v2 status bytes 18-25 are opaque to the Uno's raw-RX checks.
  std::vector<uint8_t> record = resultRecord(5, fbExpectedSequence, 0, 2);
  record[15] = 0xFF; record[16] = 0xFF; record[17] = 8;
  uint8_t sum = 0;
  for (size_t i = 0; i < record.size() - 1; ++i) sum += record[i];
  record[29] = (uint8_t)(0U - sum);
  deliverResult(record);
  CHECK(fbState == FB_IDLE && contains("RESULT id="));
  waitReady();

  TrialObservation badSlot = beginTrial(command(nextId++, 'J', 'S', 0), 625000);
  advanceUs(2000);
  (void)badSlot;
  record = resultRecord(6, fbExpectedSequence, 0, 2);
  record[17] = 7;
  sum = 0;
  for (size_t i = 0; i < record.size() - 1; ++i) sum += record[i];
  record[29] = (uint8_t)(0U - sum);
  deliverResult(record);
  CHECK(fbState == FB_DESYNC && contains("reason=result"));
  resyncAndReady();

  TrialObservation next = beginTrial(command(nextId++, 'K', 'S', 0), 400000);
  advanceUs(2000);
  (void)next;
  deliverResult(resultRecord(8, fbExpectedSequence, 0, 2));
  CHECK(fbState == FB_DESYNC && contains("reason=result"));
  resyncAndReady();
}

static void repeatedBurstTrials() {
  const uint32_t id = nextId++;
  TrialObservation trial = beginTrial(repeatCommand(id, 3, 23, 1000, 1, 0), 700000);
  CHECK(fbConfig.repeatCount == 3 && fbConfig.repeatGapMs == 23);
  CHECK(fbConfig.clockInvert == 1 && fbConfig.dataInvert == 0);
  CHECK(contains("clk_inv=1") && contains("dat_inv=0"));
  spinUntil([] { return !fbEmitPending; }, 90000);
  CHECK(irEvents.size() > trial.firstIrEvent);
  std::vector<std::vector<uint8_t> > bursts;
  std::vector<uint8_t> current;
  uint32_t previousAt = 0;
  for (size_t i = trial.firstIrEvent; i < irEvents.size(); ++i) {
    const IrEvent &event = irEvents[i];
    if (!current.empty() && event.actual - previousAt > 1000U) {
      bursts.push_back(current); current.clear();
    }
    current.push_back(event.type);
    previousAt = event.actual;
  }
  if (!current.empty()) bursts.push_back(current);
  CHECK(bursts.size() == 3);
  CHECK(bursts[0] == bursts[1] && bursts[1] == bursts[2]);
  CHECK((uint32_t)(irEvents.back().actual - trial.startAt) < 80000U);
  for (size_t i = 1; i < bursts.size(); ++i) {
    const uint32_t firstAt = irEvents[trial.firstIrEvent].actual;
    size_t index = trial.firstIrEvent;
    for (size_t n = 0; n < i; ++n) index += bursts[n].size();
    const uint32_t delta = irEvents[index].actual - firstAt;
    CHECK(delta >= i * 23000U && delta <= i * 23000U + 1000U);
  }
  CHECK((uint32_t)(hostNow - trial.startAt) < 80000U);
  expectSuccessfulResult(4, fbExpectedSequence);
  waitReady();
}

static void repeatCommandRejections() {
  const char *suffixes[] = {" 1 10", " 4 10", " 2 0", " 2 61", " 3 30"};
  const char *bases[] = {
      "T %u G X 0 7E 0 0 0 -2 3 1000 03 0 0",
      "T %u G X 0 7E 0 0 0 -2 3 1000 03 0 0",
      "T %u G X 0 7E 0 0 0 -2 3 1000 03 0 0",
      "T %u G X 0 7E 0 0 0 -2 3 1000 03 0 0",
      "T %u G S 0 7E 0 0 0 -2 3 1000 03 0 0"};
  for (size_t i = 0; i < sizeof(suffixes) / sizeof(suffixes[0]); ++i) {
    char prefix[96];
    snprintf(prefix, sizeof(prefix), bases[i], (unsigned)nextId++);
    send(std::string(prefix) + suffixes[i] + "\n");
    CHECK(fbState == FB_IDLE && fbReady && contains("reason=command"));
  }
  // 60 ms delay + two 10 ms gaps + 26 ms worst-case frame exceeds 80 ms.
  char prefix[96];
  snprintf(prefix, sizeof(prefix), "T %u G X 0 7E 0 0 0 -2 3 60000 03 0 0",
           (unsigned)nextId++);
  send(std::string(prefix) + " 3 10\n");
  CHECK(fbState == FB_IDLE && fbReady && contains("reason=command"));
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
  startUart(resultRecord(0, (uint16_t)(fbExpectedSequence - 1), 1));
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
  CHECK(fbState == FB_IDLE && fbReady && contains("reason=command"));
  CHECK(!hostBlack);
  CHECK(!contains("send R"));
  const uint32_t afterDuplicate = nextId++;
  send(command(afterDuplicate, 'W', 'S', 0) + "\n");
  CHECK(fbState == FB_WAIT_ACK && fbLastId == afterDuplicate);
  send("C " + std::to_string(afterDuplicate) + "\n");
  CHECK(fbState == FB_DESYNC && contains("reason=cancel") && contains("send R"));
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
  CHECK(fbState == FB_IDLE && fbReady && contains("reason=command"));
  CHECK(!hostBlack && !fbEmitPending);
  const uint32_t afterMalformed = nextId++;
  send(command(afterMalformed, 'W', 'S', 0) + "\n");
  CHECK(fbState == FB_WAIT_ACK && fbLastId == afterMalformed);
  send("C " + std::to_string(afterMalformed) + "\n");
  CHECK(fbState == FB_DESYNC && contains("reason=cancel"));
  resyncAndReady();

  Serial.clearOutput();
  send("T 999 W");
  CHECK(fbParser.pending());
  advanceUs(1001000);
  CHECK(fbState == FB_IDLE && fbReady && contains("reason=serial_timeout"));
  CHECK(!hostBlack && !fbEmitPending);
  // The timed-out line remains in discard-through-newline mode; terminate
  // that physical line before sending the next command.
  send("\n");
  const uint32_t afterTimeout = nextId++;
  send(command(afterTimeout, 'W', 'S', 0) + "\n");
  CHECK(fbState == FB_WAIT_ACK && fbLastId == afterTimeout);
  send("C " + std::to_string(afterTimeout) + "\n");
  CHECK(fbState == FB_DESYNC && contains("reason=cancel"));
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
  CHECK(fbState == FB_IDLE && fbReady && contains("reason=command"));
  CHECK(!hostBlack && !fbEmitPending && irEvents.size() == before);
  const uint32_t afterBadPayload = nextId++;
  send(command(afterBadPayload, 'W', 'S', 0) + "\n");
  CHECK(fbState == FB_WAIT_ACK && fbLastId == afterBadPayload);
  send("C " + std::to_string(afterBadPayload) + "\n");
  CHECK(fbState == FB_DESYNC && contains("reason=cancel"));
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

static void cameraVisibleLedCheck() {
  waitReady();
  Serial.clearOutput();
  const uint32_t id = nextVisualId++;
  const uint32_t trialIdBefore = fbLastId;
  const size_t before = pwmEvents.size();
  send("V " + std::to_string(id) + "\n");
  CHECK(fbState == FB_VISUAL_RUN && !fbReady);
  CHECK(contains("VISUAL visual_id=" + std::to_string(id) + " trial_id=unchanged channel=A pin=D5 duty=10%"));
  CHECK(pwmEvents.size() == before + 2);
  CHECK(pwmEvents[before].pin == 5 && pwmEvents[before].duty == 26);
  CHECK(pwmEvents[before + 1].pin == 6 && pwmEvents[before + 1].duty == 0);
  advanceUs(1490000);
  CHECK(fbState == FB_VISUAL_RUN && pwmEvents.size() == before + 2);
  advanceUs(20000);
  CHECK(fbState == FB_VISUAL_RUN && pwmEvents.size() == before + 4);
  CHECK(pwmEvents[before + 2].pin == 5 && pwmEvents[before + 2].duty == 0);
  CHECK(pwmEvents[before + 3].pin == 6 && pwmEvents[before + 3].duty == 26);
  CHECK(contains("channel=B pin=D6 duty=10%"));
  CHECK(fbLastId == trialIdBefore);
  advanceUs(1510000);
  CHECK(fbState == FB_IDLE && !fbReady);
  CHECK(pwmEvents[pwmEvents.size() - 2].pin == 5 && pwmEvents[pwmEvents.size() - 2].duty == 0);
  CHECK(pwmEvents[pwmEvents.size() - 1].pin == 6 && pwmEvents[pwmEvents.size() - 1].duty == 0);
  CHECK(contains("VISUAL_DONE visual_id=" + std::to_string(id)));
  waitReady();

  const uint32_t cancelId = nextVisualId++;
  Serial.clearOutput();
  send("V " + std::to_string(cancelId) + "\n");
  CHECK(fbState == FB_VISUAL_RUN);
  send("C " + std::to_string(cancelId) + "\n");
  CHECK(fbState == FB_IDLE && !fbReady);
  CHECK(contains("VISUAL_CANCELLED visual_id=" + std::to_string(cancelId)));
  CHECK(pwmEvents[pwmEvents.size() - 2].pin == 5 && pwmEvents[pwmEvents.size() - 2].duty == 0);
  CHECK(pwmEvents[pwmEvents.size() - 1].pin == 6 && pwmEvents[pwmEvents.size() - 1].duty == 0);
  waitReady();

  const size_t unchanged = pwmEvents.size();
  send("V " + std::to_string(cancelId) + "\n");
  CHECK(fbState == FB_VISUAL_RUN && pwmEvents.size() == unchanged + 2);
  CHECK(contains("VISUAL visual_id=" + std::to_string(cancelId) + " trial_id=unchanged channel=A"));
  send("C " + std::to_string(cancelId) + "\n");
  CHECK(fbState == FB_IDLE && !fbReady);
  CHECK(contains("VISUAL_CANCELLED visual_id=" + std::to_string(cancelId)));
  CHECK(pwmEvents[pwmEvents.size() - 2].pin == 5 && pwmEvents[pwmEvents.size() - 2].duty == 0);
  CHECK(pwmEvents[pwmEvents.size() - 1].pin == 6 && pwmEvents[pwmEvents.size() - 1].duty == 0);
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
  // USB camera check is available without a handheld ACK / READY input.
  setYellow(false);
  send("V 1\n");
  CHECK(fbState == FB_VISUAL_RUN && !hostBlack && fbLastId == 0);
  CHECK(contains("trial_id=unchanged"));
  send("C 1\n");
  CHECK(fbState == FB_IDLE && !hostBlack);
  CHECK(pwmEvents[pwmEvents.size() - 2].duty == 0 && pwmEvents[pwmEvents.size() - 1].duty == 0);
  CHECK(fbLastId == 0);
  nextVisualId = 2;
  setYellow(true);
  resyncAndReady();

  successfulTrials();
  v2RecordValidation();
  repeatedBurstTrials();
  preStartErrorNeverEmits();
  malformedResultCases();
  commandFailureCases();
  payloadAndEarlyEdgeCases();
  inversionParserRejections();
  repeatCommandRejections();
  opticalInversionTrials();
  cameraVisibleLedCheck();

  puts(BLACK_USE_NPN
           ? "feedback public state-machine integration (NPN): ok"
           : "feedback public state-machine integration (DIRECT_TTL): ok");
  return 0;
}
