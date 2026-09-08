#!/bin/bash
set -e

# uv installs to ~/.local/bin, which a non-interactive shell does not pick up.
export PATH="$HOME/.local/bin:$PATH"

uv sync
