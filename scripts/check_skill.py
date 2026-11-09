#!/usr/bin/env python3
"""Check this repository's skill layout and links, not interview quality."""

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1] / "skills" / "interview-questions"


def check() -> list[str]:
    errors = []
    entry = ROOT / "SKILL.md"
    content = entry.read_text(encoding="utf-8")
    frontmatter = re.match(r"\A---\n(.*?)\n---\n", content, re.S)
    if not frontmatter:
        errors.append("SKILL.md must start with YAML frontmatter")
    else:
        header = frontmatter.group(1)
        if not re.search(r"^name: interview-questions$", header, re.M):
            errors.append("Skill name must match its directory")
        if not re.search(r'^description: ".+"$', header, re.M):
            errors.append("Missing quoted description")
        if not re.search(r'^  version: "\d+\.\d+\.\d+"$', header, re.M):
            errors.append("Missing semantic version")

    reached = set()
    pending = [entry]
    while pending:
        path = pending.pop()
        if path in reached:
            continue
        reached.add(path)
        text = path.read_text(encoding="utf-8")
        if re.search(r"\[TODO:", text):
            errors.append(f"Unfinished scaffold: {path.relative_to(ROOT)}")
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I) or target.startswith("#"):
                continue
            filename, _, anchor = target.partition("#")
            resolved = (path.parent / filename).resolve()
            if not resolved.is_relative_to(ROOT.resolve()) or not resolved.is_file():
                errors.append(f"Broken/outside reference in {path.name}: {target}")
                continue
            if anchor:
                headings = {
                    re.sub(r"\s+", "-", heading.strip().lower())
                    for heading in re.findall(r"^#+ (.+)$", resolved.read_text(encoding="utf-8"), re.M)
                }
                if anchor not in headings:
                    errors.append(f"Unknown heading in {path.name}: {target}")
            if resolved.suffix == ".md":
                pending.append(resolved)
    for path in ROOT.rglob("*.md"):
        if path not in reached:
            errors.append(f"Unreachable instructions: {path.relative_to(ROOT)}")
    metadata = (ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
    match = re.search(r'^  default_prompt: (".*")$', metadata, re.M)
    if not match or "$interview-questions" not in json.loads(match.group(1)):
        errors.append("UI default prompt must invoke $interview-questions")
    match = re.search(r'^  short_description: (".*")$', metadata, re.M)
    if not match or not 25 <= len(json.loads(match.group(1))) <= 64:
        errors.append("UI description must be 25-64 characters")
    if "allow_implicit_invocation: false" in metadata:
        errors.append("Keep normal skill discovery enabled")
    return errors


if __name__ == "__main__":
    try:
        errors = check()
    except (OSError, ValueError) as exc:
        errors = [str(exc)]
    for error in errors:
        print(error, file=sys.stderr)
    if not errors:
        print("PASS: layout, metadata and local references (semantic quality not assessed)")
    raise SystemExit(bool(errors))
