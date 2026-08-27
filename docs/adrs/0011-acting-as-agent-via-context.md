# ADR-0011: User acting_as Agent modeled via Cedar context, not a compound principal

**Status:** Accepted

## Context

The Jul 20th supervisor feedback identified that Gate 2's principal was a
single undifferentiated identity, and pointed to the emerging OpenID
AuthZen profile, which separates the human user, modeled as the "Subject,"
from the acting AI agent, modeled as part of the "Context," specifically
so a policy can evaluate the trust level of each independently. The
feedback's illustrative notation, `principal == User::"alice" acting_as
Agent::"invoice-agent-v2"`, is not real Cedar syntax; Cedar principals are
single entities, and an implementation decision was needed for how to
actually express this split in a working Cedar policy.

## Decision

Keep `principal` as the human User entity, unchanged, still the subject of
the tenant-boundary check. Pass the acting agent's identity in the Cedar
request's `context` field as an entity reference, with the agent's own
`allowedActions` exposed as a `Set<Action>` attribute that a policy can
check membership against.

## Alternatives Considered

- **A compound or synthetic principal entity representing the (user,
  agent) pair**: rejected as a more invasive schema change with no clear
  benefit over using `context`, and it would have broken the simple,
  direct `principal.tenant == resource.tenant` check that only needs the
  human identity.
- **A second, separate authorization call for agent scope**: rejected as
  adding a second round trip and a second policy evaluation for no real
  benefit, when Cedar's `context` mechanism already supports evaluating
  both facts inside a single request.

## Consequences

**Positive**

- Both checks, the tenant boundary and the agent's own scope, are
  evaluated in one Cedar request, each independently able to deny,
  matching the two-question framing from the original feedback directly:
  "is this user allowed to do this at all" and "is this specific agent
  allowed to do this on the user's behalf."
- Demonstrated empirically, not just designed: an agent configured with a
  narrower scope than its user (`invoice-agent-readonly`) is denied an
  update action that the same user, acting through a fully-scoped agent
  (`invoice-agent-v2`), is permitted to perform, with every other
  variable (user, tenant, resource) held identical.

**Negative**

The security value of this split currently rests on trusting which agent
identity is asserted into `context`, and that identity is not itself
independently authenticated, it is a gateway-level deployment constant.
See ADR-0012 for that decision and its own accepted limitation.
