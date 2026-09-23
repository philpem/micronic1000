// Bounded, allocation-free command parser for the feedback harness.
// It intentionally records proposed wire choices without assigning protocol
// meaning to any byte or physical LED channel.
#ifndef M1000_FEEDBACK_HARNESS_H
#define M1000_FEEDBACK_HARNESS_H

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

enum FeedbackCommand : uint8_t {
  FB_NONE, FB_TRIAL, FB_CANCEL, FB_RESYNC, FB_BLACK_LOW, FB_BLACK_RELEASE,
  FB_VISUAL_TEST, FB_BAD
};

enum FeedbackMode : uint8_t { FB_SILENT, FB_STIMULUS };

struct FeedbackConfig {
  uint32_t trialId;
  uint8_t holdKind;       // W=100 ms, R=300 ms, P=500 ms, G=700 ms
  uint8_t mode;
  uint8_t swapRoles;      // 0: A/D5 clock, B/D6 data; 1: reversed
  uint8_t haveFlag;       // candidate start byte, no protocol meaning implied
  uint8_t flagByte;
  uint8_t stuffing;       // 0=none, 1=0 after five 1s, 2=1 after five 0s
  uint8_t closeFlag;
  uint8_t payload[16];    // worst stuffing + flags fits the 192-cell buffer
  uint8_t payloadLen;
  uint8_t polarity;
  int8_t phaseEighths;
  uint8_t leadCells;
  uint16_t delayUs;
  uint8_t clockInvert;    // optional physical level inversion (X only)
  uint8_t dataInvert;
};

inline bool fbUnsigned(const char *text, uint32_t limit, uint32_t *out) {
  if (!text || !*text) return false;
  uint32_t value = 0;
  for (const char *p = text; *p; ++p) {
    if (*p < '0' || *p > '9') return false;
    uint8_t digit = (uint8_t)(*p - '0');
    if (digit > limit || value > (limit - digit) / 10U) return false;
    value = value * 10U + digit;
  }
  *out = value;
  return true;
}

inline bool fbSigned(const char *text, int8_t *out) {
  if (!text || !*text) return false;
  bool negative = *text == '-';
  if (negative) ++text;
  uint32_t magnitude = 0;
  if (!fbUnsigned(text, 4, &magnitude)) return false;
  int8_t value = negative ? -(int8_t)magnitude : (int8_t)magnitude;
  if (value < -4 || value > 4) return false;
  *out = (int8_t)value;
  return true;
}

inline int8_t fbNibble(char ch) {
  if (ch >= '0' && ch <= '9') return (int8_t)(ch - '0');
  if (ch >= 'A' && ch <= 'F') return (int8_t)(ch - 'A' + 10);
  if (ch >= 'a' && ch <= 'f') return (int8_t)(ch - 'a' + 10);
  return -1;
}

inline bool fbByteHex(const char *text, uint8_t *out) {
  if (!text || text[0] == 0 || text[1] == 0 || text[2] != 0) return false;
  int8_t hi = fbNibble(text[0]), lo = fbNibble(text[1]);
  if (hi < 0 || lo < 0) return false;
  *out = (uint8_t)((hi << 4) | lo);
  return true;
}

inline bool fbHex(const char *text, uint8_t *dst, uint8_t *length) {
  *length = 0;
  if (!strcmp(text, "-")) return true;
  size_t n = strlen(text);
  if (!n || (n & 1) || n > 32) return false;
  for (size_t i = 0; i < n; i += 2) {
    char pair[3] = { text[i], text[i + 1], 0 };
    if (!fbByteHex(pair, &dst[*length])) return false;
    ++*length;
  }
  return true;
}

// Commands (ASCII, LF terminated, max 95 chars):
//   T id W|R|P|G S|X swap flag|-- stuff close pol phase lead delay_us payload
//     [clk_inv dat_inv]
//   C id
//   R
//   B id L|R
//   V id       bounded camera-visible check: LED A then LED B
// payload is even-length hex or '-'. With flag=-- it is literal MSB-first raw
// bytes; otherwise it follows the candidate flag. The fields are logged verbatim.
class FeedbackLineParser {
 public:
  FeedbackLineParser() : len_(0), discard_(false) { line_[0] = 0; }

  bool pending() const { return len_ != 0 && !discard_; }
  void timeout() { len_ = 0; discard_ = true; }

  FeedbackCommand feed(char ch, FeedbackConfig *cfg, uint32_t *id) {
    if (discard_) {
      if (ch == '\n') discard_ = false;
      return FB_NONE;
    }
    if (ch == '\r') return FB_NONE;
    if (ch != '\n' && (ch < ' ' || ch > '~')) {
      len_ = 0; discard_ = true; return FB_BAD;
    }
    if (ch != '\n') {
      if (len_ >= sizeof(line_) - 1) { len_ = 0; discard_ = true; return FB_BAD; }
      line_[len_++] = ch;
      return FB_NONE;
    }
    line_[len_] = 0; len_ = 0;
    return parse(cfg, id);
  }

 private:
  char line_[96];
  uint8_t len_;
  bool discard_;

  FeedbackCommand parse(FeedbackConfig *cfg, uint32_t *id) {
    char *parts[15];
    uint8_t count = 0;
    char *token = strtok(line_, " ");
    while (token && count < 15) { parts[count++] = token; token = strtok(0, " "); }
    if (token || !count) return FB_BAD;
    uint32_t parsedId = 0;
    if (count == 1 && !strcmp(parts[0], "R")) return FB_RESYNC;
    if (count == 2 && !strcmp(parts[0], "V") && fbUnsigned(parts[1], 0xFFFFFFFFUL, &parsedId)) {
      *id = parsedId; return FB_VISUAL_TEST;
    }
    if (count == 2 && !strcmp(parts[0], "C") && fbUnsigned(parts[1], 0xFFFFFFFFUL, &parsedId)) {
      *id = parsedId; return FB_CANCEL;
    }
    if (count == 3 && !strcmp(parts[0], "B") && fbUnsigned(parts[1], 0xFFFFFFFFUL, &parsedId)) {
      *id = parsedId;
      if (!strcmp(parts[2], "L")) return FB_BLACK_LOW;
      if (!strcmp(parts[2], "R")) return FB_BLACK_RELEASE;
      return FB_BAD;
    }
    if ((count != 13 && count != 15) || strcmp(parts[0], "T") ||
        !fbUnsigned(parts[1], 0xFFFFFFFFUL, &parsedId)) return FB_BAD;
    uint32_t value = 0;
    FeedbackConfig next = {};
    next.trialId = parsedId;
    if (strlen(parts[2]) != 1 || strchr("WRPG", parts[2][0]) == 0) return FB_BAD;
    next.holdKind = (uint8_t)parts[2][0];
    if (!strcmp(parts[3], "S")) next.mode = FB_SILENT;
    else if (!strcmp(parts[3], "X")) next.mode = FB_STIMULUS;
    else return FB_BAD;
    if (!fbUnsigned(parts[4], 1, &value)) return FB_BAD;
    next.swapRoles = (uint8_t)value;
    if (!strcmp(parts[5], "--")) next.haveFlag = 0;
    else if (fbByteHex(parts[5], &next.flagByte)) next.haveFlag = 1;
    else return FB_BAD;
    if (!fbUnsigned(parts[6], 2, &value)) return FB_BAD;
    next.stuffing = (uint8_t)value;
    if (!fbUnsigned(parts[7], 1, &value)) return FB_BAD;
    next.closeFlag = (uint8_t)value;
    if ((!next.haveFlag && (next.stuffing || next.closeFlag)) ||
        !fbHex(parts[12], next.payload, &next.payloadLen)) return FB_BAD;
    if (!fbUnsigned(parts[8], 1, &value)) return FB_BAD;
    next.polarity = (uint8_t)value;
    if (!fbSigned(parts[9], &next.phaseEighths) ||
        !fbUnsigned(parts[10], 16, &value)) return FB_BAD;
    next.leadCells = (uint8_t)value;
    if (!fbUnsigned(parts[11], 60000, &value)) return FB_BAD;
    next.delayUs = (uint16_t)value;
    if (count == 15) {
      if (!fbUnsigned(parts[13], 1, &value)) return FB_BAD;
      next.clockInvert = (uint8_t)value;
      if (!fbUnsigned(parts[14], 1, &value)) return FB_BAD;
      next.dataInvert = (uint8_t)value;
    }
    *cfg = next; *id = parsedId; return FB_TRIAL;
  }
};

#endif
