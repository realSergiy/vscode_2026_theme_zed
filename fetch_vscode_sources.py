#!/usr/bin/env python3
# Copyright (c) 2026 Sergiy Yeskov
"""Vendor the upstream VS Code files build.py derives the themes from.

Downloads the theme-defaults JSONs and the color registries from
microsoft/vscode at a pinned tag into vscode-src/, and records the tag in
vscode-src/VERSION.

Usage: python3 fetch_vscode_sources.py [vscode-tag]
"""

import logging
import sys
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_TAG = "1.130.0"
TARGET_DIR = Path(__file__).parent / "vscode-src"
THEME_FILES = [
    "dark_vs.json",
    "dark_plus.json",
    "dark_modern.json",
    "2026-dark.json",
    "light_vs.json",
    "light_plus.json",
    "light_modern.json",
    "2026-light.json",
]
ANSI_REGISTRY_PATH = "src/vs/workbench/contrib/terminal/common/terminalColorRegistry.ts"
EDITOR_COLOR_REGISTRY_PATH = "src/vs/editor/common/core/editorColorRegistry.ts"


def fetch(tag: str, repo_path: str, target: Path) -> None:
    url = f"https://raw.githubusercontent.com/microsoft/vscode/{tag}/{repo_path}"
    with urllib.request.urlopen(url) as response:
        target.write_bytes(response.read())
    logger.info("fetched %s", repo_path)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    tag = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TAG
    themes_dir = TARGET_DIR / "themes"
    themes_dir.mkdir(parents=True, exist_ok=True)
    for name in THEME_FILES:
        fetch(tag, f"extensions/theme-defaults/themes/{name}", themes_dir / name)
    fetch(tag, ANSI_REGISTRY_PATH, TARGET_DIR / "terminalColorRegistry.ts")
    fetch(tag, EDITOR_COLOR_REGISTRY_PATH, TARGET_DIR / "editorColorRegistry.ts")
    (TARGET_DIR / "VERSION").write_text(tag + "\n")
    logger.info("pinned to microsoft/vscode %s", tag)


if __name__ == "__main__":
    main()
