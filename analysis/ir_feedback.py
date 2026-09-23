#!/usr/bin/env python3
"""Log and run explicit Uno feedback trials over a POSIX USB serial port.

No external Python modules are required. Each transmitted/received line is
recorded with UTC and monotonic timestamps in a new JSONL file. This runner
never invents trial settings or retries a timed-out trial. It does not upload
firmware or touch the serial port unless --port is supplied.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import select
import termios
import time
from typing import Callable


class HarnessError(RuntimeError):
    """A trial failed or the serial conversation lost synchronisation."""


def load_commands(path: Path) -> list[str]:
    """Accept explicit T commands; reset/bench-drive operations stay manual."""
    commands = []
    last_id = 0
    for number, original in enumerate(path.read_text().splitlines(), 1):
        line = original.split('#', 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) < 3 or fields[0] != 'T' or not fields[1].isdigit():
            raise ValueError(f'{path}:{number}: expected T <increasing id> ...')
        trial_id = int(fields[1])
        if not last_id < trial_id <= 0xFFFFFFFF:
            raise ValueError(f'{path}:{number}: trial IDs must increase within uint32')
        if len(line.encode('ascii')) > 95:
            raise ValueError(f'{path}:{number}: command is too long')
        last_id = trial_id
        commands.append(line)
    if not commands:
        raise ValueError('command file contains no trials')
    return commands


def classify(line: str) -> tuple[str, int | None]:
    """Find structured event/ID, never matching a printed command echo."""
    words = line.strip().split()
    if not words:
        return '', None
    kind = words[0]
    if kind not in {'READY', 'SYNC', 'TRIAL', 'RESULT', 'ERROR'}:
        return '', None
    match = re.search(r'(?:^|\s)id=(\d+)(?:\s|$)', line)
    return kind, int(match.group(1)) if match else None


class SerialLines:
    """Small nonblocking 115200 8N1 serial transport with bounded input."""

    def __init__(self, port: str):
        self.fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        try:
            attr = termios.tcgetattr(self.fd)
            attr[0] = 0
            attr[1] = 0
            attr[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
            attr[3] = 0
            attr[4] = termios.B115200
            attr[5] = termios.B115200
            attr[6][termios.VMIN] = 0
            attr[6][termios.VTIME] = 0
            termios.tcsetattr(self.fd, termios.TCSANOW, attr)
        except BaseException:
            os.close(self.fd)
            raise
        self.pending = bytearray()

    def close(self):
        os.close(self.fd)

    def discard_startup_input(self):
        """Drop boot fragments before an explicit R establishes a clean line."""
        termios.tcflush(self.fd, termios.TCIFLUSH)
        self.pending.clear()

    def send(self, line: str):
        data = memoryview((line + '\n').encode('ascii'))
        deadline = time.monotonic() + 2
        while data:
            remain = deadline - time.monotonic()
            if remain <= 0 or not select.select([], [self.fd], [], remain)[1]:
                raise HarnessError('serial write timed out')
            try:
                count = os.write(self.fd, data)
            except BlockingIOError:
                continue
            data = data[count:]

    def read(self, timeout: float) -> str | None:
        deadline = time.monotonic() + timeout
        while True:
            end = self.pending.find(b'\n')
            if end >= 0:
                line = bytes(self.pending[:end]).rstrip(b'\r')
                del self.pending[:end + 1]
                return line.decode('ascii', errors='replace')
            remain = deadline - time.monotonic()
            if remain <= 0 or not select.select([self.fd], [], [], remain)[0]:
                return None
            try:
                data = os.read(self.fd, 512)
            except BlockingIOError:
                continue
            if not data:
                raise HarnessError('serial device disconnected')
            self.pending.extend(data)
            if len(self.pending) > 8192:
                raise HarnessError('serial line exceeds 8192 bytes')


class Runner:
    def __init__(self, transport, log, timeout=8.0,
                 clock: Callable[[], float] = time.monotonic):
        self.transport, self.log = transport, log
        self.timeout, self.clock = timeout, clock

    def record(self, direction, line):
        event = {'utc': datetime.now(timezone.utc).isoformat(),
                 'monotonic_s': self.clock(), 'direction': direction, 'line': line}
        self.log.write(json.dumps(event) + '\n')
        self.log.flush()
        print(f'{direction}: {line}', flush=True)

    def send(self, line):
        self.record('tx', line)
        self.transport.send(line)

    def wait(self, expected_id=None, ready=False, require_sync=True):
        deadline = self.clock() + self.timeout
        saw_sync = not require_sync
        while self.clock() < deadline:
            line = self.transport.read(max(0, deadline - self.clock()))
            if line is None:
                continue
            self.record('rx', line)
            kind, trial_id = classify(line)
            if kind == 'ERROR':
                raise HarnessError(f'Uno reported: {line}')
            if kind == 'SYNC' and ready:
                saw_sync = True
            if kind == 'READY' and ready and saw_sync:
                return line
            if kind == 'READY' and not ready:
                raise HarnessError('Uno restarted/resynchronised during a trial')
            if kind == 'RESULT':
                if ready or trial_id != expected_id:
                    raise HarnessError(f'unexpected result: {line}')
                # A valid result may contain a ROM diagnostic timeout. Keep
                # it in the record; that is experimental data, not transport
                # failure or proof of a working IR protocol.
                return line
        raise HarnessError('timeout; trial was not retried')

    def run(self, commands):
        self.send('R')
        self.wait(ready=True)
        for index, command in enumerate(commands):
            trial_id = int(command.split()[1])
            self.send(command)
            try:
                self.wait(expected_id=trial_id)
                if index + 1 < len(commands):
                    self.wait(ready=True, require_sync=False)
            except BaseException:
                # Best effort: make the optical side silent; never mask the
                # original error if the device was disconnected.
                try:
                    self.send(f'C {trial_id}')
                except (OSError, HarnessError):
                    pass
                raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True, help='e.g. /dev/ttyACM0')
    parser.add_argument('--commands', type=Path, required=True)
    parser.add_argument('--log', type=Path, required=True, help='new JSONL file, never overwritten')
    parser.add_argument('--timeout', type=float, default=8.0)
    parser.add_argument('--startup-wait', type=float, default=2.0,
                        help='seconds for Uno reset on USB open (default 2)')
    args = parser.parse_args(argv)
    if args.timeout <= 0 or args.startup_wait < 0:
        parser.error('timeout must be positive and startup wait nonnegative')
    try:
        commands = load_commands(args.commands)
        # Exclusive creation protects the evidence from an accidental rerun.
        with args.log.open('x') as log:
            serial = SerialLines(args.port)
            try:
                time.sleep(args.startup_wait)
                serial.discard_startup_input()
                Runner(serial, log, args.timeout).run(commands)
            finally:
                serial.close()
    except (OSError, ValueError, HarnessError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
