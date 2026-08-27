# Program formats: COM and DIP

## COM

The firmware recognises CP/M-style COM images. They use the ordinary
program-loading path and remain the safest portable form for applications
that only require the normal CP/M-style BDOS interface.

## DIP

DIPOS-B also recognises a proprietary DIP program format. Firmware strings
demonstrate checks for size, block count, system compatibility, and corruption.
The resident loader exposes three primitives that copy data, move data, and
queue banked calls.

**LIKELY:** a DIP uses those primitives to place code and data into more than
one bank and to arrange load-time initialisation.

**OPEN:** the exact on-file header, record grammar, checksum, and termination
marker have not been captured from the DIP parser. Do not build a DIP encoder
from the boot-load-chain grammar alone; that grammar proves the loader
mechanism, not the external file container.

See [the loader internals](../internals/os-diposb.md) for the verified
boot-chain record format and [the programmer's guide](programmer-guide.md)
for application-level constraints.
