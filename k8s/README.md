# ZTAP on Kubernetes: Bridge and Silo

This covers the Kubernetes-deployed portion of the project (outline Phase 5 onward), separate from the top-level README, which covers the local Docker Compose harness (Phase 4) that this still depends on for the actual gateway/agent/policy code.

## Status

Both tenants' Silo stacks (Keycloak + gateway, `authorizer-a`/`enforcer-a` and `authorizer-b`/`enforcer-b`) are up on a local kind cluster, with Cilium enforcing NetworkPolicy and a default-deny baseline across all ten namespaces, gVisor is smoke-tested and now protects a real `agent-sandbox` pod in each of `tenant-a`/`tenant-b`, backed by a shared Ollama deployment in `inference`. `traffic-gen-a`/`traffic-gen-b` are still empty. Bridge topology is not yet built.


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

Docker must already be installed and running (see the top-level README). The Cilium CLI is installed automatically by `install-cilium.sh` in step 0 below if it's not already on your PATH.

## 0. Recreate the cluster with Cilium as the CNI

kind's default CNI (kindnet) doesn't enforce `NetworkPolicy` at all, silently allowing everything, so it needs to be swapped out before NetworkPolicy is worth writing. `k8s/kind/kind-ztap.yaml` now sets `disableDefaultCNI: true`, which only takes effect on cluster creation, so if you already have a `ztap` cluster from the previous steps, delete it first:

`kind-ztap.yaml` also now references `ztap-node-gvisor:local` for the `tenant-a`/`tenant-b` workers (step 6), which means that image has to exist *before* `kind create cluster` runs, on every bootstrap, not just the first time. If you're migrating an existing cluster forward, `build-gvisor-node-image.sh` auto-detects the right base tag from it. If you're starting completely fresh (no `ztap` cluster running at all, e.g. after a full teardown), there's nothing to auto-detect from, pass the tag explicitly; `kind create cluster` will tell you the exact tag it wants if you forget and it fails on the control-plane image:

```bash
kind delete cluster --name ztap
chmod +x k8s/kind/build-gvisor-node-image.sh
k8s/kind/build-gvisor-node-image.sh kindest/node:v1.37.0
kind create cluster --config k8s/kind/kind-ztap.yaml
chmod +x k8s/kind/install-cilium.sh
k8s/kind/install-cilium.sh
```

Cilium has to be installed before any workload is deployed, a cluster with no CNI at all can't schedule pods, they'll sit `Pending` forever. `cilium status --wait` confirms it's actually up, not just applied, before you move on.

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
  python client/call_gateway.py bob bob-pass readRecord rec-002
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

## 5. Check that the tenants can't cross-reach each other's pods at all

Step 4 proved the app-level check (Gate 1's issuer validation) blocks cross-tenant identity reuse. This step proves something stronger and independent of it: that `enforcer-a`'s pod can't even open a TCP connection to `authorizer-b`'s pod, regardless of what token it presents. Bring the NetworkPolicies in:

```bash
kubectl apply -f k8s/base/network-policy/default-deny-all.yaml
kubectl apply -f k8s/base/network-policy/allow-dns.yaml
kubectl apply -f k8s/base/network-policy/allow-enforcer-authorizer.yaml
```

`deploy-all.sh` deliberately does not apply these on its own. If it did, they'd already be active by the time you reached step 4 above, and the cross-tenant token fetch would fail at the network layer before it ever reached Gate 1, showing a `ConnectTimeout` instead of the `403 Invalid issuer` step 4 is meant to demonstrate. Keeping this as a separate, explicit step is what makes step 4 and step 5 each show their own layer cleanly, rather than one silently masking the other.
 
```bash
#Run this in case you want to retry step 4
kubectl delete -f k8s/base/network-policy/default-deny-all.yaml -f k8s/base/network-policy/allow-dns.yaml -f k8s/base/network-policy/allow-enforcer-authorizer.yaml
```

First confirm the allowed path still works, tenant A's gateway reaching its own Keycloak, same command as step 3:

```bash
kubectl exec -it deploy/ztap-gateway -n enforcer-a -- env \
  ZTAP_KEYCLOAK_TOKEN_URL=http://keycloak.authorizer-a.svc.cluster.local:8080/realms/ztap-tenant-a/protocol/openid-connect/token \
  ZTAP_GATEWAY_URL=http://localhost:8001/invoke \
  python client/call_gateway.py alice alice-pass readRecord rec-001
```

Still `200 ALLOW`, the default-deny baseline didn't break the one path we explicitly opened. Now try to reach tenant B's Keycloak from tenant A's gateway pod, at the network layer, no gateway app code involved at all:

```bash
kubectl exec -it deploy/ztap-gateway -n enforcer-a -- python3 -c "
import httpx
try:
    r = httpx.get('http://keycloak.authorizer-b.svc.cluster.local:8080/realms/ztap-tenant-b/.well-known/openid-configuration', timeout=5)
    print('REACHABLE', r.status_code)
except Exception as e:
    print('BLOCKED', type(e).__name__)
"
```

Expect `BLOCKED ConnectTimeout`. Before step 5, this same command would have printed `REACHABLE 200`, Kubernetes allows all pod-to-pod traffic by default, so the request would have gone through fine and only gotten rejected later, at the application layer, if you'd tried to actually use a resulting token. Now it's refused before a single byte of application logic runs.

## 6. Rebuild the cluster once more with gVisor-enabled nodes

This needs another cluster recreation, gVisor requires a custom node image with the `runsc` binaries baked in, which can only be set at cluster-creation time, same constraint as the Cilium CNI change in step 0. If you're following the steps in order from a cluster that's already up, build the custom image first, while the current cluster (and its node image) still exists to auto-detect from. (If you're instead bootstrapping completely fresh with no cluster running at all, see step 0's note above, the image has to be built with an explicit tag before the very first `kind create cluster` call, this section assumes that's already done.)

```bash
chmod +x k8s/kind/build-gvisor-node-image.sh
k8s/kind/build-gvisor-node-image.sh
```

Then recreate everything:

```bash
kind delete cluster --name ztap
kind create cluster --config k8s/kind/kind-ztap.yaml
k8s/kind/install-cilium.sh
k8s/kind/deploy-all.sh
kubectl apply -f k8s/base/gvisor/runtimeclass.yaml
```

`kind-ztap.yaml` now points the `tenant-a` and `tenant-b` worker nodes at `ztap-node-gvisor:local` instead of kind's default image, and patches every node's containerd config to register `runsc` as a runtime handler. Registering the handler is harmless on nodes that don't actually have the `runsc` binary (monitoring, inference, control-plane), containerd just won't be able to serve pods that ask for it there, which is exactly what we want: `runtimeclass.yaml`'s `nodeSelector` only allows scheduling onto nodes labeled `ztap.io/gvisor: "true"`, i.e. `tenant-a` and `tenant-b`.

## 7. Verify gVisor is actually running, not silently falling back

```bash
kubectl apply -f k8s/base/gvisor/smoke-test-pod.yaml
kubectl logs gvisor-smoke-test -n tenant-a
```

Under gVisor, `dmesg` doesn't print the host kernel's boot log, it prints gVisor's own, since the sandbox implements the syscall interface itself rather than passing through to the host. Expect lines starting with `Starting gVisor...`, not a normal Linux kernel banner. If the pod instead fails to schedule at all, check `kubectl describe pod gvisor-smoke-test -n tenant-a` for the reason, the most likely cause is the node image build not actually completing before cluster recreation, or the `runsc` binary download failing partway (this Dockerfile has no retry logic, unlike `install-cilium.sh`'s CLI download, worth adding if it turns out to be flaky on your connection). Clean up once confirmed:

```bash
kubectl delete -f k8s/base/gvisor/smoke-test-pod.yaml
```

This proves gVisor itself works on this machine. It's deliberately not wired into the actual agent sandbox yet, that pod doesn't exist in the manifests so far, only Keycloak and the gateway do. Step 8 below is that pod.

## 8. Deploy the real Agent Sandbox and Ollama

Per the diagram, the gVisor-protected "Agent Sandbox" lives in `tenant-X` (the untrusted compute zone), not `traffic-gen-X`, that namespace is for whatever originates test traffic later, a separate concern. This also needs the shared `inference` service (Ollama), which doesn't exist yet either, everything up to now has only used the Keycloak/gateway path.

```bash
kubectl apply -f k8s/base/network-policy/allow-agent-inference.yaml
kubectl apply -f k8s/base/network-policy/allow-agent-authorizer.yaml
chmod +x k8s/kind/deploy-agents.sh
k8s/kind/deploy-agents.sh
```

This applies the new NetworkPolicy first: each tenant's agent needs egress to two places, its own tenant's Keycloak (to fetch its own DPoP-bound token directly, the same two-step flow the test client uses) and its own tenant's gateway (to actually invoke tools), plus the shared `inference` service, nothing else. `inference` also gets one narrow addition to the default-deny baseline, HTTPS egress to the internet, needed for the one-time pull of `llama3.2:3b` from `registry.ollama.ai`. No other namespace gets internet egress; Gate evaluation and the gateway pipeline never need to leave the cluster, only model provisioning does.

```bash
kubectl exec -n inference deploy/ollama -- ollama list
```

Once `ollama list` shows `llama3.2:3b`, run the agent for real, same command as the top-level README's local Compose instructions, just executed inside the sandboxed pod instead of on your machine directly:

```bash
kubectl exec -it deploy/agent-sandbox -n tenant-a -- python -m agent.run_agent alice alice-pass "Read record rec-001"
```

This exercises the entire pipeline in-cluster: the agent calls Ollama over the network for inference, decides to call `readRecord`, that call goes through `GatewaySession` to `enforcer-a`'s gateway, through all four gates, and the result comes back to the agent, which the model then turns into its final answer. Worth also trying the cross-tenant case from the `run_agent.py` docstring, alice attempting one of bob's records, to confirm Gate 2's tenant boundary still holds when the request originates from a real model-driven agent rather than the test client:

```bash
kubectl exec -it deploy/agent-sandbox -n tenant-a -- python -m agent.run_agent alice alice-pass "Read record rec-002"
```

Expect the agent's final answer to report a denial, sourced from the gateway's actual `403`, not the model simply refusing on its own.

## 9. Tear down

```bash
kind delete cluster --name ztap
```

## Useful commands

### Log check

```bash
#Replace enforcer-x with either enforcer-a or enforcer-b
kubectl logs -n enforcer-x deploy/ztap-gateway --tail=20
```

### Check cilium status & resources

```bash
#Overall status
cilium status
#Pods
kubectl get pods -n kube-system -l k8s.app=cilium
#Nodes
kubectl get nodes -L ztap.io/node-pool
```

## Next up

- Bridge topology manifests (shared `gateway-ingress` / `authorizer` namespaces, deliberately without the default-deny-all/per-tenant NetworkPolicy split built here, that's the actual isolation-depth variable the paper measures).
- Point `eval/run_gateway_attacks.py` and `eval/run_agent_attacks.py` at the in-cluster stack instead of localhost, they can now target the real `agent-sandbox` pods instead of running locally against `localhost` Ollama.
- `traffic-gen-a`/`traffic-gen-b` are still empty. Once the eval harness moves in-cluster, that's presumably where it runs from, dispatching requests to the agent sandboxes rather than being the sandbox itself.