#!/usr/bin/env bash

# Run pre-commit
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg
