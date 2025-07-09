#!/usr/bin/env bash

# ensure we’re in the project dir
cd "$(dirname "$0")"

# (optional) activate your virtualenv, e.g.
# source venv/bin/activate

# start the FastAPI app
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
