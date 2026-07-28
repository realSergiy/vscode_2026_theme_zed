#!/usr/bin/env python3
# Copyright (c) 2026 Sergiy Yeskov
"""Generate Zed themes from VS Code's built-in 2026 themes.

Reads the vendored VS Code sources in vscode-src/ (refresh them with
fetch_vscode_sources.py) and the declarative key mappings in mapping.json,
flattens each include chain (dark_vs -> dark_plus -> dark_modern ->
2026-dark and the light equivalent), resolves effective TextMate token
colors the way VS Code does (most specific scope selector wins, ties go to
the later rule), and maps the result onto Zed theme keys - including the
syntax keys Zed's LSP semantic token rules resolve against.

Usage: python3 build.py [path-to-vscode-src-dir]
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, TypedDict

logger = logging.getLogger(__name__)

TokenRule = tuple[str, dict[str, str]]


class ThemeMapping(TypedDict):
    chains: dict[str, list[str]]
    ui: dict[str, list[str]]
    mode_literals: dict[str, dict[str, str]]
    shared_literals: dict[str, str]
    ansi_zed_names: dict[str, str]
    collaborator_players: list[dict[str, str]]
    syntax: dict[str, list[str]]
    syntax_extras: dict[str, dict[str, str | int]]


REPO_DIR = Path(__file__).parent
VSCODE_SRC_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_DIR / "vscode-src"
VSCODE_THEMES_DIR = VSCODE_SRC_DIR / "themes"
ANSI_REGISTRY = VSCODE_SRC_DIR / "terminalColorRegistry.ts"
EDITOR_COLOR_REGISTRY = VSCODE_SRC_DIR / "editorColorRegistry.ts"
OUTPUT_DIR = REPO_DIR / "themes"
MAPPING: ThemeMapping = json.loads((REPO_DIR / "mapping.json").read_text())

BRACKET_ACCENT_KEYS = [f"editorBracketHighlight.foreground{n}" for n in range(1, 7)]
TRANSPARENT = "#00000000"


def load_theme(name: str) -> dict[str, Any]:
    text = (VSCODE_THEMES_DIR / name).read_text()
    text = re.sub(
        r'"(?:[^"\\]|\\.)*"|//[^\n]*|/\*.*?\*/',
        lambda m: m.group(0) if m.group(0).startswith('"') else "",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return json.loads(text)


def flatten(chain: list[str]) -> tuple[dict[str, str], list[TokenRule]]:
    colors: dict[str, str] = {}
    rules: list[TokenRule] = []
    for name in chain:
        theme = load_theme(name)
        colors.update(theme.get("colors", {}))
        for rule in theme.get("tokenColors", []):
            scopes = rule["scope"] if isinstance(rule["scope"], list) else [s.strip() for s in rule["scope"].split(",")]
            rules.extend((scope, rule["settings"]) for scope in scopes if " " not in scope)
    return colors, rules


def resolve_foreground(rules: list[TokenRule], token_scope: str) -> str | None:
    best: tuple[tuple[int, int], str] | None = None
    for order, (selector, settings) in enumerate(rules):
        if "foreground" not in settings:
            continue
        if token_scope == selector or token_scope.startswith(selector + "."):
            rank = (selector.count("."), order)
            if best is None or rank >= best[0]:
                best = (rank, settings["foreground"])
    return best[1] if best else None


def parse_ansi_palette(mode: str) -> dict[str, str]:
    registry = ANSI_REGISTRY.read_text()
    color_map = registry[registry.index("ansiColorMap") :]
    ansi_zed_names = MAPPING["ansi_zed_names"]
    palette: dict[str, str] = {}
    ansi_entry = re.compile(r"'terminal\.(ansi\w+)':\s*\{.*?light:\s*'(#\w+)',\s*dark:\s*'(#\w+)'", re.DOTALL)
    for match in ansi_entry.finditer(color_map):
        registry_name, light, dark = match.groups()
        palette[f"terminal.ansi.{ansi_zed_names[registry_name]}"] = light if mode == "light" else dark
    if len(palette) != len(ansi_zed_names):
        mismatch = f"expected {len(ansi_zed_names)} ANSI colors, parsed {len(palette)}"
        raise ValueError(mismatch)
    return palette


def parse_bracket_accent_defaults(mode: str) -> dict[str, str]:
    registry = EDITOR_COLOR_REGISTRY.read_text()
    defaults: dict[str, str] = {}
    for match in re.finditer(
        r"registerColor\('(editorBracketHighlight\.foreground\d)',\s*\{\s*dark:\s*'(#\w+)',\s*light:\s*'(#\w+)'",
        registry,
    ):
        key, dark, light = match.groups()
        defaults[key] = light if mode == "light" else dark
    return defaults


def build_accents(mode: str, colors: dict[str, str]) -> list[str]:
    defaults = parse_bracket_accent_defaults(mode)
    per_level = (colors.get(key, defaults.get(key)) for key in BRACKET_ACCENT_KEYS)
    return [color for color in per_level if color and not color.upper().startswith(TRANSPARENT)]


def build_style(mode: str) -> dict[str, object]:
    colors, rules = flatten(MAPPING["chains"][mode])

    def ui(vscode_keys: list[str]) -> str | None:
        for key in vscode_keys:
            if key in colors:
                return colors[key]
        return None

    style: dict[str, object] = {"background.appearance": "opaque", "accents": build_accents(mode, colors)}
    for zed_key, vscode_keys in MAPPING["ui"].items():
        style[zed_key] = ui(vscode_keys)
    style.update(MAPPING["shared_literals"])
    style.update(MAPPING["mode_literals"][mode])
    style.update(parse_ansi_palette(mode))

    style["players"] = [
        {
            "cursor": ui(["editorCursor.foreground"]),
            "background": None,
            "selection": ui(["editor.selectionBackground"]),
        },
        *MAPPING["collaborator_players"],
    ]

    editor_foreground = colors["editor.foreground"]
    syntax: dict[str, dict[str, str | int | None]] = {}
    for zed_key, scopes in MAPPING["syntax"].items():
        color = next(filter(None, (resolve_foreground(rules, s) for s in scopes)), editor_foreground)
        entry: dict[str, str | int | None] = {
            "color": color,
            "background_color": None,
            "font_style": None,
            "font_weight": None,
        }
        entry.update(MAPPING["syntax_extras"].get(zed_key, {}))
        syntax[zed_key] = entry
    style["syntax"] = syntax
    return style


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    themes = [
        {"name": label, "appearance": mode, "style": build_style(mode)}
        for mode, label in (("dark", "VSCode 2026 Dark"), ("light", "VSCode 2026 Light"))
    ]
    output = {
        "$schema": "https://zed.dev/schema/themes/v0.2.0.json",
        "name": "VSCode 2026",
        "author": "Sergiy Yeskov <sergiy.yeskov@gmail.com>",
        "themes": themes,
    }
    OUTPUT_DIR.mkdir(exist_ok=True)
    target = OUTPUT_DIR / "vscode-2026.json"
    target.write_text(json.dumps(output, indent=2) + "\n")
    logger.info("wrote %s (%d themes)", target, len(themes))


if __name__ == "__main__":
    main()
