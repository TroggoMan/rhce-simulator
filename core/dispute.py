"""
Checker dispute reporting.

When a candidate believes a validator (the "checker") scored a task wrongly,
they dispute it from the session loop. A dispute:

  1. captures evidence — the candidate's own Ansible artifacts plus live
     managed-node state,
  2. bundles it with the task, the failed check(s) and the candidate's
     written argument into a Markdown report,
  3. opens a GitHub issue (labelled ``checker-dispute``) via the ``gh`` CLI,
     or prints a pre-filled browser URL when ``gh`` isn't available.

A GitHub Action (.github/workflows/checker-dispute.yml) reacts to that
label: an AI reviewer inspects the validator for that task, compares it
against the evidence, comments a verdict, and opens a fix PR if the checker
is genuinely wrong.

Ported from the sibling rhcsa-simulator, but the evidence model is
different in a way that matters. RHCSA grades one box, so its evidence is
local commands. Here the answer is a FILE the candidate wrote and the
effect it had on OTHER machines, so evidence has to be both:

  * the artifacts themselves (playbooks, ansible.cfg, inventory) — an
    Ansible checker is usually wrong about what it expected the YAML to
    say, and no amount of node state shows that;
  * node state, gathered through the candidate's OWN inventory with the
    same ad-hoc mechanism the validators use, so the reviewer sees what the
    checker saw.

Nothing here changes state, locally or on a node. It only reads.
"""

import os
import re
import shutil
import subprocess
import urllib.parse
from datetime import datetime, timezone

from config import settings

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISPUTE_DIR = os.path.join(REPO_ROOT, "data", "disputes")
DISPUTE_LABEL = "checker-dispute"

# Used for the browser fallback URL when the git remote can't be read (a
# tarball copy, or a lab box with no origin).
GITHUB_REPO_FALLBACK = "TroggoMan/rhce-simulator"

_MAX_OUTPUT = 4000    # chars kept per command, to keep issues readable
_MAX_FILE = 6000      # chars kept per captured artifact
_MAX_ARTIFACTS = 12   # files captured from the working directory

_CMD_TIMEOUT = 45

# Artifacts worth capturing from the working directory regardless of task.
# Ansible's behaviour depends on these two more than on anything else, and
# a "your playbook didn't run" dispute is very often really about them.
_ALWAYS_ARTIFACTS = ["ansible.cfg", "inventory", "inventory.yml"]

# Category -> read-only ad-hoc queries showing the state the checker judged.
# Module + args, run through the candidate's own inventory.
_CATEGORY_EVIDENCE = {
    "selinux": [
        ("ansible.builtin.command", "getenforce"),
        ("ansible.builtin.command", "semanage boolean -l -C"),
        ("ansible.builtin.command", "semanage port -l"),
    ],
    "storage_auto": [
        ("ansible.builtin.command", "lsblk"),
        ("ansible.builtin.command", "pvs"),
        ("ansible.builtin.command", "vgs"),
        ("ansible.builtin.command", "lvs"),
        ("ansible.builtin.command", "findmnt --real"),
        ("ansible.builtin.command", "cat /etc/fstab"),
    ],
    "users_auto": [
        ("ansible.builtin.shell", "getent passwd | tail -20"),
        ("ansible.builtin.shell", "getent group | tail -20"),
        ("ansible.builtin.shell", "ls -la /etc/sudoers.d/ 2>/dev/null"),
    ],
    "scheduling_auto": [
        ("ansible.builtin.shell", "crontab -l 2>/dev/null; ls -la /etc/cron.d/"),
        ("ansible.builtin.command", "systemctl list-timers --all"),
    ],
    "file_content": [
        ("ansible.builtin.shell", "ls -la /root /opt 2>/dev/null | head -40"),
    ],
    "templates": [
        ("ansible.builtin.shell", "ls -la /etc/ | head -40"),
    ],
    "system_roles": [
        ("ansible.builtin.command", "systemctl status chronyd --no-pager"),
        ("ansible.builtin.shell", "cat /etc/chrony.conf 2>/dev/null | head -20"),
    ],
    "managed_nodes": [
        ("ansible.builtin.shell", "ls -la ~/.ssh/ 2>/dev/null"),
        ("ansible.builtin.shell", "ls -la /etc/sudoers.d/ 2>/dev/null"),
    ],
    "playbook_basics": [
        ("ansible.builtin.shell", "systemctl list-units --type=service --state=running | head -20"),
    ],
}


def _run(cmd, cwd=None, shell=False):
    """Run a command, returning (display, rc, output). Never raises."""
    display = cmd if isinstance(cmd, str) else " ".join(cmd)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, shell=shell,
                             cwd=cwd or REPO_ROOT, timeout=_CMD_TIMEOUT)
        out = ((res.stdout or "") + (res.stderr or "")).strip()
        return display, res.returncode, out[:_MAX_OUTPUT]
    except Exception as exc:  # timeout, missing binary, anything
        return display, -1, f"<could not run: {exc}>"


def gh_available() -> bool:
    """True if the gh CLI is installed and authenticated."""
    if not shutil.which("gh"):
        return False
    try:
        res = subprocess.run(["gh", "auth", "status"], capture_output=True,
                             text=True, timeout=15)
        return res.returncode == 0
    except Exception:
        return False


def repo_slug() -> str:
    """'owner/repo' from the git origin remote, or the fallback."""
    try:
        res = subprocess.run(["git", "remote", "get-url", "origin"],
                             capture_output=True, text=True, cwd=REPO_ROOT,
                             timeout=10)
        url = (res.stdout or "").strip()
        if url:
            if url.startswith("git@") or ("@" in url and "://" not in url):
                path = url.split(":", 1)[1] if ":" in url else url
            else:
                path = urllib.parse.urlsplit(url).path
            path = path.strip("/")
            if path.endswith(".git"):
                path = path[:-4]
            if path and "/" in path:
                return path
    except Exception:
        pass
    return GITHUB_REPO_FALLBACK


def resolve_source(category: str, task_id: str):
    """Locate the task's source so the reviewer opens ONE file, not the repo.

    Returns (relpath, classname, validate_line) or (None, None, None).
    Ids are assigned in __init__, so instantiating is enough to match —
    generate() is never called, which keeps this cheap and side-effect free.
    """
    try:
        import inspect
        from core.registry import TaskRegistry
        import tasks  # noqa: F401  (import triggers auto-discovery)

        classes = list(TaskRegistry.get_tasks_by_category(category) or [])
        if not classes:  # unknown category — fall back to a full scan
            for cat in TaskRegistry.get_all_categories():
                classes.extend(TaskRegistry.get_tasks_by_category(cat))

        for cls in classes:
            try:
                if getattr(cls(), "id", None) != task_id:
                    continue
            except Exception:
                continue
            src = inspect.getsourcefile(cls) or inspect.getfile(cls)
            rel = os.path.relpath(src, REPO_ROOT)
            try:
                line = inspect.getsourcelines(cls.validate)[1]
            except Exception:
                line = None
            return rel, cls.__name__, line
    except Exception:
        pass
    return None, None, None


def _artifact_names(task) -> list:
    """Filenames the task's own description referred to.

    The description is the contract the candidate was graded against, so
    the files it names are exactly the ones the reviewer needs to see. This
    beats capturing the whole directory: a working directory accumulates
    every playbook from every previous task, and burying the relevant one
    in twenty others makes the review worse, not better.
    """
    text = getattr(task, "description", "") or ""
    names = re.findall(r"[\w./-]+\.(?:yml|yaml|j2|cfg|sh)\b", text)
    # roles/<name>/... entries in the description imply the role tree too.
    names += [m for m in re.findall(r"roles/[\w./-]+", text)]
    seen, ordered = set(), []
    for name in names + _ALWAYS_ARTIFACTS:
        name = name.strip("`.,;:")
        if name and name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered[:_MAX_ARTIFACTS]


def collect_artifacts(task, workdir=None) -> list:
    """(relpath, content) for each file the task named that exists."""
    workdir = workdir or settings.get_workdir()
    captured = []
    for name in _artifact_names(task):
        path = os.path.join(str(workdir), name)
        if os.path.isdir(path):
            found, _, listing = _run(["find", path, "-type", "f"])
            captured.append((f"{name}/ (listing)", listing))
            continue
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                captured.append((name, fh.read()[:_MAX_FILE]))
        except OSError as exc:
            captured.append((name, f"<unreadable: {exc}>"))
    return captured


def collect_evidence(category: str, extra_commands=None) -> list:
    """(display, rc, output) for control-node context and node state.

    Node queries go through the candidate's own inventory and ansible.cfg,
    exactly as the validators do — the point is to show what the checker
    saw, not a second opinion gathered a different way.
    """
    workdir = settings.get_workdir()
    evidence = [
        _run(["ansible", "--version"]),
        _run(["ansible-inventory", "--list", "--yaml"], cwd=str(workdir)),
        _run(["ansible", "all", "-m", "ansible.builtin.ping"], cwd=str(workdir)),
    ]
    for module, args in _CATEGORY_EVIDENCE.get(category, []):
        evidence.append(_run(
            ["ansible", "all", "-b", "-m", module, "-a", args],
            cwd=str(workdir)))
    for raw in (extra_commands or []):
        raw = raw.strip()
        if raw:
            evidence.append(_run(raw, cwd=str(workdir), shell=True))
    return evidence


def build_report(task, result, argument, artifacts, evidence,
                 disputed_checks=None) -> str:
    """Render the dispute as Markdown for the GitHub issue body.

    disputed_checks, if given, is the exact set of check names the
    candidate ticked — from the panel, where a check that PASSED can also
    be disputed ("this shouldn't have gone green"). Without it (the
    terminal `d <n>` path) every failed, non-skipped check is assumed
    disputed, since the terminal only ever shows failures as the reason to
    argue.
    """
    if disputed_checks is not None:
        wanted = set(disputed_checks)
        failed = [c for c in result.checks if c.name in wanted]
    else:
        failed = [c for c in result.checks if not c.passed and not c.skipped]
    lines = [
        f"## Checker dispute: `{task.id}`",
        "",
        f"- **Task ID:** `{task.id}`",
        f"- **Category:** {task.category}",
        f"- **Difficulty:** {task.difficulty}",
        f"- **Scored:** {result.score}/{result.max_score} "
        f"({'PASSED' if result.passed else 'FAILED'})",
        f"- **Filed:** {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
    ]

    # Point the reviewer straight at the checker so it reads one file rather
    # than the whole repo — that is what keeps the review cheap.
    rel, classname, line = resolve_source(task.category, task.id)
    if rel:
        where = f"`{rel}`" + (f" class `{classname}`" if classname else "")
        where += f", `validate()` at line {line}" if line else ""
        lines.append(f"- **Checker source:** {where}")

    lines += ["", "### Checks the candidate disputes", ""]
    if failed:
        for check in failed:
            status = "PASSED (candidate says it shouldn't have)" if check.passed \
                else "FAILED"
            lines.append(f"- **{check.name}** — {status}")
            if check.detail:
                detail = check.detail.strip()[:1200]
                lines.append(f"  ```\n  {detail}\n  ```")
    else:
        lines.append("_(none specified)_")

    skipped = result.skipped
    if skipped:
        lines += ["", "### Checks skipped by the lab (not graded)", ""]
        lines += [f"- {c.name}" for c in skipped]

    lines += ["", "### Candidate's argument", "", argument.strip() or "_(none given)_"]

    lines += ["", "### Task as presented", "", "```",
              (task.description or "").strip(), "```"]

    if artifacts:
        lines += ["", "### The candidate's files", ""]
        for name, content in artifacts:
            lines += [f"<details><summary><code>{name}</code></summary>", "",
                      "```", content.rstrip(), "```", "", "</details>", ""]

    lines += ["", "### Environment and node state", ""]
    for display, rc, out in evidence:
        lines += [f"<details><summary><code>{display}</code> (rc={rc})</summary>",
                  "", "```", out or "<no output>", "```", "", "</details>", ""]

    lines += ["", "---", "",
              "_Filed from the RHCE simulator. Evidence is read-only: no "
              "command above changes the control node or any managed node._"]
    return "\n".join(lines)


def save_report(task, body: str) -> str:
    """Write the report next to the repo so it survives a failed submit."""
    os.makedirs(DISPUTE_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(DISPUTE_DIR, f"{task.id}-{stamp}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return path


def issue_url(task, body: str, max_url: int = 7000) -> str:
    """Pre-filled 'new issue' URL, for boxes with no gh or no auth.

    GitHub truncates very long GET URLs, so the body is progressively
    trimmed and, past a point, replaced with a pointer to the saved file.
    """
    base = f"https://github.com/{repo_slug()}/issues/new"
    title = f"Checker dispute: {task.id}"

    def build(text):
        query = urllib.parse.urlencode(
            {"title": title, "labels": DISPUTE_LABEL, "body": text})
        return f"{base}?{query}"

    url = build(body)
    if len(url) <= max_url:
        return url
    for keep in (4000, 2000, 800):
        trimmed = body[:keep] + "\n\n_(truncated — full report saved locally)_"
        url = build(trimmed)
        if len(url) <= max_url:
            return url
    return build("_Report too long for a URL; paste the saved file instead._")


def submit_issue(task, body_path: str):
    """Open the dispute issue via gh. Returns (ok, message)."""
    title = f"Checker dispute: {task.id}"
    cmd = ["gh", "issue", "create", "--title", title,
           "--label", DISPUTE_LABEL, "--body-file", body_path]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True,
                             cwd=REPO_ROOT, timeout=90)
    except Exception as exc:
        return False, f"could not run gh: {exc}"
    if res.returncode == 0:
        return True, (res.stdout or "").strip()
    err = ((res.stderr or "") + (res.stdout or "")).strip()
    # A repo with the label missing is the common first-run failure, and
    # the message gh gives for it is not obvious.
    if "label" in err.lower() and "not found" in err.lower():
        err += (f"\nCreate it once with: "
                f"gh label create {DISPUTE_LABEL} "
                f"--description 'Validator scored a task wrongly'")
    return False, err
