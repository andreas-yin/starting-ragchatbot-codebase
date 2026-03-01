#!/usr/bin/env bash
set -euo pipefail

echo "Running Black format check..."
uv run black --check backend/

echo "All quality checks passed."
