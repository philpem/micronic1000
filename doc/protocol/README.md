# Protocol specifications

This section specifies the Micronic 1000 communications layers. It separates
validated controller behaviour from fields that still require a captured wire
trace.

- [Commstar communications protocol](commstar.md) — controller transport,
  frame envelope, routing, and the evidence boundary for session/file transfer.

The specification is deliberately conservative: an unknown field is marked
open rather than assigned a name from an unverified analogy.
