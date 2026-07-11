#!/usr/bin/env python3
"""Regression tests for the scheduled archive commit/push guard."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "commit_archive_changes.sh"


def bash_executable() -> str:
    if os.name == "nt":
        git_bash = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe"
        if git_bash.exists():
            return str(git_bash)
    bash = shutil.which("bash")
    if not bash:
        raise RuntimeError("bash is required")
    return bash


BASH = bash_executable()


def run(command: list[str], cwd: Path, *, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True)
    if check and result.returncode != 0:
        raise AssertionError(f"command failed: {command}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
    return result


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], cwd, check=check)


def setup_repo(root: Path) -> tuple[Path, Path, Path]:
    remote = root / "remote.git"
    seed = root / "seed"
    work = root / "work"
    git(root, "init", "--bare", str(remote))
    git(root, "init", "-b", "main", str(seed))
    git(seed, "config", "user.name", "test")
    git(seed, "config", "user.email", "test@example.com")
    (seed / "README.md").write_text("base\n", encoding="utf-8")
    git(seed, "add", "README.md")
    git(seed, "commit", "-m", "base")
    git(seed, "remote", "add", "origin", str(remote))
    git(seed, "push", "-u", "origin", "main")
    git(root, "clone", str(remote), str(work))
    git(work, "checkout", "--detach", "origin/main")
    return remote, seed, work


def fake_curl(root: Path) -> tuple[Path, Path]:
    capture = root / "dispatch.txt"
    script = root / "fake-curl.sh"
    script.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "$DISPATCH_CAPTURE"\n', encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script, capture


def invoke(work: Path, root: Path, *, actor: str, curl_bin: Path | None = None) -> subprocess.CompletedProcess[str]:
    output = root / "github-output.txt"
    env = os.environ.copy()
    env.update(
        {
            "GITHUB_OUTPUT": output.as_posix(),
            "GITHUB_REPOSITORY": "example/archive",
            "GITHUB_TOKEN": "test-token",
            "GITHUB_ACTOR": actor,
            "SYNC_SCOPE": "all",
        }
    )
    if curl_bin:
        env["ARCHIVE_CURL_BIN"] = curl_bin.as_posix()
        env["DISPATCH_CAPTURE"] = (root / "dispatch.txt").as_posix()
    result = run([BASH, SCRIPT.as_posix()], work, check=False, env=env)
    result.output_text = output.read_text(encoding="utf-8") if output.exists() else ""  # type: ignore[attr-defined]
    return result


def change_readme(work: Path, text: str = "generated\n") -> None:
    (work / "README.md").write_text(text, encoding="utf-8")


def test_detached_head_push(root: Path) -> None:
    remote, _, work = setup_repo(root)
    change_readme(work)
    result = invoke(work, root, actor="schedule-owner")
    assert result.returncode == 0, result.stderr
    assert "changed=true" in result.output_text  # type: ignore[attr-defined]
    assert "superseded=false" in result.output_text  # type: ignore[attr-defined]
    assert git(remote, "rev-parse", "main").stdout.strip() == git(work, "rev-parse", "HEAD").stdout.strip()


def test_unchanged_remote_push_failure(root: Path) -> None:
    remote, _, work = setup_repo(root)
    hook = remote / "hooks" / "pre-receive"
    hook.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
    change_readme(work)
    result = invoke(work, root, actor="schedule-owner")
    assert result.returncode != 0
    assert "refusing to start a retry loop" in result.stdout
    assert "superseded=true" not in result.output_text  # type: ignore[attr-defined]


def advance_remote(seed: Path) -> None:
    (seed / "README.md").write_text("interactive\n", encoding="utf-8")
    git(seed, "add", "README.md")
    git(seed, "commit", "-m", "interactive")
    git(seed, "push", "origin", "main")


def test_remote_change_dispatches_once(root: Path) -> None:
    _, seed, work = setup_repo(root)
    change_readme(work)
    advance_remote(seed)
    curl_bin, capture = fake_curl(root)
    result = invoke(work, root, actor="schedule-owner", curl_bin=curl_bin)
    assert result.returncode == 0, result.stderr
    assert "changed=false" in result.output_text  # type: ignore[attr-defined]
    assert "superseded=true" in result.output_text  # type: ignore[attr-defined]
    assert len(capture.read_text(encoding="utf-8").splitlines()) == 1


def test_bot_retry_never_redispatches(root: Path) -> None:
    _, seed, work = setup_repo(root)
    change_readme(work)
    advance_remote(seed)
    curl_bin, capture = fake_curl(root)
    result = invoke(work, root, actor="github-actions[bot]", curl_bin=curl_bin)
    assert result.returncode != 0
    assert "refusing to dispatch another workflow run" in result.stdout
    assert not capture.exists()


def main() -> None:
    tests = (
        ("detached_head_push", test_detached_head_push),
        ("unchanged_remote_push_failure", test_unchanged_remote_push_failure),
        ("remote_change_dispatches_once", test_remote_change_dispatches_once),
        ("bot_retry_never_redispatches", test_bot_retry_never_redispatches),
    )
    for name, test in tests:
        with tempfile.TemporaryDirectory(prefix=f"archive-commit-{name}-") as temp_dir:
            test(Path(temp_dir))
        print(f"{name}=PASS")
    print("result=PASS")


if __name__ == "__main__":
    main()
