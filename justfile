# BASELINE
set shell := ["bash", "-euo", "pipefail", "-c"]

alias i := install
alias tc := typecheck
alias l := lint
alias c := check
alias u := upgrade

# List available recipes.
default:
    @just --list

# Install the uv environment.
install:
    uv sync

# Type-check with pyrefly.
typecheck:
    uv run pyrefly check

# Lint and format with autofix: rumdl for markdown, ruff for python.
lint:
    uv run rumdl check --fix --no-cache
    uv run rumdl fmt
    uv run ruff check --fix
    uv run ruff format

# Full gate: sync, typecheck, lint, build — autofix throughout.
check: install typecheck lint build

# Upgrade deps: uv lock --upgrade + uv-bump raise >= floors, then reinstall.
upgrade:
    uv lock --upgrade
    uvx uv-bump -v
    uv sync

# CUSTOM

# Vendor pinned VS Code sources into vscode-src/ (theme JSONs + color registries).
fetch tag='':
    uv run fetch_vscode_sources.py {{ tag }}

# Regenerate themes/vscode-2026.json from vscode-src/ via mapping.json.
build:
    uv run build.py

# Sync the environment, fetch VS Code sources, and rebuild the themes in one go.
generate tag='': install (fetch tag) build
