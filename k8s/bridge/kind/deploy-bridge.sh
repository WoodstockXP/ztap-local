#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
kind get clusters | grep -qx ztap-bridge || kind create cluster --config k8s/bridge/kind/kind-ztap-bridge.yaml
docker build -t ztap-app:local .
kind load docker-image ztap-app:local --name ztap-bridge
kubectl apply -f k8s/bridge/base/namespaces/bridge-namespaces.yaml
kubectl create configmap ztap-realm --from-file=keycloak/ztap-realm.json -n authorizer --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f k8s/bridge/base/keycloak/authorizer.yaml
kubectl apply -f k8s/bridge/base/gateway/gateway-ingress.yaml
kubectl rollout status deployment/keycloak -n authorizer --timeout=180s
kubectl rollout status deployment/ztap-gateway -n gateway-ingress --timeout=60s
echo "bridge stack up: keycloak.authorizer, ztap-gateway.gateway-ingress"