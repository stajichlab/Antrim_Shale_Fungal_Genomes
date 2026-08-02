#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Build (and optionally push) the bfd-chat Docker image.
# Run from the Exophiala/ project root.
#
# Usage:
#   ./dashboard/k8s/build.sh           # build only
#   ./dashboard/k8s/build.sh --push    # build + docker push
#   IMAGE=<custom> ./dashboard/k8s/build.sh --push  # custom image name
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
IMAGE="${IMAGE:-ghcr.io/nrp-ai/bfd-chat:latest}"
PUSH=false

for arg in "$@"; do
  case $arg in
    --push) PUSH=true ;;
    --help|-h)
      echo "Usage: $0 [--push] [--help]"
      echo "  --push   push the image after building"
      echo "  IMAGE=   set custom image (default: ghcr.io/nrp-ai/bfd-chat:latest)"
      exit 0
      ;;
  esac
done

echo "=== Building bfd-chat ==="
echo "  Context:  $PROJECT_ROOT"
echo "  Dockerfile: $PROJECT_ROOT/dashboard/Dockerfile"
echo "  Image:    $IMAGE"

# Build from project root so the COPY paths in the Dockerfile resolve correctly.
# The Dockerfile copies dashboard/lib/ and dashboard/chat/ into the image.
docker build \
  --tag "$IMAGE" \
  --file "$PROJECT_ROOT/dashboard/Dockerfile" \
  "$PROJECT_ROOT"

echo "=== Build complete: $IMAGE ==="

if $PUSH; then
  echo "=== Pushing $IMAGE ==="
  docker push "$IMAGE"
  echo "=== Push complete ==="
fi
