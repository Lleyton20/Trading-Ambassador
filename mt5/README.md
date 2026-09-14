# Trading Ambassador — MT5 Expert Advisor

Draws Trading Ambassador's live SMC analysis (order blocks, FVGs,
BOS/CHoCH, bias, confluence score) directly on an MT5 chart, by polling
the backend's REST API. See the [root README](../README.md)'s
"MT5 Expert Advisor" section for the full setup walkthrough.

**Display only.** This EA never places, modifies, or closes a trade -
same rule as the rest of the project (see `backend/README.md`, "Key
design decisions"). It only draws what the API already returns.

## Files

- `Experts/TradingAmbassadorEA.mq5` — the EA.
- `Include/JAson.mqh` — vendored JSON library
  ([vivazzi/JAson](https://github.com/vivazzi/JAson), MIT license,
  copyright retained in the file header) — MQL5 has no built-in JSON
  parser, this is the community-standard include for it.

## A note on verification

Unlike every other part of this project, this code wasn't run/compiled
before being committed — there's no MQL5 toolchain in the environment
this was written in. It's written carefully against MetaQuotes' own
documented APIs, but MetaEditor's compiler is the first real check it
gets. If it doesn't compile cleanly, the most likely spot is the
`char`/`uchar` byte-array types in `HttpGet()` (`WebRequest` and
`CharArrayToString`) — MQL5's own docs describe these two functions
using different array types in places, and this couldn't be resolved
without a compiler to test against. Fix: change `char post[]` / `char
result[]` to `uchar post[]` / `uchar result[]`.
