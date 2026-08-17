"""
"You're running an old checkout" notice.

The simulator is distributed as a git clone, so the only honest way to
know whether a candidate is out of date is to ask the remote what its tip
is. That has to stay cheap and optional: someone drilling on a lab VM
with no route to the internet must not eat a timeout on every launch, and
must never see a stack trace because of one.

So the check is:

  * `git ls-remote`, not `git fetch` — one round trip, nothing written to
    the object store, no working tree touched;
  * cached, so a normal day of practice makes at most one network call;
  * hard-timed out, and silent on every failure — no remote, no git, no
    network, detached HEAD, someone's tarball of the source: all of them
    mean "say nothing" rather than "complain";
  * opt-out via RHCE_SIM_NO_UPDATE_CHECK=1.

Being AHEAD of the remote is not being out of date. The distinguishing
question is whether the remote's tip commit already exists locally: if it
does, this checkout contains everything the remote has (and maybe more,
if the candidate is writing their own tasks). If it doesn't, the remote
has work this clone has never seen.
"""

import json
import os
import subprocess
import time
from pathlib import Path

from config import settings
from config.settings import C

CACHE_FILE = settings.DATA_DIR / "update_check.json"
CACHE_SECONDS = 24 * 60 * 60
FAIL_CACHE_SECONDS = 60 * 60
TIMEOUT_SECONDS = 4

DISABLED = "disabled"          # opted out via the env var
NO_CHECKOUT = "no-checkout"    # not a git clone; nothing to compare against
UNAVAILABLE = "unavailable"    # we asked and could not get an answer
CURRENT = "current"
BEHIND = "behind"


def _run_git(*argv, timeout=TIMEOUT_SECONDS):
    try:
        return subprocess.run(
            ["git", "-C", str(settings.BASE_DIR), *argv],
            capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None


def _git(*argv, timeout=TIMEOUT_SECONDS):
    """Run a git command in the simulator's own checkout, or None."""
    proc = _run_git(*argv, timeout=timeout)
    if proc is None or proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _git_ok(*argv, timeout=TIMEOUT_SECONDS):
    """True when the command exits 0. For git's yes/no queries, which say
    what they mean in the exit code and print nothing."""
    proc = _run_git(*argv, timeout=timeout)
    return proc is not None and proc.returncode == 0


def _read_cache():
    try:
        with open(CACHE_FILE) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _write_cache(payload):
    try:
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w") as fh:
            json.dump(payload, fh)
    except OSError:
        pass  # A read-only checkout just means we re-check next launch.


def _remote_tip():
    """SHA the remote's default branch points at, or None."""
    # Prefer the branch this checkout actually tracks; fall back to the
    # remote's HEAD so a detached or unpushed branch still gets an answer.
    upstream = _git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if upstream and "/" in upstream:
        remote, branch = upstream.split("/", 1)
        out = _git("ls-remote", "--exit-code", remote,
                   f"refs/heads/{branch}")
    else:
        out = _git("ls-remote", "--exit-code", "--symref", "origin", "HEAD")
    if not out:
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2 and len(parts[0]) == 40:
            return parts[0]
    return None


def _behind_remote():
    """True if the remote's tip is not already in this checkout's history."""
    tip = _remote_tip()
    if not tip:
        return None
    # Two separate ways to be behind, and both have to be asked:
    #
    #   * we don't have the object at all — the ordinary stale clone;
    #   * we have it (a previous fetch, or a reset that left the objects
    #     lying around) but it is not an ancestor of HEAD, so it is not
    #     actually part of what we would run.
    #
    # Being AHEAD keeps the ancestor test true, which is the point: local
    # work on top of the remote tip is not out of date.
    if not _git_ok("cat-file", "-e", f"{tip}^{{commit}}"):
        return True
    return not _git_ok("merge-base", "--is-ancestor", tip, "HEAD")


def status(force=False):
    """One of: DISABLED, NO_CHECKOUT, UNAVAILABLE, CURRENT, BEHIND."""
    if os.environ.get("RHCE_SIM_NO_UPDATE_CHECK"):
        return DISABLED
    if not (settings.BASE_DIR / ".git").exists():
        return NO_CHECKOUT
    cache = _read_cache()
    # A failed check is cached too, on a much shorter clock: someone
    # working offline should not pay the timeout on every single launch,
    # but should get a real answer soon after the network comes back.
    ttl = CACHE_SECONDS if cache.get("state") == CURRENT else FAIL_CACHE_SECONDS
    if (not force
            and cache.get("state") in (CURRENT, BEHIND, UNAVAILABLE)
            and isinstance(cache.get("checked_at"), (int, float))
            and time.time() - cache["checked_at"] < ttl):
        return cache["state"]
    behind = _behind_remote()
    state = UNAVAILABLE if behind is None else (BEHIND if behind else CURRENT)
    _write_cache({"checked_at": time.time(), "state": state})
    return state


def warn_if_outdated(force=False):
    """Report on the update check. Never raises, never blocks.

    Says something in both failure directions. Out of date is the point of
    the check; UNABLE to check is worth one line too, because a candidate
    who sees nothing has no way to tell "you're current" apart from "the
    check quietly gave up", and the first is a much stronger claim than we
    are entitled to make while offline.
    """
    try:
        state = status(force=force)
    except Exception:
        state = UNAVAILABLE
    if state == BEHIND:
        print(f"{C.YELLOW}This checkout is out of date — the upstream "
              f"repository has newer commits.{C.RESET}")
        print(f"{C.DIM}  Update with:  git -C {settings.BASE_DIR} pull{C.RESET}")
        print(f"{C.DIM}  Silence this with RHCE_SIM_NO_UPDATE_CHECK=1.{C.RESET}\n")
        return True
    if state == UNAVAILABLE:
        # Offline, no remote, git missing, DNS down, private mirror —
        # all the same to us, and none of them worth blocking practice for.
        print(f"{C.YELLOW}Could not check for updates (offline?) — "
              f"carrying on with the version you have.{C.RESET}\n")
        return True
    return False
