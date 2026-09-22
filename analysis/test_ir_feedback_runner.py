"""Host transcript controls: no silent retries or mismatched trial records."""
from io import StringIO
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ir_feedback import HarnessError, Runner, classify, load_commands


class Link:
    def __init__(self, lines):
        self.lines = list(lines)
        self.sent = []
        self.now = 0.0

    def send(self, line):
        self.sent.append(line)

    def read(self, timeout):
        self.now += 0.1 if self.lines else timeout
        return self.lines.pop(0) if self.lines else None


def runner(lines):
    link = Link(lines)
    log = StringIO()
    return Runner(link, log, timeout=2, clock=lambda: link.now), link, log


def test_startup_ready_is_not_resynchronisation_ack():
    r, link, log = runner(['READY boot', 'SYNC waiting', 'READY idle',
                           'TRIAL id=7', 'RESULT id=7 rom_seq=1 error=6'])
    r.run(['T 7 W S 0 7E 1 0 0 -2 5 7000 -'])
    assert link.sent == ['R', 'T 7 W S 0 7E 1 0 0 -2 5 7000 -']
    assert '"direction": "tx"' in log.getvalue()
    assert 'error=6' in log.getvalue()  # ROM timeout is data, not host failure


@pytest.mark.parametrize('response', [
    'RESULT id=8 rom_seq=1', 'READY boot', 'ERROR id=7 reason=checksum',
])
def test_wrong_result_reset_or_error_cancels_without_retry(response):
    r, link, _ = runner(['SYNC', 'READY', response])
    with pytest.raises(HarnessError):
        r.run(['T 7 W S', 'T 8 W S'])
    assert link.sent == ['R', 'T 7 W S', 'C 7']


def test_timeout_cancels_and_does_not_send_next_trial():
    r, link, _ = runner(['SYNC', 'READY'])
    with pytest.raises(HarnessError, match='not retried'):
        r.run(['T 7 W S', 'T 8 W S'])
    assert link.sent == ['R', 'T 7 W S', 'C 7']


def test_initial_ready_alone_cannot_start_trials():
    r, link, _ = runner(['READY boot'])
    with pytest.raises(HarnessError):
        r.run(['T 7 W S'])
    assert link.sent == ['R']


def test_results_cannot_be_read_from_echoed_command():
    assert classify('echo RESULT id=7') == ('', None)
    assert classify('RESULT id=70 rom_seq=2') == ('RESULT', 70)


def test_command_file_is_explicit_and_ids_increase(tmp_path):
    commands = tmp_path / 'trials.txt'
    commands.write_text('# baseline\nT 3 W S # comment\nT 4 R X\n')
    assert load_commands(commands) == ['T 3 W S', 'T 4 R X']
    for text in ('R\n', 'T 4 W S\nT 4 W S\n', 'T 4294967296 W S\n', '# empty\n'):
        commands.write_text(text)
        with pytest.raises(ValueError):
            load_commands(commands)


def test_batch_waits_for_fresh_ready_before_next_command():
    r, link, _ = runner(['SYNC', 'READY', 'RESULT id=7 rom_seq=1',
                         'READY', 'RESULT id=8 rom_seq=2'])
    r.run(['T 7 W S', 'T 8 W S'])
    assert link.sent == ['R', 'T 7 W S', 'T 8 W S']
