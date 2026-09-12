#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
if ! docker image inspect ztap-node-gvisor:local > /dev/null 2>&1; then
  k8s/kind/build-gvisor-node-image.sh kindest/node:v1.37.0
fi
if ! kind get clusters | grep -qx ztap-bridge; then
  kind create cluster --config k8s/bridge/kind/kind-ztap-bridge.yaml
fi
k8s/kind/install-cilium.sh
k8s/bridge/kind/deploy-bridge.sh
kubectl apply -f k8s/base/gvisor/runtimeclass.yaml
k8s/bridge/kind/deploy-bridge-agents.sh
echo "Bridge fully up: shared stack, gVisor RuntimeClass, Ollama, agent sandboxes."
echo "Verify with: eval/run_matrix.sh (or a manual spot-check per k8s/bridge/README.md steps 2-3 if you want to see the isolation guarantees directly)."
