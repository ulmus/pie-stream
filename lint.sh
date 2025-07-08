#!/bin/bash
# Lint script for pie-stream project

echo "Running ruff linter..."
uv run ruff check .

if [ $? -eq 0 ]; then
    echo "✅ No linting errors found!"
    echo "Running ruff formatter..."
    uv run ruff format .
    echo "✅ Code formatted successfully!"
else
    echo "❌ Linting errors found. Please fix them."
    exit 1
fi
