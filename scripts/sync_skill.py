#!/usr/bin/env python3
"""Install/update this skill, detecting local edits and verifying exact contents."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile

SKILL_NAME = "interview-questions"
SOURCE_ID = "super1888/Interview-Questions:skills/interview-questions"
SOURCE = Path(__file__).resolve().parents[1] / "skills" / SKILL_NAME


class SyncError(RuntimeError):
    pass


def inventory(root: Path) -> dict[str, str]:
    if root.is_symlink() or not root.is_dir():
        raise SyncError(f"Expected an ordinary skill directory: {root}")
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise SyncError(f"Symbolic links are not supported: {path}")
        mode = path.stat().st_mode
        if stat.S_ISREG(mode):
            files[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
        elif not stat.S_ISDIR(mode):
            raise SyncError(f"Unsupported file type: {path}")
    if "SKILL.md" not in files:
        raise SyncError(f"SKILL.md missing: {root}")
    return files


def digest(files: dict[str, str]) -> str:
    return hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def read_state(path: Path) -> dict | None:
    if path.is_symlink():
        raise SyncError(f"Installation state cannot be a symbolic link: {path}")
    if not path.exists():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise SyncError(f"Cannot read installation state: {path}") from exc
    if (
        not isinstance(state, dict)
        or state.get("schema") != 1
        or state.get("source_id") != SOURCE_ID
        or state.get("skill") != SKILL_NAME
        or not isinstance(state.get("files"), dict)
    ):
        raise SyncError(f"Installation belongs to another source or is invalid: {path}")
    return state


def write_state(path: Path, files: dict[str, str]) -> None:
    state = {
        "schema": 1,
        "skill": SKILL_NAME,
        "source_id": SOURCE_ID,
        "digest": digest(files),
        "files": files,
    }
    descriptor, temporary = tempfile.mkstemp(prefix=f".{SKILL_NAME}.state-", dir=path.parent)
    temp_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


@contextmanager
def exclusive_lock(root: Path):
    path = root / f".{SKILL_NAME}.sync.lock"
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise SyncError(f"Another sync may be running; inspect lock before retrying: {path}") from exc
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(str(os.getpid()) + "\n")
        yield
    finally:
        path.unlink(missing_ok=True)


def sync(source: Path, destination_root: Path, *, check: bool = False) -> dict:
    source = source.absolute()
    destination_root = destination_root.expanduser().absolute()
    destination = destination_root / SKILL_NAME
    state_path = destination_root / f".{SKILL_NAME}.installation.json"
    desired = inventory(source)
    if source.resolve() == destination.resolve():
        raise SyncError("Source and installed destination must be different directories")
    if check:
        if not destination.exists() or destination.is_symlink():
            raise SyncError(f"Skill not installed as an ordinary directory: {destination}")
        current = inventory(destination)
        state = read_state(state_path)
        if current != desired:
            raise SyncError("Installed files differ from source; run sync after resolving local edits")
        if not state or state["files"] != desired or state.get("digest") != digest(desired):
            raise SyncError("Installation state is missing or does not match source")
        return {"status": "verified", "path": str(destination), "files": len(desired), "sha256": digest(desired)}

    destination_root.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(destination_root):
        if destination.is_symlink():
            raise SyncError(f"Refusing to replace symbolic-link installation: {destination}")
        exists = destination.exists()
        current = inventory(destination) if exists else None
        state = read_state(state_path)
        if exists and current != desired and (state is None or current != state["files"]):
            raise SyncError("Existing installation has local edits or an unknown source; preserve and reconcile it first")
        if current == desired:
            write_state(state_path, desired)
            return {"status": "current" if state else "adopted", "path": str(destination), "files": len(desired), "sha256": digest(desired)}

        staging = Path(tempfile.mkdtemp(prefix=f".{SKILL_NAME}.stage-", dir=destination_root))
        candidate = staging / "candidate"
        backup = staging / "previous"
        preserve_staging = False
        try:
            shutil.copytree(source, candidate)
            if inventory(candidate) != desired or inventory(source) != desired:
                raise SyncError("Source changed during copy; retry with a stable source")
            if exists:
                os.replace(destination, backup)
            try:
                os.replace(candidate, destination)
                write_state(state_path, desired)
            except Exception as exc:
                try:
                    if destination.exists():
                        shutil.rmtree(destination)
                    if backup.exists():
                        os.replace(backup, destination)
                except Exception as rollback_error:
                    preserve_staging = True
                    raise SyncError(f"Update and rollback failed; previous files are preserved at {backup}") from rollback_error
                raise SyncError("Update failed; previous installation restored") from exc
        finally:
            if not preserve_staging:
                shutil.rmtree(staging)
        return {"status": "updated" if exists else "installed", "path": str(destination), "files": len(desired), "sha256": digest(desired)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Read-only exact-content verification")
    parser.add_argument("--dest", type=Path, help="Skills root; defaults to $CODEX_HOME/skills or ~/.codex/skills")
    args = parser.parse_args()
    destination_root = args.dest or Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "skills"
    try:
        print(json.dumps(sync(SOURCE, destination_root, check=args.check), ensure_ascii=False))
        return 0
    except (SyncError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
