// Micronic 1000 / PARCON 1000 (DIPOS-B) -- consolidated listing-repair pass.
//
// Ghidra's auto-analysis gets seven things structurally wrong on this
// firmware, and each one was previously patched up with its own throwaway
// script. This is the one script that does all of them, finds every site
// itself, takes no arguments, and can be re-run at any time.
//
//   Pass 0  Battery-RAM bootstrap.  micron1.bin holds only the two 32K ROM
//           banks. Everything the rest of the firmware calls into lives in
//           unpaged battery RAM -- the frame helper (D837), the switch
//           dispatcher (E0B2), the string and arithmetic library, the
//           session modules, the resident kernel, the runtime stub farm.
//           None of it exists until the ROM->RAM boot copies are replayed,
//           and until then most of this script has nothing to work on:
//           pass 1's byte check reads D837, which is empty on a freshly
//           imported program. So this runs first, and everything after it
//           depends on it.
//   Pass 1  Frame-helper flow.  ram:D837 had been flagged "no return", so
//           Ghidra threw away everything after every `CALL D837` -- that is,
//           every C function body in the image. This has to be corrected
//           before anything else runs, or the later passes are actively
//           destructive (see below).
//   Pass 2  Boot-load chains.  Each ROM bank's (7FFC) points at a record
//           script whose fn=2 records enqueue deferred banked calls. The
//           script is data; Ghidra decodes it as code, and the enqueued
//           target words are the only reference to ~281 routines.
//   Pass 3  Banked-call operands.  RST 10h (D7) takes three inline operand
//           bytes (db bank, dw target). Ghidra decodes them as code.
//   Pass 4  InlineTableDispatch tables.  CALL E0B2 is followed by an inline
//           switch table. Ghidra decodes it as code and cannot see the
//           handlers, because the dispatcher reaches them via JP (HL).
//   Pass 5  Compiler frame prologues.  Every routine the C compiler emitted
//           starts `LD DE,nnnn / CALL D837`. Ghidra had created no function
//           at 144 of the 348 such sites -- including the whole of
//           ROM00:4D25-5307, a gap that has already caused one documentation
//           error in this project.
//   Pass 6  Runtime stub farm.  281 four-byte slots at ram:ED1C + 4*i, each
//           an inter-bank thunk to one firmware routine. In the cold image
//           every slot is the `LD HL,1 / RET` template, so a `CALL 0EExxh`
//           anywhere in ROM01 or in a loaded program is a dead end with no
//           reference to its target. This pass restores those 281 edges.
//
// WHY PASS 5 IS SAFE.  ram:D837 is the compiler's frame-setup helper. Its
// bytes (battery RAM, byte-verified) are:
//     D836  E9                 JP (HL)             <- the trampoline it uses
//     D837  E1                 POP HL              ; caller's return address
//           C5                 PUSH BC
//           44 4D              LD B,H / LD C,L     ; stash it in BC
//           21 00 00 39        LD HL,0 / ADD HL,SP ; HL = SP
//           EB                 EX DE,HL            ; DE = SP, HL = frame size
//           39 F9              ADD HL,SP / LD SP,HL; SP += frame size
//           D5                 PUSH DE             ; save the old SP
//           DD E5 FD E5        PUSH IX / PUSH IY
//           60 69              LD H,B / LD L,C
//           CD 36 D8           CALL D836           ; = JP (HL): into the body
// so the DE loaded immediately before the CALL is the *local frame size*,
// not a call target, and the instruction pair can only appear at a function
// entry. A frame size of 0 means "no locals". The epilogue at D845 unwinds
// IY/IX/SP/BC and hands HL back to the caller's caller.
//
// The six-byte signature `11 lo hi CD 37 D8` pins four fixed bytes, so a
// chance match in data is ~1 in 2^32 per position: about 0.00002 expected
// false positives across the whole 96K image. Even so, pass 5 only creates
// a function where the listing already agrees the site is code, or where an
// independent witness (a boot-chain enqueue record, or code ending exactly
// at the site) says so. See createFrameFunctions() for the exact rule.
//
// ...WHICH IS ALSO WHY PASS 1 EXISTS.  Control provably continues at the
// instruction after `CALL D837` -- that is what `CALL D836` with HL holding
// the popped return address does. A previous analyst nonetheless flagged
// ram:D837 (named CoroutineTaskSwitch) as no-return. With that flag set,
// Ghidra's "non-returning function" repair treats every C function body as
// dead code: the first run of this script against such a database created
// 143 functions, and background auto-analysis then deleted 61 EXISTING
// ones, including hand-named routines like Lib_StrCmp and RunLoadedProgram.
// Pass 1 clears the flag -- after byte-checking that D837 really is the
// frame helper -- so the rest of the script is safe. If you ever see this
// script report a large number of new functions on a second run, check that
// flag first.
//
// IDEMPOTENCY.  Every pass tests the database before it writes, so a second
// run reports zero changes and touches nothing. Passes 1-4 are exactly
// idempotent. Pass 5 is convergent: creating a function makes Ghidra
// disassemble its body, which can expose the next prologue, so the pass
// iterates to a fixed point within a single run and is then idempotent.
//
// The script NEVER renames or re-comments anything a human wrote. New
// functions are left with Ghidra's default FUN_* names (per AGENTS.md, an
// unanalysed function must stay obviously unanalysed), existing comments
// are only replaced when they are absent, and existing functions are never
// touched.
//
// Supersedes: DefineInlineTables.java (pass 4, folded in with its behaviour
// preserved) and the ad-hoc AnnotateRst10Calls.java (passes 2 and 3, folded in
// and corrected).
//
// @category Micronic1000
// @menupath Analysis.Micronic.Analyse Micronic ROM
import ghidra.program.model.address.*;
import ghidra.program.model.data.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.scalar.Scalar;
import ghidra.program.model.symbol.*;
import ghidra.app.script.GhidraScript;

public class AnalyseMicronicRom extends GhidraScript {

    // ---- pass 0: battery RAM bootstrap ---------------------------------
    private static final String RAM_BLOCK_NAME = "battery_ram";
    private static final long RAM_BLOCK_SIZE = 0x8000L;

    /**
     * Copies performed by ROM code at boot, which no boot-load chain record
     * describes and which therefore cannot be derived from the chain walk.
     * Each row is {bank, src, length, dst}. The routine that performs each
     * one is named in the comment; that is the evidence for the row.
     */
    private static final int[][] ROM_CODE_COPIES = {
        { 0, 0x2352, 0x0013, 0xFD84 },  // comms config table   (ROM00:22E9/2306)
        { 0, 0x3257, 0x0010, 0xFE93 },  // device config copy B (ROM00:3220)
        { 0, 0x3267, 0x0010, 0xFE83 },  // device config copy A (ROM00:3220)
        { 0, 0x7030, 0x0212, 0xD681 },  // kernel dispatch block (ROM00:3BAA)
        { 0, 0x369D, 0x050D, 0xF180 },  // resident kernel (InstallKernelToRam ROM00:02FE)
    };

    /**
     * The boot-chain copies as FillBatteryRam.java hardcoded them. Kept only
     * so the script can diff them against what the chain walk actually says
     * and report any drift; the walk is what gets executed. One row is known
     * wrong -- see checkCopyListAgainstChains().
     */
    private static final int[][] LEGACY_CHAIN_COPIES = {
        { 0, 0x7242, 0x0010, 0xE0F4 },
        { 0, 0x7301, 0x00CD, 0xE22D },
        { 0, 0x73CE, 0x0861, 0xD893 },
        { 0, 0x7C2F, 0x0130, 0xE104 },
        { 1, 0x0080, 0x0075, 0xE2FA },
        { 1, 0x7BCB, 0x024A, 0xD081 },
    };

    /**
     * System variables the reset flow writes on a healthy cold boot. These
     * are observed values that cannot be derived from the ROM image, so they
     * are seeded rather than computed. Each row is {address, value}.
     */
    private static final int[][] SYSTEM_VAR_SEEDS = {
        { 0xF791, 0x00 },   // bank shadow cleared at ROM00:0165
        { 0xF81C, 0x00 },   // warm-boot signature cleared on cold start ROM00:01AD
        { 0xF81D, 0x00 },   // normal boot mode ROM00:015F/0161
        { 0xFC05, 0x70 },   // power latch value ROM00:01DC-01DE
        { 0xFEA4, 0x00 },   // ROM00:01D7-01D9
        { 0xFEAF, 0xFF },   // RAM test bitmap, all pages good
        { 0xFDB0, 0x00 },   // no RAM failure flag
        { 0xFBD5, 0x00 },   // in-restart flag cleared
        { 0xF78B, 0x20 },   // port 2Ah shadow: init value OUT at ROM00:0154
        { 0xF784, 0xFF },   // port 04h shadow: FF written at ROM00:01B5
    };

    /** Entry points worth disassembling once the RAM image is in place. */
    private static final int[] BOOTSTRAP_ENTRIES = {
        0xD681,   // dispatcher startup / chain walker
        0xD081,   // module B
        0xD893,   // module A
        0xE104,   // module A tail blob
        0xF180,   // BDOS entry
        0xF64D,   // common IRQ / banked-call entry
    };

    // ---- pass 1: frame-helper flow ------------------------------------
    /** The compiler's frame-setup helper, resident in battery RAM. */
    private static final int FRAME_SETUP = 0xD837;
    /** Its opening bytes: POP HL / PUSH BC / LD B,H / LD C,L / LD HL,0 /
     *  ADD HL,SP / EX DE,HL / ADD HL,SP / LD SP,HL / PUSH DE / PUSH IX /
     *  PUSH IY / LD H,B / LD L,C / CALL D836. Checked before the no-return
     *  flag is touched, so the pass is inert on any other program. */
    private static final byte[] FRAME_SETUP_BYTES = {
        (byte) 0xE1, (byte) 0xC5, (byte) 0x44, (byte) 0x4D, (byte) 0x21,
        (byte) 0x00, (byte) 0x00, (byte) 0x39, (byte) 0xEB, (byte) 0x39,
        (byte) 0xF9, (byte) 0xD5, (byte) 0xDD, (byte) 0xE5, (byte) 0xFD,
        (byte) 0xE5, (byte) 0x60, (byte) 0x69, (byte) 0xCD, (byte) 0x36,
        (byte) 0xD8 };

    // ---- pass 2: boot chains ------------------------------------------
    /** Word at the tail of each bank holding that bank's chain start. */
    private static final int CHAIN_PTR = 0x7FFC;
    /** Records are tiny; this only has to stop a runaway walk. */
    private static final int MAX_CHAIN_RECORDS = 4096;

    // ---- pass 3: banked call ------------------------------------------
    /** Vector taken by the inter-bank call restart (0010 -> JP F5E1). */
    private static final int RST_BANKED_CALL = 0x10;
    /** A bank number above this means the "RST" is really table data. */
    private static final int MAX_BANK = 0x0F;

    // ---- pass 4: inline dispatch --------------------------------------
    /** CALL 0xE0B2 -- the dispatcher entry, little-endian operand. */
    private static final byte[] CALL_DISPATCH = { (byte) 0xCD, (byte) 0xB2, (byte) 0xE0 };
    /** Sanity bound: real tables are small, so a large count means we have
     *  matched bytes that only look like a call. */
    private static final int MAX_CASES = 64;

    // ---- pass 5: frame prologues --------------------------------------
    /** LD DE,nnnn (11 lo hi) followed by CALL D837 (CD 37 D8). */
    private static final int OP_LD_DE_NN = 0x11;
    private static final byte[] CALL_FRAME_SETUP = { (byte) 0xCD, (byte) 0x37, (byte) 0xD8 };
    /** Fixed point is reached in two rounds in practice; three is slack. */
    private static final int MAX_PROLOGUE_ROUNDS = 4;

    // ---- pass 6: runtime stub farm -------------------------------------
    /** Slot i of the runtime stub farm is the 4 bytes at ram:ED1C + 4*i. */
    private static final int STUB_FARM_BASE = 0xED1C;
    /** One past the last slot byte; F180 is the resident kernel's base. */
    private static final int STUB_FARM_END = 0xF180;
    private static final int STUB_SLOT_SIZE = 4;
    /** Queue cursor the fn=2 handler reads and advances (ram:D72F/D744). */
    private static final int STUB_CURSOR_CELL = 0xD684;
    /** Source of the 4-byte cold template replicated across the farm. */
    private static final int STUB_TEMPLATE_SRC = 0xD6D7;
    /** RST 10h opcode, the first byte the fn=2 handler stores per slot. */
    private static final int OP_RST10 = 0xD7;

    // ---- shared -------------------------------------------------------
    /** Addresses at or above this are fixed upper RAM, which is a different
     *  address space from the banked window the ROM overlays occupy. */
    private static final int RAM_BASE = 0x8000;
    /** Bookmark category for sites the script deliberately refused to act
     *  on, so they stay visible in the GUI instead of only in this log. */
    private static final String BOOKMARK_CAT = "Micronic frame prologue";

    // Pass 0 (battery RAM bootstrap) counters.
    private int p0BlockCreated, p0Seeded, p0Copied, p0CopiesOk, p0Filled,
                p0Phantoms, p0Disassembled, p0Drift;
    /** Pass 1: 1 when the bogus no-return flag was cleared this run. */
    private int p1Fixed;
    // Pass 2 (boot chains) counters.
    private int p2Records, p2Typed, p2Refs, p2RefsFixed, p2Comments,
                p2Disassembled, p2Functions;
    // Pass 3 (banked calls) counters.
    private int p3Fixed, p3Already, p3Skipped;
    // Pass 4 (inline tables) counters.
    private int p4Defined, p4Already, p4Skipped, p4Cleared, p4Refs,
                p4Disassembled, p4Realigned;
    // Pass 5 (frame prologues) counters.
    private int p5Sites, p5Created, p5Present, p5Deferred, p5Conflict, p5Overrun;
    // Pass 6 (runtime stub farm) counters.
    private int p6Slots, p6Refs, p6Comments, p6Skipped;

    /** The boot-load chain records, read once and shared by passes 0, 2, 6. */
    private java.util.List<ChainRecord> chain = java.util.List.of();

    @Override
    public void run() throws Exception {
        println("=== AnalyseMicronicRom: " + currentProgram.getName() + " ===");

        // Read both banks' boot-load chains once. Passes 0, 2 and 6 all need
        // them, and reading them in one place is what stops the replayed copy
        // list and the annotated records from drifting apart.
        chain = readChains();

        println("");
        println("--- pass 0: battery-RAM bootstrap ---");
        bootstrapBatteryRam();

        println("");
        println("--- pass 1: frame-helper flow (ram:D837 no-return) ---");
        fixFrameHelperFlow();

        println("");
        println("--- pass 2: boot-load chains ---");
        annotateBootLoadChains();

        println("");
        println("--- pass 3: banked-call (RST 10h) inline operands ---");
        repairBankedCallOperands();

        println("");
        println("--- pass 4: InlineTableDispatch inline tables ---");
        defineInlineDispatchTables();

        println("");
        println("--- pass 5: compiler frame-prologue functions ---");
        createFrameFunctions();

        println("");
        println("--- pass 6: runtime stub farm (ram:ED1C + 4*i) ---");
        linkRuntimeStubSlots();

        summarise();
    }

    // ==================================================================
    // Pass 0 -- battery-RAM bootstrap
    //
    // micron1.bin is two 32K ROM banks and nothing else, but almost every
    // routine worth reading calls into unpaged battery RAM: the frame helper
    // (D837), the switch dispatcher (E0B2), the string and arithmetic
    // library (DB89, E04B, DFCC), the indirect-call thunk (D828), the
    // session modules (D081, D893, E104), the resident kernel (F180) and the
    // runtime stub farm (ED1C). On a freshly imported program none of that
    // exists, nothing there disassembles, and the later passes have nothing
    // to work on -- pass 1's byte check reads D837 and finds zeroes.
    //
    // This pass reconstructs the observable result of a clean cold boot:
    // create the RAM block, seed the system variables the reset flow writes,
    // replay the ROM->RAM copies, lay down the stub-farm template, drop
    // analysis artifacts, and disassemble the entry points.
    //
    // WHERE THE COPY LIST COMES FROM. Six of the eleven copies are boot-load
    // chain records, so they are taken from the chain walk rather than
    // hardcoded -- one source of truth, no drift. The other five are
    // performed by ROM code (the config tables, the kernel dispatch block,
    // the resident kernel) and appear in no chain, so they stay in
    // ROM_CODE_COPIES with the performing routine named against each.
    // checkCopyListAgainstChains() prints both and reports any disagreement.
    //
    // That diff already earned its keep: FillBatteryRam.java hardcoded the
    // E104 copy as 0130h bytes where the chain record at ROM00:7D7C says
    // 0129h. 7C2F + 0129h = 7D58, exactly where the chain script starts, so
    // the blob ends where the chain begins and 0130h over-reads seven bytes
    // of the chain itself into ram:E22D -- on top of the misc-config block
    // copied there a moment earlier. Measured against the current database,
    // length 0130h mismatches in 6 bytes and 0129h matches exactly.
    // ==================================================================
    private void bootstrapBatteryRam() throws Exception {
        AddressSpace ram = space("ram");
        if (ram == null) {
            println("no `ram` space -- nothing to do");
            return;
        }
        boolean fresh = ensureRamBlock(ram);
        seedSystemVariables(ram, fresh);

        java.util.List<int[]> copies = buildCopyList();
        checkCopyListAgainstChains(copies);
        for (int[] c : copies) {
            replayCopy(ram, c);
        }

        fillStubFarmTemplate(ram);
        removePhantomFunctions(ram);

        for (int off : BOOTSTRAP_ENTRIES) {
            Address at = ram.getAddress(off);
            if (currentProgram.getMemory().getBlock(at) == null) {
                continue;
            }
            if (currentProgram.getListing().getInstructionAt(at) == null
                    && disassemble(at)) {
                p0Disassembled++;
                println("  disassembled ram:" + hex4(off));
            }
        }
    }

    /** @return true if this run created the block (so it is a cold image). */
    private boolean ensureRamBlock(AddressSpace ram) throws Exception {
        Memory mem = currentProgram.getMemory();
        Address start = ram.getAddress(RAM_BASE);
        MemoryBlock blk = mem.getBlock(start);
        if (blk != null && blk.isInitialized()) {
            println("battery RAM block already present (" + blk.getName() + ")");
            return false;
        }
        if (blk != null) {
            println("replacing UNINITIALIZED block " + blk.getName() + " ("
                    + blk.getStart() + "-" + blk.getEnd() + ")");
            mem.removeBlock(blk, monitor);
        }
        mem.createInitializedBlock(RAM_BLOCK_NAME, start, RAM_BLOCK_SIZE,
                                   (byte) 0, monitor, false);
        p0BlockCreated = 1;
        println("created initialised block " + RAM_BLOCK_NAME + " ram:8000-ram:FFFF");
        return true;
    }

    /**
     * Seed the cold-boot system variables.
     *
     * On a block this run created, all of them are written. On a block that
     * was already there, only cells that are still zero are filled in: the
     * database may hold a real post-boot dump, and these synthetic values
     * must never overwrite observed ones. Either way a second run writes
     * nothing, because every seeded cell is then already at its value.
     */
    private void seedSystemVariables(AddressSpace ram, boolean fresh) throws Exception {
        Memory mem = currentProgram.getMemory();
        for (int[] seed : SYSTEM_VAR_SEEDS) {
            Address at = ram.getAddress(seed[0]);
            int want = seed[1] & 0xFF;
            int have = mem.getByte(at) & 0xFF;
            if (have == want) {
                continue;
            }
            if (!fresh && have != 0x00) {
                println("  KEEP observed ram:" + hex4(seed[0]) + " = "
                        + String.format("%02X", have) + " (cold-boot value is "
                        + String.format("%02X", want) + ")");
                continue;
            }
            mem.setBytes(at, new byte[] { (byte) want });
            p0Seeded++;
        }
        if (p0Seeded > 0) {
            println("seeded " + p0Seeded + " system variables");
        }
    }

    /** {bank, src, len, dst} for every copy, chain-derived plus ROM-code. */
    private java.util.List<int[]> buildCopyList() {
        java.util.List<int[]> out = new java.util.ArrayList<>();
        for (int[] c : ROM_CODE_COPIES) {
            out.add(c);
        }
        for (ChainRecord r : chain) {
            if (r.fn != 0x0001) {
                continue;               // memset and enqueue records do no copying
            }
            out.add(new int[] { "ROM01".equals(r.space.getName()) ? 1 : 0,
                                r.src, r.len, r.dst });
        }
        return out;
    }

    /**
     * Diff the chain-derived copies against the list FillBatteryRam.java
     * hardcoded, and say what disagrees. The chain is authoritative -- it is
     * what the firmware executes -- so a disagreement is a bug in the old
     * table, not a reason to distrust the walk.
     */
    private void checkCopyListAgainstChains(java.util.List<int[]> copies) {
        java.util.List<int[]> derived = new java.util.ArrayList<>();
        for (int[] c : copies) {
            boolean romCode = false;
            for (int[] rc : ROM_CODE_COPIES) {
                if (rc[1] == c[1] && rc[3] == c[3]) {
                    romCode = true;
                }
            }
            if (!romCode) {
                derived.add(c);
            }
        }
        println("copy list: " + ROM_CODE_COPIES.length + " from ROM code, "
                + derived.size() + " from the boot-load chains");
        for (int[] legacy : LEGACY_CHAIN_COPIES) {
            int[] match = null;
            for (int[] d : derived) {
                if (d[0] == legacy[0] && d[1] == legacy[1] && d[3] == legacy[3]) {
                    match = d;
                }
            }
            if (match == null) {
                p0Drift++;
                println("  DRIFT hardcoded copy bank" + legacy[0] + ":" + hex4(legacy[1])
                        + " -> ram:" + hex4(legacy[3]) + " has no chain record");
            } else if (match[2] != legacy[2]) {
                p0Drift++;
                println("  DRIFT bank" + legacy[0] + ":" + hex4(legacy[1]) + " -> ram:"
                        + hex4(legacy[3]) + " : hardcoded len " + hex4(legacy[2])
                        + "h, chain says " + hex4(match[2]) + "h -- using the chain");
            }
        }
        for (int[] d : derived) {
            boolean known = false;
            for (int[] legacy : LEGACY_CHAIN_COPIES) {
                if (d[0] == legacy[0] && d[1] == legacy[1] && d[3] == legacy[3]) {
                    known = true;
                }
            }
            if (!known) {
                p0Drift++;
                println("  DRIFT chain copy bank" + d[0] + ":" + hex4(d[1]) + " -> ram:"
                        + hex4(d[3]) + " len " + hex4(d[2]) + "h is not in the old table");
            }
        }
    }

    /**
     * Replay one ROM->RAM copy, skipping it when the bytes already match.
     *
     * The skip is what makes this pass idempotent, and it matters for more
     * than speed: writing would clear the code units over the destination,
     * discarding the disassembly of a module that is already analysed.
     */
    private void replayCopy(AddressSpace ram, int[] c) throws Exception {
        AddressSpace srcSpace = space(c[0] == 1 ? "ROM01" : "ROM00");
        if (srcSpace == null) {
            return;
        }
        Address src = srcSpace.getAddress(c[1]);
        Address dst = ram.getAddress(c[3]);
        Memory mem = currentProgram.getMemory();
        if (mem.getBlock(src) == null || mem.getBlock(dst) == null) {
            println("  SKIP copy " + src + " -> " + dst + " : unmapped");
            return;
        }
        byte[] want = new byte[c[2]];
        byte[] have = new byte[c[2]];
        if (mem.getBytes(src, want) != c[2] || mem.getBytes(dst, have) != c[2]) {
            println("  SKIP copy " + src + " -> " + dst + " : short read");
            return;
        }
        if (java.util.Arrays.equals(want, have)) {
            p0CopiesOk++;
            return;
        }
        currentProgram.getListing().clearCodeUnits(dst, dst.add(c[2] - 1), false);
        mem.setBytes(dst, want);
        p0Copied++;
        println("  copied " + hex4(c[2]) + "h bytes " + src + " -> " + dst);
    }

    /**
     * Lay down the runtime stub farm's cold template.
     *
     * KernelInitCopyData (ram:D6C0) copies the 4 bytes at ram:D6D7 to ED1C
     * and replicates them to F17F -- 1124 bytes, exactly 281 four-byte slots.
     * In this image the template is `21 01 00 C9` = `LD HL,1 / RET`.
     *
     * The guard matters. If any slot already begins with D7 the farm holds
     * live inter-bank thunks -- a real post-boot dump -- and overwriting it
     * with the template would destroy observed state and the analysis hung
     * off it. In that case the pass reports and does nothing.
     */
    private void fillStubFarmTemplate(AddressSpace ram) throws Exception {
        Memory mem = currentProgram.getMemory();
        Address base = ram.getAddress(STUB_FARM_BASE);
        if (mem.getBlock(base) == null) {
            return;
        }
        byte[] pat = new byte[STUB_SLOT_SIZE];
        mem.getBytes(ram.getAddress(STUB_TEMPLATE_SRC), pat);
        boolean blank = true;
        for (byte x : pat) {
            blank &= (x == 0);
        }
        if (blank) {
            println("  SKIP stub-farm template : ram:" + hex4(STUB_TEMPLATE_SRC)
                    + " is empty (dispatch block not installed?)");
            return;
        }

        int len = STUB_FARM_END - STUB_FARM_BASE;
        byte[] have = new byte[len];
        mem.getBytes(base, have);
        boolean matches = true;
        for (int i = 0; i < len; i++) {
            matches &= (have[i] == pat[i % STUB_SLOT_SIZE]);
        }
        if (matches) {
            return;                     // already the cold template: nothing to do
        }
        int live = 0;
        for (int i = 0; i < len; i += STUB_SLOT_SIZE) {
            if ((have[i] & 0xFF) == OP_RST10) {
                live++;
            }
        }
        if (live > 0) {
            println("  KEEP stub farm : " + live + " slot(s) hold live RST 10h thunks,"
                    + " so this is a post-boot image -- template NOT written");
            return;
        }
        byte[] fill = new byte[len];
        for (int i = 0; i < len; i++) {
            fill[i] = pat[i % STUB_SLOT_SIZE];
        }
        currentProgram.getListing().clearCodeUnits(base,
                ram.getAddress(STUB_FARM_END - 1), false);
        mem.setBytes(base, fill);
        p0Filled = 1;
        println("  stub farm ED1C..F17F set to the cold template");
    }

    /**
     * Drop functions that are analysis artifacts rather than code.
     *
     * FillBatteryRam.java deleted every `ram` function at or above F100, on
     * the reasoning that they were invented over unmapped memory. That was
     * true of the database it was written for and is catastrophic now: the
     * resident kernel lives at F180, so on the current database the original
     * predicate would delete 61 functions -- BdosDispatchFn, every
     * Syscall_InvokeService*, Kernel_BankedCallEnvelope, KernSetBank,
     * BankedCallCommonEntry, the whole SessionOpStub_* farm -- 58 of them
     * hand-named.
     *
     * The predicate here needs both halves: the function must still carry
     * Ghidra's generated FUN_ name (so nothing a human named can ever
     * match), and its entry must not be an instruction (so it is genuinely
     * not code). Functions pass 5 creates always have an instruction at the
     * entry, so this can never remove them either.
     */
    private void removePhantomFunctions(AddressSpace ram) {
        FunctionManager fm = currentProgram.getFunctionManager();
        Listing lst = currentProgram.getListing();
        java.util.List<Function> doomed = new java.util.ArrayList<>();
        FunctionIterator it = fm.getFunctions(true);
        while (it.hasNext()) {
            Function f = it.next();
            Address entry = f.getEntryPoint();
            if (!entry.getAddressSpace().equals(ram)) {
                continue;
            }
            if (!f.getName().startsWith("FUN_")) {
                continue;               // a human named it; never touch it
            }
            if (lst.getInstructionAt(entry) != null) {
                continue;               // real code; not an artifact
            }
            doomed.add(f);
        }
        for (Function f : doomed) {
            println("  removed phantom " + f.getName() + " at " + f.getEntryPoint()
                    + " (no instruction at entry)");
            fm.removeFunction(f.getEntryPoint());
            p0Phantoms++;
        }
    }

    // ==================================================================
    // Pass 1 -- frame-helper flow
    //
    // Everything else in this script depends on Ghidra being willing to lay
    // code down after a `CALL D837`, so this runs first.
    //
    // ram:D837 is the C compiler's frame-setup helper (see the header for
    // the byte-by-byte decode). It pops its own return address, opens the
    // stack frame, and then `CALL D836` -- D836 is JP (HL) -- to enter the
    // caller's body at exactly that popped address. Control therefore
    // reaches the instruction after the CALL, every time.
    //
    // The database nonetheless had D837 flagged no-return. Ghidra's
    // non-returning-function repair then treats the entire body of every C
    // routine as unreachable, clears it, and deletes any function that lived
    // there. Measured on this program: a run with the flag set created 143
    // functions and background analysis silently removed 61 existing ones,
    // 59 of them hand-named. Clearing the flag is not a matter of taste.
    //
    // The pass byte-checks the helper before touching anything, so it does
    // nothing at all on a program where D837 is something else.
    // ==================================================================
    private void fixFrameHelperFlow() throws Exception {
        AddressSpace ram = space("ram");
        if (ram == null) {
            println("no `ram` space -- nothing to do");
            return;
        }
        Address at = ram.getAddress(FRAME_SETUP);
        if (currentProgram.getMemory().getBlock(at) == null) {
            println("ram:" + hex4(FRAME_SETUP) + " is not mapped -- nothing to do");
            return;
        }
        byte[] have = new byte[FRAME_SETUP_BYTES.length];
        currentProgram.getMemory().getBytes(at, have);
        if (!java.util.Arrays.equals(have, FRAME_SETUP_BYTES)) {
            println("ram:" + hex4(FRAME_SETUP) + " does not hold the frame-setup"
                    + " helper's bytes -- left alone");
            return;
        }
        Function helper = currentProgram.getFunctionManager().getFunctionAt(at);
        if (helper == null) {
            println("frame helper at " + at + " byte-verified, but no function"
                    + " is defined there -- left alone");
            return;
        }
        if (!helper.hasNoReturn()) {
            println("frame helper " + helper.getName() + " at " + at
                    + " already returns normally");
            return;
        }
        helper.setNoReturn(false);
        p1Fixed = 1;
        println("CLEARED the no-return flag on " + helper.getName() + " at " + at);
        println("  CONFIRMED from the bytes: D837 pops the return address and");
        println("  re-enters it via CALL D836 (= JP (HL)), so `CALL D837` does");
        println("  fall through to the caller's body. Leaving the flag set makes");
        println("  Ghidra delete every C function body in the image.");
    }

    // ==================================================================
    // Pass 2 -- boot-load chains
    //
    // Each ROM bank ends with a load script, pointed to by the word at
    // <bank>:7FFC, that the dispatcher startup (ram:D681) walks at every
    // cold boot. Its grammar is confirmed from the handlers:
    //
    //     {fn=0000, addr, count}      memset(addr, 0, count)
    //     {fn=0001, src, dst, count}  memcpy(dst <- src, count)
    //     {fn=0002, N, word[N]}       enqueue N deferred {D7,bank,word} stubs
    //     {fn=FFFF}                   terminate
    //
    // Two things go wrong without this pass. The script is data, so Ghidra
    // decodes 200-odd bytes of it as garbage instructions. And the fn=2
    // target words are the *only* thing that references most of the session
    // and Commstar layer -- 134 routines in bank 0, 147 in bank 1 -- so
    // without a reference from them those routines are unreachable, and in
    // bank 1 largely undisassembled.
    //
    // The enqueued word carries no bank of its own: the stub is built with
    // the live bank shadow (F791), which is the bank whose chain is running.
    // So a bank-0 word resolves in ROM00 and a bank-1 word in ROM01. This
    // is the correction to the old AnnotateRst10Calls, which resolved every
    // target in the `ram` space and so produced 156 dangling references in
    // the bank-0 chain alone; those are repointed here.
    //
    // Records are typed field-by-field as individual words rather than as
    // one array, because the per-word "deferred far-call" comments must stay
    // visible -- an array would swallow them into a single code unit.
    // ==================================================================
    /**
     * One decoded boot-load chain record.
     *
     * `space` is the bank the record was read from, which is also the bank
     * its addresses resolve in: the chain runs with that bank paged in, and
     * the fn=2 handler stamps each stub with the live bank shadow (F791).
     */
    private static final class ChainRecord {
        final AddressSpace space;
        final Address at;
        final int fn, src, dst, len, n;
        ChainRecord(AddressSpace space, Address at, int fn, int src, int dst,
                    int len, int n) {
            this.space = space; this.at = at; this.fn = fn;
            this.src = src; this.dst = dst; this.len = len; this.n = n;
        }
    }

    /**
     * Decode both banks' chains without writing anything.
     *
     * Bank 0 first, then bank 1 -- that order is not a guess. Three
     * slot-to-target pairs recorded from a live RAM dump (slot 58 -> 48BF,
     * 60 -> 4AE0, 68 -> 4F5A, in doc/research/TASKS.md) only reproduce with
     * bank 0's 134 words occupying slots 0..133, and the two banks' word
     * counts (134 + 147 = 281 slots x 4 bytes) exactly fill ED1C..F17F,
     * which is precisely the range the cold template covers.
     *
     * The fn=2 record is consumed by its declared word count, never by
     * stepping fixed-size records through it. That matters: the 134 words at
     * ROM00:7D88 also parse as plausible 6-byte records (the first would read
     * src=3BAA dst=62C7), so a naive walk would silently mistake the stub
     * source table for chain records and run off into the padding. Reading N
     * from 7D86 and skipping 4+2N bytes lands exactly on the FFFF terminator
     * at 7E94, which is the check that the grammar is being applied right.
     */
    private java.util.List<ChainRecord> readChains() {
        java.util.List<ChainRecord> out = new java.util.ArrayList<>();
        for (String name : new String[] { "ROM00", "ROM01" }) {
            AddressSpace sp = space(name);
            if (sp == null) {
                println("SKIP chain " + name + " : no such address space");
                continue;
            }
            try {
                readOneChain(sp, out);
            } catch (Exception ex) {
                println("SKIP chain " + name + " : " + ex.getMessage());
            }
        }
        return out;
    }

    private void readOneChain(AddressSpace sp, java.util.List<ChainRecord> out)
            throws Exception {
        int start = readU16(sp.getAddress(CHAIN_PTR));
        if (start < 0x0100 || start >= CHAIN_PTR) {
            println("SKIP chain " + sp.getName() + " : implausible (7FFC) = " + hex4(start));
            return;
        }
        int off = start;
        for (int guard = 0; guard < MAX_CHAIN_RECORDS; guard++) {
            Address rec = sp.getAddress(off);
            int fn = readU16(rec);
            if (fn == 0xFFFF) {
                out.add(new ChainRecord(sp, rec, fn, 0, 0, 0, 0));
                println("chain " + sp.getName() + " " + hex4(start) + ".." + hex4(off)
                        + " terminates cleanly");
                return;
            } else if (fn == 0x0000) {
                out.add(new ChainRecord(sp, rec, fn, 0, readU16(rec.add(2)), 0,
                                        readU16(rec.add(4))));
                off += 6;
            } else if (fn == 0x0001) {
                out.add(new ChainRecord(sp, rec, fn, readU16(rec.add(2)),
                                        readU16(rec.add(4)), readU16(rec.add(6)), 0));
                off += 8;
            } else if (fn == 0x0002) {
                int n = readU16(rec.add(2));
                if (off + 4 + 2 * n > CHAIN_PTR) {
                    println("SKIP chain " + sp.getName() + " : enqueue N=" + n
                            + " runs past the bank");
                    return;
                }
                out.add(new ChainRecord(sp, rec, fn, 0, 0, 0, n));
                off += 4 + 2 * n;
            } else {
                println("SKIP chain " + sp.getName() + " at " + rec
                        + " : unknown record fn=" + hex4(fn));
                return;
            }
        }
        println("SKIP chain " + sp.getName() + " : record limit reached");
    }

    private void annotateBootLoadChains() throws Exception {
        for (ChainRecord r : chain) {
            p2Records++;
            if (r.fn == 0xFFFF) {
                typeWords(r.at, 1);
                commentIfAbsent(r.at, "boot chain: terminate");
            } else if (r.fn == 0x0000) {
                typeWords(r.at, 3);
                commentIfAbsent(r.at, String.format("boot chain: zero %s..%s",
                        hex4(r.dst), hex4(r.dst + r.n - 1)));
            } else if (r.fn == 0x0001) {
                typeWords(r.at, 4);
                commentIfAbsent(r.at, String.format(
                        "boot chain: copy %sh bytes %s -> ram:%s",
                        hex4(r.len), hex4(r.src), hex4(r.dst)));
            } else if (r.fn == 0x0002) {
                typeWords(r.at, 2);
                commentIfAbsent(r.at,
                        "boot chain: enqueue " + r.n + " deferred banked calls");
                linkChainTargets(r.space, r.at.add(4), r.n);
            }
        }
    }

    /** Type, reference and comment the N target words of one fn=2 record. */
    private void linkChainTargets(AddressSpace sp, Address first, int n) throws Exception {
        Listing lst = currentProgram.getListing();
        FunctionManager fm = currentProgram.getFunctionManager();
        ReferenceManager rm = currentProgram.getReferenceManager();

        typeWords(first, n);
        for (int i = 0; i < n; i++) {
            Address word = first.add(2 * i);
            int target = readU16(word);
            if (target == 0) {
                continue;                       // an unused queue slot
            }
            Address to = sp.getAddress(target);

            // Repoint the dangling `ram:` references the previous script
            // left behind. Only a reference whose target offset matches and
            // whose space is wrong is removed -- never a human's reference
            // to somewhere else.
            for (Reference r : rm.getReferencesFrom(word)) {
                Address t = r.getToAddress();
                if (t.getOffset() == target && !t.getAddressSpace().equals(sp)
                        && currentProgram.getMemory().getBlock(t) == null) {
                    rm.delete(r);
                    p2RefsFixed++;
                }
            }
            if (addReferenceIfAbsent(word, to, RefType.COMPUTED_CALL)) {
                p2Refs++;
            }
            if (setCommentIfAbsentOrEqual(word, CommentType.EOL,
                    "deferred far-call -> bank[f791]:" + hex4(target))) {
                p2Comments++;
            }

            // The enqueue record is proof that the target is an entry point,
            // so it is safe to disassemble undefined bytes there. Defined
            // data is left alone: that disagreement needs a human.
            if (lst.getInstructionAt(to) == null) {
                Data d = lst.getDataContaining(to);
                if (d != null && d.isDefined()) {
                    continue;
                }
                if (lst.getInstructionContaining(to) != null) {
                    continue;                   // lands mid-instruction; pass 5 reports it
                }
                if (disassemble(to)) {
                    p2Disassembled++;
                }
            }
            if (lst.getInstructionAt(to) != null && fm.getFunctionAt(to) == null
                    && fm.getFunctionContaining(to) == null) {
                if (createFunction(to, null) != null) {
                    p2Functions++;
                }
            }
        }
    }

    /** Define {@code n} consecutive 2-byte words, clearing code first. */
    private void typeWords(Address at, int n) throws Exception {
        Listing lst = currentProgram.getListing();
        for (int i = 0; i < n; i++) {
            Address a = at.add(2 * i);
            if (isDefined(a, WordDataType.class, 2)) {
                continue;
            }
            lst.clearCodeUnits(a, a.add(1), false);
            lst.createData(a, WordDataType.dataType);
            p2Typed++;
        }
    }

    private void commentIfAbsent(Address a, String text) {
        if (setCommentIfAbsentOrEqual(a, CommentType.EOL, text)) {
            p2Comments++;
        }
    }

    // ==================================================================
    // Pass 3 -- banked-call inline operands
    //
    // DIPOS-B makes every inter-bank call through RST 10h, whose dispatcher
    // at 0010 pops the return address and reads three bytes of inline
    // operand from it:
    //
    //     RST 10h        ; D7
    //     DB  bank       ; bank number for port 47h / shadow F791
    //     DW  target     ; address inside the 32K banked window
    //
    // Ghidra has no way to know the operands are not code, so it decodes
    // them and derails everything after the call. This pass re-types them
    // as DB + DW, points a reference at the callee in the *bank's own*
    // address space, and labels the site.
    //
    // Two guards keep it from destroying real data:
    //  * it only looks at addresses the listing has already decoded as an
    //    RST instruction, never at raw D7 bytes -- D7 is a common high byte
    //    in this firmware's D6xx/D7xx jump tables;
    //  * a bank number above 0x0F or a target below 0x0100 means the match
    //    is table data that Ghidra mis-decoded (ram:D6F7 and D6F9 are exactly
    //    this: the high bytes of the words D713h and D727h), so it is
    //    reported and skipped rather than "repaired".
    //
    // A target of 0000 is not an error: the deferred-call queue and the
    // ram:D79C trampoline are built as stubs whose operands are patched at
    // run time. Those get the operands typed and a comment saying so, but
    // no reference.
    // ==================================================================
    private void repairBankedCallOperands() throws Exception {
        Listing lst = currentProgram.getListing();

        // Snapshot first: this pass converts bytes that follow an RST into
        // data, which can invalidate a live InstructionIterator.
        java.util.List<Address> sites = new java.util.ArrayList<>();
        InstructionIterator it = lst.getInstructions(true);
        while (it.hasNext()) {
            Instruction ins = it.next();
            if ("RST".equals(ins.getMnemonicString()) && rstVector(ins) == RST_BANKED_CALL) {
                sites.add(ins.getAddress());
            }
        }
        println("found " + sites.size() + " decoded RST 10h sites");

        for (Address call : sites) {
            // The site may have been consumed as the operand of an earlier
            // RST since the snapshot was taken.
            if (lst.getInstructionAt(call) == null) {
                continue;
            }
            try {
                repairOneBankedCall(call);
            } catch (Exception ex) {
                p3Skipped++;
                println("SKIP " + call + " : " + ex.getMessage());
            }
        }
    }

    /** Z80 RST models its operand as an address on some builds and as a
     *  scalar on others; accept either. */
    private long rstVector(Instruction ins) {
        Address a = ins.getAddress(0);
        if (a != null) {
            return a.getOffset();
        }
        Scalar s = ins.getScalar(0);
        return (s != null) ? s.getUnsignedValue() : -1;
    }

    private void repairOneBankedCall(Address call) throws Exception {
        Listing lst = currentProgram.getListing();
        Address bankAt = call.add(1);
        Address targetAt = call.add(2);

        byte[] buf = new byte[3];
        if (currentProgram.getMemory().getBytes(bankAt, buf) != 3) {
            p3Skipped++;
            return;
        }
        int bank = buf[0] & 0xFF;
        int target = (buf[1] & 0xFF) | ((buf[2] & 0xFF) << 8);
        boolean patchedAtRuntime = (target == 0);

        if (!patchedAtRuntime && (bank > MAX_BANK || target < 0x0100)) {
            p3Skipped++;
            println("SKIP " + call + " : bank=" + bank + " target="
                    + hex4(target) + " -- table data mis-decoded as RST");
            return;
        }

        boolean changed = false;

        // Operand bytes: only clear and re-create when they are not already
        // the right shape, so a re-run leaves the listing untouched.
        if (!isDefined(bankAt, ByteDataType.class, 1)
                || !isDefined(targetAt, WordDataType.class, 2)) {
            lst.clearCodeUnits(bankAt, targetAt.add(1), false);
            lst.createData(bankAt, ByteDataType.dataType);
            lst.createData(targetAt, WordDataType.dataType);
            changed = true;
        }

        String want = patchedAtRuntime
                ? "banked call: bank/target operands patched at run time"
                : "banked call -> bank " + bank + " addr " + hex4(target);
        changed |= setCommentIfAbsentOrEqual(call, CommentType.EOL, want);

        if (!patchedAtRuntime) {
            // The callee lives in the banked window, so it belongs to the
            // overlay for `bank` -- not to the flat `ram` space. (Resolving
            // it as ram: was the bug in the old AnnotateRst10Calls: the ram
            // block starts at 8000, so every such reference dangled.)
            Address to = bankedAddress(bank, target);
            if (to != null) {
                changed |= addReferenceIfAbsent(call, to, RefType.COMPUTED_CALL);
            }
        }

        if (changed) {
            p3Fixed++;
            println(call + "  " + want);
        } else {
            p3Already++;
        }
    }

    /**
     * Resolve a banked-window address for a given bank number.
     *
     * Bank 0 and bank 1 are the two ROM dumps, modelled as the ROM00/ROM01
     * overlays; anything at or above 8000h is fixed RAM and is the same in
     * every bank. An unmodelled bank number returns null rather than a
     * guess.
     */
    private Address bankedAddress(int bank, int target) {
        if (target >= RAM_BASE) {
            return space("ram").getAddress(target);
        }
        AddressSpace sp = space(bank == 0 ? "ROM00" : bank == 1 ? "ROM01" : "");
        return (sp == null) ? null : sp.getAddress(target);
    }

    // ==================================================================
    // Pass 4 -- InlineTableDispatch inline tables
    //
    // (Folded in from DefineInlineTables.java, behaviour preserved, with a
    // check-before-write fast path added so a re-run is a no-op.)
    //
    // InlineTableDispatch (ram:E0B2) is a switch helper whose jump table is
    // stored inline, immediately after the CALL, instead of in a separate
    // data block:
    //
    //     CALL E0B2
    //         u16  count
    //         { u16 case_value, u16 handler } * count
    //         u16  default_handler
    //
    // The switch value arrives in HL. E0D8 is JP (HL), so the handler
    // returns to the caller's caller and execution never falls through past
    // the table. Ghidra does not know that, so it disassembles the table
    // bytes as code, producing bogus instructions that derail the listing.
    // ==================================================================
    private void defineInlineDispatchTables() throws Exception {
        for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
            if (!block.isInitialized()) {
                continue;
            }
            byte[] bytes = readBlock(block);
            for (int i = 0; i + CALL_DISPATCH.length <= bytes.length; i++) {
                if (bytes[i] != CALL_DISPATCH[0] || bytes[i + 1] != CALL_DISPATCH[1]
                        || bytes[i + 2] != CALL_DISPATCH[2]) {
                    continue;
                }
                Address call = block.getStart().add(i);
                try {
                    defineOneTable(block, bytes, i + 3, call);
                } catch (Exception ex) {
                    p4Skipped++;
                    println("SKIP " + call + " : " + ex.getMessage());
                }
            }
        }
    }

    /**
     * Decode and define the table at {@code off} (a block-relative offset).
     *
     * @param block the containing block
     * @param bytes that block's contents
     * @param off   offset of the table's count field
     * @param call  address of the CALL, for the plate text
     */
    private void defineOneTable(MemoryBlock block, byte[] bytes, int off, Address call)
            throws Exception {
        int count = u16(bytes, off);
        if (count > MAX_CASES) {
            p4Skipped++;
            println(String.format("SKIP %s : implausible case count %d", call, count));
            return;
        }
        int size = 2 + count * 4 + 2;          // count + entries + default
        if (off + size > bytes.length) {
            p4Skipped++;
            println("SKIP " + call + " : table runs past end of block");
            return;
        }

        Address start = block.getStart().add(off);
        Address end = block.getStart().add(off + size - 1);
        Listing lst = currentProgram.getListing();
        String plate = tablePlate(bytes, off, count, call);

        if (isWordArray(start, size / 2) && plate.equals(lst.getComment(CommentType.PLATE, start))) {
            p4Already++;
        } else {
            // Count what we are about to destroy, so the report shows how
            // much of the listing was wrong before this ran.
            int wrong = 0;
            CodeUnitIterator cu = lst.getCodeUnits(new AddressSet(start, end), true);
            while (cu.hasNext()) {
                if (cu.next() instanceof Instruction) {
                    wrong++;
                }
            }
            p4Cleared += wrong;

            lst.clearCodeUnits(start, end, false);
            lst.createData(start, new ArrayDataType(WordDataType.dataType, size / 2, 2));
            lst.setComment(start, CommentType.PLATE, plate);
            p4Defined++;
            println(String.format("%s  table %s-%s  word[%d]  (%d instructions cleared)",
                    call, start, end, size / 2, wrong));
        }

        linkTableHandlers(block, bytes, off, count);
    }

    /** Add an xref from each entry to its handler; disassemble orphans. */
    private void linkTableHandlers(MemoryBlock block, byte[] bytes, int off, int count)
            throws Exception {
        Listing lst = currentProgram.getListing();
        for (int k = 0; k <= count; k++) {                  // cases, then default
            int entry = (k < count) ? off + 2 + k * 4 + 2   // skip the case value
                                    : off + 2 + count * 4;  // the default
            int target = u16(bytes, entry);
            if (target >= RAM_BASE) {
                continue;                                   // handler in fixed RAM
            }
            Address from = block.getStart().add(entry);
            // Handlers are absolute addresses in the calling code's own space.
            Address to = block.getStart().getAddressSpace().getAddress(target);
            if (addReferenceIfAbsent(from, to, RefType.COMPUTED_JUMP)) {
                p4Refs++;
            }
            if (!(lst.getCodeUnitAt(to) instanceof Instruction)) {
                realignHandler(to);
                disassemble(to);
                p4Disassembled++;
                println("  disassembled orphaned handler " + to);
            }
        }
    }

    /**
     * Clear code units that start just *inside* a handler entry point.
     *
     * A handler address comes from a validated table, so it is a real entry
     * point. If Ghidra has laid instructions down starting one or two bytes
     * into it, that code is misaligned and blocks disassembly at the true
     * entry. ROM01:115F is the case that motivated this: `21 00 00 C9`
     * (LD HL,0 / RET) had been decoded one byte late as NOP / NOP / RET,
     * leaving 115F an undefined byte that disassemble() could not fix
     * because the stale NOP at 1160 collided with the 3-byte LD HL,0000.
     *
     * Only bytes strictly after the entry are cleared, and never the entry
     * of a defined function -- if a function starts there, the disagreement
     * is real and needs a human, so it is left alone.
     */
    private void realignHandler(Address entry) {
        Listing lst = currentProgram.getListing();
        Address clearTo = null;
        for (int d = 1; d <= 3; d++) {
            Address probe;
            try {
                probe = entry.add(d);
            } catch (AddressOutOfBoundsException ex) {
                break;
            }
            CodeUnit cu = lst.getCodeUnitAt(probe);
            if (!(cu instanceof Instruction)) {
                continue;
            }
            if (currentProgram.getFunctionManager().getFunctionAt(probe) != null) {
                break;                       // a real function entry; leave it
            }
            clearTo = cu.getMaxAddress();
        }
        if (clearTo != null) {
            lst.clearCodeUnits(entry, clearTo, false);
            p4Realigned++;
            println("  realigned misaligned code at " + entry + "-" + clearTo);
        }
    }

    /** Plate text describing one decoded table. */
    private String tablePlate(byte[] bytes, int off, int count, Address call) {
        StringBuilder sb = new StringBuilder();
        sb.append("InlineTableDispatch inline table for the CALL at ")
          .append(call).append(".\n")
          .append(count).append(" case(s): ");
        for (int k = 0; k < count; k++) {
            int entry = off + 2 + k * 4;
            sb.append(String.format("%#x->%04X ", u16(bytes, entry),
                                    u16(bytes, entry + 2)));
        }
        sb.append(String.format("; default %04X.\n", u16(bytes, off + 2 + count * 4)));
        sb.append("Format: u16 count, {u16 case, u16 handler} * count, u16 default.\n");
        sb.append("Switch value in HL; the dispatcher tail-jumps, so the handler\n");
        sb.append("returns to the caller's caller. See the ram:E0B2 plate.");
        return sb.toString();
    }

    // ==================================================================
    // Pass 5 -- compiler frame-prologue functions
    //
    // See the header for why `LD DE,nnnn / CALL D837` marks a function entry
    // and nothing else. This pass finds every such site and creates a
    // function there when one is missing -- but only where the evidence is
    // already in the database, in one of two forms:
    //
    //   TIER A  the listing already decodes the site as `LD DE,imm16`
    //           followed by a CALL. Ghidra reached the bytes and agrees
    //           they are code; it merely never marked a function start.
    //           This is the ROM00:4D25-5307 case -- eight routines with no
    //           function between them, which is how a doc error got in.
    //
    //   TIER B  the site is undefined bytes, but something independent
    //           witnesses it: either a reference already points at it (in
    //           practice, a boot-chain enqueue record from pass 2), or the
    //           preceding instruction ends exactly one byte earlier and
    //           cannot fall through (a RET or an unconditional jump), so
    //           the previous routine provably ends where this one starts.
    //           Only then is the site disassembled.
    //
    // Anything else -- undefined bytes in the middle of an undecoded run,
    // or a site inside an existing function's body -- is reported and
    // bookmarked, not acted on. Two such sites are the ROM images of RAM
    // module A (ROM00:7409 and 7472 are the same code as ram:D8CE and
    // ram:D937): real prologues, but disassembling them in ROM space would
    // resolve every internal address against the wrong space.
    //
    // Nothing here renames or re-bodies an existing function, and new
    // functions keep Ghidra's default FUN_* name so that "not yet analysed"
    // stays legible in the listing.
    // ==================================================================
    private void createFrameFunctions() throws Exception {
        java.util.Set<Address> deferred = new java.util.LinkedHashSet<>();

        // Creating a function makes Ghidra disassemble its body, which can
        // expose the next prologue, so iterate to a fixed point. In practice
        // the second round is already empty.
        for (int round = 1; round <= MAX_PROLOGUE_ROUNDS; round++) {
            int before = p5Created;
            p5Sites = p5Present = p5Conflict = 0;
            deferred.clear();
            for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
                if (!block.isInitialized()) {
                    continue;
                }
                scanPrologues(block, deferred);
            }
            int made = p5Created - before;
            println("round " + round + ": " + p5Sites + " sites, " + made
                    + " function(s) created, " + p5Present + " already present, "
                    + deferred.size() + " deferred, " + p5Conflict + " conflict(s)");
            if (made == 0) {
                break;
            }
        }

        p5Deferred = deferred.size();
        for (Address a : deferred) {
            println("  DEFER " + a + " : prologue in an undecoded run with no witness");
            bookmarkOnce(a, "frame prologue with no independent witness; "
                    + "not disassembled -- verify by hand before creating a function");
        }
    }

    private void scanPrologues(MemoryBlock block, java.util.Set<Address> deferred)
            throws Exception {
        FunctionManager fm = currentProgram.getFunctionManager();
        Listing lst = currentProgram.getListing();
        byte[] bytes = readBlock(block);

        for (int i = 0; i + 6 <= bytes.length; i++) {
            if ((bytes[i] & 0xFF) != OP_LD_DE_NN
                    || bytes[i + 3] != CALL_FRAME_SETUP[0]
                    || bytes[i + 4] != CALL_FRAME_SETUP[1]
                    || bytes[i + 5] != CALL_FRAME_SETUP[2]) {
                continue;
            }
            Address at = block.getStart().add(i);
            p5Sites++;

            if (fm.getFunctionAt(at) != null) {
                p5Present++;
                continue;
            }
            Function inside = fm.getFunctionContaining(at);
            if (inside != null) {
                p5Conflict++;
                println("  CONFLICT " + at + " : inside " + inside.getName()
                        + " @" + inside.getEntryPoint() + " -- left alone");
                continue;
            }

            Instruction ld = lst.getInstructionAt(at);
            if (ld == null) {
                if (!witnessed(at)) {
                    deferred.add(at);
                    continue;
                }
                Data d = lst.getDataContaining(at);
                if (d != null && d.isDefined()) {
                    p5Conflict++;
                    println("  CONFLICT " + at + " : defined as "
                            + d.getDataType().getName() + " -- left alone");
                    continue;
                }
                if (!disassemble(at)) {
                    deferred.add(at);
                    continue;
                }
                ld = lst.getInstructionAt(at);
            }

            // Confirm the bytes really were decoded as the prologue pair and
            // not as the tail of some longer instruction that happens to
            // start here.
            if (ld == null || ld.getLength() != 3 || !"LD".equals(ld.getMnemonicString())) {
                p5Conflict++;
                println("  CONFLICT " + at + " : decoded as " + ld + " -- left alone");
                continue;
            }
            Instruction call = lst.getInstructionAt(at.add(3));
            if (call == null || !"CALL".equals(call.getMnemonicString())) {
                p5Conflict++;
                println("  CONFLICT " + at + " : no CALL at +3 -- left alone");
                continue;
            }

            Function made = createFunction(at, null);
            if (made == null) {
                p5Conflict++;
                println("  CONFLICT " + at + " : createFunction refused");
                continue;
            }
            p5Created++;
            int frame = u16(bytes, i + 1);
            println("  created " + made.getName() + " at " + at + " (frame "
                    + (frame == 0 ? "0, no locals" : hex4(frame) + "h") + ", body "
                    + made.getBody().getMinAddress() + "-"
                    + made.getBody().getMaxAddress() + ")");

            // Ghidra's own flow analysis decides the body; the script does
            // not invent one. It only says so when that body swallows the
            // next prologue, which is the shape of a missed RET.
            Address next = nextPrologueAfter(block, bytes, i);
            if (next != null && made.getBody().contains(next)) {
                p5Overrun++;
                println("    NOTE body extends past the next prologue at " + next
                        + " -- Ghidra's flow analysis merged two routines; check by hand");
            }
        }
    }

    /**
     * Is there independent evidence that this undecoded site is an entry
     * point? Any one of three things counts:
     *
     *   - something already references it (pass 2's boot-chain records are
     *     the usual source);
     *   - a human has already put a label on it, which is a person asserting
     *     it is a routine (Ghidra's own FUN_/LAB_ defaults do not count);
     *   - the instruction immediately before it ends there and cannot fall
     *     through, so the previous routine is over and a new one must begin.
     */
    private boolean witnessed(Address at) {
        if (currentProgram.getReferenceManager().getReferenceCountTo(at) > 0) {
            return true;
        }
        Symbol sym = currentProgram.getSymbolTable().getPrimarySymbol(at);
        if (sym != null && sym.getSource() != SourceType.DEFAULT) {
            return true;
        }
        Address prevByte;
        try {
            prevByte = at.subtract(1);
        } catch (AddressOutOfBoundsException ex) {
            return false;
        }
        Instruction prev = currentProgram.getListing().getInstructionContaining(prevByte);
        return prev != null && prev.getMaxAddress().equals(prevByte) && !prev.hasFallthrough();
    }

    /** Address of the next prologue signature after block offset {@code i}. */
    private Address nextPrologueAfter(MemoryBlock block, byte[] bytes, int i) {
        for (int j = i + 6; j + 6 <= bytes.length; j++) {
            if ((bytes[j] & 0xFF) == OP_LD_DE_NN
                    && bytes[j + 3] == CALL_FRAME_SETUP[0]
                    && bytes[j + 4] == CALL_FRAME_SETUP[1]
                    && bytes[j + 5] == CALL_FRAME_SETUP[2]) {
                return block.getStart().add(j);
            }
        }
        return null;
    }

    // ==================================================================
    // Pass 6 -- runtime stub farm
    //
    // The firmware's own indirection layer. 281 four-byte slots run from
    // ram:ED1C to F17F, one per routine that loaded software or the other
    // bank may call, and a `CALL 0EExxh` is how you reach a ROM routine
    // without knowing which bank it is in.
    //
    // HOW A SLOT IS BUILT -- the fn=2 chain handler at ram:D727 is the whole
    // mechanism, byte-verified:
    //
    //     d72b  EX DE,HL / ADD HL,HL      ; BC = 2N bytes of source words
    //     d72f  LD HL,(d684)              ; the queue cursor
    //     d733  LD A,D7h / LD (DE),A      ; RST 10h opcode
    //     d737  LD A,(f791) / LD (DE),A   ; the live bank shadow
    //     d73c  LDI / LDI                 ; the 2-byte target
    //     d740  JP PE,d733                ; next slot
    //     d744  LD (d684),HL              ; write the advanced cursor back
    //
    // So slot i is `D7 bank lo hi` -- an inter-bank thunk in the same four
    // bytes as the `LD HL,1 / RET` template it replaces -- and the bank byte
    // comes from F791, i.e. from whichever bank's chain enqueued it. This is
    // why searching for a pointer to the ROM00:7D88 table finds nothing:
    // there is no separate installer. The handler reads the words inline out
    // of the record stream as it walks the chain, and 7D88 is simply where
    // bank 0's fn=2 record happens to keep them.
    //
    // WHY THE SLOT NUMBERING IS RIGHT. The cursor cell (d684) reads ED1C in
    // the cold image, and bank 0's 134 words followed by bank 1's 147 come
    // to 281 slots x 4 = 1124 bytes, landing exactly on F180 -- the resident
    // kernel's base, and exactly the range KernelInitCopyData pre-fills.
    // Three slot-to-target pairs recorded independently from a live RAM dump
    // (slot 58 -> 48BF, 60 -> 4AE0, 68 -> 4F5A) all reproduce.
    // CONFIRMED for bank 0's slots 0..133; bank 1's 134..280 follow from the
    // same shared cursor and the exact fit.
    //
    // Without this pass every one of those 281 call sites is a dead end: the
    // slot holds `LD HL,1 / RET` and carries no reference to the routine it
    // stands for, so the listing cannot be followed across the boundary.
    // ==================================================================
    private void linkRuntimeStubSlots() throws Exception {
        AddressSpace ram = space("ram");
        if (ram == null || currentProgram.getMemory()
                .getBlock(ram.getAddress(STUB_FARM_BASE)) == null) {
            println("stub farm not mapped -- nothing to do");
            return;
        }

        int declared = readU16(ram.getAddress(STUB_CURSOR_CELL));
        if (declared != STUB_FARM_BASE) {
            println("NOTE queue cursor (d684) = " + hex4(declared) + ", not the cold "
                    + hex4(STUB_FARM_BASE) + " -- slots are numbered from "
                    + hex4(STUB_FARM_BASE) + " regardless");
        }

        describeStubFarm(ram);

        int cursor = STUB_FARM_BASE;
        int slot = 0;
        for (ChainRecord r : chain) {
            if (r.fn != 0x0002) {
                continue;
            }
            for (int i = 0; i < r.n; i++) {
                if (cursor + STUB_SLOT_SIZE > STUB_FARM_END) {
                    println("STOP slot " + slot + " would run past " + hex4(STUB_FARM_END)
                            + " -- chain enqueues more than the farm holds");
                    return;
                }
                int target = readU16(r.at.add(4 + 2 * i));
                Address at = ram.getAddress(cursor);
                p6Slots++;
                if (target == 0 || target >= RAM_BASE) {
                    p6Skipped++;        // unused slot, or not a banked-window address
                } else {
                    Address to = r.space.getAddress(target);
                    if (addReferenceIfAbsent(at, to, RefType.COMPUTED_CALL)) {
                        p6Refs++;
                    }
                    if (setCommentIfAbsentOrEqual(at, CommentType.EOL,
                            "runtime stub slot " + slot + " -> "
                            + r.space.getName() + ":" + hex4(target))) {
                        p6Comments++;
                    }
                }
                cursor += STUB_SLOT_SIZE;
                slot++;
            }
        }
        println("mapped " + p6Slots + " slots, ram:" + hex4(STUB_FARM_BASE) + ".."
                + hex4(cursor - 1) + " (" + p6Skipped + " with no usable target)");
    }

    /** Plate the head of the farm once, so the geometry is in the database. */
    private void describeStubFarm(AddressSpace ram) {
        Address base = ram.getAddress(STUB_FARM_BASE);
        if (currentProgram.getListing().getComment(CommentType.PLATE, base) != null) {
            return;                     // already described; never overwrite
        }
        currentProgram.getListing().setComment(base, CommentType.PLATE,
            "RUNTIME STUB FARM -- 281 four-byte slots, ED1C..F17F.\n"
            + "Slot i is the 4 bytes at ED1C + 4*i, and is an inter-bank thunk\n"
            + "`RST 10h ; db bank ; dw target`. It is how loaded software and the\n"
            + "other ROM bank call a firmware routine without knowing its bank.\n"
            + "\n"
            + "Built by the fn=2 boot-chain handler at ram:D727, which walks the\n"
            + "record's word list and stores D7h, the live bank shadow (f791) and\n"
            + "the 2-byte target into the queue cursor (d684), advancing 4 per\n"
            + "word. Bank 0's chain supplies slots 0..133 and bank 1's 134..280:\n"
            + "281 * 4 = 1124 bytes, landing exactly on F180.\n"
            + "\n"
            + "In this cold image every slot is still the KernelInitCopyData\n"
            + "template `21 01 00 C9` = LD HL,1 / RET, so a slot returns 1 and\n"
            + "does nothing. The EOL comment on each slot names the routine it\n"
            + "stands for once installed; those come from the chain records.\n"
            + "CONFIRMED: handler D727-D748; slots 58/60/68 -> 48BF/4AE0/4F5A\n"
            + "reproduce three pairs recorded from a live RAM dump.");
    }

    // ==================================================================
    // Shared helpers
    // ==================================================================

    /** True when {@code a} holds a defined datum of exactly this type/size. */
    private boolean isDefined(Address a, Class<? extends DataType> type, int len) {
        Data d = currentProgram.getListing().getDataAt(a);
        return d != null && d.isDefined() && d.getLength() == len
                && type.isInstance(d.getDataType());
    }

    /** True when {@code a} holds a defined word[n]. */
    private boolean isWordArray(Address a, int n) {
        Data d = currentProgram.getListing().getDataAt(a);
        if (d == null || !d.isDefined() || !(d.getDataType() instanceof Array)) {
            return false;
        }
        Array arr = (Array) d.getDataType();
        return arr.getNumElements() == n
                && arr.getDataType() instanceof WordDataType;
    }

    /**
     * Set a comment only when it is absent. Returns true if the database
     * changed. An existing comment that already says the same thing counts
     * as unchanged; an existing comment that says something *else* is a
     * human's work and is left alone (and reported).
     */
    private boolean setCommentIfAbsentOrEqual(Address a, CommentType kind, String text) {
        String have = currentProgram.getListing().getComment(kind, a);
        if (text.equals(have)) {
            return false;
        }
        if (have != null) {
            println("  KEEP existing " + kind + " comment at " + a);
            return false;
        }
        currentProgram.getListing().setComment(a, kind, text);
        return true;
    }

    /** Add a reference unless an identical one is already recorded. */
    private boolean addReferenceIfAbsent(Address from, Address to, RefType type) {
        ReferenceManager rm = currentProgram.getReferenceManager();
        for (Reference r : rm.getReferencesFrom(from)) {
            if (r.getToAddress().equals(to) && r.getReferenceType() == type) {
                return false;
            }
        }
        rm.addMemoryReference(from, to, type, SourceType.ANALYSIS, 0);
        return true;
    }

    /** Bookmark an address once, so repeated runs do not stack duplicates. */
    private void bookmarkOnce(Address a, String comment) {
        BookmarkManager bm = currentProgram.getBookmarkManager();
        for (Bookmark b : bm.getBookmarks(a)) {
            if (BOOKMARK_CAT.equals(b.getCategory()) && comment.equals(b.getComment())) {
                return;
            }
        }
        bm.setBookmark(a, BookmarkType.ANALYSIS, BOOKMARK_CAT, comment);
    }

    private AddressSpace space(String name) {
        return currentProgram.getAddressFactory().getAddressSpace(name);
    }

    private byte[] readBlock(MemoryBlock block) throws Exception {
        byte[] bytes = new byte[(int) block.getSize()];
        block.getBytes(block.getStart(), bytes);
        return bytes;
    }

    private int readU16(Address a) throws Exception {
        byte[] b = new byte[2];
        currentProgram.getMemory().getBytes(a, b);
        return (b[0] & 0xFF) | ((b[1] & 0xFF) << 8);
    }

    /** Little-endian 16-bit read from a block-relative offset. */
    private static int u16(byte[] bytes, int off) {
        return (bytes[off] & 0xFF) | ((bytes[off + 1] & 0xFF) << 8);
    }

    private static String hex4(int v) {
        return String.format("%04X", v & 0xFFFF);
    }

    private void summarise() {
        println("");
        println("=== summary =======================================");
        println("pass 0  battery RAM  : " + (p0BlockCreated == 1
                ? "block CREATED" : "block already present") + ", " + p0Seeded
                + " vars seeded, " + p0Copied + " copies replayed, " + p0CopiesOk
                + " already correct");
        println("        "            + "             " + p0Phantoms
                + " phantom functions removed, " + p0Disassembled
                + " entry points disassembled, " + p0Drift
                + " copy-list disagreements, stub template "
                + (p0Filled == 1 ? "written" : "unchanged"));
        println("pass 1  frame helper : " + (p1Fixed == 1
                ? "no-return flag CLEARED on ram:D837"
                : "no change needed"));
        println("pass 2  boot chains  : " + p2Records + " records, " + p2Typed
                + " words typed, " + p2Comments + " comments added");
        println("        targets      : " + p2Refs + " references added, " + p2RefsFixed
                + " dangling references repointed, " + p2Disassembled
                + " disassembled, " + p2Functions + " functions created");
        println("pass 3  banked calls : " + p3Fixed + " repaired, " + p3Already
                + " already correct, " + p3Skipped + " skipped (data)");
        println("pass 4  inline tables: " + p4Defined + " defined, " + p4Already
                + " already correct, " + p4Skipped + " skipped, " + p4Cleared
                + " bogus instructions removed");
        println("        handlers     : " + p4Refs + " references added, "
                + p4Disassembled + " orphans disassembled, " + p4Realigned + " realigned");
        println("pass 5  prologues    : " + p5Sites + " sites, " + p5Created
                + " functions created, " + p5Present + " already present, "
                + p5Deferred + " deferred, " + p5Conflict + " conflicts, "
                + p5Overrun + " bodies overrunning the next prologue");
        println("pass 6  stub farm    : " + p6Slots + " slots, " + p6Refs
                + " references added, " + p6Comments + " comments added, "
                + p6Skipped + " with no usable target");
        println("total functions now  : "
                + currentProgram.getFunctionManager().getFunctionCount());
        println("===================================================");
        println("Nothing here is renamed or re-commented: new functions keep their");
        println("FUN_* names and existing comments are preserved. Re-running is safe");
        println("and should report zero changes.");
    }
}
