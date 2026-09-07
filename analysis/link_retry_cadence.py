#!/usr/bin/env python3
"""Run the real ROM retry callback under a 64 Hz scheduler model.

This is a bounded discriminator for the two no-payload ``0xEE`` exits in
``LinkBlockTx``.  It executes ``LinkTransferService`` and
``Comms_WorkItemSweep`` from ``micron1.bin``.  The only modelled part is RTC
delivery: HD146818 Register C's PF flag is a latch, so periodic events that
occur while the ROM interrupt worker has interrupts disabled coalesce into
one scheduler pass when the worker returns.

The model deliberately does not infer an optical stimulus-to-status mapping.
It shows which firmware timing signatures are possible after particular
``LINK_STATUS`` transitions; a stock-ROM bus capture is still needed to say
which transition physical hardware produced.
"""

import gc
from pathlib import Path

import z80


gc.disable()  # Keep the emulator's large object graph off cyclic-GC scans.

ROOT = Path(__file__).resolve().parents[1]
ROM0 = (ROOT / "micronic" / "micron1.bin").read_bytes()
ROM1 = (ROOT / "micronic" / "micron2.bin").read_bytes()

CPU_HZ = 3_686_400
RTC_PERIOD_TSTATES = CPU_HZ // 64
RUN_CHUNK_TSTATES = 20_000
RETURN_SENTINEL = 0xF100

LINK_TRANSFER_SERVICE = 0x2F86
COMMS_WORK_ITEM_SWEEP = 0x224C

LINK_CTRL_SHADOW = 0xF794
LINK_WIRE_ID = 0xFDD4
LINK_STATE = 0xFDD5
LINK_RETRIES_REMAINING = 0xFDD6
LINK_RETRY_DELAY = 0xFDD8
LINK_TX_DESCRIPTORS = 0xFDEA
LINK_PAYLOAD = 0xFD00


def run_case(name, ack_delay_ms=None):
    """Return attempt durations and retry gaps for one status policy.

    ``ack_delay_ms=None`` keeps ``LINK_STATUS`` bit 6 set until timeout.
    A numeric delay clears ``LINK_STATUS`` bit 6 after that interval and
    leaves ``LINK_STATUS`` bit 7 clear, forcing the first payload-byte wait
    to time out.
    """
    memory = bytearray(0x10000)
    memory[:0x8000] = ROM0
    memory[0xD681:0xD681 + 0x212] = ROM0[0x7030:0x7242]
    memory[0xF180:0xF180 + 0x50D] = ROM0[0x369D:0x369D + 0x50D]
    memory[0xFD84:0xFD84 + 19] = ROM0[0x2352:0x2352 + 19]
    memory[0xFC05] = 0x70
    memory[0xF791] = 0
    memory[LINK_CTRL_SHADOW] = 0x02
    memory[LINK_WIRE_ID] = 0x43
    memory[LINK_STATE] = 1
    memory[LINK_RETRIES_REMAINING] = 50
    memory[LINK_RETRY_DELAY:LINK_RETRY_DELAY + 2] = (6).to_bytes(2, "little")

    payload = bytes([6, 0, 1, 0, 0, 0])
    memory[LINK_PAYLOAD:LINK_PAYLOAD + len(payload)] = payload
    memory[LINK_TX_DESCRIPTORS:LINK_TX_DESCRIPTORS + 4] = bytes(
        [len(payload), 0, LINK_PAYLOAD & 0xFF, LINK_PAYLOAD >> 8]
    )
    memory[LINK_TX_DESCRIPTORS + 4:LINK_TX_DESCRIPTORS + 8] = bytes(4)

    machine = z80.Z80Machine()
    machine.set_memory_block(0, bytes(memory))
    run_base = 0
    prelude_seen = False
    trigger_times = []
    attempt_durations = []

    def now():
        return run_base + RUN_CHUNK_TSTATES - machine.ticks_to_stop

    def read_memory(address):
        return memory[address & 0xFFFF]

    def write_memory(address, value):
        memory[address & 0xFFFF] = value & 0xFF

    def input_port(*args):
        port = args[0]
        port = port[0] if isinstance(port, tuple) else port
        port &= 0xFF
        if port == 0x4B:
            if not prelude_seen:
                return 0x80  # LINK_STATUS bit 7 set: initial TX-ready waits.
            if ack_delay_ms is None:
                return 0xC0  # LINK_STATUS bits 7 and 6 remain set.
            elapsed = now() - trigger_times[-1]
            if elapsed < ack_delay_ms * CPU_HZ / 1000:
                return 0xC0
            return 0x00  # LINK_STATUS bit 6 clear; bit 7 still clear.
        if port == 0x05:
            return 0x19
        if port == 0x28:
            return 0
        return 0

    def output_port(*args):
        nonlocal prelude_seen
        port, value = args[0], args[1]
        port = port[0] if isinstance(port, tuple) else port
        port &= 0xFF
        value &= 0xFF
        if port == 0x4D and not prelude_seen:
            prelude_seen = True
            trigger_times.append(now())
        if port == 0x47:
            image = ROM0 if value == 0 else ROM1 if value == 1 else bytes(0x8000)
            memory[:0x8000] = image
            memory[0xF791] = value

    machine.set_read_callback(read_memory)
    machine.set_write_callback(write_memory)
    machine.set_input_callback(input_port)
    machine.set_output_callback(output_port)

    def call(entry, wall_time):
        nonlocal run_base, prelude_seen
        triggers_before = len(trigger_times)
        prelude_seen = False
        stack = 0xF000
        memory[stack] = RETURN_SENTINEL & 0xFF
        memory[stack + 1] = RETURN_SENTINEL >> 8
        machine.sp = stack
        machine.pc = entry
        machine.set_breakpoint(RETURN_SENTINEL)
        used = 0
        event = 0
        for _ in range(1000):
            run_base = wall_time + used
            machine.ticks_to_stop = RUN_CHUNK_TSTATES
            event = machine.run()
            used += RUN_CHUNK_TSTATES - machine.ticks_to_stop
            if machine.pc == RETURN_SENTINEL:
                break
        machine.clear_breakpoint(RETURN_SENTINEL)
        if machine.pc != RETURN_SENTINEL:
            raise RuntimeError(
                f"{name}: call stopped at {machine.pc:04X}, event={event}, "
                f"used={used}"
            )
        if len(trigger_times) != triggers_before:
            attempt_durations.append(used)
        return wall_time + used

    wall_time = call(LINK_TRANSFER_SERVICE, 0)
    next_boundary = RTC_PERIOD_TSTATES
    while len(trigger_times) < 3:
        if wall_time >= next_boundary:
            # Register C PF records at least one event, not how many occurred.
            while next_boundary <= wall_time:
                next_boundary += RTC_PERIOD_TSTATES
            wall_time = call(COMMS_WORK_ITEM_SWEEP, wall_time)
        else:
            wall_time = next_boundary
            next_boundary += RTC_PERIOD_TSTATES
            wall_time = call(COMMS_WORK_ITEM_SWEEP, wall_time)

    durations_ms = [ticks * 1000 / CPU_HZ for ticks in attempt_durations]
    gaps_ms = [
        (later - earlier) * 1000 / CPU_HZ
        for earlier, later in zip(trigger_times, trigger_times[1:])
    ]
    return durations_ms, gaps_ms


def main():
    cases = [
        ("LINK_STATUS bit-6 timeout", None, 93.750),
        ("first-byte LINK_STATUS bit-7 timeout; ack 0 ms", 0, 93.750),
        ("first-byte LINK_STATUS bit-7 timeout; ack 3 ms", 3, 93.750),
        ("first-byte LINK_STATUS bit-7 timeout; ack 6 ms", 6, 109.375),
    ]
    for name, delay, expected_gap in cases:
        durations, gaps = run_case(name, delay)
        steady_gap = gaps[-1]
        if abs(steady_gap - expected_gap) > 0.002:
            raise AssertionError(
                f"{name}: expected {expected_gap:.3f} ms, got {steady_gap:.3f} ms"
            )
        print(
            f"{name}: attempt={durations[-1]:.3f} ms; "
            f"steady retry={steady_gap:.3f} ms"
        )


if __name__ == "__main__":
    main()
