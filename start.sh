#!/usr/bin/env bash

# ensure we’re in the project dir
cd "$(dirname "$0")"

# (optional) activate your virtualenv, e.g.
# source venv/bin/activate

# start the main application
uv run main.py
