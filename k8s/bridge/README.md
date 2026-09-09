# ZTAP on Kubernetes: Bridge

This is the comparison arm to Silo (`k8s/README.md`). Same application code, same Cedar policies, same gVisor-protected Agent Sandbox pattern, different topology: one shared Keycloak, one shared gateway, both serving both tenants. Isolation between tenants here rests entirely on Gate 2's Cedar evaluation, there is no separate identity provider per tenant and, deliberately, no per-tenant NetworkPolicy split, that absence is the actual independent variable this arm exists to measure.

## Status

Namespaces, the shared Keycloak (`authorizer`), and the shared gateway (`gateway-ingress`) are built. Not yet deployed or verified. Agent Sandbox, inference, and NetworkPolicy for this topology are not yet built, they'll follow the same order Silo did: golden path first, then duplicate/extend.

## Prerequisites

Same as Silo's, see `k8s/README.md`'s Prerequisites section: kind, kubectl, Docker, and the Cilium CLI (auto-installed by `install-cilium.sh` if missing). The gVisor node image, `ztap-node-gvisor:local`, is reused as-is from the Silo build, it's tied to your kind version, not to a topology, no need to rebuild it here. The `RuntimeClass` object itself is cluster-scoped, though, and does need applying fresh per cluster, `deploy-bridge-agents.sh` handles that automatically now, it isn't bundled with the node image or the containerd config.

One host-level prerequisite worth calling out explicitly, since it's easy to hit on a multi-node kind cluster and the failure mode (`kube-proxy` crash-looping cluster-wide with `too many open files`) doesn't obviously point at itself: Linux's default `fs.inotify` limits are often too low for a 6-node kind cluster running Cilium. If you see that error, raise them:

```bash
sudo sysctl fs.inotify.max_user_watches=524288 && \
sudo sysctl fs.inotify.max_user_instances=512 && \
echo 'fs.inotify.max_user_watches=524288' | sudo tee -a /etc/sysctl.conf && \
echo 'fs.inotify.max_user_instances=512' | sudo tee -a /etc/sysctl.conf 
```

## 0. Bring up the cluster with Cilium

This is a separate cluster from Silo's `ztap`, not a second deployment onto it, Bridge's namespace names (`tenant-a`, `tenant-b`, `inference`, `monitoring`) collide directly with Silo's. If Silo's `ztap` cluster is still running, it's unaffected, this creates `ztap-bridge` alongside it (resource permitting, both running at once is a lot for one laptop, consider `kind delete cluster --name ztap` first if things get slow).

```bash
kind create cluster --config k8s/bridge/kind/kind-ztap-bridge.yaml
chmod +x k8s/kind/install-cilium.sh
k8s/kind/install-cilium.sh
```

`install-cilium.sh` isn't Bridge-specific, it just acts on whatever cluster `kubectl`'s current context points at, and `kind create cluster` switches context automatically, so the same script from Silo works unchanged here.

## 1. Bring up the shared stack

```bash
chmod +x k8s/bridge/kind/deploy-bridge.sh
k8s/bridge/kind/deploy-bridge.sh
```

This applies all seven Bridge namespaces, imports your *original* `keycloak/ztap-realm.json` (both alice and bob, one realm, this is exactly the config that file was written for before Silo ever needed splitting it), and deploys the one shared gateway. Expect `bridge stack up: keycloak.authorizer, ztap-gateway.gateway-ingress`.

## 2. Verify both users through the one shared gateway

Same exec-based pattern as Silo, for the same reason: requesting the token through the in-cluster hostname the gateway expects avoids the `start-dev` dynamic-issuer mismatch covered in `k8s/README.md`'s troubleshooting section.

```bash
kubectl exec -it deploy/ztap-gateway -n gateway-ingress -- env \
  ZTAP_KEYCLOAK_TOKEN_URL=http://keycloak.authorizer.svc.cluster.local:8080/realms/ztap/protocol/openid-connect/token \
  ZTAP_GATEWAY_URL=http://localhost:8001/invoke \
  python client/call_gateway.py alice alice-pass readRecord rec-001
```

Expect `200 ALLOW`. Then bob, through the exact same gateway pod, no separate `enforcer-b` to exec into this time:

```bash
kubectl exec -it deploy/ztap-gateway -n gateway-ingress -- env \
  ZTAP_KEYCLOAK_TOKEN_URL=http://keycloak.authorizer.svc.cluster.local:8080/realms/ztap/protocol/openid-connect/token \
  ZTAP_GATEWAY_URL=http://localhost:8001/invoke \
  python client/call_gateway.py bob bob-pass readRecord rec-002
```

Expect `200 ALLOW` too.

## 3. Check the tenant boundary with no network or identity backstop

This is the test that actually matters for the comparison. In Silo, cross-tenant access failed two independent ways (Gate 1's issuer check, then NetworkPolicy). Here there's only one gateway and one Keycloak, so if Cedar has a bug, there's nothing else standing between bob and alice's data. Same token, same gateway pod, just the wrong record:

```bash
kubectl exec -it deploy/ztap-gateway -n gateway-ingress -- env \
  ZTAP_KEYCLOAK_TOKEN_URL=http://keycloak.authorizer.svc.cluster.local:8080/realms/ztap/protocol/openid-connect/token \
  ZTAP_GATEWAY_URL=http://localhost:8001/invoke \
  python client/call_gateway.py bob bob-pass readRecord rec-001
```

Expect `403`, and check `kubectl logs -n gateway-ingress deploy/ztap-gateway` for the same `GATE2 decision=DENY` line Silo produced. If this holds, it's a genuinely different, and in some ways stronger, piece of evidence than Silo's equivalent test: it means Cedar's tenant boundary is sound on its own, not merely backed up by infrastructure that happens to also be correct.

## 4. Deploy the Agent Sandbox and Ollama

```bash
chmod +x k8s/bridge/kind/deploy-bridge-agents.sh
k8s/bridge/kind/deploy-bridge-agents.sh
```

This applies NetworkPolicy first: each tenant's agent gets egress to the shared `authorizer`, `gateway-ingress`, and `inference`, and nothing else, deliberately no rule anywhere allows `tenant-a` and `tenant-b` to reach each other, that mutual isolation is held constant against Silo on purpose, it's not the variable this comparison is testing. `gateway-ingress` also gets its own egress to `authorizer`, for Gate 1's JWKS fetch, independent of whatever token-fetching a client or agent does. Then Ollama comes up, pulls `llama3.2:3b` as an explicit step (same reasoning as Silo, this is a plain foreground command so a slow pull won't trigger a false CrashLoopBackOff), then both tenants' gVisor-protected `agent-sandbox` pods.

## 5. Verify end-to-end, real agent, shared everything

```bash
kubectl exec -it deploy/agent-sandbox -n tenant-a -- python -m agent.run_agent alice alice-pass "Read record rec-001"
kubectl exec -it deploy/agent-sandbox -n tenant-a -- python -m agent.run_agent alice alice-pass "Read record rec-002"
```

Expect the first to succeed and the second to be denied, same as Silo's equivalent test, but now proven through the shared gateway rather than a per-tenant one. Confirm the denial in `kubectl logs -n gateway-ingress deploy/ztap-gateway`, not the model's paraphrase of it, same caution as before.

## 6. Verify tenant-a and tenant-b still can't reach each other directly

This is the check that actually validates the NetworkPolicy design decision at the top of this doc, that collapsing the enforcement plane didn't also, incidentally, open up the untrusted compute zones to each other. Get tenant-b's Agent Sandbox pod IP directly, bypassing DNS entirely, since there's no Service in front of it and a DNS lookup failure alone wouldn't actually prove NetworkPolicy did anything:

```bash
TENANT_B_AGENT_IP=$(kubectl get pod -n tenant-b -l app=agent-sandbox -o jsonpath='{.items[0].status.podIP}')
kubectl exec -it deploy/agent-sandbox -n tenant-a -- python3 -c "
import httpx
try:
    r = httpx.get('http://${TENANT_B_AGENT_IP}:8001', timeout=5)
    print('REACHABLE', r.status_code)
except Exception as e:
    print('BLOCKED', type(e).__name__)
"
```

Expect `BLOCKED ConnectTimeout`, not a fast `ConnectError`/refused. That distinction matters: a timeout means Cilium silently dropped the packets, a fast refusal would mean the packets got through fine and there just happened to be nothing listening on that port, which would prove nothing about the policy. Nothing's actually listening on 8001 in `tenant-a`'s or `tenant-b`'s Agent Sandbox either way, the point is that a timeout means the connection attempt never got a chance to find that out.

## 7. Tear down

```bash
kind delete cluster --name ztap-bridge
```

## Next up

- Point the eval harness at both topologies once both are fully built, that comparison is the actual point of Phase 5's milestone.