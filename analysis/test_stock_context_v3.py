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
    assert image[v3.INIT_SITE:v3.INIT_SITE + 5] == (
        b"\xCD" + sym["init_wrapper"].to_bytes(2, "little") + b"\x00\x00")
    assert image[0x34E7:0x34EC] == original[0x34E7:0x34EC]
    assert sym["rx_wrapper"] == v3.CODE_ORG
    assert sym["end"] <= v3.CODE_END + 1
    changed = {i for i, (before, after) in enumerate(zip(original, image))
               if before != after}
    assert changed <= (
        set(range(v3.RX_CALL_SITE, v3.RX_CALL_SITE + 3)) |
        set(range(v3.INIT_SITE, v3.INIT_SITE + 5)) |
        set(range(v3.CODE_ORG, sym["end"])))
    assert image[0x250:v3.INIT_SITE] == original[0x250:v3.INIT_SITE]
    assert image[v3.INIT_SITE + 5:0x2FE] == original[v3.INIT_SITE + 5:0x2FE]
    info = v3.manifest(image, sym, original, "micron1_stock_context_v3.bin")
    assert info["assembly_sha256"] == hashlib.sha256(
        v3.HOOK_SOURCE.encode("ascii")).hexdigest()
    assert info["checksums"] == v3.fingerprint(image)
    assert info["patch"]["address"] == "ROM00:2FC1"
    assert info["init_patch"]["address"] == "ROM00:0252"
    assert info["init_marker"]["dwell_tstates"] == 4 * 3327
    assert info["marker"]["release_guard_tstates"] == 1663


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

    original = bytearray(v3.DEFAULT_ROM.read_bytes())
    original[v3.INIT_SITE] ^= 1
    path.write_bytes(original)
    monkeypatch.setattr(v3, "STOCK_SHA256", hashlib.sha256(original).hexdigest())
    with pytest.raises(ValueError, match="0252"):
        v3.build_image(path)


@pytest.mark.parametrize("target", ["image", "manifest"])
def test_cli_refuses_to_overwrite_source_rom(tmp_path, target):
    source = tmp_path / "source.bin"
    original = v3.DEFAULT_ROM.read_bytes()
    source.write_bytes(original)
    args = ["--rom", str(source), "-o", str(source if target == "image"
                                          else tmp_path / "output.bin")]
    if target == "manifest":
        args += ["--manifest-out", str(source)]
    with pytest.raises(SystemExit):
        v3.main(args)
    assert source.read_bytes() == original


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
def test_common_restart_marker_preserves_stock_state_and_has_distinct_width():
    patched, _, stock = v3.build_image()

    def run(image):
        cpu, mem = _machine(image)
        outputs = []
        cpu.set_output_callback(lambda port, value: outputs.append(
            (port & 0xFF, value & 0xFF, cpu.ticks_to_stop)))
        cpu.set_memory_block(0, bytes(mem))
        cpu.pc = 0x024D           # stock common cold/warm restart entry
        cpu.sp = 0xF000
        cpu.f = 0xA5
        cpu.bc = 0x1234
        cpu.de = 0x5678
        cpu.hl = 0x9ABC
        cpu.set_breakpoint(0x0259)
        cpu.ticks_to_stop = 1000000
        cpu.run()
        cpu.clear_breakpoint(0x0259)
        assert cpu.pc == 0x0259
        state = (cpu.a, cpu.f, cpu.b, cpu.c, cpu.d, cpu.e,
                 cpu.h, cpu.l, cpu.sp, mem[v3.SHADOW_2A])
        return state, outputs

    patched_state, outputs = run(patched)
    stock_state, stock_outputs = run(stock)
    assert patched_state == stock_state
    assert stock_outputs[0][:2] == (0x2A, 0x20)
    assert [event[:2] for event in outputs] == [
        (0x2A, 0x20), (0x2A, 0x20), (0x2A, 0x21),
        (0x2A, 0x20), (0x2A, 0x20)]
    # The emulator reports T-states remaining in the output callback.
    # These intervals include wrapper overhead around each assembled loop.
    intervals = [a[2] - b[2] for a, b in zip(outputs, outputs[1:])]
    assert intervals == [62, 1711, 13407, 1704]


@NEEDS_EMULATOR
@pytest.mark.parametrize("carry,shadow", [
    (True, 0xA4), (True, 0xA5),
    (False, 0xA4), (False, 0xA5),
])
def test_rx_marker_real_edge_intervals(carry, shadow):
    image, _, _ = v3.build_image()
    cpu, mem = _machine(image)
    stub = _rx_stub(carry)
    mem[0x3378:0x3378 + len(stub)] = stub
    mem[v3.SHADOW_2A] = shadow
    outputs = []
    cpu.set_input_callback(lambda port: 0)
    cpu.set_output_callback(lambda port, value: outputs.append(
        (port & 0xFF, value & 0xFF, cpu.ticks_to_stop)))
    cpu.set_memory_block(0, bytes(mem))
    cpu.sp = 0xF000
    mem[0xF000:0xF002] = b"\xC4\x2F"
    cpu.pc = v3.RX_CALL_SITE
    cpu.set_breakpoint(0x2FC4)
    for _ in range(3):
        cpu.ticks_to_stop = 100000
        cpu.run()
        if cpu.pc == 0x2FC4:
            break
    cpu.clear_breakpoint(0x2FC4)
    assert cpu.pc == 0x2FC4
    marker = [event for event in outputs if event[0] == 0x2A]
    assert [value for _, value, _ in marker] == [
        shadow & 0xFE, shadow | 1, shadow & 0xFE, shadow]
    intervals = [a[2] - b[2] for a, b in zip(marker, marker[1:])]
    assert intervals == ([1719, 3383, 1701] if carry
                         else [1719, 6739, 1701])


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
    mem[sym["delay_1ms"]:sym["delay_1ms"] + 5] = bytes.fromhex(
        "db 71 c9 00 00")
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
    assert bytes(image[sym["delay_1ms"]:sym["delay_450us"]]) == bytes.fromhex(
        "06 ff 10 fe c9")
    assert bytes(image[sym["delay_450us"]:sym["init_wrapper"]]) == bytes.fromhex(
        "06 7f 10 fe c9")
    assert 3327 / 3686.4 == pytest.approx(0.903, abs=0.001)
    assert 1663 / 3686.4 >= 0.450


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


@NEEDS_EMULATOR
def test_wrapper_preserves_actual_stock_success_and_reader_io_order():
    patched, _, stock = v3.build_image()
    descriptor = bytes.fromhex("0A 00 00 90 00 00")
    frame = bytes.fromhex("11 22 33 44 55 66")

    def run(image):
        cpu, mem = _machine(image)
        mem[0xF794] = 0x10
        mem[v3.SHADOW_2A] = 0x21
        mem[0xFDDC:0xFDDE] = (0x8000).to_bytes(2, "little")
        mem[0x8000:0x8000 + len(descriptor)] = descriptor
        payload = list(frame)
        rxd_reads = 0
        events = []
        stack_writes = []

        def inp(port):
            nonlocal rxd_reads
            port &= 0xFF
            events.append(("in", port))
            if port == 0x4E:
                rxd_reads += 1
                return 0 if rxd_reads == 1 else payload.pop(0)
            if port == 0x4B:
                return 0x01 if payload else 0x02
            return 0

        def outp(port, value):
            events.append(("out", port & 0xFF, value & 0xFF))

        def write_mem(addr, value):
            addr &= 0xFFFF
            mem[addr] = value & 0xFF
            # PUSH/CALL write next to SP; ordinary link-shadow writes to
            # F794 are below the stack and must not count as stack depth.
            if cpu.sp - 2 <= addr <= cpu.sp + 2:
                stack_writes.append(addr)

        cpu.set_input_callback(inp)
        cpu.set_output_callback(outp)
        cpu.set_write_callback(write_mem)
        cpu.set_memory_block(0, bytes(mem))
        cpu.sp = 0xF81A       # stock system-stack top at common restart
        cpu.ix = 0x1357
        cpu.iy = 0x2468
        cpu.pc = 0x2FBD       # real dispatcher loads and pushes descriptor
        _run_to(cpu, 0x2FC4, limit=20)
        regs = (cpu.a, cpu.f, cpu.b, cpu.c, cpu.d, cpu.e,
                cpu.h, cpu.l, cpu.ix, cpu.iy, cpu.sp)
        return regs, bytes(mem[0x9000:0x9006]), events, min(stack_writes), rxd_reads

    patched_regs, patched_frame, patched_events, patched_min_sp, patched_reads = run(patched)
    stock_regs, stock_frame, stock_events, stock_min_sp, stock_reads = run(stock)
    assert patched_regs == stock_regs
    assert patched_regs[0] == 0 and not (patched_regs[1] & 1)
    assert patched_regs[-1] == 0xF818
    assert patched_frame == stock_frame == frame
    assert patched_reads == stock_reads == 7  # dummy arm read plus six bytes
    assert [event for event in stock_events if event[0] == "in"][0] == ("in", 0x4E)
    assert all(event[1] in (0x4B, 0x4E) for event in stock_events
               if event[0] == "in")
    assert patched_min_sp >= 0xF79A
    assert patched_min_sp < stock_min_sp  # wrapper's saved registers
    assert patched_events[:len(stock_events)] == stock_events
    assert patched_events[len(stock_events):] == [
        ("out", 0x2A, 0x20), ("out", 0x2A, 0x21),
        ("out", 0x2A, 0x20), ("out", 0x2A, 0x21)]
