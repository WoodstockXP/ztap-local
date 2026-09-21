# ZTAP Terraform (AWS)

Deploys the Bridge and Silo topologies to real EKS infrastructure, mirroring `k8s/` and `k8s/bridge/` locally. Each topology has its own root config under `envs/`, calling the same shared modules under `modules/` with different parameters, the same "same image, differ in manifests" principle the kind setup already follows.

## Prerequisites

- AWS CLI configured with working credentials: `aws sts get-caller-identity` should return your account, not an error.
- `aws configure set region us-east-1`, everything here is pinned to that region.
- Terraform installed, provider versions are pinned per-module in each `versions.tf`.
- Docker, for building and pushing the `ztap-app` image to ECR.
- `kubectl`, for verification steps after each stage.

## Account caveats, read before starting

This has been built and tested against a personal AWS account on the **Free Plan**, which blocks On-Demand instances above Free Tier eligible types entirely, not a quota issue, an account-level restriction. `node_capacity_type` defaults to `SPOT` in `envs/bridge/variables.tf` to route around this. If your account is upgraded to a paid plan, you can override with `-var="node_capacity_type=ON_DEMAND"` for a more stable eval run, since Spot instances can be reclaimed with two minutes' notice.

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

Build and push the application image before the modules that need it (`gateway`, `agent-sandbox`):

```bash
aws ecr describe-repositories --repository-names ztap-app --query 'repositories[0].repositoryUri' --output text
```

If that fails because the repository doesn't exist yet, apply `module.ecr` first, then retry.

```bash
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

## Known limitation: gVisor is currently disabled

`agent-sandbox` runs on plain `runc`, not `gvisor`, on both topologies right now (`gvisor_enabled = false` by default in the module). A real, working gVisor install mechanism was not reached within this deployment's timeframe. What was tried and ruled out, in case this gets picked back up:

- A privileged DaemonSet patching already-running nodes (`hostPath` chroot, edit `containerd` config, `systemctl restart containerd`). Multiple sub-issues fixed along the way (missing `mount_propagation` for `/run`, wrong `containerd` 2.x plugin path), but the runtime registration never reliably took effect even once every individual piece was confirmed correct.
- A boot-time install via a custom `aws_launch_template` `user_data` script, cleaner in principle (no live restart needed), and the gVisor binaries themselves installed correctly (after also discovering gVisor's release artifact format changed from individual binaries to a single tarball), but appending to `containerd`'s config before `nodeadm` has generated it appears to have interfered with `nodeadm`'s own bootstrap, causing `NodeCreationFailure` on both tenant node groups.

The `RuntimeClass` definition (`modules/gvisor/main.tf`) is confirmed correct, `handler = "runsc"`, matching `k8s/base/gvisor/runtimeclass.yaml`. `agent-sandbox` accepts a `gvisor_enabled` variable, so re-enabling it once a working install mechanism exists is a one-line change, not a rewrite.

## Tearing down

```bash
terraform destroy
```

Do this at the end of every work session.
