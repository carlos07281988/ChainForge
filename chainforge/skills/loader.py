# Copyright 2024 ChainForge Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Skill loader — parse SKILL.md files and directories.

SKILL.md format (Codex-compatible):

    ---
    name: my-skill
    description: Does something useful
    tags: [tag1, tag2]
    ---

    ## Instructions

    Markdown instructions here...
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from chainforge.skills.base import Skill, SkillSpec


def load_skill_from_file(path: str) -> Skill:
    """Load a single skill from a SKILL.md file.

    Supports both YAML front matter and a flat format where
    the filename provides the name and the content provides instructions.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Skill file not found: {path}")

    content = p.read_text(encoding="utf-8")

    # Try to parse YAML front matter
    metadata: dict[str, Any] = {}
    instructions = content

    front_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
    if front_match:
        yaml_block = front_match.group(1)
        instructions = front_match.group(2).strip()
        metadata = _parse_front_matter(yaml_block)

    name = metadata.get("name") or _name_from_path(p)
    description = metadata.get("description") or ""
    tags = metadata.get("tags") or metadata.get("metadata", {}).get("tags", [])

    spec = SkillSpec(
        name=name,
        description=description,
        tags=tags if isinstance(tags, list) else [tags],
        version=metadata.get("version", "1.0.0"),
    )

    return Skill(spec=spec, instructions=instructions)


def load_skills_from_directory(path: str) -> list[Skill]:
    """Discover and load all skills from a directory tree.

    Scans for SKILL.md files recursively.
    """
    base = Path(path)
    if not base.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")

    skills: list[Skill] = []
    for root, dirs, files in os.walk(base):
        for f in files:
            if f == "SKILL.md":
                try:
                    skill = load_skill_from_file(os.path.join(root, f))
                    skills.append(skill)
                except Exception as e:
                    # Silently skip malformed skills; log at DEBUG level
                    import logging
                    logging.getLogger("chainforge.skills").debug(
                        "Skipping %s: %s", os.path.join(root, f), e
                    )
    return skills


def _name_from_path(path: Path) -> str:
    """Derive a skill name from the containing directory or filename."""
    parent = path.parent
    if parent.name and parent.name != ".":
        return parent.name
    return path.stem  # fallback: filename without extension


def _parse_front_matter(text: str) -> dict[str, Any]:
    """Parse simple key-value front matter (no YAML dependency)."""
    result: dict[str, Any] = {}
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            # Handle tags: list items or "kebab-case" tags
            if key == "tags":
                if value.startswith("[") and value.endswith("]"):
                    result[key] = [t.strip().strip('"').strip("'") for t in value[1:-1].split(",")]
                else:
                    result[key] = value
            elif key == "metadata":
                result[key] = {"tags": result.get("tags", [])}
            else:
                result[key] = value
    return result
