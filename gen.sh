#!/usr/bin/env bash
# Generate pretty PNG + SVG from a .dot file using the dark theme renderer.
#
# Usage:
#   ./gen.sh                  # renders example.dot -> example.svg + example.png
#   ./gen.sh myflow.dot       # renders myflow.dot  -> myflow.svg  + myflow.png
#   ./gen.sh a.dot output     # renders a.dot       -> output.svg  + output.png

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Check dependencies
if ! command -v dot &>/dev/null; then
    echo "Error: graphviz not installed. Install with:"
    echo "  brew install graphviz     # macOS"
    echo "  apt install graphviz      # Linux"
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    echo "Error: python3 not found"
    exit 1
fi

python3 "$SCRIPT_DIR/render.py" "$@"
