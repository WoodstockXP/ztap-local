# ADR-0004: Cedar as the policy engine for Gate 2

**Status:** Accepted

## Context

The Policies pillar requires a deterministic Policy-as-Code engine
evaluating a user's permissions and, later, an acting agent's own scope
(see ADR-0011), separated from application logic so policy can be
audited, tested, and updated independently of the enforcement code path.

## Decision

Cedar, via the official `cedar` CLI (Rust, `cargo install
cedar-policy-cli`) for offline policy authoring and unit testing, and
`cedarpy` (Python bindings) for in-process evaluation inside the gateway.

## Alternatives Considered

- **OPA / Rego**: the industry-standard alternative, and the one used in
  a directly relevant piece of related work (Mao et al. 2025's API
  gateway benchmark). Not chosen because Cedar's request model natively
  supports typed entities with attributes and hierarchical membership
  checks (`in`), which mapped directly onto this project's entity model
  (`principal.tenant == resource.tenant`, `action in
  context.agent.allowedActions`) without custom Rego helper logic. Cedar's
  principal/action/resource/context request shape also matches the
  AuthZen-style authorization request format the Jul 20th feedback's
  User/Agent split is built around, whereas OPA's input document is
  schema-free and would require the same structure to be imposed by
  convention rather than by the engine itself.

## Consequences

**Positive**

- Policies live as declarative `.cedar` files, testable via the official
  CLI entirely outside the Python application, exactly as done for the
  very first smoke test before any gateway code existed.
- Cedar's strict typed entity schema surfaces malformed policy or entity
  data early, as validation errors, rather than as silent incorrect
  authorization decisions.
- Having both the CLI and the Python bindings gave a fast, dependency-free
  authoring loop and a real in-process evaluation path, without settling
  for only one.

**Negative**

- `cedarpy` is an unofficial, community-maintained wrapper around the
  Rust `cedar-policy` crate, not maintained by AWS or the Cedar
  maintainers. This is a real maintenance risk worth flagging rather than
  treating as equivalent in support to the official CLI.
- The policy text is currently re-parsed on every single request rather
  than cached as a compiled policy set. Measured directly: Gate 2 adds
  roughly 15ms of latency per request, an order of magnitude more than
  Gates 1, 3, or 4 combined. This is a known, unaddressed optimization
  opportunity, and matters for Frame 3's latency-overhead claims, which
  currently reflect this unoptimized state.
