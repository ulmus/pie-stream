#!/bin/bash
# Lint script for pie-stream project

echo "Running flake8 linter..."
.venv/bin/python -m flake8 .

if [ $? -eq 0 ]; then
    echo "✅ No linting errors found!"
else
    echo "❌ Linting errors found. Please fix them."
    exit 1
fi
