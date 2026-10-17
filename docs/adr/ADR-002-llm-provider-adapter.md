# ADR-002: Gemma behind a provider adapter, with mock and Ollama

Status: Accepted. Date: 2026-10-16.

## Context
The challenge theme requires open-weight or open-source AI at the core. The Gemma prize category needs Gemma served locally, fine-tuned, or through Google Cloud or another provider. Render's free tier cannot run a model. A live demo must work for judges.

## Decision
- Define `LLMProvider.generate_json(task, system, prompt, schema, ...)` in `llm/base.py`.
- Providers, chosen by `LLM_PROVIDER`:
  - `gemma`: Gemma through the Google AI Studio REST API (`GEMMA_MODEL`, `GOOGLE_API_KEY`).
  - `euri`: Gemma 4 (`google/gemma-4-26B-A4B-it`) through the OpenAI-compatible Euri API (`EURI_API_KEY`, `EURI_MODEL`). Default in production since 17 Oct 2026; see `docs/MODEL_NOTES.md`.
  - `mock`: deterministic outputs built from the input facts. Default in tests and local dev.
  - `ollama`: local Gemma through Ollama (`OLLAMA_URL`, `OLLAMA_MODEL`). Stretch goal, config only.
- Do not rely on provider JSON mode or system-instruction support. Ask for JSON in the prompt, parse, validate with Pydantic, and make one repair attempt before failing.
- Optional `LLM_FALLBACK_TO_MOCK=true` for demos. When used, the response carries `X-LLM-Provider: mock` and the UI shows a visible "Demo model" badge. Never silently pass mock output off as Gemma.
- Record provider, model, prompt version, latency and token counts for every call.

## Consequences
- Judges can use a live app without a GPU.
- The "why open innovation matters" story is concrete: swap hosting without changing code.
- Some Gemma models on hosted APIs may lack JSON mode or system prompts, which is why validation and repair are mandatory. Check the exact model id and capabilities in AI Studio before relying on them.
- The `gemma` provider depends on a third party for availability and quota. See ADR-008.

## Alternatives considered
- Self-host Gemma on a GPU host: strongest open story, too slow and costly to set up in the time left.
- A closed model: violates the challenge theme.
