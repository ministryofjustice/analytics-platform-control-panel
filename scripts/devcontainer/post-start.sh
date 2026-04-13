#!/usr/bin/env bash

# Run pre-commit
uv run --locked pre-commit install
uv run --locked pre-commit install --hook-type commit-msg
