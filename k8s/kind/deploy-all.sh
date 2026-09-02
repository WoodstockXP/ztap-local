#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
./deploy-tenant-a.sh
./deploy-tenant-b.sh