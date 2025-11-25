#!/usr/bin/env bash

sudo apt update && sudo apt install -y git-secrets
git secrets --install
git secrets --register-aws
