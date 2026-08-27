# ADR-0007: Self-hosted Ollama with Llama 3.2 3B for agent inference

**Status:** Accepted

## Context

The Untrusted Logic Space (the agent's reasoning loop) needs a real LLM to
exercise the gateway meaningfully, self-hosted per ADR-0001. Available
hardware is a single laptop GPU (RTX 3050, 4GB VRAM) with 16GB of system
RAM.

## Decision

Ollama, serving Llama 3.2 3B (Q4 quantization, fits fully within the 4GB
VRAM budget) as the default model for both the agent runtime and the
evaluation harness, with Qwen2.5 7B documented and available as a
fallback for cases needing stronger instruction-following, at the
accepted cost of partial CPU offload and materially slower generation.

## Alternatives Considered

- **A hosted LLM API** (OpenAI, Anthropic, or similar): rejected under
  the self-hosted mandate (ADR-0001), and separately because per-request
  cost and rate limits would work directly against an evaluation harness
  designed to make many repeated adversarial calls, some deliberately
  in bursts (Gate 3 testing).
- **A larger local model as the default** (for example Qwen2.5 7B):
  rejected as the default specifically because of the VRAM constraint;
  kept available as an explicit, documented alternative rather than
  discarded, since some evaluation questions (does model capacity affect
  susceptibility to prompt injection) directly require comparing more
  than one model.

## Consequences

**Positive**

- Zero marginal cost per harness run, which matters directly for
  obtaining statistically meaningful blocking-rate numbers (many repeated
  runs), something a metered hosted API would make expensive or
  impractical at the volume this evaluation needs.
- Fully reproducible without any API key, account, or external network
  dependency once the model is pulled.

**Negative, empirically observed, not theoretical**

Llama 3.2 3B is measurably unreliable at strict tool-calling in two
distinct ways found during actual harness runs, not anticipated in
advance:

1. **Schema conformance.** It occasionally emits tool-call arguments with
   fields outside the declared schema (for example a stray `format:
   "json"` field), which under strict Pydantic validation caused the
   entire agent run to crash. Fixed by explicitly tolerating unknown
   fields (`extra="ignore"`) rather than rejecting them, since Gate 4 on
   the real gateway re-validates every argument independently regardless
   of what the local tool schema tolerates.
2. **Adversarial-prompt handling is model-specific, not general LLM
   behavior.** A direct, controlled comparison (same prompt, same
   corpus, only the model changed) showed Llama 3.2 3B reflexively
   refusing to construct a SQL-injection-pattern string, evidently due to
   RLHF-style safety training recognizing the surface pattern, not due to
   any reasoning about the gateway's security. The identical prompt
   against Qwen2.5 7B produced no such refusal; the model simply
   attempted the tool call and let the gateway's Gate 2 deny it. Any
   blocking-rate or susceptibility number reported from a single-model
   setup is model-specific and must be reported and interpreted as such,
   not generalized to "LLM agents" as a category.
