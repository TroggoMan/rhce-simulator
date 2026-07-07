"""
Thin subprocess wrapper around the ansible-core CLI tools.

Everything the simulator learns about the candidate's work on managed nodes
goes through here: syntax checks, real playbook runs, idempotence re-runs and
ad-hoc state queries — always using the candidate's OWN ansible.cfg and
inventory (we run with cwd=workdir so their ansible.cfg applies, exactly as
the exam grades it).

Unit tests monkeypatch run() so no test ever needs Ansible installed.
"""

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

DEFAULT_TIMEOUT = 300


@dataclass
class CmdResult:
    rc: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.rc == 0

    @property
    def text(self) -> str:
        return self.stdout + "\n" + self.stderr


@dataclass
class RecapLine:
    ok: int = 0
    changed: int = 0
    unreachable: int = 0
    failed: int = 0


def have_ansible() -> bool:
    return shutil.which("ansible-playbook") is not None


def have_navigator() -> bool:
    return shutil.which("ansible-navigator") is not None


def run(cmd, cwd: Optional[Path] = None, timeout: int = DEFAULT_TIMEOUT,
        env: Optional[dict] = None) -> CmdResult:
    """Run a command; never raises on non-zero exit."""
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd) if cwd else None, env=env,
            capture_output=True, text=True, timeout=timeout,
        )
        return CmdResult(proc.returncode, proc.stdout, proc.stderr)
    except FileNotFoundError as exc:
        return CmdResult(127, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        return CmdResult(124, exc.stdout or "", f"timed out after {timeout}s")


RECAP_RE = re.compile(
    r"^(?P<host>\S+)\s*:\s*ok=(?P<ok>\d+)\s+changed=(?P<changed>\d+)\s+"
    r"unreachable=(?P<unreachable>\d+)\s+failed=(?P<failed>\d+)",
    re.MULTILINE,
)


def parse_recap(output: str) -> Dict[str, RecapLine]:
    """Parse the PLAY RECAP block of ansible-playbook output."""
    recap = {}
    for m in RECAP_RE.finditer(output):
        recap[m.group("host")] = RecapLine(
            ok=int(m.group("ok")),
            changed=int(m.group("changed")),
            unreachable=int(m.group("unreachable")),
            failed=int(m.group("failed")),
        )
    return recap


def syntax_check(playbook: Path, workdir: Path, extra_args=None) -> CmdResult:
    cmd = ["ansible-playbook", "--syntax-check"] + list(extra_args or []) + [str(playbook)]
    return run(cmd, cwd=workdir)


def run_playbook(playbook: Path, workdir: Path, extra_args=None) -> CmdResult:
    cmd = ["ansible-playbook"] + list(extra_args or []) + [str(playbook)]
    return run(cmd, cwd=workdir)


@dataclass
class PlaybookRun:
    """Outcome of a full run + idempotence re-run of one playbook."""
    syntax_ok: bool = False
    run_ok: bool = False
    idempotent: bool = False
    detail: str = ""
    recap: Dict[str, RecapLine] = field(default_factory=dict)


def full_playbook_check(playbook: Path, workdir: Path, extra_args=None) -> PlaybookRun:
    """Syntax-check, run, then re-run to prove idempotence (changed=0)."""
    result = PlaybookRun()
    syn = syntax_check(playbook, workdir, extra_args)
    result.syntax_ok = syn.ok
    if not syn.ok:
        result.detail = _tail(syn.text)
        return result

    first = run_playbook(playbook, workdir, extra_args)
    result.recap = parse_recap(first.stdout)
    bad = {h: r for h, r in result.recap.items() if r.failed or r.unreachable}
    result.run_ok = first.ok and not bad and bool(result.recap)
    if not result.run_ok:
        result.detail = _tail(first.text)
        return result

    second = run_playbook(playbook, workdir, extra_args)
    recap2 = parse_recap(second.stdout)
    changed = sum(r.changed for r in recap2.values())
    result.idempotent = second.ok and changed == 0
    if not result.idempotent:
        result.detail = f"second run reported changed={changed} (expected 0)"
    return result


def adhoc(pattern: str, module: str, args: str = "", workdir: Optional[Path] = None,
          become: bool = False) -> CmdResult:
    """Run an ad-hoc command against the candidate's inventory."""
    cmd = ["ansible", pattern, "-m", module]
    if args:
        cmd += ["-a", args]
    if become:
        cmd.append("--become")
    return run(cmd, cwd=workdir)


def vault_view(path: Path, password_file: Path, workdir: Path) -> CmdResult:
    return run(
        ["ansible-vault", "view", "--vault-password-file", str(password_file), str(path)],
        cwd=workdir,
    )


def _tail(text: str, lines: int = 15) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])
