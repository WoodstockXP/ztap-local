# Running the eval harness in-cluster

Both tiers work unmodified against Silo or Bridge, they read `ZTAP_KEYCLOAK_TOKEN_URL`, `ZTAP_GATEWAY_URL`, and `ZTAP_OLLAMA_BASE_URL` the same way `agent/run_agent.py` does, and every `agent-sandbox` pod already has these set correctly for wherever it lives. Which topology or tenant you're testing is entirely a function of which pod you `exec` into, not anything in the harness code.

## Prerequisites

The `ztap-app:local` image needs the eval harness's dependencies, which it already has, `eval/` is copied into the image by the `Dockerfile` alongside `gateway/`, `agent/`, and `client/`. No separate image or deployment needed. `read_entries()` (used by both tiers for scoring) now fetches from the gateway's own `/debug/audit` endpoint over HTTP rather than reading a local file, this matters specifically because the harness runs in the agent-sandbox pod and the gateway runs in its own pod with its own filesystem, they don't share one.

## Tier 1: gateway attack corpus (Silo, tenant A)

```bash
kubectl exec -it deploy/agent-sandbox -n tenant-a -- env \
  ZTAP_KEYCLOAK_TOKEN_URL=http://keycloak.authorizer-a.svc.cluster.local:8080/realms/ztap-tenant-a/protocol/openid-connect/token \
  ZTAP_GATEWAY_URL=http://ztap-gateway.enforcer-a.svc.cluster.local:8001/invoke \
  python -m eval.run_gateway_attacks
```

## Tier 2: agent-mediated prompt injection (Silo, tenant A)

```bash
kubectl exec -it deploy/agent-sandbox -n tenant-a -- env \
  ZTAP_KEYCLOAK_TOKEN_URL=http://keycloak.authorizer-a.svc.cluster.local:8080/realms/ztap-tenant-a/protocol/openid-connect/token \
  ZTAP_GATEWAY_URL=http://ztap-gateway.enforcer-a.svc.cluster.local:8001/invoke \
  ZTAP_OLLAMA_BASE_URL=http://ollama.inference.svc.cluster.local:11434/v1/ \
  python -m eval.run_agent_attacks
```

Add `--only T2-G4-02` (or any comma-separated case IDs) to run a subset while iterating.

## The same commands against Bridge or tenant B

Swap the three env values for whatever that pod already has baked in, or just don't override them at all, since the pod's own defaults already point at the right place. For Bridge tenant A, that's:

```bash
kubectl exec -it deploy/agent-sandbox -n tenant-a -- python -m eval.run_gateway_attacks
kubectl exec -it deploy/agent-sandbox -n tenant-a -- python -m eval.run_agent_attacks
```

no `env` overrides needed at all, the Bridge `agent-sandbox` Deployment already sets `ZTAP_GATEWAY_URL` to `gateway-ingress` and `ZTAP_KEYCLOAK_TOKEN_URL` to the shared `authorizer`, since that's just what's correct for that pod. This is the same reason the Silo commands above explicitly override the env vars, when there are two tenants sharing one image, the harness needs to be told which one it's acting as; Bridge doesn't have that ambiguity to begin with.

## Comparing Silo vs Bridge

Since `kubectl exec`'s current context determines which cluster you're talking to, run the same commands once with `kubectl config use-context kind-ztap` and once with `kind-ztap-bridge`, and diff the two summaries. This is the actual comparison Phase 5's milestone is asking for, everything up to this point has been building the two arms, this is where they get pointed at each other.
