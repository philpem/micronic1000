"""Tests for the guarded live-stock receive-context diagnostic."""
import hashlib
import importlib.util
import pathlib
import sys

import pytest

try:
    import z80
except ImportError:  # pragma: no cover - emulator is supplied by analysis/venv
    z80 = None

ANALYSIS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ANALYSIS))
_SPEC = importlib.util.spec_from_file_location(
    "stock_context_v3", ANALYSIS / "rom_exerciser" / "stock_context_v3.py")
v3 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(v3)

NEEDS_EMULATOR = pytest.mark.skipif(z80 is None, reason="pyz80 is unavailable")


def test_builder_patches_only_guarded_sites_and_zero_cave():
    image, sym, original = v3.build_image()
    assert image[v3.RX_CALL_SITE:v3.RX_CALL_SITE + 3] == (
        b"\xCD" + sym["rx_wrapper"].to_bytes(2, "little"))
    assert image[0x34E7:0x34EC] == original[0x34E7:0x34EC]
    assert sym["rx_wrapper"] == v3.CODE_ORG
    assert sym["end"] <= v3.CODE_END + 1
    changed = {i for i, (before, after) in enumerate(zip(original, image))
               if before != after}
    assert changed <= (
        set(range(v3.RX_CALL_SITE, v3.RX_CALL_SITE + 3)) |
        set(range(v3.CODE_ORG, sym["end"])))
    assert image[0x250:0x2FE] == original[0x250:0x2FE]
    info = v3.manifest(image, sym, original, "micron1_stock_context_v3.bin")
    assert info["assembly_sha256"] == hashlib.sha256(
        v3.HOOK_SOURCE.encode("ascii")).hexdigest()
    assert info["checksums"] == v3.fingerprint(image)
    assert info["patch"]["address"] == "ROM00:2FC1"


def test_builder_refuses_wrong_call_bytes_and_nonempty_cave(tmp_path, monkeypatch):
    original = bytearray(v3.DEFAULT_ROM.read_bytes())
    original[v3.RX_CALL_SITE] ^= 1
    path = tmp_path / "bad-call.bin"
    path.write_bytes(original)
    monkeypatch.setattr(v3, "STOCK_SHA256", hashlib.sha256(original).hexdigest())
    with pytest.raises(ValueError, match="2FC1"):
        v3.build_image(path)

    original = bytearray(v3.DEFAULT_ROM.read_bytes())
    original[v3.CODE_ORG] = 0xFF
    path.write_bytes(original)
    monkeypatch.setattr(v3, "STOCK_SHA256", hashlib.sha256(original).hexdigest())
    with pytest.raises(ValueError, match="cave"):
        v3.build_image(path)


def _machine(image):
    mem = bytearray(0x10000)
    mem[:0x8000] = image
    cpu = z80.Z80Machine()
    cpu.set_memory_block(0, bytes(mem))
    cpu.set_read_callback(lambda addr: mem[addr & 0xFFFF])
    cpu.set_write_callback(lambda addr, value:
                           mem.__setitem__(addr & 0xFFFF, value & 0xFF))
    return cpu, mem


def _run_to(cpu, target, limit=1000):
    cpu.set_breakpoint(target)
    for _ in range(limit):
        cpu.ticks_to_stop = 100000
        cpu.run()
        if cpu.pc == target:
            break
    cpu.clear_breakpoint(target)
    assert cpu.pc == target, f"did not reach {target:04X}; PC={cpu.pc:04X}"


def _rx_stub(carry):
    # Count one stock-reader invocation through input port 70h. Return chosen
    # AF and distinctive BC/DE/HL values; all loads after flag setup preserve F.
    flag_setup = "scf" if carry else "or a"
    src = f"""
        org 0x3378
        in a,(0x70)
        xor a
        or a
        ld a,0x5a
        {flag_setup}
        ld bc,0x1234
        ld de,0x5678
        ld hl,0x9abc
        ret
    """
    from micronic.z80asm import assemble
    return assemble(src, origin=0x3378)[0]


@NEEDS_EMULATOR
@pytest.mark.parametrize("carry,delay_calls,shadow", [
    (True, 1, 0xA4), (True, 1, 0xA5),
    (False, 2, 0xA4), (False, 2, 0xA5),
])
def test_rx_wrapper_calls_stock_once_pulses_after_return_and_restores(carry,
                                                                     delay_calls,
                                                                     shadow):
    image, sym, _ = v3.build_image()
    cpu, mem = _machine(image)
    stub = _rx_stub(carry)
    mem[0x3378:0x3378 + len(stub)] = stub
    mem[v3.SHADOW_2A] = shadow
    scratch_sentinel = bytes.fromhex("de ad be ef")
    mem[0xC7E0:0xC7E4] = scratch_sentinel
    # Test-only delay replacement emits one input read per selected pulse
    # class, then executes a bounded DJNZ loop. The production loop's exact
    # bytes and 3327-T-state duration are asserted below.
    mem[sym["delay_1ms"]:sym["delay_1ms"] + 9] = bytes.fromhex(
        "06 ff db 71 06 ff 10 fe c9")
    input_ports = []
    events = []
    outputs = []
    def input_port(port):
        port &= 0xFF
        input_ports.append(port)
        events.append(("in", port))
        return 0
    cpu.set_input_callback(input_port)
    cpu.set_output_callback(lambda port, value:
                            (outputs.append((port & 0xFF, value & 0xFF,
                                             cpu.pc)),
                             events.append(("out", port & 0xFF, value & 0xFF)))
                            )
    cpu.set_memory_block(0, bytes(mem))

    # Enter through the guarded stock CALL replacement. Its callee is the
    # real-code return stub above so the wrapper contract is isolated.
    cpu.sp = 0xF000
    mem[0xF000:0xF002] = b"\xC4\x2F"
    cpu.pc = v3.RX_CALL_SITE
    _run_to(cpu, 0x2FC4, limit=20)
    assert input_ports == [0x70] + [0x71] * delay_calls
    assert cpu.a == 0x5A
    assert bool(cpu.f & 1) is carry
    assert (cpu.b, cpu.c, cpu.d, cpu.e, cpu.h, cpu.l) == (
        0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC)
    assert mem[0xC7E0:0xC7E4] == scratch_sentinel
    assert [(port, value) for port, value, _ in outputs] == [
        (0x2A, shadow & 0xFE), (0x2A, shadow | 0x01),
        (0x2A, shadow & 0xFE), (0x2A, shadow)]
    # Owner-confirmed pin 6 sinks at bit 0=1. Release before and after the
    # bounded sink interval guarantees an edge even when the incoming shadow
    # already had bit 0 set; all four writes follow stock RX's port-70 read.
    assert [value & 1 for _, value, _ in outputs] == [0, 1, 0, shadow & 1]
    assert [event for event in events if event[0] == "in"] == (
        [("in", 0x70)] + [("in", 0x71)] * delay_calls)
    assert events.index(("out", 0x2A, shadow & 0xFE)) > events.index(("in", 0x70))
    assert events[-1] == ("out", 0x2A, shadow)
    assert outputs[0][2] < outputs[1][2] < outputs[2][2] < outputs[3][2]
    assert bytes(image[sym["delay_1ms"]:sym["end"]]) == bytes.fromhex(
        "06 ff 10 fe c9")
    assert 3327 / 3686.4 == pytest.approx(0.903, abs=0.001)


@NEEDS_EMULATOR
def test_wrapper_preserves_actual_stock_link_block_rx_return_and_io_count():
    patched, _, stock = v3.build_image()

    def run(image):
        cpu, mem = _machine(image)
        mem[0xF794] = 0x10
        mem[0xFDDC:0xFDDE] = (0x8000).to_bytes(2, "little")
        mem[0x8000:0x8006] = bytes.fromhex("06 00 00 90 00 00")
        inputs, outputs, events = [], [], []

        def inp(port):
            port &= 0xFF
            inputs.append(port)
            events.append(("in", port))
            if port == 0x4B:
                return 0x0A              # bounded Link_BlockRx error return
            return 0

        def outp(port, value):
            event = (port & 0xFF, value & 0xFF)
            outputs.append(event)
            events.append(("out",) + event)

        cpu.set_input_callback(inp)
        cpu.set_output_callback(outp)
        cpu.set_memory_block(0, bytes(mem))
        cpu.sp = 0xF000
        mem[0xF000:0xF002] = b"\xC4\x2F"
        # Enter at the real dispatcher prelude: it loads and pushes the
        # descriptor pointer before calling Link_BlockRx at 2FC1.
        cpu.pc = 0x2FBD
        _run_to(cpu, 0x2FC4, limit=100)
        regs = (cpu.a, cpu.f, cpu.b, cpu.c, cpu.d, cpu.e, cpu.h, cpu.l)
        return regs, inputs, outputs, events

    patched_regs, patched_inputs, patched_outputs, patched_events = run(patched)
    stock_regs, stock_inputs, stock_outputs, _ = run(stock)
    assert patched_regs == stock_regs
    assert patched_regs[0] == 0xEC
    assert patched_regs[1] & 0x01
    assert patched_inputs == stock_inputs
    assert patched_inputs.count(0x4E) == 1
    marker = [(port, value) for port, value in patched_outputs if port == 0x2A]
    assert marker[-4:] == [(0x2A, 0x00), (0x2A, 0x01),
                           (0x2A, 0x00), (0x2A, 0x00)]
    output_count = 0
    marker_start = None
    for index, event in enumerate(patched_events):
        if event[0] == "out":
            if output_count == len(stock_outputs):
                marker_start = index
                break
            output_count += 1
    assert marker_start is not None
    assert marker_start > patched_events.index(("in", 0x4E))
    assert patched_outputs[:-4] == stock_outputs
