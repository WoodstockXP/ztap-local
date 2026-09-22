# ZTAP Terraform (AWS)

Deploys the Bridge and Silo topologies to real EKS infrastructure, mirroring `k8s/` and `k8s/bridge/` locally. Each topology has its own root config under `envs/`, calling the same shared modules under `modules/` with different parameters, the same "same image, differ in manifests" principle the kind setup already follows.

## Prerequisites

- AWS CLI configured with working credentials: `aws sts get-caller-identity` should return your account, not an error.
- `aws configure set region us-east-1`, everything here is pinned to that region.
- Terraform installed, provider versions are pinned per-module in each `versions.tf`.
- Docker, for building and pushing the `ztap-app` image to ECR.
- `kubectl`, for verification steps after each stage.

## Account caveats, read before starting

This has been built and tested against a personal AWS account on the **Free Plan**, which blocks On-Demand instances above Free Tier eligible types entirely, not a quota issue, an account-level restriction. `node_capacity_type` defaults to `SPOT` in both `envs/bridge/variables.tf` and `envs/silo/variables.tf` to route around this. If your account is upgraded to a paid plan, override with `-var="node_capacity_type=ON_DEMAND"` for a more stable eval run, since Spot instances can be reclaimed with two minutes' notice.

A GPU instance quota increase request (`Running On-Demand G and VT instances`) was denied outright on this account. `inference` runs on plain `t3.xlarge`, not a GPU instance, since nothing in the current stack does GPU-accelerated inference anyway (`ollama.yaml` has no GPU wiring, matching local behavior).

**Check Billing before any extended session**, and tear infrastructure down (`terraform destroy`) between work sessions rather than leaving it running overnight. The EKS control plane alone bills hourly regardless of node count.

## Building Bridge from scratch

```bash
cd terraform/envs/bridge
terraform init
```

Bring up infrastructure with no provider dependency problems first:

```bash
terraform apply -target=module.vpc -target=module.eks_cluster -target=module.node_group -target=module.namespaces
```

Cilium needs its own CRDs to exist before its NetworkPolicy resources can be planned, so it's a separate step:

```bash
terraform apply -target=module.cilium.helm_release.cilium
kubectl rollout restart daemonset/cilium -n kube-system
kubectl rollout status daemonset/cilium -n kube-system --timeout=120s
```

**Build and push the application image before running the full apply.** Skipping this step causes `gateway` and `agent-sandbox` to fail with `ImagePullBackOff`, see Known Errors below, this has happened twice already from moving too fast past this exact step.

```bash
terraform apply -target=module.ecr
aws ecr describe-repositories --repository-names ztap-app --query 'repositories[0].repositoryUri' --output text
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
docker build -t ztap-app:local .
docker tag ztap-app:local <repository-uri>:latest
docker push <repository-uri>:latest
```

Everything else in one pass, Terraform works out the dependency order on its own from here:

```bash
terraform apply
```

Pull the Ollama model, same as local:

```bash
kubectl rollout status deployment/ollama -n inference --timeout=300s
kubectl exec -n inference deploy/ollama -- ollama pull qwen2.5:7b
```

## Verifying it worked

```bash
kubectl get nodes -L ztap.io/node-pool,ztap.io/gvisor
kubectl get namespaces
kubectl rollout status deployment/agent-sandbox -n tenant-a --timeout=120s
kubectl rollout status deployment/agent-sandbox -n tenant-b --timeout=120s
kubectl exec -it deploy/agent-sandbox -n tenant-a -- python -m agent.run_agent alice alice-pass "Read record rec-001"
kubectl exec -it deploy/agent-sandbox -n tenant-a -- python -m agent.run_agent alice alice-pass "Read record rec-002"
```

The first agent run should succeed, the second should be denied. Confirm the denial in the gateway's own logs, not the model's paraphrase of it:

```bash
kubectl logs -n gateway-ingress deploy/ztap-gateway --tail=20
```

## Building Silo from scratch

Silo has its own root config under `envs/silo/`, reusing every module Bridge already proved. The real differences: `vpc` gets `subnet_per_tenant = true` (a real per-tenant subnet and security group, the flag existed since the first version of the module but Bridge never used it), 4 node pools instead of 5 (no `shared-services`/`security-control`, Keycloak and the gateway each colocate directly on their own tenant's node pool), two full Keycloak realms and two gateways instead of one each, and a larger, tenant-scoped network policy set.

**Tear Bridge down completely before starting Silo**, `terraform destroy` in `envs/bridge`. `module.ecr` in both root configs creates a repository named `ztap-app`, and that name must be unique per account/region, if Bridge's repository still exists, Silo's `apply` will fail on that collision, loudly and clearly.

```bash
cd terraform/envs/silo
terraform init
terraform apply -target=module.vpc -target=module.eks_cluster -target=module.node_group -target=module.namespaces
terraform apply -target=module.cilium.helm_release.cilium
kubectl rollout restart daemonset/cilium -n kube-system
kubectl rollout status daemonset/cilium -n kube-system --timeout=120s
terraform apply -target=module.ecr
```

Build and push the image, same as Bridge, a fresh repository needs a fresh push even though it's the same image:

```bash
aws ecr describe-repositories --repository-names ztap-app --query 'repositories[0].repositoryUri' --output text
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
docker build -t ztap-app:local .
docker tag ztap-app:local <repository-uri>:latest
docker push <repository-uri>:latest
```

```bash
terraform apply
kubectl rollout status deployment/ollama -n inference --timeout=300s
kubectl exec -n inference deploy/ollama -- ollama pull qwen2.5:7b
```

`observability` is not part of Silo's root config yet, deliberately, see the ClusterIP entry under Known Errors below. Add it once that's resolved.

## Verifying Silo worked

Basic rollout and the same real-agent test as Bridge, once per tenant:

```bash
kubectl get nodes -L ztap.io/node-pool,ztap.io/gvisor
kubectl get namespaces
kubectl exec -it deploy/agent-sandbox -n tenant-a -- python -m agent.run_agent alice alice-pass "Read record rec-001"
kubectl exec -it deploy/agent-sandbox -n tenant-a -- python -m agent.run_agent alice alice-pass "Read record rec-002"
kubectl exec -it deploy/agent-sandbox -n tenant-b -- python -m agent.run_agent bob bob-pass "Read record rec-002"
```

Then the tests that are actually specific to Silo, proving the isolation is real, not just that both tenants work in isolation. Cross-tenant identity reuse, a token from tenant A's Keycloak presented to tenant B's gateway:

```bash
kubectl exec -it deploy/ztap-gateway -n enforcer-b -- env \
  ZTAP_KEYCLOAK_TOKEN_URL=http://keycloak.authorizer-a.svc.cluster.local:8080/realms/ztap-tenant-a/protocol/openid-connect/token \
  ZTAP_GATEWAY_URL=http://localhost:8001/invoke \
  python client/call_gateway.py alice alice-pass readRecord rec-001
```

Expect `403 Invalid issuer`, this comes from the identity split (separate realms, separate issuers) alone, before NetworkPolicy is even involved. Then the network-level test, proving `tenant-a`'s pod can't even open a TCP connection to `authorizer-b`'s pod regardless of what token it presents:

```bash
kubectl exec -it deploy/agent-sandbox -n tenant-a -- curl -m 5 http://keycloak.authorizer-b.svc.cluster.local:8080
```

Expect a timeout, not a connection refused, that specific distinction (silently dropped versus actively rejected) is what NetworkPolicy denial looks like.

## Known limitation: gVisor is currently disabled

`agent-sandbox` runs on plain `runc`, not `gvisor`, on both topologies right now (`gvisor_enabled = false` by default in the module). A real, working gVisor install mechanism was not reached within this deployment's timeframe. What was tried and ruled out, in case this gets picked back up:

- A privileged DaemonSet patching already-running nodes (`hostPath` chroot, edit `containerd` config, `systemctl restart containerd`). Multiple sub-issues fixed along the way (missing `mount_propagation` for `/run`, wrong `containerd` 2.x plugin path), but the runtime registration never reliably took effect even once every individual piece was confirmed correct.
- A boot-time install via a custom `aws_launch_template` `user_data` script, cleaner in principle (no live restart needed), and the gVisor binaries themselves installed correctly (after also discovering gVisor's release artifact format changed from individual binaries to a single tarball), but appending to `containerd`'s config before `nodeadm` has generated it appears to have interfered with `nodeadm`'s own bootstrap, causing `NodeCreationFailure` on both tenant node groups.

The `RuntimeClass` definition (`modules/gvisor/main.tf`) is confirmed correct, `handler = "runsc"`, matching `k8s/base/gvisor/runtimeclass.yaml`. `agent-sandbox` accepts a `gvisor_enabled` variable, so re-enabling it once a working install mechanism exists is a one-line change, not a rewrite.

## Known limitation: observability is not deployed

`kube-prometheus-stack`'s pre-install admission webhook job (`kube-prometheus-stack-admission-create`) fails with `BackoffLimitExceeded`. Root cause, confirmed directly: the pod times out reaching the Kubernetes API server's ClusterIP (`172.20.0.1:443`), not a chart bug. `kube-proxy` was confirmed healthy on every node, ruling that out. Leading theory: Cilium's masquerade rule decides what to masquerade based on whether traffic is leaving the VPC CIDR (`10.0.0.0/16`, auto-detected), but the Kubernetes Service CIDR (`172.20.0.0/16`) was never part of that range, so Service-destined traffic likely gets masqueraded by mistake, a packet meant for `kube-proxy`'s local DNAT interception, sent out as if leaving the cluster instead.

Not yet tried: setting `kubeProxyReplacement: true` in the `cilium` module's Helm values, letting Cilium own Service routing entirely via its own eBPF datapath instead of coexisting with `kube-proxy`'s `iptables` rules, which sidesteps the conflict rather than trying to carve out a masquerade exception for one specific CIDR.

This is scoped to `observability` alone. Keycloak, the gateway, Ollama, and the agent sandbox never call the Kubernetes API directly, only Prometheus and `kube-state-metrics` do, to discover and watch other pods, so the rest of the pipeline works and has been verified without it.

## Known errors and how to read them

**`ImagePullBackOff` / `ErrImagePull` right after a full `terraform apply`**: the image was never pushed before `gateway` or `agent-sandbox` tried to pull it. Apply `module.ecr` and push the image first, see the build sequences above. Has happened on both Bridge and Silo builds from moving too fast past this step, worth double-checking every time, not just the first.

**`kubectl` fails with a DNS resolution error against the cluster's API server hostname**, especially right after a `terraform destroy` and rebuild: the local kubeconfig is stale, pointing at the previous cluster's endpoint. Run `aws eks update-kubeconfig --name <cluster-name> --region us-east-1` to refresh it. Not a cluster health problem.

**`aws eks describe-nodegroup` (or similar) returns `ResourceNotFoundException` for a cluster you know exists**: check `aws configure list` for the CLI's default region. Every resource here is pinned to `us-east-1` in Terraform regardless of the CLI's own default, they can disagree silently.

**`Error: installation failed` / `execution error at (chart/templates/...)` on a `helm_release`**: almost always a Helm chart version mismatch, not a real config error, since no chart version was pinned or the pinned version is older than assumed. Check the exact error against that chart's current documentation before assuming the Terraform values are wrong, `set` block syntax and default behaviors (Cilium's masquerading, the OTel Collector's `image.repository`) have both changed versions this project has hit.

**`no runtime for "runsc" is configured`**: expected, see the gVisor limitation above, `gvisor_enabled` should be `false` everywhere right now.

**A `helm_release` reports a release already exists in a `failed` state, blocking a clean retry**: `helm list -n <namespace>`, then `helm uninstall <release> -n <namespace>` before reapplying, Terraform won't clear stale Helm state on its own.

**A pod's data or downloaded model disappears after any rebuild**: check whether its volume is `emptyDir` (Ollama's is, matching local). `emptyDir` doesn't survive a pod recreation, a full `terraform destroy` and rebuild means Ollama needs `ollama pull qwen2.5:7b` run again, it isn't a bug each time it happens.

## Tearing down

```bash
terraform destroy
```

Do this at the end of every work session for whichever topology is currently up.
