"""Parse config files (JSON, YAML, dotfiles) into indexable documents."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 100_000  # 100KB

# Config file names we recognise
CONFIG_NAMES = {
    "package.json", "tsconfig.json", "jest.config.js", "jest.config.ts",
    "babel.config.js", "metro.config.js", ".eslintrc.json", "eslint.config.js",
    ".prettierrc", ".prettierrc.json", ".editorconfig",
    "app.json", "eas.json", ".detoxrc.js",
    "Brewfile", "Gemfile", "Podfile",
    ".gitconfig", ".gitignore", ".gitignore_global",
    ".zshrc", ".zprofile", ".bashrc", ".bash_profile",
    "config.yaml", "config.yml",
    "docker-compose.yml", "docker-compose.yaml", "Dockerfile",
    "pyproject.toml", "requirements.txt", "setup.cfg",
}

CONFIG_EXTENSIONS = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"}


def _is_config_file(path: Path) -> bool:
    """Check if a file is a recognised config file."""
    if path.name in CONFIG_NAMES:
        return True
    if path.suffix in CONFIG_EXTENSIONS:
        return True
    # Match hidden config files, but exclude known non-config dotfiles
    _skip_dotfiles = {".DS_Store", ".localized", ".gitkeep", ".keep", ".Spotlight-V100", ".env"}
    if path.name.startswith(".") and path.name not in _skip_dotfiles and path.suffix in ("", ".json", ".yaml", ".yml"):
        return True
    if path.name == ".env.example":
        return True
    return False


def _extract_config_summary(path: Path, content: str) -> str:
    """Extract non-default, meaningful settings from config content."""
    name = path.name

    if name == "package.json":
        try:
            pkg = json.loads(content)
            parts = [f"Package: {pkg.get('name', 'unknown')}"]
            if pkg.get("version"):
                parts.append(f"Version: {pkg['version']}")
            if pkg.get("scripts"):
                parts.append(f"Scripts: {', '.join(pkg['scripts'].keys())}")
            if pkg.get("dependencies"):
                deps = list(pkg["dependencies"].keys())
                parts.append(f"Dependencies ({len(deps)}): {', '.join(deps[:20])}")
            if pkg.get("devDependencies"):
                devdeps = list(pkg["devDependencies"].keys())
                parts.append(f"Dev dependencies ({len(devdeps)}): {', '.join(devdeps[:15])}")
            return "\n".join(parts)
        except json.JSONDecodeError:
            pass

    # Strip comment-only lines for shell/yaml configs
    lines = []
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("//"):
            lines.append(line)

    return "\n".join(lines[:100])


def parse_config(path: str | Path) -> dict[str, Any] | None:
    """Parse a config file into an indexable document.

    Returns a dict with keys: text, metadata, needs_summary, identifier.
    Returns None if the file should be skipped.
    """
    path = Path(path)

    if not path.exists() or not path.is_file():
        return None

    if not _is_config_file(path):
        return None

    try:
        size = path.stat().st_size
        if size > MAX_FILE_SIZE or size == 0:
            return None
    except OSError:
        return None

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        logger.exception("Failed to read %s", path)
        return None

    summary = _extract_config_summary(path, content)
    if not summary.strip():
        return None

    text = f"Config: {path.name}\n\n{summary}"

    # Determine project
    project = ""
    home = Path.home()
    try:
        rel = path.relative_to(home / "Developer")
        project = rel.parts[0] if rel.parts else ""
    except ValueError:
        pass

    metadata = {
        "file_path": str(path),
        "doc_type": "config",
        "project": project,
        "source_type": "docs",
    }

    return {
        "text": text,
        "metadata": metadata,
        "needs_summary": False,  # Configs are typically small enough
        "identifier": str(path),
    }
