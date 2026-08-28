#!/usr/bin/env python3
"""micronic.program - host-side COM/DIP validator for DIPOS-B images.

Implements ONLY the CONFIRMED grammar from doc/manual/program-formats.md
(runtime Load/Run loader, ROM01:0A67-10CE / Program_LoadDipOrCom at
ROM01:0CE7). The boot-load chain (ram:D6DB fn=0/1/2/FFFF) is a distinct
mechanism and is NOT validated here.

Rules (all little-endian):

  COM
    - Fallback rule (CONFIRMED, ROM01:0CE7): if the first input chunk is
      under 14 bytes OR the first word != 0xC8C9 (file bytes C9 C8), the
      loader treats the input as raw COM copied to 0x0100.
    - COM file too big: raw COM > 0xCF81 (53,121) bytes
      -> 0x232C (9004) "COM file too big."

  DIP
    - Header is exactly 14 bytes:
        +0 u16 magic 0xC8C9 (bytes C9 C8)
        +2 u16 system ID: 0 (wildcard) or 0x00E5 (Micronic 1000)
        +4 u16 entry-bank offset
        +6 u16 image size (loader CLAMPS to 0x8000, does NOT reject)
        +8 u16 run-bank offset
        +10 u16 entry address
        +12 u16 block count, max 5
    - Each block:
        +0 u16 type  (handlers exist for 0 and 1)
        +2 u16 destination bank offset
        +4 u16 destination address
        +6 u16 payload byte count
        +8 u8[payload] payload
      type 0: raw copy; type 1: payload is N*4-byte {u16 bank, u16 addr}
      items written as RST 10h trampolines.
    - Checks performed here (matching loader errors where applicable):
        * magic already used for COM/DIP discrimination; DIP magic is
          therefore implicit in the kind.
        * system ID not in {0, 0xE5} -> 0x2331 (9009)
          "Program not built for this system."
        * block count > 5 -> 0x2334 (9012) "DIP file has too many blocks."
        * 8-byte block header truncated or payload truncated
          -> 0x232B (9003) "Bad DIP file."
        * type-1 payload length not multiple of 4 -> validator-specific
          DIP_TYPE1_ALIGN (no loader code for this; payload format is
          CONFIRMED as 4-byte items).
        * image size > 0x8000 is NOT an error; loader clamps (CONFIRMED
          branch). We expose the clamped value and do not reject.

No other constraints are invented (e.g. we do NOT reject image size
>0x8000, do NOT enforce destination+payload bounds as 0x232A, and do
NOT treat unknown block types as errors -- the ROM dispatch takes the
default "next block" path with no explicit error).

Stdlib only. Intended for host tooling and CI golden tests.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import List, Optional

# ------------------------------------------------------------------ constants
DIP_MAGIC: int = 0xC8C9
DIP_MAGIC_BYTES: bytes = b"\xC9\xC8"
DIP_HEADER_SIZE: int = 14
DIP_BLOCK_HEADER_SIZE: int = 8
DIP_MAX_BLOCKS: int = 5
DIP_SYSTEM_IDS = (0x0000, 0x00E5)
DIP_IMAGE_SIZE_CLAMP: int = 0x8000
COM_MAX: int = 0xCF81  # 0xD081 - 0x0100

# Loader error catalogue (hex -> decimal + message) from
# doc/manual/program-formats.md "DIP and COM error catalogue"
ERR_COM_TOO_BIG: int = 0x232C      # 9004 "COM file too big."
ERR_DIP_BAD_FILE: int = 0x232B     # 9003 "Bad DIP file."
ERR_DIP_WRONG_SYSTEM: int = 0x2331  # 9009 "Program not built for this system."
ERR_DIP_TOO_MANY_BLOCKS: int = 0x2334  # 9012 "DIP file has too many blocks."
ERR_DIP_TOO_BIG: int = 0x232A      # 9002 "DIP file too big." (dst+payload bounds)
ERR_PROGRAM_CORRUPT: int = 0x2332  # 9010 "Program corrupt." (runtime checksum)

# Validator-specific (no direct loader error code)
ERR_DIP_TYPE1_ALIGN: str = "DIP_TYPE1_ALIGN"

_ERROR_MESSAGES = {
    ERR_COM_TOO_BIG: "COM file too big.",
    ERR_DIP_BAD_FILE: "Bad DIP file.",
    ERR_DIP_WRONG_SYSTEM: "Program not built for this system.",
    ERR_DIP_TOO_MANY_BLOCKS: "DIP file has too many blocks.",
    ERR_DIP_TOO_BIG: "DIP file too big.",
    ERR_PROGRAM_CORRUPT: "Program corrupt.",
}

# ---------------------------------------------------------------- dataclasses
@dataclass(frozen=True)
class DipHeader:
    magic: int
    system_id: int
    entry_bank_offset: int
    image_size: int
    image_size_clamped: int
    run_bank_offset: int
    entry_address: int
    block_count: int

    @property
    def image_size_was_clamped(self) -> bool:
        return self.image_size != self.image_size_clamped


@dataclass(frozen=True)
class DipBlock:
    index: int
    type: int
    dest_bank_offset: int
    dest_address: int
    payload_len: int
    payload: bytes
    offset_in_file: int  # file offset of block header


@dataclass
class ValidationIssue:
    """One validation problem.

    For loader-mapped errors, `code` is the hex error ID (e.g. 0x232B) and
    `identifier` is the symbolic name. For validator-specific issues,
    `code` is None and `identifier` is a string like DIP_TYPE1_ALIGN.
    """

    identifier: str
    message: str
    code: Optional[int] = None
    offset: Optional[int] = None
    detail: str = ""

    @property
    def decimal(self) -> Optional[int]:
        return self.code if self.code is None else int(self.code)

    def format(self) -> str:
        if self.code is not None:
            dec = self.code  # already decimal value == hex interpretation
            base = f"0x{self.code:04X} ({dec}), \"{_ERROR_MESSAGES.get(self.code, self.message)}\""
            if self.detail:
                return f"{base} -- {self.detail} [{self.identifier}]"
            return f"{base} [{self.identifier}]"
        # validator-specific
        loc = f" @ offset {self.offset}" if self.offset is not None else ""
        det = f": {self.detail}" if self.detail else ""
        return f"{self.identifier}{loc}: {self.message}{det}"

    def __str__(self) -> str:
        return self.format()


@dataclass
class ValidationResult:
    kind: str  # "COM" or "DIP"
    valid: bool
    errors: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)
    header: Optional[DipHeader] = None
    blocks: List[DipBlock] = field(default_factory=list)
    data_len: int = 0
    # For DIP, trailing bytes after last block (should be 0)
    trailing_bytes: int = 0

    def has_error(self, code_or_id) -> bool:
        for e in self.errors:
            if e.code == code_or_id or e.identifier == code_or_id:
                return True
        return False

# ---------------------------------------------------------------- helpers
def _issue_from_code(code: int, identifier: str, offset: Optional[int] = None, detail: str = "") -> ValidationIssue:
    return ValidationIssue(
        identifier=identifier,
        message=_ERROR_MESSAGES.get(code, ""),
        code=code,
        offset=offset,
        detail=detail,
    )


def classify(data: bytes) -> str:
    """Return 'DIP' or 'COM' per the first-chunk rule (CONFIRMED).

    If the first chunk (here the whole file as one chunk) is under 14 bytes
    OR the first word != 0xC8C9, the loader treats input as raw COM.
    """
    if len(data) < DIP_HEADER_SIZE:
        return "COM"
    magic = struct.unpack_from("<H", data, 0)[0]
    if magic != DIP_MAGIC:
        return "COM"
    return "DIP"


def _parse_header(data: bytes) -> DipHeader:
    # Caller ensures len >= 14 and magic == DIP_MAGIC
    magic, system_id, entry_bank_off, image_size, run_bank_off, entry_addr, block_count = struct.unpack_from(
        "<HHHHHHH", data, 0
    )
    clamped = image_size if image_size <= DIP_IMAGE_SIZE_CLAMP else DIP_IMAGE_SIZE_CLAMP
    return DipHeader(
        magic=magic,
        system_id=system_id,
        entry_bank_offset=entry_bank_off,
        image_size=image_size,
        image_size_clamped=clamped,
        run_bank_offset=run_bank_off,
        entry_address=entry_addr,
        block_count=block_count,
    )


def validate_com(data: bytes) -> ValidationResult:
    res = ValidationResult(kind="COM", valid=True, data_len=len(data))
    if len(data) > COM_MAX:
        res.valid = False
        res.errors.append(
            _issue_from_code(
                ERR_COM_TOO_BIG,
                "COM_TOO_BIG",
                detail=f"size {len(data)} > max 0x{COM_MAX:04X} ({COM_MAX})",
            )
        )
    return res


def validate_dip(data: bytes) -> ValidationResult:
    res = ValidationResult(kind="DIP", valid=True, data_len=len(data))
    if len(data) < DIP_HEADER_SIZE:
        # Should not happen if classify was used, but handle directly-called case
        res.valid = False
        res.errors.append(
            _issue_from_code(
                ERR_DIP_BAD_FILE,
                "BAD_DIP_FILE",
                offset=0,
                detail=f"header truncated: {len(data)} < {DIP_HEADER_SIZE}",
            )
        )
        return res

    header = _parse_header(data)
    res.header = header

    # System ID
    if header.system_id not in DIP_SYSTEM_IDS:
        res.valid = False
        res.errors.append(
            _issue_from_code(
                ERR_DIP_WRONG_SYSTEM,
                "DIP_WRONG_SYSTEM",
                offset=2,
                detail=f"system ID 0x{header.system_id:04X} not in {{0x0000, 0x00E5}}",
            )
        )

    # Block count
    if header.block_count > DIP_MAX_BLOCKS:
        res.valid = False
        res.errors.append(
            _issue_from_code(
                ERR_DIP_TOO_MANY_BLOCKS,
                "DIP_TOO_MANY_BLOCKS",
                offset=12,
                detail=f"block_count {header.block_count} > {DIP_MAX_BLOCKS}",
            )
        )
        # Loader reports 0x2334 and does not continue parsing blocks when
        # count >5; we stop here to mirror that (and avoid over-read).
        return res

    offset = DIP_HEADER_SIZE
    for idx in range(header.block_count):
        # Need 8 bytes of block header
        if offset + DIP_BLOCK_HEADER_SIZE > len(data):
            res.valid = False
            res.errors.append(
                _issue_from_code(
                    ERR_DIP_BAD_FILE,
                    "BAD_DIP_FILE",
                    offset=offset,
                    detail=f"block {idx}: header truncated (need 8, have {len(data)-offset})",
                )
            )
            break
        btype, dest_bank, dest_addr, payload_len = struct.unpack_from("<HHHH", data, offset)
        block_header_off = offset
        offset += DIP_BLOCK_HEADER_SIZE

        # Payload length validation
        if offset + payload_len > len(data):
            res.valid = False
            res.errors.append(
                _issue_from_code(
                    ERR_DIP_BAD_FILE,
                    "BAD_DIP_FILE",
                    offset=block_header_off,
                    detail=f"block {idx}: payload truncated (declared {payload_len}, have {len(data)-offset})",
                )
            )
            # Still record block with truncated payload for diagnostics? No, break.
            break

        payload = data[offset : offset + payload_len]

        # Type-1 alignment
        if btype == 1 and (payload_len % 4 != 0):
            res.valid = False
            res.errors.append(
                ValidationIssue(
                    identifier=ERR_DIP_TYPE1_ALIGN,
                    message="DIP type-1 payload not multiple of 4",
                    code=None,
                    offset=block_header_off,
                    detail=f"block {idx}: type 1 payload_len {payload_len} % 4 != 0",
                )
            )

        res.blocks.append(
            DipBlock(
                index=idx,
                type=btype,
                dest_bank_offset=dest_bank,
                dest_address=dest_addr,
                payload_len=payload_len,
                payload=payload,
                offset_in_file=block_header_off,
            )
        )
        offset += payload_len

    res.trailing_bytes = len(data) - offset
    # Trailing bytes: not an error per CONFIRMED grammar (loader reads exactly
    # block_count blocks via chunked consumer; extra bytes would be surplus).
    # We surface it as a warning for strict tooling but do not fail validation.
    if res.trailing_bytes != 0 and res.valid:
        # Only warn if otherwise valid; if already invalid we already explain
        # the primary error and trailing is secondary.
        res.warnings.append(
            ValidationIssue(
                identifier="DIP_TRAILING_BYTES",
                message="trailing bytes after last block",
                code=None,
                offset=offset,
                detail=f"{res.trailing_bytes} byte(s) beyond parsed image",
            )
        )

    # If any error was added, valid is False (already set). Re-check.
    if res.errors:
        res.valid = False
    return res


def validate(data: bytes) -> ValidationResult:
    """Classify and validate `data` as COM or DIP in one call."""
    kind = classify(data)
    if kind == "COM":
        return validate_com(data)
    return validate_dip(data)


def validate_file(path: str) -> ValidationResult:
    with open(path, "rb") as f:
        data = f.read()
    return validate(data)


# ---------------------------------------------------------------- builders (for tests / host tooling)
def build_dip_header(
    system_id: int = 0x00E5,
    entry_bank_offset: int = 0,
    image_size: int = 0,
    run_bank_offset: int = 0,
    entry_address: int = 0x0100,
    block_count: int = 0,
) -> bytes:
    return struct.pack(
        "<HHHHHHH",
        DIP_MAGIC,
        system_id & 0xFFFF,
        entry_bank_offset & 0xFFFF,
        image_size & 0xFFFF,
        run_bank_offset & 0xFFFF,
        entry_address & 0xFFFF,
        block_count & 0xFFFF,
    )


def build_dip_block(
    btype: int,
    dest_bank_offset: int,
    dest_address: int,
    payload: bytes,
) -> bytes:
    hdr = struct.pack(
        "<HHHH",
        btype & 0xFFFF,
        dest_bank_offset & 0xFFFF,
        dest_address & 0xFFFF,
        len(payload) & 0xFFFF,
    )
    return hdr + payload


def build_dip_file(
    header_kwargs: Optional[dict] = None,
    blocks: Optional[List[tuple]] = None,
) -> bytes:
    """Build a complete DIP file from header kwargs and block tuples.

    header_kwargs: dict for build_dip_header (block_count auto-set if omitted)
    blocks: list of (type, dest_bank, dest_addr, payload_bytes)
    """
    if blocks is None:
        blocks = []
    if header_kwargs is None:
        header_kwargs = {}
    # Auto-set block_count if not supplied
    if "block_count" not in header_kwargs:
        header_kwargs = dict(header_kwargs)
        header_kwargs["block_count"] = len(blocks)
    hdr = build_dip_header(**header_kwargs)
    body = b"".join(build_dip_block(t, b, a, p) for (t, b, a, p) in blocks)
    return hdr + body
