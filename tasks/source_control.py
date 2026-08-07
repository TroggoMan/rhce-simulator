"""
Domain 6/7: basic Git source control and pushing playbooks back to a
repository — added to the objectives alongside ansible-navigator and never
covered by the original 7-domain task set here. No managed nodes involved;
everything happens on the control node.

The "remote" is a real, throwaway bare repo the simulator creates on disk
(same pattern as rhcsa-simulator auto-creating loop devices) so cloning and
pushing are fully offline and don't depend on network access or a real
Git host.
"""

import shutil
from pathlib import Path

from config import settings
from core.registry import TaskRegistry
from tasks.base import AnsibleTask
from validators import ansible_runner as runner


def _have_git() -> bool:
    return shutil.which("git") is not None


@TaskRegistry.register("source_control")
class GitCloneAndPushTask(AnsibleTask):
    def __init__(self):
        super().__init__("git_clone_push_001", "source_control", "medium")

    def generate(self, **params):
        remote = settings.DATA_DIR / "git_remotes" / f"{self.id}.git"
        self.params = {
            "remote": str(remote),
            "clone_dir": "lab_repo",
            "playbook": "site.yml",
        }
        self._ensure_remote(remote)
        self.description = f"""
Your team's Ansible content lives in a Git repository. In  {self.workdir} :

  1. Clone this repository:
        {self.params['remote']}
     into a directory named  {self.params['clone_dir']}

  2. Inside {self.params['clone_dir']}, create a new, syntactically valid
     playbook file named  {self.params['playbook']}  (any content — a
     single play with at least one task is enough).

  3. Add it, commit it, and PUSH the commit back to the same remote.
"""
        self.hints = [
            f"git clone {self.params['remote']} {self.params['clone_dir']}",
            "cd into the clone before add/commit/push — you're committing "
            "to that repo, not your top-level working directory.",
            "git add site.yml && git commit -m '...' && git push",
        ]
        self.exam_tips = [
            "The real exam expects basic git fluency (clone, add, commit, "
            "push) and, per the objectives, doing this from within VS Code "
            "specifically — the underlying git operations graded here are "
            "identical no matter which editor/terminal you use.",
        ]
        return self

    @staticmethod
    def _ensure_remote(remote: Path):
        """Create the bare 'remote' repo fixture if it doesn't exist yet."""
        if remote.exists() or not _have_git():
            return
        remote.parent.mkdir(parents=True, exist_ok=True)
        runner.run(["git", "init", "--bare", "-b", "main", str(remote)])
        seed = remote.parent / f".seed-{remote.stem}"
        shutil.rmtree(seed, ignore_errors=True)
        runner.run(["git", "clone", str(remote), str(seed)])
        (seed / "README.md").write_text(
            "# Lab automation content\n\nClone, add a playbook, commit, push.\n")
        runner.run(["git", "-c", "user.email=lab@example.com",
                    "-c", "user.name=Lab", "add", "README.md"], cwd=seed)
        runner.run(["git", "-c", "user.email=lab@example.com",
                    "-c", "user.name=Lab", "commit", "-m", "initial"], cwd=seed)
        runner.run(["git", "push", "origin", "main"], cwd=seed)
        shutil.rmtree(seed, ignore_errors=True)

    def validate(self):
        res = self.result()
        if not _have_git():
            res.add("git available on this control node", False,
                    "install git to work through this task")
            return res
        clone_dir = self.workdir / self.params["clone_dir"]
        res.add(f"{self.params['clone_dir']} is a git clone of the remote",
                (clone_dir / ".git").is_dir(),
                "" if (clone_dir / ".git").is_dir() else
                f"git clone {self.params['remote']} {self.params['clone_dir']}")
        if not (clone_dir / ".git").is_dir():
            return res

        out = runner.run(["git", "remote", "get-url", "origin"], cwd=clone_dir)
        origin_ok = out.ok and out.stdout.strip() == self.params["remote"]
        res.add("origin points at the lab remote", origin_ok,
                "" if origin_ok else out.text.strip())

        playbook = clone_dir / self.params["playbook"]
        res.add(f"{self.params['playbook']} exists in the clone",
                playbook.exists(),
                "" if playbook.exists() else f"missing at {playbook}")
        if not playbook.exists():
            return res

        if runner.have_ansible():
            syn = runner.syntax_check(Path(self.params["playbook"]), clone_dir)
            res.add(f"{self.params['playbook']} passes --syntax-check", syn.ok,
                    "" if syn.ok else syn.text.strip()[-300:])

        pushed = runner.run(["git", "log", "--all", "--name-only",
                             "--format="], cwd=Path(self.params["remote"]))
        found = pushed.ok and self.params["playbook"] in pushed.stdout
        res.add("commit containing the playbook was pushed to the remote",
                found, "" if found else "git push origin main from the clone")
        return res


@TaskRegistry.register("source_control")
class GitBranchWorkflowTask(AnsibleTask):
    """Feature-branch workflow: create a branch, commit on it, push the
    BRANCH — not main. The 'main only' habit doesn't survive real teams."""

    def __init__(self):
        super().__init__("git_branch_001", "source_control", "medium")

    def generate(self, **params):
        remote = settings.DATA_DIR / "git_remotes" / f"{self.id}.git"
        branch = params.get("branch") or "feature/site-updates"
        self.params = {
            "remote": str(remote),
            "clone_dir": "branch_repo",
            "branch": branch,
            "playbook": "site_update.yml",
        }
        GitCloneAndPushTask._ensure_remote(remote)
        self.description = f"""
Your team never commits straight to main. In  {self.workdir} :

  1. Clone  {self.params['remote']}  into  {self.params['clone_dir']}
  2. Create and check out a NEW branch named  {branch}
  3. Inside it, add a new playbook  {self.params['playbook']}  (any valid
     content — one play, one task is enough)
  4. Commit it, then PUSH THE BRANCH (not main) to the same remote

main on the remote must be unaffected; {branch} must exist on the remote
and contain your commit."""
        self.hints = [
            f"git checkout -b {branch}",
            f"git push origin {branch}  — pushing without specifying a "
            "branch pushes your CURRENT branch only if push.default is "
            "configured for it; naming it explicitly is safer.",
            "git branch -a (after fetching) shows both local and remote "
            "branches to confirm it landed.",
        ]
        return self

    def validate(self):
        res = self.result()
        if not _have_git():
            res.add("git available on this control node", False,
                    "install git to work through this task")
            return res
        clone_dir = self.workdir / self.params["clone_dir"]
        res.add(f"{self.params['clone_dir']} is a git clone of the remote",
                (clone_dir / ".git").is_dir(),
                "" if (clone_dir / ".git").is_dir() else
                f"git clone {self.params['remote']} {self.params['clone_dir']}")
        if not (clone_dir / ".git").is_dir():
            return res

        out = runner.run(["git", "branch", "--show-current"], cwd=clone_dir)
        on_branch = out.ok and out.stdout.strip() == self.params["branch"]
        res.add(f"clone is checked out on {self.params['branch']}", on_branch,
                "" if on_branch else f"git checkout -b {self.params['branch']}")

        playbook = clone_dir / self.params["playbook"]
        res.add(f"{self.params['playbook']} exists in the clone",
                playbook.exists(), "" if playbook.exists() else
                f"missing at {playbook}")
        if not playbook.exists():
            return res

        remote_branches = runner.run(
            ["git", "branch", "-a"], cwd=Path(self.params["remote"]))
        pushed = remote_branches.ok and self.params["branch"] in remote_branches.stdout
        res.add(f"{self.params['branch']} was pushed to the remote", pushed,
                "" if pushed else f"git push origin {self.params['branch']}")

        main_untouched = runner.run(
            ["git", "log", "main", "--name-only", "--format="],
            cwd=Path(self.params["remote"]))
        clean_main = main_untouched.ok and \
            self.params["playbook"] not in main_untouched.stdout
        res.add("main was NOT modified by this push", clean_main,
                "" if clean_main else
                f"{self.params['playbook']} landed on main — it belongs on "
                f"{self.params['branch']} only")
        return res


@TaskRegistry.register("source_control")
class GitIgnoreCommitTask(AnsibleTask):
    """.gitignore — keeping generated/sensitive files (vault artifacts,
    retry files, __pycache__-style noise) out of a repo in the first place."""

    def __init__(self):
        super().__init__("git_gitignore_001", "source_control", "easy")

    def generate(self, **params):
        remote = settings.DATA_DIR / "git_remotes" / f"{self.id}.git"
        self.params = {
            "remote": str(remote),
            "clone_dir": "ignore_repo",
            "ignored": "site.retry",
            "tracked": "site.yml",
        }
        GitCloneAndPushTask._ensure_remote(remote)
        self.description = f"""
In  {self.workdir} :

  1. Clone  {self.params['remote']}  into  {self.params['clone_dir']}
  2. Create a  .gitignore  that excludes  *.retry  files (Ansible's own
     retry-file litter — never belongs in a repo)
  3. Create BOTH of these files inside the clone:
        {self.params['tracked']}   (any valid playbook content)
        {self.params['ignored']}   (any content — simulates a leftover
                                     .retry file)
  4. Stage everything with  git add .  , commit, and push

After pushing, {self.params['tracked']} must be in the repository history
and {self.params['ignored']} must NOT be — the .gitignore must have kept
it out even though you (deliberately) tried to add everything."""
        self.hints = [
            ".gitignore pattern: *.retry",
            "git add . respects .gitignore automatically — if the ignored "
            "file still gets committed, the pattern is wrong or the "
            ".gitignore wasn't created before staging.",
            "git status before committing is the sanity check: the ignored "
            "file should never show as staged.",
        ]
        return self

    def validate(self):
        res = self.result()
        if not _have_git():
            res.add("git available on this control node", False,
                    "install git to work through this task")
            return res
        clone_dir = self.workdir / self.params["clone_dir"]
        if not self.check_exists(res, f"{self.params['clone_dir']}/.gitignore"):
            return res
        self.check_contains(res, f"{self.params['clone_dir']}/.gitignore",
                            r"\*\.retry", ".gitignore excludes *.retry files")

        pushed = runner.run(["git", "log", "--all", "--name-only", "--format="],
                            cwd=Path(self.params["remote"]))
        tracked_pushed = pushed.ok and self.params["tracked"] in pushed.stdout
        res.add(f"{self.params['tracked']} was committed and pushed", tracked_pushed,
                "" if tracked_pushed else
                f"git add {self.params['tracked']} && git commit && git push")
        ignored_absent = pushed.ok and self.params["ignored"] not in pushed.stdout
        res.add(f"{self.params['ignored']} was correctly kept OUT of the repo",
                ignored_absent, "" if ignored_absent else
                f"{self.params['ignored']} got committed — .gitignore isn't "
                "working or was added after staging")
        return res
