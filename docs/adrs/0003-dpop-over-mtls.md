# ADR-0003: DPoP (RFC 9449) over mTLS for token binding

**Status:** Accepted

## Context

The Identity pillar requires cryptographic binding: a stolen bearer token
alone must not be sufficient to impersonate a session. Two IETF standards
address this directly: DPoP (RFC 9449, application-layer, tokens bound to
a client-held keypair via a per-request signed proof) and mTLS (RFC 8705,
transport-layer, tokens bound to a client certificate presented during the
TLS handshake). Both are legitimate, standards-track answers to the same
problem; the choice between them is a real architectural decision, not a
default.

## Decision

DPoP.

## Reasoning

**Deployment topology.** The Inline Policy Interceptor (Gates 1 to 4)
operates entirely at Layer 7, parsing JSON request payloads directly. mTLS
binding happens at the TLS layer, typically terminated at a load balancer
or ingress point sitting in front of the application, per the hub VPC
discussion in the Aug 10th feedback. Using mTLS would require that
termination point to extract the client certificate's thumbprint and
forward it into the request context for Gate 1 to consume, adding an
infrastructure dependency and a trust hop the architecture does not
currently have. DPoP's proof is a JWT carried in an ordinary HTTP header,
so the same interceptor code that already parses the request for Gates 2
and 4 can verify it directly, no additional infrastructure piece required.

**Certificate lifecycle overhead.** mTLS requires provisioning, rotating,
and revoking a client certificate per agent instance per tenant. The Silo
configuration multiplies this by spinning up entirely separate
infrastructure per tenant. Within a six-week project timeline, this is a
meaningfully heavier operational burden than DPoP's client-generated,
short-lived keypairs.

**Fit with the non-human identity literature.** The Background section's
review of cryptographic identity fabrics and token-driven delegation
(Huang et al. 2025, Fujie et al. 2026) frames agent identity binding
around short-lived, application-layer credentials rather than long-lived
certificates. DPoP's per-request proof model matches that framing more
directly than mTLS's session-level certificate binding.

**Keycloak's maturity.** Keycloak's official DPoP support (see ADR-0002)
made DPoP the path of least resistance to a real, standards-track,
Authorization-Server-issued binding without standing up separate
certificate-issuance infrastructure.

## Alternatives Considered

- **mTLS (RFC 8705)**: rejected for the reasons above; a legitimate
  alternative, not a weaker standard, just a worse fit for this
  architecture's Layer 7 enforcement point and timeline.
- **Unbound bearer tokens**: rejected outright. Defeats the cryptographic
  binding requirement entirely; a stolen token would be immediately
  usable by an attacker with no additional barrier.

## Consequences

**Positive**

- The proof travels with the request at the application layer, with no
  dependency on TLS termination forwarding certificate metadata.
- Two independent layers of protection are implemented in Gate 1: the
  Authorization-Server-issued `cnf.jkt` lifetime binding, confirmed
  genuinely enforced (a stolen bearer token used with the wrong private
  key is denied), plus per-request proof checks (replay cache via `jti`,
  `htm`/`htu` match, freshness window, and `ath` binding to the specific
  token presented).

**Negative**

- DPoP is a newer, less battle-tested standard in production identity
  systems than mTLS.
- Keycloak's per-version DPoP maturity had to be verified empirically
  rather than assumed, see ADR-0002.
- The local test client and evaluation harness obtain DPoP-bound tokens
  via the Resource Owner Password Credentials grant for scripting
  convenience, a testing-only simplification documented separately in
  ADR-0013, not representative of how a production agent would acquire a
  token.
