# ADR-0005: Four independent sequential gates instead of single-entity authorization

**Status:** Accepted

## Context

Existing production tooling in this space (for example Tyk MCP Gateway)
uses single-entity authorization: one component evaluates a request's
credentials against a fixed policy and returns one binary decision. This
reliably blocks unauthorized access but cannot distinguish a legitimately
authorized agent from that same agent acting under a successful prompt
injection, since it never separately evaluates identity, permission,
request pattern, and payload content as distinct questions.

## Decision

Decompose enforcement into four independently denyable sequential stages:
authentication and tenant resolution (Gate 1), Cedar-based role
authorization (Gate 2), session envelope enforcement (Gate 3), and schema
conformance validation (Gate 4). Each gate can block a request on its own,
and each gate's decision (allow or deny, and why) is logged independently
to the audit trail.

## Alternatives Considered

- **A single combined check**: rejected. Cannot distinguish "is this
  identity valid" from "is this action permitted" from "is this specific
  payload safe" from "is this request pattern safe," each a categorically
  different question, and each corresponding to a different vulnerability
  layer identified in the literature review (perceptual, cognitive, and
  executive layers, per Radanliev et al. 2026).
- **A two-stage split (auth, then everything else)**: rejected as
  insufficiently granular to test H1 (single-request enforcement) and H2
  (aggregate-pattern detection) as genuinely separate hypotheses with
  independently toggleable enforcement (see ADR-0006's `ZTAP_GATE3_ENABLED`
  toggle, which depends on Gate 3 being separable from Gates 1, 2, and 4).

## Consequences

**Positive**

- Each gate is independently testable; the Tier 1 attack corpus targets
  each gate in isolation by construction.
- Denial reason is available at "which gate" granularity, giving the
  audit trail real diagnostic value beyond a bare allow/deny.
- Matches the layered threat model from the literature review directly,
  rather than asserting a correspondence without a structural one.

**Negative, discovered during evaluation harness construction**

Sequential execution means an earlier gate's denial can preempt a later
gate from ever being exercised by a given malicious input. This was found
concretely, not anticipated: `T2-G4-02` in the Tier 2 corpus was designed
to test Gate 4's injection-character filter, but because the demo agent's
`read_record` tool reuses the same string as both the Cedar resource
lookup key (Gate 2) and the validated argument value (Gate 4), an injected
identifier is simultaneously "not a known entity" and "contains injection
characters." Gate 2 runs first and denies for the former reason, so Gate
4's filter is never actually exercised by that specific request shape.

This is not a flaw in the four-gate model itself, each gate still does
genuinely independent work in general (confirmed directly: Gate 4's
numeric bounds check has no Gate 2 equivalent, since Cedar never inspects
argument content at all, only `principal`, `action`, `resource`, and
`context`). It is a real nuance in how gates compose for specific request
shapes, and a caution for interpreting any single test result: "denied at
Gate N" is evidence about Gate N only if an earlier gate could not also
have denied the same request for an unrelated reason. Worth stating
explicitly in Results and Discussion rather than assuming gate attribution
is always clean.
