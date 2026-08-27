# ADR-0006: Sliding-window counters for Gate 3, not statistical or ML anomaly detection

**Status:** Accepted

## Context

The Aug 10th supervisor feedback distinguished two different ways to
address the temporal, aggregate-pattern gap that no single-request check
can close: rate limiting (a blunt, volume-only instrument) and User and
Entity Behavior Analytics, UEBA, which catches subtler patterns but
trades away provable, deterministic, auditable decisions for statistical
or ML-based anomaly scoring. The feedback explicitly proposed "per-session
call-count and rate thresholds on sensitive actions, simple counters, not
machine learning" as a real-world mitigation achievable within the
project's scope, narrowing the gap without claiming to close it.

## Decision

Gate 3 is implemented as a sliding-window call counter, keyed on
`(tenant, principal, action)`, with per-action thresholds and no
statistical modeling of any kind.

## Alternatives Considered

- **UEBA-style continuous behavioral risk scoring** (Thompson 2024, an
  agent's effective privilege tightens as a running risk score rises) or
  **persona-deviation detection** (Cunningham 2026, observed behavior
  compared against a declared job description): both discussed directly
  in Background as approaches that close the temporal gap more fully than
  a stateless or simple-state gate. Rejected for this project because
  both give up the deterministic, provable decision property that is
  central to the architecture's value proposition. A simple counter's
  behavior can be reasoned about and audited exactly; an ML-based scorer
  cannot, without a separate evaluation of the scorer itself, which was
  out of scope.

## Consequences

**Positive**

- Fully deterministic and directly unit-testable: threshold trip points,
  window expiry, and per-key independence were all verified against
  synthetic timestamp sequences before being trusted in the pipeline.
- Toggleable via `ZTAP_GATE3_ENABLED`, which is what makes the Evaluation
  Plan's "Gates 1, 2, and 4 only" baseline possible at all, isolating
  what aggregate-pattern detection specifically adds.

**Negative**

- This explicitly narrows rather than closes the aggregate-pattern gap,
  language borrowed directly from the Aug 10th feedback rather than an
  independent claim. A sufficiently patient or low-volume attacker
  operating under the threshold is not caught by this gate at all.
- Threshold values (10 reads per 60 seconds, 3 updates per 60 seconds)
  are starting points, not values validated against real false-positive
  rates on legitimate bursty usage. This is an open item under the
  outline's own "Session envelope thresholds" trade-off, not yet
  addressed.

**Discovered operational risk (fixed during harness construction)**

The counter store is process-local and persists for the life of the
gateway process. Running a multi-case evaluation harness against a live
gateway without resetting state between test cases caused later cases to
be silently affected by earlier ones' accumulated call counts, a real bug
that produced misleading results before being caught and fixed with a
dedicated reset endpoint used only by the test harness. Worth a
limitations note: any production form of this gate needs an explicit
session or window boundary, not an unbounded-lifetime, process-global
store, which is what the current implementation actually is.
