# Model notes

## Euri: `google/gemma-4-26B-A4B-it`

Checked 17 Oct 2026 through `llm/euri.py` (system text inside the user message, no `response_format`).

| Call | Tokens in / out | Latency | Result |
|---|---|---|---|
| Ping ("return exactly `{"ok": true}`") | 26 / 6 | 2.7 s | Raw JSON, exact |
| Extract, `samples/sample_event.txt` (630 chars) | 292 / 734 | 15 s | Correct facts, exact snippets |
| Same extract, earlier attempt | n/a | > 45 s twice | Timed out, `llm_unavailable` |

Behaviour:
- JSON comes back wrapped in a ```` ```json ```` fence, not raw. `call_validated` must strip fences.
- Follows the "copy an exact quote" rule well; values and snippets matched the source.
- Invents key names when no list is given (`mentor_asha_verma_specialty`, `judge`, `partner`). The extract prompt must list the allowed keys (LLD 3.1).
- Latency is uneven: the same request took 15 s once and over 45 s on two tries.
- Quota: not checked.
