#!/usr/bin/env bash
# =============================================================================
# build-pdf.sh — Generate docling-pipelines-guide.pdf from all book chapters
#
# Uses docker.io/asciidoctor/docker-asciidoctor — no Ruby or Node install needed.
# Podman is preferred; docker is used as a fallback if podman is not found.
#
# Usage:
#   cd docs/book
#   ./build-pdf.sh              # → docling-pipelines-guide.pdf
#   ./build-pdf.sh --open       # build then open the PDF
#   ./build-pdf.sh --out /tmp/my.pdf   # custom output path
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTER_DOC="toc.adoc"                        # relative to SCRIPT_DIR
OUTPUT_FILE="$SCRIPT_DIR/docling-pipelines-guide.pdf"
IMAGE="docker.io/asciidoctor/docker-asciidoctor"
OPEN_PDF=false

# ── Parse arguments ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --open) OPEN_PDF=true ;;
    --out)  OUTPUT_FILE="$2"; shift ;;
    -h|--help)
      sed -n '2,12p' "$0" | sed 's/^# \?//'
      exit 0 ;;
  esac
  shift
done

# ── Container runtime (podman preferred, docker fallback) ────────────────────
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

OUT_NAME="$(basename "$OUTPUT_FILE")"

echo "Image:  $IMAGE"
echo "Output: $OUTPUT_FILE"
echo ""

# ── Run asciidoctor-pdf inside the container ─────────────────────────────────
"$CONTAINER_CMD" run --rm \
  -v "${SCRIPT_DIR}:/documents${VOLUME_OPTS}" \
  -w /documents \
  "$IMAGE" \
  asciidoctor-pdf \
    -a doctype=book \
    -a toc \
    -a toclevels=3 \
    -a sectnums \
    -a "chapter-signifier=Chapter" \
    -a "appendix-caption=Appendix" \
    -a source-highlighter=rouge \
    -a rouge-style=github \
    -a icons=font \
    -a pdf-themesdir=/documents \
    -a pdf-theme=docling-pipelines \
    --base-dir /documents \
    --out-file "/documents/${OUT_NAME}" \
    "$MASTER_DOC"

# ── Result ────────────────────────────────────────────────────────────────────
if [[ -f "$OUTPUT_FILE" ]]; then
  SIZE=$(du -sh "$OUTPUT_FILE" | cut -f1)
  echo ""
  echo "PDF generated: $OUTPUT_FILE  ($SIZE)"
  if $OPEN_PDF; then
    case "$(uname -s)" in
      Darwin) open "$OUTPUT_FILE" ;;
      Linux)  xdg-open "$OUTPUT_FILE" 2>/dev/null || echo "Open: $OUTPUT_FILE" ;;
    esac
  fi
else
  echo "ERROR: PDF was not created." >&2
  exit 1
fi
