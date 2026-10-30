#!/usr/bin/env python3
"""Finalize a muse-ai installation by removing validated sibling backups."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


EXPECTED_SKILL_VERSION = "2.3.4"
EXPECTED_CLI_VERSION = "muse 0.4.3"
BACKUP_NAME = re.compile(r"muse-ai\.bak-\d{8}(?:\d{6})?")
SEMVER = re.compile(r"(\d+)\.(\d+)\.(\d+)")
CONFIRMATION_TOKEN = re.compile(r"[0-9a-f]{64}")


class CleanupFailure(Exception):
    def __init__(
        self,
        message: str,
        *,
        actual_path: Path,
        restored: bool,
        partial_delete: bool,
    ) -> None:
        super().__init__(message)
        self.actual_path = actual_path
        self.restored = restored
        self.partial_delete = partial_delete


def _output(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _validate_install(skill_root: Path) -> dict[str, str]:
    if skill_root.name != "muse-ai":
        raise ValueError("安装目录名必须是 muse-ai")

    module_path = skill_root / "module.json"
    module = json.loads(module_path.read_text(encoding="utf-8"))
    if not isinstance(module, dict):
        raise ValueError("module.json 必须是对象")
    skill_version = str(module.get("version", ""))
    if skill_version != EXPECTED_SKILL_VERSION:
        raise ValueError(
            f"Skill 版本不匹配：期望 {EXPECTED_SKILL_VERSION}，实际 {skill_version or 'missing'}"
        )

    entrypoint = skill_root / "scripts" / "muse_cli.py"
    result = subprocess.run(
        [sys.executable, str(entrypoint), "--version"],
        cwd=skill_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    cli_version = result.stdout.strip()
    if result.returncode != 0 or cli_version != EXPECTED_CLI_VERSION:
        raise ValueError(
            f"CLI 版本不匹配：期望 {EXPECTED_CLI_VERSION}，实际 {cli_version or 'unavailable'}"
        )

    return {"skillVersion": skill_version, "cliVersion": cli_version}


def _version_tuple(version: str) -> tuple[int, int, int]:
    match = SEMVER.fullmatch(version)
    if not match:
        raise ValueError(f"无效的 Skill 版本：{version or 'missing'}")
    return tuple(int(part) for part in match.groups())


def _confirmation_token(path: Path, *, backup_name: str, version: str) -> str:
    root_stat = os.stat(path, follow_symlinks=False)
    digest = hashlib.sha256()
    for value in (
        backup_name,
        version,
        str(root_stat.st_dev),
        str(root_stat.st_ino),
        oct(stat.S_IMODE(root_stat.st_mode)),
    ):
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")

    def visit(directory: Path) -> None:
        with os.scandir(directory) as iterator:
            entries = sorted(iterator, key=lambda entry: os.fsencode(entry.name))
        for entry in entries:
            entry_path = Path(entry.path)
            relative = entry_path.relative_to(path).as_posix()
            entry_stat = entry.stat(follow_symlinks=False)
            if stat.S_ISLNK(entry_stat.st_mode):
                raise ValueError(f"备份中不允许符号链接：{relative}")
            if stat.S_ISDIR(entry_stat.st_mode):
                kind = "directory"
            elif stat.S_ISREG(entry_stat.st_mode):
                kind = "file"
            else:
                raise ValueError(f"备份中不允许特殊文件：{relative}")

            for value in (
                relative,
                kind,
                str(entry_stat.st_dev),
                str(entry_stat.st_ino),
                oct(stat.S_IMODE(entry_stat.st_mode)),
            ):
                digest.update(os.fsencode(value))
                digest.update(b"\0")

            if kind == "directory":
                visit(entry_path)
                continue

            flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            file_descriptor = os.open(entry_path, flags)
            try:
                opened_stat = os.fstat(file_descriptor)
                if (
                    opened_stat.st_dev != entry_stat.st_dev
                    or opened_stat.st_ino != entry_stat.st_ino
                    or not stat.S_ISREG(opened_stat.st_mode)
                ):
                    raise ValueError(f"备份文件在预览时发生变化：{relative}")
                while True:
                    chunk = os.read(file_descriptor, 64 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                final_stat = os.fstat(file_descriptor)
                if (
                    final_stat.st_size != opened_stat.st_size
                    or final_stat.st_mtime_ns != opened_stat.st_mtime_ns
                ):
                    raise ValueError(f"备份文件在预览时发生变化：{relative}")
            finally:
                os.close(file_descriptor)
            digest.update(b"\0")

    visit(path)
    return digest.hexdigest()


def _validate_backup(path: Path, *, expected_name: str | None = None) -> dict[str, str]:
    backup_name = expected_name or path.name
    if not BACKUP_NAME.fullmatch(backup_name):
        raise ValueError("备份名称不符合规则")
    if path.is_symlink() or not path.is_dir():
        raise ValueError("备份必须是非符号链接目录")

    skill_path = path / "SKILL.md"
    module_path = path / "module.json"
    entrypoint = path / "scripts" / "muse_cli.py"
    for required in (skill_path, module_path, entrypoint):
        if required.is_symlink() or not required.is_file():
            raise ValueError(f"缺少可信文件：{required.relative_to(path)}")

    skill_text = skill_path.read_text(encoding="utf-8")
    sections = skill_text.split("---", 2)
    if len(sections) != 3 or not re.search(
        r"(?m)^name:\s*muse-ai\s*$", sections[1]
    ):
        raise ValueError("SKILL.md 未声明 name: muse-ai")

    module = json.loads(module_path.read_text(encoding="utf-8"))
    if not isinstance(module, dict):
        raise ValueError("module.json 必须是对象")
    version = str(module.get("version", ""))
    if _version_tuple(version) > _version_tuple(EXPECTED_SKILL_VERSION):
        raise ValueError(
            f"只允许删除不高于当前 {EXPECTED_SKILL_VERSION} 的备份，实际 {version}"
        )
    return {
        "name": backup_name,
        "path": str(path),
        "version": version,
        "confirmationToken": _confirmation_token(
            path, backup_name=backup_name, version=version
        ),
    }


def _inspect_backups(skill_root: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    candidates: list[dict[str, str]] = []
    rejected: list[dict[str, str]] = []
    for path in sorted(skill_root.parent.iterdir(), key=lambda item: item.name):
        if not BACKUP_NAME.fullmatch(path.name):
            continue
        try:
            candidates.append(_validate_backup(path))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            rejected.append({"name": path.name, "path": str(path), "reason": str(error)})
    return candidates, rejected


def _registration_conflicts(rejected: list[dict[str, str]]) -> list[dict[str, str]]:
    conflicts: list[dict[str, str]] = []
    for item in rejected:
        path = Path(item["path"])
        skill_path = path / "SKILL.md"
        try:
            if path.is_symlink():
                conflicts.append(item)
                continue
            if not path.is_dir():
                continue
            os.lstat(skill_path)
            conflicts.append(item)
        except FileNotFoundError:
            continue
        except OSError:
            conflicts.append(item)
    return conflicts


def _remove_confirmed_backup(path: Path, confirmation_token: str) -> dict[str, str]:
    checked = _validate_backup(path)
    if checked["confirmationToken"] != confirmation_token:
        raise ValueError("备份对象已在预览后发生变化，请重新预览并确认")

    quarantine_root = Path(
        tempfile.mkdtemp(prefix=".muse-ai-cleanup-", dir=path.parent)
    )
    os.chmod(quarantine_root, 0o700)
    quarantine = quarantine_root / path.name
    try:
        path.rename(quarantine)
    except OSError:
        try:
            quarantine_root.rmdir()
        except OSError:
            pass
        raise
    try:
        moved = _validate_backup(quarantine, expected_name=path.name)
        if moved["confirmationToken"] != confirmation_token:
            raise ValueError("备份对象在删除前发生变化，请重新预览并确认")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        if (quarantine.is_symlink() or quarantine.exists()) and not path.exists():
            try:
                quarantine.rename(path)
            except OSError:
                raise CleanupFailure(
                    f"删除前校验失败且无法恢复原路径：{error}",
                    actual_path=quarantine,
                    restored=False,
                    partial_delete=False,
                ) from error
        try:
            quarantine_root.rmdir()
        except OSError:
            pass
        raise

    try:
        shutil.rmtree(quarantine)
    except BaseException as error:
        restored = False
        actual_path = quarantine
        if (quarantine.is_symlink() or quarantine.exists()) and not path.exists():
            try:
                quarantine.rename(path)
                restored = True
                actual_path = path
            except OSError:
                pass
        try:
            quarantine_root.rmdir()
        except OSError:
            pass
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        raise CleanupFailure(
            f"删除失败，可能已部分删除；剩余内容位于 {actual_path}: {error}",
            actual_path=actual_path,
            restored=restored,
            partial_delete=True,
        ) from error
    try:
        quarantine_root.rmdir()
    except OSError:
        pass
    return checked


def cleanup_backups(*, selected_tokens: list[str] | None) -> int:
    skill_root = Path(__file__).resolve().parent.parent
    try:
        validated = _validate_install(skill_root)
        candidates, rejected = _inspect_backups(skill_root)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        _output(
            {
                "ok": False,
                "schemaVersion": 1,
                "error": {"type": "validation", "message": str(error)},
            }
        )
        return 1

    if selected_tokens is None:
        _output(
            {
                "ok": True,
                "schemaVersion": 1,
                "data": {
                    "apply": False,
                    "validated": validated,
                    "candidates": candidates,
                    "rejected": rejected,
                    "removed": [],
                },
            }
        )
        return 0

    candidate_by_token = {item["confirmationToken"]: item for item in candidates}
    invalid_selection = [
        token
        for token in selected_tokens
        if not CONFIRMATION_TOKEN.fullmatch(token) or token not in candidate_by_token
    ]
    if invalid_selection:
        _output(
            {
                "ok": False,
                "schemaVersion": 1,
                "error": {
                    "type": "selection",
                    "message": "存在无效或已失效的确认令牌，请重新预览并确认",
                    "tokens": invalid_selection,
                },
            }
        )
        return 1

    removed: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []
    for token in dict.fromkeys(selected_tokens):
        item = candidate_by_token[token]
        name = item["name"]
        candidate = skill_root.parent / name
        try:
            removed.append(_remove_confirmed_backup(candidate, token))
        except CleanupFailure as error:
            failed.append(
                {
                    "name": name,
                    "path": str(candidate),
                    "actualPath": str(error.actual_path),
                    "restored": error.restored,
                    "partialDelete": error.partial_delete,
                    "message": str(error),
                }
            )
        except (OSError, ValueError, json.JSONDecodeError) as error:
            failed.append({"name": name, "path": str(candidate), "message": str(error)})

    rescan_error: dict[str, str] | None = None
    try:
        remaining_candidates, remaining_rejected = _inspect_backups(skill_root)
        remaining_conflicts = _registration_conflicts(remaining_rejected)
    except OSError as error:
        remaining_candidates = []
        remaining_rejected = []
        remaining_conflicts = []
        rescan_error = {
            "type": "rescan",
            "message": f"删除后无法确认剩余备份：{error}",
        }
    complete = (
        not failed
        and not remaining_candidates
        and not remaining_conflicts
        and rescan_error is None
    )
    _output(
        {
            "ok": complete,
            "schemaVersion": 1,
            "data": {
                "apply": True,
                "validated": validated,
                "selected": [candidate_by_token[token]["name"] for token in dict.fromkeys(selected_tokens)],
                "removed": removed,
                "failed": failed,
                "remainingCandidates": remaining_candidates,
                "remainingRejected": remaining_rejected,
                "remainingConflicts": remaining_conflicts,
                "rescanError": rescan_error,
            },
        }
    )
    return 0 if complete else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MuseAI Skill 安装收尾工具")
    subparsers = parser.add_subparsers(dest="command", required=True)
    cleanup = subparsers.add_parser(
        "cleanup-backups", description="校验当前版本后清理同级旧备份"
    )
    cleanup.add_argument(
        "--apply",
        nargs="+",
        metavar="CONFIRMATION_TOKEN",
        help="逐个指定预览后由用户确认的对象令牌；不传时仅预览",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "cleanup-backups":
        return cleanup_backups(selected_tokens=args.apply)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
