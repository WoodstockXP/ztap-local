#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
kubectl apply -f k8s/base/gvisor/runtimeclass.yaml
kubectl apply -f k8s/bridge/base/network-policy/default-deny-all.yaml
kubectl apply -f k8s/bridge/base/network-policy/allow-dns.yaml
kubectl apply -f k8s/bridge/base/network-policy/allow-agent-shared-services.yaml
kubectl apply -f k8s/bridge/base/network-policy/allow-inference-internet.yaml
kubectl apply -f k8s/bridge/base/inference/ollama.yaml
kubectl rollout status deployment/ollama -n inference --timeout=60s
kubectl exec -n inference deploy/ollama -- ollama pull qwen2.5:7b
docker build -t ztap-app:local .
kind load docker-image ztap-app:local --name ztap-bridge
kubectl apply -f k8s/bridge/base/agent/agent-sandbox-a.yaml
kubectl apply -f k8s/bridge/base/agent/agent-sandbox-b.yaml
kubectl rollout status deployment/agent-sandbox -n tenant-a --timeout=60s
kubectl rollout status deployment/agent-sandbox -n tenant-b --timeout=60s
echo "bridge agent sandboxes and ollama (with qwen2.5:7b pulled) are up."