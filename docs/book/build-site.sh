#!/usr/bin/env bash
# =============================================================================
# build-site.sh — Build the Docling-pipelines static documentation website
#
# Uses the local Podman image docker.io/antora/antora (no Node install needed).
#
# Usage:
#   cd docs/book
#   ./build-site.sh          # build into docs/book/site/
#   ./build-site.sh --serve  # build then serve on http://localhost:8080
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PAGES_DIR="$SCRIPT_DIR/modules/ROOT/pages"
CHAPTERS_DIR="$SCRIPT_DIR/chapters"
UI_BUNDLE="$SCRIPT_DIR/ui/ui-bundle.zip"
IMAGE="docker.io/antora/antora"
SERVE=false

for arg in "$@"; do
  [[ "$arg" == "--serve" ]] && SERVE=true
done

# ─── 1. Check container runtime (podman preferred, docker fallback) ──────────
if command -v podman &>/dev/null; then
  CONTAINER_CMD="podman"
elif command -v docker &>/dev/null; then
  CONTAINER_CMD="docker"
else
  echo "ERROR: Neither podman nor docker is found on PATH." >&2
  exit 1
fi

# SELinux relabel (:Z) is only needed for podman on SELinux systems
if [ "$CONTAINER_CMD" = "podman" ]; then
  VOLUME_OPTS=":Z"
else
  VOLUME_OPTS=""
fi

# ─── 2. Copy chapter .adoc files into Antora pages directory ─────────────────
echo "Syncing chapter files → $PAGES_DIR"
mkdir -p "$PAGES_DIR"
for f in "$CHAPTERS_DIR"/*.adoc; do
  cp "$f" "$PAGES_DIR/$(basename "$f")"
done

# ─── 3. Build the UI bundle (zip) ─────────────────────────────────────────────
echo "Building UI bundle → $UI_BUNDLE"
mkdir -p "$SCRIPT_DIR/ui"
"$SCRIPT_DIR/build-ui-bundle.sh"

# ─── 4. Run Antora inside the container (podman or docker) ───────────────────
# Mount repo root as /repo (git source) and docs/book as /antora (playbook + output)
echo "Running Antora via $CONTAINER_CMD ($IMAGE)..."
"$CONTAINER_CMD" run --rm \
  -v "${REPO_ROOT}:/repo${VOLUME_OPTS}" \
  -v "${SCRIPT_DIR}:/antora${VOLUME_OPTS}" \
  -w /antora \
  "$IMAGE" \
  /antora/antora-playbook.yml

echo ""
echo "Site built at: $SCRIPT_DIR/site/index.html"

# ─── 5. Optional: serve with Python (no extra installs) ──────────────────────
if $SERVE; then
  echo "Serving on http://localhost:8080 — press Ctrl+C to stop"
  python3 -m http.server 8080 --directory "$SCRIPT_DIR/site"
fi
