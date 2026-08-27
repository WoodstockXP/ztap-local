# ADR-0013: Resource Owner Password Credentials for local testing only

**Status:** Accepted

## Context

The local test client and the evaluation harness both need to obtain
real, DPoP-bound access tokens from Keycloak repeatedly and
programmatically, without a browser in the loop, since both are scripts
run many times in a row, including deliberately in bursts for Gate 3
testing.

## Decision

Use the OAuth 2.0 Resource Owner Password Credentials grant, Keycloak's
Direct Access Grant, for the test client and the evaluation harness only.

## Alternatives Considered

- **Authorization Code flow with a real browser**: the standards-correct
  flow for a production client, and the flow real end users would go
  through. Not used for the test harness specifically because it cannot
  be scripted without headless browser automation or a mocked
  authorization step, adding real complexity to a component whose only
  job is exercising the gateway's enforcement logic, not testing a login
  user experience that this project does not otherwise touch.

## Consequences

**Positive**

- Trivially scriptable: every harness run obtains a fresh, real,
  DPoP-bound token in a few lines of code, with no browser automation
  dependency, which matters directly for a harness designed to run many
  times across many test cases.

**Negative**

Resource Owner Password Credentials is a grant type explicitly deprecated
for production use under OAuth 2.1, precisely because it requires the
client to handle the user's raw password directly. It is appropriate only
when the client itself is fully trusted, true here, the harness is
project-owned code using test credentials for test users, and it is never
appropriate for a real third-party or production agent client obtaining
delegated access on a real user's behalf. This must be stated explicitly
as a testing-only simplification if the token acquisition flow is
described anywhere in the paper's Methodology section, not presented as
the architecture's intended production authentication pattern.
