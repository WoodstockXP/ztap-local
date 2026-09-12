#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
if ! kind get clusters | grep -qx ztap; then
  k8s/kind/build-gvisor-node-image.sh kindest/node:v1.37.0
  kind create cluster --config k8s/kind/kind-ztap.yaml
fi
k8s/kind/install-cilium.sh
k8s/kind/deploy-all.sh
kubectl apply -f k8s/base/network-policy/default-deny-all.yaml
kubectl apply -f k8s/base/network-policy/allow-dns.yaml
kubectl apply -f k8s/base/network-policy/allow-enforcer-authorizer.yaml
kubectl apply -f k8s/base/network-policy/allow-agent-inference.yaml
kubectl apply -f k8s/base/network-policy/allow-agent-authorizer.yaml
kubectl apply -f k8s/base/network-policy/allow-inference-internet.yaml
kubectl apply -f k8s/base/gvisor/runtimeclass.yaml
k8s/kind/deploy-agents.sh
echo "Silo fully up: both tenants, NetworkPolicy, gVisor RuntimeClass, Ollama, agent sandboxes."
echo "Verify with: eval/run_matrix.sh (or a manual spot-check per k8s/README.md steps 3-4 if you want to see the isolation guarantees directly)."
