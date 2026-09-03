#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
BASE_IMAGE=$(docker inspect ztap-worker3 --format '{{.Config.Image}}' 2>/dev/null || true)
if [ -z "$BASE_IMAGE" ]; then
  BASE_IMAGE="${1:?no running ztap cluster found to auto-detect the base image; pass it explicitly, e.g. ./build-gvisor-node-image.sh kindest/node:v1.37.0}"
fi
docker build --build-arg BASE_IMAGE="$BASE_IMAGE" -t ztap-node-gvisor:local -f gvisor-node.Dockerfile .
echo "built ztap-node-gvisor:local from $BASE_IMAGE"
