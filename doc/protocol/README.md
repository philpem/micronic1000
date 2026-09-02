# Protocol reference

This section states the **contract** for the Micronic 1000 communications
layers. It separates stable M1000-facing controller behaviour from the
uncaptured wire layer and unresolved Commstar session grammar.

- [Commstar transport](commstar.md) — controller mechanics, validated frame
  envelope, the session state machine and wire states, observable session
  requests, and the blockers for a physical server. The full byte-level
  evidence, register timing, and bounded traces are in
  [RE notes: Commstar evidence](../re-notes/commstar-evidence.md).

Two companion pages complete the picture for anyone implementing a host: the
handheld-side entry points a loaded program calls, in
[Commstar application API](../reference/commstar-api.md), and a working host
implementation, in
[Commstar peer library](../reference/commstar-peer.md).

The contract uses **stability** terms (`Stable` / `Provisional` /
`Not implementable`). Evidence and trace bytes live in the RE notes.
