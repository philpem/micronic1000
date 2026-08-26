/* BootTrace.java
 *
 * //@category Micronic
 *
 * Micronic 1000 / PARCON 1000 (micron1.bin) boot dispatcher trace.
 *
 * Definitively traces the DIPOSB dispatcher boot sequence with Ghidra's
 * p-code emulator (generic ghidra.app.emulator.EmulatorHelper, NOT the
 * ghidra.pcode.emu.z80 API), starting at ram:d681 (the DIPOS dispatch
 * block copied there by FillBatteryRam). The dispatcher sets its own
 * SP, initialises its data area, performs chained loader syscalls whose
 * parameter pointer lives at ram:7FFC, makes kernel calls into the
 * resident kernel image at ram:F180-F68C, and finally parks in an idle
 * loop at ram:d6ac (LD BC,0 / CALL 0005h / JP d6ac).
 *
 * Preconditions (run FillBatteryRam first):
 *   - initialised "battery_ram" block ram:8000-ffff with the copied
 *     dispatch block (d681, 212h bytes) and kernel image (f180, 50Dh),
 *   - seeded system variables.
 *
 * What this script does:
 *   1. Verifies the preconditions (battery_ram present, ram:d681 holds
 *      initialised bytes).
 *   2. Installs an I/O stub: creates an initialised block "io_stub"
 *      covering io:0000-io:FFFF filled with FFh (skipped if present).
 *      Ghidra's Z80 p-code routes IN/OUT through the 'io' space, so
 *      prefilled FFh makes every IN return FFh and every OUT benign.
 *      NOTE: the block MUST exist before the EmulatorHelper is built,
 *      because the emulator snapshots program memory at construction.
 *   3. Sets SP=f000h, PC=d681h and single-steps up to 5,000,000
 *      instructions with instrumentation between steps:
 *        - histogram of every instruction executed inside the
 *          dispatcher module ram:d681-d897,
 *        - write tracking for ram:D894-ED1B and ram:E000-EFFF. The
 *          EmulatorHelper API offers no per-write hook, so we poll:
 *          the watched pages are shadow-diffed every CHECKPOINT_INTERVAL
 *          steps and once more at termination (per the documented
 *          fallback). First-observed written byte + final byte are kept
 *          per address; byte-level change pairs are reported (a 16-bit
 *          loader store appears as two adjacent byte changes).
 *        - SUCCESS stop when PC reaches ram:d6ac,
 *        - WARN (once per address) when executing below 8000h (banked /
 *          low-memory territory, e.g. the legitimate CALL 0005h BDOS
 *          vector used by the idle loop),
 *        - hard failure when PC reaches 0000h or tries to execute
 *          uninitialised memory.
 *   4. Fallback I/O emulation: if a step throws and the faulting
 *      instruction decodes as IN/OUT (DB nn, D3 nn, ED 4x/6x IN r,(C),
 *      ED 41-7F odd OUT (C),r), we manually force A=FFh, advance PC by
 *      the instruction length (from the Listing, default 2) and resume.
 *      This is an approximation: ED-prefixed IN forms touch other
 *      registers too, which we do not model. Capped at 100 recoveries.
 *   5. Summary: dispatcher histogram, sorted/compressed list of watched
 *      addresses written with first/final byte values, non-zero check
 *      for 0xD9A0, 0xE02B, 0xD081, 0xEDAC, 0xE36F, final 7FFCh pointer,
 *      and the last 20 executed addresses on failure/timeout.
 *   6. With script argument "dump": writes the post-boot image
 *      ram:D000-FFFF to /tmp/opencode/postboot.bin.
 *
 * Idempotent: re-runs are safe; the only persistent program change is
 * the optional io_stub block (never overwritten once present).
 */
import ghidra.app.emulator.EmulatorHelper;
import ghidra.app.script.GhidraScript;
import ghidra.pcode.memstate.MemoryState;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressFactory;
import ghidra.program.model.address.AddressSpace;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;

import java.io.File;
import java.io.FileOutputStream;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

public class BootTrace extends GhidraScript {

	private static final int ENTRY = 0xd681;      // dispatcher startup
	private static final int IDLE = 0xd6ac;       // success idle loop
	private static final int MOD_LO = 0xd681;     // dispatcher module range
	private static final int MOD_HI = 0xd897;
	private static final int W1_LO = 0xd894;      // watched write range 1
	private static final int W1_HI = 0xed1b;
	private static final int W2_LO = 0xe000;      // watched write range 2
	private static final int W2_HI = 0xefff;      // overlaps range 1 above e000
	private static final long INITIAL_SP = 0xf000;
	private static final long MAX_STEPS = 5000000L;
	private static final int CHECKPOINT_INTERVAL = 8192;
	private static final int PROGRESS_INTERVAL = 200000;
	private static final int MAX_IO_RECOVERIES = 100;
	private static final int RING_SIZE = 20;
	private static final int[] KEY_ADDRS =
		{ 0xd9a0, 0xe02b, 0xd081, 0xedac, 0xe36f };
	private static final File DUMP_FILE = new File("/tmp/opencode/postboot.bin");

	private Memory mem;
	private AddressSpace ramSpace;
	private AddressSpace ioSpace;
	private MemoryState memState;
	private EmulatorHelper emu;

	@Override
	public void run() throws Exception {
		mem = currentProgram.getMemory();
		AddressFactory af = currentProgram.getAddressFactory();

		ramSpace = af.getDefaultAddressSpace();
		ioSpace = af.getAddressSpace("io"); // may be null; handled later

		if (!preconditionsOk()) {
			return;
		}

		boolean txStarted = false;
		int tx = 0;
		try {
			tx = currentProgram.startTransaction("BootTrace_io_stub");
			txStarted = true;
			if (!ensureIoStub()) {
				// non-fatal: fallback IN/OUT recovery still armed
				println("BootTrace: continuing WITHOUT io space stub; " +
						"instruction-level IN/OUT fallback remains active.");
			}
		} finally {
			if (txStarted) {
				currentProgram.endTransaction(tx, true);
			}
		}

		try {
			trace();
		} catch (Throwable t) {
			printerr("BootTrace: fatal error during emulation: " + t);
			t.printStackTrace();
		}
	}

	// ------------------------------------------------------------------
	// setup

	private boolean preconditionsOk() {
		MemoryBlock bram = mem.getBlock(ramAddr(0x8000));
		if (bram == null || !bram.isInitialized()) {
			printerr("BootTrace: battery_ram block ram:8000-ffff is missing or " +
					"uninitialized. Run FillBatteryRam first.");
			return false;
		}
		byte[] probe = new byte[1];
		if (mem.getBytes(ramAddr(ENTRY), probe) != 1) {
			printerr("BootTrace: ram:" + hex4(ENTRY) +
					" is not initialized (dispatch block not copied?). " +
					"Run FillBatteryRam first.");
			return false;
		}
		println("BootTrace: precondition ok, battery_ram present, entry byte at ram:" +
				hex4(ENTRY) + " = " + hex2(probe[0] & 0xff));
		return true;
	}

	/**
	 * Creates the io_stub block io:0000-io:FFFF filled FFh if absent.
	 * Must run BEFORE the EmulatorHelper is constructed. Returns false
	 * when the io space does not exist (stub skipped, not fatal).
	 */
	private boolean ensureIoStub() {
		if (ioSpace == null) {
			printerr("BootTrace: WARN no 'io' address space found in this program; " +
					"cannot install I/O stub.");
			return false;
		}
		Address ioBase = ioSpace.getAddress(0x0000);
		MemoryBlock blk = mem.getBlock(ioBase);
		if (blk != null) {
			println("BootTrace: io block '" + blk.getName() + "' already present at " +
					ioBase + ", skipping io_stub creation.");
			return true;
		}
		try {
			mem.createInitializedBlock("io_stub", ioBase, 0x10000L, (byte) 0xff,
					monitor, false);
			println("BootTrace: created io_stub block io:0000-io:ffff filled FFh " +
					"(all IN reads will yield FFh).");
			return true;
		} catch (Exception e) {
			printerr("BootTrace: WARN failed to create io_stub block: " + e.getMessage());
			return false;
		}
	}

	// ------------------------------------------------------------------
	// main trace

	private void trace() {
		println("BootTrace: constructing emulator...");
		try {
			emu = new EmulatorHelper(currentProgram);
		} catch (Throwable t) {
			printerr("BootTrace: cannot build EmulatorHelper for " +
					currentProgram.getLanguageID() + ": " + t);
			return;
		}

		try {
			if (!grabMemoryState()) {
				return;
			}
			if (emu.writeRegister("SP", INITIAL_SP)) {
				println("BootTrace: SP <- " + hex4((int) INITIAL_SP));
			} else {
				printerr("BootTrace: WARN could not write SP register; " +
						"continuing (dispatcher sets its own SP immediately).");
			}
			try {
				emu.setExecutionAddress(ramAddr(ENTRY));
			} catch (Throwable t) {
				printerr("BootTrace: cannot set execution address ram:" +
						hex4(ENTRY) + ": " + t);
				return;
			}

			// Baseline snapshots of the watched ranges, as loaded from
			// the FillBatteryRam-initialised program image.
			byte[] base1 = snapshot(W1_LO, W1_HI);
			byte[] base2 = snapshot(W2_LO, W2_HI);
			byte[] snap1 = Arrays.copyOf(base1, base1.length);
			byte[] snap2 = Arrays.copyOf(base2, base2.length);

			TreeMap<Integer, Integer> hist = new TreeMap<Integer, Integer>();
			TreeMap<Integer, int[]> writes = new TreeMap<Integer, int[]>();
			Set<Long> lowWarned = new HashSet<Long>();
			List<Long> last20 = new ArrayList<Long>(RING_SIZE);

			long steps = 0;
			long totalExec = 0;
			int ioRecovers = 0;
			String outcome = null;

			while (!monitor.isCancelled()) {
				long pc = emu.getExecutionAddress().getOffset();
				last20.add(pc);
				if (last20.size() > RING_SIZE) {
					last20.remove(0);
				}

				if (pc == IDLE) {
					outcome = "SUCCESS: idle loop reached at ram:" + hex4(IDLE);
					break;
				}
				if (pc == 0x0000) {
					outcome = "FAIL: PC reached ram:0000";
					break;
				}
				if (pc >= MOD_LO && pc <= MOD_HI) {
					Integer k = Integer.valueOf((int) pc);
					Integer c = hist.get(k);
					hist.put(k, Integer.valueOf(c == null ? 1 : c.intValue() + 1));
				}
				if (pc < 0x8000 && lowWarned.add(Long.valueOf(pc))) {
					println("BootTrace: WARN executing below 8000h at ram:" +
							hex4((int) pc) + " (bank semantics unknown)");
				}

				int op0 = peekOp(pc);
				if (op0 < 0) {
					outcome = "FAIL: attempted to execute uninitialised memory at ram:" +
							hex4((int) pc);
					break;
				}
				boolean isIoInstr = decodeIsIo(pc);

				try {
					emu.step(1);
				} catch (Throwable t) {
					if (isIoInstr && ioRecovers < MAX_IO_RECOVERIES) {
						recoverIoFault(pc, ++ioRecovers);
						continue;
					}
					outcome = "FAIL: emulator error at ram:" + hex4((int) pc) +
							" after " + steps + " steps: " + t.getMessage();
					break;
				}

				steps++;
				totalExec++;

				if (totalExec % CHECKPOINT_INTERVAL == 0) {
					snap1 = snapshot(W1_LO, W1_HI);
					snap2 = snapshot(W2_LO, W2_HI);
					diffInto(writes, W1_LO, base1, snap1);
					diffInto(writes, W2_LO, base2, snap2);
				}
				if (totalExec % PROGRESS_INTERVAL == 0) {
					println("BootTrace: progress steps=" + totalExec + " pc=ram:" +
							hex4((int) pc) + " ioRecovers=" + ioRecovers +
							" writesSoFar=" + writes.size());
				}
				if (steps > MAX_STEPS) {
					outcome = "TIMEOUT: exceeded " + MAX_STEPS + " steps";
					break;
				}
			}

			if (monitor.isCancelled()) {
				outcome = "CANCELLED by user after " + totalExec + " steps";
			}
			if (outcome == null) {
				outcome = "ENDED unexpectedly after " + totalExec + " steps";
			}

			// Final diff pass catches anything changed since the last checkpoint.
			diffInto(writes, W1_LO, base1, snapshot(W1_LO, W1_HI));
			diffInto(writes, W2_LO, base2, snapshot(W2_LO, W2_HI));

			report(outcome, totalExec, steps, ioRecovers, hist, writes, last20);

			if (outcome.startsWith("SUCCESS") && wantsDump()) {
				dumpPostBootImage();
			}
		} finally {
			try {
				emu.dispose();
			} catch (Throwable t) {
				// ignore
			}
		}
	}

	private boolean wantsDump() {
		for (String a : getScriptArgs()) {
			if ("dump".equalsIgnoreCase(a)) {
				return true;
			}
		}
		return false;
	}

	/**
	 * Fetches the emulator MemoryState. Primary path uses
	 * EmulatorHelper.getMemoryState(); a guarded reflective fallback to
	 * getMemState() covers older/newer naming so partial functionality
	 * survives an API rename.
	 */
	private boolean grabMemoryState() {
		try {
			memState = emu.getMemoryState();
			return true;
		} catch (Throwable primaryMiss) {
			try {
				Method m = EmulatorHelper.class.getMethod("getMemState");
				memState = (MemoryState) m.invoke(emu);
				println("BootTrace: using reflective getMemState() fallback.");
				return true;
			} catch (Throwable t2) {
				printerr("BootTrace: cannot access emulator MemoryState: " + t2);
				return false;
			}
		}
	}

	// ------------------------------------------------------------------
	// memory helpers (all emulator-state accesses go through MemoryState,
	// which reflects live emulation rather than the static program image)

	private int peekOp(long off) {
		long v = memState.getValue(ramSpace, off, 1);
		return (int) v; // -1 when uninitialised/unmapped
	}

	private byte[] snapshot(int lo, int hi) {
		int len = hi - lo + 1;
		byte[] buf = new byte[len];
		for (int i = 0; i < len; i++) {
			buf[i] = (byte) memState.getValue(ramSpace, lo + i, 1);
		}
		return buf;
	}

	private void diffInto(TreeMap<Integer, int[]> writes, int lo, byte[] base,
			byte[] cur) {
		for (int i = 0; i < cur.length; i++) {
			if (cur[i] != base[i]) {
				int off = lo + i;
				int b = cur[i] & 0xff;
				int[] e = writes.get(Integer.valueOf(off));
				if (e == null) {
					writes.put(Integer.valueOf(off), new int[] { b, b }); // first, final
				} else {
					e[1] = b;
				}
			}
		}
	}

	// ------------------------------------------------------------------
	// I/O fault fallback

	/** True if the instruction at pc decodes as a Z80 IN/OUT form. */
	private boolean decodeIsIo(long pc) {
		int op0 = peekOp(pc);
		if (op0 == 0xdb || op0 == 0xd3) {
			return true; // IN A,(n) / OUT (n),A
		}
		if (op0 == 0xed) {
			int op1 = peekOp(pc + 1);
			if (op1 >= 0x40 && op1 <= 0x7f) {
				return true; // IN r,(C) even incl. OUT (C),0 / OUT (C),r odd
			}
		}
		return false;
	}

	/**
	 * Documented fallback for a faulting IN/OUT: force A=FFh (the stubbed
	 * port value), advance PC past the instruction and resume. Length is
	 * taken from the Listing when available, else assumed 2. Approximate
	 * for ED-prefixed IN forms (other result registers not modelled).
	 */
	private void recoverIoFault(long pc, int n) {
		int len = 2;
		try {
			Listing listing = currentProgram.getListing();
			Instruction ins = listing.getInstructionAt(ramAddr((int) pc));
			if (ins != null) {
				len = ins.getLength();
			}
		} catch (Throwable t) {
			// keep default 2
		}
		try {
			emu.writeRegister("A", 0xff);
		} catch (Throwable t) {
			printerr("BootTrace: WARN could not force A=ff during IO recovery.");
		}
		emu.setExecutionAddress(ramAddr((int) (pc + len)));
		println("BootTrace: IO fault #" + n + " at ram:" + hex4((int) pc) +
				" stubbed (A=ff, PC+=" + len + ")");
	}

	// ------------------------------------------------------------------
	// reporting

	private void report(String outcome, long totalExec, long steps, int ioRecovers,
			TreeMap<Integer, Integer> hist, TreeMap<Integer, int[]> writes,
			List<Long> last20) {
		println("");
		println("==================== BootTrace summary ====================");
		println("Outcome            : " + outcome);
		println("Steps requested/done: " + steps + " / " + totalExec);
		println("IO fallback stubs  : " + ioRecovers);

		int histTotal = 0;
		for (Integer c : hist.values()) {
			histTotal += c.intValue();
		}
		println("--- Dispatcher module ram:" + hex4(MOD_LO) + "-" + hex4(MOD_HI) +
				": " + hist.size() + " unique addresses, " + histTotal +
				" executions ---");
		for (Map.Entry<Integer, Integer> e : hist.entrySet()) {
			println("  ram:" + hex4(e.getKey().intValue()) + "  x" + e.getValue());
		}

		int n1 = 0;
		int n2 = 0;
		for (Integer off : writes.keySet()) {
			if (off.intValue() >= W1_LO && off.intValue() <= W1_HI) {
				n1++;
			}
			if (off.intValue() >= W2_LO && off.intValue() <= W2_HI) {
				n2++;
			}
		}
		println("--- Written addresses ram:" + hex4(W1_LO) + "-" + hex4(W1_HI) +
				" : " + n1 + " unique");
		println("--- Written addresses ram:" + hex4(W2_LO) + "-" + hex4(W2_HI) +
				" : " + n2 + " unique (overlap e000-ed1b counted in both) ---");
		println("Runs compress consecutive addresses sharing identical first/final bytes:");
		printRuns(writes);

		println("--- Key address check (final emulated image) ---");
		for (int ka : KEY_ADDRS) {
			int v = memState.getValue(ramSpace, ka, 1);
			String state;
			if (v < 0) {
				state = "UNINITIALISED";
			} else if ((v & 0xff) != 0) {
				state = "NON-ZERO";
			} else {
				state = "zero";
			}
			String inWatch = "";
			if (ka >= W1_LO && ka <= W1_HI || ka >= W2_LO && ka <= W2_HI) {
				int[] e = writes.get(Integer.valueOf(ka));
				inWatch = e == null ? "" : "  [tracked write first=" + hex2(e[0]) +
						" final=" + hex2(e[1]) + "]";
			} else {
				inWatch = "  [outside watched ranges]";
			}
			println("  ram:" + hex4(ka) + " = " +
					(v < 0 ? "??" : hex2(v & 0xff)) + "  " + state + inWatch);
		}

		long ptr = memState.getValue(ramSpace, 0x7ffc, 1) |
				(memState.getValue(ramSpace, 0x7ffd, 1) << 8);
		println("Loader param pointer ram:7FFC final value: " + hex4((int) ptr));

		if (!outcome.startsWith("SUCCESS")) {
			StringBuilder sb = new StringBuilder("Last executed addresses:");
			for (Long pc : last20) {
				sb.append(" ").append(hex4(pc.intValue()));
			}
			println(sb.toString());
		}
		println("===========================================================");
	}

	/** Prints the written-address set compressed into maximal runs. */
	private void printRuns(TreeMap<Integer, int[]> writes) {
		Integer prevOff = null;
		int runStart = 0;
		int runEnd = 0;
		int[] runVals = null;
		int runLen = 0;
		for (Map.Entry<Integer, int[]> e : writes.entrySet()) {
			int off = e.getKey().intValue();
			int[] vals = e.getValue();
			boolean contig = prevOff != null && off == prevOff.intValue() + 1;
			boolean sameVals = runVals != null && vals[0] == runVals[0] &&
					vals[1] == runVals[1];
			if (contig && sameVals) {
				runEnd = off;
				runLen++;
			} else {
				flushRun(runVals, runStart, runEnd, runLen);
				runStart = off;
				runEnd = off;
				runVals = vals;
				runLen = 1;
			}
			prevOff = e.getKey();
		}
		flushRun(runVals, runStart, runEnd, runLen);
	}

	private void flushRun(int[] vals, int start, int end, int len) {
		if (vals == null || len == 0) {
			return;
		}
		if (len == 1) {
			println("  ram:" + hex4(start) + ": first=" + hex2(vals[0]) +
					" final=" + hex2(vals[1]));
		} else {
			println("  ram:" + hex4(start) + "-ram:" + hex4(end) + " (" + len +
					" bytes): first=" + hex2(vals[0]) + " final=" + hex2(vals[1]));
		}
	}

	// ------------------------------------------------------------------
	// dump

	private void dumpPostBootImage() {
		try {
			DUMP_FILE.getParentFile().mkdirs();
			byte[] img = snapshot(0xd000, 0xffff); // 0x3000 bytes
			FileOutputStream fos = new FileOutputStream(DUMP_FILE);
			try {
				fos.write(img);
			} finally {
				fos.close();
			}
			println("BootTrace: dumped ram:D000-ffff (" + img.length +
					" bytes) -> " + DUMP_FILE.getAbsolutePath());
		} catch (Exception e) {
			printerr("BootTrace: dump failed: " + e);
		}
	}

	// ------------------------------------------------------------------

	private Address ramAddr(int off) {
		return ramSpace.getAddress(off & 0xffffL);
	}

	private String hex4(int v) {
		String s = Integer.toHexString(v & 0xffff).toUpperCase();
		while (s.length() < 4) {
			s = "0" + s;
		}
		return s;
	}

	private String hex2(int v) {
		String s = Integer.toHexString(v & 0xff).toUpperCase();
		if (s.length() < 2) {
			s = "0" + s;
		}
		return s;
	}
}
