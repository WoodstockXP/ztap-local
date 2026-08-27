# ADR-0010: One shared agent process serving all tenants

**Status:** Accepted

## Context

The Aug 10th supervisor feedback asked directly: how many agents, one
shared process or one process per tenant. This has direct cost,
operational complexity, and isolation consequences and needed an explicit
decision rather than an implicit default.

## Decision

A single agent runtime process serves requests for every tenant. Tenant
scoping for any given call comes entirely from which verified token or
session is used to make it, never from a process-level boundary.

## Alternatives Considered

- **One dedicated agent process per tenant**: rejected as more expensive
  and operationally heavier to run and manage than necessary, and because
  Silo's isolation-depth story already provides infrastructure-level
  per-tenant separation at the gateway and backend layer. Duplicating the
  agent runtime as well would blur exactly what is being varied between
  Bridge and Silo, since both configurations would then differ in more
  than one dimension at once.

## Consequences

**Positive**

- Cheaper and simpler to operate than per-tenant agent processes.
- Matches the project's own Silo design: even in the otherwise fully
  duplicated Silo stack, only the inference layer is shared sequentially
  between tenants for cost reasons, following the same underlying
  principle of sharing the expensive, stateless-per-request component
  while keeping tenant-specific state isolated elsewhere.

**Negative**

Named directly in the Aug 10th feedback and still true of the current
build: a shared agent process is exactly where cross-tenant correlation
could occur if the model's context or memory is not strictly isolated
per request. This makes strict per-request context isolation, no memory
persistence between calls, or memory explicitly scoped and cleared per
tenant, a hard requirement rather than an optional nicety. It should be
included directly in the evaluation rather than assumed to hold; as of
this build, it has not yet been independently verified, only assumed by
the current implementation's stateless-per-call design.
