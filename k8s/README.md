# ZTAP on Kubernetes: Bridge and Silo

This covers the Kubernetes-deployed portion of the project (outline Phase 5 onward), separate from the top-level README, which covers the local Docker Compose harness (Phase 4) that this still depends on for the actual gateway/agent/policy code.

## Status

Both tenants' Silo stacks (Keycloak + gateway, `authorizer-a`/`enforcer-a` and `authorizer-b`/`enforcer-b`) are up and reachable on a local kind cluster. NetworkPolicies, gVisor sandboxing, and the Bridge topology are not yet built.

## Prerequisites

```bash
# kind
curl -Lo ./kind https://kind.sigs.k8s.io/dl/latest/kind-linux-amd64
chmod +x ./kind && sudo mv ./kind /usr/local/bin/kind
kind version

# kubectl, if not already installed
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl && sudo mv kubectl /usr/local/bin/
kubectl version --client
```

Docker must already be installed and running (see the top-level README).

## 1. Bring up both tenant's Silo stacks

From the repo root:

```bash
chmod +x k8s/kind/deploy-tenant-a.sh k8s/kind/deploy-tenant-b.sh k8s/kind/deploy-all.sh
k8s/kind/deploy-all.sh
```

This creates the `ztap` kind cluster if it doesn't exist, builds the `ztap-app:local` image once, loads it into kind, then applies each tenant in turn: namespaces, the tenant's realm ConfigMap, its Keycloak deployment, and its gateway deployment.

Expect it to finish with both `tenant-a stack up: ...` and `tenant-b stack up: ...` lines. To bring up just one tenant, run `k8s/kind/deploy-tenant-a.sh` or `k8s/kind/deploy-tenant-b.sh` directly.

## 2. Reach the stack from your machine

```bash
kubectl port-forward -n authorizer-a svc/keycloak 8080:8080 &
kubectl port-forward -n enforcer-a svc/ztap-gateway 8001:8001 &
```

Sanity-check the realm imported correctly:

```bash
curl -s http://localhost:8080/realms/ztap-tenant-a/.well-known/openid-configuration | head -c 200
```

That should return JSON, not a 404.

## 3. Run the existing test client against it

Run the client from inside the `ztap-gateway` pod, not from the host. The gateway image already bundles `client/`, and this sidesteps a hostname mismatch described in Troubleshooting below:
 
```bash
kubectl exec -it deploy/ztap-gateway -n enforcer-a -- env \
  ZTAP_KEYCLOAK_TOKEN_URL=http://keycloak.authorizer-a.svc.cluster.local:8080/realms/ztap-tenant-a/protocol/openid-connect/token \
  ZTAP_GATEWAY_URL=http://localhost:8001/invoke \
  python client/call_gateway.py alice alice-pass readRecord rec-001
```
 
`GATEWAY_URL` stays `localhost` here since the client is running inside the same pod as uvicorn. Run the same for tenant B, from inside its own gateway pod:

```bash
kubectl exec -it deploy/ztap-gateway -n enforcer-b -- env \
  ZTAP_KEYCLOAK_TOKEN_URL=http://keycloak.authorizer-b.svc.cluster.local:8080/realms/ztap-tenant-b/protocol/openid-connect/token \
  ZTAP_GATEWAY_URL=http://localhost:8001/invoke \
  python client/call_gateway.py bob bob-pass readRecord rec-001
```

Expect `200 ALLOW` here too.
 
## 4. Check that the tenants can't cross-authenticate

This is the actual point of Silo, not just that both work, but that tenant A's identity can't be used against tenant B's gateway. Get a token from `authorizer-a` (tenant A's Keycloak) but present it to `enforcer-b` (tenant B's gateway):

```bash
kubectl exec -it deploy/ztap-gateway -n enforcer-b -- env \
  ZTAP_KEYCLOAK_TOKEN_URL=http://keycloak.authorizer-a.svc.cluster.local:8080/realms/ztap-tenant-a/protocol/openid-connect/token \
  ZTAP_GATEWAY_URL=http://localhost:8001/invoke \
  python client/call_gateway.py alice alice-pass readRecord rec-001
```

Expect `403 Invalid issuer`, tenant B's gateway only trusts `authorizer-b`, so a token from `authorizer-a` fails Gate 1 immediately, the same failure mode you just walked through above, now working as an isolation guarantee instead of a bug. Note this holds even with no NetworkPolicy in place yet, it comes from the identity split (separate realms, separate issuers), not from network-level blocking. NetworkPolicy in the next step adds a second, independent layer on top: even if the issuer check were somehow bypassed, the pods wouldn't be able to route to each other at all.

### Troubleshooting: `Invalid issuer` on Gate 1
 
Keycloak's `start-dev` mode stamps each token's `iss` claim dynamically, from whatever host/port the request actually arrived on, not a fixed value. If you request a token via `kubectl port-forward` to `localhost:8080`, the token's `iss` becomes `http://localhost:8080/...`. The gateway pod's `ZTAP_KEYCLOAK_ISSUER` is set to the in-cluster DNS name (`keycloak.authorizer-a.svc.cluster.local`), since that's the only address actually reachable from inside the pod, so a `localhost`-issued token never matches and Gate 1 denies with `Invalid issuer`. Requesting the token through the same in-cluster hostname the gateway expects (as in step 3 above) avoids this entirely, since it's also how the eval harness will reach Keycloak once it runs in-cluster.

## 5. Tear down

```bash
kind delete cluster --name ztap
```

## Next up

- Cilium `NetworkPolicy` per tenant, this is what actually makes the Silo isolation claim testable, not just the namespace split.
- gVisor `RuntimeClass` on the agent sandbox pods.
- Bridge topology manifests (shared `gateway-ingress` / `authorizer` namespaces).
- Point `eval/run_gateway_attacks.py` and `eval/run_agent_attacks.py` at the in-cluster stack instead of localhost.