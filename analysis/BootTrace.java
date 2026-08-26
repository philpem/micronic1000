/* BootTrace.java
 *
 * //@category Micronic
 *
 * Micronic 1000 / PARCON 1000 - emulate the DIPOSB dispatcher boot
 * sequence and capture the post-boot battery-RAM image.
 *
 * Preconditions:
 *   - FillBatteryRam.java has been run (battery_ram block exists,
 *     dispatch module installed at ram:d681, kernel image at f180).
 *
 * What it does:
 *   1. Starts emulation at ram:d681 (dispatcher startup).
 *   2. Breakpoint at ram:d6ac = the resident idle loop; reaching it
 *      means boot-load scripts, ED-area init and kernel notify calls
 *      have all executed.
 *   3. Memory-write tracking captures every write; afterwards we
 *      summarise writes inside ram:D081-D480 / D894-F17F and probe
 *      key addresses (d9a0, e02b, d081, edac, e36f).
 *   4. Optional script argument "dump": writes ram:D000-FFFF to
 *      /tmp/opencode/postboot.bin.
 *
 * I/O policy: Z80 IN/OUT touch the io address space, which is not
 * backed by real hardware here. A memory-fault handler answers any
 * uninitialised read with 0xFF bytes, which keeps poll loops happy.
 */
import java.io.FileOutputStream;
import java.math.BigInteger;
import java.util.TreeSet;

import ghidra.app.emulator.EmulatorHelper;
import ghidra.app.script.GhidraScript;
import ghidra.pcode.memstate.MemoryFaultHandler;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSetView;
import ghidra.program.model.lang.Register;
import ghidra.program.model.mem.MemoryBlock;

public class BootTrace extends GhidraScript {

	private static final int ENTRY = 0xD681; // dispatcher startup
	private static final int IDLE = 0xD6AC; // resident idle loop
	private static final long INITIAL_SP = 0xF000L;
	private static final long STEP_LIMIT = 1_000_000L;

	@Override
	public void run() throws Exception {
		Address entry = addr("ram:" + hex4(ENTRY));
		Address idle = addr("ram:" + hex4(IDLE));

		// ---- preconditions -------------------------------------------------
		MemoryBlock battery = currentProgram.getMemory().getBlock(addr("ram:8000"));
		if (battery == null || !battery.isInitialized()) {
			printerr("BootTrace: battery_ram block missing - run FillBatteryRam first.");
			return;
		}
		byte first = currentProgram.getMemory().getByte(entry);
		if ((first & 0xff) != 0xC3) { // JP opcode expected
			printerr("BootTrace: ram:d681 does not start with JP (got " +
					Integer.toHexString(first & 0xff) + "h). Run FillBatteryRam first.");
			return;
		}

		ensureIoStub();

		EmulatorHelper emu = new EmulatorHelper(currentProgram);
		try {
			emu.setMemoryFaultHandler(new FaultFillFF());
			registerStubs(emu);

			// Preload the banked window with ROM bank 0 content -
			// on real hardware bank 0 is mapped at reset, and both
			// the (7FFC) chain pointer and the load-script stream
			// live inside it.
			byte[] bank0 = new byte[0x8000];
			int nb = currentProgram.getMemory().getBytes(
					addr("ROM00:0000"), bank0);
			if (nb == 0x8000) {
				emu.writeMemory(addr("ram:0000"), bank0);
				println("BootTrace: banked window preloaded with ROM00 image.");
			} else {
				printerr("BootTrace: short read of ROM00 (" + nb + " bytes) - continuing.");
			}

			emu.enableMemoryWriteTracking(true);

			Register sp = emu.getStackPointerRegister();
			Register pc = emu.getPCRegister();
			if (sp == null || pc == null) {
				printerr("BootTrace: cannot identify SP/PC registers.");
				return;
			}
			emu.writeRegister(sp, INITIAL_SP);
			emu.writeRegister(pc, BigInteger.valueOf(ENTRY));

			emu.setBreakpoint(idle);

			println("BootTrace: starting emulation at " + entry + ", breakpoint at " + idle);

			long steps = 0;
			boolean ok = true;
			long[] pcHist = new long[64];
			int histIdx = 0;
			while (steps < STEP_LIMIT) {
				Address curPc = emu.getExecutionAddress();
				pcHist[histIdx++ % pcHist.length] = curPc == null ? -1 : curPc.getOffset();
				ok = emu.step(monitor);
				steps++;
				Address cur = emu.getExecutionAddress();
				if (cur != null && cur.equals(idle)) {
					break;
				}
				if (!ok) {
					break;
				}
				if (cur != null && cur.getOffset() == 0x0000L) {
					println("BootTrace: PC reached 0000 (reset vector executed?) at step " + steps);
					break;
				}
				if (steps % 50000 == 0) {
					println("BootTrace: ... " + steps + " steps, PC=" + cur);
				}
			}
			StringBuilder hb = new StringBuilder("BootTrace: last PCs:");
			for (int i = 0; i < pcHist.length && steps > 0; i++) {
				int idx = (histIdx + i) % pcHist.length;
				if (pcHist[idx] >= 0) {
					hb.append(" ").append(hex4((int) pcHist[idx]));
				}
			}
			println(hb.toString());

			Address end = emu.getExecutionAddress();
			println("BootTrace: stopped after " + steps + " steps at " + end +
					(ok ? "" : " (step error: " + emu.getLastError() + ")"));
			if (end != null && end.equals(idle)) {
				println("BootTrace: SUCCESS - idle loop reached.");
			} else {
				printerr("BootTrace: idle loop NOT reached.");
			}

			// capture tracked writes AND emulator memory contents
			// BEFORE disposing the emulator - its MemoryState is
			// separate from the program database!
			lastTrackedWrites = emu.getTrackedMemoryWriteSet();
			capturedPostBoot = emu.readMemory(addr("ram:D000"), 0x3000);
			reportWrites();
			probeKeys();

			String[] args = getScriptArgs();
			if (args != null && args.length > 0 && "dump".equalsIgnoreCase(args[0])) {
				dumpCaptured();
			}
		} finally {
			emu.dispose();
		}
	}

	// ------------------------------------------------------------------

	/**
	 * Z80 SLEIGH models DI/EI (and some I/O) as CALLOTHER pcode ops the
	 * basic emulator does not implement. Register no-op handlers so boot
	 * can continue; interrupts never fire in this emulation, so doing
	 * nothing for DI/EI is semantically fine here.
	 */
	private void registerStubs(EmulatorHelper emu) {
		String[] ops = { "disableMaskableInterrupts", "enableMaskableInterrupts" };
		for (final String name : ops) {
			emu.registerCallOtherCallback(name, new ghidra.pcode.emulate.BreakCallBack() {
				@Override
				public boolean pcodeCallback(ghidra.pcode.pcoderaw.PcodeOpRaw op) {
					println("BootTrace: stubbed CALLOTHER '" + name + "'");
					return true;
				}
			});
		}
	}

	/** Answers every uninitialised memory read with 0xFF bytes. */
	private static class FaultFillFF implements MemoryFaultHandler {
		@Override
		public boolean uninitializedRead(Address addr, int size, byte[] buf, int offset) {
			for (int i = 0; i < size; i++) {
				buf[offset + i] = (byte) 0xFF;
			}
			return true;
		}

		@Override
		public boolean unknownAddress(Address addr, boolean write) {
			return false;
		}
	}

	/** io space stub so Z80 IN/OUT never faults on an absent block. */
	private void ensureIoStub() throws Exception {
		Address ioStart = addr("io:0000");
		if (ioStart == null) {
			return;
		}
		MemoryBlock blk = currentProgram.getMemory().getBlock(ioStart);
		if (blk != null && blk.isInitialized()) {
			// already present - just refresh readiness values below
		} else {
			int tx = currentProgram.startTransaction("io_stub");
			try {
				if (blk != null) {
					println("BootTrace: replacing UNINITIALIZED io block with stub.");
					currentProgram.getMemory().removeBlock(blk, monitor);
				}
				blk = currentProgram.getMemory().createInitializedBlock(
						"io_stub", ioStart, 0x10000L, (byte) 0xFF, monitor, false);
				println("BootTrace: created io_stub block (64K of FFh).");
			} finally {
				currentProgram.endTransaction(tx, true);
			}
		}
		// Peripheral readiness values the firmware polls for:
		//   port 28h (indexed-comms data/status): bit7 clear = ready
		//   port 05h: lines asserted low -> 0 looks "active"
		//   port 49h: IR detectors idle
		byte[] patch = new byte[] { 0x00 };
		currentProgram.getMemory().setBytes(addr("io:0028"), patch);
		currentProgram.getMemory().setBytes(addr("io:0005"), patch);
	}

	private void reportWrites() {
		AddressSetView writes = lastTrackedWrites;
		if (writes == null) {
			printerr("BootTrace: no tracked write set available.");
			return;
		}
		TreeSet<Long> interesting = new TreeSet<Long>();
		for (ghidra.program.model.address.AddressRange r : writes.getAddressRanges()) {
			long s = r.getMinAddress().getOffset();
			long e = r.getMaxAddress().getOffset();
			if (e - s > 0x40000L) {
				e = s + 0x40000L; // safety cap
			}
			for (long a = s; a <= e; a++) {
				interesting.add(Long.valueOf(a));
			}
		}
		int inQueue = 0, inBlob = 0;
		for (long a : interesting) {
			if (a >= 0xED1CL && a <= 0xF17FL) {
				inQueue++;
			}
			if (a >= 0xD893L && a <= 0xE704L) {
				inBlob++;
			}
		}
		println("BootTrace: tracked written addresses total=" + interesting.size() +
				", within deferred-call queue ED1C-F17F=" + inQueue +
				", within chain-blob D893-E704=" + inBlob);
	}

	private AddressSetView lastTrackedWrites;

	private void probeKeys() {
		int[] keys = { 0xD9A0, 0xE02B, 0xD081, 0xEDAC, 0xE36F };
		StringBuilder sb = new StringBuilder("BootTrace: probes (emulator state) ");
		for (int k : keys) {
			if (capturedPostBoot == null) {
				sb.append(hex4(k)).append("=?  ");
				continue;
			}
			int idx = k - 0xD000;
			byte v = (idx >= 0 && idx < capturedPostBoot.length)
					? capturedPostBoot[idx] : (byte) 0xFF;
			sb.append(hex4(k)).append("=")
					.append(String.format("%02X", v & 0xff)).append("h  ");
		}
		println(sb.toString());
	}

	private void dumpCaptured() throws Exception {
		if (capturedPostBoot == null) {
			printerr("BootTrace: nothing captured.");
			return;
		}
		FileOutputStream fos = new FileOutputStream("/tmp/opencode/postboot.bin");
		fos.write(capturedPostBoot);
		fos.close();
		println("BootTrace: wrote " + capturedPostBoot.length +
				" bytes of emulated ram:D000-FFFF to /tmp/opencode/postboot.bin");
	}

	private byte[] capturedPostBoot;

	private Address addr(String s) {
		try {
			return currentProgram.getAddressFactory().getAddress(s);
		} catch (Exception e) {
			return null;
		}
	}

	private String hex4(int v) {
		String s = Integer.toHexString(v).toUpperCase();
		while (s.length() < 4) {
			s = "0" + s;
		}
		return s;
	}
}
