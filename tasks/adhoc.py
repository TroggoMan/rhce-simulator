"""
Domain 2: ad-hoc commands. The classic exam form is "write a script that
uses an ad-hoc command", which grades both the script artifact and the
state it produces.
"""

import os
import random

from core.registry import TaskRegistry
from tasks.base import AnsibleTask
from validators import ansible_runner as runner


@TaskRegistry.register("adhoc")
class AdhocScriptTask(AnsibleTask):
    def __init__(self):
        super().__init__("adhoc_script_001", "adhoc", "easy")

    def generate(self, **params):
        marker = params.get("marker") or random.choice(
            ["/etc/motd.d/adhoc", "/var/tmp/adhoc_was_here", "/etc/adhoc.marker"])
        text = params.get("text") or random.choice(
            ["Managed by Ansible", "EX294 practice system", "Automation in effect"])
        self.params = {"marker": marker, "text": text}
        self.description = f"""
Create a shell script  adhoc.sh  in your working directory ({self.workdir})
that uses an Ansible AD-HOC command (not a playbook) to create the file
{marker}  on ALL managed nodes with exactly this content:

    {text}

The script must be executable and runnable as  ./adhoc.sh .
"""
        self.hints = [
            "ansible all -m ansible.builtin.copy -a 'content=\"...\" dest=...'",
            "copy's content= adds no trailing newline unless you include one.",
            "chmod +x adhoc.sh",
        ]
        return self

    def validate(self):
        res = self.result()
        script = self.workdir / "adhoc.sh"
        if not self.check_exists(res, "adhoc.sh"):
            return res
        res.add("adhoc.sh is executable", os.access(script, os.X_OK),
                "" if os.access(script, os.X_OK) else "chmod +x adhoc.sh")
        self.check_contains(res, "adhoc.sh", r"\bansible\b(?!-playbook).*-m\s",
                            "script uses an ad-hoc ansible command")
        if runner.have_ansible():
            out = runner.run(["bash", str(script)], cwd=self.workdir)
            res.add("adhoc.sh runs successfully", out.ok,
                    "" if out.ok else out.text.strip()[-300:])
            self.check_node_state(
                res, f"{self.params['marker']} has the required content on all nodes",
                "all", "ansible.builtin.command",
                f"cat {self.params['marker']}", expect=self.params["text"],
                become=True)
        return res


@TaskRegistry.register("adhoc")
class AdhocPackageFactsScriptTask(AnsibleTask):
    """Ad-hoc queries aren't limited to command/shell — package_facts is the
    module form of 'is this installed', and it's what the exam expects you
    to reach for instead of parsing rpm -q output."""

    def __init__(self):
        super().__init__("adhoc_pkgfacts_001", "adhoc", "medium")

    def generate(self, **params):
        pkg = params.get("pkg") or random.choice(["tar", "rsync", "vim-enhanced"])
        self.params = {"pkg": pkg, "outfile": "pkg_audit.txt"}
        self.description = f"""
Create a shell script  pkg_audit.sh  in your working directory
({self.workdir}) that uses a SINGLE ad-hoc command (not a playbook) with
the  ansible.builtin.package_facts  module against ALL managed nodes to
report whether the package  {pkg}  is installed, redirecting the raw
output to  {self.params['outfile']} .

The script must be executable and runnable as  ./pkg_audit.sh .
"""
        self.hints = [
            "ansible all -m ansible.builtin.package_facts -a 'manager=auto'",
            "package_facts populates ansible_facts.packages — it doesn't print "
            "a yes/no by itself, so pipe/tee the raw ad-hoc output to the file.",
            "Redirect with: ... > pkg_audit.sh's target file, or use tee.",
        ]
        return self

    def validate(self):
        res = self.result()
        script = self.workdir / "pkg_audit.sh"
        if not self.check_exists(res, "pkg_audit.sh"):
            return res
        res.add("pkg_audit.sh is executable", os.access(script, os.X_OK),
                "" if os.access(script, os.X_OK) else "chmod +x pkg_audit.sh")
        self.check_contains(res, "pkg_audit.sh", r"package_facts",
                            "script uses the package_facts module")
        if runner.have_ansible():
            out = runner.run(["bash", str(script)], cwd=self.workdir)
            res.add("pkg_audit.sh runs successfully", out.ok,
                    "" if out.ok else out.text.strip()[-300:])
            self.check_exists(res, self.params["outfile"])
        return res


@TaskRegistry.register("adhoc")
class AdhocHostPatternTask(AnsibleTask):
    """Host-pattern fluency: limit expressions, group math, and exclusion —
    the ad-hoc skill that makes 'run this everywhere EXCEPT...' possible."""

    def __init__(self):
        super().__init__("adhoc_pattern_001", "adhoc", "medium")

    def generate(self, **params):
        marker = params.get("marker") or "/var/tmp/prod_only.marker"
        self.params = {"marker": marker}
        self.description = f"""
Create a shell script  pattern.sh  in your working directory
({self.workdir}) that uses a SINGLE ad-hoc command targeting a HOST
PATTERN — every host in the  prod  group that is NOT ALSO in the  dev
group — to create the file  {marker}  with the content  prod-only .

If every prod host is also in dev on this inventory, the pattern must
still be written correctly (that's what's graded); the file simply won't
land anywhere, which is fine.

The script must be executable and runnable as  ./pattern.sh .
"""
        self.hints = [
            "Host pattern syntax: 'prod:!dev' excludes dev from prod.",
            "ansible 'prod:!dev' -m ansible.builtin.copy -a 'content=... dest=...'",
            "Quote the pattern — the shell would otherwise try to expand '!' itself.",
        ]
        return self

    def validate(self):
        res = self.result()
        script = self.workdir / "pattern.sh"
        if not self.check_exists(res, "pattern.sh"):
            return res
        res.add("pattern.sh is executable", os.access(script, os.X_OK),
                "" if os.access(script, os.X_OK) else "chmod +x pattern.sh")
        self.check_contains(res, "pattern.sh", r"prod:!dev|prod\s*:\s*!\s*dev",
                            "script uses the prod:!dev host pattern")
        if runner.have_ansible():
            out = runner.run(["bash", str(script)], cwd=self.workdir)
            res.add("pattern.sh runs successfully", out.ok,
                    "" if out.ok else out.text.strip()[-300:])
        return res
