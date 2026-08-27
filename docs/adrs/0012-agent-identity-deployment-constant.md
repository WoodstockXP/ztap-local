# ADR-0012: Agent identity as a gateway deployment constant, not self-asserted

**Status:** Accepted

## Context

Once ADR-0011 required an "acting agent" identity to be present on every
Gate 2 request, a decision was needed for where that identity value comes
from.

## Decision

The acting agent's identity is a fixed configuration value on the gateway
process itself, an environment variable (`ZTAP_AGENT_ID`) read once at
process start, not a value the caller supplies per request.

## Alternatives Considered

- **Letting the caller self-assert its own agent identity in the request
  payload**: rejected outright as a security hole. An untrusted caller
  could simply claim to be a more privileged agent identity, which would
  defeat the entire purpose of scoping agent permissions in the first
  place.
- **Issuing agents their own separate cryptographic credential**, a
  distinct token or certificate per agent identity, verified with the
  same rigor as Gate 1's user token: this is the architecturally correct
  long-term answer, and matches the Identity pillar's own "Agent:
  Discrete identity" design goal. It was not built in this pass; a real
  credential issuance and verification system for agent identities is
  substantial additional work, out of scope for the current phase.

## Consequences

**Positive**

- Closes the self-assertion security hole entirely, while still allowing
  the `acting_as` split from ADR-0011 to be demonstrated and tested end
  to end with a real, working example.

**Negative, an explicit and important limitation**

Agent identity as currently implemented carries none of Gate 1's
cryptographic rigor. Changing which agent is "acting" for a deployment
requires restarting the gateway process with a different environment
variable value, not presenting a request-level credential. A real
deployment intending to front multiple distinct agents simultaneously,
not switchable only by restart, cannot be represented by this design as
it stands. This should be stated clearly in the paper's Limitations
section rather than left implicit or, worse, described in language that
implies agent identity is verified with anything like the strength of
user identity. It is not; it is trusted configuration, not verified
identity.
