// Define every InlineTableDispatch inline table as data.
//
// InlineTableDispatch (ram:E0B2) is a switch helper whose jump table is stored
// inline, immediately after the CALL, instead of in a separate data block:
//
//     CALL E0B2
//         u16  count
//         { u16 case_value, u16 handler } * count
//         u16  default_handler
//
// The switch value arrives in HL. E0D8 is JP (HL), so the handler returns to
// the caller's caller and execution never falls through past the table.
// Ghidra does not know that, so it disassembles the table bytes as code,
// producing bogus instructions that derail the surrounding listing.
//
// This script scans every initialised memory block for `CALL E0B2`, decodes
// the table that follows, clears the range, types it as word[2*count+2] and
// attaches a plate listing the decoded cases. It then adds a reference from
// each entry to its handler -- the dispatcher's indirect jump leaves Ghidra
// with no flow to them -- and disassembles any handler left as raw bytes.
//
// Self-contained: no arguments, no external table, safe to re-run.
//
// @category Micronic1000
// @menupath Analysis.Micronic.Define InlineTableDispatch tables
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.data.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;

public class DefineInlineTables extends GhidraScript {

    /** CALL 0xE0B2 -- the dispatcher entry, little-endian operand. */
    private static final byte[] CALL_DISPATCH = { (byte) 0xCD, (byte) 0xB2, (byte) 0xE0 };

    /** Sanity bound: real tables are small, so a large count means we have
     *  matched bytes that only look like a call. */
    private static final int MAX_CASES = 64;

    /** Handlers at or above this live in the fixed upper RAM, which may not be
     *  present in the same address space as the calling code. */
    private static final int RAM_BASE = 0x8000;

    private int defined, skipped, cleared, refs, disassembled;

    @Override
    public void run() throws Exception {
        for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
            if (!block.isInitialized()) {
                continue;
            }
            scanBlock(block);
        }
        println("---");
        println("defined " + defined + " tables, " + skipped + " skipped, "
                + cleared + " bogus instructions removed");
        println("added " + refs + " handler references, disassembled "
                + disassembled + " orphaned handlers");
    }

    /** Find and process every CALL E0B2 in one block. */
    private void scanBlock(MemoryBlock block) throws Exception {
        int len = (int) block.getSize();
        byte[] bytes = new byte[len];
        block.getBytes(block.getStart(), bytes);

        for (int i = 0; i + CALL_DISPATCH.length <= len; i++) {
            if (bytes[i] != CALL_DISPATCH[0] || bytes[i + 1] != CALL_DISPATCH[1]
                    || bytes[i + 2] != CALL_DISPATCH[2]) {
                continue;
            }
            Address call = block.getStart().add(i);
            try {
                defineTable(block, bytes, i + 3, call);
            } catch (Exception ex) {
                skipped++;
                println("SKIP " + call + " : " + ex.getMessage());
            }
        }
    }

    /**
     * Decode and define the table at ``off`` (a block-relative offset).
     *
     * @param block the containing block
     * @param bytes that block's contents
     * @param off   offset of the table's count field
     * @param call  address of the CALL, for the plate text
     */
    private void defineTable(MemoryBlock block, byte[] bytes, int off, Address call)
            throws Exception {
        int count = u16(bytes, off);
        if (count > MAX_CASES) {
            skipped++;
            println(String.format("SKIP %s : implausible case count %d", call, count));
            return;
        }
        int size = 2 + count * 4 + 2;          // count + entries + default
        if (off + size > bytes.length) {
            skipped++;
            println("SKIP " + call + " : table runs past end of block");
            return;
        }

        Address start = block.getStart().add(off);
        Address end = block.getStart().add(off + size - 1);
        Listing lst = currentProgram.getListing();

        // Count what we are about to destroy, so the report shows how much of
        // the listing was wrong before this ran.
        int wrong = 0;
        CodeUnitIterator it = lst.getCodeUnits(new AddressSet(start, end), true);
        while (it.hasNext()) {
            if (it.next() instanceof Instruction) {
                wrong++;
            }
        }
        cleared += wrong;

        lst.clearCodeUnits(start, end, false);
        lst.createData(start, new ArrayDataType(WordDataType.dataType, size / 2, 2));
        lst.setComment(start, CodeUnit.PLATE_COMMENT, plateFor(bytes, off, count, call));
        defined++;
        println(String.format("%s  table %s-%s  word[%d]  (%d instructions cleared)",
                call, start, end, size / 2, wrong));

        linkHandlers(block, bytes, off, count);
    }

    /** Add an xref from each entry to its handler; disassemble orphans. */
    private void linkHandlers(MemoryBlock block, byte[] bytes, int off, int count)
            throws Exception {
        ReferenceManager rm = currentProgram.getReferenceManager();
        Listing lst = currentProgram.getListing();
        for (int k = 0; k <= count; k++) {                 // cases, then default
            int entry = (k < count) ? off + 2 + k * 4 + 2   // skip the case value
                                    : off + 2 + count * 4;  // the default
            int target = u16(bytes, entry);
            if (target >= RAM_BASE) {
                continue;                                   // handler in fixed RAM
            }
            Address from = block.getStart().add(entry);
            // Handlers are absolute addresses in the calling code's own space.
            Address to = block.getStart().getAddressSpace().getAddress(target);
            rm.addMemoryReference(from, to, RefType.COMPUTED_JUMP,
                                  SourceType.ANALYSIS, 0);
            refs++;
            if (!(lst.getCodeUnitAt(to) instanceof Instruction)) {
                disassemble(to);
                disassembled++;
                println("  disassembled orphaned handler " + to);
            }
        }
    }

    /** Plate text describing one decoded table. */
    private String plateFor(byte[] bytes, int off, int count, Address call) {
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

    /** Little-endian 16-bit read from a block-relative offset. */
    private static int u16(byte[] bytes, int off) {
        return (bytes[off] & 0xFF) | ((bytes[off + 1] & 0xFF) << 8);
    }
}
