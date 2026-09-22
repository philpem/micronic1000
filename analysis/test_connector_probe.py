"""Execute the release connector ROM, including stock LCD/key helpers."""
from pathlib import Path
import hashlib
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import z80
from rom_exerciser import connector


class Probe:
    def __init__(self, dirty=0xA5, edge=lambda: 0xFF, version=1):
        self.image, self.sym, _ = connector.build_image(version=version)
        self.mem = bytearray([dirty] * 65536)
        self.mem[:32768] = self.image
        self.cpu = z80.Z80Machine()
        self.cpu.set_memory_block(0, bytes(self.mem))
        self.cpu.set_read_callback(lambda a: self.mem[a & 65535])
        self.cpu.set_write_callback(lambda a, v: self.mem.__setitem__(a & 65535, v & 255))
        self.writes = []
        self.edge = edge
        self.edge_reads = 0
        self.key = None
        self.drive = 0
        self.lcd_reg = 0
        self.cursor = 0
        self.screen = bytearray(b' ' * 256)
        self.cpu.set_input_callback(self.read_port)
        self.cpu.set_output_callback(self.write_port)
        self.cpu.pc = connector.BOOT
        self.run_to('main_loop')
        self.writes.clear()
        self.edge_reads = 0

    def read_port(self, p):
        p &= 255
        if p == 0x2D:
            self.edge_reads += 1
            return self.edge()
        if p == 0 and self.key is not None:
            if self.drive == 1 << (self.key % 6):
                return 1 << (self.key // 6)
        return 0

    def write_port(self, p, v):
        p &= 255
        self.writes.append((p, v))
        if p == 2:
            self.drive = v & 63
        elif p == 0x23:
            self.lcd_reg = v
        elif p == 3:
            if self.lcd_reg == 10:
                self.cursor = (self.cursor & 0xFF00) | v
            elif self.lcd_reg == 11:
                self.cursor = (self.cursor & 255) | (v << 8)
            elif self.lcd_reg == 12:
                if self.cursor < len(self.screen):
                    self.screen[self.cursor] = v
                self.cursor = (self.cursor + 1) & 65535

    def run_to(self, name):
        addr = self.sym[name]
        self.cpu.set_breakpoint(addr)
        for _ in range(120):
            self.cpu.ticks_to_stop = 100000
            self.cpu.run()
            if self.cpu.pc == addr:
                break
        self.cpu.clear_breakpoint(addr)
        assert self.cpu.pc == addr, hex(self.cpu.pc)

    def call(self, name, a=None):
        if a is not None:
            self.cpu.a = a
        self.cpu.sp = 0xC8FE
        self.mem[0xC8FE:0xC900] = b'\x00\x80'
        self.cpu.pc = self.sym[name]
        self.cpu.set_breakpoint(0x8000)
        for _ in range(50):
            self.cpu.ticks_to_stop = 100000
            self.cpu.run()
            if self.cpu.pc == 0x8000:
                break
        self.cpu.clear_breakpoint(0x8000)
        assert self.cpu.pc == 0x8000

    def value(self, name):
        return self.mem[self.sym[name]]

    def command(self, char):
        self.call('handle_key', ord(char))


def test_image_is_guarded_and_only_reclaims_dedicated_session_code(tmp_path):
    image, sym, original = connector.build_image()
    assert len(image) == 32768
    assert sym['end'] <= connector.LIMIT
    changes = [i for i, (a, b) in enumerate(zip(image, original)) if a != b]
    assert all(connector.BOOT <= i < connector.BOOT + 3 or
               connector.ORIGIN <= i < sym['end'] for i in changes)
    bad = bytearray(original)
    bad[0x1EEC] ^= 1
    p = tmp_path / 'wrong.bin'; p.write_bytes(bad)
    with pytest.raises(ValueError, match='verified stock'):
        connector.build_image(p)
    fp = connector.fingerprint(image)
    assert fp['md5'] == hashlib.md5(image).hexdigest()
    assert int(fp['sum24'], 16) == sum(image) & 0xFFFFFF


@pytest.mark.parametrize('dirty', [0x00, 0xA5, 0xFF])
def test_startup_initialises_dirty_ram_and_displays_complete_rows(dirty):
    p = Probe(dirty)
    assert p.value('MODE') == ord('S')
    assert p.value('SHADOW2A') == p.value('BASE2A') == 0x20
    assert p.value('SHADOW2C') == p.value('BASE2C') == 0x20
    assert p.mem[0xF5F6:0xF5F8] == b'\xED\x45'
    rows = [bytes(p.screen[i:i + 20]).decode() for i in range(0, 160, 20)]
    assert rows[0] == 'CONNECTOR PROBE 1   '
    assert rows[1].startswith('2A=20 2C=20 2D=')
    assert rows[2] == 'SEL=2C/01 MODE=S    '
    assert rows[3] == 'IN OR=FF AND=FF     '
    assert rows[4:] == ['A-E:PIN P/T:PULSE   ', 'L/H:HOLD S:STOP     ',
                        'SPACE:BASE R:RESET  ', 'NO/YES:CONTRAST     ']


@pytest.mark.parametrize('key,port,mask', [('A',0x2C,1), ('B',0x2C,2),
                                           ('C',0x2A,2), ('D',0x2A,1), ('E',0x2A,16)])
def test_all_candidates_hold_and_restore_without_other_output_changes(key, port, mask):
    p = Probe()
    p.command(key)
    p.writes.clear()
    p.command('H'); p.command('L'); p.command('S')
    assert p.writes == [(port, 0x20 | mask), (port, 0x20), (port, 0x20)]
    assert p.value('SHADOW2A') == p.value('SHADOW2C') == 0x20


def test_gated_baseline_survives_other_candidate_and_reset_restores_both():
    p = Probe()
    p.command('B'); p.command(' ')
    assert p.value('BASE2C') == 0x22
    p.command('A'); p.command('H')
    assert p.value('SHADOW2C') == 0x23
    p.command('S')
    assert p.value('SHADOW2C') == 0x22
    p.command('R')
    assert p.value('SHADOW2C') == p.value('SHADOW2A') == 0x20
    assert p.value('MODE') == ord('S')


@pytest.mark.parametrize('mode,half', [('P',50), ('T',4)])
def test_waveform_toggles_at_known_dwell_counts_while_input_samples_accumulate(mode, half):
    samples = iter([0xFE, 0xFF] * 100000)
    p = Probe(edge=lambda: next(samples))
    p.command('A'); p.command(mode)
    p.writes.clear()
    for _ in range(half - 1):
        p.call('sample_wait'); p.call('wave_tick')
    assert p.writes == []
    p.call('sample_wait'); p.call('wave_tick')
    assert p.writes == [(0x2C,0x21)]
    assert p.value('INPUT_OR') == 0xFF
    assert p.value('INPUT_AND') == 0xFE
    for _ in range(half):
        p.call('sample_wait'); p.call('wave_tick')
    assert p.writes[-1] == (0x2C,0x20)
    assert p.edge_reads == 2 * half * 184
    p.call('display')
    assert b'2D=FF' in p.screen[20:40]
    assert p.screen[60:80] == b'IN OR=FF AND=FE     '


def test_real_keyboard_scan_maps_letters_and_contrast_keys():
    p = Probe()
    for idx, key in [(1,'A'),(2,'B'),(6,'C'),(7,'D'),(8,'E'),(25,'P'),(32,'T')]:
        p.key = idx
        p.call('key_scan')
        assert p.cpu.a == ord(key)
    p.key = None
    p.call('key_scan'); assert p.cpu.a == 0xFF
    before = p.value('CONTRAST')
    p.call('handle_key',1)
    assert p.value('CONTRAST') == before - 2
    p.call('handle_key',6)
    assert p.value('CONTRAST') == before

@pytest.mark.parametrize('key,port,mask', [('A',0x2C,1), ('B',0x2C,2),
                                           ('C',0x2A,2), ('D',0x2A,1), ('E',0x2A,16)])
def test_high_baseline_is_restored_for_every_candidate(key, port, mask):
    p = Probe()
    p.command(key); p.command(' ')
    p.writes.clear()
    p.command('H'); p.command('L'); p.command('S')
    assert p.writes == [(port,0x20 | mask),(port,0x20),(port,0x20 | mask)]
    other = 'SHADOW2A' if port == 0x2C else 'SHADOW2C'
    assert p.value(other) == 0x20


def test_main_loop_debounces_held_key_and_updates_live_input():
    p = Probe(edge=lambda: 0x5A)
    p.key = 11  # SPACE: toggle baseline only once while held
    p.cpu.pc = p.sym['main_loop']
    for _ in range(3):
        p.run_to('key_done')
        assert p.value('BASE2C') == 0x21
        p.run_to('main_loop')
    assert b'2D=5A' in p.screen[20:40]
    assert p.screen[60:80] == b'IN OR=5A AND=5A     '
    p.key = None
    p.run_to('key_done'); p.run_to('main_loop')
    p.key = 11
    p.run_to('key_done')
    assert p.value('BASE2C') == 0x20


@pytest.mark.parametrize('version', [1, 2])
def test_pinned_release_manifest_matches_fresh_source_build(version):
    import json
    image, symbols, original = connector.build_image(version=version)
    _, release = connector._source_and_output(version)
    manifest = json.loads(release.with_suffix('.json').read_text())
    assert manifest['checksums'] == connector.fingerprint(image)
    assert manifest['assembly_sha256'] == hashlib.sha256(
        connector.SOURCES[version].read_bytes()).hexdigest()
    assert manifest == connector.build_manifest(
        image, symbols, original, version, release.name)


def test_v2_f_selects_port2c_bit5_and_low_baseline_survives_selection_changes():
    p = Probe(version=2)
    rows = [bytes(p.screen[i:i + 20]).decode() for i in range(0, 160, 20)]
    assert rows[0] == 'CONNECTOR PROBE 2   '
    assert rows[4] == 'A-F:PIN P/T:PULSE   '

    p.command('R'); p.command('F'); p.command(' ')
    assert (p.value('BASE2A'), p.value('BASE2C')) == (0x20, 0x00)
    assert (p.value('SHADOW2A'), p.value('SHADOW2C')) == (0x20, 0x00)

    # The requested R,F,SPACE,B,SPACE,C,SPACE sequence keeps F's released-low
    # bit 5 while B and C independently retain their selected baseline bits.
    p.command('B'); p.command(' ')
    assert (p.value('BASE2A'), p.value('BASE2C')) == (0x20, 0x02)
    assert (p.value('SHADOW2A'), p.value('SHADOW2C')) == (0x20, 0x02)
    p.command('C'); p.command(' ')
    assert (p.value('BASE2A'), p.value('BASE2C')) == (0x22, 0x02)
    assert (p.value('SHADOW2A'), p.value('SHADOW2C')) == (0x22, 0x02)

    p.command('R')
    assert (p.value('BASE2A'), p.value('BASE2C')) == (0x20, 0x20)
    assert (p.value('SHADOW2A'), p.value('SHADOW2C')) == (0x20, 0x20)

    # F's default is high; its temporary L/H modes leave the retained baseline
    # unchanged, and STOP restores that high baseline.
    p.command('F'); p.command('L')
    assert p.value('SHADOW2C') == 0x00 and p.value('BASE2C') == 0x20
    p.command('H')
    assert p.value('SHADOW2C') == 0x20 and p.value('BASE2C') == 0x20
    p.command('S')
    assert p.value('SHADOW2C') == p.value('BASE2C') == 0x20

    # F is reachable through the stock keyboard scan, not only direct calls.
    p.key = 9
    p.call('key_scan')
    assert p.cpu.a == ord('F')


def test_v2_diff_is_limited_to_its_candidate_limit_and_data_region():
    v1, s1, _ = connector.build_image()
    v2, s2, _ = connector.build_image(version=2)
    changed = [i for i, (a, b) in enumerate(zip(v1, v2)) if a != b]
    assert changed
    # The A-F comparison and the absolute references relocated by the added
    # candidate are the only changed instructions. Remaining bytes are the
    # candidate table and v2's banner/help data; no stock or unrelated region
    # is touched.
    assert [i for i in changed if i < s2['candidates']] == [
        0x605B, 0x6066, 0x6140, 0x61E3, 0x61EF, 0x61FB,
        0x6216, 0x622D, 0x6239, 0x6245, 0x6251,
    ]
    assert v1[s2['key_candidate_limit'] + 1] == ord('F')
    assert v2[s2['key_candidate_limit'] + 1] == ord('G')
    assert all(s2['candidates'] <= i < s2['end'] for i in changed
               if i >= s2['candidates'])
    assert v1[connector.BOOT:connector.BOOT + 3] == v2[connector.BOOT:connector.BOOT + 3]


def test_cli_can_write_a_local_image_and_optional_provenance(tmp_path):
    image_path = tmp_path / 'micron1_connector_v2.bin'
    manifest_path = tmp_path / 'provenance' / 'micron1_connector_v2.json'
    connector.main(['--version', '2', '--out', str(image_path),
                    '--manifest-out', str(manifest_path)])
    image, symbols, original = connector.build_image(version=2)
    assert image_path.read_bytes() == image
    import json
    assert json.loads(manifest_path.read_text()) == connector.build_manifest(
        image, symbols, original, 2, image_path.name)


@pytest.mark.parametrize('version', [1, 2])
def test_cli_does_not_overwrite_pinned_manifest_by_default(tmp_path, version):
    _, release = connector._source_and_output(version)
    image_path = tmp_path / release.name
    manifest_path = image_path.with_suffix('.json')
    pinned = release.with_suffix('.json').read_bytes()
    manifest_path.write_bytes(pinned)
    assert not image_path.exists()
    connector.main(['--version', str(version), '--out', str(image_path)])
    assert manifest_path.read_bytes() == pinned
    import json
    assert connector.fingerprint(image_path.read_bytes()) == json.loads(pinned)['checksums']


def test_cli_rejects_manifest_path_that_would_replace_the_image(tmp_path):
    image_path = tmp_path / 'burn.bin'
    with pytest.raises(SystemExit):
        connector.main(['--out', str(image_path), '--manifest-out', str(image_path)])
    assert not image_path.exists()
