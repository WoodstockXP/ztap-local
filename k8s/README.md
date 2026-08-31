# ZTAP on Kubernetes: Bridge and Silo

This covers the Kubernetes-deployed portion of the project (outline Phase 5 onward), separate from the top-level README, which covers the local Docker Compose harness (Phase 4) that this still depends on for the actual gateway/agent/policy code.

## Status

Tenant A's Silo stack (Keycloak + gateway, `authorizer-a` + `enforcer-a` namespaces) is up and reachable on a local kind cluster. Tenant B, NetworkPolicies, gVisor sandboxing, and the Bridge topology are not yet built.

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

## 1. Bring up tenant A's Silo stack

From the repo root:

```bash
chmod +x k8s/kind/deploy-tenant-a.sh
./k8s/kind/deploy-tenant-a.sh
```

This creates the `ztap` kind cluster if it doesn't exist, builds the `ztap-app:local` image from the repo's `Dockerfile`, loads it into kind, applies all ten Silo namespaces, creates the `ztap-realm-tenant-a` ConfigMap from `keycloak/ztap-realm-tenant-a.json`, then applies and waits on the `authorizer-a` Keycloak deployment and the `enforcer-a` gateway deployment.

Expect it to finish with `tenant-a stack up: keycloak.authorizer-a, ztap-gateway.enforcer-a`.

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

The client's Keycloak/gateway URLs are env-configurable now (`ZTAP_KEYCLOAK_TOKEN_URL`, `ZTAP_GATEWAY_URL`, `ZTAP_CLIENT_ID`), so the same `client/call_gateway.py` works unmodified, just point it at the tenant-a realm:

```bash
export ZTAP_KEYCLOAK_TOKEN_URL=http://localhost:8080/realms/ztap-tenant-a/protocol/openid-connect/token
python client/call_gateway.py alice alice-pass readRecord rec-001
```

Expect `200 ALLOW`, same result as the Compose version, now served from inside the cluster.

## 4. Tear down

```bash
kind delete cluster --name ztap
```

## Next up

- Mirror this for tenant B (`authorizer-b` / `enforcer-b`, `ztap-realm-tenant-b`).
- Cilium `NetworkPolicy` per tenant, this is what actually makes the Silo isolation claim testable, not just the namespace split.
- gVisor `RuntimeClass` on the agent sandbox pods.
- Bridge topology manifests (shared `gateway-ingress` / `authorizer` namespaces).
- Point `eval/run_gateway_attacks.py` and `eval/run_agent_attacks.py` at the in-cluster stack instead of localhost.