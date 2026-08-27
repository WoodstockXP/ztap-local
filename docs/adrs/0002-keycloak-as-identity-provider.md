# ADR-0002: Keycloak as the Identity Provider

**Status:** Accepted

## Context

Gate 1 needs a real OAuth 2.0 Identity Provider capable of issuing DPoP
bound access tokens (see ADR-0003), self-hosted per ADR-0001. The provider
also needs to support custom user attributes (tenant assignment) surfaced
as token claims, since tenant resolution in Gate 1 depends on a `tenant`
claim being present and trustworthy.

## Decision

Keycloak, specifically version 26.4 or later, chosen because that is the
first release where DPoP support (RFC 9449) is officially supported rather
than a preview feature (DPoP had existed since Keycloak 23.0.0 as preview
only). Realm, client, and test-user configuration is version-controlled as
a realm-import JSON file (`keycloak/ztap-realm.json`) so a fresh container
reproduces the exact same identity configuration every time.

## Alternatives Considered

- **Ory Hydra or Kratos**: self-hosted and viable in principle, but DPoP
  support maturity was not independently verified at the time of
  evaluation, and switching would have meant re-deriving the same
  confidence Keycloak's official 26.4 announcement already provided.
- **Auth0 or Okta**: rejected under ADR-0001, managed and commercial.
- **A custom-built OAuth server**: rejected. Reinventing token issuance
  and DPoP proof handling from scratch carries high risk of subtle
  authentication bugs that would undermine the entire security claim the
  gateway depends on; using a maintained, standards-compliant IdP was the
  more defensible choice for a component this security-critical.

## Consequences

**Positive**

- The realm-import file gives fully reproducible identity configuration
  from a clean container, no manual console clicking required to recreate
  the environment.
- Official (non-preview) DPoP support as of 26.4 means Gate 1's AS-issued
  `cnf.jkt` lifetime binding (see ADR-0003) is a real, standards-track
  guarantee rather than a workaround built on an unstable preview feature.

**Negative**

- Exact realm-import attribute names for some newer client settings (for
  example the flag enabling required DPoP-bound tokens) were not
  confirmed against authoritative documentation before implementation,
  and had to be verified empirically against a running instance. Anything
  inferred this way should be re-checked before being treated as
  authoritative in the paper.
- The realm also required explicit `firstName`, `lastName`, and `email`
  fields on imported users, and an explicit empty `requiredActions` list,
  neither of which was obvious from the import format alone; both were
  found by debugging a login failure ("Account is not fully set up")
  rather than anticipated in advance.
