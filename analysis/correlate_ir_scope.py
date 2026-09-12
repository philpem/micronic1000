#!/usr/bin/env python3
"""Correlate an ordered IR scope decode without pretending its gaps are bits."""

from __future__ import annotations

import argparse
import collections
import json
import statistics
from pathlib import Path


def autocorrelation(values: list[str], max_lag: int) -> list[dict[str, object]]:
    result = []
    for lag in range(1, min(max_lag, len(values) - 1) + 1):
        pairs = len(values) - lag
        matches = sum(left == right for left, right in zip(values, values[lag:]))
        result.append({"lag": lag, "matches": matches, "pairs": pairs, "rate": matches / pairs})
    return result


def byte_bits(value: int, lsb_first: bool) -> str:
    bits = f"{value:08b}"
    return bits[::-1] if lsb_first else bits


def positions(stream: str, needle: str) -> list[int]:
    return [index for index in range(len(stream) - len(needle) + 1) if stream[index:index + len(needle)] == needle]


def repeated_ngrams(sequence: list[str], max_length: int = 6) -> list[dict[str, object]]:
    repeated = []
    for length in range(2, max_length + 1):
        counts = collections.Counter(
            "".join(sequence[index:index + length])
            for index in range(len(sequence) - length + 1)
        )
        repeated.extend(
            {"sequence": value, "length": length, "count": count}
            for value, count in counts.items()
            if count > 1
        )
    return sorted(repeated, key=lambda item: (-item["count"], item["length"], item["sequence"]))


def invert(bits: str) -> str:
    return "".join("1" if bit == "0" else "0" for bit in bits)


def common_suffix(strings: list[str]) -> str:
    limit = min(map(len, strings))
    for length in range(limit, -1, -1):
        suffix = strings[0][-length:] if length else ""
        if all(value.endswith(suffix) for value in strings):
            return suffix
    raise AssertionError("empty input")


def hdlc_tail(bits: str, flag_offset: int) -> dict[str, object]:
    tail = bits[flag_offset + 8:]
    unstuffed = []
    stuffed_zero_offsets = []
    one_run = 0
    for offset, bit in enumerate(tail):
        if bit == "1":
            one_run += 1
            unstuffed.append(bit)
            continue
        if one_run == 5:
            stuffed_zero_offsets.append(offset)
        else:
            unstuffed.append(bit)
        one_run = 0
    return {
        "bits_after_first_flag": tail,
        "additional_flag_offsets": [
            flag_offset + 8 + offset
            for offset in positions(tail, "01111110")
        ],
        "hdlc_unstuffed_bits_after_first_flag": "".join(unstuffed),
        "hdlc_stuffed_zero_offsets_after_first_flag": stuffed_zero_offsets,
    }


def inverted_line_tail(raw_bits: str, raw_flag_offset: int) -> dict[str, object]:
    """Remove the physical-one stuffing complementary to inverted HDLC."""
    tail = raw_bits[raw_flag_offset + 8:]
    decoded = []
    stuffed_one_offsets = []
    zero_run = 0
    for offset, bit in enumerate(tail):
        if bit == "0":
            zero_run += 1
            decoded.append(bit)
            continue
        if zero_run == 5:
            stuffed_one_offsets.append(offset)
        else:
            decoded.append(bit)
        zero_run = 0
    raw_unstuffed = "".join(decoded)
    return {
        "raw_bits_after_inverted_flag": tail,
        "raw_unstuffed_bits_after_inverted_flag": raw_unstuffed,
        "raw_unstuffed_octets": [
            f"{int(raw_unstuffed[offset:offset + 8], 2):02X}"
            for offset in range(0, len(raw_unstuffed) - 7, 8)
        ],
        "raw_unstuffed_trailing_bits": raw_unstuffed[len(raw_unstuffed) // 8 * 8:],
        "raw_stuffed_one_offsets_after_inverted_flag": stuffed_one_offsets,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("decode", type=Path, help="JSON from decode_ir_scope.py")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-lag", type=int, default=24)
    parser.add_argument(
        "--candidate-bytes",
        default="81,03,0c,00,01,7f",
        help="comma-separated hexadecimal controller-boundary candidate bytes",
    )
    args = parser.parse_args()

    bursts = json.loads(args.decode.read_text())
    if not bursts:
        parser.error("decode contains no bursts")
    bit_key = "cell_bits" if all("cell_bits" in burst for burst in bursts) else "bits"
    patterns = list(dict.fromkeys(burst[bit_key] for burst in bursts))
    labels = {pattern: chr(ord("A") + index) for index, pattern in enumerate(patterns)}
    sequence = [labels[burst[bit_key]] for burst in bursts]
    bitstream = "".join(burst[bit_key] for burst in bursts)
    gaps = [
        bursts[index]["start_s"] - bursts[index - 1]["end_s"]
        for index in range(1, len(bursts))
    ]
    byte_values = [int(value, 16) for value in args.candidate_bytes.split(",")]
    hdlc_flag = "01111110"
    inverted_patterns = [invert(pattern) for pattern in patterns]
    maximum_length = max(map(len, patterns))
    candidates = []
    for value in byte_values:
        per_family = []
        for pattern in patterns:
            per_family.append(
                {
                    "label": labels[pattern],
                    "msb_first_offsets": positions(pattern, byte_bits(value, False)),
                    "lsb_first_offsets": positions(pattern, byte_bits(value, True)),
                }
            )
        candidates.append(
            {
                "byte": f"{value:02X}",
                "msb_first_bits": byte_bits(value, False),
                "lsb_first_bits": byte_bits(value, True),
                "within_burst": per_family,
            }
        )

    inverted_flag_data = []
    for pattern in patterns:
        inverted = invert(pattern)
        flag_offsets = positions(inverted, hdlc_flag)
        details = {
            "label": labels[pattern],
            "inverted_flag_offsets": flag_offsets,
            "right_aligned_flag_offsets": [
                maximum_length - len(pattern) + offset
                for offset in flag_offsets
            ],
        }
        if flag_offsets:
            details.update(hdlc_tail(inverted, flag_offsets[0]))
            details.update(inverted_line_tail(pattern, flag_offsets[0]))
        inverted_flag_data.append(details)

    result = {
        "burst_count": len(bursts),
        "bit_source": bit_key,
        "families": [
            {"label": labels[pattern], "bits": pattern, "count": sequence.count(labels[pattern])}
            for pattern in patterns
        ],
        "polarity_scan": {
            "inverted_common_suffix": common_suffix(inverted_patterns),
            "inverted_hdlc_flag": inverted_flag_data,
        },
        "ordered_family_sequence": "".join(sequence),
        "family_autocorrelation": autocorrelation(sequence, args.max_lag),
        "repeated_family_ngrams": repeated_ngrams(sequence),
        "concatenated_edge_bit_count": len(bitstream),
        "concatenated_edge_bit_note": "Burst gaps are not represented as bits; use only for edge-order correlation.",
        "bit_autocorrelation": autocorrelation(list(bitstream), args.max_lag),
        "inter_segment_gap_us": [gap * 1e6 for gap in gaps],
        "median_inter_segment_gap_us": statistics.median(gaps) * 1e6,
        "candidate_byte_substrings": candidates,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")

    print("families:", ", ".join(f"{item['label']}={item['bits']} x{item['count']}" for item in result["families"]))
    print("sequence:", result["ordered_family_sequence"])
    print("median inter-segment gap (us):", round(result["median_inter_segment_gap_us"], 3))
    print("inverted common suffix:", result["polarity_scan"]["inverted_common_suffix"])
    print("inverted HDLC-flag offsets / right-aligned offsets:")
    for item in result["polarity_scan"]["inverted_hdlc_flag"]:
        print(
            f"  {item['label']}: {item['inverted_flag_offsets']} / "
            f"{item['right_aligned_flag_offsets']}; after={item.get('bits_after_first_flag', '')}; "
            f"unstuffed={item.get('hdlc_unstuffed_bits_after_first_flag', '')}; "
            f"raw-octets={item.get('raw_unstuffed_octets', [])}; "
            f"raw-trailing={item.get('raw_unstuffed_trailing_bits', '')}; "
            f"closing={item.get('additional_flag_offsets', [])}"
        )
    print("best family lags:")
    for item in sorted(result["family_autocorrelation"], key=lambda entry: entry["rate"], reverse=True)[:5]:
        print(f"  {item['lag']}: {item['matches']}/{item['pairs']} ({item['rate']:.3f})")
    print("candidate byte matches within each family (MSB/LSB offsets):")
    for item in candidates:
        matches = [
            f"{entry['label']}={entry['msb_first_offsets']}/{entry['lsb_first_offsets']}"
            for entry in item["within_burst"]
            if entry["msb_first_offsets"] or entry["lsb_first_offsets"]
        ]
        print(f"  {item['byte']}: {', '.join(matches) if matches else '-'}")


if __name__ == "__main__":
    main()
