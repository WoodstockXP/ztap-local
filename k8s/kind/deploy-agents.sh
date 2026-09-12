#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
kubectl apply -f k8s/base/network-policy/allow-inference-internet.yaml
kubectl apply -f k8s/base/network-policy/allow-agent-authorizer.yaml
kubectl apply -f k8s/base/inference/ollama.yaml
kubectl rollout status deployment/ollama -n inference --timeout=300s
kubectl exec -n inference deploy/ollama -- ollama pull qwen2.5:7b
docker build -t ztap-app:local .
kind load docker-image ztap-app:local --name ztap
kubectl apply -f k8s/base/agent/agent-sandbox-a.yaml
kubectl apply -f k8s/base/agent/agent-sandbox-b.yaml
kubectl rollout status deployment/agent-sandbox -n tenant-a --timeout=60s
kubectl rollout status deployment/agent-sandbox -n tenant-b --timeout=60s
echo "agent sandboxes and ollama (with qwen2.5:7b pulled) are up."